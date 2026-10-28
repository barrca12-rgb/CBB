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

**Timestamps, exactly (Oct 28, Chad's review).** Every logged quote carries three times, all UTC ISO 8601:

| Field | Whose clock | Set when | Used for |
|---|---|---|---|
| `observed_at` | ours | once per poll, when our code parses the provider's response (`odds_api.parse`: `pd.Timestamp.now()` after the HTTP call returns; `odds.py` likewise for SGO). Every quote in one poll has the same value. | the 15-minute window; the in-play exclusion; choosing the cutoff; "last" quote per book |
| `source_updated_at` | the provider's | copied from the response: The Odds API market `last_update` (else the bookmaker's `last_update`); SGO `lastUpdatedAt` | freshness only, through quote age |
| `start` | the provider's | copied from the response: The Odds API `commence_time`; SGO `status.startsAt`. The feed's **scheduled** start as of that poll. | choosing the cutoff; the in-play exclusion |

Derived: **quote age** = `observed_at` - `source_updated_at` (seconds). **Cutoff** = one scheduled start per game.

The rules, each on one named timestamp:
1. **Cutoff** (`forward_eval.tip_cutoff`): among this game's quotes (any market, any book) with `observed_at` earlier
   than their own `start`, take the one with the latest `observed_at`; the cutoff is the `start` it carries. It is
   chosen by **our** clock only; the provider's `source_updated_at` plays no part. A quote observed at or after its
   own `start` can never set the cutoff, so an update received after the feed's start cannot move it. If no quote was
   observed before its own start, the cutoff is `lines/closing.csv`'s latest `start` for the game.
2. **Window**: `cutoff - 15 min <= observed_at < cutoff`, on **our** clock. A quote the provider stamped inside the
   window but that we received later is outside it; one we received inside it counts whatever its provider stamp.
3. **In play**: excluded if `observed_at >= start` (its own start), in addition to rule 2.
4. **Freshness**: `-60 s <= quote age <= 300 s`, i.e. the provider's stamp is no more than 5 minutes older than our
   receipt (and at most 60 s ahead of our clock). This is the **only** use of `source_updated_at`.
5. **Per book**: the last valid quote by `observed_at` (ties broken by the fixed order below). **Close**: median
   across books on the selected side.

**What the cutoff can and cannot guarantee.** Neither source reports the actual tip; the cutoff is a scheduled start.
- *Feed start earlier than the real tip* (Memphis vs Iowa State: feed 6:00, tip 7:00 pm ET): the close is taken an
  hour early, an **early-market comparison** even though the arithmetic is right. Caught by `tip_check` (ESPN 60 min
  later: "conflict"), alerted before tip; the extra polling and the labeled diagnostic close at ESPN's start (below)
  record the real closing window. The protocol's figure is not changed (frozen).
- *Feed start later than the real tip*: quotes received after the real tip but before the feed's start would pass
  rules 2-3, i.e. in-play prices could enter the close. Caught when ESPN's start is more than 10 minutes earlier
  ("review") or 30+ ("conflict"), both before tip. **Not caught:** a feed start up to 10 minutes late, or both sources
  wrong in the same direction. Scheduled starts normally precede the real tip by a few minutes, so in the usual case
  the window ends before the ball goes up.
- Our `observed_at` is stamped after the response arrives, so it is a few seconds later than the provider's snapshot:
  a quote is never treated as earlier than it was.

**Pregame validity gate (Oct 28; diagnostic now, rule change proposed below).** A value that matches the frozen
calculation is a *computed protocol value*; it is a *verified pregame close* only if the quotes in it were pregame.
The scheduled start cannot show that (a feed start 1-10 minutes late passes every scheduled-time check), so the gate
uses an independent record of the actual tip: ESPN's play-by-play stamps each play with a wall-clock time, and the
first play of period 1 (the jump ball) is the tip (`cbb/tipoff.py`, cached in `lines/tipoffs.csv`; e.g. Purdue vs
UConn, Apr 8 2024: scheduled 01:20, jump ball 01:21:33 UTC). For each computed close, `bets/clv_primary.csv` stores
`actual_tip`, `pregame_check` and `pregame_note`:

