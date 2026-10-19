# INC-2026-020: Mechanical seal leak on PUMP-01

| Field | Value |
| --- | --- |
| Incident ID | INC-2026-020 |
| Machine | PUMP-01 (Plant A, Cooling loop 1) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2026-08-14T09:09:23.663Z |
| Resolved | 2026-08-14T23:54:34.144Z |
| Confirmed fault category | seal_leak |
| Unplanned downtime | 10.8 h |
| Related procedure | SOP-PUMP-103 Mechanical seal leak troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 66.601 | degC |
| vibration_mm_s | 3.184 | mm/s RMS |
| discharge_pressure_bar | 5.009 | bar |
| flow_m3h | 109.888 | m3/h |
| motor_current_a | 43.647 | A |
| rpm | 1479.27 | rpm |

Log event codes observed: `PRS-306` (Discharge pressure decay), `SEL-510` (Seal leak detector), `SEL-590` (Seal leak rate high), `FLW-320` (Flow below setpoint).

## Root cause
Seal flush line blocked by scale.

## Corrective action
Descaled flush line, replaced seal, added flush-flow indicator.

## Lessons learned
Flush line blockage gives a slow leak that worsens over days.

## Keywords
seal leak, PRS-306, SEL-510, SEL-590, FLW-320, PUMP-01, centrifugal pump
