"""Karini webhook dispatcher + status poller (one shared recipe for all runs).

Karini webhook API (Karini framework guide):
  start : POST {base}/api/webhook/recipe/{recipe_id}   header x-api-token  -> {"batch_status", "request_id", ...}
  status: GET  {base}/api/webhook/request/{request_id}  header x-api-token  -> {"status": inProcess|success|failed, ...}
The final answer is at full_response.response.results[0].final_answer and starts with "Final#$%Answer>:".

Execution states (pda.karini_executions.status):
  queued -> posting -> accepted -> success | failed | timed_out
                    -> post_failed
The agents' real work (traces, report, email status) is written by the agents themselves
into PostgreSQL through pda.tool_* functions; polling only gives each execution a final state.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time

import requests
from psycopg.types.json import Jsonb

from . import db
from .config import settings

log = logging.getLogger("pda.karini")
_tasks: set[asyncio.Task] = set()   # keep references so in-flight posts are not garbage-collected
MARKER = "Final#$%Answer>:"


def _headers(api_token: str) -> dict:
    return {"Content-Type": "application/json", "x-api-token": api_token}


def parse_final_answer(raw) -> tuple[object | None, str | None]:
    """Strip the Karini marker and code fences, then try JSON."""
    if raw is None:
        return None, None
    text = raw if isinstance(raw, str) else json.dumps(raw)
    if MARKER in text:
        text = text.split(MARKER, 1)[1]
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip())
    try:
        return json.loads(text), text
    except ValueError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0)), text
            except ValueError:
                pass
    return None, text


def _extract_final(resp: dict):
    try:
        return resp["full_response"]["response"]["results"][0]["final_answer"]
    except (KeyError, IndexError, TypeError):
        return resp.get("response")


# ----------------------------------------------------------------------------- HTTP (sync, run in threads)
def _post(payload: dict, creds: dict) -> dict:
    url = f"{creds['base_url']}/api/webhook/recipe/{creds['recipe_id']}"
    attempts = []
    for attempt in range(1, settings.karini_post_retries + 1):
        try:
            r = requests.post(url, json=payload, headers=_headers(creds["api_token"]),
                              timeout=settings.karini_post_timeout_s)
            try:
                body = r.json()
            except ValueError:
                body = {"raw": r.text[:2000]}
            attempts.append(r.status_code)
            if r.status_code < 300 and isinstance(body, dict) and body.get("request_id"):
                return {"ok": True, "http_status": r.status_code, "body": body, "attempts": attempt}
            if r.status_code < 300:
                return {"ok": False, "http_status": r.status_code, "body": body, "attempts": attempt,
                        "error": "webhook accepted the call but returned no request_id"}
            if r.status_code < 500 and r.status_code != 429:
                return {"ok": False, "http_status": r.status_code, "body": body, "attempts": attempt,
                        "error": f"webhook rejected the request (HTTP {r.status_code})"}
        except requests.RequestException as exc:
            attempts.append(type(exc).__name__)
        if attempt < settings.karini_post_retries:
            time.sleep(2 ** (attempt - 1))
    return {"ok": False, "http_status": None, "body": None, "attempts": len(attempts),
            "error": f"webhook unreachable after {len(attempts)} attempts: {attempts}"}


def _status(request_id: str, creds: dict) -> dict:
    url = f"{creds['base_url']}/api/webhook/request/{request_id}"
    r = requests.get(url, headers=_headers(creds["api_token"]), timeout=settings.karini_post_timeout_s)
    r.raise_for_status()
    return r.json()


# ----------------------------------------------------------------------------- dispatcher
async def dispatcher_loop(wake: asyncio.Event) -> None:
    """Posts queued executions, never more than KARINI_MAX_CONCURRENT in flight."""
    while True:
        try:
            await _dispatch_once()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("dispatcher iteration failed")
        try:
            await asyncio.wait_for(wake.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pass
        wake.clear()


async def _dispatch_once() -> None:
    if not settings.karini_enabled:
        await db.execute(
            "UPDATE pda.karini_executions SET status = 'post_failed', finished_at = now(), updated_at = now(), "
            "error = 'Karini is disabled on the backend (KARINI_ENABLED=false)' "
            "WHERE status = 'queued'")
        return
    inflight = await db.fetch_one(
        "SELECT count(*) AS n FROM pda.karini_executions WHERE status IN ('posting', 'accepted')")
    free = settings.karini_max_concurrent - int(inflight["n"])
    if free <= 0:
        return
    async with db.pool.connection() as c:
        async with c.transaction():
            cur = await c.execute(
                "SELECT event_id FROM pda.karini_executions WHERE status = 'queued' "
                "ORDER BY created_at LIMIT %s FOR UPDATE SKIP LOCKED", (free,))
            ids = [r["event_id"] for r in await cur.fetchall()]
            if ids:
                await c.execute("UPDATE pda.karini_executions SET status = 'posting', updated_at = now() "
                                "WHERE event_id = ANY(%s)", (ids,))
    for eid in ids:
        t = asyncio.create_task(_post_one(eid))
        _tasks.add(t)
        t.add_done_callback(_tasks.discard)


async def _post_one(event_id) -> None:
    try:
        await _post_one_inner(event_id)
    except Exception as exc:  # noqa: BLE001 - never leave a row in 'posting'
        log.exception("posting %s failed", event_id)
        await db.execute("UPDATE pda.karini_executions SET status = 'post_failed', error = %s, finished_at = now(), "
                         "updated_at = now() WHERE event_id = %s AND status = 'posting'",
                         (f"backend error while posting: {type(exc).__name__}"[:500], event_id))


async def _post_one_inner(event_id) -> None:
    row = await db.fetch_one(
        "SELECT x.payload, r.karini_base_url, r.karini_recipe_id, r.karini_api_token "
        "FROM pda.karini_executions x JOIN pda.runs r ON r.run_id = x.run_id WHERE x.event_id = %s", (event_id,))
    creds = settings.karini_creds_for(row)
    if creds is None:
        await db.execute(
            "UPDATE pda.karini_executions SET status = 'post_failed', finished_at = now(), updated_at = now(), "
            "error = 'no Karini credentials for this run (set them at Start, or configure the backend env)' "
            "WHERE event_id = %s AND status = 'posting'", (event_id,))
        return
    res = await asyncio.to_thread(_post, row["payload"], creds)
    if res["ok"]:
        await db.execute(
            "UPDATE pda.karini_executions SET status = 'accepted', request_id = %s, http_status = %s, response = %s, "
            "karini_status = %s, attempts = %s, posted_at = now(), updated_at = now() WHERE event_id = %s",
            (res["body"]["request_id"], res["http_status"], Jsonb(res["body"]), res["body"].get("batch_status"),
             res["attempts"], event_id))
    else:
        await db.execute(
            "UPDATE pda.karini_executions SET status = 'post_failed', http_status = %s, response = %s, error = %s, "
            "attempts = %s, finished_at = now(), updated_at = now() WHERE event_id = %s",
            (res["http_status"], Jsonb(res["body"]) if res["body"] is not None else None, res["error"],
             res["attempts"], event_id))


# ----------------------------------------------------------------------------- poller
async def poller_loop() -> None:
    while True:
        try:
            await _poll_once()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("poller iteration failed")
        await asyncio.sleep(max(2.0, settings.karini_poll_interval_s / 3))


async def _poll_once() -> None:
    await db.execute(
        "UPDATE pda.karini_executions SET status = 'post_failed', finished_at = now(), updated_at = now(), "
        "error = 'posting did not complete' WHERE status = 'posting' AND updated_at < now() - interval '3 minutes'")
    await db.execute(
        "UPDATE pda.karini_executions SET status = 'timed_out', finished_at = now(), updated_at = now(), "
        "error = 'no final status from Karini within ' || %s || ' s' "
        "WHERE status = 'accepted' AND posted_at < now() - make_interval(secs => %s)",
        (settings.karini_execution_timeout_s, settings.karini_execution_timeout_s))
    due = await db.fetch_all(
        "SELECT x.event_id, x.request_id, r.karini_base_url, r.karini_recipe_id, r.karini_api_token "
        "FROM pda.karini_executions x JOIN pda.runs r ON r.run_id = x.run_id WHERE x.status = 'accepted' "
        "AND (x.last_polled_at IS NULL OR x.last_polled_at < now() - make_interval(secs => %s)) "
        "ORDER BY x.last_polled_at NULLS FIRST LIMIT 20", (settings.karini_poll_interval_s,))
    for row in due:
        creds = settings.karini_creds_for(row)
        if creds is None:
            await db.execute("UPDATE pda.karini_executions SET last_polled_at = now(), poll_count = poll_count + 1, "
                             "error = 'no Karini credentials for this run to poll status', updated_at = now() "
                             "WHERE event_id = %s", (row["event_id"],))
            continue
        try:
            resp = await asyncio.to_thread(_status, row["request_id"], creds)
        except Exception as exc:  # noqa: BLE001 - keep polling until timeout
            await db.execute("UPDATE pda.karini_executions SET last_polled_at = now(), poll_count = poll_count + 1, "
                             "error = %s, updated_at = now() WHERE event_id = %s",
                             (f"status poll failed: {type(exc).__name__}: {exc}"[:500], row["event_id"]))
            continue
        status = str(resp.get("status", "")).strip()
        if status.lower() == "success":
            parsed, raw = parse_final_answer(_extract_final(resp))
            await db.execute(
                "UPDATE pda.karini_executions SET status = 'success', karini_status = %s, final_answer = %s, "
                "final_answer_raw = %s, error = NULL, last_polled_at = now(), poll_count = poll_count + 1, "
                "finished_at = now(), updated_at = now() WHERE event_id = %s",
                (status, Jsonb(parsed) if parsed is not None else None, (raw or "")[:20000], row["event_id"]))
        elif status.lower() == "failed":
            await db.execute(
                "UPDATE pda.karini_executions SET status = 'failed', karini_status = %s, response = %s, "
                "error = %s, last_polled_at = now(), poll_count = poll_count + 1, finished_at = now(), "
                "updated_at = now() WHERE event_id = %s",
                (status, Jsonb(resp), str(resp.get("error") or resp.get("response") or "recipe failed")[:500],
                 row["event_id"]))
        else:
            await db.execute(
                "UPDATE pda.karini_executions SET karini_status = %s, last_polled_at = now(), error = NULL, "
                "poll_count = poll_count + 1, updated_at = now() WHERE event_id = %s",
                (status or "unknown", row["event_id"]))
