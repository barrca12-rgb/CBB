# Rotation-adjusted totals classifier: Stage A result (Oct 29, 2026): **INCONCLUSIVE**

**A close-trained classifier tested at early quotes. It is not the opener-trained test originally requested.** The
classifier learns from ESPN closing totals of the three earlier seasons (no opener or timestamped quotes exist for
2021-22 and 2022-23). It is then applied to first-observed DraftKings quotes.

Research only. Nothing live, no shadow, and no production or shadow file touched (verified). Protocol `PLAN.md` was
committed before any evaluation prediction. Amendment 1 (strict timing) was added after the first grading,
prompted by review of input timing, not by results. Every predictions file was hashed before grading.

## Reproduce
```
python -m research.rotation_totals.build A      # original cutoffs -> out/predictions_A.csv (+ .sha256)
python -m research.rotation_totals.grade A      # -> out/report_A.txt, bets_A.csv
python -m research.rotation_totals.verify A     # -> out/verify_A.txt
python -m research.rotation_totals.strict       # strict cutoffs (primary) -> out/predictions_A_strict.csv (+ .sha256), strict_A.txt
python -m research.rotation_totals.grade A_strict   # -> out/report_A_strict.txt, bets_A_strict.csv
```

## Log of every run
1. **First build:** L-BFGS missed the frozen convergence criterion. Hash kept in `predictions_A_lbfgs.sha256`; it
   was never graded. Refit by exact Newton steps on the same objective.
2. **Original-cutoff build:** graded, INCONCLUSIVE. Kept as a sensitivity analysis.
3. **Verify:** one mis-specified check (stage-1 cutoff) was corrected. All checks pass.
4. **Strict-timing review (Amendment 1):** decision-time cutoffs; KenPom D-2 and Torvik D-3 for the 565
   day-before decisions; graded (primary).

## Timing check against the decision timestamp (strict build)

| Input | Latest information | Before the decision? |
|---|---|---|
| Stage-1 ratings, Four Factors, possessions, season average, rotation, market closes | games of D-2; last D-2 tip ≥ 11.9 h before the earliest decision | yes |
| KenPom (day-before decisions) | archive dated D-2: ratings at the start of D-2 | yes, published by D-2 |
| Torvik (day-before decisions) | file dated D-3 or earlier | yes |
| KenPom and Torvik (32 game-day decisions) | archive D-1, file D-2 | yes, published the day before |
| Rest, neutral, altitude; quotes | schedule; the decision snapshot itself | yes |

- **Not verifiable:** later box-score corrections, and Torvik files possibly reconstructed after the fact.
- **Effect of the rebuild:**
  - KenPom totals moved 0.47 points on average and Torvik 0.72 on the rebuilt slates.
  - 19 baseline and 15 candidate decisions changed.

## Coverage
| Season | Target games | Eligible | Not in feed | No complete DraftKings market | Team played D-1 (excluded) | Left-censored |
|---|---|---|---|---|---|---|
| 2024-25 | 339 | 325 | 11 | 0 | 3 | 2 |
| 2025-26 | 309 | 272 | 9 | 9 | 19 | 17 (14 on 2026-03-07) |

Rotation adjustment missing: 45 eligible games (7.5%), set to 0 as frozen.

## Results, strict cutoffs (primary). 1 unit risked, recorded DraftKings prices, pushes 0

| | Bets | W-L-P | Win % | Units | ROI | Max drawdown |
|---|---|---|---|---|---|---|
| 2024-25 baseline | 70 | 39-31-0 | 55.71 | +4.63 | +6.6% | 7.18 |
| 2024-25 candidate | 87 | 52-35-0 | 59.77 | +12.59 | +14.5% | 4.16 |
| 2025-26 baseline | 64 | 38-26-0 | 59.38 | +8.56 | +13.4% | 8.39 |
| 2025-26 candidate | 55 | 33-22-0 | 60.00 | +8.45 | +15.4% | 4.29 |
| Pooled baseline | 134 | 77-57-0 | 57.46 | +13.19 | +9.8% | 8.52 |
| Pooled candidate | 142 | 85-57-0 | 59.86 | +21.05 | +14.8% | 7.11 |

