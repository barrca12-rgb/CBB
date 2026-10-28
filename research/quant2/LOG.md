# Quant batch 2: results (plan in PLAN.md, committed before any fit as b1d8f2a)

Every variant run is listed here, failures included. All exploratory: every season has been used before.

| # | Variant | Market | Pre-registered? | Result | Verdict |
|---|---|---|---|---|---|
| 1 | C1 falsification: variance model for \|result - close\| (fit 2014-17, test 2018-19) | spread | yes | corr 0.047, sigma P90/P10 **1.094** (bar 1.10) | **rejected (stopped at the gate)** |
| 2 | same | total | yes | corr 0.048, P90/P10 **1.074** | **rejected (stopped)** |
| 3 | C2 falsification: residual median vs mean by decile, 2014-19 | both | yes | margin max gap 0.76, total overall mean +1.18 vs median +0.40 | passed the gate |
| 4 | C2 median (LAD) stage 2 | spread | yes | MAE +0.0021 [99.4%: -0.0015, +0.0055], 5/7 seasons; RMSE 11.2574 -> 11.2589 | **rejected** |
| 5 | C2 median (LAD) stage 2 | total | yes | MAE 13.1499 -> 13.1254, **+0.0245** [99.4%: +0.0134, +0.0351], 6/7 seasons; RMSE 16.6649 -> 16.6570 | passes the bar; see why |
| 6 | A1 v1 slopes, intercept at the training-residual median (-0.60) | total | no (ablation after #5) | +0.0246 [+0.0178, +0.0316] | reproduces #5: the gain is a constant shift |
| 7 | A5 same centering on E2's features (secondary; E2 untouched) | total | no (ablation) | +0.0243 beyond E2 | adds to E2 |

`out/falsify.txt`, `out/c2_run.txt`, `out/c2_by_season.csv`, `out/c2_why.txt`.

## C1: rejected at the gate
Pre-game features predict the size of the miss against the close only weakly (correlation 0.05). The predicted
spread of outcomes varies by under 10% from game to game in both markets. Against the closing line, outcomes are
close to homoskedastic, so per-game cover probabilities cannot add much to the card's single mapping. Stopped
before any probability model was built, as pre-registered.

## C2: why it wins, and why it is smaller than it looks
- **It is one number.** Least absolute deviations changes the totals intercept, not the weights: moving v1's
  intercept by -0.60 points (A1) gives the same gain. Spreads: nothing.
- **Real part, skew.** Totals residuals are right-skewed: 6.1% of games go to overtime and finish about 17.7 points
  over. Mean minus median is +0.61 overall and +0.31 in regulation-only games. For absolute error and for
  over/under, the median is the right center. With no bias, a 0.6-point shift is worth only about 0.005-0.01 of
  MAE.
- **Confounded part, scoring level.** The season gains follow v1's yearly totals bias:

  | | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
  |---|---|---|---|---|---|---|---|
  | v1 mean residual | -1.63 | -1.58 | -1.25 | -0.19 | -0.19 | -0.05 | +0.60 |
  | C2 MAE gain | +0.061 | +0.049 | +0.043 | +0.011 | +0.016 | +0.006 | -0.004 |

  Most of the 2020-26 gain is v1 over-forecasting in low-scoring years; in 2026, a high-scoring year, the shift hurt.
- **Share of games over the forecast** (a median forecast is near 50%): v1 47.2%, C2 48.8%.
- **Fixed thresholds** (source 3, not the forecast claim):
  - Opener totals 2024-26: 3,706 plays at 55.56% -> 3,376 at 56.31%. The 937 dropped won 53.4%; the 607 added
    won 56.3%.
  - Overs share of plays: 71% -> 51%. v1 leans heavily to overs at the opener.
  - Close 2020-26: 51.61% -> 52.10%.
  - Fewer plays, so the win-rate change is not evidence of a better forecast by itself.
- **Verdict:** passes the pre-registered bar, but the honest size of the durable part (skew) is about 0.005-0.01
  MAE. That is **credible enough for an after-the-fact prospective read, not for adoption.**

## Prospective test of C2 (pre-registered Oct 28, 2026, before any 2026-27 game)
- **Challenger:** C2 total = the card's v1 total - 0.61 (frozen; the 2026 fit's training median, never refit),
  including opening week.
- **Scoring:** `python -m research.quant2.c2_shadow`, from the files the card already writes. No live job, no new
  infrastructure; E2's scorer is reused read-only.
- **Read:** March 14.
- **Primary:** totals MAE gain, paired date bootstrap. Pass = gain > 0 with the 95% interval excluding 0, AND
  opener totals win% at 3+ not lower.
- **Also reported:** v1's median residual and the share over the forecast.
- **Power warning:** one season (about 5,000 games) has a standard error of roughly 0.008 on this gain. A
  skew-only effect (about 0.005-0.01) will probably not reach significance. A null read means "too small to see in
  one season", not "wrong".
