---
inclusion: always
---
# Product: Predictive Diagnostic Assistant (PDA) workshop

Multi-student workshop demo. One backend + one SPA on a domain, one PostgreSQL (RDS), one shared Karini recipe. No login.

## User flow
1. Student opens the SPA, clicks **Start**, enters an email. Backend creates a `run_id` + `access_token` (kept in browser localStorage `pda_runs`).
2. Backend simulates ONE pump (`PUMP-01`), one reading every 10 s (`event_id` per reading).
3. Each reading is scored (synthetic z-score or SageMaker RCF + XGBoost).
4. Confirmed anomaly (2 of last 3 readings anomalous) -> backend POSTs the Karini webhook with flat metadata incl. `notify_email`, `run_id`, `event_id`, prediction.
5. Karini recipe (simplified): entry_router -> Agent 1 evidence_gatherer -> Agent 2 diagnostic_reporter -> End.
   - Agent 1: this run's logs + history from DB, past incidents from `pda_incidents_kb` and procedures from `pda_procedures_kb` (or DB fallback). Two separate KB tools.
   - Agent 2 (merged diagnosis + report): diagnoses via `fault-diagnosis` skill, then saves the report, emails it to the student (SMTP from no-reply@karini.ai), records the email outcome and ONE combined output, all via `report-notification` skill.
6. Live dashboard (SSE) shows telemetry, score chart, logs, agent traces, report, and the actual fault ("answer reveal") after diagnosis.
7. Auto-stop at 10 min; manual Stop; "Inject fault now" button.

## Workshop rules (env-configurable)
- Random fault: first onset reading 5-12, then a new onset every 15-30 readings (always <= 5 min). Fault lasts 8-13 readings. Near-miss (sub-threshold) blips p=0.35.
- Re-arm trigger after 3 normal readings; max 8 triggers/run; max 5 emails/run; max 10 concurrent Karini executions; Karini timeout 600 s.
- Faults: bearing_wear, misalignment, cavitation, seal_leak, motor_overload.

## Non-goals / constraints
- Not production. Synthetic data only. Single shared agent DB login (documented limitation).
- Secrets live on the backend only; email recipient always comes from DB (`runs.notify_email`), never from agent text.
- User preference: concise, technical, no emojis.
