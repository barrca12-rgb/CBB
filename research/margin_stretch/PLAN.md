# Margin stretch (pre-registered Nov 9, 2026; Chad: "improve the damn model ... WIN MORE GAMES")

**Evidence before the test:** live 2026-27 spreads: favorites 41-34 (Pinnacle CLV +6.5%), underdogs 24-32 (CLV
-2.0%). Over 107 live games, actual margin on model margin slope 1.22 (market 1.10); the model's margins are flatter
than the market's (slope 0.89). In the backtest the actual-on-model slope rose from 0.96 (2023) to 1.02, 1.03, 1.045
(2024-26). The model under-separates teams, which makes underdogs look better than they are.

**Change:** final margin x k (k > 1 stretches), applied after the live blowout correction. k chosen per test season
walk-forward: the k in 0.94..1.20 (step 0.01) that minimizes margin absolute error on the three seasons before it.
Totals untouched.

**Judge:** margin mean absolute error 2023-2026 (out of sample), and opener spread plays (2.5+) in 2015-17 and
2024-26: win %, units at -110, close movement; also underdog and favorite plays separately.

**Ship rule:** margin error lower in 2023-26, AND opener spread win % not lower by more than 0.3 in either period AND
higher in at least one. Otherwise do not ship.
