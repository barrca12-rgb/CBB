# Missing-starter totals term: results (Oct 29, 2026)

Research only. v1, E2 and every shadow and scheduled read are unchanged; nothing is live and no shadow was added.
Plan: `PLAN.md`, saved before any computation. Code: `run.py` (`python -m research.missing_starter.run`; output
`out/run.txt`, `out/seasons.csv`, `out/eras.csv`). All intervals are 95% from a date-clustered bootstrap (4,000
draws over dates). All results are exploratory.

## Verdict: **closed (KILL)**
- **What fired:** two of the three pre-registered kill conditions.
  - **MAE:** the 2020-26 totals MAE gain is +0.0065, below 0.02.
  - **Opener CLV at 3+:** the gain is −0.033 in dev 2015-17 and +0.047 in conf 2024-26, both below 0.1.
- **What did not fire:** the moved-games test passed narrowly (+0.024 vs the close, 2020-26).
- **The effect is real but small.**
  - Inside the totals equation, one missing starter is worth −1.25, −0.60 and −0.98 points in 2014-19, 2020-23 and
    2024-26. All three intervals exclude 0, and they match the Oct 29 addendum (−1.22, −0.59, −1.14).
  - The term moves the forecast by only 0.59 points (SD), and about 8% of games by 1+ point. That is too little to
    clear the MAE bar or to shift opener CLV.
- **Jan 15 injury-study Q3 item: not confirmed.**
  - This is the "missed last game" backtest that Q3 requires before any live totals input could be proposed. On the
    betting scoreboard it does not support adding one.
  - The Q3 live read keeps its own pre-registered rule unchanged. It measures a different input: injury-report
    minutes at T−60.

## Reconciliation check: PASS
- **Close totals at 3+:** the baseline reproduces research/quant3 "V0 v1" for 2025-26 (season 2026): **1,478 plays
  at 48.71%** (target 1,478 at 48.71%).
- **MAE also matches quant3:** 2020-23 13.1371 and 2024-26 13.1585.

## Results table
| Measure | Baseline (v1) | Candidate (+ miss_sum) | Gain (95%) | Kill bar | Result |
|---|---|---|---|---|---|
| Totals MAE, 2020-26 (37,695 games) | 13.1469 | 13.1404 | +0.0065 [+0.0003, +0.0130] | ≥ 0.02 | **fail** |
| — 2020-23 / 2024-26 | 13.1371 / 13.1585 | 13.1290 / 13.1538 | +0.0081 [−0.0014, +0.0174] / +0.0047 [−0.0034, +0.0125] | — | — |
| Opener totals 3+, dev 2015-17: n / win% / CLV | 3,591 / 57.62% / 1.311 | 3,688 / 57.62% / 1.278 | CLV −0.033 [−0.067, +0.001] | ≥ 0.1 | **fail** |
| Opener totals 3+, conf 2024-26: n / win% / CLV | 3,636 / 55.78% / 1.669 | 3,704 / 55.83% / 1.716 | CLV +0.047 [+0.011, +0.086] | ≥ 0.1 | **fail** |
| Close totals 3+, 2024-26 (descriptive) | 4,174 / 49.52% | 4,106 / 49.66% | — | — | — |
| Moved 1+ games vs close, 2020-26 (3,164 games, 582 side flips) | +0.460 / 50.95% | +0.485 / 51.43% | +0.024 [−0.437, +0.476] | ≥ 0 | pass |
| — 2015-19 / 2020-23 / 2024-26 (descriptive) | — | — | +0.049 / +0.282 / −0.492 [−1.414, +0.400] | — | — |
| miss_sum coefficient per starter (×0.17), era refit: 2014-19 / 2020-23 / 2024-26 | — | −1.25 [−1.68, −0.77] / −0.60 [−1.08, −0.07] / −0.98 [−1.47, −0.42] | SE (per 1.0 share) 1.37 / 1.50 / 1.57 | — | real, small |

**Other results**
- **Walk-forward coefficient by season.** Per 1.0 of combined missing share, it drifted from −10.9 (fit for 2015)
  to −6.1 (fit for 2026).
- **MAE gain by season (2015-26).** It runs from −0.004 to +0.021, with 2018, 2022 and 2026 negative. Only 2020's
  interval excludes 0. Full table: `out/run.txt`.
- **Moved games in 2024-26.** These are the seasons where the addendum found the close did not price absences. The
  candidate's side did worse against the close there (−0.49, interval spans 0), even though it lowered 93% of moved
  totals.

## Specifications run (all logged, including failures)
1. **`run.py` first run:** crashed before any result was produced. NumPy 2's batched `solve` needs the right-hand
   side as (n, p, 1). Fixed the shape only.
2. **Second run:** completed, but the dev 2015-17 CLV gain was NaN.
   - **Cause:** a few 2015-17 opener plays have no closing total. Pandas' mean skips them; the bootstrap did not.
   - **Effect on the kill rule:** NaN would have passed the < 0.1 test silently.
   - **Fix:** dropped plays with no closing total from the CLV comparison, the same as `research/quant/common.scorecard()`.
     The other measures were unchanged.
3. **Third run (reported above):** no further changes. No other specification was run.
