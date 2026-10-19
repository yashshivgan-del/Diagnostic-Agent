# Predictive Diagnostic Assistant: AWS workshop

Students open one web page, enter their email and press **Start**. A simulated industrial pump streams telemetry every 10 seconds, scored live by anomaly models on Amazon SageMaker. When a fault is confirmed, one shared **Karini AI** recipe runs three agents:
- **Evidence Gatherer:** reads the run's machine logs and the pump's history in PostgreSQL, and searches past incidents in a Knowledge Base.
- **Diagnostic Investigator:** ranks the likely causes using rules from its skill.
- **Report and Notification:** saves the report and emails it to the student.

Every step appears live on the student's dashboard. Afterwards the dashboard reveals the true fault next to the agents' top hypothesis.

**Start with [`docs/SETUP_GUIDE.md`](docs/SETUP_GUIDE.md).** For a 5-minute local demo with a mock Karini: `cp .env.example .env && docker compose up --build`, then open http://localhost:8000.

| Folder | Contents |
| --- | --- |
| `backend/` | Starlette backend: runs, simulator loop, SageMaker calls, Karini dispatch + polling, live updates; `static/` = the dashboard |
| `simulator/` | PUMP-01 telemetry and log generator with the random 5-minute fault schedule; fault signatures |
| `db/` | RDS / DBeaver scripts: `01_schema`, `02_agent_functions`, `03_roles`, `04_seed` (+ `all_in_one`, `05_cleanup`) |
| `karini/` | Recipe layout, 5 prompts (2 routers, 3 agents), 3 skills (+ zips), tool definitions, DB-tool acceptance test |
| `data/` | Synthetic data: model training sets, 20 incident reports + 7 procedures for the Knowledge Base, generator |
| `ml/` | SageMaker RCF + XGBoost training/deployment, threshold calibration, local check, cleanup |
| `deploy/` | EC2 production compose (backend + Caddy HTTPS), Caddyfile, IAM policy |
| `tools/mock_karini.py` | Karini webhook emulator that plays the agents with fixed rules (local dry runs) |
| `docs/` | Setup guide, student handout |

All data is synthetic. "Synthetic" inference mode is a demo score, not an ML prediction, and the dashboard labels it. Agents give advisory diagnoses only and never control equipment.
# Diagnostic-Agent
