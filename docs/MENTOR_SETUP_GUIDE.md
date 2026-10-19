# Mentor setup guide — Predictive Diagnostic Assistant (PDA) workshop

Hand this to whoever is standing the workshop up on a new machine. It is the short, current path:
clone → local dry run → RDS → Karini recipe → deploy. It reflects the **current** architecture
(2 agents, 2 knowledge-base tools, SMTP email, per-run Karini credentials, playground sandbox IDs).

The long reference is `docs/SETUP_GUIDE.md`. Where that file and this one differ, **this one is current**
(the long guide still describes the older 3-agent / 5-prompt layout).

---

## 0. What you are standing up

```
Student browser ─► Backend + dashboard (one host, HTTPS)
                     │ every 10 s per run: simulate PUMP-01 → score → store
                     │ confirmed anomaly (2 of last 3) → POST Karini webhook
                     ▼
                   PostgreSQL (schema pda)  ◄── Karini agents call pda.tool_* functions (login pda_agent)
                     │ NOTIFY on every change
                     ▼
                   Backend streams each run live to its own browser (SSE)
```

Two Karini agents (merged from the old three):
- **`evidence_gatherer`** — pulls this run's event, logs, history from the DB and searches two KBs.
- **`diagnostic_reporter`** — diagnoses, saves the report, emails it, records the outcome.

No login. A run is identified by a secret token kept in the browser. Agents never touch tables; they
only call 8 `pda.tool_*` functions.

---

## 1. Get the code onto the new machine

The project is self-contained in this folder. Copy it across by whichever is easiest:
- `docs/pda-workshop.zip` already in this repo, or
- `git clone <your repo>`, or
- `scp` / a USB copy of the `pda-workshop` folder.

Prerequisites on the new machine:
- **Docker Desktop** (for the local dry run and for the production compose).
- **DBeaver** (to load the database onto RDS).
- Optional for the ML path: Python 3.11+ and AWS credentials.

Never copy a real `.env` — it holds secrets. Each machine starts from `.env.example`.

---

## 2. Local dry run (no AWS, no Karini) — 15 min

This proves the whole contract before you touch any cloud service.

```bash
cp .env.example .env
docker compose up --build
```

Open http://localhost:8000 → **Start run** → enter any email → **Inject fault now**.
Within ~30 s the score should cross the threshold, an agent card appears, the stages turn green, and
the card ends with the actual fault and a ✓.

What ran: Postgres 16 with `db/01`–`04` applied automatically, the backend in `INFERENCE_MODE=synthetic`,
and the **mock Karini** (`tools/mock_karini.py`) playing both agents against the real `pda.tool_*`
functions. Faster loop: `SIM_INTERVAL_S=2 RUN_MAX_SECONDS=120 docker compose up`.

If this works, the database schema, functions, dispatch, polling and live dashboard are all good.

---

## 3. Create the RDS PostgreSQL database — 15 min

AWS console → RDS → Create database:

| Setting | Value |
| --- | --- |
| Engine | PostgreSQL 16 |
| Template | Dev/Test, single-AZ |
| Instance | `db.t4g.small` (class of 30); `db.t4g.micro` for a dry run |
| Storage | 20 GB gp3 |
| Identifier | `pda-workshop` |
| Master user / password | e.g. `postgres` / a strong password (this is the schema owner that runs 01–04) |
| Initial database | the default `postgres` database; everything lives in schema `pda` inside it |
| Public access | **Yes**, so Karini can reach it — then restrict with the security group |
| Encryption | on |

**Security group**, inbound TCP 5432, allow only:
- the backend host's security group (step 6),
- your own IP (for DBeaver),
- the outbound IPs of your Karini environment (ask Karini support; prod and sandbox differ).

Never open 5432 to `0.0.0.0/0`.

> The reference deployment uses host `load-opt-demo.cr0wcueo0rpo.us-east-1.rds.amazonaws.com:5432`,
> database `postgres`, schema `pda`. Your new instance will have its own endpoint — use it everywhere
> the guide says "RDS endpoint".

---

## 4. Load the database with DBeaver — 10 min

1. **New connection → PostgreSQL**: host = RDS endpoint, port 5432, database `postgres`, user = master
   user. SSL tab → mode `require`. Test, Finish.
