# Roster-based preseason ratings, version 3: learned box weights and box-anchored lineup ratings (pre-registered)

Written Nov 6, 2026, before any version 3 result was computed. Chad, Nov 6: "yes run it" (after the xRAPM article,
roycewebb.com, Nov 2026: a box-score metric with weights learned against lineup impact, then lineup ratings that
start from it instead of zero). The article and xrapm.com are NBA only; this builds the college version from our
own data. Backtest only; nothing live changes.

## Step 0: learned box-score weights (SPM)

- **Target:** each player's lineup rating (off + def, points per 100 possessions) from one ridge fit on all CBBD
  stints of the seasons used (lambda 500, as frozen in research/player_impact), matched to ESPN players by name
  within games.
- **Inputs:** the player's box stats per 100 on-floor team possessions over the same seasons: points, 2-point and
  3-point attempts, free-throw attempts, offensive and defensive rebounds, assists, steals, blocks, turnovers, fouls.
- **Fit:** ridge (alpha 1 on standardized inputs), weighted by on-floor possessions, players with 300+ possessions.
- **Walk-forward weights:** player values for season s use weights fit on lineup seasons before s+1 (that is,
  seasons up to s). For s before 2024 there are none; those use weights fit on 2024-2026 (a definition borrowed
  from later seasons; no team results of the season being predicted enter it). Stated as a limit.
- **Check (reported):** weights fit on 2024-2025 against Game Score's fixed weights, at predicting 2026 lineup
  ratings (correlation, possession-weighted).

## Step 1: roster priors

- **V3a:** version 2's V2a with each player's season rating replaced by his learned-weight box value (shrunk toward
  the league median with 150 possessions, as before). Development, transfer level and the roster features are
  re-estimated on the new scale, walk-forward as in PLAN_v2.md.
- **V3b:** V3a, plus for player seasons 2024-2026 (priors 2025-2027) an xRAPM-style rating: the season's lineup
  ridge with each player's prior set to his V3a box value instead of zero, mapped to the box scale by a regression
  on 2024 player seasons (as PLAN_v2.md 3b).
- **Gate (same as version 2):** step 2 runs if V3a's correlation with the final margin rating (2016-2026) is at
  least 0.010 above V2a's (0.812) or its RMSE at least 0.10 lower (4.920). V3b against V3a on 2025-2026, reported.

## Step 2 (only if step 1 passes)

As PLAN_v2.md: R1v3 (prior, no outside numbers) and R3v3 (blend, outside numbers in stage 2), with the same reading
rules, against base, version 1's R1 and (if run) version 2.

## Limits stated now

- Roster leak (first 5 games) as before.
- Lineup data covers only 2023-24 to 2025-26; the weights for earlier seasons are fit on later seasons.
- Player matching by name can miss players with name changes; unmatched players fall back to the box value.
