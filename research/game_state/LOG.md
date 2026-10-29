# Game-state-adjusted team ratings: log and result (Oct 29, 2026)

Research only. Nothing live changed. Nothing is promoted, no shadow is touched, and no follow-up variant is launched
from this result. 2025-26 has been examined extensively in earlier studies; it is not an untouched holdout, so
everything here is **exploratory**.

## Verdict
**No. Game-state context did not add net units in either market.** The frozen rule (PLAN.md) fails on both closing
pools.

| Market | Decision family, frozen variant | Candidate − control, 2025-26 close (95% date-clustered) | vs strongest existing | Rule |
|---|---|---|---|---|
| Spreads | F (fixed stage 2): **none** | 0.00 (identical to the baseline) | −19.73 vs lineup v2 | **No** (no adjustment survived validation) |
| Totals | F: **foul** (inferred late-fouling possessions weighted 0) | +10.55 [−11.36, +32.91] | −17.91 vs C2 | **No** (interval includes 0; trails C2) |

**How credible is the totals improvement?** Not credible.
- **Interval:** +10.55 units vs the baseline, but the interval spans −11 to +33.
- **Source of the gain:** it comes from bets dropped, not bets added.
  - **Dropped:** 61 bets that lost 11.36 under the baseline.
  - **Added:** 81 bets that lost 0.82.
- **Comparators:** it trails C2 (v1 − 0.61) by 17.91 units at the close.
- **Openers:** it loses at the ESPN opener (−1.91; E2 is +42 better there).
- **DraftKings sample:** its only gain (+2.61) is three added bets on one date.

The refit family (reported separately, never decisive here) shows nothing either:
- **Closing totals:** R − refit control is +0.64.
- **Closing spreads:** −0.64.
- **Opener spreads:** −13.27.
- **DraftKings sample:** +2.67 on spreads and +3.63 on totals, each from a single date.

## What already existed, and the missing piece
- **Stage 1** (`cbb/ratings.py`, `cbb/data.py`):
  - Every possession counts equally in ppp (3-point luck regressed) and in pace.
  - Overtime is handled only by measuring pace per 40 minutes.
  - A per-game weight hook (`wt_mult`) exists but is unused.
- **Stage 2:** has no endgame or overtime term. Average overtime and fouling live in the intercept.
- **Earlier studies:**
  - P2 garbage-time points as a stage-2 feature: killed.
  - E1 endgame/overtime tie term: absent.
  - totals_late (h) blowout term: killed.
- **The untested piece:** changing how stage 1 *estimates* offense, defense and tempo from possessions. That is the
  only thing this study changed.

## Data (possessions.py; `out/possession_validation.txt`)
**Possessions:**
- Rebuilt from ESPN play-by-play, 2014-2026 (2013 has none).
- The game state before each possession uses only the score and clock at that moment.

**Coverage of the model's games:**

| Seasons | Valid games |
|---|---|
| 2014-2021 | 83-91% |
| 2022-2025 | 94-96% |
| 2025-26 | 99.1% |

**How games fail:** most failures are a final-score mismatch or a possession-count imbalance (2015: 257; 2018: 177
point-sum failures).

**Accuracy:** possession counts average 1.000-1.007 of the box-score estimate (SD 0.014-0.017). No clock ever ran
backward in a valid game.

**Fouls:**
- **Observed:** personal fouls, 33-38 per game.
- **Inferred late fouling:** a quick defensive foul with ≤ 2:00 left and the offense ahead by 1-12.
  - 0.46-0.63 such possessions per game.
  - 1.42-1.49 points each, against 1.00-1.08 overall.
- **Uncertainty:** inferred, not labeled. ESPN's rare "Intentional Foul" is a flagrant call.

**Coverage pool** (both teams have valid play-by-play for ≥ 90% of earlier games): 95.5% of 2025-26 closing
opportunities.

**Prior-study correction.** quant3 reported 236 "truncated" 2025-26 play-by-play files. That was an ordering
artifact: it took each game's last row by `sequence_number`. By `game_play_number`, only 4 model games differ from
the schedule final.
- **Consequence:** quant3's regulation totals excluded about 232 complete games.
- **Impact:** its conclusions (normal 2025-26 overtime, skew mostly regulation) are unaffected in direction. No
  live figure depends on it.

## Every variant (learning; validation 2019-2025, stage-2 coefficients from earlier seasons only)
- **Weighting:** w = 1 − α·D^κ, where D = 2Φ(|lead| / (11·√(τ/2400))) − 1. "foul" = weight 0 on inferred
  late-fouling possessions.
