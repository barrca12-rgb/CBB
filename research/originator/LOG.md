# Originator research log

Research against the frozen benchmark: the live-like variant (`audit/out/wf_live_approx.pkl`: crews 0, KenPom
from the day before). Nothing here touches live v1, the card, selection rules, staking, the bet log or the
forward-test protocol. Every specification tried is logged here, failures included.

## Two scorecards, reported separately

- **Scorecard 1, forecasting:** out-of-sample MAE for margin and total against the frozen model, plus
  cover-probability calibration.
- **Scorecard 2, betting information:**
  - (a) OLS of (result - closing line) on the challenger's adjustment, with the frozen model's own edge against
    the close as a control. Date-clustered SEs.
  - (b) The opener CLV scoreboard: mean line value of the frozen rule's opener plays (spread 2.5+, total 3+),
    openers oriented by moneyline, swapped records excluded.

  Development seasons for CLV: 2014-2017. Confirmation: 2024-2026.

## 2026-10-27: pre-registration (written before any run)

### Part A: error decomposition

**Exact identity.** With P = possessions and e = points per possession:
- total miss = (P - P^)(e^h + e^a) + P(eh - e^h) + P(ea - e^a);
- margin miss = (P - P^)(e^h - e^a) + P(eh - e^h) - P(ea - e^a).

**Inputs:**
- **P^:** the model's stage-1 possessions (`pred_poss`).
- **Expected points per possession:** from the frozen final numbers, home points = (T^ + M^)/2 and away points =
  (T^ - M^)/2, each divided by P^.
- **Actual P:** the mean of the two teams' box-score possession estimates (FGA - ORB + TOV + 0.475 FTA).
- **For the closing line:** T^ = closing total and M^ = -closing spread. P^ is the model's, since the line has no
  pace.

**Game state:**
- **Overtime points:** from the schedule's period scores; reported as a separate term inside the efficiency
  parts.
- **Late-game fouling and garbage time:** need play-by-play, which this repository does not store. Every game is
  flagged "not decomposable" for those two; nothing is guessed. Data requirement noted.

