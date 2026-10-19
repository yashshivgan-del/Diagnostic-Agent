"""Predictive Diagnostic Assistant - workshop backend (Starlette + psycopg).

One backend, one SPA, one PostgreSQL database, one Karini recipe. No login:
each Start creates a run_id; the dashboard shows that run's data live.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# On Windows, Python 3.8+ defaults to the Proactor event loop, which psycopg's async
# pool cannot use ("Psycopg cannot use the 'ProactorEventLoop' to run in async mode").
# Select the selector loop before anything creates an event loop. No effect on Linux/macOS,
# so the Docker/EC2 deployment is unchanged.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # shared `simulator` package
    sys.path.insert(0, str(ROOT))

from sse_starlette.sse import EventSourceResponse  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import FileResponse, JSONResponse  # noqa: E402
from starlette.routing import Mount, Route  # noqa: E402
from starlette.staticfiles import StaticFiles  # noqa: E402

from . import db, karini, live, views  # noqa: E402
from .config import normalize_recipe_id, settings  # noqa: E402
from .runs import RunManager  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
STATIC = Path(__file__).resolve().parents[1] / "static"
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
manager = RunManager()


@asynccontextmanager
async def lifespan(_app):
    await db.open_pool()
    await manager.recover_after_restart()
    await db.execute("UPDATE pda.karini_executions SET status = 'post_failed', finished_at = now(), updated_at = now(), "
                     "error = 'backend restarted while posting' WHERE status = 'posting'")
    wake = asyncio.Event()
    manager.bind_dispatcher(wake)
    tasks = [asyncio.create_task(karini.dispatcher_loop(wake), name="dispatcher"),
             asyncio.create_task(karini.poller_loop(), name="poller"),
             asyncio.create_task(live.listener_loop(), name="listener")]
    logging.getLogger("pda").info("backend up: inference=%s karini=%s", settings.inference_mode,
                                  "configured" if settings.karini_configured else "NOT configured")
    try:
        yield
    finally:
        await manager.shutdown()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await db.close_pool()


def err(status: int, msg: str) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=status)


def _run_id(request: Request) -> str | None:
    rid = request.path_params["run_id"]
    return rid if UUID_RE.match(rid) else None


# ----------------------------------------------------------------------------- routes
async def index(_request: Request):
    return FileResponse(STATIC / "index.html")


async def config(_request: Request):
    return JSONResponse(settings.public())


async def health(_request: Request):
    try:
        await db.fetch_one("SELECT 1 AS ok")
        return JSONResponse({"ok": True, "active_runs": len(manager.workers)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=503)


async def create_run(request: Request):
    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        return err(400, "invalid JSON body")
    email = str(body.get("email", "")).strip()
    label = (str(body.get("label") or "").strip() or None)
    if not EMAIL_RE.match(email) or len(email) > 254:
        return err(400, "please enter a valid email address")
    if label and len(label) > 60:
        return err(400, "label must be at most 60 characters")
    k = body.get("karini") or {}
    base_url = str(k.get("base_url") or "").strip().rstrip("/")
    recipe_id = normalize_recipe_id(str(k.get("recipe_id") or ""))
    api_token = str(k.get("api_token") or "").strip()
    given = [v for v in (base_url, recipe_id, api_token) if v]
    if given and len(given) != 3:
        return err(400, "to use your own recipe, provide the base URL, recipe ID and API token together")
    if base_url and not base_url.lower().startswith(("http://", "https://")):
        return err(400, "Karini base URL must start with http:// or https://")
    if len(base_url) > 300 or len(recipe_id) > 200 or len(api_token) > 400:
        return err(400, "Karini credentials are too long")
    karini_creds = {"base_url": base_url, "recipe_id": recipe_id, "api_token": api_token} if given else None
    try:
        run = await manager.create_run(email, label, karini_creds)
    except RuntimeError as exc:
        return err(429, str(exc))
    out = await views.run(str(run["run_id"]))
    out["access_token"] = run["access_token"]   # returned once; the browser keeps it
    return JSONResponse(out, status_code=201)


def _token(request: Request) -> str | None:
    return request.headers.get("x-run-token") or request.query_params.get("t")


async def _authorized(request: Request) -> str | None:
    """run_id if the request carries that run's access token, else None."""
    rid = _run_id(request)
    if rid and await views.check_token(rid, _token(request)):
        return rid
    return None


async def list_runs(request: Request):
    """POST {runs: {run_id: token, ...}} -> summaries of those runs (this browser's history)."""
    try:
        body = await request.json()
        pairs = {str(k): str(v) for k, v in dict(body.get("runs") or {}).items() if UUID_RE.match(str(k))}
    except (ValueError, TypeError, AttributeError):
        return err(400, "invalid JSON body")
    return JSONResponse(await views.history(dict(list(pairs.items())[:100])))


async def get_run(request: Request):
    rid = await _authorized(request)
    snap = await views.snapshot(rid) if rid else None
    return JSONResponse(snap) if snap else err(404, "run not found in this browser")


async def stop_run(request: Request):
    rid = await _authorized(request)
    if not rid:
        return err(404, "run not found in this browser")
    if not manager.stop(rid):
        return err(409, "run is not active")
    return JSONResponse({"ok": True, "status": "stopping"})


async def inject(request: Request):
    rid = await _authorized(request)
    if not rid:
        return err(404, "run not found in this browser")
    res = manager.inject(rid)
    if res == "injected":
        return JSONResponse({"ok": True, "status": "fault starts on the next reading"})
    if res == "fault_already_active":
        return err(409, "a fault is already developing; wait for the maintenance reset")
    return err(409, "run is not active")


async def stream(request: Request):
    rid = await _authorized(request)
    if not rid:
        return err(404, "run not found in this browser")
    q = live.broker.subscribe(rid)

    async def gen():
        try:
            yield {"event": "hello", "data": json.dumps({"run_id": rid})}
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(q.get(), timeout=10)
                except asyncio.TimeoutError:
                    continue
                yield {"event": item["kind"], "data": json.dumps(item["data"])}
        finally:
            live.broker.unsubscribe(rid, q)

    return EventSourceResponse(gen(), ping=15, headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


routes = [
    Route("/", index),
    Route("/run/{rest:path}", index),
    Route("/api/config", config),
    Route("/api/health", health),
    Route("/api/runs", create_run, methods=["POST"]),
    Route("/api/runs/history", list_runs, methods=["POST"]),
    Route("/api/runs/{run_id}", get_run),
    Route("/api/runs/{run_id}/stop", stop_run, methods=["POST"]),
    Route("/api/runs/{run_id}/inject", inject, methods=["POST"]),
    Route("/api/runs/{run_id}/stream", stream),
    Mount("/static", StaticFiles(directory=STATIC), name="static"),
]

app = Starlette(routes=routes, lifespan=lifespan)
