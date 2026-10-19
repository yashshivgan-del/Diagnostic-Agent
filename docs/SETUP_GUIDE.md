# Setup guide: Predictive Diagnostic Assistant (AWS workshop)

This guide takes you from zero to a working workshop:
- one backend and one dashboard on your domain,
- one PostgreSQL database on Amazon RDS,
- SageMaker models,
- one Karini recipe shared by every student.

Budget about 2–3 hours the first time, plus model training time.

| Step | What | Where | Time |
| --- | --- | --- | --- |
| 1 | Local dry run with mock Karini | your laptop | 15 min |
| 2 | Create the RDS database | AWS console | 15 min |
| 3 | Load schema, functions, roles and seed data | DBeaver | 10 min |
| 4 | Train and deploy the models | SageMaker | 30–45 min |
| 5 | Deploy backend + dashboard on your domain | EC2 | 30 min |
| 6 | Build the Karini recipe | Karini | 45–60 min |
| 7 | Acceptance tests | dashboard + Karini | 20 min |
| 8 | Workshop day | - | - |

---

## 0. How it works

```
Student (browser) ──► Dashboard + Backend (one EC2, your domain, HTTPS)
                         │  every 10 s per run: simulate PUMP-01 → SageMaker RCF + XGBoost → store
                         │  confirmed anomaly (2 of last 3 readings) → POST Karini webhook
                         ▼
                      Amazon RDS PostgreSQL (schema pda) ◄── Karini agents call pda.tool_* functions
                         │  NOTIFY on every change                      (database tool, login pda_agent)
                         ▼
                      Backend streams the run's rows live to the student's browser (Server-Sent Events)
```

**Identifiers.** There is no login.
- `run_id`: one Start-to-Stop session. Start asks for the student's email.
- `event_id`: one reading.
- `request_id`: one Karini execution.

Every row is stored with its `run_id` and `event_id`. A dashboard shows only its own run.

**Privacy.** Start returns a secret run token to the browser, which keeps it in local storage. Viewing a run, streaming it, stopping it, injecting a fault and listing past runs all require that token. A run is therefore visible only in the browser that started it. On a shared screen, later students on the same browser see earlier runs from that browser in "Your recent runs".

**Run behaviour.**
- A random fault starts on PUMP-01 within the first 50–120 s, then again at most every 5 minutes.
- Each fault worsens over a few readings, is confirmed by the 2-of-3 rule, triggers the recipe once, then clears with a maintenance reset.
- The **Inject fault now** button starts a fault on the next reading.
- Runs auto-stop after 10 minutes.
- Each run sends at most 5 emails and starts at most 8 agent executions.

**What the agents can touch.** Agents never see tables. They call 8 database functions (`db/02_agent_functions.sql`). Each function takes the `event_id`, works out the run itself, validates its input, and logs the call. That log is what the dashboard shows.

**Answer reveal.** The simulator records the true fault. The dashboard shows it next to the agents' top hypothesis once Agent 2 or Agent 3 has finished, and for every reading after the run ends.

---

## 1. Local dry run (no AWS, no Karini)

Prerequisites: Docker Desktop.

```bash
cp .env.example .env
docker compose up --build
```
Open http://localhost:8000, click **Start run**, enter any email, then click **Inject fault now**.
- Within about 30 s you should see the anomaly score cross the threshold, an agent card appear, and all 7 stages turn green.
- The card ends with "Actual fault … ✓".

What runs:
- Postgres 16 with `db/01`–`04` applied automatically.
- The backend in `INFERENCE_MODE=synthetic`, which uses a demo score, not ML.
- **Mock Karini** (`tools/mock_karini.py`): implements Karini's webhook API and plays the three agents with fixed rules, calling the real `pda.tool_*` functions as `pda_agent`.

This proves the database contract, dispatch, polling and the live dashboard before you build anything in Karini.

Faster demo: `SIM_INTERVAL_S=2 RUN_MAX_SECONDS=120 docker compose up` gives the same schedule at five times the speed.

---

## 2. Create the RDS PostgreSQL database

AWS console → RDS → Create database:

