# Win-probability rule re-fit (pre-registered Oct 29, 2026, before any fit or removal count was computed)

Research only (`research/winprob/`). Approved by Chad. Nothing live changes: `cbb/run_day.py` (`WIN_PROB`, `win_prob`,
`ev`, `MIN_EV`), picks, staking and the bet log are untouched. Any change that survives goes to Chad as a proposal.

**What was looked at before writing this:** column names and opener coverage by season in the frame below; the
book names in one quote file; `bets/bets.csv` (9 rows, all open, none graded). No win rate, fit, price
distribution or removal count was computed.

**Known prior information (not untouched data):** `research/calibration/LOG.md` (Oct 27) already reported 2024-26
opener spread cover rates by edge on a different frame (56.0% at 2.5-3 vs rule 57.0%; 58.4% at 3-4 vs 58.0%), and a
least-squares slope through 50% on 2014-17 (0.0183) that fit 2024-26 worse than 0.0255. The check seasons are
therefore not a clean holdout; results are exploratory.

## Question
The live rule is p(e) = min(0.5 + b·e, c): spreads b = 0.0255, c = 0.58; totals b = 0.014, c = 0.565. A play needs
edge ≥ 2.5 (spreads) / 3 (totals) **and** EV = p·payout(price) − (1 − p) ≥ +2% at the book's price. Is p too
generous, so that the EV filter lets through plays at worse prices (−115, −120 and worse) that should be dropped?
At −110 the EV filter never binds for v1 edges, so the **only** live consequence is at worse prices, and the re-fit
can **only remove** plays (the candidate rule is min(live p, fitted p); it never adds a play).

## Data
- **Frame:** `research/persistent_disagreement/common.baseline()`: live-like walk-forward v1 (stage-2 weights for
  season s fit on 2013..s−1, KenPom from the day before, referee crews 0) with the live opening-week totals rule.
  Swapped records (`swapped`) excluded.
- **Lines:** ESPN openers `open_home_spread`, `open_total` (oriented by moneyline), assumed −110 (no recorded opener
  prices). Closes `home_spread`, `total` for CLV.
- **Edges and results:**
  - Spreads: e = `final_margin` + `open_home_spread` (home side if e > 0); result r = `margin` + `open_home_spread`.
  - Totals: e = `final_total` − `open_total` (over if e > 0); r = `points` − `open_total`.
  - Win if sign(r) = sign(e); **pushes (r = 0) excluded** from win rates and fits.
- **Development seasons:** season labels 2014-2017 (2013-14 to 2016-17), the seasons inside "2014-2019" that have
  openers. The request's parenthetical named 2014-15..2016-17, but 2013-14 openers also exist in the frame; the
  primary fit uses 2014-2017 and a 2015-2017 fit is reported as a sensitivity.
- **Check seasons:** 2024-2026 (2023-24 to 2025-26), the seasons inside "2020-2026" that have openers.

## Fit (per market, development seasons only)
- **Form:** p(e) = min(0.5 + b·|e|, c), through 50% at zero edge, as the live rule.
- **Sample:** every non-swapped, non-push game with |e| ≥ 2 against the opener (all edges above 2, no upper limit).
- **Method:** binomial maximum likelihood over (b, c) on a grid: b from 0 to 0.050 in steps of 0.0001, c from 0.50
  to 0.75 in steps of 0.0025. Interval: 1,000 date-clustered bootstrap resamples (seed 20261029), 2.5-97.5%.
- **Sensitivities (reported, not used for the decision):** (S1) development 2015-2017; (S2) edges 2 ≤ |e| < 6;
  (S3) slope only, cap fixed at live; (S4) cap only, slope fixed at live.

## Check (2024-2026, per market)
- **Band table:** observed win rate vs live p vs fitted p, bands 2-2.5, 2.5-3, 3-4, 4-5, 5-6, 6+.
- **Likelihood:** mean log-likelihood per game of fitted vs live rule on 2024-26 (|e| ≥ 2), with a date-clustered
  bootstrap interval for the difference. The fitted rule **passes the check** if its 2024-26 log-likelihood is at
  least the live rule's (point estimate).

## Removal analysis (2024-2026 v1 plays)
- **Break prices:** for edges 2.5, 3, 3.5, 4, 4.5, 5, 6 (spreads) and 3, 3.5, 4, 4.5, 5, 6 (totals): the worst
  American price that clears +2% under the live rule and under the candidate rule. A play is removed exactly when
  its price lies between the two.
- **R, recorded prices (primary where it exists):** the Odds API change logs `research/market/data/quotes_<date>.csv.gz`
  on the 9 dates in 2024-26 (2023-11-11, 2024-01-13, 2024-03-02, 2024-11-09, 2025-01-11, 2025-03-01, 2025-11-08,
  2026-01-10, 2026-03-07). Per game: the DraftKings (live preferred book) first-observed complete market
  (`research/rotation_totals/build.first_observed`), with both spread prices at that snapshot
  (`research/persistent_disagreement/score.dk_spreads`). Edge = baseline forecast vs the DraftKings number; v1 play =
  edge ≥ threshold and live EV ≥ +2% at the DraftKings price of that side. Removed = candidate EV < +2%. Graded at
  the DraftKings number and price; CLV = DraftKings first-observed number to the ESPN close, in points toward the
  play. Caveat: forecasts are live-like (not the strict D−2 inputs of the rotation-totals study). Also reported:
  the price distribution across all books at those snapshots, and `bets/bets.csv` graded rows (expected none).
- **A, assumed prices (clearly labeled assumed):** all 2024-26 v1 opener plays (ESPN opener, edge ≥ threshold).
  Each play's price is drawn from the empirical DraftKings price distribution of its market (the price of the side,
  pooled over all 12 quote dates, 2022-26), assumed independent of edge and outcome. Expected removed plays per
  season = Σ P(price between the two break prices | edge); their expected record and ROI at those prices are the
  same weights applied to the play outcomes; CLV (opener to close, points toward the play) weighted the same way.
  Intervals: date-clustered bootstrap.
- If R has fewer than ~30 removed plays in total, it is called **too sparse** and A carries the count; R is still
  reported.

## Prior
The rule is about 1.5 percentage points generous for spreads at edges 2.5-5 (band table quoted in the request: 54.3%
at 2-2.5, 55.4% at 2.5-3, 56.4% at 3-4, 55.0% at 4-5), so the fitted spread rule should be roughly b ≈ 0.020,
c ≈ 0.565. The removed plays should be a few dozen a season, at −120 and worse.
**Note, from the request's own numbers (arithmetic, not data):** the quoted totals rates (55.3-56.2% at 2-4) are
*above* the live totals rule there (52.8-55.6%), so for totals the prior "1.5 below" does not hold as stated; if the
fitted totals rule is at or above the live rule over the play range, the candidate removes nothing and totals close.

## Kill rule and verdict (per market)
- **Closed** if any of:
  1. the fitted rule fails the 2024-26 likelihood check above;
  2. fewer than 20 plays a season affected (removed), averaged over 2024-26 (A count; R scaled to a season as a
     cross-check);
  3. the removed plays did not lose: ROI at their own price ≥ 0 (pooled 2024-26).
- **Mar 14 candidate** if none of these applies.
- **Jan 15 candidate** only if the removed plays lost clearly (95% date-clustered ROI interval entirely below 0)
  **and** there are 50+ of them a season.

## Outputs
`research/winprob/fit.py` (one script, writes `research/winprob/out/`), `research/winprob/LOG.md` with the fitted
rule, the removal table, every specification run (failures included) and the verdict.
