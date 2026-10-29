# Persistent model-market disagreement: log and result (Oct 29, 2026)

Research only. Nothing live changed. Nothing is promoted, and no further test is launched from this result.
2025-26 was used in earlier research, so it is not an untouched holdout: **exploratory**.

## Verdict
**No.** Persistent-disagreement information does not increase net units beyond simple shrinkage or beyond our
existing candidates, in either market. The frozen rule (PLAN.md) fails on both primary pools.

| Market (primary pool) | Candidate − comparator (95% date-clustered) | Candidate − baseline | Candidate − existing | Rule |
|---|---|---|---|---|
| Closing totals (A) | +3.55 [−5.91, +14.91] **fail** | +105.64 pass | +88.55 pass (E2) | **No** |
| Early spreads (B) | −6.73 [−30.09, +16.82] **fail** | −71.27 **fail** | −76.18 **fail** (lineup v2) | **No** |

**Why totals "beat" the baseline and E2 without adding value.** The gain comes from betting less, not from the
persistence features.
- **Bets:** the baseline and E2 make about 1,460-1,480 bets, both losing. The candidate makes 36.
- **Same gain without the features:** constant shrinkage alone is +102.09 [+30.73, +173.18] vs baseline.
- **What the features add on top:** +3.55. That is the whole of the 2025-11-03 slate (+4.00); without that date it
  is −0.45.

**Why spreads fail.** Shrinkage toward the market cuts bet volume from 797 to 117-160. The baseline's dropped bets
were profitable (+70.18 units across 640 dropped bets).

## Sequence (each step committed before the next)
| Step | Commit | What |
|---|---|---|
| Pre-registration | b60047f | PLAN.md, before any feature was computed |
| Learning, freeze | 0724f21 | 20 variants per market on earlier seasons; `out/frozen.json` |
| Scoring | 4f25a7a | `out/predictions.csv`, sha256 `088048d0…bf8183`, no outcome columns |
| Grading, verification | this commit | `grade.py` → `out/report.txt`, `out/graded.csv`; `verify.py` → `out/verify.txt` |

## Every variant (learning; chosen by validation MSE, units descriptive at −110)
Shared columns:
- **MSE columns:** the mean across folds.
- **Units columns:** summed over the validation seasons.
- **Comparator and baseline:** the same in every row (no grid).

**Closing totals.**
- **Folds:** validate 2019-2025, each fit on 2016..v−1.
- **Comparator:** MSE 272.827, −16.5 units.
- **Baseline:** MSE 277.661, −123.0 units.

| N | k | λ | Candidate MSE | Candidate units |
|---|---|---|---|---|
| 8 | 25 | 10 | 272.830 | −39.5 |
| 8 | 25 | 100 | 272.830 | −39.5 |
| 8 | 25 | 1,000 | 272.830 | −40.3 |
| 8 | 25 | 10,000 | 272.831 | −37.7 |
| 8 | 25 | 100,000 | 272.818 | −23.3 |
| 8 | 100 | 10 | 272.829 | −33.9 |
| 8 | 100 | 100 | 272.829 | −34.8 |
| 8 | 100 | 1,000 | 272.829 | −30.8 |
| 8 | 100 | 10,000 | 272.829 | −37.7 |
| 8 | 100 | 100,000 | 272.815 | −25.4 |
| all | 25 | 10 | 272.816 | −38.2 |
| all | 25 | 100 | 272.816 | −38.2 |
| all | 25 | 1,000 | 272.815 | −37.8 |
| all | 25 | 10,000 | 272.813 | −33.6 |
| **all** | **25** | **100,000** | **272.807** | **−22.8** (chosen) |
| all | 100 | 10 | 272.818 | −34.5 |
| all | 100 | 100 | 272.818 | −34.5 |
| all | 100 | 1,000 | 272.817 | −34.4 |
| all | 100 | 10,000 | 272.815 | −37.3 |
| all | 100 | 100,000 | 272.808 | −29.4 |

**Early spreads at the opener.**
- **Folds:** 2015-16 → 2017; 2015-17 → 2024; 2015-17 + 2024 → 2025.
- **Comparator:** MSE 125.317, +33.7 units.
- **Baseline:** MSE 126.012, +189.2 units.

