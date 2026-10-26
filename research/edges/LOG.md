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

## 2026-10-26: follow-up, spread edges of 5+ points (pre-registered before running)

Plays: the frozen rule's spread plays against the opener, edge 5+ (comparison bands 2.5-3.5 and 3.5-5), from idea 2's
construction.

Data-quality checks:
- **Source of the opener:** the 2014-17 "Opening" pseudo-book; 2024 a multi-book median; 2025-26 a single book.
  How many books stood behind each opener (2024).
- **Orientation:** whether the opener was checked against its own moneylines, corrected, or in the uncheckable
  residue.
- **Opener-to-close move:** the share of 5+ plays whose consensus close moved 5+ points from the opener. A huge
  move suggests a stale or wrong opener, or real news.
- **Same plays at the close:** win % graded at the closing number, and the edge re-measured against the close. If
  the model still has 5+ points against the close and wins, the opener was not the whole story.

Robustness, recomputed with each exclusion:
- excluding uncheckable openers;
- excluding opener-to-close moves of 5+;
- excluding November;
- by season.

Calibration:
- win % by edge band (2.5-3.5, 3.5-5, 5-7, 7+) against the live card's win-chance table (0.5 + 0.0255 x edge,
  capped at 0.58);
- a logistic fit of win on edge, on development only, checked on the holdout.
- **Run 1 (`out/e5_run.txt`):** the largest edges are home/away swaps between the odds data and the game data.
  The model's margin is about the same size as the line with the opposite sign, and they grade as easy "wins".
- **Added diagnostic (declared after seeing run 1, so it is a data check, not a pre-registered test):** flag a
  game as "line likely swapped" when both the model and KenPom disagree with the opener's favourite and each is
  10+ points from the opener (|model + open| >= 10 and |KenPom + open| >= 10). The rule uses only pregame
  information; no result or close. Then recount the headline opener results without the flagged games.
- **Run 2 (`out/e5b_swaps.txt`):**
  - 67 spread plays flagged as likely swapped; 88% at neutral sites; the result sided with the model in 55 of 67.
  - All 67 are in the 7+ edge band, and they won 90%.
  - They were saved in `out/e5_swapped_games.csv` and excluded from runs 3 and 4.
- **Run 3 (`out/e5c_clean.txt`):** the 5+ checks without the swaps.
- **Run 4 (`out/e5d_neutral.txt`, declared after run 3):** a looser check for smaller swaps. Neutral-site plays
  where the model and KenPom both favour the other team are 16% of neutral plays vs 8% at home courts; excluding
  them, neutral sites still read 60.0% / 59.6%.

## 2026-10-26: execution timing, which picks must be taken now (pre-registered before running)

- **Plays:** the frozen rule at the opener (idea 2's construction), with the likely swapped games excluded
  (`evaluate.swapped` rule). Seasons 2014-17 and 2024 are development; 2025-26 is the holdout.
- **Outcome classes, from the opener-to-close move toward the bet (line value, lv):**
  - "chased" if lv >= 1;
  - "stable" if -1 < lv < 1;
  - "faded" if lv <= -1.
- **Per class:** win % graded at the opener vs at the close. The difference is the value of acting at once.
- **Predicting "chased" from what is known when the pick is made:**
  - edge size;
  - market;
  - month;
  - neutral site;
  - power-conference teams in the game;
  - opening spread size;
  - KenPom's agreement with the model's side against the opener (KenPom's edge on the same side, points);
  - whether a total is an over.

  Logistic regression fitted on development and scored on the holdout by AUC. Then: holdout picks in the top and
  bottom thirds of predicted "chased" probability, graded at the opener vs at the close.
- **Question answered:** which picks lose their value by waiting, and whether that can be told in advance.
  "Never realistically available" needs timestamps (live logs from Nov 1, or the historical snapshot sample).
- **Run 1 (`out/e6_run.txt`), reported as is.** The "chased" model's development AUC was 0.625 and its holdout
  AUC 0.493, so it is not predictable.
