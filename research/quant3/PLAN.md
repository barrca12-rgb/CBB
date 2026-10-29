# C2 totals, deeper: mean vs median, scoring-level drift, or artifact? (pre-registered Oct 29, 2026, before any new computation)

Research only (`research/quant3/`). v1, E2 and every shadow and scheduled read are unchanged; nothing here adds a
shadow or a scheduled review. All seasons have shaped development, so every result is **exploratory**.

## Evaluation periods
- **Primary:** the three most recent completed seasons: 2023-24, 2024-25 and 2025-26 (season labels 2024-2026).
  Each is reported alone and pooled.
- **Older seasons** (2015-2023) are used for training, for choosing settings and for mechanism only. An older-season
  gain cannot outweigh weak recent evidence.

## Step 1. Reproduce and verify timing
- Rebuild v1's walk-forward totals and the earlier C2 numbers (`research/quant2`). Report the seasonal bias (mean of
  result - forecast), MAE and RMSE.
- **Timing checks** (code reading):
  - stage-1 ratings: games before the date only (`ratings.fit`: `tg["date"] < asof`), preseason prior, last
    season's league averages;
  - stage 2: fit on earlier seasons only;
  - KenPom: from the day before (`audit/a2_timing.kp_prev`);
  - the scoring-level feature `season_avg_total`: earlier rows of the same season, including earlier same-day
    rows (a known small leak, audit/AUDIT.md);
  - every new setting: chosen on earlier seasons only.

## Step 2. Why the bias moved (about -1.6 to +0.6)
- **H-level:** the stage-2 totals equation passes changes in league scoring through incompletely: its intercept
  and weights are fixed from earlier seasons, so a season scoring above (below) the training average is
  under-forecast (over-forecast).
  - Test: regress each season's bias on its scoring level minus the training seasons' average level; also by
    month.
  - Falsified if the slope's interval includes 0 or the season-level correlation is under 0.5.
- **Existing mechanisms that should already absorb level** (each inspected before any correction is added):
  - stage-1's in-season intercept (`b0` = this season's mean points per 100 once games exist);
  - the stage-2 feature `season_avg_total` (weight about 0);
  - the live opening-week re-anchoring to KenPom's mean (`run_day.opening_week_totals`, first 7 days).

## Step 3. Separate the mechanisms
- **Mean vs median:** regulation-only totals (first two halves, from the ESPN schedule's line scores) vs full
  games. For each season: mean minus median of the residual, the overtime share and overtime points.
  - Diagnosis only: the deployable forecast is always judged on the full-game total bets settle on.
- **Level drift:** the season bias of the regulation-only residual, and its month-by-month path within a season.

## Variants (fixed now; no others)
Each is applied on top of v1's walk-forward totals, with the live opening-week rule applied to every base
forecast.

| Variant | Definition |
|---|---|
| V0 | frozen v1 |
| V1 | v1 - 0.61 (the already-frozen diagnostic) |
| V2 | v1 + in-season bias correction = sum of this season's earlier completed-game residuals / (n + k). Residuals are result - v1 forecast, for games before the date. Shrinkage k is chosen for season s from {250, 500, 1000, 2000, 4000} by lowest MAE on seasons 2015..s-1. No correction from earlier seasons. |
| V3 | median (least-absolute-deviations) stage 2, walk-forward, trained on earlier seasons only (`research/quant2/c2_median.lad`) |

## Measures
- Per primary season and pooled 2024-26, on identical games:
  - bias, MAE, RMSE;
  - paired MAE and RMSE change vs V0 (date bootstrap, 95% and 98.3% = Bonferroni over 3 variants).
- **Fixed thresholds:** opener totals edge 3+ in each primary season, overs and unders separately, with n and
  win%; close totals the same.
- **Alongside E2:** E2's specification (walk-forward refit; the frozen E2 coefficients include these seasons, so
  they cannot be scored historically) with the same corrections.
- **Why 2025-26 hurt:** the season's scoring level, the H-level prediction, the regulation-only decomposition, and
  the sampling error of a season's bias.

## Conclusion rule (fixed now)
- **Stable correction worth a prospective test:** a variant's pooled 2024-26 MAE gain has a 98.3% interval above
  0, it is not negative in any of the three seasons by more than its own season's standard error, and opener
  totals win% is not lower pooled.
- **Changing bias we can anticipate:** V2 meets that rule, and H-level holds.
- **Otherwise:** no actionable improvement. "Inconclusive" is reported as such.
