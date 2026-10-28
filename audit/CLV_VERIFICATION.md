# CLV verification (audit of Oct 28, 2026; first-game report to follow)

**Status: built, not verified.** The pipeline is built and tested on synthetic data; it has not yet been run on a
real closing window. Chad's instruction (Oct 28): the status stays "built, not verified" on every surface
(`cbb/clv_primary.VERIFICATION_STATUS`) until he changes it. The first-game check reports "first live capture
verified" only when its evidence checklist passes (section 7); that finding does not change the status, and running
polling jobs is never evidence of verification.

Scope: Chad's Oct 28 instruction. A (display only) and B (the model-check tripwire) are implemented under change
control (MODEL_FREEZE.md, "2026-10-28: one CLV everywhere"; Discord note `2026-10-28-clv-definition`, posted
Oct 28, 15:25 UTC). Predictions, bet selection, staking and the frozen primary-close definition are unchanged.

Code audited: `audit/forward_eval.py` (frozen protocol code), `cbb/clv_primary.py`, `cbb/quotelog.py`, `cbb/odds.py`,
`cbb/odds_api.py`, `cbb/tracker.py`, `cbb/record.py`, `cbb/report_html.py`, `cbb/record_page.py`,
`cbb/record_chart.py`, `cbb/review.py`, `audit/health.py`, `.github/workflows/update.yml`, `quotes.yml`. Records
audited: `bets/bets.csv`, `bets/signal_log.csv`, `bets/accepted.csv`, `bets/alert_log.csv`, `lines/closing.csv`,
`lines/obs/`, `lines/obs_targeted/`, `lines/polls*.csv`, `reports/cbb_*.csv`. Tests: `audit/test_clv_primary.py` (19),
`audit/test_tip_correction.py` (9) and `audit/test_forward_eval.py` (23), 51 passing.

## 1. Entry

| What | Where | Rule |
|---|---|---|
| Alert entry: line, odds, book, logged time | `bets/bets.csv` `line`, `odds`, `book`, `logged_at` (and `alert_line`) | Written once by `tracker.log` when the play first shows; the protocol's immutability check (`forward_eval.immutability`) rejects any later change to these defining fields. OpenTimestamped every run (`bets.csv.ots`). |
| Alert send time | `bets/alert_log.csv` (ntfy, Discord) | `forward_eval.alert_times`: first successful ntfy send, else first Discord post. |
| Cohort A, alert CLV | every model v1 signal, logged at or after 2026-10-26T19:20:50Z | CLV of the alert number against the primary close. |
| Cohort B, observed-quote CLV | A signals whose own generating quote is in `bets/signal_log.csv`: same book and number, available, feed timestamp at most 600 s old | Same CLV as A, restricted to this cohort. |
| Cohort C, accepted-bet CLV | `bets/accepted.csv` (Pikkit or the book's history; the card's Placed button writes book, line, odds, stake, time) matched by `bet_id` | CLV of the **accepted** number against the same primary close (`clv_primary.accepted_clv`); fixed Oct 28, it previously used the alert number. |
| Pre-freeze signals | logged before 2026-10-26T19:20:50Z | Reported on their own row, never pooled (fixed Oct 28 on the verification page). |

- **Current records:** 9 bets logged, 2 void, 7 open. 6 of the 7 open bets are **pre-freeze**, including the Nov 1
  Notre Dame–Villanova Under 149.5. One is model v1 (Over 159.5, Miami at Florida, logged Oct 27 00:20 UTC); it is the
  only signal with a cohort B record. `bets/accepted.csv` is empty, so **no bet is a confirmed fill**: the `placed`
  flag is Chad's mark, not a confirmation, and every CLV shown is the alert price's.
- **Wording:** no surface calls an alert a filled bet. Discord result posts say "placed" or "not placed" from the flag;
  the verification page counts C only from `accepted.csv`.

## 2. Close

