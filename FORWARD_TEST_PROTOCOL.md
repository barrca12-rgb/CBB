# Forward-test protocol, v2.2 (declared Oct 26, 2026, before the season's first games on Nov 1; v2.1 Oct 28; v2.2 Oct 29)

This file fixes how the 2026-27 live record is collected and judged. It is fingerprinted in `MODEL_FREEZE.md`
together with its evaluation code, `audit/forward_eval.py`, and that code's tests, `audit/test_forward_eval.py`.
Both were written before any forward data existed. Every read runs the evaluation code unchanged. A change to
either file is a new protocol version, with a dated changelog entry, made before the data it would affect. Results
already computed are never recomputed under a later version without saying so. v2.0 replaces v1.1; no forward data
existed under v1.1.

**Headline until the final read:** promising historical results; live profitability and execution remain
unverified.

## 1. What is being tested: model v1

**Subject:** the live card as it runs on the code and data fingerprinted in `MODEL_FREEZE.md` (freeze commit
`dfb4bc7`, committed 2026-10-26T19:20:50Z). This is "model v1".

Logging and reporting changes that leave every prediction and selection unchanged may be added. Each one is listed in
`MODEL_FREEZE.md` with a check that the card and the bet log are byte-identical with and without it.

| Part | Model v1 configuration (from code) |
|---|---|
| Stage-1 ratings | `ratings.fit` on this season's box scores dated before the card day, loaded at run time (`run_day.project`) |
| Preseason prior | KenPom and Barttorvik preseason, averaged (`backtest.preseason_prior`), dumped to `audit/out/frozen_preseason_prior_2027.csv` |
| KenPom | FanMatch for the card day once published, else KenPom's current ratings at run time |
| Barttorvik | the newest non-empty time-machine file in the 7 days before the card day, else the live ratings file |
| Referee crews | from ESPN's game page at each run; a game with no crew posted gets crew inputs 0. Never filled from later observations |
| Market ratings | this season's closes from `lines/closing.csv`, games before the card day; 0 until 30 lined games |
| Injuries | absences in each team's previous box score, plus the injury report from the source named in `injuries/sources/choice.json`. With no such file (the state at the freeze) that source is ESPN. Writing `choice.json` is a model change (section 8). `injury_sources.py` only recommends a switch |
| Stage-2 weights | `data/projection.json` |
| Opening week | the season's first 7 days: totals shifted to KenPom's average scoring level (`run_day.opening_week_totals`) |
| Line feeds | SportsGameOdds (`odds.py`; every third run, stops at 95% of its monthly allowance, subscription ends Nov 25) and The Odds API (`odds_api.py`; every run, `ODDS_API_EVERY_RUN=1`). Both ignore quotes untouched for 12 hours. After SGO ends or stops, The Odds API alone |
| Selection | each card run: for each game, the side and book with the best EV at the book's price across the 7 books (DraftKings, FanDuel, BetMGM, Caesars, Fanatics, bet365, theScore Bet; ties go to DraftKings). A BET needs spread edge >= 2.5 or total edge >= 3.0, and EV >= +2% (`run_day.plays`; win chance from `run_day.WIN_PROB`) |
| Logging | the first run in which a side qualifies logs one signal (`bet_id` = date, game, market, side) at that book's number and price (`tracker.log`). A logged signal is never re-priced, re-selected or deleted |
| Stakes | the card's units follow the live record (`tracker.status`). This protocol evaluates flat 1 unit per signal. Staking is not part of the test and is not changed by it |

**Historical comparisons:** the production backtest, `safe_lag1`, no-Barttorvik and live-like tables are research
comparisons, never interchangeable with model v1 results. No historical table corresponds exactly to model v1:
- **Market ratings:** ESPN consensus closes in the backtest, our own feed live.
- **Inputs:** the backtest has no injury report and no opening-week rule.
- **Selection:** consensus openers without prices or EV in the backtest, any book at any run by EV live.
- **Barttorvik:** time-machine files in the backtest.

Historically, spreads at the opener were 56-58.4% across filtering variants (2015-17 and 2024-26). That is a
**historical spread filtering-sensitivity range**. It is not a confidence interval, an expected live win rate, or a
totals result.

## 2. Signals, cohorts and versions

**Model v1 signals:** rows in `bets/bets.csv` logged at or after 2026-10-26T19:20:50Z, for games dated 2026-11-01
through 2027-03-14. Signals logged earlier (8, of which 2 are void) are the pre-freeze cohort, reported separately
and never pooled.

