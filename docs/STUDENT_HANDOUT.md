# Student handout: Predictive Diagnostic Assistant

1. Open the workshop page your instructor gives you.
2. Click **Start run**, enter your email (diagnostic reports are sent there, at most 5), and click **Start**.
3. **Telemetry** shows PUMP-01 live: bearing temperature, vibration, pressure, flow, motor current and speed. The shaded band is the normal range.
4. **Anomaly score** is the model's score each reading. The dashed line is the threshold. Red dots are anomalous readings. A red diamond means the agents were triggered: 2 of the last 3 readings were anomalous.
5. **Agent activity** has one card per triggered anomaly. Watch the stages:
   - **Webhook:** the backend called the Karini recipe.
   - **Evidence:** Agent 1 read this run's logs, the pump's maintenance history and similar past incidents.
   - **Diagnosis:** Agent 2 ranked the likely causes, with evidence strength and safe inspection checks.
   - **Report / Email:** Agent 3 saved the report and emailed it to you.
   - **Recipe:** the Karini execution finished.
6. Open each section of the card to see what the agent found and which tools it called.
7. When the diagnosis is ready, the card reveals the **actual fault** the simulator injected. Compare it with the agent's top hypothesis. If they differ, look at the evidence: which log codes or past incidents point where?
8. Don't want to wait? Press **Inject fault now**. A run stops automatically after 10 minutes, or press **Stop**. Agent work already started still finishes.

Things to try:
- **Misalignment vs bearing wear:** both raise vibration and temperature. What evidence separates them? Hint: `VIB-205` and `MNT-610`.
- **Cavitation vs seal leak:** both lower pressure and flow. What differs?
- In one run, find a reading above the threshold that did *not* trigger the agents. Why not?
