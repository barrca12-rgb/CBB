# Roster-based preseason ratings, version 4: different fits, chosen on early seasons, judged on later ones (pre-registered)

Written Nov 6, 2026, before any version 4 result was computed. Chad, Nov 6: "try fitting different". Backtest only;
nothing live changes.

## Why a holdout

Trying several fits and keeping the best one overstates how good it is. So the fit is chosen on 2016-2021 only and
judged on 2022-2026, which plays no part in the choice.

## The fits (all walk-forward: each season's prior uses seasons before it only)

| | Fit | Inputs |
|---|---|---|
| F0 | V3a as run (reference) | ridge on V3a features |
| F1 | **End-to-end box stats:** ridge on the roster's projected-minutes-weighted last-season box rates (11 stats per 100 possessions), plus last season's off/def/tempo, returning share, transfer and newcomer shares | the team model learns which stats matter for team strength directly |
| F2 | F1 + V3a features together | |
| F3 | Gradient boosting (sklearn HistGradientBoostingRegressor, 200 trees, depth 3, learning rate 0.05) on the F2 inputs | non-linear |
| F4 | V3a features with ridge alpha 10 | stronger shrinkage |
| F5 | V3a features with ridge alpha 0.1 | weaker shrinkage |

Targets as before: the season's final stage-1 off, def and tempo, centered.

## Choice and judgment

- **Choice:** the fit with the highest correlation with the final margin rating over 2016-2021.
- **Judgment (holdout 2022-2026):** the chosen fit goes to step 2 (the full model, PLAN_v2.md's R1/R3 reading) if
  its holdout correlation is at least 0.010 above F0's holdout correlation, or its holdout RMSE at least 0.10 lower.
- Every fit's numbers on both periods are reported.

## Limits stated now

- Same roster leak as earlier versions (first 5 games).
- F1's box rates use each player's last D-I season (transfers included); newcomers enter only through the newcomer
  share.
