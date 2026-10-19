# SOP-PUMP-104: Motor overload and electrical troubleshooting

Applies to: centrifugal pumps PUMP-01 to PUMP-05 (synthetic demo fleet).
Fault category: `motor_overload`.

## Typical signature
- Motor current above the 48 A rating (`ELC-410`); thermal overload pre-trip above ~58 A (`ELC-490`).
- Phase current imbalance warnings (`ELC-412`).
- Bearing/motor temperature rises with current (`TMP-110`), speed drops by 10 rpm or more.
- Flow and pressure are normal or slightly high (pump pushed right of best efficiency point).

## Distinguish from
- Bearing wear (SOP-PUMP-101): temperature and vibration rise, but current rises only slightly.

## Safe validation checks
1. Compare the three phase currents on the motor control centre display.
2. Check the discharge valve position and recent setpoint changes (`CTL-030`).
3. Review insulation resistance test history for the motor (electrical team).
4. Confirm the motor cooling fan and air path are unobstructed (visual only).

## Escalation
- Electrical checks inside the MCC are performed by qualified electricians only.
- Repeated `ELC-490`: request a planned stop to avoid an overload trip.
