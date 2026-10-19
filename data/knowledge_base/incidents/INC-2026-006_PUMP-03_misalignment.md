# INC-2026-006: Shaft misalignment on PUMP-03

| Field | Value |
| --- | --- |
| Incident ID | INC-2026-006 |
| Machine | PUMP-03 (Plant A, Process water) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2026-02-07T11:02:48.538Z |
| Resolved | 2026-02-08T07:52:23.124Z |
| Confirmed fault category | misalignment |
| Unplanned downtime | 11.4 h |
| Related procedure | SOP-PUMP-105 Shaft alignment troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 68.71 | degC |
| vibration_mm_s | 6.305 | mm/s RMS |
| discharge_pressure_bar | 6.13 | bar |
| flow_m3h | 116.163 | m3/h |
| motor_current_a | 46.002 | A |
| rpm | 1474.426 | rpm |

Log event codes observed: `MNT-610` (Coupling work), `VIB-205` (Axial vibration), `VIB-201` (High vibration).

**Initial hypothesis:** Bearing wear. This was ruled out during inspection; the confirmed cause was shaft misalignment. Do not rely on vibration alone to distinguish them.

## Root cause
Soft foot on motor baseplate after re-installation.

## Corrective action
Corrected soft foot with shims, re-aligned shaft.

## Lessons learned
Soft foot was not checked during re-installation.

## Keywords
misalignment, MNT-610, VIB-205, VIB-201, PUMP-03, centrifugal pump