**Tip time.** `forward_eval.tip_cutoff`: the `start` carried by the latest observation made before its own reported
start. `start` is the feed's scheduled start: The Odds API `commence_time`, or SGO `status.startsAt`, stored in UTC
ISO 8601 (the game's date is its US Eastern date). If the game was never observed pregame, `lines/closing.csv`'s
`start` (the latest start a feed reported) is used. Actual tip times are not observed.

**In-play exclusion.** Only observations with `observed_at` before the cutoff **and** before the observation's own
reported start are eligible. The feeds also stop listing a game once it starts (`odds_api.py` skips events whose
`commence_time` has passed; `odds.py` skips SGO events flagged started, ended or cancelled), and the quote logger
stops watching at the scheduled start.

**Freshness.** Quote age = our `observed_at` minus the feed's own timestamp (`source_updated_at`: the Odds API
market `last_update`, falling back to the bookmaker `last_update`; SGO `lastUpdatedAt`). Valid for the close: status
available, age between -60 s and +300 s (frozen).

**What the feed's timestamp means (checked Oct 28).** The provider's documentation could not be retrieved (the-odds-api.com
is outside this session's network allowlist), so this is measured, not quoted. In 504 consecutive observations of the
same book, game, market and side (polls a median 169 s apart), the line and price **never changed**, yet the timestamp
**advanced in 396 (79%)** and stayed put in 108. Within a poll, a book's markets share one timestamp (129 of 129). So
`last_update` is **not the last price change**: it behaves as the time the provider last refreshed that book's markets
(a scrape or feed update), every few minutes, at a book-specific pace (median age: Fanatics 39 s, DraftKings 42 s,
Caesars 111 s; Caesars' 90th percentile 375 s). It is also **not a confirmation that the book still offers the
market**: a market the book pulls drops out of the provider's response, which the logger records as `absent`.
Effect on the frozen filter: "age at most 300 s" means "the provider re-read this book's market within 5 minutes";
an unchanged line therefore passes (correct: a stable number is still a valid close), while a slow-refreshing book
(Caesars) is excluded more often even when its line is live, which can reduce the book count but never adds an old
number. If the provider ever reports the time of the last price change instead, a stable line would age out and books
would drop from the close; the age distribution in the health of each first-game report is the check for that.

**Selection.** Window [cutoff - 15 min, cutoff). Only the 7 books. All observations sit in one deterministic order
(observation time; card log before targeted log; The Odds API before SGO; feed timestamp, number, price). Per book,
the last valid observation in that order is taken; the close is the median across books, converted to the play's
side (spreads: home number, away rows negated; totals: the total). `clv_primary` calls `forward_eval.strict_close`
itself; nothing is re-implemented. The window and freshness rules come from the frozen constants
(`STRICT_WINDOW`, `STRICT_MAX_AGE_S`, `CLOCK_SKEW_S`, `BOOKS`).

**Polling into the window.** `quotelog.watched_games`: every open bet (pre-freeze included) is watched from its alert
for 95 minutes and in the 20 minutes before its scheduled tip (from `lines/closing.csv`). In that window the
targeted poll (`quotes.yml`, every 3 minutes via cron-job.org; Odds API, 2 credits a call) and each card run
(every 10 minutes) log every quote at every book, plus an `absent` row for a book in the poll that did not list it.

**Edge cases, as the code handles them:**

| Case | Handling | Finding |
|---|---|---|
| Changed start time | The cutoff moves to the start carried by the latest pregame observation; polling follows `closing.csv`'s latest start. Tested for corrections before, during and after the window (below). | **Open:** Memphis vs Iowa State (feed an hour early; below). |
| Postponed or cancelled | Protocol: void. The grader grades only games ESPN marks final, so a postponed game's bet stays `open` (excluded from every CLV average) until voided. | **Open:** no code voids postponed games automatically; the two voids so far were set by hand. A last-minute postponement could still produce a primary close from pre-start quotes, but the bet is never settled, so the close is never averaged. |
| Moved to another date | The game key includes the bet's date, so quotes under the new date do not match: "no quotes logged for this game", counted as missing (the protocol's rule). | As designed. |
| A book removes the market early | The book's later polls show `absent` (excluded). Its last valid quote counts only if it falls inside the 15-minute window and is fresh. A stale number is never carried forward (unlike the grader's same-book close, which keeps a book's last number however old). | As designed. |

**Tip-time check (Oct 28): two separate conclusions.**

*(a) No systematic daylight-saving shift found.* All 7 games with both a feed start and an ESPN start are after the
Nov 1 clock change (no lined D-I games on Oct 31; Nov 3-8 not yet listed by the feed):

| Difference, ESPN minus feed | Games |
|---|---|
| 0 min | 4: Notre Dame vs Villanova (Rome), Miami vs Florida, Gonzaga vs Purdue, Arizona vs UCLA |
| 60 min | 2: Memphis vs Iowa State (Sioux Falls), Ohio State vs BYU (Salt Lake City); feed earlier |
| other | 1: Liberty vs High Point; placeholder times on both sides (ESPN 11:59 pm, feed 2:00 am ET) |

A pre-change offset in either source would shift every post-change game by 60 minutes; four of the six real times
agree to the minute, and the two officially announced times found (Hall of Fame Series, Las Vegas: Gonzaga vs Purdue
4:30 pm and Arizona vs UCLA 7:00 pm Pacific, 00:30 and 03:00 UTC) match both sources. Limits: 7 games, one day; no
pre-change comparison exists, so a shift confined to some other date range is not excluded by this sample.

*(b) Two start times were unresolved on Oct 28.* Ohio State vs BYU (feed 8:00, ESPN 9:00 pm ET) and Memphis vs Iowa
State (feed 6:00, ESPN 7:00 pm ET) had no announced tip time on the schools' schedules ("TBD"; the Sanford Pentagon
showed a 5:00-8:00 pm window). **Update, Oct 28 (Chad):** Ohio State tips at 9:00 pm and Memphis at 7:00 pm (Eastern,
matching ESPN's displayed times).
- **Ohio State +1.5:** resolved. The feed has since moved its start to 9:00 pm ET; cutoff, ESPN and the feed agree
  (`tip_check = ok`).
- **Memphis Over 152.5:** still open. ESPN is right; the feed still says 6:00 pm ET, an hour early. Under the frozen
  rule the cutoff is the feed's start, and the frozen polling (`cbb/quotelog.py`) stops at it. If the feed does not
  correct before about 6:40 pm ET on Nov 2, the close is taken 5:45-6:00 pm ET, an hour before the real tip, and the
  real closing window gets only the 10-minute card polls. The play stays `tip_check = conflict`, alerted, on the card
  and in the health line. **Chad chose option 2 (Oct 28):** for any conflict play the 20 minutes before ESPN's start
  are polled as well (`cbb/quotelog.py`), and a diagnostic close at ESPN's start (`close_espn_start`,
  `clv_espn_start`, `books_espn_start`; same strict rule) is shown beside the protocol's CLV, labeled as such. The
  protocol's cutoff and CLV are unchanged; an uncaptured window gives no diagnostic value.