| Setting | Value |
| --- | --- |
| Engine | PostgreSQL 16 (13+ works) |
| Template | Dev/Test (single-AZ is fine for a workshop) |
| Instance | `db.t4g.small` (30 students); `db.t4g.micro` for a dry run |
| Storage | 20 GB gp3 |
| DB instance identifier | `pda-workshop` |
| Master username / password | e.g. `pda_owner` / a strong password |
| Initial database name | the default `postgres` database (used by this workshop); everything lives in schema `pda` inside it |
| Public access | **Yes**, so Karini can reach it; lock it down with the security group below |
| Encryption | on (default) |

**Security group** (inbound TCP 5432) allows only:
- the backend EC2 security group (step 5),
- your own IP, for DBeaver,
- the outbound IP addresses of your Karini environment. Ask Karini support: production and sandbox differ.

Never open 5432 to `0.0.0.0/0`.

---

## 3. Load the database with DBeaver

1. **New connection → PostgreSQL**:
   - host = RDS endpoint, port 5432, database `postgres` (or the database you created), user = master user. Use the same database name in `DATABASE_URL` and the Karini tool.
   - In the **SSL** tab, use SSL with mode `require`.
   - Test the connection, then Finish.
2. Open `db/03_roles.sql` and **replace the two passwords** (`CHANGE_ME_app_password`, `CHANGE_ME_agent_password`). Save.
3. Run these files in order. For each: File → Open, choose the `pda` connection, then **Execute SQL Script (Alt+X)**, not Execute Statement (Ctrl+Enter).

   | File | Creates |
   | --- | --- |
   | `db/01_schema.sql` | schema `pda`, 8 tables, live-update triggers |
   | `db/02_agent_functions.sql` | the `pda.tool_*` functions agents call |
   | `db/03_roles.sql` | logins `pda_app` (backend) and `pda_agent` (Karini) + permissions |
   | `db/04_seed.sql` | PUMP-01 30-day history (relative to now) + 27 knowledge-base documents |

   `db/all_in_one.sql` contains all four in one file; edit the passwords inside it first.
4. If DBeaver splits a function into pieces ("unterminated dollar-quoted string"): Preferences → Editors → SQL Editor → SQL Processing → set **"Blank line is statement delimiter"** to **Never**, then rerun. The scripts are safe to run again.
5. Verify (expected: `t f f t`):
   ```sql
   SELECT has_function_privilege('pda_agent', 'pda.tool_get_event(text)', 'EXECUTE') AS agent_tool,
          has_table_privilege('pda_agent', 'pda.machine_logs', 'SELECT')            AS agent_table,
          has_function_privilege('pda_app', 'pda.tool_get_event(text)', 'EXECUTE')   AS app_tool,
          has_table_privilege('pda_app', 'pda.runs', 'INSERT')                       AS app_runs;
   SELECT count(*) FROM pda.machine_logs;   -- 272 seed rows
   SELECT count(*) FROM pda.kb_documents;   -- 27
   ```

**Re-seeding.** The seed timestamps are relative to `now()`. If the workshop is weeks after setup, rerun `04_seed.sql` so the 7-day and 30-day history stays recent.

---

## 4. Train and deploy the models (SageMaker)

Skip this step to run the workshop in synthetic mode. The dashboard then labels scores "synthetic"; everything else works the same.

Use a SageMaker notebook or Studio (its execution role is used automatically), or a machine with AWS credentials and a SageMaker execution role ARN.

```bash
pip install -r ml/requirements.txt
python ml/local_model_check.py          # optional: trains XGBoost locally to sanity-check the data (~1 min)
python ml/train_rcf.py --role <SageMakerExecutionRoleArn>       # trains + deploys endpoint pda-rcf, calibrates threshold
python ml/train_xgboost.py --role <SageMakerExecutionRoleArn>   # trains + deploys endpoint pda-xgb
```

**Random Cut Forest** (`train_rcf.py`):
- **Training data:** 50,400 normal readings (`data/training/rcf_train.csv`), standardized first because RCF is sensitive to feature scale.
- **Threshold:** calibrated on `eval_labeled.csv` as the mean plus 3 standard deviations of normal scores.
- **Outputs:**
  - `ml/artifacts/rcf_calibration.json`: precision and recall per fault type.
  - The values for `.env`:
    ```
    ANOMALY_THRESHOLD_RCF=<printed threshold>
    RCF_SCALER_JSON=<printed one-line JSON>
    ```
- An RCF score is an anomaly score, not a failure probability.

