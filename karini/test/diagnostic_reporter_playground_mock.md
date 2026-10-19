# diagnostic_reporter — prompt playground mock

Use this to test the merged `diagnostic_reporter` agent in the Karini prompt playground in isolation.
The agent reads ONE node variable, `{evidence_result}`, diagnoses it (fault-diagnosis skill), then
calls the real `pda.tool_save_report` and `maintenance_email` tools (report-notification skill). So the
playground run exercises:

1. LLM: diagnose (Part A), build the report JSON (R1) and fill the HTML email template (R3).
2. DB: `tool_save_report` / `tool_record_notification` / `tool_record_output` as agent `diagnostic_reporter` (real `pda_agent` DB tool).
3. Email: `maintenance_email` (real send via SMTP from `no-reply@karini.ai`).

The second JSON block below (a ready-made diagnosis) is OPTIONAL reference: the merged agent produces
its own diagnosis from `{evidence_result}`. You only need to set `{evidence_result}`.

## Fastest path: sandbox event IDs (no DB setup, no real email)

For drafting prompts you do **not** need to seed anything. Three fixed sandbox `event_id`s make every
`pda.tool_*` function return canned fixtures without touching the tables and without sending email
(`tool_save_report` returns `send_email: false`). They never return `already_reported`, so you can
re-run the same ID as many times as you like.

| Sandbox `event_id` | Scenario | Use for |
| --- | --- | --- |
| `e5000000-0000-4000-8000-000000000001` | misalignment, sufficient evidence | the normal "diagnosis + report" path |
| `e5000000-0000-4000-8000-000000000002` | motor_overload, conflicting evidence | ranked hypotheses / contradicting evidence |
| `e5000000-0000-4000-8000-000000000003` | none, empty evidence | the no-diagnosis path |

Set `{evidence_result}` with the sandbox `event_id` you want (keep the rest of the package shape the
same as the Variable 1 example, or build it yourself). The merged agent then calls the real DB tool
with that ID; because it is a sandbox ID, the tool validates and renders everything but writes nothing
and sends no email. `tool_last_result` returns a `sandbox: true` marker — in sandbox mode, trust each
tool's own `ok` return, not that confirmation. Use a **real** run event (the DBeaver seed below) only
when you want an actual `pda.diagnostic_reports` row and a real email.

## Prerequisite (real end-to-end only): a real event must exist in the DB
`tool_save_report` looks the event up by `event_id`. The mock below uses
`e1000000-0000-4000-8000-000000000777`. Insert it once in DBeaver (as the schema owner / `postgres`)
before testing. It also needs a run row (for `notify_email` + email cap) and a prediction row.
Change the email to your own verified/test address.

```sql
-- test run (gives notify_email + email cap); all NOT NULL columns supplied
INSERT INTO pda.runs (run_id, access_token, notify_email, label, machine_id, status, seed,
                      inference_mode, threshold, email_cap, auto_stop_at)
VALUES ('a1000000-0000-4000-8000-000000000777', 'playground-token', 'shivgany5@gmail.com',
        'pg-playground', 'PUMP-01', 'running', 777, 'synthetic', 2.5, 5, now() + interval '10 min')
ON CONFLICT (run_id) DO UPDATE SET notify_email = EXCLUDED.notify_email, status = 'running';
-- test event (PUMP-01, misalignment-looking telemetry)
INSERT INTO pda.machine_events (event_id, run_id, seq, ts, machine_id, telemetry, ground_truth)
VALUES ('e1000000-0000-4000-8000-000000000777', 'a1000000-0000-4000-8000-000000000777', 777, now(),
        'PUMP-01',
        '{"temperature_c": 69.8, "vibration_mm_s": 6.1, "pressure_bar": 4.9, "flow_m3h": 118.0, "current_a": 47.5, "rpm": 2965}'::jsonb,
        '{"phase": "fault", "fault_category": "misalignment"}'::jsonb)
ON CONFLICT (event_id) DO NOTHING;
-- prediction row (anomaly above threshold so the event is a real anomaly)
INSERT INTO pda.model_predictions (event_id, run_id, inference_mode, inference_status, anomaly_score,
                                   threshold, is_anomaly, confirmed, predicted_fault, trigger_decision)
VALUES ('e1000000-0000-4000-8000-000000000777', 'a1000000-0000-4000-8000-000000000777', 'synthetic', 'ok',
        3.32, 2.5, true, true, 'misalignment', 'triggered')
ON CONFLICT (event_id) DO NOTHING;
```

To re-test with a clean slate (so `tool_save_report` does not return `already_reported`):
```sql
DELETE FROM pda.diagnostic_reports WHERE event_id = 'e1000000-0000-4000-8000-000000000777';
DELETE FROM pda.agent_traces       WHERE event_id = 'e1000000-0000-4000-8000-000000000777';
```

