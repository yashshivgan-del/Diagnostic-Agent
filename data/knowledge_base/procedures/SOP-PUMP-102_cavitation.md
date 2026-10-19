# SOP-PUMP-102: Cavitation and suction troubleshooting

Applies to: centrifugal pumps PUMP-01 to PUMP-05 (synthetic demo fleet).
Fault category: `cavitation`.

## Typical signature
- Flow drops well below the 120 m3/h setpoint (`FLW-320`), often by 15 m3/h or more.
- Discharge pressure falls and fluctuates; low suction pressure warning (`PRS-305`).
- Broadband, erratic vibration with crackling noise (`VIB-202`).
- Motor current usually drops slightly (less hydraulic work), unlike motor overload.

## Distinguish from
- Seal leak (SOP-PUMP-103): pressure and flow decline slowly and smoothly, vibration stays near normal, and seal leak detector codes (`SEL-510`) appear.

## Safe validation checks
1. Check suction tank level and the low-level alarm/interlock status.
2. Read the differential pressure across the suction strainer, if fitted.
3. Confirm the suction isolation valve position visually (do not operate it without authorisation).
4. Listen at the pump casing for crackling noise typical of cavitation.
5. Compare recent setpoint changes (`CTL-030`) with the flow drop.

## Escalation
- Sustained cavitation damages the impeller. If flow stays more than 15% below setpoint, request a controlled reduction of duty through operations.
