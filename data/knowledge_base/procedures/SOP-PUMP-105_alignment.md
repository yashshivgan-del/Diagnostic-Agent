# SOP-PUMP-105: Shaft alignment troubleshooting

Applies to: centrifugal pumps PUMP-01 to PUMP-05 (synthetic demo fleet).
Fault category: `misalignment`.

## Typical signature
- High vibration (`VIB-201`) with a dominant axial component and 2x running-speed peak (`VIB-205`).
- Moderate temperature rise (+5 to +8 degC); current slightly up.
- Very often preceded by coupling or motor work in the previous days (`MNT-610`).

## Distinguish from
- Bearing wear (SOP-PUMP-101): vibration is mainly radial, rises gradually over weeks, and is often accompanied by lubrication issues. Several past incidents were first misdiagnosed as bearing wear; check maintenance history before concluding.

## Safe validation checks
1. Query maintenance history for the last 7 days for `MNT-610` (coupling replaced / re-aligned).
2. Take handheld axial and radial vibration readings; compare axial vs radial.
3. Inspect the coupling guard area for coupling element wear debris (visual, guard in place).
4. Check the alignment report attached to the last work order, if available.

## Escalation
- Laser re-alignment requires a planned stop and lock-out/tag-out (SAFE-001).