## Variable 1 — paste as `evidence_result`
```json
{
  "status": "ready",
  "event_id": "e1000000-0000-4000-8000-000000000777",
  "machine_id": "PUMP-01",
  "event_summary": "PUMP-01 score 3.32 >= 2.5; vibration and bearing temperature above normal.",
  "prediction": {"anomaly_score": 3.32, "threshold": 2.5, "predicted_fault": "misalignment", "inference_mode": "synthetic"},
  "telemetry_deviations": [
    {"sensor": "vibration_mm_s", "value": 6.1, "normal_range": "1.6-3.3", "direction": "high"},
    {"sensor": "temperature_c", "value": 69.8, "normal_range": "57-68", "direction": "high"}
  ],
  "logs": [
    {"log_id": 15521, "ts": "2026-10-15T08:07:12Z", "level": "WARN", "event_code": "VIB-205", "message": "Axial vibration component high, 2x running-speed peak dominant (4.27 mm/s)"},
    {"log_id": 15519, "ts": "2026-10-15T08:07:02Z", "level": "WARN", "event_code": "VIB-201", "message": "Overall vibration 6.1 mm/s above 4.5 mm/s alert limit"}
  ],
  "maintenance_history": [
    {"log_id": 15488, "ts": "2026-10-13T10:14:00Z", "event_code": "MNT-610", "message": "Coupling element replaced and shaft re-aligned (work order WO-46482)"}
  ],
  "recurring_warnings": [
    {"event_code": "VIB-201", "level": "WARN", "occurrences": 3, "last_seen": "2026-10-14T22:10:00Z"}
  ],
  "kb_refs": [
    {"doc_id": "SOP-PUMP-105", "type": "procedure", "title": "Shaft alignment troubleshooting", "excerpt": "Axial 2x vibration after coupling work indicates possible misalignment; take handheld axial and radial readings.", "relevance": "Matches VIB-205 and recent MNT-610."},
    {"doc_id": "INC-2026-016", "type": "incident", "title": "Shaft misalignment on PUMP-01", "excerpt": "Same VIB-205/VIB-201 pattern; first misdiagnosed as bearing wear.", "relevance": "Same axial-vibration pattern after coupling work."}
  ],
  "evidence_status": "sufficient",
  "evidence_gaps": ["No vibration spectrum available to confirm the 2x component independently"],
  "tool_errors": [],
  "untrusted_content_flags": [],
  "summary": "2 warning logs, 2 knowledge-base documents"
}
```

## Optional reference — the diagnosis the agent should produce
You do NOT paste this anywhere. The merged agent produces its own diagnosis from `evidence_result`.
This is only here so you can eyeball whether the agent's Part-A diagnosis matches the expected one.
```json
{
  "status": "diagnosed",
  "event_id": "e1000000-0000-4000-8000-000000000777",
  "summary": "Shaft misalignment after recent coupling work is the most likely cause (high strength).",
  "observed_facts": [
    {"statement": "Vibration 6.1 mm/s, above the 4.5 mm/s alert limit", "sources": ["telemetry:vibration_mm_s", "log:15519"]},
    {"statement": "Axial vibration with dominant 2x peak reported", "sources": ["log:15521"]},
    {"statement": "Coupling replaced and shaft re-aligned two days before the event", "sources": ["log:15488"]}
  ],
  "hypotheses": [
    {"rank": 1, "cause": "Shaft misalignment after recent coupling work", "fault_category": "misalignment",
     "evidence_strength": "high", "supporting": ["log:15521", "log:15488", "doc:SOP-PUMP-105", "doc:INC-2026-016"],
     "contradicting": [], "reasoning": "Axial 2x vibration plus coupling work two days earlier matches the SOP-PUMP-105 signature. INC-2026-016 shows the same pattern was once mistaken for bearing wear."},
    {"rank": 2, "cause": "Early bearing wear", "fault_category": "bearing_wear", "evidence_strength": "low",
     "supporting": ["telemetry:temperature_c", "log:15519"], "contradicting": ["log:15521"],
     "reasoning": "High vibration and temperature are consistent with bearing wear, but the axial component points away from it."}
  ],
  "safe_checks": [
    {"check": "Take handheld axial and radial vibration readings and compare them", "source": "SOP-PUMP-105", "discriminates": "misalignment vs bearing_wear"},
    {"check": "Review the alignment report attached to work order WO-46482", "source": "SOP-PUMP-105", "discriminates": "confirms misalignment"}
  ],
  "overall_confidence": "high",
  "model_agreement": "agrees",
  "uncertainties": ["Model inference_mode is synthetic, so the predicted class is not independent evidence"],
  "additional_info_needed": ["Laser alignment readings from WO-46482"]
}
```

