# Forward-test protocol, v1.1 (declared Oct 26, 2026, before the season's first games on Nov 1)

This file fixes how the 2026-27 live record is collected and judged. It is fingerprinted in `MODEL_FREEZE.md`.
Changing it creates v1.1 with a dated changelog entry. Results already computed are never recomputed under a later
version without saying so. The evaluation code is `audit/forward_eval.py`, written before any forward data existed
and fingerprinted with this file. Each read runs it unchanged.

## 1. What is being tested

**Subject:** the live card exactly as it runs, with the model files fingerprinted at commit `dfb4bc7` in
`MODEL_FREEZE.md`. Logging and reporting changes that do not change any prediction or selection may be added; each
is listed in `MODEL_FREEZE.md` with a check that the card output is identical. This is the primary configuration,
"live v1".

| Part | Live v1 configuration (from code) |
|---|---|
| Stage-1 ratings | `ratings.fit` on this season's box scores dated before the card day, as loaded at run time (`run_day.project`) |
| Preseason prior | KenPom + Barttorvik preseason, averaged (`backtest.preseason_prior`). Values dumped to `audit/out/frozen_preseason_prior_2027.csv` (fingerprinted) |
| KenPom | FanMatch for the card day once published (game-day morning), else KenPom's current ratings at run time |
| Barttorvik | newest non-empty time-machine file in the 7 days before the card day, else Barttorvik's live ratings file. In practice the live file, because dates requested before their file existed are cached empty |
| Referee crews | taken from ESPN's game page at each run. A game with no crew posted gets crew inputs 0 (average crew); crews enter only once ESPN posts them, usually near tip. Never filled from later observations |
| Market ratings | this season's closing lines from `lines/closing.csv` (our own feed), games before the card day; 0 until 30 lined games |
| Player availability | absences in each team's previous box score, plus the ESPN injury report adjustment. The injury report is live-only, with no historical analogue |
| Stage-2 weights | `data/projection.json` (fit 2013-2026 with crews and FanMatch present) |
| Opening week | first 7 days of the season: totals shifted so the day's average matches KenPom's (`run_day.opening_week_totals`) |
| Selection | each card run (every 10 minutes): for each game, the side and book with the best expected value at the book's price, across the 7 books (DraftKings, FanDuel, BetMGM, Caesars, Fanatics, bet365, theScore Bet; ties go to DraftKings). A BET needs spread edge >= 2.5 or total edge >= 3.0, and EV >= +2% at that price (`run_day.plays`) |
| Logging | the first run in which a side qualifies logs one signal (`bet_id` = date, game, market, side) at that book's number and price (`tracker.log`) |
| Stakes | card units scale with the live record (`tracker.status` multiplier). **This protocol evaluates flat 1 unit per signal, regardless of logged stake.** |

**No historical table corresponds exactly to live v1.** The closest is the live-like approximation
(`audit/b1_live_approx.py`): production weights, crews 0 and KenPom from the day before at prediction time. It still
differs in four ways:
- **Market ratings:** ESPN consensus closes in the backtest, our own feed live.
- **Inputs:** no injury report and no opening-week rule in the backtest.
- **Selection:** historically, the consensus opener with no prices and no EV rule; live, any book at any run, by EV.
- **Barttorvik:** time-machine files in the backtest, the live file live.

The original production backtest tables (referee crews and FanMatch present), `safe_lag1`, no-Barttorvik and
live-like are **research comparisons**, never interchangeable with live v1 results.

## 2. Cohorts

All three are reported side by side on the record page and in each read. Cohort v1 starts at the freeze,
**2026-10-26T19:20:50Z**. Signals logged earlier (8, of which 2 void) are the pre-freeze cohort, reported
separately and never pooled with v1.

- **A, primary:** every signal logged under live v1 for games dated 2026-11-01 through 2027-03-14, bet or not.
  Every A signal posts to Discord at log time.
- **B:** A signals whose logged quote was observed in the generating pull, at the named book, at the logged
  number, with status available and the feed's own timestamp no older than 600 seconds (`bets/signal_log.csv`).
  Signals without that record (logged before the logging change, or the feed gave no timestamp) are counted and
  excluded from B.
