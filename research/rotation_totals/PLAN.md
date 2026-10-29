# Rotation-adjusted totals classifier vs the current model at first-observed DraftKings quotes
# **A close-trained classifier tested at early quotes. It is not the opener-trained test originally requested.**
# (pre-registered Oct 29, 2026, before any evaluation-date prediction or outcome was computed)

Research only (`research/rotation_totals/`). Frozen v1, E2, C2, ridge 1,000, lineup v2 and every schedule, threshold,
staking rule, alert, workflow and bet log are unchanged. No shadow is created. **Newly specified test**, not a
reproduction of another chat's pilot. Results are exploratory: 2024-25 and 2025-26 have already been researched,
and Stage A's six dates are the same dates another chat's pilot used.

**Question:** does a totals classifier with expected-rotation inputs earn more net units than the current model at
first-observed DraftKings quotes, consistently in 2024-25 and in 2025-26?

## Evaluation dates (frozen)
- **Stage A (existing quotes, no credits):** 2024-11-09, 2025-01-11, 2025-03-01 (2024-25); 2025-11-08, 2026-01-10,
  2026-03-07 (2025-26). These are the only dates in those seasons with timestamped DraftKings quotes in
  `research/market/data/`. Snapshots run every 30 minutes from 17:00 UTC the day before; 2025-01-11 is every 5
  minutes.
- **Stage B (only if Chad approves about 28,600 Odds API credits):** 20 dates fixed by calendar rule before any
  result. The rule takes, in each month Nov-Feb, the second Wednesday and the third Saturday; in March, the first
  Wednesday and the second Saturday.
  - **2024-25:** 2024-11-13, 11-16, 12-11, 12-21, 2025-01-08, 01-18, 02-12, 02-15, 03-05, 03-08.
  - **2025-26:** 2025-11-12, 11-15, 12-10, 12-20, 2026-01-14, 01-17, 02-11, 02-21, 03-04, 03-14.
  - **Pull:** the same window and spacing as Stage A (30 minutes from 17:00 UTC the day before), all books, run
    through the repo's research workflow. Never more than the approved credits, and the live logger's reserve is
    kept.
- **Final verdict:** on every frozen date available at the time (Stage A alone if Stage B is not approved). Stage A
  and Stage B are also reported separately.

