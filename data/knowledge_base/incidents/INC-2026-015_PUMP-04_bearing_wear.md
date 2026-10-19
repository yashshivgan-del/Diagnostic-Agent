# INC-2026-015: Bearing wear on PUMP-04

| Field | Value |
| --- | --- |
| Incident ID | INC-2026-015 |
| Machine | PUMP-04 (Plant B, Boiler feed) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2026-06-01T08:06:53.028Z |
| Resolved | 2026-06-01T19:48:56.446Z |
| Confirmed fault category | bearing_wear |
| Unplanned downtime | 6.8 h |
| Related procedure | SOP-PUMP-101 Bearing condition troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 80.797 | degC |
| vibration_mm_s | 6.776 | mm/s RMS |
| discharge_pressure_bar | 6.009 | bar |
| flow_m3h | 118.591 | m3/h |
| motor_current_a | 42.807 | A |
| rpm | 1473.029 | rpm |

Log event codes observed: `VIB-201` (High vibration), `TMP-110` (Bearing temperature high), `LUB-150` (Lubrication overdue).

## Root cause
Bearing contamination from water ingress past a failed lip seal.

## Corrective action
Replaced both bearings and the lip seal, added a bearing isolator.

## Lessons learned
Water ingress follows wash-down of the pump area.

## Keywords
bearing wear, VIB-201, TMP-110, LUB-150, PUMP-04, centrifugal pump
