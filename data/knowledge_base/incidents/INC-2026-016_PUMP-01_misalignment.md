# INC-2026-016: Shaft misalignment on PUMP-01

| Field | Value |
| --- | --- |
| Incident ID | INC-2026-016 |
| Machine | PUMP-01 (Plant A, Cooling loop 1) |
| Equipment type | Centrifugal pump, 55 kW, 1480 rpm |
| Detected | 2026-06-26T09:36:48.896Z |
| Resolved | 2026-06-26T16:20:15.681Z |
| Confirmed fault category | misalignment |
| Unplanned downtime | 2.9 h |
| Related procedure | SOP-PUMP-105 Shaft alignment troubleshooting |

## Symptoms
Telemetry at peak deviation (synthetic demo data):

| Sensor | Value | Unit |
| --- | --- | --- |
| temperature_c | 68.831 | degC |
| vibration_mm_s | 6.39 | mm/s RMS |
| discharge_pressure_bar | 5.869 | bar |
| flow_m3h | 116.584 | m3/h |
| motor_current_a | 44.648 | A |
| rpm | 1478.551 | rpm |

Log event codes observed: `MNT-610` (Coupling work), `VIB-205` (Axial vibration), `VIB-201` (High vibration).

**Initial hypothesis:** Bearing wear. This was ruled out during inspection; the confirmed cause was shaft misalignment. Do not rely on vibration alone to distinguish them.

## Root cause
Thermal growth not compensated in cold alignment.

## Corrective action
Re-aligned using hot-alignment offsets from OEM data.

## Lessons learned
Boiler-feed duty requires thermal growth offsets.

## Keywords
misalignment, MNT-610, VIB-205, VIB-201, PUMP-01, centrifugal pump
