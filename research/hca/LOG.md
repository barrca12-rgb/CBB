# Home-court weight test (research only; nothing live changes)

## 2026-10-27: pre-registration (written before running)

**Question (Chad):** would giving home court more weight, especially in recent years, have improved results?

**How the model handles home court now:**
- stage 1 fits a league home edge from the data (prior 3.5 points per 100 possessions per side);
- stage 2 fits a `venue` coefficient walk-forward;
- `team_hca` adds each team's own home edge from the three seasons before.

**Diagnostic, per season, non-neutral games:**
- mean (actual home margin - live-like model margin);
- mean (actual home margin + closing home spread), i.e. whether home teams beat the market.

**Challengers:** the frozen live-like model with +0.5, +1.0 and +1.5 points added to the home margin in non-neutral
games. Fixed bumps, no fitting.

**Scorecards:**
- margin MAE 2020-26;
- opener spread CLV, dev 2014-17 and confirm 2024-26;
- opener spread win%, dev (2014-17 + 2024) and holdout (2025-26), with the home/away split of the plays.

**Pass:** spread CLV gain +0.05 or more in both eras AND holdout opener win% not below frozen. Otherwise killed.

## 2026-10-27: results (`out/h_result.csv`, `out/h_diag.csv`, `out/h_run.txt`): all KILL

- **Diagnostic:** the model's home residual is within ±0.33 points every season. The recent seasons are slightly
  negative (2024 -0.14, 2025 -0.06, 2026 -0.22), so if anything the model already gives home teams a touch too
  much. Home teams vs the close are also within ±0.33 (2025 +0.06, 2026 -0.15).
- **Every bump is worse on every scorecard:**

| bump | MAE 2020-26 | CLV dev / conf | win% dev / holdout |
|---|---|---|---|
| 0 | 8.882 | 1.250 / 1.127 | 56.76 / 57.66 |
| +0.5 | 8.897 | 1.211 / 1.082 | 56.60 / 56.97 |
| +1.0 | 8.928 | 1.055 / 0.931 | 55.55 / 55.78 |
| +1.5 | 8.974 | 0.853 / 0.767 | 54.36 / 54.74 |

The bump mostly adds home plays that win less often.