2. Open `db/03_roles.sql` and **change the two passwords** (`pda_app` and `pda_agent`). Save. Keep them;
   you need `pda_app` in `.env` and `pda_agent` in the Karini DB tool.
3. Run **`db/all_in_one.sql`** (it is `01`+`02`+`03`+`04` concatenated — edit the passwords inside it
   first), or run `01` → `02` → `03` → `04` individually. For each: File → Open → pick the connection →
   **Execute SQL Script (Alt+X)**, not Execute Statement.

   | File | Creates |
   | --- | --- |
   | `db/01_schema.sql` | schema `pda`, 8 tables, live-update triggers |
   | `db/02_agent_functions.sql` | the 8 `pda.tool_*` functions (incl. the playground sandbox branches) |
   | `db/03_roles.sql` | logins `pda_app` (backend) and `pda_agent` (Karini) + grants |
   | `db/04_seed.sql` | PUMP-01 history relative to `now()` + 27 KB documents |

4. If DBeaver splits a function ("unterminated dollar-quoted string"): Preferences → Editors → SQL
   Editor → SQL Processing → **"Blank line is statement delimiter" = Never**, then rerun. Re-running is safe.
5. Verify (expect `t f f t`, then the counts):
   ```sql
   SELECT has_function_privilege('pda_agent','pda.tool_get_event(text)','EXECUTE') AS agent_tool,
          has_table_privilege('pda_agent','pda.machine_logs','SELECT')             AS agent_table,
          has_function_privilege('pda_app','pda.tool_get_event(text)','EXECUTE')    AS app_tool,
          has_table_privilege('pda_app','pda.runs','INSERT')                        AS app_runs;
   SELECT count(*) FROM pda.machine_logs;   -- 272 seed rows
   SELECT count(*) FROM pda.kb_documents;   -- 27
   ```
6. **Sandbox check** (lets Karini trainees draft prompts with no live data — new in this build):
   ```sql
   SELECT pda.tool_get_event('e5000000-0000-4000-8000-000000000001');  -- sandbox:true, misalignment
   ```
   If this returns `"sandbox": true`, `02_agent_functions.sql` loaded correctly.

Re-seed note: seed timestamps are relative to `now()`. If the workshop is more than a week after
setup, rerun `04_seed.sql` so the 7-/30-day history stays recent.

---

## 5. Build the Karini recipe — 45–60 min

All source is in `karini/`. Canvas layout and edges: `karini/recipe/RECIPE_LAYOUT.md`.
Full tool details (descriptions to paste, SMTP fields, sandbox IDs): `karini/tools/TOOLS.md`.

### 5.1 Tools
| Tool | Type | Attach to | Notes |
| --- | --- | --- | --- |
| `pda_database` | Database (PostgreSQL), login **`pda_agent`** | both agents | May only run `pda.tool_*`. Paste the description from TOOLS.md |
| `pda_incidents_kb` | Knowledge Base, dataset "PDA incidents" | `evidence_gatherer` | Upload `data/knowledge_base/incidents/*.md` (20 files) |
| `pda_procedures_kb` | Knowledge Base, dataset "PDA procedures-V1" | `evidence_gatherer` | Upload `data/knowledge_base/procedures/*.md` (7 files) |
| `maintenance_email` | Messaging (SMTP, sender `no-reply@karini.ai`) | `diagnostic_reporter` | SMTP host/port/app-password live only in the Karini tool config |

- Run **`karini/test/db_tool_acceptance.md`** through `pda_database`. All 8 checks must pass before anything else.
- Keep each KB file's **name as the document title** — it starts with the doc ID the agents cite.
- Verify KB search: `pda_incidents_kb` for "axial vibration coupling misalignment" returns `INC-*`;
  `pda_procedures_kb` for "shaft alignment troubleshooting" returns `SOP-`/`REF-`/`SAFE-`. If a KB is
  unavailable, set `INCIDENT_SEARCH: database` in the `evidence-retrieval` skill and re-zip; the agent
  then full-text-searches the same docs in Postgres.

### 5.2 Skills
Upload the three zips from `karini/skills_zip/`:

| Skill zip | Attach to |
| --- | --- |
| `evidence-retrieval.zip` | `evidence_gatherer` |
| `fault-diagnosis.zip` | `diagnostic_reporter` |
| `report-notification.zip` | `diagnostic_reporter` |

