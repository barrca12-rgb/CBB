# Absences valued by learned player weights (pre-registered)

Written Nov 6, 2026, before any result was computed. Chad, Nov 6: "go ahead with 2 and 4" (4 = this). Backtest only;
nothing live changes.

## Why

Absences enter stage 2 today as `miss_diff`: the share of each team's minutes held by regulars who sat out its
previous game, home minus away (`cbb/players.py`). Every minute counts the same. The learned box weights from
research/roster_prior (version 3) predict a held-out season's lineup impact far better than Game Score (0.53 vs
0.38), so an absent player can be valued by how much he actually helps.

## The input

For each team-game, using only games before it:
- regulars = players with 3+ games so far who did not play in the team's previous game (as `players.py`);
- each one's value = learned-weight value from his season-to-date box stats per 100 on-floor possessions, shrunk
  toward the team's average by 150 possessions, minus the team's minutes-weighted average value (so missing a
  below-average player counts as negative);
- `miss_impact` = sum over those players of (his share of the team's minutes so far x his relative value);
- `miss_impact_diff` = home minus away.
- Weights: fit on lineup seasons before the game's season (research/roster_prior/build_v3.spm); seasons up to 2024
  use the 2024-2026 fit (a definition borrowed from later seasons, stated as a limit).

## Variants (production walk-forward, `audit/common.frame`, own-ratings base stage 1)

- **M0:** base.
- **M1 (primary):** stage-2 margin features + `miss_impact_diff` (minutes-based `miss_diff` kept).
- **M2:** `miss_impact_diff` replaces `miss_diff`.

## Measured (2015-2026)

- Final margin average miss, all games and games where |miss_impact_diff| is in its top 10%.
- Opener spreads at 2.5+ (`audit/a2_timing.score`): win %, ROI, line move toward us, 2015-17 and 2024-26.

## Proposal rule (all three, for M1; M2 reported)

- All-games margin miss lower than M0.
- Opener spread win % not lower than M0 by more than 0.3 points in either period.
- Opener spread win % higher than M0 in at least one period.
