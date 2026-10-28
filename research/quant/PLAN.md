# Quant lead: forecast improvements (pre-registered Oct 28, 2026, before any challenger was fit)

Research only (`research/quant/`). The live model, selection, staking, alerts, schedules, pages and CLV tracking are
untouched.

## Baseline (verified, `python -m research.quant.baseline`, `out/baseline_run.txt`)
- Stage 2 = ridge (lambda 1, unstandardized; with ~70k rows it is OLS to within 0.13 points) on 17 margin and 16
  total features; walk-forward, one fit per season on every earlier season from 2013. The research walk-forward
  equals `cbb.projection.walk_forward`, and a 2013-26 refit reproduces `data/projection.json` exactly (diff 0).
- Prediction frame: referee crews zeroed, KenPom from the day before (the live-like benchmark used by every study).
- 2020-26: margin MAE 8.882 (close 8.817), total MAE 13.150 (close 13.002); opener plays 2024-26 spreads 57.8%
  (n 2,268), totals 55.6% (n 3,706).

## Periods already used
Every season 2014-2026 has influenced development: 2014-19 and 2020-26 in the stage-2 build, audit and the Oct 26-28
research (opener eras 2015-17 and 2024-26; holdout 2025-26 read many times). **There is no untouched historical
holdout.** Any gain here is exploratory; the only clean test is prospective (2026-27 shadow).

## Design used by all three experiments
- **Comparator:** the frozen baseline on identical games, frames and information cutoffs.
- **Fit:** the frozen walk-forward with the challenger's added feature(s); nothing else changes. Feature forms below
  are fixed now; nothing is tuned.
- **Scan used to choose them:** `out/scan_run.txt`, 2014-2019 only.
- **Evaluation:** 2020-2026 (not used for the choice, though previously used elsewhere).
  - Primary: MAE of the affected market, paired difference, 95% bootstrap over dates, per season.
  - Secondary, thresholds fixed (spread 2.5, total 3): opener win% and CLV 2024-26; close win% 2020-26; play counts;
    2015-17 shown as in-sample.
  - Calibration: slope of (result - close) on (model - close).
- **Credible-candidate bar (for a prospective shadow, never a live change):**
  - MAE gain of 0.010 or more in 2020-26, with the paired interval excluding 0 at 99.2% (Bonferroni for 3
    experiments x 2 markets);
  - better in at least 5 of 7 seasons;
  - opener CLV 2024-26 not worse by more than 0.02 and close win% 2020-26 not lower.
  - Below the bar but positive is inconclusive; otherwise absent.

## E1. Endgame and overtime points in totals
- **Mechanism:** in a game expected to be close, regulation more often ends tied (overtime adds 5 minutes, about
  1/8 of a game, roughly 17 points) and the last minutes more often bring intentional fouling (free throws, extra
  possessions). Totals features are sums of team inputs and carry no closeness term.
- **Scan (2014-19):** total residual +1.5 to +2.2 when the expected margin is under 6, +0.3 to +0.8 at 13-25. Versus
  the close, -0.043 per point of |margin| (t -2.3): the market under-prices it too.
- **New information:** the expected margin's effect on the total (a new function of existing pre-game inputs).
- **Available at prediction time:** yes (stage-1 margin).
- **Feature:** `p_tie` = normal density at 0 of a margin with mean `pred_margin`, SD 10.9 (the 2014-19 residual SD).
  It is added to the total features only.

## E2. Site and schedule context in totals
- **Mechanism:**
  - Neutral sites are often large or unfamiliar arenas (event venues, depth perception behind the basket) with lower
    shooting and pace; the totals model has no site term (`venue` is in margin features only).
  - Conference games are scouted, familiar opponents; the scan shows totals beating the close there.
- **Scan, vs the close with the model edge as control (2014-19):** neutral -1.10 (t -3.0), conference +0.85 (t 3.4).
- **New information:** site type and conference flag, which totals do not use today.
- **Available:** yes (schedule).
- **Features:** `neutral` and `conf_game` (0/1) added to the total features.

## E3. Home court in conference vs non-conference games (spreads)
- **Mechanism:** non-conference home games are often one-off "buy" games, where the visitor travels for a single
  guaranteed road game; conference home games are routine, familiar trips. One `venue` term plus team home edges
  cannot separate them.
- **Scan, vs the close (2014-19):** conference games -0.36 points (t -2.5) for the home side.
- **New information:** whether the game is in conference.
- **Available:** yes (schedule).
- **Feature:** `venue_x_conf` = venue x conf_game, added to the margin features.

Every variant run is logged in LOG.md, failures included. No other variant will be tried in this batch.
