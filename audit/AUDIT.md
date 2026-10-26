# Backtest audit: is the opening-line edge real, and was it bettable? (Oct 26, 2026)

**Verdict: promising but unverified.**

- **Statistical / predictive validity: promising, not established.** Every reported row reproduces exactly. The
  edge against the opener survives every information-timing restriction tested: with each input restricted to
  what was public a day earlier, opener win rates are 54.9-57.7% and the 95% intervals (clustered by date) stay
  above 52.4%. But every evaluated season helped shape the model, thresholds and data rules, so there is no
  untouched holdout. The true out-of-sample edge is unknown and smaller than reported by an unknown amount.
- **Practical bettability: unverified.** The historical "opener" is not a timestamped, priced quote at a named,
  accessible book. 2015-17 is an unnamed ESPN pseudo-book, 2024 a median across books, and there are no spread or
  total prices anywhere, so -110 is assumed. Whether a pick could have existed while that number was up, at what
  price and for what stake, cannot be established from the historical data. Profit is fragile: one point worse
  than the opener takes ROI from about +10% to roughly 0-6%.
- **"Being early matters" is not established.** The same picks do grade about 4 points of win rate better at the
  opener than at the close. But the timing audit cannot show the picks could have existed while the opener was
  available.

All scripts are in `audit/` and are read-only: the production model, `cbb/output/` and the bet log are untouched.
Model version audited: commit `dfb4bc7` (frozen; see `MODEL_FREEZE.md`). Stage-1 file:
`cbb/output/backtest_2013_2026.csv` (blended KenPom+Barttorvik prior).

## Reported vs reproduced vs adjusted

Plays include pushes; win % excludes them. ROI uses flat 1-unit stakes at an assumed -110: no historical price
exists for any spread or total. "Conservative" = the `safe_lag1` variant (below). CIs are 95% percentile
bootstraps over game dates.

| Row | Reported | Reproduced (W-L-P) | Reproduced ROI @-110 [CI] | Conservative win % [CI] | Conservative ROI @-110 [CI] | Conservative, 1 pt worse | Same plays at close (conservative) |
|---|---|---|---|---|---|---|---|
| Spreads vs opener 2024-26 | 57.8%, 2,221 | 57.77% (1283-938-8) | +10.3% [6.5, 13.9] | 57.5% [55.4, 59.4] | +9.7% [5.8, 13.3] | +3.1% | 53.7% (+2.5% ROI) |
| Totals vs opener 2024-26 | 57.4%, 4,241 | 57.39% (2434-1807-15) | +9.5% [6.5, 12.6] | 54.9% [53.2, 56.6] | +4.8% [1.6, 8.0] | -0.1% | 50.5% (-3.5%) |
| Spreads vs opener 2015-17 | 57.6%, 1,935 | 57.57% (1114-821-46) | +9.7% [5.7, 13.7] | 56.3% [54.1, 58.6] | +7.2% [3.1, 11.6] | -0.2% | 51.7% (-1.2%) |
| Totals vs opener 2015-17 | 58.4%, 3,763 | 58.36% (2196-1567-60) | +11.2% [7.6, 14.5] | 57.7% [55.8, 59.6] | +10.1% [6.5, 13.7] | +6.0% | 54.6% (+4.1%) |
| Spreads vs close 2020-26 | 52.4%, 5,520 | 52.43% (2894-2626-61) | +0.1% | n/a | n/a | n/a | n/a |
| Totals vs close 2020-26 | 53.1%, 11,219 | 53.14% (5962-5257-57) | +1.5% | n/a | n/a | n/a | n/a |
| Spreads vs close 2024-26 | 52.2%, 2,569 | 52.20% (1341-1228-7) | -0.4% | n/a | n/a | n/a | n/a |
| Totals vs close 2024-26 | 51.9%, 4,729 | 51.91% (2455-2274-10) | -0.9% | n/a | n/a | n/a | n/a |

Sources: `audit/a1_reproduce.py` (bet-level file `audit/out/bets_reported.csv`), `audit/a6_adjusted.py`
(`audit/out/adjusted_summary.csv`).

## Most material problems, ranked by impact on the conclusion

1. **The opener is not an executable quote, and there is no price or time** (`cbb/lines_hist.py`).
   - **2015-17:** every opener comes from ESPN's "Opening" pseudo-book. No book is named and there is no
     timestamp; its moneyline matches Pinnacle's in a spot check, but that is inference.
   - **2024:** the median of up to ~10 books' openers (Unibet and Caesars state books lead). A median is not
     a bettable quote.
   - **2025:** ESPN BET alone. **2026:** DraftKings (4,766 games) or ESPN BET (1,257).
   - **Prices:** no spread or total price is stored in any season, only moneylines.
   - **Consequence:** whether the number was available, when, at what price and for what size cannot be
     reconstructed.
