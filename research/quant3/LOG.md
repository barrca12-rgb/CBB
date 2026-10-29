# C2 totals, deeper: results (Oct 29, 2026)

Research only. v1, E2, the C2 prospective read (Mar 14, item 5b) and every other shadow and scheduled job are
unchanged. Nothing was deployed, and no shadow or scheduled review was added. **All results are exploratory.** The three
primary seasons (2023-24, 2024-25, 2025-26) have already shaped development; only a prospective season can confirm
anything.

Code: `study.py` (pre-registered steps; output `out/run.txt`, `out/seasons.csv`, `out/variants.csv`), `skew.py`
(the mean-vs-median piece alone; output `out/skew.txt`). Plan: `PLAN.md`, committed before any computation.

## Answer
**C2 is mostly an artifact of when the bias was measured, not a correction to keep.** It has two parts:
- **A real but small part: mean vs median.** Totals residuals are right-skewed (mean minus median +0.35 to +0.84
  every season). After each season's level bias is removed, lowering forecasts by 0.61 improves MAE in **all 12
  seasons**, but only by +0.002 to +0.017 (2024 +0.010, 2025 +0.006, 2026 +0.014).
- **A larger part that comes and goes: the yearly level bias.** It ran from -1.6 (2019-22) to +0.6 (2026) and is not
  predictable in-season. C2's large older-season gains (+0.037 in 2020-23) came from v1 over-forecasting in those
  years. In 2025-26 v1 under-forecast by 0.58, so shifting it down hurt.

**No variant meets the pre-registered rule on the primary seasons.** The recent evidence is **inconclusive and
small**.

## Step 1. Reproduction and timing
- **Reproduced.** v1's walk-forward season bias (before the opening-week rule) is -0.19, -0.05 and +0.60 for 2024-26,
  matching quant2. With the live opening-week rule applied, it is -0.11, -0.02 and +0.58. The shift's MAE gains
  (+0.013, +0.006, -0.004) match quant2's C2 gains (+0.016, +0.006, -0.004) within the effect of that rule.
- **Timing, by code reading.**
  - **Stage-1 ratings:** use games before the date only, plus the preseason prior and last season's league
    averages.
  - **Stage 2:** fit on seasons before s.
  - **KenPom:** taken from the day before.
  - **V2's shrinkage:** k chosen on 2015..s-1 only (k = 500 for 2021-26, 1000 for 2020).
  - **LAD:** walk-forward, earlier seasons only.
  - **Known small leak, unchanged:** `season_avg_total` includes earlier games from the same day. Its weight is
    -0.027, so it is immaterial.

## Step 2. Why the bias moved from about -1.6 to +0.6
**Decomposition.** Stage-2 training residuals average zero. So each season's bias equals the actual change in
scoring against the training seasons, minus the change stage 2 forecast, which is the sum over features of weight ×
change in that feature's mean.

| Season | Actual change | Stage-1 total change | KenPom change | Forecast change | Bias | Largest non-level contributions |
|---|---|---|---|---|---|---|
| 2019 | +3.07 | +3.71 | +2.94 | +4.72 | -1.65 | FT rate +0.76, ORB +0.56, ref fouls +0.52 |
| 2020 | -0.71 | -1.40 | -0.86 | +0.92 | -1.63 | FT rate +1.00, ref fouls +0.53, ORB +0.48 |
| 2021 | +0.52 | +0.76 | +0.50 | +2.10 | -1.58 | early-season interactions (net -0.13), FT rate +0.77, ref fouls +0.63 |
| 2022 | -0.97 | -1.46 | -0.98 | +0.28 | -1.25 | FT rate +1.03, ref fouls +0.62 |
| 2023 | +0.48 | -0.44 | +0.12 | +0.67 | -0.19 | FT rate +0.62, ref fouls +0.59 |
| 2024 | +4.23 | +3.90 | +3.97 | +4.42 | -0.19 | ref fouls +0.60, eFG -0.27 |
| 2025 | +4.24 | +4.41 | +4.04 | +4.29 | -0.05 | ref fouls +0.58, eFG -0.57 |
| 2026 | +7.68 | +8.26 | +7.49 | +7.09 | +0.60 | eFG -0.82, Torvik total -0.52, FT rate -0.45, ref fouls +0.56 |

- **2019-22 over-forecasts.** The level inputs tracked scoring. Stage 2 also added about 1.2-1.7 points through the
  free-throw-rate, offensive-rebound and referee-foul features. Those features drifted up relative to their training
  means, but scoring did not follow.
