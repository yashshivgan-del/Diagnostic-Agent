# INC-2026-012: Cavitation on PUMP-02

| Field | Value |
| --- | --- |
| Incident ID | INC-2026-012 |
| Machine | PUMP-02 (Plant A, Cooling loop 2) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2026-05-07T18:00:42.577Z |
| Resolved | 2026-05-08T11:37:30.225Z |
| Confirmed fault category | cavitation |
| Unplanned downtime | 12.9 h |
| Related procedure | SOP-PUMP-102 Cavitation and suction troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 64.891 | degC |
| vibration_mm_s | 5.454 | mm/s RMS |
| discharge_pressure_bar | 4.393 | bar |
| flow_m3h | 100.832 | m3/h |
| motor_current_a | 38.028 | A |
| rpm | 1481.349 | rpm |

Log event codes observed: `FLW-320` (Flow below setpoint), `VIB-202` (Broadband vibration), `PRS-305` (Low suction pressure), `VIB-201` (High vibration).

## Root cause
Suction isolation valve left partially closed after maintenance.

## Corrective action
Fully opened suction valve, added valve-position check to the return-to-service checklist.

## Lessons learned
Return-to-service checklist did not include suction valve position.

## Keywords
cavitation, FLW-320, VIB-202, PRS-305, VIB-201, PUMP-02, centrifugal pump