| N | k | λ | Candidate MSE | Candidate units |
|---|---|---|---|---|
| 8 | 25 | 10 | 125.257 | +77.0 |
| 8 | 25 | 100 | 125.256 | +77.9 |
| 8 | 25 | 1,000 | 125.244 | +80.1 |
| 8 | 25 | 10,000 | 125.233 | +63.4 |
| 8 | 25 | 100,000 | 125.261 | +46.0 |
| 8 | 100 | 10 | 125.262 | +74.3 |
| 8 | 100 | 100 | 125.260 | +74.3 |
| 8 | 100 | 1,000 | 125.248 | +75.1 |
| 8 | 100 | 10,000 | 125.238 | +69.6 |
| 8 | 100 | 100,000 | 125.264 | +44.4 |
| all | 25 | 10 | 125.231 | +67.0 |
| all | 25 | 100 | 125.230 | +68.0 |
| all | 25 | 1,000 | 125.224 | +64.5 |
| **all** | **25** | **10,000** | **125.220** | **+54.7** (chosen) |
| all | 25 | 100,000 | 125.256 | +49.5 |
| all | 100 | 10 | 125.240 | +55.3 |
| all | 100 | 100 | 125.239 | +55.3 |
| all | 100 | 1,000 | 125.232 | +59.5 |
| all | 100 | 10,000 | 125.228 | +60.5 |
| all | 100 | 100,000 | 125.260 | +55.1 |

**Frozen fits** (`out/frozen.json`). Coefficients are listed as [D0, D0·V*, D0·Sdir*, S*].

| Market | Trained on | Candidate coefficients | Comparator c |
|---|---|---|---|
| Totals | 2016-2025 | [0.291, +0.048, +0.052, −0.019] | 0.301 |
| Spreads | 2015-17, 2024-25 | [0.628, +0.053, −0.104, −0.174] | 0.564 |

**Warning visible before scoring:** in every spread variant, shrinkage cost units on earlier seasons (baseline
+189.2, comparator +33.7). MSE-optimal shrinkage is not units-optimal at fixed thresholds. As pre-registered, this
did not change the specification.

## 2025-26 results (1 unit risked per bet)
Full tables are in `out/report.txt`. "Existing" is E2 for totals and lineup v2 (β 0.38) for spreads.

### A. Closing totals
- **Opportunities:** 5,747.
- **Dates:** 147.
- **Price:** assumed −110; there are no recorded closing prices.

| Strategy | Bets | W-L-P | Win % | Units | ROI |
|---|---|---|---|---|---|
| Baseline (v1) | 1,478 | 720-758-0 | 48.71 | −103.45 | −7.0% |
| Comparator (c·D0) | 30 | 15-15-0 | 50.00 | −1.36 | −4.5% |
| **Candidate** | 36 | 20-16-0 | 55.56 | **+2.18** | +6.1% |
| E2 (strongest existing) | 1,459 | 719-740-0 | 49.28 | −86.36 | −5.9% |
| C2 (v1 − 0.61) | 1,482 | 737-745-0 | 49.73 | −75.00 | −5.1% |

**Candidate − comparator: +3.55 [−5.91, +14.91].**
- **Other differences:** − baseline +105.64 [+32.27, +178.64]; − E2 +88.55 [+16.82, +158.00]; − C2 +77.18
  [−2.45, +155.09].
- **vs baseline:** 36 retained (+2.18), 0 added, 1,442 dropped (−105.64 under the baseline), 0 reversed.
- **vs comparator:** 21 retained (+3.82), 15 added (−1.64), 9 dropped (−5.18 under the comparator), 0 reversed.
- **Timing:** 25 of the 36 candidate bets are in November, when |D0| is large enough to clear 3 points after
  shrinking by about 0.3.
- **Monthly candidate units:** Nov −0.18, Dec +1.55, Jan +0.91, Feb +0.91, Mar −1.00.

### B. Early spreads, full season (ESPN opener, untimestamped)
- **Opportunities:** 5,742.
- **Price:** assumed −110.
- **Feature timing:** history from games before D−1.