**Incremental units (candidate − baseline):**

| | Strict (primary) | Date-clustered 95% | Excluding left-censored | Original cutoffs |
|---|---|---|---|---|
| 2024-25 | +7.96 | [+0.55, +16.20] (only 3 dates) | +7.05 | +6.01 |
| 2025-26 | **−0.11** | [−16.70, +30.37] (3 dates) | +0.62 | +0.07 |
| Pooled | +7.86 | [−13.05, +36.13] (6 dates) | +7.68 | +6.08 |

- **On the 2024-25 interval:** it excludes 0 only because its 3 dates all happen to be positive. Resampling 3
  clusters cannot support a claim.
- **Selection (pooled):**
  - 59 shared bets, with identical units.
  - 0 flipped.
  - 83 added by the candidate: +12.97 units.
  - 75 dropped from the baseline: those had made +5.12 units.
- **By date (incremental):**

  | Date | Season | Incremental units |
  |---|---|---|
  | 2024-11-09 | 2024-25 | +2.38 |
  | 2025-01-11 | 2024-25 | +0.18 |
  | 2025-03-01 | 2024-25 | +5.40 |
  | 2025-11-08 | 2025-26 | −4.66 |
  | 2026-01-10 | 2025-26 | +10.12 |
  | 2026-03-07 | 2025-26 | −5.57 |

  - Without its best date (2026-01-10), the pooled gain is **−2.27**.
  - 2025-26 without its best date: **−10.23**.

## Verdict under the frozen rule: INCONCLUSIVE
- **Not met:** 2025-26's incremental units are not positive (−0.11 strict, +0.07 original).
- **Not met:** the pooled interval spans zero by a wide margin.
- **Concentrated:** the pooled gain depends on one date.
- **Met:** candidate units are positive.

## Odds API credits for Stage B (nothing spent)
- **Cost of the 20 frozen dates:** 1,419-1,439 snapshots × 20 credits = **28,380-28,780 credits**. The snapshot
  formula matches the existing files within one snapshot per date. Hard cap: 28,800.
- **Balance:** 57,814 at 14:40 UTC Oct 29 (`lines/odds_api_usage.json` history).
- **Live use through the Nov 25 renewal:**
  - **Measured now (preseason):** about 470 a day (card pull, 3 credits × about 144 runs).
  - **In season:** targeted polls add 2 credits every 3 minutes while any game is in a watch window. That is about
    320-770 a day on normal slates, and up to about 960 if windows cover the whole day.
  - **Total:** about 1,600 (Oct 29-Nov 1) + 24 days × 750-1,200 = **about 19,600-30,400**. This is consistent
    with the projection already in `audit/OPERATIONS.md` (20,000-32,000).
- **Pulling now:** 57,814 − 28,780 = 29,034.
  - That is below the 50,000 research floor (`audit/OPERATIONS.md`, `research/market/LOG.md`).
  - After live use it would leave between about −1,400 and +9,400 at renewal. **It could stop the live logger
    before Nov 25.** Not acceptable.
- **Reserve:** no change proposed. The 50,000 floor covers the worst-case live projection (about 32,000) with a
  margin.
- **Recommendation:** run Stage B right after the Nov 25 renewal.
  - **Assumption:** the plan resets the balance to 100,000; this is confirmed in `lines/odds_api_usage.json`
    before starting.
  - **Cost:** 28,380-28,780 (cap 28,800).
  - **Remaining:** at least 71,200, above the 50,000 floor and enough for December's live use.
  - **Guard:** aborts if the balance would drop below 50,000.
  - The 20 dates are unchanged. They can strengthen the evidence but cannot guarantee a decisive result.
