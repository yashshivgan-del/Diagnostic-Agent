# `pda_database` acceptance test (run before building the agents)

Run each statement **through the Karini database tool**, from the tool's test console or from a throwaway agent told to run the SQL exactly and return the raw result. This confirms the tool connects as `pda_agent` and accepts the exact call shapes the skills use.

Prepare a test event first, in DBeaver as the master user:
```sql
-- creates run + anomalous reading; note the event_id printed
INSERT INTO pda.runs (run_id, access_token, notify_email, label, seed, inference_mode, threshold, auto_stop_at)
VALUES ('aaaaaaaa-0000-4000-8000-000000000001', 'acceptance-token', 'you@example.com', 'acceptance', 1, 'synthetic', 2.5, now());
INSERT INTO pda.machine_events VALUES ('aaaaaaaa-0000-4000-8000-0000000000e1', 'aaaaaaaa-0000-4000-8000-000000000001', 1, now(), 'PUMP-01',
  '{"temperature_c":70.1,"vibration_mm_s":6.2,"discharge_pressure_bar":6.0,"flow_m3h":118,"motor_current_a":44.9,"rpm":1478}', '{}');
INSERT INTO pda.model_predictions (event_id, run_id, inference_mode, inference_status, anomaly_score, threshold, is_anomaly, confirmed, predicted_fault, trigger_decision)
VALUES ('aaaaaaaa-0000-4000-8000-0000000000e1', 'aaaaaaaa-0000-4000-8000-000000000001', 'synthetic', 'ok', 4.0, 2.5, true, true, 'misalignment', 'triggered');
```

| # | Run through the tool | Expected |
| --- | --- | --- |
| 1 | `SELECT current_user, current_database();` | `pda_agent`, your database |
| 2 | `SELECT pda.tool_get_event('aaaaaaaa-0000-4000-8000-0000000000e1');` | JSON with `"status": "ready"` |
| 3 | `SELECT pda.tool_get_logs('aaaaaaaa-0000-4000-8000-0000000000e1', 10);` | `"ok": true` |
| 4 | `SELECT pda.tool_get_history('aaaaaaaa-0000-4000-8000-0000000000e1', 7);` | rows from the seed history |
| 5 | `SELECT pda.tool_search_incidents('aaaaaaaa-0000-4000-8000-0000000000e1', 'axial vibration coupling');` | documents `INC-...` |
| 6 | `BEGIN; SELECT pda.tool_record_output('aaaaaaaa-0000-4000-8000-0000000000e1', 'evidence_gatherer', $ev_aaaaaaaa${"status":"ready","summary":"it's a test"}$ev_aaaaaaaa$::jsonb); COMMIT; SELECT pda.tool_last_result('aaaaaaaa-0000-4000-8000-0000000000e1', 'evidence_gatherer');` | last result has `"kind": "output"`, `"tool": "tool_record_output"` |
| 7 | `SELECT count(*) FROM pda.runs;` | **permission denied** |
| 8 | `DELETE FROM pda.machine_logs;` | **permission denied** |

| Outcome | Action |
| --- | --- |
| All pass | Build the agents |
| 1 shows another user | Fix the tool credentials. The security design depends on `pda_agent`. |
| 7 or 8 succeed | Stop: the tool uses a login with too many rights |
| 6 fails on `$tag$` quoting | Report to Karini support; as a workaround, ask the agent to double single quotes and use `'...'::jsonb` instead of `$tag$` |
| 6 runs but `tool_last_result` shows the earlier call | The tool did not commit; test the commit behaviour per the Karini guide |

Clean up (DBeaver, master user): `DELETE FROM pda.runs WHERE run_id = 'aaaaaaaa-0000-4000-8000-000000000001';`
