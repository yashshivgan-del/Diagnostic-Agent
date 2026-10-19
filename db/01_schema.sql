-- =============================================================================
-- Predictive Diagnostic Assistant (workshop) - 01 schema
-- PostgreSQL 13+ (Amazon RDS). Run as the database owner / RDS master user.
-- DBeaver: open this file, connect to the target database, Execute Script (Alt+X).
-- Re-running is safe (IF NOT EXISTS / OR REPLACE).
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS pda;
-- One row per Start..Stop session. No login: the run is the identity.
CREATE TABLE IF NOT EXISTS pda.runs (
    run_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    access_token    TEXT NOT NULL,          -- given only to the browser that started the run
    notify_email    TEXT NOT NULL CHECK (notify_email ~* '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$'),
    label           TEXT CHECK (char_length(label) <= 60),
    machine_id      TEXT NOT NULL DEFAULT 'PUMP-01',
    status          TEXT NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'stopped', 'auto_stopped', 'interrupted')),
    stop_reason     TEXT,
    seed            BIGINT NOT NULL,
    inference_mode  TEXT NOT NULL,
    threshold       DOUBLE PRECISION NOT NULL,
    email_cap       INT NOT NULL DEFAULT 5,
    emails_sent     INT NOT NULL DEFAULT 0,
    trigger_count   INT NOT NULL DEFAULT 0,
    karini_base_url  TEXT,                  -- per-run Karini creds (NULL = use backend env default)
    karini_recipe_id TEXT,
    karini_api_token TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    auto_stop_at    TIMESTAMPTZ NOT NULL,
    stopped_at      TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_runs_started ON pda.runs (started_at DESC);
