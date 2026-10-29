# Stage-2 coefficient instability: does it hurt forecasts? (pre-registered Oct 29, 2026, before any diagnostic or fit)

Research only (`research/stage2_stability/`). The live model, E2, C2, ridge 1,000 and every other shadow, schedule,
alert and report are unchanged. Nothing here adds a shadow or a scheduled review. All seasons have shaped
development, so every result is **exploratory**.

## What earlier work already established (read before planning)
- **Stage 2** (`cbb/projection.py`): ridge, penalty 1, on raw (unstandardized) features; intercept unpenalized; one
  fit per season on all earlier seasons from 2013 (walk-forward). Totals have 15 features, margins 16.
- **Stronger penalties** (`research/weights/LOG.md`, V6 penalty 100 and V7 penalty 1,000): killed; MAE within 0.007,
  development gains did not carry over. Ridge 1,000 still runs as a live shadow (`research/r1000/PLAN.md`).
  - **What it actually does:** the penalty acts on raw scales. Checked today, descriptive only: against 70,000
    training games, a penalty of 1,000 cuts altitude by about a third and the referee terms by about 2%, and every
    other totals feature by under 0.2%. For the features this study is about (eFG%, Torvik, free-throw rate,
    offensive rebounds, referees), **ridge 1,000 is essentially v1.** It has never tested scale-aware or grouped
    shrinkage.
- **Season-recency weights and separate Nov-Dec / Jan-on fits** (`research/originator/LOG.md`, D1): killed; MAE
  changed by 0.001 or less.
- **Dropping sources** (`research/weights`, V1-V5; `research/stage2_ablation`): no gain; KenPom matters only for
  Nov-Dec totals in recent seasons; Torvik redundant.
- **quant3** (`research/quant3/LOG.md`): the seasonal totals bias moved from about -1.6 (2019-22) to +0.6 (2026). A
  contribution breakdown pointed at free-throw rate, offensive rebounds, referee fouls, eFG% and Torvik. That
  breakdown is descriptive, not causal. An in-season running bias correction failed.

## Data facts found while planning (descriptive, no evaluation)
- **Same-day leak:** `season_avg_total` counts earlier rows of the same date (95% of dates have more than one value).
- **Referee train/predict mismatch:** training uses recorded crews (ref_fouls averages about -0.8, ref_pts about
  +0.4 in recent seasons). The live-like prediction frame sets both to 0 (crew unknown at the opener). That is a
  missing-data offset, separate from coefficient instability.
- Torvik is missing in 2013-14 (filled with KenPom); market ratings are 0 until teams have lined games.

## Step 0. Reproduce and fix the leak
- Reproduce frozen v1's walk-forward totals and margins (`research/quant/common.fit_predict`, live opening-week
  totals rule applied). This is **R-frozen**, the labeled reference.
- **R0, the research baseline:** identical, except `season_avg_total` is recomputed from games on earlier dates only.
  The rest of the rule is unchanged: 200 games in the season, otherwise last season's average, otherwise the mean
  of pred_total. It is recomputed in both the training and the prediction frames. The leak fix's effect (R0 vs
  R-frozen) is reported on its own.
- Every candidate below is compared with R0.

## Step 1. Diagnostics (all fits walk-forward: season s fit on 2013..s-1)
1. **Coefficient paths, standardized:** each fit's coefficients times the training SD of each feature, for 2015-2026.
   Reported in groups, never one coefficient alone:
   - **Level:** pred_total, pred_total_x_early, kp_total, kp_total_x_early, bt_total, season_avg_total.
   - **Four factors:** efg_sum, tov_rate_sum, orb_rate_sum, ft_rate_sum.
   - **Referees:** ref_fouls, ref_pts.
   - **Other:** rest_sum, mkt_t, altitude.

   Plus the level group's pass-through (sum of its coefficients). Margins are reported the same way, as a
   secondary.
2. **Prediction-level sensitivity** (what matters, not coefficients), for test seasons 2015-2026:
   - **Fit-to-fit churn:** RMS difference in season-s forecasts between the fit through s-1 and the fit through s-2.
   - **Training-window perturbations:** drop the first training season; drop the most recent one; leave each
     earlier season out in turn. Report the RMS forecast change, the MAE range and the bias range.
   - **Date-clustered bootstrap of the training set** (200 resamples): SD of each group's contribution to season-s
     forecasts and SD of the season-s bias.
   - **Reading:** large coefficient movement with small forecast churn means harmless movement among correlated
     inputs. Forecast churn that moves MAE means harmful.
