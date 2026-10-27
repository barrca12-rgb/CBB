# Possession-value player weights for the lineup adjustment (research only; nothing live changes)

## 2026-10-27: pre-registration (written before any value was measured)

**Idea (from LUMA's LOKI, an NBA model):** value each box-score action by what it is worth in possessions, measured
from the data, instead of Game Score's fixed weights.
- **Current weights** (`player_ratings.WEIGHTS`): points 1.0, missed FG -0.7, missed FT -0.4, OREB 0.7, DREB 0.3,
  AST 0.7, STL 1.0, BLK 0.7, TOV -1.0, foul -0.4.
- **Where they matter:** they set each player's offensive and defensive value in the lineup adjustment
  (`cbb/lineup.py`, the v2 shadow).

### Possession-value (EV) weights, per season, from that season's data

- **Measured quantities:**
  - **V0:** league points per possession (team box points / team possessions).
  - **p_or:** league offensive rebound rate on misses (OREB / (OREB + DREB)).
  - **r_rim:** league make rate on rim attempts (play-by-play: layups, dunks, tips).
  - **a_pts:** average points of an assisted make (play-by-play: share of assisted makes that are threes).
  - **f_net:** net points conceded per foul (league FT points minus 0.44 x V0 per FTA, over league fouls).
- **Assumptions:**
  - A possession after an offensive rebound is worth V0.
  - A free throw attempt uses 0.44 of a possession.

**Offense:**

| Action | Weight |
|---|---|
| point | +1 |
| made FG | -V0 (the possession used) |
| missed FG | -(1 - p_or) x V0 |
| FTA | -0.44 x V0 |
| OREB | +(1 - p_or) x V0 |
| turnover | -V0 |
| assist | +0.5 x (a_pts - V0) |

**Defense:**

| Action | Weight |
|---|---|
| DREB | +p_or x V0 (the opponent's second chance removed) |
| steal | +V0 |
| block | +(2 x r_rim - p_or x V0) |
| foul | -f_net |

- **What the box score has:** made and missed FG and FTA are not separate columns in the lineup code, so they come
  from FGM, FGA, FTA and points.
- **Offense and defense** are split as in `lineup.py` (offense: points, shots, FT, OREB, AST, TOV; defense: DREB,
  STL, BLK, fouls).
- **Everything else is identical to the frozen adjustment:** expected vs embedded minutes, team-relative values
  shrunk with 150 possessions, team possessions.

### Test (2014-2026, same frames and code path as the v2 backtest, `research/v2_lineup/backtest.py`)

- **Versions:**
  - **GS:** the current Game Score adjustment.
  - **EV:** the possession-value adjustment.
- **Beta:** each has its own walk-forward beta on the frozen live-like model's margin residual (seasons before
  each season).

**Scorecards:**
1. **Out-of-sample R-squared** of beta x adjustment on the residual, 2020-26.
2. **Beyond the close:** coefficient on beta x adjustment in OLS of (home margin + closing spread), controlling for
   the frozen edge vs the close, 2020-26, date-clustered. Compared on the t-statistic.
3. **Opener:**
   - spread CLV of the v1+adjustment play rule (2.5+), 2015-17 and 2024-26;
   - win% at the opener, development (2015-17 + 2024) and holdout (2025-26), descriptive.

### Pass (candidate for a v2.1 shadow next to v2)

EV beats GS on (1) and on (2)'s t-statistic, AND EV's spread CLV is at least GS's in both eras. Otherwise killed;
the v2 shadow keeps Game Score weights.

## 2026-10-27: results (`out/av_result.csv`, `out/constants.csv`, `out/av_run.txt`): KILL

- **Check:** the copied adjustment loop reproduces the saved Game Score adjustments exactly (max difference 4e-16).
- **Measured constants:** V0 1.01-1.09 points per possession (rising since 2021); p_or 0.26-0.29; r_rim 0.58-0.61;
  a_pts 2.42-2.48; f_net 0.27-0.29.
- **Implied 2024 weights:** point +1, made FG -1.05, missed FG -0.77, FTA -0.46, OREB +0.77, TOV -1.05, AST +0.71,
  DREB +0.28, STL +1.05, BLK +0.88, foul -0.29.
  - The main difference from Game Score is that a made FG is charged the possession it used (a made two nets +0.95,
    not +2). EV rewards efficiency, Game Score volume.

| | GS (current) | EV | v1 (no adjustment) |
|---|---|---|---|
| OOS R2 on the residual, 2020-26 | **0.00136** | 0.00118 | |
| beyond-close coef (se), t | **0.849 (0.146), 5.83** | 0.871 (0.159), 5.49 | |
| spread CLV 2015-17 / 2024-26 | **1.346 / 1.166** | 1.314 / 1.165 | 1.297 / 1.127 |
| win% dev / holdout | 57.73 / 57.47 | 57.93 / 57.28 | 57.13 / 57.66 |

**Verdict:** EV is slightly worse on all three decisive measures, so KILL. The v2 shadow keeps Game Score weights.

**Side result:** both versions carry strong information beyond the closing line (t 5.8 and 5.5), and both add
opener CLV over v1 in both eras. The lineup signal holds under a quite different player valuation. Its value comes
from who is playing (expected vs embedded minutes), not from the fine detail of how players are valued.