-- One row per reading (every 10 s while the run is active).
CREATE TABLE IF NOT EXISTS pda.machine_events (
    event_id      UUID PRIMARY KEY,
    run_id        UUID NOT NULL REFERENCES pda.runs(run_id) ON DELETE CASCADE,
    seq           INT NOT NULL,
    ts            TIMESTAMPTZ NOT NULL,
    machine_id    TEXT NOT NULL,
    telemetry     JSONB NOT NULL,
    ground_truth  JSONB NOT NULL,          -- simulator truth; shown to students only after diagnosis
    UNIQUE (run_id, seq)
);
CREATE INDEX IF NOT EXISTS idx_events_run ON pda.machine_events (run_id, seq DESC);
-- Machine logs. run_id NULL = shared seed history (visible to every run's agents).
CREATE TABLE IF NOT EXISTS pda.machine_logs (
    log_id      BIGSERIAL PRIMARY KEY,
    run_id      UUID REFERENCES pda.runs(run_id) ON DELETE CASCADE,
    event_id    UUID,
    machine_id  TEXT NOT NULL,
    ts          TIMESTAMPTZ NOT NULL,
    log_level   TEXT NOT NULL CHECK (log_level IN ('DEBUG', 'INFO', 'WARN', 'ERROR')),
    event_code  TEXT NOT NULL,
    message     TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'simulator',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_logs_run_ts     ON pda.machine_logs (run_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_logs_machine_ts ON pda.machine_logs (machine_id, ts DESC);
-- SageMaker (or synthetic) result per reading + the backend's trigger decision.
CREATE TABLE IF NOT EXISTS pda.model_predictions (
    event_id            UUID PRIMARY KEY REFERENCES pda.machine_events(event_id) ON DELETE CASCADE,
    run_id              UUID NOT NULL REFERENCES pda.runs(run_id) ON DELETE CASCADE,
    inference_mode      TEXT NOT NULL,
    inference_status    TEXT NOT NULL CHECK (inference_status IN ('ok', 'failed')),
    anomaly_score       DOUBLE PRECISION,
    threshold           DOUBLE PRECISION NOT NULL,
    is_anomaly          BOOLEAN,
    confirmed           BOOLEAN NOT NULL DEFAULT false,   -- 2 of the last 3 readings anomalous
    predicted_fault     TEXT,
    fault_probabilities JSONB,
    trigger_decision    TEXT NOT NULL,
        -- normal | anomaly_unconfirmed | triggered | suppressed_not_rearmed | suppressed_trigger_cap
        -- | inference_failed | karini_disabled
    error               TEXT,
    latency_ms          INT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pred_run ON pda.model_predictions (run_id, created_at DESC);
-- One Karini recipe execution per triggered event (event_id = idempotency key).
CREATE TABLE IF NOT EXISTS pda.karini_executions (
    event_id          UUID PRIMARY KEY REFERENCES pda.machine_events(event_id) ON DELETE CASCADE,
    run_id            UUID NOT NULL REFERENCES pda.runs(run_id) ON DELETE CASCADE,
    status            TEXT NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued', 'posting', 'accepted', 'post_failed', 'success', 'failed', 'timed_out')),
    karini_status     TEXT,            -- raw status from Karini: inProcess | success | failed
    request_id        TEXT,
    http_status       INT,
    payload           JSONB NOT NULL,
    response          JSONB,
    final_answer      JSONB,
    final_answer_raw  TEXT,
    error             TEXT,
    attempts          INT NOT NULL DEFAULT 0,
    poll_count        INT NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    posted_at         TIMESTAMPTZ,
    last_polled_at    TIMESTAMPTZ,
    finished_at       TIMESTAMPTZ,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_exec_status ON pda.karini_executions (status);
CREATE INDEX IF NOT EXISTS idx_exec_run ON pda.karini_executions (run_id);
-- Every agent tool call and every agent's final output (written by pda.tool_* functions).
CREATE TABLE IF NOT EXISTS pda.agent_traces (
    trace_id    BIGSERIAL PRIMARY KEY,
    run_id      UUID NOT NULL REFERENCES pda.runs(run_id) ON DELETE CASCADE,
    event_id    UUID NOT NULL REFERENCES pda.machine_events(event_id) ON DELETE CASCADE,
    agent       TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('tool_call', 'output')),
    tool        TEXT,
    request     JSONB,
    response    JSONB,
    ok          BOOLEAN,
    summary     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_traces_event ON pda.agent_traces (event_id, trace_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_traces_output ON pda.agent_traces (event_id, agent) WHERE kind = 'output';
-- Diagnostic report + email outcome per event (written by pda.tool_save_report / tool_record_notification).
CREATE TABLE IF NOT EXISTS pda.diagnostic_reports (
    event_id            UUID PRIMARY KEY REFERENCES pda.machine_events(event_id) ON DELETE CASCADE,
    run_id              UUID NOT NULL REFERENCES pda.runs(run_id) ON DELETE CASCADE,
    report              JSONB NOT NULL,
    report_markdown     TEXT NOT NULL,
    top_hypothesis      TEXT,
    overall_confidence  TEXT,
    severity            TEXT,
    email_to            TEXT NOT NULL,
    email_subject       TEXT NOT NULL,
    email_body          TEXT NOT NULL,
    email_status        TEXT NOT NULL DEFAULT 'pending'
                        CHECK (email_status IN ('pending', 'submitted', 'failed', 'skipped_cap')),
    email_detail        TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_reports_run ON pda.diagnostic_reports (run_id);
-- Knowledge-base documents (copy of the Karini KB). Used only if the recipe is set to
-- INCIDENT_SEARCH=database (fallback when the Karini Knowledge Base node is not available).
CREATE TABLE IF NOT EXISTS pda.kb_documents (
    doc_id    TEXT PRIMARY KEY,
    title     TEXT NOT NULL,
    doc_type  TEXT NOT NULL CHECK (doc_type IN ('incident', 'procedure', 'reference')),
    content   TEXT NOT NULL,
    tsv       TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', title || ' ' || content)) STORED
);
CREATE INDEX IF NOT EXISTS idx_kb_tsv ON pda.kb_documents USING GIN (tsv);
-- -----------------------------------------------------------------------------
-- Live updates: every change that the dashboard shows raises a NOTIFY on channel
-- 'pda_live' with the run_id and key. The backend LISTENs and streams to the SPA.
-- Works for rows written by the backend AND by Karini agents (through tool_*).
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION pda.notify_change() RETURNS trigger
LANGUAGE plpgsql AS $fn$
DECLARE
    r JSONB := to_jsonb(NEW);
BEGIN
    PERFORM pg_notify('pda_live', json_build_object(
        'table', TG_TABLE_NAME, 'op', TG_OP,
        'run_id', r->>'run_id', 'event_id', r->>'event_id', 'trace_id', r->>'trace_id')::text);
    RETURN NEW;
END
$fn$;
DROP TRIGGER IF EXISTS trg_live_runs ON pda.runs;
CREATE TRIGGER trg_live_runs AFTER UPDATE ON pda.runs
    FOR EACH ROW EXECUTE FUNCTION pda.notify_change();
DROP TRIGGER IF EXISTS trg_live_pred ON pda.model_predictions;
CREATE TRIGGER trg_live_pred AFTER INSERT ON pda.model_predictions
    FOR EACH ROW EXECUTE FUNCTION pda.notify_change();
DROP TRIGGER IF EXISTS trg_live_exec ON pda.karini_executions;
CREATE TRIGGER trg_live_exec AFTER INSERT OR UPDATE ON pda.karini_executions
    FOR EACH ROW EXECUTE FUNCTION pda.notify_change();
DROP TRIGGER IF EXISTS trg_live_trace ON pda.agent_traces;
CREATE TRIGGER trg_live_trace AFTER INSERT OR UPDATE ON pda.agent_traces
    FOR EACH ROW EXECUTE FUNCTION pda.notify_change();
DROP TRIGGER IF EXISTS trg_live_report ON pda.diagnostic_reports;
CREATE TRIGGER trg_live_report AFTER INSERT OR UPDATE ON pda.diagnostic_reports
    FOR EACH ROW EXECUTE FUNCTION pda.notify_change();