| `pregame_check` | Condition |
|---|---|
| verified | the latest included quote was observed (our clock) at least 60 s before the actual tip, and the cutoff is within 30 min of it |
| early | every included quote pregame, but the cutoff is more than 30 min before the actual tip (an early-market close; Memphis would be this if the feed stays at 6:00 pm ET) |
| in-play risk | the latest included quote is within 60 s of, or after, the actual tip; or, with no actual tip, at or after the earliest scheduled start (feed or ESPN) |
| unverified | no actual tip available (ESPN posted no timed plays); quotes before every scheduled start, which does not prove they were pregame |
| n/a | no computed close |

The 60 s margin covers the difference between ESPN's clock and ours; our `observed_at` is stamped after the response
arrives, so a quote is never treated as earlier than it was. Shown beside every close ("pregame verified" etc.:
Discord field "Pregame check", record page and card close cells); coverage lines count "pregame verified: n of m".
**Nothing reads it for a rule:** averages, the stake cap and the tripwire still use every computed close.

**Proposed amendment (protocol v2.2; for Chad, not enacted).** Keep the frozen calculation unchanged and reproducible.
Add: (1) the official Alert CLV average and every rule that reads it (stake cap, tripwire) count only closes with
`pregame_check = verified`; (2) "in-play risk" closes are excluded and reported as "computed, not a valid pregame
close"; (3) "early" and "unverified" closes are reported in their own rows, not pooled; (4) coverage is reported as
verified / early / unverified / in-play risk / no close. Requires a dated MODEL_FREEZE.md entry with new fingerprints
for `cbb/tracker.py` and `audit/forward_eval.py` (and the protocol text), a Discord note, and Chad's approval. Until
then the gate is a label.

