#!/usr/bin/env python3
"""Generate docs/PDA_End_to_End_Test_Guide.docx (one-off, run with python-docx installed)."""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

OUT = Path(__file__).resolve().parent / "PDA_End_to_End_Test_Guide.docx"

NAVY = RGBColor(0x1F, 0x2A, 0x44)
GREY = RGBColor(0x6B, 0x72, 0x80)
MONO = "Consolas"

doc = Document()

# ---- base styles
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(11)


def heading(text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = NAVY
    return h


def para(text="", italic=False, bold=False, color=None, size=None):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.italic = italic
    r.bold = bold
    if color is not None:
        r.font.color.rgb = color
    if size is not None:
        r.font.size = Pt(size)
    return p


def bullet(text, level=0):
    p = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    p.add_run(text)
    return p


def numbered(text):
    p = doc.add_paragraph(style="List Number")
    p.add_run(text)
    return p


def code(text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.2)
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(6)
    for i, line in enumerate(text.strip("\n").splitlines()):
        if i:
            p.add_run("\n")
        r = p.add_run(line)
        r.font.name = MONO
        r.font.size = Pt(9.5)
    # light shading
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), "F2F3F5")
    pPr.append(shd)
    return p


def table(headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    for i, htext in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ""
        run = c.paragraphs[0].add_run(htext)
        run.bold = True
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            cells[i].paragraphs[0].add_run(str(val))
    doc.add_paragraph()
    return t


# =========================================================== title
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.LEFT
r = title.add_run("Predictive Diagnostic Assistant")
r.bold = True
r.font.size = Pt(24)
r.font.color.rgb = NAVY
sub = doc.add_paragraph()
r = sub.add_run("End-to-End Test Guide (real RDS + Karini)")
r.font.size = Pt(14)
r.font.color.rgb = GREY
meta = doc.add_paragraph()
r = meta.add_run("AWS workshop demo  |  per-run Karini recipe credentials  |  synthetic inference")
r.italic = True
r.font.color.rgb = GREY
doc.add_paragraph()

para("This guide walks one operator through a complete end-to-end test of the PDA workshop stack: "
     "database, backend, SPA, and the Karini recipe (three agents + email). It assumes the recent "
     "change where each student run supplies its own Karini webhook base URL, recipe ID, and x-api-token "
     "from the Start form. Follow the sections in order. Synthetic inference is used, so SageMaker is not required.")

# =========================================================== 0 prerequisites
heading("0. Prerequisites", 1)
table(["Component", "What you need"], [
    ["Python", "3.11+ on the backend host (3.12 verified on Windows)."],
    ["Database", "Postgres 16 / RDS reachable; schema owner login (RDS master 'postgres')."],
    ["DBeaver", "To run the SQL files against RDS (SETUP_GUIDE section 3)."],
    ["Karini tenant", "A recipe published with the 2 routers + 3 agents; a webhook base URL, recipe ID, x-api-token."],
    ["Email", "The maintenance_email tool configured with a working sender (SES or SMTP)."],
    ["Network", "RDS security group allows 5432 inbound from Karini egress IPs AND from the backend host."],
])
para("You will need two kinds of Karini credentials:", bold=True)
bullet("Database tool (pda_agent / its password) - used by all three agents to call pda.tool_* functions.")
bullet("Webhook credentials (base URL + recipe ID + x-api-token) - entered per run on the SPA Start form.")

# =========================================================== 1 database
heading("1. Load the database", 1)
para("Apply the schema, functions, roles, and seed to RDS. The all_in_one.sql file drops and rebuilds "
     "schema pda and resets the pda_app / pda_agent passwords on every run, so it is a clean-slate reset.")
numbered("Open db/03_roles.sql (or the role block inside all_in_one.sql) and set the pda_app and pda_agent passwords you intend to use.")
numbered("In DBeaver, connect to RDS as the schema owner (master user 'postgres', database 'postgres').")
numbered("Run db/all_in_one.sql in full. Alternatively run 01_schema.sql, 02_agent_functions.sql, 03_roles.sql, 04_seed.sql in that order.")
para("Verify the new per-run columns exist:", bold=True)
code("SELECT column_name FROM information_schema.columns\n"
     "WHERE table_schema='pda' AND table_name='runs'\n"
     "  AND column_name LIKE 'karini_%';")
para("Expected: karini_base_url, karini_recipe_id, karini_api_token.", italic=True)
para("Verify seed logs loaded:", bold=True)
code("SELECT count(*) FROM pda.machine_logs WHERE run_id IS NULL;   -- expect 272")

# =========================================================== 2 db-tool acceptance
heading("2. Karini DB tool acceptance (privilege boundary)", 1)
para("Run karini/test/db_tool_acceptance.md through the Karini database tool configured as pda_agent. "
     "This is the security gate: the agent login must only be able to EXECUTE pda.tool_* functions.")
table(["Check", "Expected"], [
    ["current_user", "pda_agent (NOT postgres)."],
    ["SELECT ... FROM pda.runs", "permission denied for table runs."],
    ["DELETE FROM pda.machine_logs", "permission denied for table machine_logs."],
    ["SELECT pda.tool_get_event(...)", "returns one JSON object."],
])
para("If current_user is postgres or a raw table SELECT succeeds, STOP: the DB tool is using the wrong "
     "login. Fix it to pda_agent before continuing.", color=RGBColor(0xB0, 0x00, 0x00))

# =========================================================== 3 backend
heading("3. Start the backend", 1)
para("Create .env from .env.example and set DATABASE_URL to the pda_app login on RDS. "
     "Leave the global KARINI_* values blank (or set a fallback) - students will supply their own per run.")
code("# .env (key lines)\n"
     "DATABASE_URL=postgresql://pda_app:<password>@load-opt-demo.cr0wcueo0rpo.us-east-1.rds.amazonaws.com:5432/postgres?sslmode=require\n"
     "INFERENCE_MODE=synthetic\n"
     "KARINI_ENABLED=true\n"
     "KARINI_BASE_URL=\n"
     "KARINI_RECIPE_ID=\n"
     "KARINI_API_TOKEN=")
para("Run the backend (Windows launcher handles the psycopg event-loop requirement):", bold=True)
code("python run_local.py")
para("On Linux/Docker use the normal uvicorn entrypoint instead. Then confirm health:", italic=True)
code("# browser or curl\n"
     "GET http://localhost:8000/api/health   -> {\"ok\": true, \"active_runs\": 0}\n"
     "GET http://localhost:8000/api/config   -> inference_mode, threshold, karini_configured")
para("Note: karini_configured in /api/config reflects only the global default. A run with its own "
     "credentials works even when this is false.", italic=True)

# =========================================================== 4 per-run creds happy path
heading("4. End-to-end run with per-run Karini credentials", 1)
para("This is the main test. One browser acts as one student.")
numbered("Open http://localhost:8000 and click Start run.")
numbered("Enter a real email you can check (used only for this run's report, max 5 emails).")
numbered("Expand 'Your Karini recipe' and fill all three fields:")
bullet("Karini base URL - e.g. https://app.karini.ai", 1)
bullet("Recipe ID - the bare id, or paste the full webhook URL (the backend strips it to the id)", 1)
bullet("API token - your x-api-token", 1)
numbered("Click Start. The browser stores the creds in localStorage (key pda_karini) and the run token (pda_runs).")
numbered("Watch the live dashboard: telemetry every 10 s, the score chart, and logs.")
numbered("Click 'Inject fault now' to force a fault on the next reading (otherwise wait for the random fault).")
numbered("After 2 of 3 readings are anomalous, the backend posts YOUR recipe. The Recipe stage turns active, then the three agents run.")
numbered("Confirm the answer reveal (actual fault) appears after diagnosis, and the report + email status show on the Agent 3 card.")
numbered("Check your inbox for the HTML report email.")

para("Prefill check:", bold=True)
bullet("Click Start run again. The three Karini fields should be pre-filled from the last run. This confirms per-student reuse across runs.")

para("Isolation check (two recipes):", bold=True)
bullet("In a second browser (or private window), Start a run with a DIFFERENT recipe ID/token.")
bullet("Confirm each run's execution posts to its own recipe. The run row stores its own creds; neither run uses the other's.")

# =========================================================== 5 verify in DB
heading("5. Verify in the database", 1)
para("Replace <RUN_ID> with the run_id shown on the dashboard.")
code("-- the run stored its own creds (token is intentionally never shown in the SPA)\n"
     "SELECT run_id, karini_base_url, karini_recipe_id,\n"
     "       (karini_api_token IS NOT NULL) AS has_token\n"
     "FROM pda.runs WHERE run_id='<RUN_ID>';")
code("-- execution reached success and used the right recipe\n"
     "SELECT event_id, status, karini_status, http_status, error\n"
     "FROM pda.karini_executions WHERE run_id='<RUN_ID>' ORDER BY created_at;")
code("-- all three agents persisted a trace\n"
     "SELECT agent, kind, tool, ok FROM pda.agent_traces\n"
     "WHERE run_id='<RUN_ID>' AND kind='output' ORDER BY agent;")
code("-- report saved and email submitted\n"
     "SELECT event_id, severity, overall_confidence, email_status, email_detail\n"
     "FROM pda.diagnostic_reports WHERE run_id='<RUN_ID>';")
table(["Signal", "Pass"], [
    ["karini_executions.status", "success"],
    ["agent_traces", "two output rows: evidence_gatherer, diagnostic_reporter, ok=true"],
    ["diagnostic_reports.email_status", "submitted"],
    ["Inbox", "HTML report email received"],
])

# =========================================================== 6 fallback & negative
heading("6. Fallback and negative tests", 1)
table(["Scenario", "Steps", "Expected"], [
    ["Global fallback", "Set KARINI_* in .env, restart, Start a run leaving the three fields blank.",
     "Run posts using the env default recipe."],
    ["No creds anywhere", "Blank .env Karini values AND blank Start fields; trigger a fault.",
     "Execution -> post_failed with 'no Karini credentials for this run'."],
    ["Partial creds", "Fill only 1 or 2 of the three Start fields.",
     "SPA blocks submit: 'provide the base URL, recipe ID and API token together'."],
    ["Bad base URL", "Enter a base URL without http(s).",
     "400 error: 'Karini base URL must start with http:// or https://'."],
    ["Email cap", "Trigger more than 5 emails in one run.",
     "6th report saved with email_status skipped_cap; no email."],
    ["Token isolation", "Open the run URL in a browser without the run token.",
     "'Run not available in this browser' - no data shown."],
])

# =========================================================== 7 email format
heading("7. Email formatting check", 1)
para("The report email body is built as HTML by pda.tool_save_report (or assembled by Agent 3 from the "
     "template in karini/prompts/agent3_email_template.html).")
bullet("If the email renders with headings, a key-facts table, telemetry table, and hypothesis cards: HTML send is working.")
bullet("If you see raw <table>/<div> tags as text: the maintenance_email tool is sending text/plain. Set it to HTML (text/html).")

# =========================================================== 8 cleanup
heading("8. Cleanup after testing", 1)
para("Remove test runs without wiping the shared seed logs (never TRUNCATE pda.runs CASCADE).")
code("DELETE FROM pda.runs WHERE run_id='<RUN_ID>';   -- cascades to that run's events/logs/execs/reports")
para("To reset the whole database before the workshop, re-run db/all_in_one.sql (it drops and rebuilds "
     "schema pda and reseeds). Rotate any Karini tokens used during testing.", italic=True)

# =========================================================== 9 troubleshooting
heading("9. Troubleshooting quick map", 1)
table(["Symptom", "Look at"], [
    ["No triggers", "model_predictions.trigger_decision; threshold env; INFERENCE_MODE."],
    ["Execution post_failed", "run's karini_base_url/recipe_id/token; karini_executions.error; recipe published?"],
    ["Stuck accepted -> timed_out", "Karini run logs; router output must be {\"next\":...}."],
    ["Agent says write failed", "agent_traces for the event; DB tool commit behaviour; dollar-quote tag."],
    ["Email failed", "maintenance_email sender identity; diagnostic_reports.email_status."],
    ["Dashboard not live", "Caddy flush_interval -1 (prod); /api/health; LISTEN loop logs."],
    ["Wrong diagnosis", "tool_get_logs window; fault-diagnosis skill rules; KB results."],
    ["permission denied for pda_agent", "GRANTs in 03_roles.sql for changed function signatures."],
])

doc.save(OUT)
print("wrote", OUT)
