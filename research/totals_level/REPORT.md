# Totals: tracking the season's scoring level: results (pre-registered in PLAN.md, Nov 5, 2026)

Backtest only; nothing live changes. Rerun: `python -m research.totals_level.backtest` (output in `out/`).

## Verdict: neither variant passes. No proposal.

| Variant | Total miss, days 0-20 / 21-60 / all | Bias, days 0-20 | Opener totals win %, 2015-17 / 2024-26 |
|---|---|---|---|
| T0 base | 13.732 / 13.119 / 13.245 | +0.07 | 58.35 / 57.54 |
| **T1 recent-miss correction, k=0.5, 7 days (primary)** | 13.720 / 13.112 / 13.235 | +0.13 | 58.00 / 56.84 |
| T1 k=0.25, 7 days | 13.720 / 13.113 / 13.236 | +0.10 | 58.18 / 57.13 |
| T1 k=1.0, 7 days | 13.765 / 13.127 / 13.253 | +0.19 | 57.27 / 55.75 |
| T1 k=0.5, 14 days | 13.733 / 13.111 / 13.237 | +0.33 | 58.48 / 57.05 |
| T2 smooth scoring environment | 13.727 / 13.123 / 13.247 | +0.08 | 57.11 / 57.49 |

- **T1 (primary):** misses are 0.01 lower, but opener totals fall 0.35 and 0.70 points (allowed 0.3), with more
  plays. Chasing last week's misses adds noise that creates false edges.
- **T2:** the all-games miss is not lower and 2015-17 opener totals fall 1.2 points.

## Reading

The model has no scoring-level problem to fix historically: its average total bias is within 0.1 point at every
stage of the season. This season's games landing 2.7 points under the close is the market's miss as much as ours
(the model sat 1.5 points under the close). The remaining gap to the closing total is game-specific information,
not the league level. The opening-day intercept fix (own_ratings Study A) remains the one totals change ready to
propose, for next season's opener.
