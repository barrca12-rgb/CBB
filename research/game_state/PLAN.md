# Game-state-adjusted team ratings (pre-registered Oct 29, 2026, before any stage-2 validation or 2025-26 scoring)

Research only (`research/game_state/`). The live model, shadows, predictions, picks, alerts, thresholds, staking and
bet logs are unchanged. Nothing is promoted and no follow-up variant is launched from the 2025-26 result.
**2025-26 has been examined extensively in earlier studies; it is not an untouched holdout. Results are exploratory.**

**Hypothesis:** raw per-possession scoring and pace mix team strength with behavior caused by the score and the
clock (bench units and clock-killing in decided games, strategic fouling at the end). Weighting possessions by game
state may estimate offense, defense and tempo better, and so forecast spreads and totals better.

## What already exists (code and ledger)
| Where | Treatment | Status |
|---|---|---|
| `cbb/data.py`, `cbb/ratings.py` (stage 1) | Every possession counts equally in ppp (3-point luck regressed) and pace. Overtime: pace is per 40 minutes; ppp includes overtime possessions. A per-game weight hook `wt_mult` exists but is unused | live |
| Stage 2 (`cbb/projection.py`) | No endgame or overtime term. The intercept carries average overtime (5.5-7.1% of games, 1.3-2.0 pts/game, quant3) and average late fouling. `ref_fouls` is crew tendency (0 in research frames) | live |
| research/pbp P2 | Garbage-time net points (margin > 20, last 10 min) as a stage-2 feature | killed (adjustment too small to change plays) |
| research/quant E1 | Endgame/overtime tie-probability term in totals | absent (worse in 7 of 7 seasons) |
| research/totals_late (h) | Blowout term in totals | killed (no effect) |
| research/quant2, quant3 | Overtime share of the totals skew; truncated play-by-play artifact | diagnostic |

**The missing adjustment:** no study has changed how stage 1 *estimates* offense, defense and tempo from
possessions. P2 added garbage-time points as an outcome-side feature; it did not re-estimate ratings. This study
changes only the stage-1 rating inputs.

## Data (built and validated before this plan; `possessions.py`, `out/possession_validation.txt`)
- **Possessions:** reconstructed from cached ESPN play-by-play (2014-2026). 2013 has no play-by-play, so its games
  keep production inputs.
- **Valid game:** all of the following must hold:
  - the play-by-play final equals the schedule final;
  - the number of periods matches;
  - the possession points sum to the final;
  - the clock never runs backward;
  - the two teams' possession counts differ by ≤ periods + 1;
  - the possession count is within 10% of the box-score estimate.
- **Coverage:**
  - Valid games are 83-91% of model games in 2014-2021, 94-96% in 2022-2025, and 99.1% in 2025-26.
  - Among valid games, possessions average 1.000-1.007 of the box estimate (SD 0.014-0.017).
- **Game state before each possession**, using only the score and clock at that moment (never the winner, final
  margin or later events):
  - the offense's lead;
  - seconds left (in regulation, or in the current overtime period).
- **Observed vs inferred fouls:**
  - **Observed:** personal fouls are logged events, about 33-38 per game.
  - **Inferred late-game fouling:** a defensive foul within 8 s of a possession's start, possession starting with
    ≤ 2:00 left, offense ahead by 1-12. It is inferred, not labeled: ESPN's rare "Intentional Foul" is a flagrant
    call.
  - **Frequency and cost:** 0.46-0.63 such possessions per game, at 1.42-1.49 pts each (overall 1.00-1.08).
  - **Uncertainty:** the rule can include ordinary fouls and miss slow fouls.

## The adjustment (`stage1.py`; smooth, one strength parameter)
**Weighting:**
- **Decidedness before a possession:** D = 2Φ(|lead| / (11·√(max(τ,1)/2400))) − 1, where τ is seconds left.
  - 11 points is a full game's margin SD and is fixed, not tuned.
  - D = 0 for a level game, approaching 1 when the game is out of reach.
- **Possession weight:** w = 1 − α·D^κ.
- **Team-game targets:**
  - ppp moves by (weighted − unweighted) play-by-play ppp.
  - Pace moves by (weighted − unweighted) possessions per 40 minutes, with time weighted the same way.
  - Games without valid play-by-play keep production targets.
- **Variants (10, all recorded):**
  - none (α = 0);
  - κ ∈ {2, 8} × α ∈ {0.25, 0.5, 0.75, 1};
  - "foul": weight 0 on inferred late-fouling possessions only.

