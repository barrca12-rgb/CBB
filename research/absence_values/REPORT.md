# Absences valued by learned player weights: results (pre-registered in PLAN.md, Nov 6, 2026)

Backtest only; nothing live changes. Rerun: `python -m research.absence_values.backtest` (output in `out/`).

## Verdict: does not pass. No proposal.

| Variant | Margin miss, all games | Margin miss, top 10% absence impact | Opener spreads win %, 2015-17 / 2024-26 |
|---|---|---|---|
| M0 base | 8.7699 | 8.6167 | 57.51 / 57.69 |
| **M1 + learned-value absences (primary)** | **8.7666** | **8.5936** | 57.34 / 57.50 |
| M2 learned values replace minutes | 8.7750 | 8.6325 | 56.51 / 57.34 |

- **M1:** the margin miss is lower, most where absences are largest (-0.023 points in the top 10%), and opener
  spreads stay within 0.3 points, but they are lower in both periods (-0.17, -0.19). The rule needed a gain
  somewhere. No.
- **M2:** replacing the minutes-based input loses on every measure. Minutes missed carry information the value
  version does not.

## Reading

Valuing absent players by learned impact makes the model's margins slightly more accurate, especially in games with
big absences, but the gain is too small to change which spreads become plays. This matches the earlier absence
studies (Game Score values, lineup ratings): the market already prices who is out, and the minutes-based input
captures most of what is left.