| Strategy | Bets | W-L-P | Win % | Units | ROI |
|---|---|---|---|---|---|
| Baseline (v1) | 797 | 462-335-0 | 57.97 | +85.00 | +10.7% |
| Comparator | 117 | 72-45-0 | 61.54 | +20.45 | +17.5% |
| **Candidate** | 160 | 91-69-0 | 56.88 | **+13.73** | +8.6% |
| Lineup v2 (strongest existing) | 836 | 485-351-0 | 58.01 | +89.91 | +10.8% |

**Candidate − comparator: −6.73 [−30.09, +16.82].**
- **Other differences:** − baseline −71.27 [−123.09, −23.18]; − v2 −76.18 [−127.82, −26.64].
- **vs baseline:** 157 retained (+14.82), 3 added (−1.09), 640 dropped (+70.18 under the baseline), 0 reversed.
- **vs comparator:** 67 retained (+13.18), 93 added (+0.55), 50 dropped (+7.27 under the comparator), 0 reversed.
- **Monthly candidate units:** Nov −5.73, Dec +9.36, Jan +1.82, Feb −0.27, Mar +8.55.

### C. Early spreads, dated sample (DraftKings first observed; reported, cannot decide)
- **Opportunities:** 272, on 3 dates.
- **Decisions:** 241 day-before, 31 game-day.

**At recorded prices:**

| Strategy | Bets | W-L-P | Units |
|---|---|---|---|
| Baseline | 43 | 27-16-0 | +7.89 |
| Comparator | 8 | 5-3-0 | +1.50 |
| Candidate | 8 | 5-3-0 | +1.51 |
| Lineup v2 | 42 | 27-15-0 | +8.82 |

- **Candidate − comparator:** +0.02.
- **Candidate − baseline:** −6.38.
- **Same games at an assumed −110:** baseline +8.55, comparator +1.55, candidate +1.55, v2 +9.55.

## Descriptive, not pre-registered (no decision rests on it, and nothing is launched from it)
Forecast accuracy of the same frozen predictions on 2025-26: the mean squared error of the result vs the market.
Values are the MSE reduction from using the candidate instead of the comparator, with 95% date-clustered intervals.

| Pool | MSE reduction |
|---|---|
| A totals | +0.12 [−0.16, +0.40] |
| B spreads | **+0.46 [+0.23, +0.69]** |
| C spreads | +0.02 [−0.86, +0.47] |

- **Spreads:** the persistence terms made the opener-spread forecast slightly more accurate than constant shrinkage.
  It still did not convert into units at the fixed thresholds, because any shrinkage removes most of v1's
  profitable bets.
- **Totals:** no accuracy gain.
- **Use:** this is recorded for completeness. Under the brief, it does not justify a follow-up test.

## Verification (`verify.py`, all passed)
- **Hash and freeze:** the predictions hash matches the one written before grading. The frozen fits use seasons
  ≤ 2025 only, and frozen.json was committed before predictions.csv.
- **Feature timing:**
  - Recomputed from scratch for 400 games × 2 lags (250 from 2025-26, 150 from learning seasons). The cached sums
    match to 4.6e-13.
  - Every prior game is dated before its cutoff, completed, and counted once. 41 of the first 3,000 2025-26 games
    are rematches.
  - S and V in predictions.csv match the sums.
- **Pool C quotes:** the DraftKings spread and price are rebuilt independently from the change-only log at each
  decision snapshot (0 mismatches). Every snapshot is before tip.
- **Baseline reconciliation**, from the frame:
  - A: 1,478 plays at 48.71%.
  - B: 462-335-0.
  - Baseline edges equal the frame's.
- **Grading:** recomputed with a plain loop for every pool, strategy and price basis, and matched exactly.
- **Production and shadows:**
  - The only file outside the folder that changed since the study began is one `.gitignore` line for this study's
    feature caches.
  - cbb/, bets/, .github/ and MODEL_FREEZE.md are unchanged.
  - No uncommitted change exists outside the folder.

## Caveats
- **A and B prices:** assumed −110. Only pool C has recorded prices.
- **Pool B openers:** untimestamped. The D−1 history cutoff is conservative, but the quote time is unknown.
- **"First observed":** these are the first quotes we saw, not proven openers.
- **Holdout status:** 2025-26 is not an untouched holdout.