**XGBoost** (`train_xgboost.py`):
- Six classes (normal plus five faults), trained on 35,200 rows and validated on 8,800.
- Expect about 98% accuracy.
- Most errors are bearing wear vs misalignment, which is deliberate: the agents must resolve it with logs and history.

**Costs.** Endpoints bill per hour. After the workshop:
```bash
python ml/cleanup.py   # deletes pda-rcf and pda-xgb
```

**Regenerating data (optional).** `python data/generate_data.py` rewrites the training sets, the knowledge-base documents and `db/04_seed.sql`.

---

## 5. Deploy the backend and dashboard on your domain

One EC2 instance runs the backend (simulator, inference calls, Karini dispatch, live updates) and serves the dashboard. Caddy provides HTTPS automatically.

1. **IAM role for EC2:**
   - Create a role with the inline policy `deploy/iam-backend-policy.json`, which allows `sagemaker:InvokeEndpoint` on `pda-*`.
   - Attach it to the instance.
   - Not needed for synthetic mode.
2. **Launch the instance:**
   - Amazon Linux 2023, `t3.small`, same region as the RDS database and SageMaker endpoints.
   - Security group: inbound 80 and 443 from anywhere, 22 from your IP.
   - Add this security group to the RDS inbound rule (step 2).
3. **DNS:** create an A record such as `pda.yourdomain.com` pointing to the instance's Elastic IP.
4. **Install and start:**
   ```bash
   sudo dnf install -y docker git && sudo systemctl enable --now docker
   sudo mkdir -p /usr/local/lib/docker/cli-plugins && sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose && sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
   # copy this project to the instance (scp the zip, or git clone your repo), then:
   cd pda-workshop && cp .env.example .env && nano .env
   ```
   Set in `.env`:
   - `DATABASE_URL=postgresql://pda_app:<password>@<rds-endpoint>:5432/postgres?sslmode=require`
   - `INFERENCE_MODE=sagemaker`, `AWS_REGION`, `ANOMALY_THRESHOLD_RCF`, `RCF_SCALER_JSON` (from step 4)
   - `KARINI_BASE_URL`, `KARINI_RECIPE_ID`, `KARINI_API_TOKEN` (from step 6; leave `KARINI_ENABLED=false` until then)
   ```bash
   sudo SITE_DOMAIN=pda.yourdomain.com docker compose -f deploy/docker-compose.prod.yml up -d --build
   curl https://pda.yourdomain.com/api/health      # {"ok": true, ...}
   ```
5. **Updating later:** `sudo SITE_DOMAIN=... docker compose -f deploy/docker-compose.prod.yml up -d --build`.
   - Runs active during a restart are marked `interrupted`.
   - Executions already posted to Karini keep being polled.

**One backend process.** Run exactly one backend container. Each run's simulator and the live-update listener live in that process. One `t3.small` handles the 60 concurrent runs the defaults allow.

---

## 6. Build the Karini recipe

All files are in `karini/`. The node layout and edges are in `karini/recipe/RECIPE_LAYOUT.md`.

### 6.1 Tools (`karini/tools/TOOLS.md`)
1. **`pda_database`**:
   - Database tool, connector `postgres`, RDS endpoint, database `postgres` (tables are in schema `pda`), user **`pda_agent`**.
   - Paste the description from TOOLS.md.
   - Then run **`karini/test/db_tool_acceptance.md`** through the tool. All 8 checks must pass.
2. **`incident_knowledge_base`**:
   - Knowledge Base with every file in `data/knowledge_base/incidents/` and `data/knowledge_base/procedures/`; keep file names as titles.
   - Run one test search.
   - If it doesn't work, set `INCIDENT_SEARCH: database` in the `evidence-retrieval` skill; Agent 1 then searches the same documents in Postgres.
3. **`maintenance_email`**:
   - Messaging (SES), with a verified sender.
   - Confirm SES production access, otherwise only verified recipients receive mail.

### 6.2 Skills
Upload the three zips from `karini/skills_zip/`:

| Skill | Attach to |
| --- | --- |
| `evidence-retrieval.zip` | `evidence_gatherer` |
| `fault-diagnosis.zip` | `diagnostic_investigator` |
| `report-notification.zip` | `report_notifier` |

Edit the configuration block at the top of each `SKILL.md` first if needed: `INCIDENT_SEARCH`, and the database field names your database tool asks for.

