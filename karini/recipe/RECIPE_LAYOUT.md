# Karini recipe layout: `pda-diagnostic-recipe` (simplified for the workshop)

One recipe serves every student. The backend calls it only for confirmed anomalies.
The system was simplified from 5 functional nodes to 3: one router guard, then two agents.

```
Webhook ──► Start ──► entry_router ──► evidence_gatherer ──► diagnostic_reporter ──► End
                          │ (default)
                          └────────────► End
```

## Nodes

Node names must match exactly: the router returns them as `{"next": "<node name>"}`.

| Node name | Type | Prompt file | Tools (tool box) | Skill(s) | Settings |
| --- | --- | --- | --- | --- | --- |
| Webhook | `webhook` | - | - | - | Generate the token; long-running task ON; timeout at least 300 s |
| Start | `start` | - | - | - | - |
| `entry_router` | `router` | `prompts/entry_router.md` | - | - | Metadata ON; message context: last message; small fast model; temperature 0 |
| `evidence_gatherer` | `agent2` | `prompts/agent1_evidence_gatherer.md` | `pda_database`, `pda_incidents_kb`, `pda_procedures_kb` | `evidence-retrieval` | Metadata ON; max iterations 14; message context: last message |
| `diagnostic_reporter` | `agent2` | `prompts/agent2_diagnostic_reporter.md` | `pda_database`, `maintenance_email` | `fault-diagnosis` + `report-notification` | Message context: node variable `evidence_result` = last message of `evidence_gatherer`; max iterations 10; strongest reasoning model |
| End | `end` | - | - | - | - |

## Edges

| From | To | Type |
| --- | --- | --- |
| Webhook | Start | plain |
| Start | entry_router | plain |
| entry_router | evidence_gatherer | router edge |
| entry_router | End | router edge, **default** |
| evidence_gatherer | diagnostic_reporter | plain |
| diagnostic_reporter | End | plain |
| each agent | its tool box / skill(s) | agent-to-tool-box, agent-to-skill |

## What changed from the 3-agent version
- `evidence_router` node: **removed**. Evidence always flows straight to `diagnostic_reporter`.
- `diagnostic_investigator` + `report_notifier`: **merged** into one `diagnostic_reporter` that
  diagnoses (skill `fault-diagnosis`), then saves the report and emails it (skill `report-notification`).
- The single knowledge base `incident_knowledge_base` is **split** into two KB tools:
  `pda_incidents_kb` (dataset "PDA incidents") and `pda_procedures_kb` (dataset "PDA procedures-V1").
- The agents' DB names are now exactly `evidence_gatherer` and `diagnostic_reporter`. The merged
  agent records ONE combined output (`pda.tool_record_output(event_id, 'diagnostic_reporter', ...)`)
  and the report/notification traces are attributed to `diagnostic_reporter` too.

## Model suggestions

| Node | Temperature | Why |
| --- | --- | --- |
| entry_router | 0 | One short structured decision |
| evidence_gatherer | 0 | Many tool calls; must copy data exactly |
| diagnostic_reporter | 0 to 0.2 | The reasoning step; also assembles the report and email |

## What the backend sends

The body follows the payload contract in the Karini guide. `metadata` carries IDs and the prediction;
agents read everything else through `pda.tool_*`.

```json
{
  "input_message": "agent: evidence_gatherer\nDiagnose anomaly event 8efb47c7-dd28-4aab-8492-37f126cd5522 on PUMP-01 (run b76ee94c-df6a-4aed-95ea-07adbb283d73).",
  "files": [],
  "metadata": {
    "agent": "evidence_gatherer", "trigger": "anomaly",
    "run_id": "b76ee94c-df6a-4aed-95ea-07adbb283d73", "event_id": "8efb47c7-dd28-4aab-8492-37f126cd5522",
    "machine_id": "PUMP-01", "timestamp": "2026-10-14T08:07:15.121Z", "notify_email": "student@example.com",
    "anomaly_score": 3.322, "threshold": 2.5, "is_anomaly": true, "confirmed": true,
    "predicted_fault": "misalignment", "predicted_fault_probability": 0.71,
    "second_fault": "bearing_wear", "second_fault_probability": 0.24,
    "inference_mode": "synthetic", "today": "2026-10-14"
  }
}
```

## What the backend reads back

- **Live dashboard:** rows the agents write through `pda.tool_*`: tool calls, each agent's output,
  the report and the email status. The dashboard timeline shows: Confirmed, Webhook, Evidence,
  Diagnosis & report, Email, Recipe.
- **Execution status:** the backend polls `GET /api/webhook/request/<request_id>` until `success`
  or `failed`, then stores the final answer of `diagnostic_reporter`.
