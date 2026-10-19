"""Live updates: Postgres LISTEN 'pda_live' -> per-run subscribers -> Server-Sent Events.

Triggers in 01_schema.sql raise a NOTIFY for every row the dashboard shows, whoever wrote it
(the backend or a Karini agent through pda.tool_*). Only browsers subscribed to that run_id
receive the item.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict

import psycopg

from . import views
from .config import settings

log = logging.getLogger("pda.live")


class Broker:
    def __init__(self):
        self.subs: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self.subs[run_id].add(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        self.subs[run_id].discard(q)
        if not self.subs[run_id]:
            self.subs.pop(run_id, None)

    def publish(self, run_id: str, kind: str, data: dict) -> None:
        for q in list(self.subs.get(run_id, ())):
            try:
                q.put_nowait({"kind": kind, "data": data})
            except asyncio.QueueFull:
                # slow client: drop the backlog and tell it to reload the snapshot
                while not q.empty():
                    q.get_nowait()
                q.put_nowait({"kind": "resync", "data": {}})


broker = Broker()


async def _item_for(note: dict) -> list[tuple[str, dict]]:
    run_id, table = note.get("run_id"), note.get("table")
    eid = note.get("event_id")
    if table == "model_predictions":
        r = await views.reading(run_id, eid)
        return [("reading", r)] if r else []
    if table == "karini_executions":
        r = await views.execution(run_id, eid)
        return [("execution", r)] if r else []
    if table == "agent_traces":
        r = await views.trace(run_id, int(note["trace_id"]))
        out = [("trace", r)] if r else []
        if r and r["kind"] == "output" and r["agent"] == "diagnostic_reporter":
            t = await views.truth(run_id, eid)
            if t:
                out.append(("truth", t))
        return out
    if table == "diagnostic_reports":
        r = await views.report(run_id, eid)
        out = [("report", r)] if r else []
        t = await views.truth(run_id, eid)
        if t:
            out.append(("truth", t))
        return out
    if table == "runs":
        r = await views.run(run_id)
        return [("run", r)] if r else []
    return []


async def listener_loop() -> None:
    backoff = 1
    while True:
        try:
            async with await psycopg.AsyncConnection.connect(settings.database_url, autocommit=True) as conn:
                await conn.execute("LISTEN pda_live")
                log.info("listening on pda_live")
                backoff = 1
                async for n in conn.notifies():
                    try:
                        note = json.loads(n.payload)
                    except ValueError:
                        continue
                    run_id = note.get("run_id")
                    if not run_id or run_id not in broker.subs:
                        continue
                    for kind, data in await _item_for(note):
                        broker.publish(run_id, kind, data)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - reconnect
            log.exception("listener failed; reconnecting in %s s", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
