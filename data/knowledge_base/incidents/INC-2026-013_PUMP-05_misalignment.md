# INC-2026-013: Shaft misalignment on PUMP-05

| Field | Value |
| --- | --- |
| Incident ID | INC-2026-013 |
| Machine | PUMP-05 (Plant B, Wash-down) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2026-05-18T10:00:16.101Z |
| Resolved | 2026-05-19T05:07:55.967Z |
| Confirmed fault category | misalignment |
| Unplanned downtime | 15.7 h |
| Related procedure | SOP-PUMP-105 Shaft alignment troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 68.484 | degC |
| vibration_mm_s | 6.612 | mm/s RMS |
| discharge_pressure_bar | 6.132 | bar |
| flow_m3h | 112.127 | m3/h |
| motor_current_a | 44.543 | A |
| rpm | 1486.514 | rpm |

Log event codes observed: `MNT-610` (Coupling work), `VIB-205` (Axial vibration), `VIB-201` (High vibration).

## Root cause
Soft foot on motor baseplate after re-installation.

## Corrective action
Corrected soft foot with shims, re-aligned shaft.

## Lessons learned
Soft foot was not checked during re-installation.

## Keywords
misalignment, MNT-610, VIB-205, VIB-201, PUMP-05, centrifugal pump
