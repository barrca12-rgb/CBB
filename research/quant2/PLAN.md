# Quant batch 2: pre-registration (Oct 28, 2026, written and committed before any candidate was fit)

Research only (`research/quant2/`). v1 stays live and unchanged; E2 stays frozen in its prospective test and is
used here only as a secondary comparison. All seasons 2014-26 have shaped development, so every finding below is
**exploratory**.

## Baseline and ledger
- **Baseline:** v1's frozen live-like walk-forward (`research/quant/common.py`, verified in research/quant: it
  equals the production code and the live coefficients exactly).
  - 2020-26: margin MAE 8.882, total MAE 13.150.
  - Cover probability on the card = 0.5 + 0.0255 x edge (spreads, cap 0.58) and 0.5 + 0.014 x edge (totals, cap
    0.565), `cbb/run_day.win_prob`. It is homoskedastic: the same edge gets the same probability in every game.
- **Already tested, not repeated** (research/*/LOG.md):
  - rotation and player value (v2 shadow);
  - recency weights, two-regime fits, tier-specific stage-1, half-life, prior strength;
  - 3-point luck (D2, P1, R1, R2);
  - garbage time; Poisson and multiplicative functional form (Poisson totals is on the March list);
  - rematches, public-team bias, home-court variants, pace mismatch and 3PA interplay (about 0.15 points);
  - calibration of mean forecasts; new coaches;
  - E1 (overtime/endgame term in the mean, rejected), E2 (neutral totals, in shadow), E3 (conference home court).
- **No tree or boosting experiment exists in the repository's ledger.** I cannot compare to one; no tree model is
  proposed here, because neither candidate needs one.

## Shortlist (ranked)
Ranked by plausible signal, data quality, availability at forecast time, novelty and cost.
1. **Heteroskedastic cover probabilities** (distribution).
   - The spread of outcomes around the line should scale with possessions and with how lopsided and uncertain the
     game is.
   - Never tested: every probability on the card assumes one spread for all games.
   - Data in hand, cheap. **Selected (C1).**
2. **Median (least-absolute-deviation) second stage** (estimating the right quantity).
   - Cover and MAE depend on the median; OLS estimates the mean, which blowouts and overtime pull.
   - Never tested; one-line change to the fitting step. **Selected (C2).**
3. *Preseason continuity weighting:* dropped. The stage-1 prior is KenPom + Barttorvik preseason, which already
   use returning minutes and roster data.
4. *Opponent-dependent tempo:* dropped (pace mismatch already tested at about 0.15 points).
5. *Ensemble breadth (Haslametrics, EvanMiya):* dropped for now. Only end-of-season archives and two days of
   snapshots exist, so there is no leak-free history.
6. *Shooting skill vs luck, competitive possessions, endgame:* already tested (see the ledger).

## C1. Heteroskedastic cover probabilities
- **Hypothesis:** the SD of (result - line) varies predictably between games, so P(cover) at a given edge should
  vary too.
- **Mechanism and sources:**
  - Stern (1994, JASA 89:1128, "A Brownian motion model for the progress of sports scores"): the score difference
    behaves like a Brownian motion whose variance grows with elapsed play, so variance scales with possessions.
  - Blowouts, early-season uncertainty, disagreement between rating systems and three-point reliance add
    variance on top.
  - Proper scoring: Gneiting and Raftery (2007, JASA 102:359).
- **Variance features, pre-game only:** pace (`pred_poss`), model total, |model margin|, games played,
  neutral, |KenPom margin - stage-1 margin| (source disagreement), and both teams' season-to-date 3PA rate (from
  earlier games only).
- **Baselines:**
  - B0, the live linear mapping;
  - B1, a homoskedastic probit refit P = Phi(a + b x edge) (same flexibility minus heteroskedasticity).
- **Challenger:** P = Phi(a + b x edge / sigma_hat).
  - sigma_hat from a regression of |result - close| on the variance features.
  - Both fit walk-forward, on seasons before s only.
- **Evaluation:** home-cover and over outcomes vs the close, 2020-26 (pushes dropped); also vs the opener
  (2024-26).
- **Primary metric:** mean log loss, challenger vs B1, paired, date bootstrap.
- **Also reported:** Brier, calibration (intercept and slope), season by season.
- **Fixed-threshold selection (source 3):**
  - Edge thresholds are unchanged; only the +2% EV filter at an assumed -110 can change.
  - Report the changed plays.
- **Minimum useful:**
  - log-loss gain of 0.0005 or more per game, 95% interval excluding 0, better in at least 5 of 7 seasons, in a
    market.
  - Below that: inconclusive or rejected.
- **Cheap falsification first (2014-19 only):**
  - Fit the variance model on 2014-17, predict 2018-19.
  - **Stop** if corr(sigma_hat, |result - close|) < 0.03 or the 90th/10th percentile ratio of sigma_hat is
    < 1.10, in both markets.

## C2. Median second stage
- **Hypothesis:** fitting stage 2 by least absolute deviations (Koenker and Bassett 1978, Econometrica 46:33)
  instead of least squares gives better MAE and cover rates.
- **Mechanism:** the conditional median differs from the mean in skewed games (lopsided margins, overtime-heavy
  totals).
- **Data:** same features, same frames, same walk-forward; only the loss changes. Fit by iteratively reweighted
  least squares; ridge penalty as v1.
- **Cheap falsification (2014-19 only):**
  - Median of v1 residuals by decile of predicted margin and of predicted total.
  - **Stop** if every decile median is within 0.20 points of its mean and the overall median is within 0.10 of 0,
    in a market.
- **Primary metric:** MAE 2020-26, paired, date bootstrap.
- **Also reported:** RMSE (expected to worsen slightly), season by season; ATS / over-under at the fixed
  thresholds vs the opener 2024-26 and the close 2020-26, with the changed selections.
- **Minimum useful:** MAE gain of 0.010 or more, 95% interval excluding 0, better in at least 5 of 7 seasons.

## Multiple testing and decisions
- **Tests:** 2 candidates x 2 markets = 4 primary tests. A candidate is credible only if its gain survives a
  99.4% interval (Bonferroni over this batch).
- **Prior use of the data:** this is the eleventh-plus test on the same seasons, so even a pass is exploratory.
  It earns at most a prospective shadow read, scored after the fact from the card's saved inputs like E2.
- **Survivors:** checked for information beyond E2 (totals only), without touching E2.
- **Log:** every variant run goes in LOG.md.
