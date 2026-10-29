# Persistent model-market disagreement (pre-registered Oct 29, 2026, before any feature was computed)

Research only (`research/persistent_disagreement/`). The live model, shadows, picks, alerts, staking and bet logs are
unchanged. Nothing is promoted and no further test is launched from the 2025-26 result. **2025-26 has been used in
earlier research, so it is not an untouched holdout; results are exploratory.**

**Hypothesis:** the model may repeatedly over- or underrate particular teams. A fresh disagreement with the market may
be informative, while a persistent disagreement that has repeatedly been wrong may be model bias, which should shrink
today's projection toward the market.

## What earlier work did and did not test
| Earlier test | What it measured | Result |
|---|---|---|
| Calibration #2, residual persistence | team's model errors **vs results** | none (−0.005), closed |
| Market s4, shooting surprise | prior results **vs market expectations**; does the close overreact? | small move, no reversal, closed |
| Edges E7-D, "market ratings agree" | filter on agreement with market ratings | nothing in holdout, killed |
| v1 feature `mkt_m` / `mkt_t` | team ratings implied by earlier closes, a stage-2 input | live |

Not tested before: **our own forecasts' persistent disagreement with the market**, and whether those past
disagreements were right.

## Pools (2025-26 scored; earlier seasons for learning only)
| Pool | Market | Quotes | Price | Timing |
|---|---|---|---|---|
| A | closing totals | ESPN consensus close, every game | assumed −110 (no recorded closing prices) | decision at the close; features use games on earlier dates |
| B | early spreads, full season | ESPN opener (oriented by moneyline; swapped records excluded) | assumed −110 | **untimestamped**: openers have no time. Features use games before D−1. Model inputs are the established live-like frame (KenPom from the day before) |
| C | early spreads, dated sample | DraftKings first-observed complete market, 2025-11-08, 2026-01-10, 2026-03-07 | recorded prices | every input before the quote time. Strict rule (`research/rotation_totals` Amendment 1): day-before decisions use KenPom D−2, Torvik D−3 and stage-1 ratings from games before D−1. Games where a team played D−1 are excluded |

- **On pool C:** it is a small dated sample, not a full-season test.
- **On "first observed":** these are the first quotes we saw, not proven openers.

## Baseline (reproduced, then held fixed)
**Forecasts:** frozen v1, historical specification. Stage-2 weights for season s are fit on 2013..s−1 (never today's
coefficients).
- **A and B:** the live-like frame (`research/quant/common.fit_predict`), with the live opening-week totals rule for
  totals.
- **C:** the strict conservative inputs above, with the same walk-forward weights.

**Selection, unchanged:**
- **Totals:** edge ≥ 3 and EV ≥ +2%.
- **Spreads:** edge ≥ 2.5 and EV ≥ +2%.
- **Win chance:** `run_day.win_prob`. At −110 the EV rule never binds for these edges; at recorded prices it can.

**Reconciliation targets** (must match before anything else is scored):
- **A:** 2025-26 close totals 1,478 plays at 48.71% (`research/quant3/out/variants.csv`).
- **B:** 2025-26 opener spreads 462-335-0 (`research/stage2_stability/out/compare.txt`).

## Strongest existing candidates (same pools)
- **Totals (A):** the E2 specification (neutral + conference-game terms, walk-forward refit; frozen E2 untouched).
  C2 (v1 − 0.61) is reported as well.
- **Spreads (B, C):** lineup v2: v1 margin + β × (home − away rotation adjustment), with β walk-forward (2025-26:
  0.38, `research/v2_lineup/backtest.py`). In C, the adjustment's timing is protected by the D−1 exclusion.

## Features (strictly backward-looking, same season only)
**Each prior game** h of a team (date before the cutoff; last N games per team):
- **Disagreement:** d_h = model − market at that game's close.
  - **Spreads:** both sides oriented to the team (team's model margin − team's market margin).
  - **Totals:** model total − close total.
