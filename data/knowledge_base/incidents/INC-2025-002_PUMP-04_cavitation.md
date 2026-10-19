# INC-2025-002: Cavitation on PUMP-04

| Field | Value |
| --- | --- |
| Incident ID | INC-2025-002 |
| Machine | PUMP-04 (Plant B, Boiler feed) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2025-11-15T12:18:46.226Z |
| Resolved | 2025-11-16T02:56:52.044Z |
| Confirmed fault category | cavitation |
| Unplanned downtime | 9.4 h |
| Related procedure | SOP-PUMP-102 Cavitation and suction troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 64.804 | degC |
| vibration_mm_s | 5.29 | mm/s RMS |
| discharge_pressure_bar | 4.206 | bar |
| flow_m3h | 92.146 | m3/h |
| motor_current_a | 37.801 | A |
| rpm | 1484.03 | rpm |

Log event codes observed: `FLW-320` (Flow below setpoint), `VIB-202` (Broadband vibration), `PRS-305` (Low suction pressure), `VIB-201` (High vibration).

## Root cause
Suction isolation valve left partially closed after maintenance.

## Corrective action
Fully opened suction valve, added valve-position check to the return-to-service checklist.

## Lessons learned
Return-to-service checklist did not include suction valve position.

## Keywords
cavitation, FLW-320, VIB-202, PRS-305, VIB-201, PUMP-04, centrifugal pump