`diagnostic_reporter` uses **both** `fault-diagnosis` and `report-notification`. Edit the config block
at the top of a `SKILL.md` (e.g. `INCIDENT_SEARCH`) before zipping if you change it; re-zip the folder
into `karini/skills_zip/<name>.zip`.

### 5.3 Prompts (`karini/prompts/`)
- `entry_router.md` — the one router (answers `{"next":"<node>"}`).
- `agent1_evidence_gatherer.md`
- `agent2_diagnostic_reporter.md`
- `agent3_email_template.html` — the HTML the email agent fills (the DB returns the field values).

Keep doubled braces `{{ }}` exactly; single braces are Karini variables (`{metadata}`, `{evidence_result}`).
Publish a version of each prompt.

### 5.4 Canvas
Webhook → Start → `entry_router` → `evidence_gatherer` → `diagnostic_reporter` → End.
Plain edge from `evidence_gatherer` to `diagnostic_reporter` (no evidence_router). The router's default
edge goes to End. `diagnostic_reporter` reads the earlier output via the node variable `{evidence_result}`.

### 5.5 Deploy and get credentials
Publish and deploy the recipe. On the Webhook node, copy the **recipe id** from
`…/api/webhook/recipe/<recipe id>` and **generate a token**. You will either put these in `.env` as the
default, or have each student paste their own on the Start form (see step 6).

### 5.6 Draft prompts without live data (sandbox)
Trainees can iterate on `diagnostic_reporter` in the Karini **playground** using three fixed event IDs
that return canned fixtures, write nothing and send no email:

| Sandbox `event_id` | Scenario |
| --- | --- |
| `e5000000-0000-4000-8000-000000000001` | misalignment (sufficient evidence) |
| `e5000000-0000-4000-8000-000000000002` | motor_overload (conflicting evidence) |
| `e5000000-0000-4000-8000-000000000003` | none (empty, no-diagnosis path) |

Copy-paste `evidence_result` fixtures and the exact behaviour are in
`karini/test/diagnostic_reporter_playground_mock.md`. Sandbox `tool_save_report` always returns
`send_email: false`, so the playground never emails anyone, and the IDs never return "already reported",
so they can be re-run forever.

---

## 6. Configure and deploy the backend

### Option A — one shared recipe for everyone (`.env` defaults)
On the host, `cp .env.example .env` and set:
```
DATABASE_URL=postgresql://pda_app:<password>@<rds-endpoint>:5432/postgres?sslmode=require
INFERENCE_MODE=synthetic            # or sagemaker (see step 7)
KARINI_ENABLED=true
KARINI_BASE_URL=https://app.karini.ai
KARINI_RECIPE_ID=<recipe id>
KARINI_API_TOKEN=<token>
```

### Option B — each student uses their own recipe (per-run credentials)
Leave `KARINI_RECIPE_ID` / `KARINI_API_TOKEN` blank. Each student pastes their **base URL + recipe id +
API token** into the Start form; the browser remembers them. A run with its own creds ignores the `.env`
defaults; a run without them falls back to `.env`. This is the normal multi-student mode.

### Run it
Local/simple host:
```bash
docker compose up --build -d
curl http://localhost:8000/api/health
```
Production (HTTPS via Caddy on your domain):
```bash
sudo SITE_DOMAIN=pda.yourdomain.com docker compose -f deploy/docker-compose.prod.yml up -d --build
curl https://pda.yourdomain.com/api/health      # {"ok": true, ...}
```
Caddy must keep `flush_interval -1` for SSE (already set in `deploy/Caddyfile`). Run exactly one backend
container — the run workers and the live-update listener live in that single process; one `t3.small`
handles the default 60 concurrent runs. On restart, active runs are marked `interrupted`; executions
already posted to Karini keep being polled.

---

## 7. (Optional) SageMaker models