- **Selection:** by validation MSE against settled full-game results.
- **Units:** at the close, −110, descriptive only.
- **F:** baseline coefficients (fit on unadjusted inputs from 2013).
- **R:** refit on 2014..s−1 (play-by-play years).

| Family | Variant | Margin MSE | Total MSE | Stage-1 SD ratio, margin / total | Spread units (bets) | Total units (bets) |
|---|---|---|---|---|---|---|
| F | **none** (spreads) | **126.0533** | 277.5880 | 1.000 / 1.000 | +18.6 (5,499) | −123.0 (11,537) |
| F | κ2 α0.25 | 126.1996 | 277.6351 | 1.027 / 1.001 | +64.1 (6,207) | −138.0 (11,596) |
| F | κ2 α0.5 | 127.3166 | 277.9600 | 1.072 / 1.005 | −7.6 (8,935) | −117.7 (11,977) |
| F | κ2 α0.75 | 131.6814 | 278.9936 | 1.159 / 1.014 | −277.5 (15,250) | −142.2 (13,173) |
| F | κ2 α1 | 156.5814 | 283.0258 | 1.420 / 1.045 | −804.5 (24,935) | −225.5 (16,177) |
| F | κ8 α0.25 | 126.2769 | 277.5738 | 1.030 / 1.001 | +47.1 (6,328) | −114.4 (11,560) |
| F | κ8 α0.5 | 127.4912 | 277.8063 | 1.077 / 1.004 | −45.9 (9,130) | −50.9 (11,895) |
| F | κ8 α0.75 | 131.3083 | 278.5539 | 1.155 / 1.011 | −363.0 (14,627) | −48.8 (12,924) |
| F | κ8 α1 | 145.1552 | 280.8017 | 1.322 / 1.030 | −654.7 (22,216) | −113.7 (14,972) |
| F | **foul** (totals) | 126.0565 | **277.5647** | 0.998 / 1.002 | +62.4 (5,504) | −176.5 (11,564) |
| R | none (refit control) | 126.0505 | 277.9533 | 1.000 / 1.000 | +57.4 (5,548) | −151.3 (12,229) |
| R | **κ2 α0.25** (spreads) | **126.0011** | 277.8759 | 1.027 / 1.001 | +97.1 (5,726) | −155.6 (12,006) |
| R | κ2 α0.5 | 126.2068 | 278.0009 | 1.072 / 1.005 | +64.0 (6,252) | −170.2 (11,909) |
| R | κ2 α0.75 | 126.6761 | 278.4413 | 1.159 / 1.014 | +8.4 (6,853) | −144.6 (12,022) |
| R | κ2 α1 | 127.0304 | 279.2257 | 1.420 / 1.045 | −36.2 (6,876) | −123.1 (12,302) |
| R | **κ8 α0.25** (totals) | 126.0319 | **277.8104** | 1.030 / 1.001 | +59.3 (5,701) | −165.8 (11,999) |
| R | κ8 α0.5 | 126.2494 | 277.8636 | 1.077 / 1.004 | +38.5 (6,119) | −151.3 (11,894) |
| R | κ8 α0.75 | 126.6606 | 278.1842 | 1.155 / 1.011 | +30.7 (6,633) | −193.8 (12,076) |
| R | κ8 α1 | 126.9821 | 278.7829 | 1.322 / 1.030 | −40.8 (6,857) | −184.8 (12,253) |
| R | foul | 126.0578 | 277.8812 | 0.998 / 1.002 | +66.8 (5,550) | −166.5 (12,144) |

**What validation showed before 2025-26 was touched:**
- **Strength vs settled score:** down-weighting decided possessions widens team gaps and raises home edge (SD up 3%
  at α 0.25 and 42% at α 1). The settled margin includes the compression this removes, so with fixed coefficients
  every non-trivial α forecasts settled margins worse.
- **The refit family:** absorbs the scale. Its best margin variant (κ2 α0.25) beats its own control by 0.049, and
  only because both drop 2013. Its best totals variant (277.81) is still worse than the baseline (277.59).
- **Decision families:** the scale check kept F for both markets. F's selection for spreads is "none", so the
  spread verdict is "no" by rule 1 before scoring.
- **Totals pick:** "foul" was selected on MSE (+0.023). Its validation units at the close were worse than none
  (−176.5 vs −123.0). That was descriptive and not used, as pre-registered.

