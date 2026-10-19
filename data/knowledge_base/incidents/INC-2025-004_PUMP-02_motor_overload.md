# INC-2025-004: Motor overload on PUMP-02

| Field | Value |
| --- | --- |
| Incident ID | INC-2025-004 |
| Machine | PUMP-02 (Plant A, Cooling loop 2) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2025-12-31T13:24:14.804Z |
| Resolved | 2026-01-01T00:09:08.420Z |
| Confirmed fault category | motor_overload |
| Unplanned downtime | 5.8 h |
| Related procedure | SOP-PUMP-104 Motor overload and electrical troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 72.959 | degC |
| vibration_mm_s | 3.443 | mm/s RMS |
| discharge_pressure_bar | 6.377 | bar |
| flow_m3h | 117.465 | m3/h |
| motor_current_a | 61.227 | A |
| rpm | 1473.478 | rpm |

Log event codes observed: `ELC-410` (Motor overcurrent), `ELC-412` (Phase imbalance), `TMP-110` (Bearing temperature high), `ELC-490` (Thermal overload pre-trip).

**Initial hypothesis:** Bearing wear. This was ruled out during inspection; the confirmed cause was motor overload. Do not rely on vibration alone to distinguish them.

## Root cause
Motor winding insulation degradation causing phase imbalance.

## Corrective action
Motor replaced; failed motor sent for rewind. Insulation resistance trended monthly.

## Lessons learned
Phase imbalance warnings preceded the overload by about 10 days.

## Keywords
motor overload, ELC-410, ELC-412, TMP-110, ELC-490, PUMP-02, centrifugal pump
