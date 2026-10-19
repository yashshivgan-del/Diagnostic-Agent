# INC-2026-005: Bearing wear on PUMP-05

| Field | Value |
| --- | --- |
| Incident ID | INC-2026-005 |
| Machine | PUMP-05 (Plant B, Wash-down) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2026-01-10T09:55:17.886Z |
| Resolved | 2026-01-10T22:10:26.548Z |
| Confirmed fault category | bearing_wear |
| Unplanned downtime | 4.4 h |
| Related procedure | SOP-PUMP-101 Bearing condition troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 78.495 | degC |
| vibration_mm_s | 7.782 | mm/s RMS |
| discharge_pressure_bar | 5.93 | bar |
| flow_m3h | 117.778 | m3/h |
| motor_current_a | 43.13 | A |
| rpm | 1469.42 | rpm |

Log event codes observed: `VIB-201` (High vibration), `LUB-150` (Lubrication overdue), `TMP-110` (Bearing temperature high).

## Root cause
Bearing contamination from water ingress past a failed lip seal.

## Corrective action
Replaced both bearings and the lip seal, added a bearing isolator.

## Lessons learned
Water ingress follows wash-down of the pump area.

## Keywords
bearing wear, VIB-201, LUB-150, TMP-110, PUMP-05, centrifugal pump
