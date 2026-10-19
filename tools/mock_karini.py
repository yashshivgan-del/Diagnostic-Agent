#!/usr/bin/env python3
"""Mock Karini - for local development and instructor dry runs. NOT an LLM.

Implements the same webhook API as Karini:
  POST /api/webhook/recipe/{recipe_id}   header x-api-token  -> {"batch_status": "inProcess", "request_id", "recipe_id"}
  GET  /api/webhook/request/{request_id} header x-api-token  -> {"status", "response", "full_response": {...}}
and plays the two agents (evidence_gatherer + diagnostic_reporter) with fixed rules, calling the REAL pda.tool_* functions as the
pda_agent login, exactly in the order the skills prescribe. Use it to verify the database
contract, the backend dispatch/poll logic and the live dashboard before wiring Karini.

Run:
  MOCK_AGENT_DATABASE_URL=postgresql://pda_agent:...@host:5432/pda \
  MOCK_TOKEN=dev-token uvicorn tools.mock_karini:app --port 8090
Backend .env:
  KARINI_BASE_URL=http://localhost:8090  KARINI_RECIPE_ID=mock  KARINI_API_TOKEN=dev-token
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

if sys.platform == "win32":  # psycopg async needs the selector loop, not Windows' default Proactor loop
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import psycopg
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

DB_URL = os.getenv("MOCK_AGENT_DATABASE_URL", "postgresql://pda_agent:CHANGE_ME_agent_password@localhost:5432/pda")
TOKEN = os.getenv("MOCK_TOKEN", "dev-token")
STEP_DELAY = float(os.getenv("MOCK_STEP_DELAY_S", "2"))
FAIL_EVERY = int(os.getenv("MOCK_FAIL_EVERY", "0"))  # >0: every Nth request ends 'failed' (test the UI)
MARKER = "Final#$%Answer>:"
REQUESTS: dict[str, dict] = {}
COUNTER = {"n": 0}


async def call(conn, sql: str, *params):
    cur = await conn.execute(sql, params)
    row = await cur.fetchone()
    return row[0] if row else None


def diagnose(evidence: dict) -> dict:
    """Rule-based stand-in for Agent 2 (the real agent reasons with the fault-diagnosis skill)."""
    codes = {l["event_code"] for l in evidence["logs"]} | {m["event_code"] for m in evidence["maintenance_history"]}
    pred = evidence["event"]["prediction"]["predicted_fault"]
    rules = [
        ("misalignment", {"VIB-205", "MNT-610"}, "SOP-PUMP-105"),
        ("motor_overload", {"ELC-410", "ELC-412", "ELC-490"}, "SOP-PUMP-104"),
        ("seal_leak", {"SEL-510", "SEL-590", "PRS-306"}, "SOP-PUMP-103"),
        ("cavitation", {"PRS-305", "VIB-202"}, "SOP-PUMP-102"),
        ("bearing_wear", {"TMP-190", "VIB-290", "VIB-201", "TMP-110"}, "SOP-PUMP-101"),
    ]
    scored = []
    for fault, keys, sop in rules:
        hit = sorted(codes & keys)
        if fault == "misalignment" and hit == ["MNT-610"]:
            hit = []  # coupling work alone is not evidence
        if hit:
            scored.append((len(hit) + (1 if fault == pred else 0), fault, hit, sop))
    if not scored and pred and pred != "normal":
        scored.append((1, pred, [], dict((f, s) for f, _k, s in rules).get(pred, "SAFE-001")))
    scored.sort(reverse=True)
    log_ids = {l["event_code"]: l["log_id"] for l in evidence["logs"] + evidence["maintenance_history"]}
    hyps = []
    for rank, (score, fault, hit, sop) in enumerate(scored[:3], start=1):
        support = [f"log:{log_ids[c]}" for c in hit if c in log_ids] + [f"doc:{sop}"]
        hyps.append({"rank": rank, "cause": fault.replace("_", " "), "fault_category": fault,
                     "evidence_strength": "high" if score >= 3 else "medium" if score == 2 else "low",
                     "supporting": support, "contradicting": [],
                     "reasoning": f"log codes {', '.join(hit) or 'none'}; model class {pred}"})
    top_sop = scored[0][3] if scored else "SAFE-001"
    return {"summary": f"top hypothesis: {hyps[0]['cause']}" if hyps else "no hypothesis",
            "observed_facts": [{"statement": f"{l['event_code']}: {l['message']}", "sources": [f"log:{l['log_id']}"]}
                               for l in evidence["logs"][:5]],
            "hypotheses": hyps,
            "safe_checks": [{"check": f"Follow the inspection-only checks in {top_sop}", "source": top_sop}],
            "overall_confidence": hyps[0]["evidence_strength"] if hyps else "low",
            "model_agreement": "agrees" if hyps and hyps[0]["fault_category"] == pred else "disagrees",
            "uncertainties": ["MOCK diagnosis: fixed rules, not an LLM"], "additional_info_needed": []}


async def run_recipe(request_id: str, payload: dict) -> None:
    st = REQUESTS[request_id]
    meta = payload.get("metadata", {})
    eid = meta.get("event_id", "")
    try:
        async with await psycopg.AsyncConnection.connect(DB_URL, autocommit=True) as c:
            # ---------------- Agent 1: evidence_gatherer
            await asyncio.sleep(STEP_DELAY)
            ev = await call(c, "SELECT pda.tool_get_event(%s)", eid)
            if not ev.get("ok") or ev.get("status") == "already_processed":
                st.update(status="success", answer={"agent": "evidence_gatherer", "status": ev.get("status"),
                                                    "next": "End"})
                return
            logs = (await call(c, "SELECT pda.tool_get_logs(%s, 10)", eid))["logs"]
            hist = await call(c, "SELECT pda.tool_get_history(%s, 7)", eid)
            codes = " ".join(sorted({l["event_code"] for l in logs if l["level"] in ("WARN", "ERROR")}))
            q = f"{(ev['prediction']['predicted_fault'] or '').replace('_', ' ')} {codes} centrifugal pump"
            docs = (await call(c, "SELECT pda.tool_search_incidents(%s, %s)", eid, q))["documents"]
            warn = [l for l in logs if l["level"] in ("WARN", "ERROR")]
            evidence = {"status": "ready", "event": ev, "logs": logs, "maintenance_history": hist["maintenance_history"],
                        "recurring_warnings": hist["recurring_warnings_30d"],
                        "kb_refs": [{"doc_id": d["doc_id"], "type": d["type"], "title": d["title"],
                                     "excerpt": d["excerpt"][:200]} for d in docs],
                        "evidence_status": "sufficient" if warn and docs else "partial" if warn or docs else "none",
                        "summary": f"{len(warn)} warning/error logs, {len(docs)} knowledge-base documents"}
            await call(c, "SELECT pda.tool_record_output(%s, 'evidence_gatherer', %s::jsonb)",
                       eid, json.dumps({k: v for k, v in evidence.items() if k != "event"}))
            # ---------------- Agent 2: diagnostic_reporter (merged diagnosis + report + email)
            await asyncio.sleep(STEP_DELAY)
            diag = diagnose(evidence) if evidence["evidence_status"] != "none" else None
            report = {
                "summary": (f"{meta.get('machine_id')} anomaly (score {meta.get('anomaly_score')}). "
                            + (f"Most likely: {diag['hypotheses'][0]['cause']}." if diag and diag["hypotheses"]
                               else "No diagnosis: insufficient evidence.")),
                "severity": "high" if any(l["level"] == "ERROR" for l in logs) else "medium",
                "overall_confidence": diag["overall_confidence"] if diag else "low",
                "observed_facts": diag["observed_facts"] if diag else [],
                "hypotheses": diag["hypotheses"] if diag else [],
                "safe_checks": diag["safe_checks"] if diag else [],
                "evidence_gaps": [] if evidence["kb_refs"] else ["no knowledge-base match"],
                "uncertainties": ["MOCK run: no LLM involved"],
            }
            tag = "rpt_" + eid[:8]
            body = json.dumps(report).replace("$", "").replace("%", "%%")  # %% = literal % for psycopg
            async with c.transaction():
                await c.execute(f"SELECT pda.tool_save_report(%s, ${tag}${body}${tag}$::jsonb)", (eid,))
            last = await call(c, "SELECT pda.tool_last_result(%s, 'diagnostic_reporter')", eid)
            saved = last["result"] if last.get("tool") == "tool_save_report" else {"status": "failed"}
            email_status = "skipped"
            if saved.get("send_email"):
                await asyncio.sleep(STEP_DELAY / 2)
                # The real recipe sends saved["email"] with the Karini SMTP messaging tool here.
                email_status = "submitted"
                await call(c, "SELECT pda.tool_record_notification(%s, 'submitted', %s)", eid,
                           "MOCK: email not actually sent")
            # One combined output row for the merged agent: carry the diagnosis content (so the
            # dashboard shows hypotheses/safe checks) plus the report/email status.
            final = {"status": "done", "event_id": eid, "report_status": saved.get("status"),
                     "email_status": email_status,
                     "severity": report["severity"], "overall_confidence": report["overall_confidence"],
                     "top_hypothesis": report["hypotheses"][0]["cause"] if report["hypotheses"] else None,
                     "hypotheses": report["hypotheses"], "safe_checks": report["safe_checks"],
                     "observed_facts": report["observed_facts"], "uncertainties": report["uncertainties"],
                     "summary": "mock recipe completed"}
            await call(c, "SELECT pda.tool_record_output(%s, 'diagnostic_reporter', %s::jsonb)", eid, json.dumps(final))
        COUNTER["n"] += 1
        if FAIL_EVERY and COUNTER["n"] % FAIL_EVERY == 0:
            st.update(status="failed", error="MOCK: simulated recipe failure")
        else:
            st.update(status="success", answer=final)
    except Exception as exc:  # noqa: BLE001
        st.update(status="failed", error=f"{type(exc).__name__}: {exc}")


def _auth(request: Request) -> bool:
    return request.headers.get("x-api-token") == TOKEN


async def start(request: Request):
    if not _auth(request):
        return JSONResponse({"error": "invalid token"}, status_code=401)
    payload = await request.json()
    rid = str(uuid.uuid4())
    REQUESTS[rid] = {"status": "inProcess"}
    asyncio.create_task(run_recipe(rid, payload))
    return JSONResponse({"batch_status": "inProcess", "request_id": rid, "recipe_id": request.path_params["recipe_id"]})


async def status(request: Request):
    if not _auth(request):
        return JSONResponse({"error": "invalid token"}, status_code=401)
    st = REQUESTS.get(request.path_params["request_id"])
    if not st:
        return JSONResponse({"error": "unknown request"}, status_code=404)
    out = {"status": st["status"], "response": None}
    if st["status"] == "success":
        answer = f"{MARKER} {json.dumps(st['answer'])}"
        out.update(response=answer, full_response={"response": {"results": [{"final_answer": answer}]}})
    if st["status"] == "failed":
        out["error"] = st.get("error")
    return JSONResponse(out)


app = Starlette(routes=[Route("/api/webhook/recipe/{recipe_id}", start, methods=["POST"]),
                        Route("/api/webhook/request/{request_id}", status)])
