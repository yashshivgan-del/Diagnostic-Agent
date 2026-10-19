---
inclusion: always
---
# Tech stack and conventions

## Backend (`backend/app`)
- Python 3.11+, **Starlette** (not FastAPI), uvicorn, sse-starlette, psycopg 3 async + psycopg_pool, boto3, numpy, requests.
- Single process runs everything: `RunManager` / `RunWorker` (simulation loop per run), `karini.dispatcher_loop` + `poller_loop`, `live.listener_loop` (Postgres `LISTEN pda_live`) -> `Broker` -> SSE per run.
- Each tick is ONE transaction: insert event, logs, execution row (if triggered), prediction last.
- Karini executions table is the queue: dispatcher uses `FOR UPDATE SKIP LOCKED`; statuses queued -> posting -> accepted -> success|failed|timed_out, or post_failed. `posting` times out after 3 min, `accepted` after 600 s.
- Restart recovery: `recover_after_restart` marks orphaned runs `interrupted`.

## Karini integration (from Karini framework guide)
- Trigger: `POST {KARINI_BASE_URL}/api/webhook/recipe/{recipe_id}`, header `x-api-token`, body `{input_message, files, metadata}`.
- Poll: `GET /api/webhook/request/{id}`; answer at `full_response.response.results[0].final_answer`, after marker `Final#$%Answer>:`.
- One router (`entry_router`) answers `{"next":"<node>"}`. Literal braces in prompts are doubled `{{ }}`. Node variables: `{metadata}` (entry_router), `{evidence_result}` (diagnostic_reporter). Merged system: evidence_gatherer -> diagnostic_reporter (plain edge, no evidence_router).
- Agents use the Karini **database tool** (login `pda_agent`) and may only call `pda.tool_*` functions. Write pattern:
  `BEGIN; SELECT pda.tool_x(...); COMMIT; SELECT pda.tool_last_result('<event_id>','<agent>');`
  A write succeeded only if `tool_last_result.tool` equals the function just called. JSON passed with dollar-quote tags `$rp_<8chars>$...$rp_<8chars>$`.
- Retrieval/diagnosis/report logic lives in SKILLS (`karini/skills/*/SKILL.md`), not Python tools.

## Database (Postgres 16 / RDS)
- Schema `pda`. Logins: `pda_app` (backend; SELECT/INSERT/UPDATE on tables), `pda_agent` (EXECUTE on 8 SECURITY DEFINER `tool_*` functions only, pinned search_path).
- Triggers call `notify_change()` -> NOTIFY `pda_live` with `{run_id, type, ...}`.
- SQL files must stay DBeaver-friendly: no blank lines inside function bodies. Apply order 01 -> 02 -> 03 -> 04 (or `all_in_one.sql`). RDS master is NOT superuser — test with a non-superuser owner having CREATEROLE.
- Never `TRUNCATE pda.runs CASCADE` (wipes seed logs where `run_id IS NULL`); use `DELETE FROM pda.runs`.

## Frontend (`backend/static`)
- Vanilla JS SPA, no build. Always `esc()` inserted values; use `arr()` for possibly-malformed arrays. SVG charts. Handles SSE `resync` by refetching snapshot.
- Run token: `x-run-token` header for stop/inject; `?t=` on stream; `POST /api/runs/history` with tokens.

## ML (`ml/`)
- SageMaker built-in RCF (anomaly score, standardized via `RCF_SCALER_JSON`) and XGBoost `multi:softprob` (fault class). Data in `data/training/*.csv` from `data/generate_data.py`.

## Common commands
- Local full demo (no AWS/Karini): `cp .env.example .env && docker compose up --build` -> http://localhost:8000 (mock Karini at `tools/mock_karini.py`, `KARINI_RECIPE_ID=mock`, `KARINI_API_TOKEN=dev-token`).
- Regenerate data/seed: `python data/generate_data.py` (rewrites `db/04_seed.sql`, KB docs, training CSVs). Then rebuild `db/all_in_one.sql` = cat 01..04.
- Rebuild skill zips after editing a SKILL.md: zip `karini/skills/<name>/` into `karini/skills_zip/<name>.zip`.
- Train: `python ml/train_rcf.py`, `python ml/train_xgboost.py`; local check `python ml/local_model_check.py`; teardown `python ml/cleanup.py`.
- Prod: `deploy/docker-compose.prod.yml` + Caddy (`flush_interval -1` required for SSE).
