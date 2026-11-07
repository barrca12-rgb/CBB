# Unders in big mismatches: report (Nov 7, 2026)

Plan: PLAN.md (written before results). Script: `python -m research.blowout_unders.backtest`; every number is in
out/results.txt, out/plays.csv and out/games.csv.

## Verdict: no (the decision rule fails)

Opener Under plays (edge 3+, graded at the opener), |opening spread| 15 or more vs under 15:

| Period | Unders 15+ | Unders under 15 | Move to us by close, 15+ |
|---|---|---|---|
| 2015-17 | 61.2% (291 plays) | 56.1% | +0.74 |
| 2024-26 | 57.0% (331 plays) | 58.3% | +1.09 |

Big-mismatch Unders won well above break-even in both periods, and the close moved toward them. Removing them would
have cost money.

## What does show up (a lead, not a change)

- **The model's total runs low in 20+ point mismatches.** Over all games, actual total minus the model's total:
  +1.44 (2015-17) and +2.33 (2024-26) at 20+, against +0.11 to +1.27 in closer games. The model sits 1.2-1.3 points
  under the closing total there; the close is nearer the result.
- **Unders at 20+ are the weakest Under group in 2024-26:** 55.8% (208 plays), close moving only +0.72 our way
  (other Unders +1.5 to +1.8). November only: 55.4% (139 plays). Still profitable at -110.
- Live 2026-27 (only the plays whose card kept an opening spread): Unders at 20+ are 6-7, Pinnacle CLV -6.6%;
  Overs at 20+ 5-0. Too few to read.

## Next step (separate plan if pursued)

A total adjustment by spread size (e.g. a big-mismatch term in stage 2), judged on all-games total accuracy and
opener win %, both periods. Not a filter on Unders.
