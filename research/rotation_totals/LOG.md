# Rotation-adjusted totals classifier: Stage A result (Oct 29, 2026): **INCONCLUSIVE**

Research only. Nothing live, no shadow, and no production or shadow file was touched (verified, `out/verify_A.txt`).
Protocol `PLAN.md` was committed before any evaluation prediction. Predictions (`out/predictions_A.csv`, sha256
`17df7b0f…`) were committed before grading. Grading checks that hash.

## Reproduce
```
python -m research.rotation_totals.build A    # predictions only; outcomes never enter -> out/predictions_A.csv (+ .sha256), build_A.txt
python -m research.rotation_totals.grade A    # verifies the hash, grades -> out/bets_A.csv, report_A.txt
python -m research.rotation_totals.verify A   # independent checks -> out/verify_A.txt
```
Source hashes: `SOURCES.sha256` (frames, conservative frame, lag-1 stage 1, rotation code and output, all six quote
files). Candidate fits: `out/candidate_2025.json`, `out/candidate_2026.json`.

## Log of every run
1. **First build:**
   - **Problem:** L-BFGS stopped before the frozen convergence criterion (gradient norm 0.35 and 0.65, criterion
     < 1e-6). Hash kept in `out/predictions_A_lbfgs.sha256`; never graded.
   - **Fix:** exact Newton steps on the same objective (gradient norm 7.6e-7 and 3.3e-13). Same bet counts.
2. **Graded build:** the Newton build.
3. **Verify:** first version mis-specified the stage-1 cutoff check (compared a league-wide game count with a
   team's games). It was corrected to compare the fit's game count with the production fit before D-1. All checks
   pass.

## Coverage (Stage A: the six existing dates)

| Season | Target games | Eligible | Not in feed | No complete DraftKings market | Team played D-1 (excluded) | Left-censored (of eligible) |
|---|---|---|---|---|---|---|
| 2024-25 | 339 | 325 | 11 | 0 | 3 | 2 |
| 2025-26 | 309 | 272 | 9 | 9 | 19 | 17 (14 on 2026-03-07) |

- **Fallbacks:** no KenPom or Torvik fallbacks.
- **Rotation adjustment missing:** 45 eligible games (7.5%), set to 0 as frozen.
- **Opener check:** none of the first-observed quotes is a proven opener.

## Results (1 unit risked per bet, recorded DraftKings prices, pushes 0)

| | Bets | W-L-P | Win % | Units | ROI | Max drawdown |
|---|---|---|---|---|---|---|
| 2024-25 baseline | 63 | 34-29-0 | 53.97 | +2.01 | +3.2% | 7.53 |
| 2024-25 candidate | 84 | 48-36-0 | 57.14 | +8.02 | +9.6% | 5.16 |
| 2025-26 baseline | 66 | 39-27-0 | 59.09 | +8.37 | +12.7% | 6.48 |
| 2025-26 candidate | 55 | 33-22-0 | 60.00 | +8.44 | +15.3% | 5.09 |
| Pooled baseline | 129 | 73-56-0 | 56.59 | +10.38 | +8.0% | 6.74 |
| Pooled candidate | 139 | 81-58-0 | 58.27 | +16.46 | +11.8% | 5.18 |

**Incremental units (candidate − baseline):**

| | All eligible | Date-clustered 95% | Excluding left-censored |
|---|---|---|---|
| 2024-25 | +6.01 | [−8.73, +16.19] (3 dates) | +5.10 |
| 2025-26 | **+0.07** | [−11.04, +22.08] (3 dates) | +0.79 |
| Pooled | +6.08 | [−13.27, +27.30] (6 dates) | +5.90 |

A game-level interval, which ignores dependence between games on the same date, is no tighter: pooled
[−17.5, +29.1].

**Where the difference comes from (pooled):**
- 54 shared bets: identical units.
- 0 flipped.
- 85 added by the candidate: +11.11 units.
- 75 dropped from the baseline: those had made +5.03 units.
- **The candidate's edge is entirely in which games it bets, not in better calls on the same games.**

**Concentration by date (incremental units):**

| Date | Season | Incremental units |
|---|---|---|
| 2024-11-09 | 2024-25 | +5.40 |
| 2025-01-11 | 2024-25 | −2.91 |
| 2025-03-01 | 2024-25 | +3.52 |
| 2025-11-08 | 2025-26 | −3.68 |
| 2026-01-10 | 2025-26 | +7.36 |
| 2026-03-07 | 2025-26 | −3.62 |

- Without its best date (2026-01-10), the pooled gain is **−1.28**.
- 2025-26 without its best date: **−7.29**. That season's +0.07 is one good date and two bad ones.

## Verdict under the frozen rule: INCONCLUSIVE
- **Conditions met:**
  - incremental units are positive in both seasons;
  - pooled candidate units are positive.
- **Condition not met:** the pooled incremental interval is far from excluding 0. 2025-26's gain is effectively
  zero, and the pooled gain disappears without one date.
- **Power:** six dates cannot settle a difference of this size.

## Caveats (disclosed)
- **Training gap:** the classifier is trained on ESPN closing totals of the three earlier seasons, because no
  opener or timestamped quotes exist for 2021-22 and 2022-23. It is applied to first-observed DraftKings quotes.
- **Not new evidence:** these six dates were also used by another chat's pilot of a related candidate, so they are
  not untouched. This is a newly specified test, not a reproduction of that pilot. Different eligibility, inputs and
  baseline mean the numbers are not comparable.
- **Reconstruction, not replay:** conservative daily cutoff (inputs as of the day before). KenPom/Torvik
  publication times and later box-score corrections cannot be verified.

## Next step (Chad's call)
Stage B: the 20 dates already frozen in `PLAN.md` (10 per season, rule-based).
- **Cost:** about 28,600 Odds API credits.
- **Balance:** 57,835 on Oct 29, with about 25,000 held for the live logger until the Nov 25 renewal.
- **Process:** same frozen specification, no changes. The verdict is then taken on all 26 dates, with Stage A and
  Stage B also reported separately.
- **If not approved:** the test stays inconclusive and nothing changes.
