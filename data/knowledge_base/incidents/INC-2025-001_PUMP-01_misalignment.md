# INC-2025-001: Shaft misalignment on PUMP-01

| Field | Value |
| --- | --- |
| Incident ID | INC-2025-001 |
| Machine | PUMP-01 (Plant A, Cooling loop 1) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2025-10-30T16:15:24.521Z |
| Resolved | 2025-10-31T00:24:39.446Z |
| Confirmed fault category | misalignment |
| Unplanned downtime | 2.5 h |
| Related procedure | SOP-PUMP-105 Shaft alignment troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 69.747 | degC |
| vibration_mm_s | 6.537 | mm/s RMS |
| discharge_pressure_bar | 6.08 | bar |
| flow_m3h | 117.257 | m3/h |
| motor_current_a | 44.663 | A |
| rpm | 1476.165 | rpm |

Log event codes observed: `MNT-610` (Coupling work), `VIB-205` (Axial vibration), `VIB-201` (High vibration).

## Root cause
Soft foot on motor baseplate after re-installation.

## Corrective action
Corrected soft foot with shims, re-aligned shaft.

## Lessons learned
Soft foot was not checked during re-installation.

## Keywords
misalignment, MNT-610, VIB-205, VIB-201, PUMP-01, centrifugal pump
