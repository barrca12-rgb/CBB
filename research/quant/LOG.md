# Quant lead: results log (plan in PLAN.md, committed before any challenger was fit)

Every variant run is listed here, failures included.

| # | Variant | Market | Pre-registered? | MAE gain 2020-26 (+ = better) | Verdict |
|---|---|---|---|---|---|
| 1 | E1 endgame/OT term `p_tie` | total | yes | -0.0033 [-0.0051, -0.0016]; 0 of 7 seasons better | **absent** |
| 2 | E2 `neutral` + `conf_game` | total | yes | +0.0114 [99.2%: +0.0037, +0.0196]; 7 of 7 | **credible candidate (exploratory)** |
| 3 | E3 `venue x conf_game` | spread | yes | +0.0012 [99.2%: +0.0002, +0.0022]; 5 of 7 | **inconclusive** (real but negligible) |
| 4 | E2 decomposition: `neutral` only | total | no (diagnostic after the result) | +0.0107 | carries all of E2 |
| 5 | E2 decomposition: `conf_game` only | total | no (diagnostic after the result) | -0.0007 | nothing |

`out/exp_run.txt`, `out/exp_result.csv`, `out/exp_by_season.csv`, `out/e2_checks.txt`.

## E1: absent
Fitted with every other input, the tie-probability term comes out *negative* (-2.1, i.e. at most -0.08 points),
and it worsens totals in every season. The raw scan pattern (close games over the model) is already explained by
the existing inputs; closeness itself adds nothing.

## E2: credible candidate, exploratory (neutral sites score less than the model expects)
- **Totals, 2020-26 (same 37,695 games):** MAE 13.1499 -> 13.1385. Better in all 7 seasons (+0.004 to +0.017).
- **Where:** all of it is neutral-site games. Baseline mean residual on neutral games -1.50 (Nov-Dec events) and
  -2.61 (March tournaments); MAE gain +0.096 and +0.212 there. Home/away games: -0.004 to -0.015 (the fit spreads a
  little intercept). Fitted neutral coefficient -1.69 points.
- **Opener totals 2024-26, fixed 3-point threshold:**
  - win% 55.56 -> 56.28 (+0.73, 95% date bootstrap [+0.02, +1.50]); plays 3,706 -> 3,763; CLV 1.671 -> 1.719.
  - The 3,306 shared plays never flip side. Plays only the baseline makes win 47.9% (412); plays only E2 makes
    win 54.7% (466).
- **Close totals 2020-26:** 51.61% -> 51.83% (11,059 -> 10,885 plays). Calibration vs the close: slope 0.143 -> 0.161
  (the edge vs the close carries more of the result).
- **In-sample 2015-17 openers** (the scan era, so not evidence): 57.71% -> 57.99%.
- **Simulated ROI at -110:** +6.1% -> +7.5%. Simulated only: historical opener prices are verified for 12 sampled
  dates, not for these games.
- **Why credibility is limited:** every season here has been used before (about 40 tests on the same 2014-26 data
  this week). The effect is consistent and has a plain mechanism, but it is exploratory until it holds on 2026-27.
- **Link to the late-season totals problem** (research/totals_late): March conference and NCAA tournament games are
  neutral-site and over-predicted by about 2.6 points, part of why January-April totals lose to the close.

## E3: inconclusive
The home side does about 0.35 points worse in conference games than one venue term implies. It is statistically
real but worth 0.001 points of MAE and +0.18 opener win% on 2,268 plays. That is not enough to act on.

## Spreads
Nothing tested here improves spreads materially. Prior work (SUMMARY.md) found the same.

## Prospective test of E2 (pre-registered Oct 28, 2026, before any 2026-27 game)
- **Coefficients:** frozen today in `out/e2_coefficients.json` (fit 2013-26; never refit during the test).
- **Data:** scored after the fact from `reports/features_<date>.csv` (already written by every card run) and the
  card's `open_total`. No live change, no new job: `python -m research.quant.e2_shadow score`.
- **Read:** with the March 14 decision read.
- **Primary:** neutral-site totals MAE, E2 vs v1, paired date bootstrap.
- **Pass:** gain above 0 with the 95% interval excluding 0, AND all-games totals MAE not worse, AND opener totals
  win% at the fixed 3-point threshold not lower.
- **If it passes:** a live change proposal for 2027-28 (Chad's approval, freeze entry, Discord note).
- **Otherwise:** closed.

## 2026-10-28: Chad kept v1 live; E2 runs as a shadow (scorer revised before any 2026-27 game was final)
- No live change. E2 is scored after the fact from the card's saved inputs; coefficients stay frozen.
- Scorer fixes, so v1 matches the card exactly:
  - both versions get the live opening-week shift to KenPom (`run_day.opening_week_totals`);
  - finals come from the ESPN schedule, and `conf_game` from the schedule's pre-game flag.
- Check: v1 totals equal the card's `model_total` on all 121 priced Nov 1-2 games (max diff 3e-14).
- The pass rule and the March 14 read are unchanged; the weekly health line also shows the running numbers.

## 2026-10-29: E2 decision endpoint moved to paired CLV (Chad approved, before any 2026-27 game)
- **The live shadow:** E2 now runs as a live shadow (`cbb/shadow_e2.py`, `research/e2_shadow/PLAN.md`) with these
  same frozen coefficients.
- **The decision rule:** the weekly paired-CLV sequential read (`research/power/sequential.py`): |z| ≥ 3.29 at
  interim looks, 1.96 at the Mar 14 final.
- **The MAE pass rule above:** becomes secondary, still scored and reported on Mar 14.
- **Why:** on the opener backtest, paired CLV separated E2 from v1 in both eras (+209 and +151 points). The MAE
  rule could not in one season.
