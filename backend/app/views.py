"""Read models for the dashboard (snapshot + single items pushed live).

Ground truth (the simulator's real fault) is revealed for an event only once a diagnosis
exists for it (Agent 2 output or a saved report), or after the run has ended.
"""
from __future__ import annotations

import hmac
import json
from typing import Any

from . import db

READING_SQL = """
SELECT e.event_id, e.seq, e.ts, e.telemetry, e.ground_truth,
       p.inference_mode, p.inference_status, p.anomaly_score, p.threshold, p.is_anomaly, p.confirmed,
       p.predicted_fault, p.fault_probabilities, p.trigger_decision, p.error AS inference_error, p.latency_ms
  FROM pda.machine_events e JOIN pda.model_predictions p USING (event_id)
"""

EXEC_COLS = ("event_id, run_id, status, karini_status, request_id, http_status, final_answer, error, attempts, "
             "poll_count, created_at, posted_at, finished_at, updated_at, payload")
REPORT_COLS = ("event_id, run_id, report, report_markdown, top_hypothesis, overall_confidence, severity, "
               "email_to, email_subject, email_status, email_detail, created_at, updated_at")


def mask_email(e: str | None) -> str | None:
    if not e or "@" not in e:
        return e
    user, dom = e.split("@", 1)
    return (user[:2] + "***" if len(user) > 2 else user[:1] + "***") + "@" + dom


def jsonable(obj: Any) -> Any:
    return json.loads(json.dumps(obj, default=str))


def _run_public(r: dict) -> dict:
    out = {k: r[k] for k in ("run_id", "label", "machine_id", "status", "stop_reason", "inference_mode", "threshold",
                             "email_cap", "emails_sent", "trigger_count", "started_at", "auto_stop_at", "stopped_at")}
    out["email_masked"] = mask_email(r["notify_email"])
    out["karini_custom"] = bool(r.get("karini_recipe_id"))   # run uses its own recipe (token never exposed)
    return out


async def run(run_id: str) -> dict | None:
    r = await db.fetch_one("SELECT * FROM pda.runs WHERE run_id = %s", (run_id,))
    return jsonable(_run_public(r)) if r else None


async def _revealed_events(run_id: str, run_status: str) -> set[str] | None:
    """None = reveal everything (run ended)."""
    if run_status != "running":
        return None
    rows = await db.fetch_all(
        "SELECT event_id::text AS id FROM pda.diagnostic_reports WHERE run_id = %s "
        "UNION SELECT event_id::text FROM pda.agent_traces WHERE run_id = %s AND kind = 'output' "
        "AND agent = 'diagnostic_reporter'", (run_id, run_id))
    return {r["id"] for r in rows}


def _gate(reading: dict, revealed: set[str] | None) -> dict:
    eid = str(reading["event_id"])
    if revealed is not None and eid not in revealed:
        reading["ground_truth"] = None
    return reading


async def reading(run_id: str, event_id: str) -> dict | None:
    r = await db.fetch_one(READING_SQL + " WHERE e.event_id = %s AND e.run_id = %s", (event_id, run_id))
    if not r:
        return None
    logs = await db.fetch_all("SELECT log_id, ts, log_level, event_code, message, source FROM pda.machine_logs "
                              "WHERE event_id = %s ORDER BY ts, log_id", (event_id,))
    st = await db.fetch_one("SELECT status FROM pda.runs WHERE run_id = %s", (run_id,))
    r["logs"] = logs
    return jsonable(_gate(r, await _revealed_events(run_id, st["status"])))


async def execution(run_id: str, event_id: str) -> dict | None:
    r = await db.fetch_one(f"SELECT {EXEC_COLS} FROM pda.karini_executions WHERE event_id = %s AND run_id = %s",
                           (event_id, run_id))
    if r and r.get("payload"):
        r["payload"]["metadata"]["notify_email"] = mask_email(r["payload"]["metadata"].get("notify_email"))
    return jsonable(r) if r else None


