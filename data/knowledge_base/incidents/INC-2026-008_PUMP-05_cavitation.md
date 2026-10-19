# INC-2026-008: Cavitation on PUMP-05

| Field | Value |
| --- | --- |
| Incident ID | INC-2026-008 |
| Machine | PUMP-05 (Plant B, Wash-down) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2026-03-18T17:37:45.928Z |
| Resolved | 2026-03-19T18:44:27.078Z |
| Confirmed fault category | cavitation |
| Unplanned downtime | 16.4 h |
| Related procedure | SOP-PUMP-102 Cavitation and suction troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 65.53 | degC |
| vibration_mm_s | 5.295 | mm/s RMS |
| discharge_pressure_bar | 4.289 | bar |
| flow_m3h | 88.5 | m3/h |
| motor_current_a | 38.939 | A |
| rpm | 1485.451 | rpm |

Log event codes observed: `FLW-320` (Flow below setpoint), `PRS-305` (Low suction pressure), `VIB-202` (Broadband vibration), `VIB-201` (High vibration).

**Initial hypothesis:** Mechanical seal leak. This was ruled out during inspection; the confirmed cause was cavitation. Do not rely on vibration alone to distinguish them.

## Root cause
Suction strainer approximately 70% blocked.

## Corrective action
Cleaned suction strainer, added differential-pressure gauge across strainer.

## Lessons learned
Debris load increases after upstream tank cleaning.

## Keywords
cavitation, FLW-320, PRS-305, VIB-202, VIB-201, PUMP-05, centrifugal pump