- **C:** accepted bets confirmed with book, placement time, line, odds and stake (`bets/accepted.csv`, from Pikkit
  or entered from the book's own history), matched to A by `bet_id`. For each match, report:
  - number deterioration;
  - price deterioration;
  - time from alert to placement.

  A feed quote is never proof of acceptance. A recorded stake is never evidence of a book's limit. The `placed`
  flag in the bet log is not a confirmation.

## 3. Units and handling rules

1. **Unit:** the signal. Spreads and totals are separate analyses. There is no combined figure.
2. **Duplicates:** a signal is logged once per `bet_id`. A later signal on the opposite side of the same game and
   market is a separate signal and is included, flagged, with a sensitivity read that excludes the later one.
   A spread and a total on the same game are two signals; dependence is handled by date clustering.
3. **Books and quotes:** only the logged book, number and price count. No later re-selection of book, quote,
   model variant or delay.
4. **Pushes:** stake returned (0 units), counted in the ROI denominator, excluded from win %.
5. **Voids:** listed and excluded from every metric.
6. **Unsettled:** listed and excluded until settled.
7. **Missing close:** excluded from line value only, and counted.
8. **Prices:** the logged price, or -110 where none was logged, labelled "assumed" with a count.
9. **ROI:** units divided by settled signals, flat 1 unit each.

## 4. Closing line and line value

- **Source:** `lines/closing.csv`, the last pre-tip observation per game and book. The Odds API and SGO are merged;
  SGO ends Nov 25, after which The Odds API alone.
- **Eligible:** the 7 books above. A book's close counts only if it was observed (`pulled_at`) within 60 minutes
  before the scheduled start. Older ones are excluded and counted.
- **Consensus close:** the median across eligible books, or the single book if only one. Spreads use the median
  home spread converted to the signal's side; totals use the median total.
- **Line value:** points the consensus close moved toward the signal's side from the logged number:
  - spreads: logged spread minus closing spread, from the signal's side;
  - overs: close minus logged;
  - unders: logged minus close.

  Reported as a mean with its distribution, spreads and totals separately. A point is not treated as equally
  valuable across markets, and points are never converted to money.
- **Price-aware comparison:** where both sides' prices exist at log time (the generating pull) and at the same
  book's close, and the closing number equals the logged number, compute:
  - the proportional no-vig probability of our side at log time and at the close;
  - the difference between them.

  Signals without that are not converted.
- **Separation:** line value and realized profit are reported separately; neither proves the other.

## 5. Quote logging and the delay test

**Logging:** each card pull logs every quote at the 7 books for games inside a watch window, both sides of spreads
and totals. A game is inside its window when a signal was logged, or a book's quote was first seen, in the last 65
minutes. Each row carries:
- event id, book, market, side, line, price;
- the feed's own timestamp and the quote's age;
- our observation time and the quote's status (available, unavailable, stale).

Each poll attempt is logged with its status, error, cost and gap (`cbb/quotelog.py`). Each signal records its
generation time, input cutoffs, the quote it was logged at, and its alert times. "First seen" is our first
observation, not a book's true opener.

**Targeted polling:** every 3 minutes (`.github/workflows/quotes.yml`, `cbb/poll_targets.py`). One Odds API call for
spreads and totals costs 2 credits, whatever the number of games, and runs only when some game is inside a window.
- **Odds API cost:**
  - targeted polling: at most 480 calls a day, so at most 960 credits a day and about 29,800 a month;
  - card runs: 3 credits every 10 minutes, about 13,400 a month;
  - total: at most about 43,000 a month, against a monthly allowance of about 100,000 (95,616 remained on
    Oct 26; confirm the plan on the account page).
- **SGO is not used for targeted polling:**
  - it costs 1 entity per event returned (observed);
  - the card runs alone would reach the code's 95% stop within days in season;
  - the allowance is shared with the NFL model;
  - the subscription ends Nov 25;
  - its per-minute limit is not documented in this repository.

**Delay test:** each A signal is re-priced at the first observed quote at its book and side at least 5, 15, 30 and
60 minutes after its alert (the ntfy send time, else the logged time). This is done regardless of remaining edge,
and whether the +2% EV rule would still accept the new quote is reported separately. Each delay reports, as
separate counts:
- **filled:** observed available, with the elapsed time;
- **unavailable or stale** at that observation;
- **no observation.**

A quote is never assumed to have stayed available across a gap, a suspension or a missing observation.

Secondary (v1.1): at each delay, whether any of the 7 books was observed available at the logged number or better, using each book's own first observation after that delay. Reported as a share, with "no book at logged number" and "no observation" counted separately.

**If the logging change is not approved and running before a read:** delay results come only from card pulls (about
10 minutes apart) and are labelled with actual elapsed observation time. No 5-minute claim is made.

## 6. Pauses, reviews and changes

Four separate things:
1. **Data-integrity or operational failure:** a feed down, a logging error, a missed run. Fixed as soon as found
   and recorded in `MODEL_FREEZE.md`. Affected signals are flagged, never deleted or re-generated.
2. **Pausing wagering (cohort C):** the existing tripwire (line value under +0.4 after 150 settled signals: review;
   under 0: pause) may pause real bets and opens a review. It never changes the model.
3. **Signal logging (cohort A):** continues through any pause.
4. **Model changes:** only at a checkpoint, with Chad's approval, a backtest, and a Discord announcement the day
   they go live. A change starts a new versioned cohort (v2). v1 signals are never overwritten or re-predicted, and
   versions are never pooled without saying so.

## 7. Statistical evaluation

**Endpoints:** two primary endpoints per market, both on cohort A:
- mean line value against the consensus close;
- ROI at the logged price.

Secondary, descriptive only: the same for cohort C at actual prices, alert-to-bet deterioration, ROI under each
delay, and the price-aware comparison.

**Uncertainty:** a percentile bootstrap over game dates (5,000 draws, fixed seed in `forward_eval.py`). Date
clustering does not remove the selection effects in the historical design.

**Reads:**
- **Checkpoints:** January 15, 2027 and the final read after 2027-03-14.
- **Interim:** a market is read at a checkpoint only if it has 600 or more decided signals; otherwise that read is
  descriptive only.
- **Interim conclusion:** "supported" only if both endpoints reach z >= 3.0 (a Haybittle-Peto boundary, spending
  almost no error). Otherwise "continue". No other early conclusion, and no repeated looks at ordinary 95%
  intervals.
- **Final read:** each market's verdict, with α one-sided 0.025 split across 2 markets x 2 endpoints:
  - **supported:** both endpoints z >= 2.50;
  - **contradicted:** the 95% upper bound of either endpoint below 0;
  - **inconclusive:** anything else.

  "Inconclusive" is an acceptable, predeclared outcome.

**Power at -110:**
- **Win-rate SE:** sqrt(0.524 x 0.476 / n). At 600 decided signals that is 2.04 points.
- **Expected z** (gap from 52.4% over that SE): 600 signals put a true 57% about 2.3 SE from break-even. A true 54%
  is about 0.8 SE away and 55% about 1.3, so 600 signals cannot distinguish them.
- **Same-day dependence:** in the historical opener cohorts the design effect was 0.9-1.2 (median 1.0), so the
  dependence-aware SE is 1.9-2.2 points. Live clustering may differ and is re-measured at each read.
- **ROI SE** at 600 signals is about 3.9 points.
- 600 signals is the floor for an interim read. The full regular season is the final read.

**Hypotheses, not expectations:** historical opener results (+5% to +10% ROI, about +1 point of line value) come
from seasons that were reused to design the model.

## 8. Reporting

At each read, `python -m audit.forward_eval --through <date>` is run unchanged. Its output goes into the helpers'
doc and to Chad with:
- cohorts A, B and C;
- pre-freeze signals separately;
- every count: selections, wins, losses, pushes, voids, unsettled, missing closes, assumed prices, and delay-test
  outcomes.

## Changelog

- v1.0 (2026-10-26): declared.
- v1.1 (2026-10-26, before any forward data): adds the secondary any-book delay measure (section 5), from the helpers' response to the audit.
