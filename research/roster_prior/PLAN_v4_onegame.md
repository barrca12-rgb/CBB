# Check: do one-game rosters cause the larger 2026-27 shift? (pre-registered)

Written Nov 6, 2026, before computing. Backtest only.

- **Seasons:** 2024-2026 (the holdout seasons closest to now).
- **Variants:** the F2 prior exactly as fit (trained on 5-game rosters, walk-forward), applied with the season's roster
  taken from (a) each team's first 5 games, as in the backtest, and (b) each team's first game only, as in the
  2026-27 replay.
- **Measured:** correlation of each prior with the season's final margin rating; the prior's spread (sd); and, for
  days 0-20 games with opener spreads of 15+, the prior gap between favorite and underdog (favorite minus underdog
  margin rating) under (a) and (b), against KenPom/Barttorvik's gap.
- **Reading (stated now):** one-game rosters are the cause if (b)'s mismatch gap is at least 1.5 points per 100
  possessions smaller than (a)'s on average. Otherwise they are not the main cause.