**Double counting.** This is checked by construction and in diagnostics.
- **Level terms:** b0 and p0 come from the unadjusted fit, so the full-game level (average fouling) is unchanged.
- **Mean shift:** the mean stage-1 total shift is 0.006-0.027 points.
- **Overtime:** enters only through pace per 40 minutes and the stage-2 intercept, as before.
- **2025-26 overtime bias:** +19.86 for the baseline and +19.87 for F on closing totals; −2.06 for both on spreads.
  Overtime games are neither double-counted nor newly mis-forecast.

## 2025-26 results (1 unit risked; full tables in `out/report.txt`)
- **Lines:** closing and opener prices are assumed −110. The DraftKings sample uses recorded prices; −110 is also
  shown for it, in `report.txt`.
- **Columns:** "Δ vs control" is candidate − baseline for F and candidate − refit control for R.
- **Intervals:** date-clustered paired bootstrap 95%.

### Closing spreads (primary): 5,742 opportunities (coverage pool 5,484), 147 dates
| Strategy | Bets | W-L-P | Win % | Units | ROI | Δ vs control |
|---|---|---|---|---|---|---|
| Baseline (v1) | 861 | 439-422-0 | 50.99 | −22.91 | −2.7% | |
| F = none | 861 | 439-422-0 | 50.99 | −22.91 | −2.7% | 0.00 |
| R control | 843 | 429-414-0 | 50.89 | −24.00 | −2.8% | |
| R κ2 α0.25 | 878 | 447-431-0 | 50.91 | −24.64 | −2.8% | −0.64 [−27.37, +25.91] |
| Lineup v2 (strongest) | 826 | 431-395-0 | 52.18 | −3.18 | −0.4% | |

- **Coverage pool:** baseline −16.64, R − control −1.36.
- **R vs its control:** 757 retained, 121 added (+5.00), 86 dropped (+5.64 under the control), 0 reversed.

### Closing totals (primary): 5,747 opportunities (coverage pool 5,488), 147 dates
| Strategy | Bets | W-L-P | Win % | Units | ROI | Δ vs control |
|---|---|---|---|---|---|---|
| Baseline (v1) | 1,478 | 720-758-0 | 48.71 | −103.45 | −7.0% | |
| **F = foul** | 1,498 | 736-762-0 | 49.13 | −92.91 | −6.2% | **+10.55 [−11.36, +32.91]** |
| R control | 1,471 | 727-744-0 | 49.42 | −83.09 | −5.6% | |
| R κ8 α0.25 | 1,478 | 731-747-0 | 49.46 | −82.45 | −5.6% | +0.64 [−28.73, +29.09] |
| E2 | 1,459 | 719-740-0 | 49.28 | −86.36 | −5.9% | |
| C2 (strongest) | 1,482 | 737-745-0 | 49.73 | −75.00 | −5.1% | |

- **Coverage pool:** baseline −101.09, F −86.64 (Δ +14.45 [−7.82, +37.45]).
- **F vs baseline:** 1,417 retained, 81 added (−0.82), 61 dropped (−11.36 under the baseline), 0 reversed.
- **Monthly F − baseline:** Nov −2.00, Dec −0.91, Jan +12.46, Feb +10.18, Mar −9.19, Apr 0.
- **Concentration:** 64 dates differ. The best is 2026-02-07 (+4.64); without it the difference is +5.91.

### ESPN openers (descriptive; untimestamped; conservative inputs, stage 1 before D−1)
- **Baseline here:** spreads 493-351-0 (+97.18) and totals 778-639-0 (+68.27). The live-like figures used in
  earlier studies are 462-335-0 and 1,407 at 55.51%; both are reproduced in `report.txt`.

| Pool | Baseline | F | Δ F | R − refit control | Strongest existing |
|---|---|---|---|---|---|
| Spreads, 5,742 | +97.18 (844 bets) | identical | 0.00 | −13.27 [−38.64, +11.09] | v2 +101.55 |
| Totals, 5,747 | +68.27 (1,417) | +66.36 (1,438) | −1.91 [−24.36, +20.18] | +0.09 [−32.00, +32.91] | E2 +110.55 |

### DraftKings first observed (dated sample, 3 dates, 272 games, recorded prices; not full-season evidence)
| Pool | Baseline | F | R / refit control | Strongest existing |
|---|---|---|---|---|
| Spreads | 43 bets, 27-16-0, +7.89 | identical | +9.67 / +7.00 | v2 +8.82 |
| Totals | 64 bets, 38-26-0, +8.56 | 67 bets, 41-26-0, +11.17 | +12.23 / +8.59 | E2 +12.37 (rotation classifier +8.45, C2 +5.89) |