- **2025-26 under-forecast.** KenPom and the stage-1 total rose with record scoring. Stage 2's negative weights on
  eFG% and the Torvik total, which are collinear with the level inputs, held back about 1.3 points; the referee-foul
  feature gave back +0.56. Net, the forecast rose 7.09 against an actual 7.68.
- **H-level holds statistically:** bias = -0.84 + 0.128 × level gap; slope 95% interval [+0.005, +0.250];
  correlation 0.59 over 12 seasons. But the decomposition shows the mechanism is **feature drift inside stage 2**,
  not a weak pass-through of the level inputs. The level pass-through on KenPom, Torvik and the stage-1 total is
  about 1.0.
- **Existing mechanisms inspected.**
  - **Stage-1 in-season intercept:** tracks the season mean as games accrue. The stage-1 total tracked 2026 (149.5
    forecast vs 149.4 actual).
  - **`season_avg_total`:** weight about 0, so it absorbs nothing.
  - **Opening-week rule:** re-anchors the first 7 days to KenPom's mean. It moved the season bias only by about
    0.02-0.13.
  - **Overlap with a new adjustment:** a bias correction (V2) would duplicate stage 1's job on the level and would
    chase stage-2 feature drift. The chase failed (V2 below).

## Step 3. Separating the mechanisms
- **Overtime correction (a data fix made during this study).** The first run showed 2025-26 overtime at 9.3% of
  games and 3.17 points per game. That was an artifact: 236 games that season have truncated play-by-play (about 44
  points short of the final), so they looked like overtime.
  - Regulation totals are now used only where the play-by-play final equals the schedule final (88-97% of games; older seasons have more missing play-by-play).
  - Corrected 2025-26 overtime is **5.5% of games and 1.38 points per game**, normal for 2015-26 (5.5-7.1%,
    1.3-2.0).
  - Overtime did not cause 2025-26.
- **Skew (mean minus median).** Full games: +0.59, +0.50 and +0.77 in 2024-26. Regulation only: +0.36, +0.44 and
  +0.47.
  - About 0.06-0.30 of the skew comes from overtime; the rest is regulation scoring's own right tail.
  - It is stable, so a median center is right for absolute error and for over/under.
- **Level-free test (`skew.py`, diagnosis only).** Removing each season's bias in hindsight and then shifting by
  -0.61 improves MAE in all 12 seasons: +0.002 to +0.017, average about +0.009.
  - This is the durable value of C2 in a season with no level bias.
  - It is the same size as one season's sampling error (about 0.008).
- **Level drift.** v1's 2026 bias was positive in every month (+0.93, +0.72, +0.25, +0.66, +0.19). In 2025 the sign
  changed month to month. A level bias is either persistent within a season or not there at all, and it cannot be
  seen in advance from earlier seasons.

## Step 4. Variants vs frozen v1 (identical games, opening-week rule on every base)
**MAE gain vs v1** (positive = better). 95% interval; for pooled 2024-26 the 98.3% interval is in parentheses.

| Variant | 2024 | 2025 | 2026 | Pooled 2024-26 | 2020-23 (older) |
|---|---|---|---|---|---|
| V1 v1 - 0.61 | +0.013 [-0.002, +0.030] | +0.006 [-0.012, +0.024] | -0.004 [-0.021, +0.014] | +0.005 (-0.007, +0.017) | +0.037 |
| V2 running in-season bias | -0.006 [-0.015, +0.003] | -0.000 [-0.013, +0.011] | **-0.028 [-0.049, -0.007]** | **-0.011 (-0.022, -0.001)** | +0.044 |
| V3 median (LAD) stage 2 | +0.019 [+0.003, +0.037] | +0.012 [-0.004, +0.028] | +0.002 [-0.015, +0.019] | +0.011 (**-0.0004**, +0.023) | +0.038 |

**Bias, MAE and RMSE:**

| | v1 bias | v1 MAE | v1 RMSE | V1 bias | V3 bias | V2 bias |
|---|---|---|---|---|---|---|
| 2024 | -0.11 | 13.030 | 16.586 | +0.50 | +0.52 | -0.24 |
| 2025 | -0.02 | 12.856 | 16.454 | +0.59 | +0.57 | +0.13 |
| 2026 | +0.58 | 13.590 | 17.144 | +1.19 | +1.19 | -0.13 |
| Pooled | +0.15 | 13.159 | 16.731 | +0.76 | +0.76 | -0.08 |