3. **What drives the movement:**
   - **Feature scaling:** standardized vs raw paths.
   - **Correlated predictors:** correlation and VIF within groups; does the group's total contribution stay stable
     while members trade off?
   - **Missing data:** the referee offset in prediction (coefficient × (0 - training mean)) per season; Torvik's
     2013-14 fill; market ratings at 0.
   - **Changing inputs:** each feature's season mean and SD against its training mean (standardized shift).
   - **Changing relationships:** the cross-fitted oracle (item 5).
4. **Do eFG%, Torvik, FT rate, ORB and referees explain recent errors after the other inputs?**
   - **Test:** in 2024-26, regress R0's walk-forward residual on all features (standardized, within-season
     de-meaned), with date-clustered SEs. Report joint Wald tests per group, and each listed feature's partial
     coefficient.
   - **Meaning:** a nonzero partial coefficient means the training-era coefficient was off for that season.
   - **Referees** have no variation in the live-like frame, so they are tested on the training frame's recorded
     crews for the same games, labeled as such.
5. **Oracle bounds** (how much any coefficient adaptation could gain at most). For each season, cross-fitted: fit on
   odd dates, score even dates, and the reverse. Each variant starts from R0's forecast and refits within the
   season:
   - **(i) intercept only:** the level;
   - **(ii) level group plus intercept;**
   - **(iii) four factors, referees and other, plus intercept;**
   - **(iv) all coefficients.**

   **Reading:** (iv) minus (i) bounds what coefficient instability could cost beyond a level shift.
6. **Detectable before the errors?**
   - **(a) Within-season persistence:** correlation, across 2015-2026, between a group's residual slope in Nov-Dec
     and its slope in Jan-Mar, with an interval.
   - **(b) Early warning:** does the prior fit-to-fit churn, or the standardized input shift known before the games,
     predict a season's absolute bias or its MAE loss against the oracle?

   With 10-12 seasons, (b) is descriptive.

**"Material harm"**: on pooled 2024-26 totals, the cross-fitted all-coefficient oracle beats the intercept-only
oracle by 0.02 MAE or more. That is about two seasons' standard errors, and the size E2 had to show. Below that,
instability cannot materially cost us beyond a level shift, whatever any correction does.

## Step 2. Challengers (at most two)
- Pre-registered in an addendum to this file, committed **after the diagnostics and before any challenger is fit**.
- Each will state:
  - **mechanism;**
  - **how it differs from ridge 1,000;**
  - **any setting**, chosen only by an inner walk-forward on seasons before s (never on 2024-26);
  - **primary metric, minimum useful improvement and stopping rule.**
- If the diagnostics show no material harm, no challenger is fit and the study closes.

## Comparison (identical games; live opening-week totals rule on every forecast)
**Models compared:**
1. R-frozen (reference);
2. R0 (leak fixed; the baseline for every comparison);
3. ridge 1,000 on R0's inputs, same walk-forward;
4. up to two challengers.

**Reported for 2024, 2025 and 2026 separately and pooled; 2020-23 shown for context only:**
- **Totals:** bias, MAE, RMSE.
- **Spreads:** margin bias, MAE, RMSE.
- **Paired differences vs R0:** date-clustered bootstrap (games on the same date share shocks); 95% intervals and
  98.3% (Bonferroni over three comparisons with R0).
- **Fixed-threshold opener plays** (totals edge 3+, spread edge 2.5+), overs/unders and home/away separately:
  - wins-losses-pushes, coverage (games with an opener) and n;
  - shared, added and dropped selections with each group's record;
  - opener-to-close CLV in points, labeled as such (historical openers and closes only; no actual-entry CLV exists
    for these seasons);
  - **simulated** returns at an assumed -110 (pushes return 0), labeled as simulations.

**Secondary check:** only if a challenger survives, check it alongside the E2 specification (neutral-site term,
walk-forward refit; frozen E2 untouched). The question is whether neutral-site context explains its benefit.

## Rules
- Older seasons are for training, mechanism and settings. A gain concentrated in older seasons cannot justify a
  candidate that fails 2024-26.
- 2026 is examined explicitly. Nothing is re-tuned after seeing it.
- Every variant tried, including failures, goes in `LOG.md`.
- **Recommendation:** one next step. If nothing shows credible incremental value, the study closes.
