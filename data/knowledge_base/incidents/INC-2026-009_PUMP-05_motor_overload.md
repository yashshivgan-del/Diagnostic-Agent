# INC-2026-009: Motor overload on PUMP-05

| Field | Value |
| --- | --- |
| Incident ID | INC-2026-009 |
| Machine | PUMP-05 (Plant B, Wash-down) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2026-03-25T02:34:24.818Z |
| Resolved | 2026-03-25T23:42:47.584Z |
| Confirmed fault category | motor_overload |
| Unplanned downtime | 12.8 h |
| Related procedure | SOP-PUMP-104 Motor overload and electrical troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 73.364 | degC |
| vibration_mm_s | 3.505 | mm/s RMS |
| discharge_pressure_bar | 6.272 | bar |
| flow_m3h | 121.434 | m3/h |
| motor_current_a | 59.267 | A |
| rpm | 1468.535 | rpm |

Log event codes observed: `ELC-410` (Motor overcurrent), `ELC-412` (Phase imbalance), `TMP-110` (Bearing temperature high), `ELC-490` (Thermal overload pre-trip).

## Root cause
Foreign object partially jamming the impeller.

## Corrective action
Removed debris from impeller eye, installed finer suction screen.

## Lessons learned
Debris entered during upstream pipework modification.

## Keywords
motor overload, ELC-410, ELC-412, TMP-110, ELC-490, PUMP-05, centrifugal pump
