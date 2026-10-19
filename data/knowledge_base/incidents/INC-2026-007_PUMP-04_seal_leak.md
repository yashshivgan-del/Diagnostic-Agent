# INC-2026-007: Mechanical seal leak on PUMP-04

| Field | Value |
| --- | --- |
| Incident ID | INC-2026-007 |
| Machine | PUMP-04 (Plant B, Boiler feed) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2026-03-12T17:38:11.701Z |
| Resolved | 2026-03-13T15:39:38.788Z |
| Confirmed fault category | seal_leak |
| Unplanned downtime | 16.2 h |
| Related procedure | SOP-PUMP-103 Mechanical seal leak troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 66.304 | degC |
| vibration_mm_s | 2.878 | mm/s RMS |
| discharge_pressure_bar | 4.891 | bar |
| flow_m3h | 108.365 | m3/h |
| motor_current_a | 42.583 | A |
| rpm | 1481.969 | rpm |

Log event codes observed: `SEL-510` (Seal leak detector), `PRS-306` (Discharge pressure decay), `FLW-320` (Flow below setpoint), `SEL-590` (Seal leak rate high).

## Root cause
Seal flush line blocked by scale.

## Corrective action
Descaled flush line, replaced seal, added flush-flow indicator.

## Lessons learned
Flush line blockage gives a slow leak that worsens over days.

## Keywords
seal leak, SEL-510, PRS-306, FLW-320, SEL-590, PUMP-04, centrifugal pump
