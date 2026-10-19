# INC-2026-019: Cavitation on PUMP-01

| Field | Value |
| --- | --- |
| Incident ID | INC-2026-019 |
| Machine | PUMP-01 (Plant A, Cooling loop 1) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2026-08-14T01:28:19.345Z |
| Resolved | 2026-08-14T16:32:24.929Z |
| Confirmed fault category | cavitation |
| Unplanned downtime | 10.5 h |
| Related procedure | SOP-PUMP-102 Cavitation and suction troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 68.128 | degC |
| vibration_mm_s | 5.6 | mm/s RMS |
| discharge_pressure_bar | 4.147 | bar |
| flow_m3h | 101.45 | m3/h |
| motor_current_a | 38.007 | A |
| rpm | 1483.35 | rpm |

Log event codes observed: `VIB-202` (Broadband vibration), `FLW-320` (Flow below setpoint), `PRS-305` (Low suction pressure), `VIB-201` (High vibration).

## Root cause
Suction tank level below minimum while low-level alarm was bypassed.

## Corrective action
Restored low-level interlock, refilled tank, inspected impeller (light pitting).

## Lessons learned
Interlock bypasses must be logged and time-limited.

## Keywords
cavitation, VIB-202, FLW-320, PRS-305, VIB-201, PUMP-01, centrifugal pump