### 6.3 Prompts
- Create five prompts from `karini/prompts/` (the text inside each code block).
- Keep the doubled braces `{{ }}` exactly. Single braces are Karini variables (`{metadata}`, `{evidence_result}`, `{diagnosis_result}`).
- **Publish a version** of each prompt.

### 6.4 Canvas
Build the nodes, settings and edges from `RECIPE_LAYOUT.md`:
- Webhook → Start → `entry_router` → `evidence_gatherer` → `evidence_router` → `diagnostic_investigator` → `report_notifier` → End.
- `evidence_router` → `report_notifier` (no-evidence path).
- The routers' default edges go to End.
- Agents 2 and 3 read earlier outputs through **node variables**: `evidence_result` and `diagnosis_result`.

### 6.5 Deploy and connect
1. Publish and deploy the recipe.
2. On the Webhook node, copy the **recipe id** from the URL `…/api/webhook/recipe/<recipe id>` and **generate a token**.
3. Put both into `.env` on the EC2 host:
   ```
   KARINI_ENABLED=true
   KARINI_BASE_URL=https://app.karini.ai     # or your environment's host
   KARINI_RECIPE_ID=<recipe id>
   KARINI_API_TOKEN=<token>
   ```
4. Restart the backend (step 5.5).

---

## 7. Acceptance tests

| # | Test | Expected |
| --- | --- | --- |
| 1 | `karini/test/db_tool_acceptance.md` | all 8 pass |
| 2 | Start a run with your email; wait for the first fault, or press Inject | score crosses the threshold on the chart; agent card appears; webhook ✓ within seconds |
| 3 | Watch the card | Evidence → Diagnosis → Report → Email turn green as each agent finishes; tool calls are listed |
| 4 | Your inbox | Email with subject `[PDA][…] PUMP-01: possible …` |
| 5 | Reveal | "Actual fault: … / Agent's top hypothesis: …" with ✓ or ✗ |
| 6 | Press Inject twice quickly | the second press says a fault is already developing |
| 7 | Press Stop | no new readings; the open agent card still completes |
| 8 | Leave a run alone | auto-stops at 10:00; status `auto stopped` |
| 9 | Second browser, second run at the same time | each dashboard shows only its own run; pasting one run's URL into the other browser shows "not available in this browser" |
| 10 | Set a wrong `KARINI_API_TOKEN`, restart | cards show `Webhook !` with "rejected the request (HTTP 401)" |

Useful queries (DBeaver, master user):
```sql
SELECT status, count(*) FROM pda.karini_executions GROUP BY 1;
SELECT run_id, status, trigger_count, emails_sent, started_at FROM pda.runs ORDER BY started_at DESC LIMIT 20;
SELECT agent, tool, ok, summary, created_at FROM pda.agent_traces ORDER BY trace_id DESC LIMIT 30;
SELECT event_id, email_status, email_detail FROM pda.diagnostic_reports ORDER BY created_at DESC LIMIT 20;
```

---

## 8. Workshop day

**Before:**
- Rerun `db/04_seed.sql` if setup was more than a week ago.
- Check `/api/health`, do one full run yourself (test 2–5), and confirm both endpoints are `InService`.

**Student instructions:**
1. Open `https://pda.yourdomain.com`.
2. Click **Start run**, enter your email, click Start.
3. Watch the telemetry. When the pump develops a fault, follow the agent card: Evidence, Diagnosis, Report, Email. Open each section to see what the agent found.
4. Compare the actual fault with the agent's top hypothesis. When they differ, read the evidence and ask why.
5. To skip waiting, press **Inject fault now**. The run stops by itself after 10 minutes; start a new one to try again.

**During:**
- `SELECT status, count(*) FROM pda.karini_executions GROUP BY 1;` should show mostly `success`, and only a few `accepted` at a time.
- If many are `queued`, Karini is slow. Raise `KARINI_MAX_CONCURRENT` carefully, or ask students to stagger starts.

**After:**
- `python ml/cleanup.py` (endpoints).
- Optional: `db/05_cleanup.sql` (old runs).
- Stop the EC2 instance and snapshot or delete RDS.

---

## 9. Troubleshooting