- **RMSE is worse for every variant pooled:** V1 -0.017, V2 -0.005, V3 -0.010. Moving to a median trades squared
  error for absolute error, as expected.
- **Fixed thresholds, opener totals, edge 3+** (n / win%):

  | | v1 overs | v1 unders | v1 all | V1 all | V2 all | V3 overs | V3 unders | V3 all |
  |---|---|---|---|---|---|---|---|---|
  | 2024 | 920 / 56.0 | 138 / 55.1 | 1058 / 55.86 | 868 / 57.14 | 1153 / 55.59 | 578 / 58.7 | 272 / 55.9 | 850 / 57.76 |
  | 2025 | 912 / 55.8 | 259 / 56.8 | 1171 / 56.02 | 1025 / 55.51 | 1108 / 55.14 | 611 / 56.5 | 408 / 55.6 | 1019 / 56.13 |
  | 2026 | 741 / 54.9 | 666 / 56.2 | 1407 / 55.51 | 1462 / 55.47 | 1599 / 55.28 | 496 / 55.2 | 955 / 56.9 | 1451 / 56.31 |
  | Pooled | 2573 / 55.6 | 1063 / 56.2 | 3636 / 55.78 | 3355 / 55.92 | 3860 / 55.34 | 1685 / 56.9 | 1635 / 56.4 | 3320 / 56.63 |

  - Close, pooled: v1 49.52%, V1 50.18%, V2 49.28%, V3 50.28%.
  - The shift mainly rebalances v1's lean toward overs (71% of opener plays) and drops some overs.
  - V3's +0.85 pt opener edge is within sampling noise: one sample's standard error is about 0.85 pt, and the two
    play sets differ.
- **Alongside the E2 specification** (walk-forward refit; frozen E2 itself is unchanged and cannot be scored
  historically):
  - V1 +0.0045, V2 -0.0116 (98.3%: -0.022, -0.002), V3 +0.0103 (98.3%: -0.0010, +0.0219).
  - Opener: E2 3674 / 56.53% vs E2 + V3 3346 / 56.81%.
  - The pattern is identical, so any benefit neither depends on E2 nor adds to it.

## Why C2 hurt in 2025-26
- **Not sampling alone.** The +0.58 bias is about 2.5 standard errors, and positive in every month.
- **Not overtime.** That was a data artifact (Step 3).
- **Not the level inputs failing.** KenPom and stage 1 tracked the record level.
- **An existing-model interaction in a changing scoring environment.** Stage 2's negative weights on eFG% and the
  Torvik total held back about 1.3 points of a record scoring rise (the referee-foul feature gave +0.56 back), so v1
  was already near median-centered (median residual about -0.19). A further -0.61 overshot.
- **The same mechanism ran the other way in 2019-22.** Feature drift pushed forecasts up, and C2's shift happened to
  undo it.
- **Sampling still matters for the gain itself.** 2026's V1 gain of -0.004 has an interval of ±0.017.

## Conclusion against the pre-registered rule
- **Stable correction?** No.
  - V3's pooled 98.3% interval reaches -0.0004, just below zero.
  - V1's reaches -0.007.
  - Both are well under one season's standard error in 2026.
- **Anticipatable bias?** No. V2 is significantly worse in 2026 and pooled, even though H-level holds.
- **Result: no actionable improvement.** The recent evidence is inconclusive.
  - The only durable piece is the skew, worth about 0.01 MAE.
  - The level bias it rides on is not predictable.

## Recommendation
**Make no change, and add nothing.**
- Keep v1 live, E2 and the existing C2 prospective read (Mar 14) exactly as scheduled.
- Read that C2 result as a test of the skew piece only. A null there is the expected outcome ("too small to see in
  one season"), not a reason to revisit.
- The lead worth a future pre-registered study is the stage-2 feature drift (free-throw rate, referee fouls, eFG%).
  That is where the -1.6 to +0.6 swing came from. It is a question about the model's features, not about C2.

## Sources
- Koenker, R. and Bassett, G. (1978), "Regression Quantiles," *Econometrica* 46(1): 33-50, doi:10.2307/1913643.
  Retrieved and verified Oct 29, 2026 from the Econometric Society's page
  (https://www.econometricsociety.org/publications/econometrica/1978/01/01/regression-quantiles) and EconBiz. It
  is the basis for the least-absolute-deviations (median) estimator in V3. The full text is paywalled; only the
  citation and abstract were checked.
- No other outside sources were used. Every number here comes from the repo's own data and the scripts above.
