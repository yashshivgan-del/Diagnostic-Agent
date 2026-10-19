-- =============================================================================
-- Predictive Diagnostic Assistant (workshop) - 03 roles and permissions
-- EDIT THE TWO PASSWORDS BELOW before running. Run as the schema owner (RDS master user).
--   pda_app   : backend login (reads/writes application tables, LISTEN for live updates)
--   pda_agent : Karini database tool login (may ONLY execute pda.tool_* functions)
-- Re-running is safe; it also re-applies the grants.
-- =============================================================================
DO $do$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'pda_app') THEN
        CREATE ROLE pda_app LOGIN PASSWORD 'CHANGE_ME_app_password';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'pda_agent') THEN
        CREATE ROLE pda_agent LOGIN PASSWORD 'CHANGE_ME_agent_password';
    END IF;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO pda_app, pda_agent', current_database());
END
$do$;
-- Nobody gets anything by default.
REVOKE ALL ON SCHEMA pda FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA pda FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA pda FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA pda REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
-- Backend
GRANT USAGE ON SCHEMA pda TO pda_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA pda TO pda_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA pda TO pda_app;
ALTER ROLE pda_app SET statement_timeout = '15s';
-- Karini agents: functions only, no table access at all.
GRANT USAGE ON SCHEMA pda TO pda_agent;
REVOKE ALL ON ALL TABLES IN SCHEMA pda FROM pda_agent;
GRANT EXECUTE ON FUNCTION
    pda.tool_get_event(TEXT),
    pda.tool_get_logs(TEXT, INT),
    pda.tool_get_history(TEXT, INT),
    pda.tool_search_incidents(TEXT, TEXT),
    pda.tool_record_output(TEXT, TEXT, JSONB),
    pda.tool_save_report(TEXT, JSONB),
    pda.tool_record_notification(TEXT, TEXT, TEXT),
    pda.tool_last_result(TEXT, TEXT)
TO pda_agent;
ALTER ROLE pda_agent SET statement_timeout = '10s';
-- Hardening (best effort; some managed services do not allow these, which is reported as a NOTICE):
--  * hide other sessions' SQL text: all agents share the pda_agent login, so pg_stat_activity would
--    otherwise show the event_ids other agents are working on.
DO $do$
BEGIN
    -- REVOKE CREATE ON SCHEMA public FROM PUBLIC is intentionally NOT run: this database may be shared
    -- with other applications (e.g. the default 'postgres' database) and the revoke would affect them.
    IF (SELECT rolsuper FROM pg_roles WHERE rolname = current_user) THEN
        REVOKE SELECT ON pg_catalog.pg_stat_activity FROM PUBLIC;
    ELSE
        RAISE NOTICE 'pg_stat_activity left as is (needs superuser; not possible on RDS) - see SETUP_GUIDE known limitations';
    END IF;
END
$do$;
-- Verify (expect: pda_agent true for tool_*, false for tables; pda_app true for tables):
-- SELECT has_function_privilege('pda_agent', 'pda.tool_get_event(text)', 'EXECUTE')      AS agent_can_call_tool,
--        has_table_privilege('pda_agent', 'pda.machine_logs', 'SELECT')                   AS agent_can_read_logs,
--        has_function_privilege('pda_agent', 'pda._trace(uuid,text,text,jsonb,jsonb)', 'EXECUTE') AS agent_can_call_internal,
--        has_table_privilege('pda_app', 'pda.runs', 'INSERT')                             AS app_can_write_runs;
