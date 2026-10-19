-- Verify Agent 3 emailed the student address from the DB, not the tool's hardcoded recipient.
-- Run in DBeaver as the master user (postgres), or via psql. Read-only.
--
-- PASS criteria per row:
--   recipient_matches_run = true   (email_to equals runs.notify_email)
--   email_status          = 'submitted'  (tool accepted the send) or 'skipped_cap'
-- A row with recipient_matches_run = false means Agent 3 used the wrong address.

SELECT r.run_id,
       r.notify_email                         AS run_notify_email,     -- source of truth (what the student entered)
       d.email_to                             AS report_email_to,      -- what tool_save_report handed the agent
       (d.email_to = r.notify_email)          AS recipient_matches_run,
       d.email_status,
       d.email_subject,
       left(d.email_detail, 80)               AS email_detail,
       d.created_at
  FROM pda.diagnostic_reports d
  JOIN pda.runs r ON r.run_id = d.run_id
 ORDER BY d.created_at DESC
 LIMIT 20;

-- Quick aggregate: any mismatch at all?
SELECT count(*) FILTER (WHERE d.email_to <> r.notify_email) AS wrong_recipient_rows,
       count(*)                                             AS total_reports
  FROM pda.diagnostic_reports d
  JOIN pda.runs r ON r.run_id = d.run_id;