**Personnel:** a share, not points. The share of the team's minutes tonight played by "newly present" players
(under half their average minutes in the team's previous 3 games), and the share of usual minutes missing from
"absent" players (prior-3 average 10+ minutes, tonight 0 or under half). Its share of the miss is the R-squared of
regressing the miss on both teams' personnel shares.

**Variance share:** cov(part, miss) / var(miss), so the additive parts sum to 1. Reported overall, by month and by
conference tier (high = ACC, B10, B12, BE, SEC, P12 by today's table; game tier = both high / both low-or-mid /
mixed), model vs line side by side.

**Predictability:**
- **Per component** (possessions residual; each team's offense residual, from the offense's view; personnel
  shares): predictors are the team's season-to-date mean and previous game of the same component, and the
  opponent's season-to-date mean of the mirror component.
- **Out of sample:** fit 2014-2019, test 2020-2026, R-squared.
- **"Already in the line?":** add (closing line - frozen model) in matching units and report whether the
  predictor's coefficient survives (estimate and date-clustered SE, with and without the line term).

**Priors:**
- possessions slightly predictable (R2 0.01-0.03);
- efficiency residuals essentially noise (R2 < 0.01);
- personnel shares partly predictable from the previous game (R2 0.05-0.2);
- most of the predictable part already in the line.

**Kill rule:** out-of-sample R2 < 0.01 means the component is noise and closed.

### Part B: rotation adjustment

- **Gate:** run only if Part A's personnel component reaches out-of-sample R2 above 0.05.
- **If run:** as specified in the task. Fit 2014-2019, test 2020-2026. Kill if the coefficient's interval
  includes 0 or R2 < 0.01.
- **Prior:** low.

### Part D1: recency-weighted and two-regime stage 2

**Variants**, each walk-forward on the live-like features (train with crews as recorded, predict with crews 0
and KenPom D-1, as `audit/b1_live_approx`):
- (a) season weights 0.5^((s - 1 - season)/h) for h = 2 and 4 seasons;
- (b) two regimes: separate ridge fits for November-December games and January onwards, each trained only on
  that regime's games from earlier seasons;
- (c) (b) with h = 4 weights.

**Choice and kill:** choose on 2014-2017 opener CLV (spreads and totals, combined mean line value), confirm on
2024-2026. MAE is a sanity check. Kill: under 0.1 points of opener CLV gain over the frozen model in either era.

**Prior:** low (the ridge already fits stably).

### Part D2: tier-specific stage-1 parameters

**One-at-a-time grid around the frozen configuration** (stage 1 re-run for 2013-2026 for each):
- half-life 60 / 240 days (frozen 120);
- prior strength 3 / 12 games (frozen 6);
- 3-point luck regression 0.2 / 0.5 (frozen 0.35).

**Choice:** each variant's stage-1 margin and total predictions feed the same stage-2 walk-forward (live-like).
For each tier (high / mid / low by conference), pick the variant with the lowest 2014-2019 margin MAE for that
tier's games. Mid = A10, MWC, WCC, Amer, MVC; low = the rest. The game tier is that of the weaker conference
(any low-major team makes it a low game).

**Test:** 2020-2026, MAE by tier against the frozen model and the closing line, plus opener CLV.

**Kill:** the low-major MAE improvement over the frozen model is under 0.03 points.

**Prior:** low (the line beats us on low majors by about 0.4 points; parameter tuning is unlikely to close
that).

## 2026-10-27: Part A results and the Part B gate

- **Part A run 1:** crashed. The 2014-2022 schedule files have no period scores.
- **Part A run 2:** the reported output (`out/a_run.txt`). Overtime points are computed for 2023-2026 only and
  flagged unavailable before that.
- **Gate:** personnel shares reached out-of-sample R2 0.071 (absent) and 0.069 (newly present), above the 0.05
  gate, so Part B runs as pre-specified.
- **Part B specification**, in `b_rotation.py`'s docstring, fixed before its run:
  - Game Score weights split into offensive (points, misses, offensive rebounds, assists, turnovers) and defensive
    (defensive rebounds, steals, blocks, fouls) value;
  - expected minutes shrunk toward embedded minutes with 2 games of weight;
  - team possessions = mean of the last 10 games.
- **Part B run 1** (`out/b_run.txt`): **gate FAIL** under the kill rule.
  - Margin: coefficient 0.42, 95% interval 0.32-0.52 on 2020-26, so the interval excludes 0. Out-of-sample R2 is
    0.0014, under 0.01.
  - Total: R2 -0.015.
  - **Per the pre-registration: stop here; no lineup simulator; scorecards not run.**
  - **Note for the reader, added after the result:** a single feature with a typical effect of half a point
    cannot reach R2 0.01 on game margins whose miss SD is 11 points (0.5^2 / 11^2 = 0.002). The bar fits large
    signals only.

## 2026-10-27: Part D1 result; D2 run method

- **D1 run** (`out/d1_run.txt`), after two container restarts (the first run was lost; the second completed).
- **Refit check:** reproduces the frozen live-like numbers exactly (max difference 2e-13).
- **All four variants KILLED.** Opener CLV gain was -0.011 to -0.005 (development) and -0.012 to +0.030
  (confirmation), all under 0.1. MAE changed by 0.001 points or less.
- **Scorecard 2:** every adjustment's coefficient on (result - close) is within about 1.2 SE of 0.
- **D2 method change (an implementation shortcut, not a new specification):**
  - **Why:** rebuilding the full stage-2 frame per variant (KenPom from the day before for every date) took
    longer than each container session lasted.
  - **What:** each variant's stage-1 outputs are now swapped into the frozen frames, and the features derived
    from them are recomputed (`d2_tiers.swap`).
  - **Equivalence:** it matches a full rebuild except for two rare fallbacks, documented in the function.
- **D2 run** (`out/d2_run.txt`): **KILLED.**
  - Choices on 2014-2019: high-major luck 0.5, mid prior 12, low-major luck 0.5.
  - Test 2020-26 MAE gain vs frozen: high +0.006, mid -0.011, **low +0.0004** (kill bar 0.03).
  - Opener CLV: 0.805 vs 0.807 (development), 1.456 vs 1.465 (confirmation).
  - Scorecard 2: margin coefficient 0.13 (se 0.16); total 0.40 (se 0.21).

## 2026-10-27: Part B subset pass (helpers' review; pre-registered before running; `b2_subset.py`)

- **Subset:** games where either team's minutes-weighted value change (adj_off + adj_def, from
  `b_adjustments.csv.gz`) is 2+ points in absolute value. The threshold is fixed and not iterated.
- **Report** (fit 2014-2019, test 2020-2026):
  - subset size per season;
  - the frozen model's mean margin residual signed by the adjustment;
  - the coefficient of the residual on the margin adjustment within the subset (date-clustered 95% interval);
  - opener CLV of the frozen rule's spread plays in the subset where the adjustment points the same way vs the
    opposite way.
- **Decision rule (from the review):** a few hundred games a season with a residual near 0.42 x the change makes
  it a v2 shadow candidate; dozens of games means close.
- **b2_subset run 1** (`out/b2_run.txt`):
  - About 280 games a season (2020-26); residual in the adjustment's direction 1.36 points; coefficient 0.44
    (CI 0.27-0.62).
  - Opener CLV: 1.55 (on the adjustment's side) vs 0.72 (against).
  - **Meets the review's rule: v2 shadow candidate.**
- **Added check (not pre-registered), information beyond the close** (`out/b2b_beyond_close.txt`): the adjustment's
  coefficient on (result - close), controlling for the frozen edge vs the close:
  - subset 2014-19: 0.22 [0.02, 0.43];
  - subset 2020-26: 0.31 [0.13, 0.49];
  - all games 2020-26: 0.35 [0.24, 0.46].
