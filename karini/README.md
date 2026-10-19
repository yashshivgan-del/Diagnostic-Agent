# Karini package

| Path | Use |
| --- | --- |
| `recipe/RECIPE_LAYOUT.md` | Nodes, settings, edges, webhook payload |
| `prompts/entry_router.md` | The one router, after Start: anomaly → `evidence_gatherer`, else End |
| `prompts/agent1_evidence_gatherer.md` | Agent 1 prompt (two KB tools) |
| `prompts/agent2_diagnostic_reporter.md` | Agent 2 prompt (merged diagnosis + report + email) |
| `prompts/agent3_email_template.html` | HTML email template filled by `diagnostic_reporter` |
| `skills/<name>/SKILL.md` | Skill sources (edit the configuration block at the top) |
| `skills_zip/<name>.zip` | Ready-to-upload skill zips (same content) |
| `tools/TOOLS.md` | `pda_database`, `pda_incidents_kb`, `pda_procedures_kb`, `maintenance_email`: settings and descriptions |
| `test/db_tool_acceptance.md` | Run through `pda_database` before building agents |

Conventions from the Karini framework guide used throughout:
- Routers answer `{"next": "<node name>"}`.
- Literal braces in prompts are doubled.
- Agent final answers start with `Final#$%Answer>:`.
- Agents read previous outputs through node variables.
- Agents call database functions only, never tables. Writes use `BEGIN; SELECT pda.tool_x(...); COMMIT; SELECT pda.tool_last_result('<event_id>', '<agent>');`.

Full steps: `docs/SETUP_GUIDE.md`, section 6.