- **Totals F gain (+2.61):** three added bets, all on 2026-01-10.
- **Spreads R gain (+2.67):** mostly 2026-03-07.

### Supporting diagnostics (2025-26 closing pools; result − forecast)
| Market | Forecast | MAE | RMSE | Bias | Bias where \|pred\| ≥ 15 (spreads) or ≥ 10 from the median (totals) |
|---|---|---|---|---|---|
| Spreads | baseline = F | 8.992 | 11.371 | −0.27 | +0.77 |
| Spreads | R κ2 α0.25 | 8.989 | 11.366 | −0.30 | +0.69 |
| Spreads | closing line | 8.940 | 11.268 | −0.19 | +0.08 |
| Totals | baseline | 13.592 | 17.146 | +0.58 | +0.44 |
| Totals | F foul | 13.587 | 17.143 | +0.58 | +0.44 |
| Totals | R κ8 α0.25 | 13.586 | 17.145 | +0.76 | +0.59 |
| Totals | closing line | 13.379 | 16.893 | +0.58 | 0.00 |

The accuracy changes are in the third decimal place. Every forecast remains less accurate than the closing line.

## Sequence (each step committed before the next)
| Step | Commit |
|---|---|
| Possessions built and validated; PLAN.md pre-registered | 7c8013d |
| Validation of all 20 variant × family fits; `frozen.json` | 3d1aae6 |
| 2025-26 adjusted stage 1 computed (after the freeze; verified by file times) | n/a |
| Hashed predictions (sha256 `5a42f39b…6bd5`) | 38d0bf9 |
| Grading | c8da427 |
| Verification, this log | this commit |

## Reconciliation (all exact)
**Stage 1:**
- **Recorded file vs today's code:** the recorded stage-1 file (`audit/out/_stage1_base`) differs from today's code
  by a mean 0.047 points of margin (max 1.13, November, preseason-prior inputs).
- **Why it doesn't matter here:** the study adds (adjusted − unadjusted) changes from today's code to the exact
  baseline frames, so α = 0 equals the baseline.
- **Exact reproductions:** α = 0 reproduces today's production stage 1 (1e-12) and the audit's lag-1 file (4e-13).

**Pool figures:**

| Figure | Reproduced | Prior source |
|---|---|---|
| Closing totals | 1,478 at 48.71% | quant3, persistent_disagreement |
| Live-like opener spreads | 462-335-0 | stage2_stability R0, persistent_disagreement |
| Live-like opener totals | 1,407 at 55.51% | quant3 |
| Without the opening-week rule: close totals | 1,485 at 48.485% | quant baseline |
| Without the opening-week rule: close spreads | 861 at 50.987% | quant baseline |
| Without the opening-week rule: opener totals | 1,417 | quant baseline |
| DraftKings spreads | 43 bets, +7.89 | persistent_disagreement |
| DraftKings totals | 64 bets, +8.56; rotation classifier 55 bets, +8.45 | rotation_totals |
| Conservative opener totals | 0 difference | rotation_totals.baseline_forecast |
| Lineup v2 frame | max 2e-14 | — |

## Verification (`verify.py`, all passed; `out/verify.txt`)
- **Order:** the hash matches. PLAN → freeze → 2025-26 stage 1 → predictions, in commit and file order.
- **Possession accounting (240 sampled games):**
  - The margin before every possession equals the signed sum of all earlier possessions' points, so no later
    information enters.
  - Period clocks start at 20:00 (5:00 in overtime) and never increase.
  - Points sum to the finals.
  - Possessions match the per-team event-count estimate (ratio 1.010).
- **Feature timing:**
  - For 9 sampled days × 3 variants, the stored forecasts equal production `ratings.fit` on the adjusted targets,
    even with every game on or after the cutoff overwritten with absurd values (1e-11).
- **Grading:** all 46 pool × price × strategy results were recomputed with independent code and matched exactly.
- **Untouched:** the only change outside the folder is one `.gitignore` line for the large parquet caches.
  cbb/, bets/, .github/ and MODEL_FREEZE.md are unchanged.

## Stopping
The hypothesis failed. As instructed: no promotion, no shadow change, and no follow-up variant from the 2025-26
results.