| Symptom | Check |
| --- | --- |
| Dashboard loads but never updates | Proxy buffering. With Caddy keep `flush_interval -1`; behind an ALB, raise the idle timeout above 30 s |
| Readings show `inference failed` | Endpoint names, `AWS_REGION`, EC2 instance role, endpoint `InService`; the error text is in the score panel |
| Agent card: `Webhook !` with 401/403 | `KARINI_API_TOKEN` must match the Webhook node token; `KARINI_RECIPE_ID`; `KARINI_BASE_URL` host |
| Card stays at Webhook, recipe `inProcess`, then `timed out` | Recipe not deployed, or an agent stuck: open the recipe History in Karini and read the trace |
| Evidence stage fails, tool calls show nothing | `pda_database` cannot connect: RDS security group vs Karini IPs, user `pda_agent`, password |
| Tool call `ok: false`, "unknown event_id" | Karini is connected to a different database than the backend |
| Report fails with `invalid_report` | Agent 3 skipped the self-check; the error list is in the tool call; the skill retries once |
| Email `failed` with "not verified" | SES sandbox: verify the address or request production access |
| History shows nothing | Seed is old: rerun `db/04_seed.sql` |
| Every run says "too many active runs" | `MAX_ACTIVE_RUNS` reached; raise it or wait for auto-stops |

---

## 10. Reference

**Backend API** (no authentication; the run is the identity)

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/runs` `{email, label?}` | Start a run; returns `access_token` once |
| POST | `/api/runs/history` `{runs: {run_id: token}}` | Summaries of this browser's runs (emails masked) |
| GET | `/api/runs/{run_id}` + header `x-run-token` | Snapshot: run, readings, logs, executions, traces, reports |
| GET | `/api/runs/{run_id}/stream?t=<token>` | Server-Sent Events: `reading`, `execution`, `trace`, `report`, `truth`, `run`, `resync` |
| POST | `/api/runs/{run_id}/stop` + header `x-run-token` | Stop |
| POST | `/api/runs/{run_id}/inject` + header `x-run-token` | Fault on the next reading (409 if one is already active) |
| GET | `/api/config`, `/api/health` | Public settings, health |

**Tables** (schema `pda`)

| Table | Contents |
| --- | --- |
| `runs` | One row per run |
| `machine_events` | One row per reading |
| `machine_logs` | Log lines; `run_id` NULL = shared seed |
| `model_predictions` | Score + trigger decision |
| `karini_executions` | One row per triggered event |
| `agent_traces` | Tool calls + agent outputs |
| `diagnostic_reports` | Report + email status |
| `kb_documents` | Knowledge-base copy for the search fallback |

**Trigger decision** (in `model_predictions.trigger_decision`): a reading triggers the recipe only when all of these hold:
- the score is at or above the threshold,
- at least 2 of the last 3 readings were anomalous,
- the run is "re-armed": at least 3 normal readings since the last trigger,
- the run has fewer than 8 triggers.

Otherwise the decision records why not.

**Email cap.** `tool_save_report` stops preparing emails after 5 per run. The report is still saved and shown.

---

## 11. Known limitations

**What was tested.**
- **Database:** every SQL file was applied to PostgreSQL 16 as a non-superuser owner with CREATEROLE, the way the RDS master user works. Every `pda.tool_*` function was called as `pda_agent`.
- **Backend with the mock Karini:** start, inject, the agents' database writes, live updates, stop, auto-stop, the email cap, and Karini being unreachable.
- **Dashboard:** driven in headless Chromium.

**What was not tested here** (no access):
- The real Karini tenant: prompt and skill behaviour with a live LLM, the Knowledge Base node, the SES email tool.
- SageMaker endpoints.
- DBeaver itself, as opposed to psql.

Run section 7 before the workshop.

**Synthetic mode** scores are a deterministic demo score, not ML; the dashboard labels them.

**Shared agent login.** All agent sessions use `pda_agent`. On RDS, a role can see the SQL text of its own other sessions in `pg_stat_activity`. A deliberately manipulated agent could therefore learn event IDs that other runs' agents are working on, and record output for them. Data is synthetic and students do not control the agents, so this is accepted for the workshop. For stronger isolation, use one login per recipe instance.

**One backend process.** The live-update listener and the run workers live in that process. Scaling to several backend instances would need a shared run registry.

**Karini specifics** marked "verify" in the Karini guide are flagged in `karini/tools/TOOLS.md`:
- the Knowledge Base node,
- database-tool commit behaviour,
- the `catalog_name` / `database_name` / `object_name` fields.

Check each with the acceptance test.