## Quote selection (frozen)
- **Book:** DraftKings only. One decision per game.
- **Decision snapshot:** the first snapshot at which both spread sides and both total sides are present together.
  State is rebuilt from the change-only quote log (each outcome's latest row at or before the snapshot; `absent`
  removes it). The snapshot must be before the tip (ESPN tip and the feed's commence time).
- **Price and number:** the total's number and the chosen side's American price at that snapshot. No other book,
  no later line, nothing from the close of the target game.
- **Called "first observed",** not "opener".
  - **Left-censored:** games already complete at the date's first snapshot. They were possibly posted earlier, and
    are reported separately.
- **Target games:** feed games whose ESPN date (Eastern time) equals the evaluation date, matched to ESPN game ids
  by team (either orientation) with the research name lookup (`research/market/s1_sample_report.lookup`).

## Information cutoff (frozen, conservative daily rule)
Every input uses only information available before the start of the day before the game (ET). Decision snapshots
are no earlier than 17:00 UTC that day.

| Input | Source |
|---|---|
| Stage-1 ratings, Four Factors, possessions, `games_before` | stage-1 fit on games before D-1 (`audit/out/backtest_lag1_2013_2026.csv`) |
| KenPom total | KenPom archive dated D-1 |
| Torvik total | Torvik file one day earlier than production |
| Market ratings | closes of games before D-1 |
| Referees | unknown: 0 |
| Season scoring average | games on dates before D-1, once there are 200 games; else last season's average (recomputed here) |
| Rest, altitude, neutral | schedule (known in advance) |
| Rotation adjustments | team's earlier games; **games where either team played on D-1 are excluded** (their adjustment would include that game) |

- **Frame:** `audit/out/wf_safe_lag1.pkl`, with `season_avg_total` replaced as above.
- **Not verifiable:** exact publication times of KenPom/Torvik files and later box-score corrections. That makes
  this a conservative reconstruction, not a live replay.

## Baseline: current model, historical specification (frozen)
- **Weights:** stage-2 ridge (penalty 1, 15 totals features), fit for season s on seasons 2013..s-1 of the
  production training frame. The leak-fixed season average is used (`research/stage2_stability/common.frames`).
  It is never fit on the season being evaluated, and never uses today's coefficients.
- **Forecast:** those weights applied to the conservative inputs above.
- **Opening-week rule:** the live rule (`run_day.opening_week_totals`) on each date's full D-I slate in that frame:
  during a season's first 7 days, shift the day's totals so their mean equals KenPom's.
- **Selection** (live rule, unchanged):
  - edge = forecast − DraftKings total, betting the side it points to;
  - win probability = min(0.5 + 0.014 × |edge|, 0.565);
  - EV at the recorded price;
  - bet if |edge| ≥ 3 and EV ≥ +2%.

## Candidate: rotation-adjusted totals classifier (frozen)
**Model:** logistic regression for P(final total > quoted total).
- **Training:** for evaluation season s, the three immediately preceding seasons (2025: 2022-2024; 2026:
  2023-2025). Rows are all games in the conservative frame with an ESPN total and spread; pushes are dropped.
- **Training gap, disclosed:**
  - **What:** no timestamped or opening quotes exist for 2021-22 and 2022-23, so training uses ESPN closing totals
    and spreads as the quoted numbers.
  - **What is used:** past seasons' closes only, never the target game's.
  - **Effect:** the classifier is trained against closing lines and applied to first-observed lines.

**Inputs** (q = quoted total):
1. current-model total − q, where the current-model total is the baseline forecast for that season, out of
   sample, with the opening-week rule;
2. stage-1 total − q;
3. KenPom total − q;
4. Torvik total − q;
5. projected possessions (stage-1);
6. q;
7. |quoted spread|;
8. log1p(`games_before`);
9. neutral flag;
10. early-season factor;
11. combined rest;
12. combined projected eFG%;
13. turnover rate;
14. offensive-rebound rate;
15. free-throw rate;
16. altitude flag;
17-20. current-model edge × (log1p `games_before`, possessions, neutral, early), each moderator centered on its
   training mean;
21. home + away offensive rotation adjustment;
22. home + away defensive rotation adjustment.

**Fitting:**
- **Standardization:** every input is standardized with the training mean and SD.
- **Objective:** summed logistic loss + 100/2 × Σ β² over the 22 standardized coefficients, with the intercept
  unpenalized. Fit by L-BFGS to a gradient norm < 1e-6.

**Rotation adjustments:** the existing implementation `research/originator/b_rotation.py`, used unchanged (output
`research/originator/out/b_adjustments.csv.gz`). From a team's earlier games only:
- **Expected minutes:** a weighted average over the last 5 games (weights 5, 4, 3, 2, 1; a missed game counts 0),
  shrunk toward the embedded minutes with 2 games of weight. It is 0 if the player sat out the team's previous game.
- **Embedded minutes:** season-to-date minutes weighted 0.5^(days/120), the rating's half-life.
- **Player value:** offensive and defensive box-score value per 100 on-floor possessions, relative to the team,
  season to date, shrunk toward the team with 150 possessions.
- **Adjustment:** Σ (expected − embedded)/200 × relative value × team possessions/100, offense and defense
  separately.
- **Missing:** a team-game with no adjustment counts as 0, and its coverage is reported.

**Decision:**
- p = P(over); if p ≥ 0.5 take the over with p, else the under with 1 − p.
- EV = p × payout(price) − (1 − p).
- Bet if EV ≥ +2%.

## Scoring (frozen)
- **Stakes:** 1 unit risked per bet. A win pays at the recorded American price, a loss is −1, a push is 0.
- **Outcome:** the final score (overtime included) against the DraftKings number.
- **Order of work:**
  1. Predictions for every eligible game are written and hashed before any result is joined.
  2. Grading reads that file.

## Reporting (per season and pooled; Stage A and B separately when both exist)
- **Coverage:** eligible games; exclusions by reason (no complete DraftKings market before tip, not matched,
  outside the frame, team played D-1); left-censoring.
- **Results:** bets, W-L-P, win % excluding pushes, net units, ROI, max drawdown in decision-time order.
- **Incremental units (candidate − baseline):**
  - date-clustered bootstrap (dates resampled within season; 95% interval);
  - a game-level bootstrap, labeled as ignoring date dependence.
  - With 3 dates a season in Stage A, the clustered interval has almost no power; that is stated, not hidden.
- **Selection changes:** shared, added, dropped and flipped bets, with each group's units.
- **Concentration:** units by date, and the result with the best date removed.
- **Missing data:** rotation coverage, KenPom/Torvik fallbacks, left-censored games.

## Decision rule (frozen)
- **Supported for prospective evaluation:** all of the following:
  - incremental units > 0 in both seasons;
  - pooled candidate units > 0;
  - pooled incremental 95% date-clustered interval above 0.
- **Failed:** pooled incremental units ≤ 0, or pooled candidate units ≤ 0.
- **Inconclusive:** anything else.
- No tuning of features, thresholds, staking or books after results. Even "supported" is a proposal only.

## Amendment 1 (Oct 29, 2026, after Stage A was graded; prompted by Chad's review of input timing, not by results)
- **Finding:** every input was checked against the actual decision timestamp, not the game date (`strict.py`,
  `out/strict_A.txt`).
  - 565 of 597 Stage A decisions were made on the day before the game; the earliest was 11:55 ET.
  - **Safe:** stage-1 ratings, Four Factors, season average, rotation and market closes stop at games of D-2. The
    last D-2 tip was at least 11.9 h before the earliest decision.
  - **Not safe:** KenPom's archive dated D-1 is the ratings at the start of D-1 (verified: the opening-day archive
    equals the preseason ratings), but its publication time on D-1 cannot be verified. The same holds for Torvik's
    file dated D-2.
- **Rule from now on (both models):**
  - **Decisions made on the day before:** KenPom archive dated D-2 and the latest Torvik file dated D-3 or earlier.
  - **Decisions made on game day:** keep the D-1 archive and the D-2 file, both published the day before.
- **Stage A:**
  - The strict rebuild (`predictions_A_strict.csv`) is the primary Stage A result.
  - The original grading is kept and reported as a sensitivity analysis.
  - The candidate's coefficients and the baseline's stage-2 weights are unchanged; only these decision-time inputs
    and the opening-week day mean move.
  - Training rows keep their original inputs. Training needs no decision time, and the candidate stays frozen.
- **Stage B:** the same strict rule, built with `strict.py`'s inputs. The 20 dates are unchanged.
- **Credit guard for Stage B:** the pull aborts if it would leave fewer than 50,000 credits. Hard cap 28,800.
