# INC-2026-017: Bearing wear on PUMP-03

| Field | Value |
| --- | --- |
| Incident ID | INC-2026-017 |
| Machine | PUMP-03 (Plant A, Process water) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2026-07-31T06:03:05.150Z |
| Resolved | 2026-07-31T19:46:06.870Z |
| Confirmed fault category | bearing_wear |
| Unplanned downtime | 5.8 h |
| Related procedure | SOP-PUMP-101 Bearing condition troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 77.619 | degC |
| vibration_mm_s | 7.187 | mm/s RMS |
| discharge_pressure_bar | 6.051 | bar |
| flow_m3h | 118.281 | m3/h |
| motor_current_a | 43.159 | A |
| rpm | 1473.815 | rpm |

Log event codes observed: `VIB-201` (High vibration), `LUB-150` (Lubrication overdue), `TMP-110` (Bearing temperature high).

## Root cause
Lubrication interval missed for approximately 3 months.

## Corrective action
Replaced drive-end bearing, added the pump to the CMMS lubrication route.

## Lessons learned
Pump was missing from the lubrication route after a CMMS migration.

## Keywords
bearing wear, VIB-201, LUB-150, TMP-110, PUMP-03, centrifugal pump