Skip to run in synthetic mode (a deterministic demo score, clearly labelled on the dashboard — not ML).
For real inference:
```bash
pip install -r ml/requirements.txt
python ml/local_model_check.py                                   # optional local sanity check
python ml/train_rcf.py --role <SageMakerExecutionRoleArn>        # deploys endpoint pda-rcf, prints threshold + scaler
python ml/train_xgboost.py --role <SageMakerExecutionRoleArn>    # deploys endpoint pda-xgb
```
Then in `.env`: `INFERENCE_MODE=sagemaker`, `AWS_REGION`, `ANOMALY_THRESHOLD_RCF`, `RCF_SCALER_JSON`
(all printed by `train_rcf.py`), and give the EC2 role `deploy/iam-backend-policy.json`
(`sagemaker:InvokeEndpoint` on `pda-*`). Tear down after: `python ml/cleanup.py` (endpoints bill per hour).

---

## 8. Acceptance tests before the workshop

| # | Test | Expected |
| --- | --- | --- |
| 1 | `karini/test/db_tool_acceptance.md` through `pda_database` | all 8 pass |
| 2 | Start a run, press **Inject fault now** | score crosses threshold; agent card appears; webhook ✓ within seconds |
| 3 | Watch the card | Evidence → Diagnosis → Report → Email turn green; tool calls listed |
| 4 | Your inbox | HTML email, subject `[PDA][…] PUMP-01: possible …`, rendered tables/cards (not raw tags) |
| 5 | Reveal | "Actual fault … / Agent's top hypothesis …" with ✓ or ✗ |
| 6 | Two browsers, two runs at once | each dashboard shows only its own run; a foreign run URL says "not available in this browser" |
| 7 | Leave a run | auto-stops at 10:00 |
| 8 | Wrong `KARINI_API_TOKEN` (or wrong per-run token) | card shows a 401 webhook rejection |

Handy DBeaver queries (master user):
```sql
SELECT status, count(*) FROM pda.karini_executions GROUP BY 1;
SELECT run_id, status, trigger_count, emails_sent, started_at FROM pda.runs ORDER BY started_at DESC LIMIT 20;
SELECT agent, tool, ok, summary, created_at FROM pda.agent_traces ORDER BY trace_id DESC LIMIT 30;
SELECT event_id, email_status, email_detail FROM pda.diagnostic_reports ORDER BY created_at DESC LIMIT 20;
```

---

## 9. Troubleshooting quick map

| Symptom | Look at |
| --- | --- |
| Dashboard loads but never updates | SSE buffering: Caddy `flush_interval -1`; `/api/health`; the LISTEN loop logs |
| Reading shows `inference failed` | endpoint names, `AWS_REGION`, EC2 role, endpoint `InService`; `INFERENCE_MODE` |
| Card `Webhook !` 401/403 | token must match the Webhook node (or the per-run token); recipe id; base URL host |
| Card stuck at Webhook → `timed out` | recipe not deployed, or an agent stuck; the router must output `{"next":...}`; read the recipe History |
| Evidence stage fails, no tool calls | `pda_database` cannot connect: RDS security group vs Karini IPs, user `pda_agent`, password |
| Tool `ok:false` "unknown event_id" | Karini is pointed at a different database than the backend |
| Agent says a write failed | `agent_traces` for the event; DB-tool commit behaviour; the `$tag$` dollar-quote |
| Email `failed` | SMTP app password / sender identity; `diagnostic_reports.email_status` |
| Wrong diagnosis | `tool_get_logs` window, `fault-diagnosis` skill rules, KB results |
| History empty | seed is old: rerun `db/04_seed.sql` |
| "too many active runs" | `MAX_ACTIVE_RUNS` reached; raise it or wait for auto-stops |

---

## 10. Known limitations (tell your mentor)

- **Not production.** Synthetic data only.
- **Shared agent login.** Every agent session uses `pda_agent`; strong per-run isolation would need one
  login per recipe instance. Accepted for the workshop because data is synthetic and students do not
  control the agents.
- **One backend process.** Scaling to several instances would need a shared run registry.
- **Verify on the real Karini tenant** (no access during build): KB node behaviour, DB-tool commit
  behaviour, `$tag$` dollar-quote quoting, SMTP/SES sending. Step 8 covers these.
- The long `docs/SETUP_GUIDE.md` still documents the older 3-agent / 5-prompt / SES layout; trust this
  file for the agent topology, email transport and sandbox IDs.

That is the whole path: dry run, RDS, recipe, deploy, test. Budget ~2–3 hours the first time.
