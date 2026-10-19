-- Delete workshop runs (and all their readings, logs, executions, traces, reports) older than 7 days.
-- Seed history (run_id NULL) and kb_documents are kept. Run as the master user after the workshop.
DELETE FROM pda.runs WHERE started_at < now() - interval '7 days';
-- Everything: DELETE FROM pda.runs;
