---
inclusion: always
---
# Status, history and troubleshooting

## Status (2026-10-14)
Complete and tested locally (PG16 as non-superuser owner, backend + mock Karini, Playwright UI, 3 concurrent runs: 15/15 executions succeeded, 15/15 diagnoses correct, email cap enforced, token isolation verified).
NOT yet verified in real environments: Karini tenant (KB node, DB tool commit behaviour, `$tag$` quoting), SES production access, SageMaker training/endpoints, DBeaver execution on RDS.

## Target environment
- RDS host `load-opt-demo.cr0wcueo0rpo.us-east-1.rds.amazonaws.com:5432`, database `postgres`, schema `pda`. Master user `postgres` (schema owner; runs 01-04). Backend connects as `pda_app`, Karini DB tool as `pda_agent`, both to database `postgres`. Never store passwords in repo files.

## Next steps for the operator
1. Change passwords in `db/03_roles.sql`; load RDS via DBeaver (SETUP_GUIDE s3).
2. Run `karini/test/db_tool_acceptance.md` through the Karini DB tool.
3. Test KB search returns `INC-`/`SOP-` names; else set `INCIDENT_SEARCH: database` in evidence-retrieval skill and re-zip.
4. Request SES production access (sandbox only sends to verified addresses).
5. Train models, set `INFERENCE_MODE=sagemaker`, `RCF_SCALER_JSON`, `ANOMALY_THRESHOLD_RCF`.
6. Deploy EC2 + Caddy; open RDS 5432 to Karini egress IPs.

## Known past bugs (do not reintroduce)
- Previous episode's logs leaked into evidence -> `tool_get_logs` window = greatest(ts - minutes, latest MNT-620 <= ts).
- Near-miss scores crossed threshold -> keep near-miss profile max z ~2.27 < 2.5.
- Write confirmation false-positive -> `tool_last_result(event_id, agent)` filtered by agent; every exit of `tool_record_output` traced; skills check `tool` field.
- Email cap race -> lock run row, count pending + submitted.
- XSS in badges -> escape everything in app.js.
- Reveal compared free text -> compare `fault_category`; `gt.phase !== "fault"` = false alarm.
- Stale poll error displayed as failure -> clear `error` while in process.
- SSE queue overflow -> send `resync`.
- `ts_headline` `StartSel=` empty invalid -> use `@@` then replace.
- ORDER BY expression on UNION -> wrap in subquery.

## Troubleshooting quick map
| Symptom | Look at |
| --- | --- |
| No triggers | `model_predictions.trigger_decision`, threshold env, `INFERENCE_MODE` |
| Execution `post_failed` | `KARINI_BASE_URL`, recipe id, token; `karini_executions.error` |
| Stuck `accepted` -> `timed_out` | Karini run logs; router output must be `{"next":...}` |
| Agent says write failed | `agent_traces` for event; DB tool commit behaviour; dollar-quote tag |
| Email failed | SES sandbox / sender identity; `diagnostic_reports.email_status` |
| Dashboard not live | Caddy `flush_interval -1`; `/api/health`; LISTEN loop logs |
| Wrong diagnosis | `tool_get_logs` window, fault-diagnosis skill rules, KB results |
| permission denied for pda_agent | GRANT in 03_roles.sql for new/changed function signatures |
