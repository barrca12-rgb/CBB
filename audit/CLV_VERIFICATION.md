# CLV verification (audit of Oct 28, 2026; first-game report to follow)

**Status: built, not verified.** The pipeline is built and tested on synthetic data; it has not yet been run on a
real closing window. It is marked verified only by the first-game report (section 7), not because polling jobs are
running. Every CLV figure on every surface carries this status until then (`cbb/clv_primary.VERIFICATION_STATUS`).

Scope: Chad's Oct 28 instruction. A (display only) and B (the model-check tripwire) are implemented under change
control (MODEL_FREEZE.md, "2026-10-28: one CLV everywhere"; Discord note `2026-10-28-clv-definition`, posted
Oct 28, 15:25 UTC). Predictions, bet selection, staking and the frozen primary-close definition are unchanged.

Code audited: `audit/forward_eval.py` (frozen protocol code), `cbb/clv_primary.py`, `cbb/quotelog.py`, `cbb/odds.py`,
`cbb/odds_api.py`, `cbb/tracker.py`, `cbb/record.py`, `cbb/report_html.py`, `cbb/record_page.py`,
`cbb/record_chart.py`, `cbb/review.py`, `audit/health.py`, `.github/workflows/update.yml`, `quotes.yml`. Records
audited: `bets/bets.csv`, `bets/signal_log.csv`, `bets/accepted.csv`, `bets/alert_log.csv`, `lines/closing.csv`,
`lines/obs/`, `lines/obs_targeted/`, `lines/polls*.csv`, `reports/cbb_*.csv`. Tests: `audit/test_clv_primary.py` (14)
and `audit/test_forward_eval.py` (23), all passing.

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
bookmaker/market `last_update`, SGO `lastUpdatedAt`). Valid for the close: status available, age between -60 s and
+300 s. In the 540 observations logged so far, 95% of available quotes were 300 s old or less (Caesars' 90th
percentile is 375 s, so Caesars will sometimes drop out).

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
| Changed start time | The cutoff moves with the latest pregame report; the watch window follows `closing.csv`'s latest start. Tested (`test_a_moved_start_moves_the_cutoff`). | **Open:** for two current bets the feed's start is 60 min before ESPN's: Memphis at Iowa State (feed 23:00, ESPN 00:00 UTC; Over 152.5) and Ohio State at BYU (feed 01:00, ESPN 02:00 UTC; Ohio State +1.5). If the feed is wrong, their close is taken about an hour before the real tip, and the Odds API stops listing the game at its own start. The protocol defines the cutoff by the feed, so this is not changed; each play now carries `espn_start` and `start_gap_min`, and a gap over 10 min is flagged in its reason. |
| Postponed or cancelled | Protocol: void. The grader grades only games ESPN marks final, so a postponed game's bet stays `open` (excluded from every CLV average) until voided. | **Open:** no code voids postponed games automatically; the two voids so far were set by hand. A last-minute postponement could still produce a primary close from pre-start quotes, but the bet is never settled, so the close is never averaged. |
| Moved to another date | The game key includes the bet's date, so quotes under the new date do not match: "no quotes logged for this game", counted as missing (the protocol's rule). | As designed. |
| A book removes the market early | The book's later polls show `absent` (excluded). Its last valid quote counts only if it falls inside the 15-minute window and is fresh. A stale number is never carried forward (unlike the grader's same-book close, which keeps a book's last number however old). | As designed. |

**Tip-time check (Oct 28): not daylight saving.** All 7 games with both a feed and an ESPN start are after the Nov 1
clock change (no lined D-I games on Oct 31; Nov 3-8 not yet listed by the feed):

| Difference, ESPN minus feed | Games |
|---|---|
| 0 min | 4: Notre Dame vs Villanova (Rome), Miami vs Florida, Gonzaga vs Purdue, Arizona vs UCLA |
| 60 min | 2: Memphis vs Iowa State (Sioux Falls), Ohio State vs BYU (Salt Lake City); feed earlier |
| other | 1: Liberty vs High Point; placeholder times on both sides (ESPN 11:59 pm, feed 2:00 am ET) |

A pre-change offset would shift every post-change game; four of six real times agree. Third-source check: the Hall
of Fame Series (Las Vegas) lists Gonzaga vs Purdue at 4:30 pm and Arizona vs UCLA at 7:00 pm Pacific (00:30 and
03:00 UTC), matching both sources; Ohio State and BYU, and Iowa State and Memphis, list their games' times as TBD,
so neither source's time is confirmed for the disputed pair. Verdict: provisional times, not a feed, parsing or
ESPN offset error; no protocol change. The two plays stay flagged (`start_gap_min` = -60), and the cutoff moves
when the feed updates its start. Notre Dame vs Villanova is unaffected (both sources 14:30 UTC): its pre-tip polls
run 14:10-14:30 UTC (9:10-9:30 am ET) and the first-game check stays at 17:15 UTC (12:15 pm ET). Re-checked on
Nov 2 before the games.

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

## 6. Evidence

`audit/clv_example.py <bet_id>` writes `audit/examples/clv_<bet_id with | as _>.md`: the entry (with cohort, alert
sends, the cohort B and C records), the tip cutoff and its source with ESPN's start, every quote observed from 20
minutes before to 10 minutes after the cutoff (book, side, line, price, feed timestamp, observation time, age,
status, reported start) labeled INCLUDED, superseded or excluded with the reason, the consensus close, the signed
CLV, the price comparison per book, the same-book diagnostic, and every surface's figure with an explicit agreement
check and coverage beside every average. Tested on synthetic quotes (3 books included; a stale, an absent, an early
and an in-play quote excluded; all surfaces +2.00).

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
- **It reports:** whether the 3-minute pre-tip polls captured at least two fresh books; whether a primary close was
  computed; whether both CLV columns were written (`bets.csv` same-book, `bets/clv_primary.csv` primary); what is
  missing; and whether every surface agrees to the decimal. It writes the traced example and adds the result below.
- **Until that report exists, the status everywhere is "built, not verified".**

### First-game report

Pending (the game is on Nov 1).
