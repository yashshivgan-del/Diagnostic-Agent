---
inclusion: always
---
# Project structure (where to change what)

| Path | Responsibility |
| --- | --- |
| `simulator/fault_profiles.py` | Features, normal ranges, 5 fault profiles, event codes (incl. MNT-610 misalignment backfill, MNT-620 recovery/reset), `SIM_MACHINE_ID` |
| `simulator/engine.py` | `FaultSchedule` (timing, inject, near-miss), `PumpSimulator.tick(run_id, now)` -> `{event_id, seq, ts, telemetry, ground_truth, logs}`, synthetic score/class |
| `backend/app/config.py` | All env settings (see `.env.example`) |
| `backend/app/runs.py` | Run lifecycle, trigger decision (`_decide`), payload to Karini (`build_payload`), auto-stop, inject |
| `backend/app/inference.py` | synthetic vs sagemaker inference |
| `backend/app/karini.py` | Dispatcher/poller, `parse_final_answer` |
| `backend/app/views.py` | Snapshot/history JSON, token check (hmac), email masking, ground-truth gating |
| `backend/app/live.py` | LISTEN/NOTIFY -> SSE broker |
| `backend/app/main.py` | Routes: `/`, `/run/...`, `/api/config`, `/api/health`, `POST /api/runs`, `POST /api/runs/history`, `GET /api/runs/{id}`, `/stop`, `/inject`, `/stream` |
| `backend/static/` | SPA (index.html, app.js, styles.css) |
| `db/01_schema.sql` | Tables: runs, machine_events, machine_logs, model_predictions, karini_executions, agent_traces, diagnostic_reports, kb_documents; notify triggers |
| `db/02_agent_functions.sql` | `tool_get_event`, `tool_get_logs` (window bounded by last MNT-620), `tool_get_history`, `tool_search_incidents`, `tool_record_output`, `tool_save_report` (validation + email cap with run row lock), `tool_record_notification`, `tool_last_result` |
| `db/03_roles.sql` | `pda_app`, `pda_agent` (CHANGE the passwords) |
| `db/04_seed.sql` | Generated: 272 seed logs (relative to now()) + 27 KB docs |
| `db/05_cleanup.sql` | Drop everything |
| `karini/recipe/RECIPE_LAYOUT.md` | Canvas nodes, edges, settings, payload |
| `karini/prompts/` | 1 router prompt (entry_router) + 2 agent prompts (agent1_evidence_gatherer, agent2_diagnostic_reporter) + agent3_email_template.html |
| `karini/skills/` + `skills_zip/` | evidence-retrieval (config `INCIDENT_SEARCH: kb|database`, two KBs), fault-diagnosis, report-notification. The merged agent `diagnostic_reporter` uses fault-diagnosis + report-notification together. |
| `karini/tools/TOOLS.md` | `pda_database`, `pda_incidents_kb`, `pda_procedures_kb`, `maintenance_email` (SMTP) |
| `karini/test/db_tool_acceptance.md` | 8 checks to run through the Karini DB tool first |
| `tools/mock_karini.py` | Local stand-in for Karini; plays the 2 agents (evidence_gatherer, diagnostic_reporter) via real `tool_*` functions; `MOCK_FAIL_EVERY` |
| `data/` | Generator, training CSVs, KB incidents (20) + procedures (7) |
| `ml/` | SageMaker training/cleanup scripts |
| `deploy/` | Prod compose, Caddyfile, IAM policy |
| `docs/SETUP_GUIDE.md` | Full setup: 0 arch, 1 local, 2 RDS, 3 DBeaver, 4 SageMaker, 5 EC2+Caddy, 6 Karini, 7 acceptance, 8 workshop day, 9 troubleshooting, 10 API ref, 11 limitations |
| `docs/STUDENT_HANDOUT.md` | Student instructions |

## Cross-file invariants (keep in sync when changing)
- Fault category names: `fault_profiles.py`, XGBoost labels, `fault-diagnosis` skill, `tool_save_report` validation, `app.js` `FAULT_WORDS`, mock_karini.
- Event codes: `fault_profiles.py`, `REF-001` procedure, skills, seed data.
- Agent names `evidence_gatherer|diagnostic_reporter` (merged system): prompts, skills, `tool_record_output` allow-list + `tool_save_report`/`tool_record_notification` traces in 02 SQL + all_in_one, `app.js` timeline, `views._revealed_events`, mock.
- Webhook metadata keys: `runs.build_payload`, router/agent prompts, RECIPE_LAYOUT.
- Changing a `tool_*` signature: update 02 SQL, 03 GRANTs, TOOLS.md description, skills, acceptance test, mock_karini; re-zip skills; rebuild all_in_one.sql.
