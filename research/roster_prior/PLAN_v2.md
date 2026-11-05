# Roster-based preseason ratings, version 2 (pre-registered)

Written Nov 5, 2026, after version 1's results (REPORT.md) and before any version 2 result was computed. Chad,
Nov 5: "do 1 2 3". Backtest only; nothing live changes.

Version 1 closed about half the gap between last season's results and KenPom/Barttorvik. Version 2 adds the three
things it was missing. Everything else (roster from the first 5 games, projected minutes, walk-forward ridge,
targets, priors before 2016) is unchanged from PLAN.md.

## The three additions

1. **Development by experience.** A returning player's last-season rating is moved by the average year-over-year
   change of players with the same number of earlier D-I seasons in our box scores (1, 2, 3, 4+), estimated on
   seasons before S only. Players with fewer than 200 minutes in either season are left out of the estimate.
2. **Transfer level.** A transfer's last-season rating is moved by slope x (his new team's last-season margin rating
   minus his old team's), the slope estimated on earlier seasons' transfers only (200+ minutes both seasons).
3. **Better player values.**
   - **3a, every season:** two more roster features, so value is not only a raw box score: the projected-minutes-
     weighted last-season margin rating of the teams the roster's minutes came from (level of competition), and the
     weighted relative rating (player rate minus his old team's rate).
   - **3b, where lineup data exists (player seasons 2024-2026, so priors for 2025 and 2026):** each player's rating
     is the average of his box rating and his lineup-based rating (on/off ridge on CBBD stints, lambda 500 as frozen
     in research/player_impact), mapped to the box scale by a regression on 2024 player-seasons only. CBBD players
     are matched to ESPN players within the same game by name.

## Variants

- **V2a:** version 1 + additions 1, 2 and 3a.
- **V2b:** V2a + 3b (differs from V2a only in 2025 and 2026).

## Step 1 (decides step 2)

Priors against the season's final margin rating, 2016-2026, as in PLAN.md: RMSE and correlation, overall and by tier.
- **Go to step 2 if** V2a's correlation is at least 0.010 above version 1's (0.805), or its RMSE at least 0.10 lower.
- V2b against V2a on 2025-2026 only, reported.

## Step 2

Stage 1 rerun with the V2a prior (V2b if it beats V2a on both RMSE and correlation in 2025-2026), then the
walk-forward model:
- **R1v2:** the prior, no KenPom or Barttorvik anywhere.
- **R3v2:** the average of this prior and the current prior in stage 1, outside inputs in stage 2.

Same reading as PLAN.md:
- R1v2 replaces the outside prior if its early margin miss is within 0.10 of base and its opener spread win % is
  within 1.5 points of base in both periods.
- R3v2 improves the model if its early margin and total misses are both lower than base and no opener win % falls
  by more than 0.5 points.

Also reported: R1v2 against version 1's R1 (9.488 early margin miss; 55.0 / 54.7% opener spreads).

## Limits stated now

- The roster leak from PLAN.md remains.
- Experience counts start in 2012-13 box scores, so a fifth-year player in 2016 counts as 3 earlier seasons.
- 3b covers only two prior seasons, so it can change little in the totals.
