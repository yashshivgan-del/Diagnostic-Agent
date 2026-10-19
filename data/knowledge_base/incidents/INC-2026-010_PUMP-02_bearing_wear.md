# INC-2026-010: Bearing wear on PUMP-02

| Field | Value |
| --- | --- |
| Incident ID | INC-2026-010 |
| Machine | PUMP-02 (Plant A, Cooling loop 2) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2026-03-31T05:58:19.424Z |
| Resolved | 2026-04-01T06:29:37.570Z |
| Confirmed fault category | bearing_wear |
| Unplanned downtime | 15.2 h |
| Related procedure | SOP-PUMP-101 Bearing condition troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 77.526 | degC |
| vibration_mm_s | 7.752 | mm/s RMS |
| discharge_pressure_bar | 6.034 | bar |
| flow_m3h | 115.349 | m3/h |
| motor_current_a | 42.278 | A |
| rpm | 1478.921 | rpm |

Log event codes observed: `VIB-201` (High vibration), `LUB-150` (Lubrication overdue), `TMP-110` (Bearing temperature high).

## Root cause
Drive-end bearing outer-race spalling caused by degraded lubricant.

## Corrective action
Replaced drive-end bearing (6312-C3), flushed housing, regreased to OEM quantity.

## Lessons learned
Lubrication interval exceeded; grease had oxidised.

## Keywords
bearing wear, VIB-201, LUB-150, TMP-110, PUMP-02, centrifugal pump