**Two thresholds, two purposes.** Every play compares the protocol's cutoff with ESPN's scheduled start
(`start_gap_min`) and with the feed's latest reported start in `closing.csv` (`feed_gap_min`), stored in
`bets/clv_primary.csv` as `tip_check`:
- **over 10 minutes: "review" (diagnostic).** Set below the 15-minute closing window: a gap over 15 minutes means the
  protocol's window and a window around the other start do not overlap at all, so anything over 10 is worth a look.
  Placeholder times (ESPN's 11:59 pm) and real moves show up here first.
- **30 minutes or more: "conflict" (escalation).** Large enough that the close is plainly taken at a different time
  from the other source's tip; the case for a rule change, which only Chad can approve.

Both levels are visible and reviewed before tip, never only after: the play's reason text carries the flag; the card
shows a warning line on the logged play; `cbb/tipcheck.py` runs on every card run and sends one phone alert per bet
and per distinct set of times (logging every finding to `bets/tip_review.csv`); the weekly health line counts open
reviews and flags each. Nothing in this changes the cutoff or the close.

**Start-time corrections (tested, `audit/test_tip_correction.py`; old start T0, corrected start T1 = T0 + 60 min):**

| Correction arrives | Protocol cutoff and close | Polling (`quotelog.watched_games`) |
|---|---|---|
| Before the window (observed 60 min before T0) | Cutoff T1; the close uses quotes in [T1-15, T1). | Follows T1 once the card pull stores it: the old window is not polled; [T1-20, T1) is. |
| During the window (observed 5 min before T0) | Cutoff T1. Quotes already captured in the old window are **not** used. With nothing captured in [T1-15, T1): **unavailable**, "no quote observed in the 15 minutes before the tip cutoff". With quotes there: a normal close. | Pauses after the correction is stored and resumes at T1-20. |
| After the old start, seen by a later observation (feed relists the game) | Cutoff T1; nothing captured in the new window -> **unavailable**, no close from the old window and no implied quotes. | Treated as started at T0, resumes once a card pull stores T1. |
| After the old start, only in `closing.csv` (no observation carries T1) | The frozen rule keeps the cutoff at T0 (the start of the latest pregame observation): the close is taken in the old window. Flagged `conflict` (`feed_gap_min` = -60) and alerted. | If T1 is stored, polling covers [T1-20, T1); the first observation there moves the cutoff to T1. |
| Never stored | Cutoff T0. | Stops at T0; nothing is polled near an unknown new start. |

A corrected cutoff never implies quotes that were not captured: the close only ever uses logged observations, and a
window with none is reported unavailable with its reason.

**Coverage today:** only DraftKings, Caesars and Fanatics are quoting the Nov 1–2 games (FanDuel, BetMGM, bet365,
theScore Bet not yet posted); SGO returned no events. With 3 books, a primary close needs at least one of them fresh
in the window. The Nov 4 books check covers the other four.

## 3. Missing coverage

- **Requirement:** the protocol requires at least one valid book in the window; it sets no higher minimum, and that
  is not changed. Zero valid books = **no primary close**.
- **Reported, never substituted:** `clv_primary.primary` returns `clv_status` (ok / pending / unavailable / void) and
  a reason (tip time unknown; no quotes logged; no quote in the window; quotes in the window but none valid, with the
  counts of unavailable, stale and number-less rows). `attach` never falls back to the grader's close or to zero; if
  the observations cannot be read, CLV shows as unavailable and Discord holds the result post for the next run.
  Tested (`test_missing_close_is_unavailable_with_a_reason_never_zero_or_the_graders`,
  `test_attach_keeps_the_graders_value_as_diagnostic_and_never_substitutes_it`).
- **Stored and shown per play:** `bets/clv_primary.csv` (rebuilt every run): cutoff and its source, ESPN start and gap,
  close, CLV, book count, each book's quote age and seconds before the cutoff, status, reason, and the price comparison.
  Shown: Discord "147.5 (3 books)" or "unavailable" plus "Why no CLV"; card recent table "147.5 (3)" or "n/a" with the
  reason on hover; record page close with book count and quote ages on hover.
- **Tripwire:** bets without a primary close are excluded from the trailing 150 and counted (`missing`), never zero.
  It cannot fire until **N = 150** bets have a primary close (`TRIP_MIN_CLOSES`). If the closes cannot be read its state
  is "unavailable" and the last state is kept. The card's Model check tile shows "n/150 bets with a close · k without".
- **Health line:** reports settled plays, with a primary close, and missing; any missing one is flagged with its
  reason (`audit/health.py`).
- **Coverage everywhere an average appears:** "primary close for n of N decided plays" on the card tile, the card's
  record table ("Close coverage"), the record page (tile and table), the verification page (per cohort), the weekly
  chart tiles and caption, and the tripwire. Averages are over decided plays (W or L) with a primary close.
- **Final read gate (unchanged):** strict-close coverage of at least 80% (`MIN_CLOSE_COVERAGE`) for a market's E1
  verdict.

## 4. Calculation

`forward_eval.line_value`, + = the entry beat the close. Each case is a test in `test_positive_clv_means_a_better_entry`
(two books, both sides quoted, 5 minutes before tip, 30 s old):

| Case | Entry | Close (play's side) | Formula | CLV | Why it is better |
|---|---|---|---|---|---|
| Favorite | Florida -5.5 (home) | -6.5 (home number -6.5) | line - close = -5.5 - (-6.5) | **+1.0** | laid 5.5 where the market closed at 6.5 |
| Underdog | Purdue +4.5 (away in the test) | +3.5 (home -3.5, negated) | 4.5 - 3.5 | **+1.0** | got 4.5 where the market closed at 3.5 |
| Over | Over 152.5 | 154.5 | close - line = 154.5 - 152.5 | **+2.0** | over a lower number than the close |
| Under | Under 149.5 | 147.5 | line - close = 149.5 - 147.5 | **+2.0** | under a higher number than the close |

A worse entry is negative (`test_worse_entry_is_negative`: Under 149.5, close 151.5 -> -2.0).

**Points vs price.** Points CLV ignores price. Where paired prices exist, each closing book's quote on the play's side
is compared with the entry by the protocol's own odds-aware rule (`forward_eval.assess`, measure A: number first, then
payout; a better number at a worse price is "ambiguous" and never converted). Stored per play in `price_vs_close`
and in the traced example. Identical numbers at different prices are not called equal
(`test_same_number_different_price_is_not_called_equal`: Under 149.5 at -110 vs a -125 close = "no: same number, worse
price", i.e. the entry beat the close on price). No new probability conversion is introduced. The grader's `clv_prob`
column (a normal-curve conversion of points) stays in `bets/bets.csv` and is not shown on any surface.

## 5. Consistency

Every surface calls `cbb/clv_primary.py` (one calculation, 2 decimals). Checked end to end by
`test_every_surface_shows_the_same_primary_clv` (a settled +2.00 play and a settled play with no close, coverage 1 of 2)
and in a browser render of the card (tile "+2.00 · primary close for 1 of 2 decided plays (50%) · built, not
verified"; record table "+2.00 · 1/2"; recent table "+2.00", same-book "+1.00", "n/a" for the missing one).

| Surface | Code | Uses primary CLV | Same-book shown as |
|---|---|---|---|
| Discord result posts | `record._settled` via `clv_primary.attach` | yes | "Same-book CLV (diagnostic)" |
| Card Avg CLV tile | `report_html._clv_view` | yes, with coverage and status | not shown |
| Card record table | `report_html._clv_view` | yes, with "Close coverage" | not shown |
| Card recent-results table | `report_html._clv_view` | yes | "Same-book CLV (diagnostic)" column |
| Card loss review | `review.classify` via `attach` | yes ("No primary close" is its own reason) | not shown |
| Record page | `record_page.build` via `attach`, `coverage` | yes | "Same-book CLV (diagnostic)" column |
| Verification page | `record_page.cohorts` | yes; C at the accepted number | not shown |
| Weekly charts and caption | `record_chart.stats` via `attach` | yes, decided plays, "close for n of N" | not shown |
| Model-check tripwire | `tracker.tripwires` via `clv_primary.primary` | yes | not used |
| Health line | `audit.health` via `attach` | coverage counts | not used |

- **Same-book CLV** stays in `bets/bets.csv` (`close_line`, `clv_pts`) as a diagnostic only.
- **Already-posted Discord results:** none existed (no game has been played); the Oct 28 note explains the definition.
- **Stake cap, moved to the primary close (Chad's decision, Oct 28):** `tracker.status()` holds a market's stake
  multiplier at 0.5 when its **primary-close** CLV averages below 0 after 25 bets with a primary close (numbers
  unchanged; only the input). Missing closes are excluded and counted; unreadable closes keep the last state
  ("held"). Consequence: the cap can fire later than before, since it waits for 25 bets with a primary close rather
  than 25 settled bets. Shown on the card next to the stake multiplier and in the health line. Tested both ways
  (`test_stake_cap_fires_on_negative_primary_clv_despite_positive_same_book` and its reverse, the 25-with-a-close
  minimum, and the held state). No rule reads the same-book CLV any more.
- **Stake cap, confirmed (code read, Oct 28):**
  - *Eligible cohort:* every settled bet in the market (`status == "settled"`): model v1 **and pre-freeze** bets, placed
    or not; open and void bets excluded. Pre-freeze plays are **not** excluded; that is the population the cap has
    always used, and excluding them would be a staking change (not made; Chad's call).
  - *Ordering and window:* none. The cap is a season-to-date mean over every eligible bet with a primary close (no
    trailing window, so order does not matter), with the minimum of 25 counting only bets with a close. (The model-check
    tripwire is different: the trailing 150 bets with a close, ordered by game date then logged time, same cohort.)
  - *Refresh:* each successful run writes `bets/stake_cap.json` with `refreshed_at` (UTC). While the closes cannot be
    read the state is "held" and `refreshed_at` keeps the last successful time, so a stale cap is visible. Shown on
    the card ("cap off ... · refreshed <time> ET") and in the health line. Last successful refresh: written by each
    card run from Oct 28 on; tested (`test_stake_cap_records_its_last_successful_refresh_and_keeps_it_while_held`).

## 6. Evidence

`audit/clv_example.py <bet_id>` writes `audit/examples/clv_<bet_id with | as _>.md`: the entry (with cohort, alert
sends, the cohort B and C records), the tip cutoff and its source with ESPN's start, every quote observed from 20
minutes before to 10 minutes after the cutoff (book, side, line, price, feed timestamp, observation time, age,
status, reported start) labeled INCLUDED, superseded or excluded with the reason, the consensus close, the signed
CLV, the price comparison per book, the same-book diagnostic, and every surface's figure with an explicit agreement
check and coverage beside every average. It also lists every poll in the 20 minutes before the cutoff (card pulls and
targeted polls, with the longest gap) and ends with an **evidence checklist**: entry present; game graded; cutoff and
its source; tip time consistent (`tip_check` ok); at least 2 eligible books fresh in the window; every included quote
in the window, before the cutoff and its own start, age at most 300 s; included books equal the stored count; signed
CLV equals the protocol's line value; every surface agrees. The verdict reads "first live capture verified" only if
every check passes, otherwise "NOT verified" with the failed checks; open timing and coverage items are listed either
way. Tested on synthetic quotes: 3 fresh books -> verified (open items: 3 of 7 books, no confirmed fill); 1 book with an
ESPN time 60 min later -> NOT verified (book count, tip time).

The required example, **Notre Dame–Villanova Under 149.5 (Nov 1)**, is generated by the first-game check after the
game: `audit/examples/clv_2026-11-01_401920982_total_under.md`. It is a **pre-freeze** signal (logged Oct 25, 22:32
UTC), so it is the first placed bet but not part of model v1 cohort A; it has no cohort B record and no cohort C fill.

## 7. First-game check

- **Game:** Notre Dame vs Villanova, Eternal City Tip-Off (Rome), scheduled 2026-11-01 14:30 UTC (9:30 am ET) by
  ESPN and all three quoting books; the cutoff will be the feed's latest pregame start.
- **Scheduling:** the check is keyed to the game, not a clock time. It first wakes at the scheduled tip plus 2 hours
  45 minutes (17:15 UTC); it then reads the game's verified cutoff from the observations and ESPN's status. If the
  game is not final or the bet not yet graded, it re-arms itself 30 minutes later (up to 8 times), and if the cutoff
  moved, from the new cutoff plus 2 hours 45 minutes.
- **It reports:** the original entry; the raw closing observations with timestamps, quote ages and every exclusion;
  the book count, cutoff and cutoff source; the signed CLV; whether the 3-minute pre-tip polls captured at least two
  fresh books; whether both CLV columns were written (`bets.csv` same-book, `bets/clv_primary.csv` primary); what is
  missing; and whether every surface agrees to the decimal. It writes the traced example and adds the result below.
- **Verdict wording:** "first live capture verified" only when the example's evidence checklist passes; unresolved
  timing and coverage items stay listed. The status everywhere stays **"built, not verified"** until Chad changes it.

### First-game report

Pending (the game is on Nov 1).