## Expected result
- `report_status: "saved"`, `email_status: "submitted"`, `severity: "high"`, `top_hypothesis: "Shaft misalignment after recent coupling work"`, `overall_confidence: "high"`.
- A row in `pda.diagnostic_reports` for the event; `email_status = 'submitted'`.
- An HTML email at the test address rendering the header, key-facts table, telemetry table, hypothesis cards and safe checks (not raw tags). If tags show as text, the `maintenance_email` tool is still sending plain text — set it to HTML (text/html).

## Empty-diagnosis variant (optional second test)
To test the "no diagnosis" path, set `evidence_result` to a package with `evidence_status: "none"`,
empty `logs` and empty `kb_refs`. Expect the agent to save a report with `hypotheses: []`,
`overall_confidence: "low"`, and a summary saying an anomaly was detected but evidence was insufficient.
```

## Sandbox `evidence_result` (copy-paste, no DB setup)

Paste one of these as `{evidence_result}`. They use the sandbox `event_id`s, so `tool_save_report`
writes nothing and sends no email (`send_email: false`), and you can re-run them forever.

Misalignment (`...001`, sufficient evidence):
```json
{
  "status": "ready",
  "event_id": "e5000000-0000-4000-8000-000000000001",
  "machine_id": "PUMP-01",
  "event_summary": "SANDBOX PUMP-01 score 3.32 >= 2.5; axial vibration high after recent coupling work.",
  "prediction": {"anomaly_score": 3.32, "threshold": 2.5, "predicted_fault": "misalignment", "inference_mode": "synthetic"},
  "telemetry_deviations": [
    {"sensor": "vibration_mm_s", "value": 6.1, "normal_range": "1.6-3.3", "direction": "high"},
    {"sensor": "temperature_c", "value": 69.8, "normal_range": "57-68", "direction": "high"}
  ],
  "logs": [
    {"log_id": 901, "ts": "2026-01-01T00:00:12Z", "level": "WARN", "event_code": "VIB-205", "message": "Axial vibration component high, 2x running-speed peak dominant (4.27 mm/s)"},
    {"log_id": 900, "ts": "2026-01-01T00:00:02Z", "level": "WARN", "event_code": "VIB-201", "message": "Overall vibration 6.1 mm/s above 4.5 mm/s alert limit"}
  ],
  "maintenance_history": [
    {"log_id": 850, "ts": "2025-12-30T10:14:00Z", "event_code": "MNT-610", "message": "Coupling element replaced and shaft re-aligned (work order WO-46482)"}
  ],
  "recurring_warnings": [
    {"event_code": "VIB-201", "level": "WARN", "occurrences": 3, "last_seen": "2025-12-31T22:10:00Z"}
  ],
  "kb_refs": [
    {"doc_id": "SOP-PUMP-105", "type": "procedure", "title": "Shaft alignment troubleshooting", "excerpt": "Axial 2x vibration after coupling work indicates possible misalignment; take handheld axial and radial readings.", "relevance": "Matches VIB-205 and recent MNT-610."},
    {"doc_id": "INC-2026-016", "type": "incident", "title": "Shaft misalignment on PUMP-01", "excerpt": "Same VIB-205/VIB-201 pattern; first misdiagnosed as bearing wear.", "relevance": "Same axial-vibration pattern after coupling work."}
  ],
  "evidence_status": "sufficient",
  "evidence_gaps": ["No vibration spectrum available to confirm the 2x component independently"],
  "tool_errors": [],
  "untrusted_content_flags": [],
  "summary": "SANDBOX: 2 warning logs, 2 knowledge-base documents"
}
```

No diagnosis (`...003`, empty evidence):
```json
{
  "status": "ready",
  "event_id": "e5000000-0000-4000-8000-000000000003",
  "machine_id": "PUMP-01",
  "event_summary": "SANDBOX PUMP-01 anomaly, but no corroborating logs or knowledge-base matches.",
  "prediction": {"anomaly_score": 2.61, "threshold": 2.5, "predicted_fault": "cavitation", "inference_mode": "synthetic"},
  "telemetry_deviations": [],
  "logs": [],
  "maintenance_history": [],
  "recurring_warnings": [],
  "kb_refs": [],
  "evidence_status": "none",
  "evidence_gaps": ["No logs within the window", "No knowledge-base matches"],
  "tool_errors": [],
  "untrusted_content_flags": [],
  "summary": "SANDBOX: no supporting evidence"
}
```

Expected in sandbox: `tool_save_report` returns `status: "saved"`, `sandbox: true`, `send_email: false`,
plus the full `email.subject` / `email.body` / `email.fields`. No `pda.diagnostic_reports` row is
written and no email is sent. `tool_last_result` returns `sandbox: true` — trust each tool's own `ok`.