**Freshness: what is and is not established.** The earlier wordings ("never adds an old number"; "the provider
re-read this book") overstated the evidence and are withdrawn. The rule is stated only as what it checks:
**the provider timestamp is within five minutes of our receipt.** What that timestamp means is unresolved.
- *Measured* (the-odds-api.com documentation is outside the network allowlist, so not quoted): in 504 consecutive
  observations of the same book, game, market and side (polls a median 169 s apart) the line and price never changed,
  yet `last_update` advanced in 396 (79%). Within a poll a book's markets share one stamp (129 of 129). This
  establishes only that the stamp is **not exclusively a price-change time**. It does not establish that the provider
  re-read the sportsbook, or that the book still offered the price, when the stamp advanced. Median age: Fanatics
  39 s, DraftKings 42 s, Caesars 111 s (90th percentile 375 s).
- *An unchanged but live quote excluded:* happens whenever a book's provider timestamp is over 5 minutes old
  (Caesars often), whatever the stamp means; it lowers the book count.
- *An old price passing the filter:* **not ruled out.** If the stamp can advance without the book's price being
  re-confirmed, a stale price passes. Our data cannot tell the cases apart: SGO's 24 observations of the same books
  carry no numbers (all `absent`), so there is no second priced source.
- *Diagnostics (no rule change):* the traced example lists every book's stamp and age, flags any closing book 1+ point
  away from the other books' median, and always carries "provider timestamp meaning unconfirmed" as an open item.
  Resolving it needs the provider's documentation on `last_update` (Chad to read; the site is blocked here) or a
  second priced source.

**Selection.** Window [cutoff - 15 min, cutoff). Only the 7 books. All observations sit in one deterministic order
(observation time; card log before targeted log; The Odds API before SGO; feed timestamp, number, price). Per book,
the last valid observation in that order is taken; the close is the median across books, converted to the play's
side (spreads: home number, away rows negated; totals: the total). `clv_primary` calls `forward_eval.strict_close`
itself; nothing is re-implemented. The window and freshness rules come from the frozen constants
(`STRICT_WINDOW`, `STRICT_MAX_AGE_S`, `CLOCK_SKEW_S`, `BOOKS`).

**Polling into the window.** `quotelog.watched_games`: every open bet (pre-freeze included) is watched from its alert
for 95 minutes and in the 20 minutes before its scheduled tip (from `lines/closing.csv`). In that window the
targeted poll (`quotes.yml`, every 3 minutes via cron-job.org; Odds API, 2 credits a call) and each card run
(every 10 minutes) log every quote at every book, plus an `absent` row for a book in the poll that did not list it. When ESPN's start differs from the feed's by 30+ minutes, the 20 minutes before ESPN's start are watched as
well (Chad, option 2); the Odds API parser passes a game's quotes to the log even after the feed's start so that
window can be recorded (the card still drops started games; the protocol's close still excludes those quotes by
rule 3). For a conflict play `bets/clv_primary.csv` holds `close_espn_start` / `clv_espn_start` /
`books_espn_start`, labeled "not the protocol's CLV".

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

**What the number measures: "Alert CLV (points)".** The entry is the alert (logged) number, so the figure measures
the alert's value against the close, not necessarily the value of the bet Chad placed. Every surface labels it
"Alert CLV" (Discord field "Alert CLV (points)", card tile and tables, record page). Accepted-bet CLV (cohort C) uses
the accepted number from `bets/accepted.csv` against the same close and is shown on its own row; none is confirmed
yet. Points cannot tell -110 from -125 at the same number, so prices are shown beside it, never converted: Discord's
"Prices at close" field (each closing book's number and price on the play's side), the record page's close tooltip,
and the per-book price comparison below. **One-book closes** are valid under the frozen rule and flagged wherever the
close appears ("one-book close"); every coverage line also reports the 2+-book subset with its own average
("2+ books: n (avg), 1 book: n"). The frozen minimum is unchanged.

The formulas, with both spread numbers on the selected team (`test_points_clv_is_measured_on_the_selected_side`):

| Selection | Entry | Close | CLV |
|---|---:|---:|---:|
| Favorite | -12 | -12.5 | +0.5 |
| Underdog | +12 | +11.5 | +0.5 |
| Over | 152.5 | 154 | +1.5 |
| Under | 149.5 | 148 | +1.5 |

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
- **Two conclusions, reported separately** (`audit/clv_example.py`, section 6): **A. Does the independent arithmetic
  match?** (cutoff, book count, close and signed CLV recomputed from the raw files equal the stored values; no
  same-time ties) and **B. Were the selected quotes pregame and eligible?** (cutoff established from raw pregame
  observations, not `closing.csv`; every included quote from an eligible book, available, with a number, observed in
  the window and before its own start, provider timestamp within 5 minutes; `pregame_check = verified`; tip times
  consistent). C covers the operational items (entry, graded, 2+ books, every surface agrees). "First live capture
  verified" needs A, B and C.
- **The closing-file fallback, exactly.** `lines/closing.csv` can supply one thing: a game's **scheduled start**,
  used as the cutoff only when no quote of the game was observed before its own start. It never supplies a quote, a
  number or a close. In that case no quote can pass the in-play rule, so neither the protocol nor the trace produces
  a close (`test_closing_file_fallback_supplies_a_start_only_and_never_a_close`), and check B fails ("cutoff not
  established from raw pregame observations"). Missing raw quotes are never replaced by an aggregate close.
- **Consistency is not correctness.** Agreement across pages shows one number is shown everywhere; it does not show
  the number is right. The trace therefore also recomputes the cutoff, the per-book quotes, the close and the alert
  CLV straight from the raw `lines/obs*/` files with the standard library only (`clv_example.recompute`; no
  `forward_eval` or `clv_primary` function), and the checklist requires that recomputation to match the stored
  values exactly. Tested against the protocol on synthetic quotes, stale, out-of-window and in-play rows included
  (`test_independent_recomputation_from_raw_files_matches_the_protocol`).
- **Verdict wording:** "first live capture verified" only when the example's evidence checklist passes; unresolved
  timing and coverage items stay listed. The status everywhere stays **"built, not verified"** until Chad changes it.

### First-game report

Pending (the game is on Nov 1).
