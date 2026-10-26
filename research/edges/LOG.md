# Edge search log

## 2026-10-26: pre-registration (written before any of these scripts was run)

Shared for every idea:
- **Model:** the frozen model's live-like walk-forward numbers (`audit/out/wf_live_approx.pkl`: crews 0, KenPom
  from the day before).
- **Openers:** oriented by their own moneylines (`lines_hist` rule "flip").
- **Seasons:** development 2014-2024. Holdout 2025-2026, read once per idea after the development run, with the
  specification unchanged.
- **Uncertainty:** date-clustered bootstrap, 5,000 draws, seed 20261026.

### Idea 1: moneylines at real prices
- **Prices:** ESPN per-book moneylines.
  - Closing moneylines from every season's file.
  - Opening moneylines 2024-26 from `research/../audit/out/espn_open_meta_<season>.csv`.
  - A book's pair is dropped if either price is missing or 0, or its implied probabilities sum outside 1.00-1.12.
- **Model win probability:** p_home = Phi(final_margin / 11), the live card's own mapping (`run_day`), frozen.
- **Rule:** for each game, each side at the best price across books. Bet the side with the higher EV when
  EV >= +5% (primary). +2% and +10% are reported as descriptive only.
- **Sensitivity:** the median price across books instead of the best.
- **Outcomes:** win %, ROI at the actual price, and average price. Eras: closes (all seasons) and openers
  (2024-26).
- **Calibration (development only):** log loss of the model vs the de-vigged market (proportional), and a logistic
  regression of the outcome on logit(p_model) and logit(p_market).

### Idea 2: where the opener edge concentrates
- **Plays:** the frozen rule against the opener (spread edge 2.5+, total edge 3+), graded on the opener, win %
  and ROI at an assumed -110 (opener prices unknown). Opener seasons: development 2014-2017 and 2024; holdout
  2025-2026.
- **Segments (fixed list):**
  - month (Nov, Dec, Jan, Feb, Mar+);
  - conference tier (game between two power-conference teams / one / none; conferences as listed today in
    `data/teams.csv`, an approximation for older seasons);
  - opening spread size (0-4.5, 5-9.5, 10-14.5, 15+);
  - opening total (<135, 135-144.5, 145-154.5, 155+);
  - site (neutral / not);
  - side (favourite vs underdog for spreads, over vs under for totals);
  - edge size (2.5-3.5 / 3.5-5 / 5+ spreads; 3-4 / 4-6 / 6+ totals).
- **Flag:** a segment with 100+ development plays whose win % differs from the market's overall development win % by
  2+ date-clustered SEs.
- **Report:** how many flags would be expected by chance. Each flag is then checked once on the holdout.

### Idea 4: totals matchup features
- **Features:** season-to-date before each game, from team box scores, shrunk to the league average with 5 games
  of prior.
  - **pace mismatch:** |tempo_home - tempo_away| (possessions per game);
  - **three-point interplay:** (home 3PA rate - league) x (away 3PA rate allowed - league) + the same with home
    and away swapped.
- **Walk-forward fit:** for each season s, fit OLS on seasons before s (2014 onwards, every game with a close):
  (actual total - closing total) on (model total - closing total), pace mismatch and three-point interplay. The
  adjusted model total = model total + the fitted feature terms.
- **Test:** totals against the opener (edge 3+) with the adjusted vs the frozen model total. Development seasons
  2015-2017 and 2024 (2014 has no earlier season to fit on); holdout 2025-2026.
- **Report:** coefficient z-scores per fit, and win % and ROI (assumed -110) for both versions.

## 2026-10-26: idea 1, run 1 (development and holdout printed together)

- **Bug:** the "median price" sensitivity took the median of American odds directly. Across +-100 that gives
  values near 0 and impossible payouts (+29% to +62% ROI). The market probability in the calibration used the
  same median, so the calibration was wrong as well.
- **Unaffected:** the primary rule (best price, EV >= 5%) does not use the median.
- **Fix (a correction, not a new specification):** the median is taken in implied-probability space, then
  converted back.
- **Holdout status:** run 1 also printed the holdout rows. The holdout read for idea 1 is therefore run 1's
  primary rows. Run 2 changes only the median-based rows and the calibration.
- **Run 2 (reported, `out/e1_run.txt`):**
  - Primary rows unchanged from run 1.
  - Median-price rows now sensible.
  - Calibration corrected: the model and the de-vigged market have nearly equal log loss, and both carry
    information (z 15 and 17 at the close).

## 2026-10-26: idea 2, runs

- **Run 1:** crashed building the plays (a column-length error in `common.opener_plays`); no results produced.
- **Run 2:** the reported output (`out/e2_run.txt`). 38 segments tested and 3 flagged, against about 1.7 expected
  by chance. Holdout read once.

## 2026-10-26: idea 4, run 1

Run 1 is the reported output (`out/e4_run.txt`). The holdout was read once in the same run, which printed
development and holdout together, as for idea 1.
