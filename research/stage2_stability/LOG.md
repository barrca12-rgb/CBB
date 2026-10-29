# Stage-2 coefficient instability: results and decision (Oct 29, 2026)

Research only. Frozen v1, E2, C2, ridge 1,000 and every other shadow, schedule, alert and report are unchanged. No
shadow or scheduled review was added. **All results are exploratory.** 2023-24 to 2025-26 have already shaped
development.

## Reproduce
```
python -m research.stage2_stability.diag      # step 0 + diagnostics -> out/diag.txt (+ paths, sensitivity, bootstrap, partial, oracle csv)
python -m research.stage2_stability.compare   # pre-registered comparison -> out/compare.txt, compare_metrics.csv, compare_plays.csv
```
Plan and challenger pre-registration: `PLAN.md`. Commits 7488a3a (plan, before any diagnostic) and 1b55816
(challengers, after diagnostics, before either was fit).

## Experiment ledger (every variant run)
| # | Variant | Pre-registered | Totals MAE gain vs R0, pooled 2024-26 [98.3%] | Per season 2024 / 2025 / 2026 | Verdict |
|---|---|---|---|---|---|
| 0 | R0: leak fix (season_avg_total from earlier dates only) vs frozen | yes | +0.0008 [+0.0003, +0.0014] | +0.0010 / +0.0009 / +0.0006 | real, negligible; R0 is the baseline |
| 1 | Ridge 1,000 on R0 inputs (existing shadow's spec) | yes (comparator) | -0.0010 [-0.0028, +0.0007] | -0.0008 / +0.0000 / -0.0023 | nothing for totals; spreads -0.0058 (below) |
| 2 | S1 season-centered four factors | yes | **-0.0023** [-0.0123, +0.0075] | +0.0171 / -0.0020 / **-0.0218** | **killed**: older gain (+0.068 in 2020-23) does not carry; significant harm in 2026 |
| 3 | S2 referee imputation (unknown crews = training mean, not 0) | yes | **+0.0087** [+0.0015, +0.0163] | +0.0150 / +0.0091 / +0.0021 | **killed**: below the +0.010 minimum; RMSE worse (MSE gain -0.156, 2026 -0.441 [-0.750, -0.117]) |
| D1 | Within-season refits, cross-fitted odd/even dates (hindsight oracle) | yes (diagnostic) | all coefficients minus intercept only: +0.020 | -0.015 / +0.043 / +0.032 | hindsight bound only |
| D2 | Nov-Dec refit applied to Jan-Mar (ex-ante) | yes (diagnostic) | all coefficients minus intercept only: **-0.095** | -0.046 / -0.153 / -0.084 | adaptation loses |

No other variant was fit. E2's secondary check was not run, because no challenger survived (stopping rule).

## 1. Does coefficient instability materially harm forecasts? **No.**
- **Coefficients are stable (standardized, `paths.csv`).**
  - Since the 2018 fit: eFG% -1.1 to -1.2 points per SD, FT rate -1.0, ORB -0.4, Torvik -0.8, KenPom +2.9, our
    ratings +8.7.
  - Level pass-through (sum of the level weights) is 1.00-1.01 from 2017 on.
  - **The only moving coefficients** are the two early-season interactions (ours × early, KenPom × early). They have
    variance inflation of about 2,000 and move in opposite directions (+3.5 / -4.0 in 2024; +2.2 / -2.7 in 2026),
    with a small net effect. This is harmless movement between correlated inputs.
- **Forecast-level sensitivity is small** (2024-26):
  - fit-to-fit churn: 0.04-0.08 points RMS;
  - dropping or leaving out any training season moves forecasts at most 0.15-0.24 points RMS, and MAE by -0.008
    to +0.008;
  - date-clustered training bootstrap: MAE SD 0.005-0.0075, bias SD 0.14-0.18.
- **The hindsight bound sits at the pre-set "material" line, but cannot be used.**
  - Refitting all coefficients within each season with cross-fitting beats re-centering alone by +0.020 pooled
    (-0.015 / +0.043 / +0.032). The line was 0.02.
  - That needs the season's own data. Done ex ante (Nov-Dec fit applied to Jan-Mar), it loses 0.08-0.15 every
    season.
  - Within-season deviations don't persist: Nov-Dec vs Jan-Mar partial slopes correlate +0.20 [-0.63, +0.74].
    KenPom's and Torvik's flip sign within 2025 and 2026.
- **Spreads:** no instability harm. Refitting margin coefficients within the season is worse even in hindsight
  (-0.031 beyond re-centering).

## 2. Verified vs inferred
**Verified (direct measurement or controlled test):**
- **The same-day leak in `season_avg_total` is real and immaterial:** +0.0008 MAE when fixed; 0.03 points RMS of
  forecast change.
- **Coefficients and forecasts are stable** across chronological fits, resamples and training windows (item 1).
- **Referee train/predict mismatch.** Training uses recorded crews (ref_fouls averages -0.7, ref_pts +0.2 over the
  training seasons). Prediction sets unknown crews to 0. This raises every totals forecast by a nearly constant
  0.38-0.63 points (0.47 / 0.42 / 0.38 in 2024-26).
- **With the other inputs held fixed, the four factors explain nothing of the 2024-26 residuals.** Group Wald p is
  0.32 / 0.70 / 0.96; eFG% partial -0.15 (t -0.9), FT rate -0.04, ORB -0.09.
- **The level group does explain them:** Wald p ≤ 0.006 each season. In 2026, Torvik was under-weighted relative
  to KenPom (+3.4 / -4.1 per SD, t +3.3 / -2.4), but within-season slopes flip, so this is not stable.
- **Knowing the crew would explain residuals** (recorded-crew t up to 6). Crews are usually unknown at the opener,
  so that is not available to the card.
- **The drift-bias link is not stable (controlled test).** Removing league-wide four-factor drift (S1) improves
  2020-23 by +0.068 and hurts 2026 by -0.022.

**Inferred (association, not proven cause):**
- The seasonal totals bias moves with league-wide input drift: four factors, Torvik/KenPom level, and the scoring
  average.
  - In 2015-23 the four-factor drift contribution correlates -0.72 with season bias.
  - S1 shows the link reversed in 2024-26, so the drift's relationship to scoring changes in a way that the inputs
    available before the game do not anticipate.
- The input shift known before the season does not forecast |bias| (rho -0.06). It does correlate with the
  hindsight oracle gap (rho +0.61, p 0.04, 12 seasons, descriptive only).

## 3. Does any tested correction beat existing regularization on recent seasons? **No.**
- **Ridge 1,000:**
  - for totals, -0.0010. By construction it shrinks only altitude, about a third; everything else changes under
    0.2%.
  - for spreads, -0.0058 (95% [-0.0117, -0.0002]; 98.3% includes 0); squared error worse, -0.168 [-0.298, -0.044].
  - descriptive only; its live shadow is untouched and is judged on its own pre-registered rule.
- **S1** fails recent seasons outright.
- **S2** is the closest: +0.0087 pooled with a 98.3% interval above 0.
  - It misses the pre-set +0.010 minimum and worsens RMSE.
  - It is also almost a constant downward shift (-0.38 to -0.47). Its MAE gain is the same mean-vs-median effect
    measured in quant3, not an instability fix.
  - Its 2026 gain is +0.002.

**Fixed-threshold openers (2024-26 pooled; `compare.txt` has every season, side, and shared/added/dropped group):**

| Model | Totals W-L-P | Totals win% | Simulated -110 return | CLV |
|---|---|---|---|---|
| R0 | 2020-1597-9 | 55.85% | +239.4u | +1.68 |
| S1 | 2135-1712-7 | 55.50% | +228.9u | +1.70 |
| S2 | 1871-1467-6 | 56.05% | +233.9u | +1.75 |
| ridge 1,000 | 1996-1586-9 | 55.72% | +228.6u | +1.68 |

- **Mix:** S2 moves the mix toward unders (overs 58% of plays vs 70% for R0). Its dropped plays won 53.8%, its added
  plays 54.1%: a change in the mix, not better selection.
- **Spreads (ridge 1,000 vs R0):** 57.67% vs 57.76%, with 242 fewer plays.
- **Labels:** CLV is opener-to-close only (no recorded entry prices exist for these seasons). Returns are simulated
  at -110 with pushes returning 0.

## 4. What failed and why
- **S1 (season-centered four factors):**
  - **Rationale:** in 2015-23 the four factors' league-wide drift was priced as if it were matchup information, and
    the evidence was strong (correlation -0.72).
  - **Outcome:** in 2024-26 the drift moved with real scoring in the other direction, and centering removed signal
    (2026 -0.022, 95% [-0.040, -0.005]).
  - **Lesson:** an older-era mechanism and a historical contribution breakdown were not enough. This is the case the
    brief warned about.
- **S2 (referee imputation):**
  - **Rationale:** the mismatch is real.
  - **Outcome:** it acts as a level shift whose value depends on each season's unpredictable bias. It helped a lot
    when v1 over-forecast (2020-23 +0.030) and barely in 2026 (+0.002). Squared error is worse.
- **In-season adaptation** (diagnostic D2): deviations don't persist, so learning them early costs more than it
  gains. It was not taken to a challenger, as the evidence did not support it.
- **Stronger uniform regularization:** already established as no help (weights V6/V7), and confirmed here on clean
  inputs. For totals it cannot reach the features in question.

## 5. Recommendation
**Close the study.** Coefficient instability is not hurting the forecasts, and no tested correction adds credible
value beyond the current model and its existing regularization. Make no change and add no shadow.
- **Open totals-level question:** the March 14 C2 read (item 5b). S2 shows that a principled cause, the
  unknown-crew imputation, accounts for part of the downward shift C2 tests. A separate S2 shadow would duplicate it.
- **Note for the March list** (fact, not a proposal): unknown referee crews are imputed as 0 rather than the training
  mean. That raises totals forecasts by about 0.4 points when crews are unknown. Any change would be a model change
  under the freeze, and on present evidence it is neutral.
