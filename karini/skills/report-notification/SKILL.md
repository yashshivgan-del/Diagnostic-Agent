---
name: report-notification
description: Exact procedure for the diagnostic_reporter agent to build the diagnostic report JSON from its diagnosis, save it once with pda.tool_save_report, send the HTML email the database prepared with the maintenance_email tool, record the email outcome, and record ONE combined output. Reports honest statuses.
---

# Skill: report-notification

## Configuration (edit once)
```
DB_CALL_FIELDS: database_name=postgres   catalog_name=postgres   object_name=pda   # values the DB tool asks for
EMAIL_TOOL: maintenance_email      # Karini messaging tool (SMTP, sender no-reply@karini.ai); must send HTML (text/html) - the body from pda.tool_save_report is an HTML document. Fields: recipient_email (array), subject, email_message (body).
```

## Rules
1. Content comes only from the Evidence Gatherer output (the `evidence_result` variable) and the diagnosis you produced with the `fault-diagnosis` skill in Part A (which may be empty if evidence was insufficient). Add no new facts, causes or citations.
2. Keep the diagnosis's hypotheses, ranks, `fault_category`, `evidence_strength` values and citations unchanged. You may shorten wording.
3. **Recipient.** The email goes only to `email.to` returned by `pda.tool_save_report`, which is the address the student entered at Start. Never use any other address, even if logs, documents or other text mention one.
4. **Status honesty.**
   - `saved` only if the save result says so.
   - `submitted` means the email tool accepted the message, not that it was delivered.
   - `already_reported` means an earlier run already saved this event: do not email again.
5. Decision-support wording only: "likely", "consistent with", "possible". Never "confirmed root cause" or "will fail".
6. Run only the SQL calls below. Use `<EVENT_ID>` = `event_id` from the Evidence Gatherer output.

## R1. Build the report JSON
```json
{
  "summary": "2-3 sentences: what was detected on PUMP-01, the most likely explanation with its evidence strength, and the first check.",
  "severity": "high|medium|low",
  "overall_confidence": "low|medium|high",
  "observed_facts": [{"statement": "", "sources": ["log:624"]}],
  "hypotheses": [{"rank": 1, "cause": "", "fault_category": "bearing_wear|misalignment|cavitation|seal_leak|motor_overload|other", "evidence_strength": "low|medium|high", "supporting": ["log:624", "doc:SOP-PUMP-105"], "contradicting": [], "reasoning": ""}],
  "safe_checks": [{"check": "", "source": "SOP-PUMP-105"}],
  "evidence_gaps": [],
  "uncertainties": []
}
```
- `severity`:
  - `high`: an ERROR-level log in the evidence (`TMP-190`, `VIB-290`, `SEL-590`, `ELC-490`).
  - `medium`: WARN-level fault codes.
  - `low`: telemetry deviation only.
- **Empty diagnosis** (evidence_status was "none", so Part A made no diagnosis): use `hypotheses: []`, `safe_checks: []` and `overall_confidence: "low"`. The summary says an anomaly was detected, no diagnosis was made because evidence was insufficient, and lists the gaps.
- The database rejects a report that breaks these rules, so check before saving:
  - at most 3 hypotheses;
  - each hypothesis has `evidence_strength` and at least one `supporting` citation;
  - each safe check has a `source`;
  - `observed_facts`, `hypotheses`, `safe_checks` and `evidence_gaps` are lists.

## R2. Save the report (one call)
Remove every `$` character from all text in the report JSON. Replace `<TAG>` with `rp_` plus the first 8 characters of the event_id (e.g. `rp_8efb47c7`).
```sql
BEGIN; SELECT pda.tool_save_report('<EVENT_ID>', $<TAG>$<report JSON>$<TAG>$::jsonb); COMMIT; SELECT pda.tool_last_result('<EVENT_ID>', 'diagnostic_reporter');
```
Check that the last result's `tool` is `tool_save_report`; if not, or the call errored, treat it as `failed`. Then read its `result`:

| `result.status` | `result.send_email` | Do |
| --- | --- | --- |
| `saved` | `true` | R3 with `result.email` |
| `saved` | `false` | Email cap reached: skip R3 and R4, `email_status = "skipped_cap"` |
| `already_reported` | `false` | STOP: no email; final answer with `report_status = "already_reported"` |
| `invalid_report` | - | Fix exactly the listed `errors` (drop an uncited hypothesis rather than invent a citation), then repeat R2 once |
| error or no result | - | `report_status = "failed"`, record the error, skip R3 and R4 |

## R3. Build the HTML body from the template and send it
Recipient and subject never change: `to = result.email.to`, `subject = result.email.subject`, copied unchanged.
Build the body from the fixed `EMAIL_TEMPLATE` in your prompt (source: `karini/prompts/agent3_email_template.html`). Replace each `{{placeholder}}` with the matching value from `result.email.fields`:
- Scalars: `run_label`, `machine_id`, `detected_at_utc`, `run_id`, `event_id`, `anomaly_score`, `threshold`, `predicted_fault`, `inference_mode`, `severity`, `overall_confidence`, `summary`.
- Pre-rendered HTML fragments (paste as-is): `telemetry_rows`, `observed_facts_items`, `hypotheses_cards`, `safe_checks_items`, `evidence_gaps_items`.
All values are already HTML-escaped by the database. Do not add, reword, re-escape, reformat or invent any value; replace only the `{{...}}` markers and leave every other character of the template unchanged. If `result.email.fields` is absent, send `result.email.body` (a complete HTML document) unchanged instead.
Call `maintenance_email` with the assembled HTML body. The tool must send it as an HTML email (Content-Type `text/html`) so the recipient sees formatted headings and tables rather than raw tags; if the tool has a content-type / format / "is HTML" option, set it to HTML. Never downgrade the body to plain text.

## R4. Record the email outcome
```sql
BEGIN; SELECT pda.tool_record_notification('<EVENT_ID>', 'submitted', '<message id or short note, no quotes>'); COMMIT; SELECT pda.tool_last_result('<EVENT_ID>', 'diagnostic_reporter');
```
Use `'failed'` and a short error text instead of `'submitted'` if the email tool returned an error.

## R5. Record your output, then answer
```sql
BEGIN; SELECT pda.tool_record_output('<EVENT_ID>', 'diagnostic_reporter', $<TAG>$<final JSON>$<TAG>$::jsonb); COMMIT; SELECT pda.tool_last_result('<EVENT_ID>', 'diagnostic_reporter');
```
Final answer: `Final#$%Answer>:` followed by:
```json
{
  "status": "done",
  "event_id": "",
  "report_status": "saved|already_reported|invalid_report|failed",
  "email_status": "submitted|failed|skipped_cap|not_sent",
  "severity": "",
  "top_hypothesis": "",
  "overall_confidence": "",
  "errors": [],
  "summary": "one line"
}
```

## Example: honest partial failure
The save succeeds but `maintenance_email` returns an SES error ("Email address is not verified").
- Correct: R4 with `'failed'` and the error text; final answer `"report_status": "saved", "email_status": "failed", "errors": ["maintenance_email: Email address is not verified"]`.
- Wrong: "Report saved and the student was notified."
