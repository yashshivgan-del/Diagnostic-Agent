# SOP-PUMP-101: Bearing condition troubleshooting

Applies to: centrifugal pumps PUMP-01 to PUMP-05 (synthetic demo fleet).
Fault category: `bearing_wear`.

## Typical signature
- Overall vibration rising above the 4.5 mm/s alert limit (`VIB-201`), often with higher scatter.
- Bearing temperature rising above 72 degC (`TMP-110`), critical above 82 degC (`TMP-190`).
- Small motor current increase (+1 to +2 A); flow and discharge pressure largely unchanged.
- `LUB-150` (lubrication overdue) is common but is NOT proof of bearing damage on its own.

## Distinguish from
- Misalignment (SOP-PUMP-105): also raises vibration and temperature, but the axial component dominates (`VIB-205`) and recent coupling work (`MNT-610`) is usually present.
- Motor overload (SOP-PUMP-104): temperature rises together with a large current increase (`ELC-410`).

## Safe validation checks (inspection only, no adjustments while running)
1. Review the vibration trend for the last 7 days; bearing wear rises gradually.
2. Check lubrication records (`MNT-615`, `LUB-150`) for this pump.
3. Take a handheld vibration reading at drive-end and non-drive-end bearing housings; compare to the online sensor.
4. Measure bearing housing temperature with an IR thermometer to confirm the sensor reading.
5. If an envelope/spectrum analyser is available, look for bearing defect frequencies.

## Escalation
- Vibration above 9.0 mm/s or temperature above 85 degC: request a planned stop through the shift supervisor.
- Any bearing replacement requires lock-out/tag-out (SAFE-001).
