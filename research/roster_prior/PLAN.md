# Our own roster-based preseason ratings (pre-registered)

Written Nov 5, 2026, before any result was computed. Chad, Nov 5: "do both, start with 2" (backlog items 2 and 1).
Backtest only: `cbb/ratings.py`, `cbb/backtest.py`, `data/projection.json` and the live card are unchanged.

## Why

In November and December, stage 1 starts every team from KenPom's and Barttorvik's preseason ratings
(`backtest.preseason_prior`). Last season's own results alone were a much weaker start (own_ratings B4): early
margin miss 9.77 against 9.17, opener spreads about 53% against 57.5%. The outside numbers carry roster information:
who returned, who transferred in, who left. This project builds that from our own data.

## Data (all already cached, no paid pulls)

- hoopR player box scores 2013-2026 (`data.fetch("player_box")`), player ratings from `cbb/player_ratings.py`
  (`season_rates`: value per 100 on-floor possessions, shrunk toward the league rate).
- Team ratings: each season's final stage-1 ratings fit with no prior (off, def, tempo), as in own_ratings.

## The prior

For team T in season S (S from 2015, so every input season has a prior season):
- **Roster:** players who appear for T in T's first 5 games of S (see Limits).
- **Projected minutes:** each roster player's minutes last season (at any D-I team), scaled so the roster sums to
  the team's minutes; players with no D-I minutes get the newcomer rate (`player_ratings.NEWCOMER` below the median)
  and fill the rest.
- **Features:** last season's off, def and tempo; roster strength (projected-minutes-weighted last-season player
  rating, minus the league median); returning share (share of T's last-season minutes held by players on the S
  roster); returning share x last season's off and def; incoming-transfer minutes share.
- **Model:** ridge regressions for off, def and tempo, target = T's final stage-1 rating in S, fit walk-forward on
  seasons before S only. The prediction is the prior, centered on the national average, with no extra shrinkage.

## Step 1: cheap check (decides step 2)

Across team-seasons 2016-2026 (2015 has no training season), compare each prior with the season's final rating
(margin = off + def, points per 100 possessions):

| Prior | |
|---|---|
| (a) KenPom/Barttorvik preseason (current) | `backtest.preseason_prior` |
| (b) Last season carried at 60% (own_ratings B4) | `research/own_ratings/run.own_prior` |
| (c) **Roster prior** (this plan) | |

Measures: root mean square error and correlation with the final margin rating, overall and for high, mid and low
tiers (KenPom tier of the prior season).

**Go to step 2 only if** (c)'s error is lower than (b)'s by at least a third of the gap between (b) and (a).

## Step 2: the model with the roster prior

Stage 1 rerun 2013-2026 with the roster prior (from 2015; 2013-14 keep the current prior), then the production
walk-forward (`audit/common.frame`), as in own_ratings:
- **R1:** roster prior, no KenPom or Barttorvik anywhere (against B4).
- **R2:** roster prior in stage 1, KenPom and Barttorvik still in stage 2 (against base).
- **R3:** the average of the roster prior and the current prior in stage 1, outside inputs in stage 2 (against base).

Measured: final margin and total miss, days 0-20 and all, 2015-2026; opener plays (spreads 2.5+, totals 3+) for
2015-17 and 2024-26 with win %, ROI at -110 and line move toward us (`audit/a2_timing.score`).

**Reading:**
- R1 "replaces the outside prior" if its early margin miss is within 0.10 of base and its opener spread win % is
  within 1.5 points of base in both periods.
- R2 or R3 "improves the model" if early margin and total misses are both lower than base and no opener win % falls
  by more than 0.5 points. That would go to Chad as a proposal.

## Limits stated now

- **Roster leak:** the first-5-games roster is known only once games start. Preseason, the live version would use
  the published roster. The first 5 games also drop players hurt before the season, which a preseason roster would
  not. The effect is stated, not removed.
- **Freshmen and recruits:** valued at the newcomer rate; no recruiting rankings (not in our data).
- **Player value:** a box-score rating with fixed weights, the same one used elsewhere in the repo.
