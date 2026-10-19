# INC-2026-011: Mechanical seal leak on PUMP-02

| Field | Value |
| --- | --- |
| Incident ID | INC-2026-011 |
| Machine | PUMP-02 (Plant A, Cooling loop 2) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2026-04-23T02:39:41.289Z |
| Resolved | 2026-04-24T01:21:01.701Z |
| Confirmed fault category | seal_leak |
| Unplanned downtime | 16.4 h |
| Related procedure | SOP-PUMP-103 Mechanical seal leak troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 64.994 | degC |
| vibration_mm_s | 2.91 | mm/s RMS |
| discharge_pressure_bar | 4.951 | bar |
| flow_m3h | 107.12 | m3/h |
| motor_current_a | 42.152 | A |
| rpm | 1480.351 | rpm |

Log event codes observed: `SEL-510` (Seal leak detector), `PRS-306` (Discharge pressure decay), `FLW-320` (Flow below setpoint), `SEL-590` (Seal leak rate high).

## Root cause
Mechanical seal faces worn after a dry-running event.

## Corrective action
Replaced mechanical seal cartridge, verified seal flush flow.

## Lessons learned
Dry running for under 2 minutes was enough to damage the faces.

## Keywords
seal leak, SEL-510, PRS-306, FLW-320, SEL-590, PUMP-02, centrifugal pump
