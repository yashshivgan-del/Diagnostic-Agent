# INC-2026-014: Motor overload on PUMP-04

| Field | Value |
| --- | --- |
| Incident ID | INC-2026-014 |
| Machine | PUMP-04 (Plant B, Boiler feed) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2026-05-28T21:35:59.810Z |
| Resolved | 2026-05-29T17:00:23.047Z |
| Confirmed fault category | motor_overload |
| Unplanned downtime | 10.7 h |
| Related procedure | SOP-PUMP-104 Motor overload and electrical troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 77.715 | degC |
| vibration_mm_s | 3.054 | mm/s RMS |
| discharge_pressure_bar | 6.334 | bar |
| flow_m3h | 122.949 | m3/h |
| motor_current_a | 62.58 | A |
| rpm | 1468.969 | rpm |

Log event codes observed: `ELC-410` (Motor overcurrent), `ELC-412` (Phase imbalance), `TMP-110` (Bearing temperature high), `ELC-490` (Thermal overload pre-trip).

## Root cause
Motor winding insulation degradation causing phase imbalance.

## Corrective action
Motor replaced; failed motor sent for rewind. Insulation resistance trended monthly.

## Lessons learned
Phase imbalance warnings preceded the overload by about 10 days.

## Keywords
motor overload, ELC-410, ELC-412, TMP-110, ELC-490, PUMP-04, centrifugal pump
