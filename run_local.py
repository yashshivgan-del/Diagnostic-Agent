#!/usr/bin/env python3
"""Local launcher for the backend on Windows.

Why this exists: on Windows, psycopg's async pool cannot run on the Proactor event loop,
and uvicorn 0.53 hardcodes `asyncio.ProactorEventLoop` on Windows (uvicorn/loops/asyncio.py),
so neither an event-loop policy nor `--loop asyncio` changes it. This launcher skips uvicorn's
loop factory entirely: it builds a SelectorEventLoop itself and runs uvicorn's Server on it.

Usage (PowerShell), from the repo root:
    python run_local.py
Reads .env automatically. The Linux Docker image still uses the plain uvicorn CLI (uvloop),
so this file only matters for a bare-metal Windows run.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


def main() -> None:
    _load_dotenv(ROOT / ".env")
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    config = uvicorn.Config("backend.app.main:app", host=host, port=port, loop="none")
    server = uvicorn.Server(config)

    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop()  # psycopg async needs this, not Proactor
    else:
        loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(server.serve())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
