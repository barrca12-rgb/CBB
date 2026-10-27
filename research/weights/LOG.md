# Source weighting (research only; nothing live changes)

## 2026-10-27: pre-registration (written before running)

**Question (Chad):** would different weighting raise the win %?

**Already tested and killed:** rating recency (stage-1 half-life 60/240, prior strength, 3-point luck; D2) and
stage-2 season-recency weights and early/late-season fits (D1). See `research/originator/LOG.md`.

**Tested here:** how much the final number leans on each source.
- The stage-2 ridge weights our ratings, KenPom, Barttorvik and the market ratings (from earlier closing lines) to
  predict final scores. But we bet against the opener, which already reflects the public ratings.
- Each variant refits the stage-2 walk-forward on the live-like frames with:
  - **V1** no KenPom (`kp_*`, `kp_*_x_early`);
  - **V2** no Barttorvik (`bt_*`);
  - **V3** no KenPom and no Barttorvik;
  - **V4** no market ratings (`mkt_m`, `mkt_t`);
  - **V5** our ratings and context only (no KenPom, Barttorvik or market ratings);
  - **V6** all inputs, ridge penalty 100 (shrinks every weight; the frozen model uses 1);
  - **V7** all inputs, ridge penalty 1,000.

**Scored per market (spreads, totals), frozen play rule (spread 2.5+, total 3+), at the opener:**
- win% in development (2014-17 + 2024) and holdout (2025-26);
- opener CLV in 2014-17 and 2024-26;
- MAE 2020-26.

**Selection and pass:**
- **Selection:** the variant with the best development win% per market is chosen. Holdout is looked at once.
- **Pass** (candidate for a forward shadow log, not a live change): the chosen variant beats frozen by +0.5 points
  of win% in development AND +1.0 point in holdout AND +0.05 opener CLV in both eras.
- Otherwise killed. All 7 variants are reported.

## 2026-10-27: results (`out/w_result.csv`, `out/w_run.txt`): KILL both markets

| variant | spread win% dev / hold | spread CLV dev / conf | total win% dev / hold | total CLV dev / conf |
|---|---|---|---|---|
| frozen | 56.76 / 57.66 | 1.250 / 1.127 | 55.45 / 55.53 | 0.646 / 1.671 |
| V1 no KenPom | 56.93 / 57.89 | 1.266 / 1.155 | 55.73 / 55.96 | 0.660 / 1.568 |
| V2 no Barttorvik | 56.70 / 57.85 | 1.247 / 1.106 | 55.45 / 55.47 | 0.644 / 1.669 |
| V3 no KenPom, Barttorvik | 57.06 / 57.69 | 1.257 / 1.106 | 55.67 / 54.96 | 0.673 / 1.540 |
| V4 no market ratings | 57.02 / 57.79 | 1.247 / 1.099 | 55.44 / 55.27 | 0.652 / 1.672 |
| V5 own + context | 57.08 / 57.46 | 1.272 / 1.081 | 55.55 / 54.91 | 0.675 / 1.547 |
| V6 ridge 100 | 56.18 / 58.14 | 1.233 / 1.134 | 55.56 / 55.56 | 0.668 / 1.675 |
| V7 ridge 1000 | 56.12 / 58.82 | 1.226 / 1.117 | 56.83 / 55.44 | 1.002 / 1.679 |

- **Spreads:** V5 was chosen on development (+0.32). Holdout -0.20. KILL.
- **Totals:** V7 was chosen on development (+1.38, CLV +0.36). Holdout -0.09, CLV +0.01. KILL. Its development gain
  did not carry over.
- **Overall:** every variant is within about ±1 point of frozen, with no pattern that holds in both periods. MAE
  differs by at most 0.007. The frozen weighting is already as good as any reweighting of the same inputs.