- **Realized result vs market:** r_h = result − close, oriented the same way.
- **Inputs:** each prior forecast is the walk-forward pregame forecast. Each prior close and result belongs to a
  completed earlier game.

**Today's game** combines the **union** of both teams' prior games, de-duplicated by game id, so a rematch counts once.
- **Spreads:** each prior game's d is oriented to today's home team. A rematch gives the same value from either
  side, so it is counted once.

From that union:
- **S (persistent lean):** Σ oriented d / (n + 4). For spreads it is toward today's home team; for totals, toward
  the over.
- **Sdir:** sign(D0) × S. Positive means today's disagreement points the same way as the habitual lean.
- **V (track record):** Σ d·r / (Σ d² + k). This asks whether past disagreements for these teams predicted results
  against the market. It is orientation-free.
- **D0:** today's disagreement, model − contemporaneous market quote (home side for spreads, over for totals).

## Models (no intercepts; the market is the anchor)
- **Comparator, constant shrinkage:** predicted result-vs-market ŷ = c·D0, with c by OLS on the training seasons.
- **Candidate:** ŷ = b0·D0 + b1·D0·V* + b2·D0·Sdir* + b3·S*.
  - **Starred terms** are standardized on training data.
  - **Ridge penalty λ** on b1..b3 only. b0 is unpenalized, so as λ grows the candidate becomes the comparator.
- **Projection:** market + ŷ. The edge is ŷ, and the fixed thresholds above apply to it.
- **Baseline:** ŷ = D0 (c = 1).

## Learning (earlier seasons only; frozen before 2025-26 is scored)
**Grid:**
- **N:** 8 games or the full season to date.
- **k:** 25 or 100 (in squared points).
- **λ:** 10, 100, 1,000, 10,000 or 100,000.

That is 20 combinations, chosen by mean validation MSE of the result vs market. Validation units are reported but
not used to choose.

**Totals (A), at the close:**
- **Folds:** validate 2019..2025, each trained on 2016..v−1.
- **Final fit:** 2016-2025.

**Spreads (B, C), at the opener** (ESPN openers exist only for 2015-17 and 2024-25):
- **Folds:** train 2015-16 → validate 2017; train 2015-17 → validate 2024; train 2015-17 + 2024 → validate 2025.
- **Final fit:** 2015-17 + 2024-25.
- **Pool C** uses that same frozen fit, applied to DraftKings first-observed quotes.

**Freeze:** the chosen settings and coefficients are written to `out/frozen.json` and committed before 2025-26 is
scored. Predictions are written and hashed before grading.

## Scoring and report (per pool)
- **Stakes:** 1 unit risked. A win pays at the price (assumed −110 in A and B, recorded in C); a push is 0.
- **Comparisons:** baseline, comparator, candidate and strongest existing candidate, on identical games.
- **Results:** opportunities, bets, W-L-P, win %, ROI, units.
- **Changes:** candidate − baseline, − comparator, − strongest candidate, with date-clustered paired bootstrap 95%
  intervals.
- **Selection:** retained, added, dropped and reversed bets with units.
- **Breakdowns:** monthly, top dates, units without the best date.

## Verdict rule (fixed now)
**"Adds value beyond simple shrinkage and existing candidates"** in a market requires, on its primary pool (A for
totals, B for spreads), all of:
- candidate − comparator > 0 with a 95% date-clustered interval above 0;
- candidate − baseline > 0;
- candidate − strongest existing candidate > 0.

Pool C is reported but cannot decide (3 dates). If those conditions fail, the answer is **no**. No re-specification,
no new windows or penalties after scoring.

## Verification
A separate script checks:
- **Feature timing:** brute-force recomputation on a random sample. Every prior game must be dated before the cutoff
  and every close used must belong to a completed earlier game.
- **Baseline reconciliation:** the targets above.
- **Grading:** recomputed exactly.
- **Production and shadows:** no file outside this folder changed.