- **A, every signal (primary):** every model v1 signal, bet or not. Each one posts to the Discord record channel
  when it is logged.
- **A with a recorded price:** A signals whose bet-log row carries the price of the logged quote. Only these enter
  profitability (section 4).
- **B, fresh observed quote:** A signals whose own quote was observed in the pull that generated them
  (`bets/signal_log.csv`), with all of the following:
  - at the logged book and number;
  - status available;
  - a feed timestamp at most 600 seconds old (up to 60 seconds ahead of our clock is accepted).

  Signals without that record are counted and excluded from B.
- **C, accepted bets:** bets confirmed with book, placement time, line, odds and stake (`bets/accepted.csv`, from
  Pikkit or the book's own history), matched to A by `bet_id`. C is graded at the accepted line and price. For each
  bet, report:
  - number deterioration;
  - price deterioration;
  - time from alert to placement.

  A feed quote is never proof of acceptance, and the bet log's `placed` flag is not a confirmation.

**Versions and the shadow strategy:** if production switches to a model v2 at a checkpoint (section 8), model v1
continues as a shadow strategy through 2027-03-14:
- It runs as the frozen code with alerts and posting switched off.
- It writes to its own log, `bets/shadow_v1/bets.csv`.
- The switch time is recorded in `forward_eval.VERSIONS`.

v1 signals after the switch come only from the shadow log, and v2 signals are never v1 signals. Nothing is
regenerated retrospectively. If shadow operation is impossible, v1 is labelled "interrupted at <time>" and evaluated
on its signals up to then. The evaluation implements this (`load_signals`) and the tests check it.

**Immutability:** at each read, the evaluation checks every committed version of `bets/bets.csv`. No model v1 signal
may have changed a defining field (id, game, market, side, teams, number, price, book, edge, prediction, logged time)
or disappeared. Settlement and status columns may change.

The external record is separate:
- **Discord:** every signal is posted at log time.
- **OpenTimestamps:** the bet log is stamped on every run (`bets/bets.csv.ots`).

## 3. Denominators and handling rules

| Item | Rule |
|---|---|
| Unit | the signal. Spreads and totals are analysed separately; there is no combined figure |
| Decided | settled W or L |
| Push | stake returned: 0 units. In the ROI denominator, excluded from win % and from price coverage |
| Void (cancelled, postponed and voided by the tracker) | listed by id, excluded from every metric |
| Unsettled | listed, excluded until settled. Still unsettled at the final read: excluded and counted |
| Missing close | excluded from line value only, counted, and the coverage reported |
| Missing price | the signal stays in A and in every count. It is excluded from confirmatory ROI and counted (section 4) |
| Duplicates | one signal per `bet_id`. A later opposite-side signal on the same game and market is included and flagged, with a sensitivity read without it. A spread and a total on one game are two signals; date clustering handles the dependence |
| Books and quotes | only the logged book, number and price count. Nothing is re-selected later (book, quote, model variant, delay) |

## 4. Prices and profitability

- **Confirmatory ROI:** flat 1 unit per settled signal at its recorded price (the logged quote's price). Signals
  without a recorded price never enter it. The denominator is settled signals with a recorded price, pushes
  included.
- **Hypothetical ROI:** missing prices at -110. Always labelled hypothetical, never used for a verdict.
- **Coverage requirement:** a "supported" ROI verdict needs a recorded price on at least 95% of decided signals in
  that market. This is necessary, not sufficient.
- **Missing-price checks, at every read:**
  - **Where missing prices cluster:** the missing share by book, week, edge band, feed and market. A group with 10
    or more decided signals and a missing share of at least max(10%, twice the overall share) is flagged.
  - **Sensitivities:** missing prices set to the worst and to the best recorded price in that market. A
    "supported" ROI verdict also needs z >= 2.50 with the worst. A "contradicted" one also needs z <= -2.50 with
    the best.
  - **Insufficient evidence:** the verdict is "inconclusive". Incomplete records are never silently dropped.
- **Kinds of evidence, kept apart:**
  - recorded-price signals (A with a price);
  - fresh observed quotes (B);
  - accepted bets (C);
  - "observed available" quotes in the delay test (section 6). These are never fills.

## 5. Quote logging

**What is logged:** each card pull, and each targeted poll every 3 minutes (`.github/workflows/quotes.yml`, started by
a cron-job.org job), logs quotes for the games in a watch window. Each logged game gets every quote at the 7 books,
both sides of the spread and the total (`cbb/quotelog.py`).

**Watch window:**
- from a signal's actual alert through 95 minutes after it (the 60-80 minute window plus a polling buffer);
- the 20 minutes before the scheduled tip of a game with an open signal;
- either way, stopping at the scheduled start.

The pull that generates a signal also logs every quote of that signal's game at that pull. This is the cohort B
record.

**Each observation row carries:**
- our observation time, the feed, its event id and the game;
- the scheduled start the feed reported;
- book, market, side, number and price;
- the feed's own timestamp and the quote's age;
- the status:
  - available;
  - unavailable: the feed said so;
  - stale: older than 12 hours by the feed's own flag;
  - absent: the book was in the poll but did not list this quote, or a watched game was missing from the poll before
    its tip.

**Other logs:**
- Each poll attempt is logged with its status (ok, skipped, error), error text, cost, credits left and gap. A
  targeted poll with no game in a watch window makes no call and writes no row; the workflow's run history shows
  it ran.
- Each signal records its generation time, the pull it used, its quote, and its input cutoffs.
- Each alert attempt (ntfy and Discord) is logged with its send time and result.

A quote is only ever seen at an observation. Nothing is inferred between polls. Finished days are gzipped.

**Cost:** see `audit/OPERATIONS.md`. Targeted polling uses The Odds API only, at 2 credits per call, and calls only
when a game is watched.

## 6. Delay test

**Alert time:** the first successful ntfy alert for the signal, else its first successful Discord post, else its
logged time. The fallback is labelled.

**Windows:** 5-10, 15-25, 30-45 and 60-80 minutes after the alert. Results are labelled by window and actual elapsed
time, never as exact 5, 15, 30 or 60-minute execution.

**For each signal and window:**
- Take the **first** observation in the window, before the tip cutoff (section 7), at the original book on the
  signal's side. Classify it:
  - **unavailable:** unavailable or absent;
  - **stale:** marked stale, no feed timestamp, a timestamp more than 60 seconds ahead of our clock, or one older
    than 600 seconds;
  - **available.**
- A later observation in the window never replaces an unavailable or stale first one.
- **No observation in the window:** "missing".
- **A window starting at or after the cutoff:** "window after tip".
- **A window cut short by the tip:** flagged.
- "Observed available" is not a fill. A missing or unavailable observation is not proof that no bet was possible.

**For each observed-available quote, reported separately:**
- **A. Opportunity retained:** the original number or better at an acceptable price. An acceptable price is a payout
  at least as favourable as the original price.
  - same number, price as good or better: yes;
  - better number, price as good or better: yes;
  - better number, worse price: "ambiguous". Never converted, since no number-to-price equivalence is used;
  - same number, worse price: no;
  - worse number: no.

  Number-or-better at any price is reported as descriptive only.
- **B. Remaining model EV:** whether the quote still passes the frozen +2% EV rule. B uses:
  - the signal's own logged prediction (`model`);
  - the frozen win-chance table and 2.5 / 3.0 thresholds, copied into `forward_eval.py` and tested against the
    freeze commit;
  - never updated ratings or later information.

  Reported both as EV alone and as edge threshold plus EV.

**Original book vs tracked books:** the original book is the primary measure. Each tracked book's own first
observation in the window is reported separately, as signals with A at one or more books, and signals with no book
observed.

**Hypothetical ROI at the observed quote:** descriptive only.

## 7. Closing lines

**Tip cutoff:** the scheduled start carried by the latest observation made before its own reported start.
- **Delays and reschedules:** they move the cutoff.
- **Never observed pregame:** the game uses `closing.csv`'s scheduled start.
- **Actual tip times:** not observed and not used.
- **Postponed or cancelled games:** void.
- **Games moved to another date:** close missing, counted.

**Primary (strict) close, per book:**
- the last valid observation made within the 15 minutes before the cutoff;
- valid means: available, a feed timestamp no more than 300 seconds old (up to 60 seconds ahead accepted), and
  observed before the cutoff and before its own reported start;
- only the 7 books are eligible.

**Consensus:**
- **Spreads:** the median of the books' home numbers (away rows negated), converted to the signal's side.
- **Totals:** the median total.
- Each close reports its number of books, their observation times before the cutoff and their feed ages.

**Duplicates and conflicts:** all observations sit in one deterministic order:
1. observation time;
2. card log before targeted log;
3. The Odds API before SGO;
4. feed timestamp, number, price.

"Last" and "first" are taken in that order, so the same data always gives the same close.

**Benchmark close (secondary):** `lines/closing.csv`, books observed within 60 minutes before the scheduled start,
median. Reported for coverage and sensitivity. It never replaces the primary close, whichever gives the better
result. Post-tip and in-play quotes are excluded everywhere.

**Line value:** points the close moved toward the signal from its logged number:
- spreads: logged minus close, from the signal's side;
- overs: close minus logged;
- unders: logged minus close.

A point is not treated as equally valuable across markets, and points are never converted to money.

## 8. Pauses, reviews and changes

- **Data-integrity or operational failure:** fixed when found and recorded in `MODEL_FREEZE.md`. Affected signals
  are flagged, never deleted or regenerated.
- **Pausing real bets:** the existing tripwire can pause cohort C. It never changes the model.
- **Signal logging (A):** continues through any pause.
- **Model changes:** anything that can change a selection, including every row of the table in section 1. Only at a
  checkpoint, with Chad's approval, a backtest and a Discord announcement the day they go live. A change starts model
  v2 under section 2. v1 continues as a shadow or is labelled interrupted.

## 9. Statistical plan

**Reads:**
- **January 15, 2027:** descriptive only. Estimates, counts and descriptive intervals; no z, no test, no verdict.
  No interim stopping rule or boundary exists.
- **Final read:** run on **2027-03-14** (Selection Sunday), after every game through 2027-03-14 is graded, and in
  any case before the first NCAA tournament game on 2027-03-16. Games through 2027-03-14. The only formal conclusions.

**Primary endpoints, per market (spreads and totals separately), on model v1 cohort A:**
- **E1:** mean line value against the strict close (points).
- **E2:** ROI at recorded prices (units per signal).

**Uncertainty:** a date-clustered bootstrap. Game dates are resampled with replacement, 5,000 draws, fixed seed
20261026. Each draw's statistic is the mean over all signals on the drawn dates.
- **z** = the mean of the bootstrap draws divided by their standard deviation (the bootstrap SE).
- **Intervals:** 95% percentile intervals, descriptive.

**Multiplicity:** 2 markets x 2 endpoints = 4 one-sided tests at a familywise 0.025, Bonferroni: 0.00625 each,
critical z = 2.50.

**Endpoint verdicts, final read only:**
- **inconclusive** if:
  - the market has fewer than 100 decided signals;
  - for E1, strict-close coverage is below 80%;
  - for E2, recorded-price coverage among decided signals is below 95%;
- otherwise:
  - **supported:** z >= 2.50, and for E2 also z >= 2.50 with missing prices at the worst recorded price;
  - **contradicted:** z <= -2.50, and for E2 also z <= -2.50 with missing prices at the best recorded price;
  - **inconclusive:** anything else.

**Market verdict:**
- **supported** only if both endpoints are supported;
- **contradicted** if one is contradicted and neither is supported;
- **inconclusive** otherwise.

"Inconclusive" is an acceptable, predeclared outcome.

**Secondary, descriptive only:**
- the 60-minute benchmark;
- cohorts B and C;
- delay windows;
- the price-free win rate;
- the opposite-side sensitivity;
- missing-price clustering.

**Power:** the season is a fixed sample with limited power, not a guarantee of a decisive answer.
- **At -110:**
  - **Win-rate SE:** about 2.0 points at 600 decided signals (dependence-aware 1.9-2.2).
  - **ROI SE:** about 3.9 points.
- **What 600 signals can detect:**
  - A true 57% is about 2.3 SE from break-even, below the 2.50 bar.
  - A true 54% (about 0.8 SE) and 55% (about 1.3) cannot be told apart.
- **Expected outcome:** even a real edge of the size seen historically may well end "inconclusive" in one season.

Historical results (+5% to +10% ROI, about +1 point of line value) come from seasons reused to design the model.
They are hypotheses, not expectations.

## 10. Reporting

At each read, run unchanged:
- `python -m audit.forward_eval --through <date>`;
- `python -m unittest audit.test_forward_eval`.

The output goes to the helpers' doc and to Chad with:
- every count;
- cohorts A, B and C;
- the pre-freeze signals separately;
- the version status (running, shadow, interrupted).

## Appendix B. Band B (written Oct 29, 2026, before any band B play was logged and before any game)

Approved by Chad on Oct 29. Band B is a separate, tagged bet type beside v1, not a change to v1. Every v1 rule,
endpoint, test and threshold in sections 1-10 is unchanged, and v1's signals exclude band B.

**What it is.** A play is band B when it meets all of these:
- the frozen v1 projection's edge against the best book's number is 2.0 to 2.49 points on a spread;
- it passes v1's +2% EV rule at that book's price, with v1's win-probability rule;
- it is not a v1 play.

The same best-book choice, opening-week rule and accepted-price flow apply.
- **Totals:** a totals band B (2.0 to 2.99) is built but switched off. Chad chose spreads only on Oct 29 because
  the replay on inputs known at the opener did not support totals (`research/band_b/out/replay.txt`). Switching it
  on is a new approval and a `MODEL_FREEZE.md` entry.
- **Stake:** 0.5 unit flat. The live-record multiplier and the stake cap do not apply.
- **Logging:** in `bets/bets.csv` with `bet_type` = "bandB" and a bet id ending in `|bandB`. Each play is alerted
  and posted with the tag.
- **One bet per game and market:** a game and market that v1 has already bet is never logged as band B. If a game
  logged as band B later reaches v1's cutoff, v1 logs it as usual and the band B play stands. That play counts in
  band B only, and each read reports how many such games there were.

**Cohorts and measures.** Every band B play is cohort A. It gets the same primary close (section 7), delay windows
(section 6), accepted-price fields (section 4) and immutability check as a v1 play. It is read with the same code as
its own version, `python -m audit.forward_eval --version bandB`, and never pooled with v1.

**Decision rule** (fixed now; measured on settled band B plays at the primary close, at recorded prices):
- **Jan 15:** descriptive only.
- **Decision read:** at 300 settled band B plays, or on Mar 14, whichever comes first.
  - Mean primary CLV above +0.3 points **and** win rate above 52.4%: keep band B and move it to 1 unit.
  - Mean primary CLV from 0 to +0.3: keep it at 0.5 unit. This also covers CLV above +0.3 with a win rate at or
    below 52.4%.
  - Mean primary CLV below 0: end band B.
- **Per market:** if a market reaches 150 settled plays by itself, it is judged on its own by the same rule. With
  totals off, this concerns spreads.
- **Approval:** any change of stake, or ending band B, is a `MODEL_FREEZE.md` entry and a Discord note. It goes to
  Chad with the numbers.

**Tripwires.** Band B is excluded from v1's trailing-150 model check and from v1's stake cap. The Monday health
report (`audit/health.py`) carries its own trailing-100 primary-CLV line, flagged when below 0. The flag is a report
to Chad, not an automatic pause.

## Changelog

- v1.0 (2026-10-26): declared.
- v1.1 (2026-10-26, before any forward data): adds a secondary any-book delay measure.
- v2.0 (2026-10-26, before any forward data):
  - January 15 is descriptive only; the interim verdict and the z >= 3.0 boundary are removed.
  - z is defined as the bootstrap mean over the bootstrap SE.
  - Confirmatory ROI uses recorded prices only. Assumed prices are hypothetical.
  - Profitability requires 95% price coverage, plus clustering checks and the worst/best-price sensitivities.
  - Denominators are defined.
  - Delay windows are bounded at 5-10 / 15-25 / 30-45 / 60-80 minutes, with the first observation and its status.
  - A (opportunity retained) and B (frozen EV) are reported separately.
  - Watch windows run from the actual alert; absent quotes are logged.
  - The strict 15-minute / 5-minute-age primary close is added, with the 60-minute close as a secondary benchmark,
    plus the tip-cutoff and duplicate rules.
  - Model versions, the shadow strategy and the immutability check are added.
  - The frozen definition covers injury-source choice and line feeds.
  - Same day, operational fix after the first scheduled targeted poll and still before any forward data: idle
    targeted polls write no row, and the workflow saves its log correctly before the first quote is logged.
- v2.1 (2026-10-28, before any game was played or graded; Chad's request): the final read moves from on or after
  March 16 to March 14, after the last regular-season and conference-tournament games are graded, so the decision is
  made before the NCAA tournament starts on March 16. The game window (through March 14), the endpoints, the tests
  and every threshold are unchanged. No result had been computed.
- v2.2 (2026-10-29, before any game was played and before any band B play was logged; Chad's approval): Appendix B
  adds band B as a separate, tagged bet type with its own pre-set decision rule.
  - `audit/forward_eval.py` excludes band B from v1's signals and reads band B as its own version
    (`--version bandB`). In the delayed check, B_rule uses band B's 2.0-point floor for band B plays.
  - v1's endpoints, tests, thresholds, games and every v1 number are unchanged. The test is
    `audit/test_band_b.py`.