async def trace(run_id: str, trace_id: int) -> dict | None:
    r = await db.fetch_one("SELECT * FROM pda.agent_traces WHERE trace_id = %s AND run_id = %s", (trace_id, run_id))
    return jsonable(r) if r else None


async def report(run_id: str, event_id: str) -> dict | None:
    r = await db.fetch_one(f"SELECT {REPORT_COLS} FROM pda.diagnostic_reports WHERE event_id = %s AND run_id = %s",
                           (event_id, run_id))
    if not r:
        return None
    r["email_to"] = mask_email(r["email_to"])
    return jsonable(r)


async def truth(run_id: str, event_id: str) -> dict | None:
    r = await db.fetch_one("SELECT event_id, ground_truth FROM pda.machine_events WHERE event_id = %s AND run_id = %s",
                           (event_id, run_id))
    return jsonable(r) if r else None


async def snapshot(run_id: str) -> dict | None:
    rrow = await db.fetch_one("SELECT * FROM pda.runs WHERE run_id = %s", (run_id,))
    if not rrow:
        return None
    revealed = await _revealed_events(run_id, rrow["status"])
    readings = await db.fetch_all(READING_SQL + " WHERE e.run_id = %s ORDER BY e.seq", (run_id,))
    readings = [_gate(r, revealed) for r in readings]
    logs = await db.fetch_all("SELECT log_id, event_id, ts, log_level, event_code, message, source FROM pda.machine_logs "
                              "WHERE run_id = %s ORDER BY ts DESC, log_id DESC LIMIT 400", (run_id,))
    execs = await db.fetch_all(f"SELECT {EXEC_COLS} FROM pda.karini_executions WHERE run_id = %s ORDER BY created_at",
                               (run_id,))
    for x in execs:
        x["payload"]["metadata"]["notify_email"] = mask_email(x["payload"]["metadata"].get("notify_email"))
    traces = await db.fetch_all("SELECT * FROM pda.agent_traces WHERE run_id = %s ORDER BY trace_id", (run_id,))
    reports = await db.fetch_all(f"SELECT {REPORT_COLS} FROM pda.diagnostic_reports WHERE run_id = %s", (run_id,))
    for rep in reports:
        rep["email_to"] = mask_email(rep["email_to"])
    return jsonable({"run": _run_public(rrow), "readings": readings, "logs": logs, "executions": execs,
                     "traces": traces, "reports": reports})


async def check_token(run_id: str, token: str | None) -> bool:
    """A run is visible and controllable only with the token handed to the browser that started it."""
    if not token:
        return False
    r = await db.fetch_one("SELECT access_token FROM pda.runs WHERE run_id = %s", (run_id,))
    return bool(r) and hmac.compare_digest(r["access_token"], token)


async def history(run_tokens: dict[str, str]) -> list[dict]:
    """Summaries of the runs this browser started (ids + tokens it kept in localStorage)."""
    if not run_tokens:
        return []
    rows = await db.fetch_all(
        "SELECT r.*, (SELECT count(*) FROM pda.machine_events e WHERE e.run_id = r.run_id) AS readings, "
        "(SELECT count(*) FROM pda.karini_executions x WHERE x.run_id = r.run_id) AS executions, "
        "(SELECT count(*) FROM pda.diagnostic_reports d WHERE d.run_id = r.run_id) AS reports "
        "FROM pda.runs r WHERE r.run_id = ANY(%s::uuid[]) ORDER BY r.started_at DESC LIMIT 100",
        (list(run_tokens.keys()),))
    rows = [r for r in rows if hmac.compare_digest(r["access_token"], run_tokens.get(str(r["run_id"]), ""))]
    out = []
    for r in rows:
        item = _run_public(r)
        item.update(readings=r["readings"], executions=r["executions"], reports=r["reports"])
        out.append(item)
    return jsonable(out)