**Strength vs settled score:**
- **Strength from the adjusted fit:** home edge, offense, defense and tempo.
- **Level from the unadjusted fit:** b0 and p0, which carry average late fouling.
- **Effect:** the stage-1 forecast stays on the full-game scale.
- **Overtime:** enters exactly as before (pace per 40 minutes; stage 2's intercept), so it is not counted twice.
- **What is not modeled:** a matchup-specific endgame (e.g. blowouts compressing margins). Validation on settled
  full-game results is what checks it; diagnostics by predicted-margin size and for overtime games are reported.

**Isolation:** the stage-1 forecast change (adjusted − unadjusted, both from today's code) is added to the exact
baseline frames' stage-1 inputs (`pred_margin`, `pred_total` and their early-season interactions). Every other
input is untouched.
- **Why a difference:** the recorded stage-1 file differs slightly from today's code (mean |Δ| 0.05 pts of margin,
  max 1.1, November preseason-prior inputs).
- **Exactness:** with α = 0 the research forecast equals the baseline exactly.

## Two stage-2 families, separately identified
- **F (fixed):** the baseline's own walk-forward stage-2 coefficients (fit on unadjusted inputs, 2013..s−1)
  applied to the adjusted inputs.
- **R (refit):** stage 2 refit walk-forward on adjusted training inputs, seasons 2014..s−1 (play-by-play years).
  - **Control:** the same refit on unadjusted inputs, same rows (equivalently refitted unadjusted control).
- **Decision family per market:** F, unless the scale check fails, in which case R.
  - **Scale check:** for R's selected variant, SD of the adjusted stage-1 input ÷ SD of the unadjusted one, on
    validation games, outside [0.95, 1.05] means a refit is needed because the scale changed.
  - Both families are always reported.

## Learning (seasons before 2025-26 only; frozen before scoring)
- **Validation seasons:** 2019-2025. Each season is predicted with stage-2 coefficients from earlier seasons only.
- **Stage 1:** walk-forward by day within each season (games before the day).
- **Selection:** per market (margin → spreads, total → totals) and per family, choose the variant with the lowest
  validation MSE against the settled full-game result.
  - The totals forecast includes the live opening-week rule.
  - "none" is a candidate; ties go to the smaller adjustment.
- **Reported, not used to choose:** validation units at the close (−110).
- **Freeze:** selected variants, scale checks and decision families go to `out/frozen.json`, committed before any
  2025-26 adjusted stage-1 is computed.

## Pools (2025-26; identical opportunities, prices and selection rules for every comparison)
| Pool | Quotes | Price | Inputs | Status |
|---|---|---|---|---|
| A-tot, A-spr | ESPN closing total / spread | assumed −110 | live-like frame (stage 1 before D, KenPom D−1, crews 0) | **primary** |
| B-tot, B-spr | ESPN opener (oriented; swapped records out) | assumed −110 | conservative frame (stage 1 before D−1, KenPom D−1, Torvik earlier, market before D−1), clean-train stage-2 weights 2013..s−1 | **descriptive** (openers have no timestamp) |
| C-tot, C-spr | DraftKings first-observed complete market, 2025-11-08, 2026-01-10, 2026-03-07 (272 games) | recorded | strict decision-time inputs (rotation_totals Amendment 1: stage 1 before D−1, KenPom D−2, Torvik D−3 for day-before decisions) | **dated sample, not full-season** |

- **Adjusted inputs:** stage-1 deltas at lag 0 for A, and lag 1 (games before D−1) for B and C.
- **Coverage pool:** games where both teams have valid play-by-play for ≥ 90% of their earlier same-season games.
  The baseline is reported on the full pool and on the coverage pool.
- **Selection:**
  - **Spreads:** edge ≥ 2.5 and EV ≥ 2% (0.0255/pt, cap 0.58).
  - **Totals:** edge ≥ 3 and EV ≥ 2% (0.014/pt, cap 0.565).
  - **Stakes:** flat 1 unit risked.

## Reconciliation (must hold before scoring)
| Figure | Prior source |
|---|---|
| A-tot baseline 1,478 at 48.71% | quant3 `variants.csv` v1 2026; persistent_disagreement A |
| Live-like opener spreads 462-335-0 | stage2_stability R0; persistent_disagreement B |
| Live-like opener totals 1,407 at 55.51% | quant3 `variants.csv` |
| Without the opening-week rule: close totals 1,485 at 48.485%, close spreads 861 at 50.987%, opener totals 1,417 | quant `baseline_run.txt` |
| C-spr baseline 43 bets 27-16-0, +7.89 recorded | persistent_disagreement C |
| C-tot baseline 64 bets 38-26-0, +8.56; rotation classifier 55 bets, +8.45 | rotation_totals `report_A_strict.txt` |
| quant3's "236 truncated 2025-26 games" vs 4 final-score failures among model games here | explained in LOG |

## Comparators (strongest existing research candidates, same pool and rows)
- **Totals:**
  - E2 (neutral + conference-game terms, walk-forward refit);
  - C2 (v1 − 0.61);
  - in pool C, also the rotation-totals classifier (strict).
- **Spreads:** lineup v2 (v1 margin + β·rotation adjustment, β = 0.38 walk-forward).
- **"Strongest":** whichever of these has the most units on that pool. This is the strictest comparison, so a
  weaker comparator cannot be substituted.

## Report (per pool, assumed and recorded prices separate)
- **Results:** opportunities, bets, W-L-P, win %, ROI, units.
- **Differences:** vs baseline, control (R) and the strongest comparator, with date-clustered paired bootstrap
  95% intervals.
- **Selection:** retained, added, dropped and reversed bets.
- **Breakdowns:** monthly results, top dates, units without the best date.
- **Diagnostics (supporting only):** MAE, RMSE and bias vs settled results, by predicted-margin size and for
  overtime games.

## Verdict rule (fixed now)
A market (spreads or totals) **adds net units** only if, on its primary closing pool (A), in its decision family,
all of the following hold:
1. The selected variant is not "none".
2. Candidate − control (F: baseline; R: refit control) > 0, with the 95% date-clustered interval above 0.
3. The same difference > 0 on the coverage pool.
4. Candidate − baseline > 0.
5. Candidate − strongest existing comparator > 0.

Otherwise the answer for that market is **no**. Pools B and C inform credibility only. There is no
re-specification after scoring.

## Verification (separate script)
- **Possession accounting:** recomputed independently on a sample of games (points, counts, state before each
  possession).
- **Feature timing:** every team-game feeding a forecast is dated before its cutoff.
- **Reproduction:** α = 0 reproduces production stage 1.
- **Reconciliation:** the table above.
- **Grading:** recomputed with independent code.
- **Untouched:** no file outside the folder changes, apart from `.gitignore` for large caches.
