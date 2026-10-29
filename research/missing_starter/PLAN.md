# Missing-starter totals term: does "sat out the last game" belong in v1's totals? (pre-registered Oct 29, 2026, before any computation)

Research only (`research/missing_starter/`). v1, E2, every shadow and every scheduled read are unchanged. Nothing
here goes live and nothing here adds a shadow. Approved by Chad. All seasons have shaped development, so every
result is **exploratory**; only a prospective season can confirm anything.

**Why.** The Oct 29 addendum to `research/injury_reports/PLAN.md` found that one missing starter (about 0.17 of a
team's minutes) goes with a game total about 1.14 points below v1's total in 2024-26, and that the closing total
did not price it (about -0.61 vs the close). v1's totals equation does not use missing minutes; the margin equation
does (`miss_diff`).

## Input (no new data, no leak)
- `miss_sum = home_missing + away_missing`: the same "sat out the team's last game" excess-missing-minutes share
  that the margin model's `miss_diff = home_missing - away_missing` already uses. Both columns are already in the
  research frames (training frame as recorded, prediction frame); 0 when nobody qualifies.
- It is known before tip (it describes the team's previous game), so it adds no leak.

## Fit
- Frames: `research/quant/common.base_frames()` (training frame as recorded; prediction frame with referee crews 0
  and KenPom from the day before; openers oriented by moneyline; swapped records flagged).
- **Baseline:** `fit_predict(train, pred)` (frozen stage 1, stage-2 ridge lambda 1, walk-forward: season s fit on
  2013..s-1), then the live opening-week rule `research/quant3/study.opening_week`.
- **Candidate:** the same with `tf = projection.TOTAL_FEATURES + ["miss_sum"]`; margins unchanged.
- **Reconciliation check (must pass before anything else is read):** the baseline reproduces research/quant3
  "V0 v1": 2025-26 (season 2026) close totals at edge 3+, 1,478 plays at 48.71%.

## Scoreboard
All intervals are 95% from a date-clustered bootstrap (resample dates; 4,000 draws, fixed seed).
1. **Totals MAE**, baseline vs candidate on identical games: pooled 2020-26 (primary) and each season 2015-26;
   paired MAE gain (baseline MAE - candidate MAE) with interval.
2. **The miss_sum coefficient by era.** Stage-2 totals ridge (lambda 1, same inputs as the candidate) refit on the
   training frame of each era alone: **2014-19, 2020-23, 2024-26**. Report the coefficient (points per 1.0 of
   combined missing share), per one starter (x 0.17), with a date-clustered bootstrap SE and 95% interval. Also the
   walk-forward coefficient used for each season 2015-26 (descriptive).
3. **Opener totals at the 3+ threshold** (`research/quant/common.plays()` conventions: openers oriented by
   moneyline, swapped records excluded, pushes dropped from win rates): plays, win rate and mean CLV (close -
   open, oriented to the side) for baseline and candidate, in **dev 2015-17** and **conf 2024-26**. CLV gain =
   candidate mean CLV - baseline mean CLV, with a date-clustered interval. Close totals at 3+ reported alongside
   (descriptive).
4. **Beyond the close, on the games the term moves.** Games with a closing total, swapped records excluded, where
   |candidate total - baseline total| >= 1. For each game and each model: side = sign(model total - closing total);
   outcome = side x (result - closing total). Report the mean of candidate outcome - baseline outcome (points per
   game; 0 where both pick the same side), with its date-clustered interval, and each side's win rate vs the close.
   **Primary period 2020-26 pooled**; 2015-19, 2020-23 and 2024-26 reported separately (descriptive).

## Prior
Moderate: a real historical effect of about a point per missing starter, mostly already in the closing total before
2024. A ridge term this small should move few games, so the MAE gain is expected to be small.

## Kill rule (fixed now)
**KILL** if any of:
- the totals MAE gain over the frozen baseline, pooled 2020-26, is **< 0.02** (point estimate);
- the opener CLV gain at 3+ is **< 0.1** points in **either** era (dev 2015-17 or conf 2024-26; point estimates);
- the moved games lose to the close: the candidate-minus-baseline outcome vs the close on moved games, 2020-26
  pooled, is **< 0** (point estimate).

Otherwise the verdict is **"candidate for the Mar 14 list"**, with a note on whether it confirms the Jan 15
injury-study Q3 item (which needs exactly this historical "missed last game" backtest before any live totals input
can be proposed). A kill closes the term as a historical v1 change; the live Q3 read on Jan 15 keeps its own
pre-registered rule unchanged either way.

## Logging
Every specification run, including failures and reruns, goes in `LOG.md` with one results table and the verdict.
No re-specification after seeing results: not the input, the eras, the threshold, the moved-games cut or the kill
rule.
