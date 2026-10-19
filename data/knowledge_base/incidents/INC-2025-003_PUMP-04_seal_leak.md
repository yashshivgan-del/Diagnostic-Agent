# INC-2025-003: Mechanical seal leak on PUMP-04

| Field | Value |
| --- | --- |
| Incident ID | INC-2025-003 |
| Machine | PUMP-04 (Plant B, Boiler feed) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2025-11-16T08:45:41.846Z |
| Resolved | 2025-11-16T23:21:37.844Z |
| Confirmed fault category | seal_leak |
| Unplanned downtime | 7.9 h |
| Related procedure | SOP-PUMP-103 Mechanical seal leak troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 66.235 | degC |
| vibration_mm_s | 2.777 | mm/s RMS |
| discharge_pressure_bar | 4.911 | bar |
| flow_m3h | 110.532 | m3/h |
| motor_current_a | 41.457 | A |
| rpm | 1481.528 | rpm |

Log event codes observed: `SEL-510` (Seal leak detector), `PRS-306` (Discharge pressure decay), `FLW-320` (Flow below setpoint), `SEL-590` (Seal leak rate high).

## Root cause
Seal O-ring chemically degraded by process additive.

## Corrective action
Replaced seal with FKM O-ring variant.

## Lessons learned
Elastomer compatibility must be checked when water treatment chemicals change.

## Keywords
seal leak, SEL-510, PRS-306, FLW-320, SEL-590, PUMP-04, centrifugal pump