2. **No untouched holdout; heavy reuse of the evaluation seasons.** The model was built Oct 25-26, 2026. The
   first full backtest of the untuned model, commit `aa5cfae`, reports "no edge yet". The edge appeared after
   decisions judged on these same seasons:
   - rating settings grid-tuned on 2014-19, by prediction error;
   - second-stage inputs added: KenPom, Barttorvik, Four Factors, 3-point luck, market ratings, altitude, referees;
   - book exclusions decided after seeing fake edges (`NOT_BOOKS`);
   - thresholds set Oct 26 from the opener seasons (`cbb/run_day.py:39`);
   - the blended prior adopted Oct 26 on the opener seasons;
   - about 40 further ideas tested and dropped on the same data.

   Stage-2 weights are fit walk-forward by season (verified, `projection.walk_forward`), but the model's form was
   chosen with full sight of 2015-17 and 2024-26. Every historical prediction was reconstructed in Oct 2026;
   none was archived in real time.
3. **Referee crews leak into totals** (`context.referees`). Each game's actual crew is used. Crews are not known
   when openers post. Removing them takes 2024-26 opener totals from 57.4% to 55.9% (ROI +9.5% to +6.6%) and
   2015-17 from 58.4% to 57.9%. Spreads are unaffected.
4. **The profit is mostly the opening number.**
   - Graded at the close, the same opener-selected plays win 53.2-55.1% (production) or 50.5-54.6%
     (conservative), against 52.4% break-even at -110.
   - In the conservative version, one point worse than the opener erases spreads 2015-17 (-0.2%) and totals
     2024-26 (-0.1%). Spreads 2024-26 keep +3.1%.
   - Price matters too: -115 instead of -110 costs about 2.2 ROI points.
5. **The opener cleaning uses the close.** `consensus()` drops an opener when it sits closer to the mirrored
   close than to the close itself: 36-93 games a season. This uses future information. The count is small next to
   the play counts, and its direction is unknown.
6. **Small timing leaks that tested as immaterial:**
   - KenPom FanMatch (published game-day morning) replaced with KenPom's archive from the day before;
   - Barttorvik one file earlier;
   - market ratings from closes before the day before;
   - the stage-1 ratings cutoff one day earlier (`audit/stage1_lag.py`);
   - `season_avg_total` includes earlier same-day rows (coefficient -0.008).

   Each moved win rates by 0-1 point. Archive check: a day's games first appear in KenPom's archive the next day,
   so `archive(d)` holds games through d-1.
7. **Concentration and correlation.**
   - 1,285 opener games carry both a spread and a total play.
   - The best 10% of dates carry most of the units (for example spreads 2015-17: 172 of 192 units). Results are
     heavy-tailed by date.
   - Months vary widely: totals 2024-26 made 26 units in January and 123 in February.
   - Plays where the line moved 4+ points between open and close are 5-20% of plays but win 62-71% at the opener.
     Without them, the opener record is still 56.2-57.5%.

## Information timing (step 2)

| Input | What the backtest uses | When it was public | Status |
|---|---|---|---|
| Stage-1 team ratings | games strictly before the game date | after each team's previous game | verified in code; one-day-earlier cutoff tested: small change |
| Preseason prior | KenPom preseason archive + Barttorvik earliest time-machine file | preseason | KenPom: published preseason (verified by API flag). Barttorvik time machine may be reconstructed retrospectively: unverified |
| KenPom (stage 2) | FanMatch for the game date | game-day morning, usually after the opener | verified; replaced with the previous day's archive: negligible change |
| Barttorvik (stage 2) | latest file before the game date | that file's date | file contents may be retrospective reconstructions: unverified; one file earlier: negligible |
| Four Factors | from stage-1 fit, games before the date | as stage 1 | verified |
| Missing players | absences in the team's previous game (box score) | after the previous game | verified (`players.availability`); back-to-back days are rare |
| Market ratings | earlier dates' consensus closes | after those games | verified; shifting a day: negligible |
| Referee crews | the game's actual crew | around game day | **leak for openers** (problem 3) |
| Rest, altitude, team home edge | schedule; earlier seasons only | in advance | verified |
| Season scoring level | earlier rows, including same-day rows | partly after | minor; coefficient ~0 |
| Stage-2 weights | walk-forward by season | n/a | verified; feature set chosen in-sample (problem 2) |
| Opener and close | ESPN odds feed, pulled Oct 2026 | unknown time | no timestamps; possible later revision by ESPN: unverifiable |

The conservative `safe_lag1` variant combines every restriction: no referees, KenPom from the day before,
Barttorvik one file earlier, market ratings before the day before, and ratings from games before the day before
(`audit/a2_timing.py`, `audit/stage1_lag.py`). Because ESPN openers carry no time, these tests bound the leakage;
they do not prove the picks existed while each opener was posted. That is impossible to verify from the
historical data.

## Same plays, opener vs close (step 4)

Line value = (consensus close - consensus opener) in our side's favor, in points; positive means the market moved
toward the pick. It measures actual movement, not model disagreement.

| Opener-selected cohort | Win % at opener | Same plays at close | Moved our way / unchanged / against | Move p10 / p50 / p90 |
|---|---|---|---|---|
| Spreads 2015-17 | 57.6% | 53.2% | 76% / 9% / 14% | -0.5 / +1.0 / +3.0 |
| Spreads 2024-26 | 57.8% | 53.8% | 62% / 22% / 16% | -1.0 / +1.0 / +3.0 |
| Totals 2015-17 | 58.4% | 55.1% | 64% / 12% / 23% | -1.5 / +1.0 / +4.0 |
| Totals 2024-26 | 57.4% | 53.5% | 65% / 14% / 21% | -1.0 / +1.0 / +5.0 |

