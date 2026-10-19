# INC-2026-018: Bearing wear on PUMP-03

| Field | Value |
| --- | --- |
| Incident ID | INC-2026-018 |
| Machine | PUMP-03 (Plant A, Process water) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2026-08-06T15:15:03.309Z |
| Resolved | 2026-08-07T00:49:05.339Z |
| Confirmed fault category | bearing_wear |
| Unplanned downtime | 3.9 h |
| Related procedure | SOP-PUMP-101 Bearing condition troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 78.766 | degC |
| vibration_mm_s | 7.168 | mm/s RMS |
| discharge_pressure_bar | 6.038 | bar |
| flow_m3h | 122.722 | m3/h |
| motor_current_a | 43.452 | A |
| rpm | 1472.473 | rpm |

Log event codes observed: `VIB-201` (High vibration), `TMP-110` (Bearing temperature high), `LUB-150` (Lubrication overdue).

## Root cause
Bearing contamination from water ingress past a failed lip seal.

## Corrective action
Replaced both bearings and the lip seal, added a bearing isolator.

## Lessons learned
Water ingress follows wash-down of the pump area.

## Keywords
bearing wear, VIB-201, TMP-110, LUB-150, PUMP-03, centrifugal pump
