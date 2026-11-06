# Roster-prior shadow: what it logs and how it will be read (pre-registered)

Written Nov 6, 2026, before any shadow result is graded. Chad, Nov 6: "go ahead and build the shadow".

## What runs

`cbb/shadow_rp4.py`, after every card run (`.github/workflows/shadow_rp4.yml`). For each game on today's and later
cards it prices three versions against the same latest quotes with the card's own rule:
- **v1:** the live model (check: matches the card's own numbers).
- **base:** the current prior, stage 2 refit the same way as the blend's (`data/shadow_rp4_base.json`).
- **rp4:** the blend: stage 1 from the average of the current prior and F2 (rosters from each team's games so far,
  up to 5), stage 2 fit on the blend's backtest (`data/shadow_rp4.json`).

Logs: `bets/shadow_rp4/signals.csv` (each version's new BETs, once each), `games_latest.csv` (every version's numbers
per game), `prior_latest.csv`, `runs.csv`. No alerts, stakes, posts or card changes.

## How it will be read

- **Window:** plays on games from Nov 20, 2026 (teams have about 5 games, matching how F2 was trained). Earlier
  signals are logged and reported apart.
- **Comparison:** rp4 against base (same pipeline, only the prior differs); v1 reported alongside.
- **Measures:** primary-close CLV (`cbb/clv_primary` method) per play and the mean, win %, units at the logged price,
  and all-games margin and total misses against the final score.
- **Jan 15, 2027:** descriptive only.
- **Mar 14, 2027 (decision):** the blend goes to Chad as a proposal if its mean CLV is above base's, its win % is not
  more than 1 point below base's, and its all-games margin miss is not higher. Otherwise it stays research.
