# SOP-PUMP-103: Mechanical seal leak troubleshooting

Applies to: centrifugal pumps PUMP-01 to PUMP-05 (synthetic demo fleet).
Fault category: `seal_leak`.

## Typical signature
- Seal leak detector reports wet condition (`SEL-510`); high leak rate (`SEL-590`) at later stage.
- Slow, smooth discharge pressure decay (`PRS-306`) and a moderate flow reduction.
- Vibration and bearing temperature stay close to normal.
- Early-stage leaks may not raise the anomaly score above threshold; the leak detector is the leading indicator.

## Distinguish from
- Cavitation (SOP-PUMP-102): faster flow loss, erratic pressure, broadband vibration (`VIB-202`).

## Safe validation checks
1. Visually inspect the seal area and drain sump level from a safe distance.
2. Check the seal flush line flow indicator, if fitted.
3. Review recent dry-running events (`SYS-003`/`SYS-002` with low flow) and chemical dosing changes.
4. Confirm the leak detector is not a false alarm by checking for visible fluid.

## Escalation
- `SEL-590` or visible spray: request a planned stop. Seal replacement requires lock-out/tag-out (SAFE-001).
