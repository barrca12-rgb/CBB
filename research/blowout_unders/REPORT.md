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

## Part 2: 20+ point mismatches in depth (Nov 7, Chad: "investigate the 20 point mismatches more")

All 2015-2026 games with a close (57,670), by closing |spread|. Model = the backtest's final projection.

| |spread| | games | total: actual - model | favorite pts: actual - model | underdog pts: actual - model | margin: actual - model | model margin - close |
|---|---|---|---|---|---|---|
| <10 | 41,469 | -0.13 | -0.06 | -0.07 | +0.01 | -0.34 |
| 10-15 | 8,970 | +0.04 | -0.02 | +0.06 | -0.09 | +0.18 |
| 15-20 | 3,916 | -0.13 | -0.08 | -0.05 | -0.03 | +0.40 |
| 20-25 | 1,818 | +0.04 | +0.15 | -0.11 | +0.27 | +0.12 |
| 25-30 | 881 | +1.86 | +1.62 | +0.24 | +1.38 | -0.31 |
| 30+ | 616 | +2.82 | +2.49 | +0.33 | +2.16 | -1.39 |

- **The miss is the favorite's scoring at 25+.** Favorites outscore the model by 1.6 (25-30) and 2.5 (30+) points;
  the underdog's points are about right. So the model's margin is too small and its total too low together.
- **It is recent:** 20+ games, 2023-26: total +2.19 / +1.68 (Nov), favorite points +1.80 / +1.47, margin +1.41 /
  +1.25, and the model's margin sits 1.1 below the close. 2015-22 shows little of it.
- **What it does to plays (openers, 2024-26):** the model takes big dogs far more than big favorites at 20+
  (218 vs 115 plays). Dogs at 30+: 107 plays, 54.2%, the close moving only +0.2 our way; favorites at 25+: close
  +2.4 to +2.9 our way. Unders at 25+: 138 plays, close +0.3 to +0.8 (other Unders +1.1 to +1.8).
- **Live 2026-27 spreads (Pinnacle CLV):** dogs getting 25+: 21 plays, 9-12, -4.2u, CLV -4.1% to -4.9%; favorites
  laying 15+: 33 plays, 21-12, +6.9u, CLV +6.9% to +14.2%.

Reading: in blowouts the model shrinks the favorite's scoring margin too much. That creates big-dog and Under
plays the market does not back, and it is why the model sides with big favorites only when the market is far off.

## Next (needs its own pre-registered plan)

A mismatch term in stage 2: extra favorite points growing with the projected margin past about 20, fit walk-forward,
judged on all-games margin and total accuracy at 20+ and on opener win % and close movement for dogs and Unders at
20+, in both periods, plus the live plays replayed. Fallback if it fails: a higher edge bar for dogs getting 25+.