- **Key numbers:** college margins land on 3 through 6 at a fairly flat 5.3-6.3% each, so there is no dominant
  key number. Moves were re-graded on actual final margins, not converted at a fixed value per point.
- **Win rate at the close by move size:** plays the market moved 2+ points our way still win only 47-57% at the
  close. Most of their value was the number.
- **Close-selected plays:** the "vs close" rows in the reported table are a separate strategy, picks re-selected
  against the close. They are near break-even: -0.9% to +1.5% ROI.

## Validation and uncertainty (step 5)

- **No untouched holdout exists** (problem 2). The 2026-27 live season is the first.
- **Per season, opener:** spreads 56.6-58.8% every season; totals 56.4-60.5%. Results are consistent across all 6
  opener seasons, but those seasons were all used to design the model.
- **By edge size:** win rate rises loosely with edge. Spreads at 6+ points win 67-71% on only 51-84 plays.
- **Intervals:** clustered by game date, so spread and total plays on the same game, and same-day market errors,
  resample together.
- **Baselines against the same openers and thresholds:**

| Baseline | Spreads 15-17 / 24-26 | Totals 15-17 / 24-26 |
|---|---|---|
| KenPom FanMatch alone | 50.2% / 49.8% | 51.5% / 50.6% |
| Barttorvik alone (no home edge in our setup) | 51.4% / 49.7% | 51.2% / 49.8% |
| Market ratings from earlier closes (10+ games) | 52.7% / 51.7% | n/a |
| Our stage-1 ratings alone | 56.6% / 55.4% | 57.3% / 53.3% |
| Final model | 57.6% / 57.8% | 58.4% / 57.4% |

Public ratings and market-only ratings do not beat these openers. The edge, whatever it is, comes from our own
ratings and how they are combined.

## Betting economics (step 6)

Flat 1 unit per play, at an assumed -110 because no recorded prices exist. All price and slippage figures below
are hypothetical sensitivity tests, not observed replays.

- **ROI at the opener:** production +9.5% to +11.2%; conservative +4.8% to +10.1%.
- **At -115:** production +7.3% to +9.0%.
- **One point worse than the opener:** production +3.3% to +6.4%; conservative -0.2% to +6.0%.
- **1.5 points worse:** production spreads about -0.4%.
- **Max drawdown (production):** 13-34 units per cohort.
- **Execution after a delay:** testing at 5, 15, 30 or 60 minutes after the opener needs a quote history. None
  exists for 2014-2026, so this is **unverified**.
- **Limits and stake size:** no historical evidence exists. None is assumed here.

## What cannot be established from the available evidence

- When each historical opener was posted. For 2015-17, which book posted it.
- Whether any pick could have existed while its opener was still available, and at what delay.
- The price on any historical spread or total, and the stake any book would have accepted.
- Whether ESPN, KenPom or Barttorvik revised or backfilled historical values before they were pulled in Oct 2026.
  KenPom's archive behaves like as-of snapshots, which is consistent but not proof.
- A true out-of-sample edge: no season was left unused during design.

## Forward test (the only way to settle it)

1. **Frozen model and rules:** commit `dfb4bc7`, file fingerprints in `MODEL_FREEZE.md`, announced on the Discord
   record, until the Jan 15, 2027 checkpoint. Changes only between checkpoints, with approval, a backtest and a
   public announcement.
2. **Timestamped predictions:** every card run logs plays to `bets/bets.csv` with `logged_at`, the book, number
   and price. Each play posts to Discord at log time. The bet log is OpenTimestamps-stamped after every change.
3. **Logged quotes:** `lines/moves.csv` records every change in number or price per game and book, polled every
   10 minutes; `lines/openers.csv` keeps each book's first-seen quote with time; `lines/closing.csv` the last.
   - **Delay test:** re-price each play at the first logged quote at least 5, 15, 30 and 60 minutes after it was
     logged.
   - **Placed bets:** Pikkit holds the actual price, time and stake.
4. **Predeclared evaluation:**
   - **Interim read Jan 15, 2027; final read at the end of the regular season or 600 logged plays, whichever is
     later.** No model changes are made because of interim results.
   - **Primary:** mean line value of logged plays against the consensus close of the tracked books, at the
     logged number; and ROI at the logged price.
   - **Secondary:** the same for placed bets at actual prices; the gap between alerted and bet numbers; ROI under
     each delay.
   - **Report with intervals clustered by date.** All logged plays count, whether or not they were bet; voids
     are listed and excluded.
5. **Expectations stated in advance, from the conservative variant:**
   - opener win rate about 55-57%;
   - line value about +1.0 point;
   - ROI at -110 about +5% to +10% at the logged number;
   - near break-even if graded at the close.

   Live line value under +0.4 after 150 plays triggers review (existing tripwire). Under 0 means pause.
