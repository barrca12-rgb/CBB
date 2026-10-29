# Opener speed: which feed sees a new opener first, and how fast the card alerts it

Approved by Chad. Measurement only.
- **Nothing changed:** no file outside `research/speed/` was touched, nothing was committed, and no odds API was
  called (0 credits).
- **Script:** `python -m research.speed.measure` (add `--since <UTC time>` to change the window, `--no-refresh` to
  skip the git rebuild).
- **Outputs:** `research/speed/out/measure.txt` (every table below), `out/openers.csv` (one row per game, book and
  market), `out/alerts.csv` (one row per bet), and `out/pulls.parquet` (cache of the closing.csv git history).
- **Data:** run of Oct 29, 23:30 UTC. Window: from 2026-10-26 00:00 UTC (Oct 25, 8 pm ET). This is preseason: 7
  games, 31 game-book openers and 8 alerts. Every number below is a description of 4 days, not an estimate.

## Method

- **Pulls:** every committed version of `lines/closing.csv` is one card-run pull (636 pulls from Oct 25 22:32 to
  Oct 29 23:30 UTC).
  - A version's own pull is the set of rows whose `pulled_at` equals that version's latest value. Older rows are
    kept games and are dropped.
  - Every Odds API poll logged in `lines/polls.csv` (512 of 512) has a matching commit, so no run is missing.
- **Feed of a row:**
  - The row is from The Odds API when `sgo_event` starts with `oa:`. Otherwise it is from SportsGameOdds (SGO).
  - `odds.pull` drops an Odds API row when SGO already has that game and book. So on the runs that pull SGO (every
    third run), an Odds API copy can be hidden.
  - The other two runs out of three skip SGO and show The Odds API's full set. Its first sighting is therefore exact
    to within one run.
- **Opener:** the first card run at which a (game, book, market) has a number.
  - Spreads and totals posted together in every case, so the tables count game-books.
  - **Bracket:** the time since that feed's previous successful poll that did not have the line. The book posted
    inside the bracket, so the bracket bounds the part of the lag we cannot see.
  - **Left-censored:** an opener first seen at a feed's first poll ever. The Odds API began on Oct 26 at 02:28 UTC,
    and the 5 DraftKings lines it found then may have been up for days. These openers are flagged and left out of
    the posting histogram.
- **Feed's own timestamp:** this is The Odds API's `last_update` or SGO's `lastUpdatedAt`.
  - It is logged only in `lines/obs*`, and only for watched games (from a signal's alert onward).
  - It therefore exists only for openers that arrived in the same pull as a signal.
- **Alert lag:** time from the first card run that showed the alerted number (at that book, same side) to `logged_at`.
  - `logged_at` is the alert time. `bets/alert_log.csv` starts on Oct 26, and the one ntfy send it holds came 1 second after `logged_at`.
  - **Upper bound:** adds the bracket, giving `logged_at` minus the feed's last poll without the number.
  - **Cause:** "rule/model change" when a commit to `cbb/` or `data/projection.json` falls between the first quote
    and the alert. Otherwise "polling".
- **Latency from cadence:** the delay from a posting instant, chosen uniformly at random, to the feed's next
  successful poll. It uses the actual poll times from Oct 26 to Oct 29, sampled every 10 seconds.

## 1. Openers: which feed first, its timestamp, the card run that had it

Posting batches (one book's new games in one card run):

| first card run (ET) | book | first feed | games | feed's own timestamp (ET) | bracket (min) | note |
|---|---|---|---|---|---|---|
| Sun 10-25 22:28:26 | DraftKings | The Odds API | 5 | - | - | left-censored (first Odds API poll) |
| Sun 10-25 22:40:23 | Caesars | The Odds API | 5 | - | 2.1 | second Odds API poll |
| Mon 10-26 20:20:40 | Fanatics | The Odds API | 6 | 20:19:41 (59 s before the run) | 10.0 | alerted in the same run |
| Mon 10-26 22:40:36 | Fanatics | The Odds API | 1 | - | 10.0 | |
| Wed 10-28 12:20:45 | FanDuel | **SGO** | 1 | - | 30.1 | The Odds API had it 128 min later |
| Wed 10-28 13:20:46 | theScore Bet | **SGO** | 1 | - | 30.1 | The Odds API had it 68 min later |
| Wed 10-28 14:29:03 | theScore Bet | The Odds API | 6 | - | 8.2 | SGO had one of these 22 min later |
| Wed 10-28 14:29:03 | FanDuel | The Odds API | 1 | - | 8.2 | |
| Wed 10-28 15:30:58 | FanDuel | The Odds API | 1 | - | 10.3 | |
| Wed 10-28 15:40:47 | FanDuel | The Odds API | 3 | - | 9.8 | SGO had one of these 10 min later |
| Thu 10-29 17:10:38 | FanDuel | The Odds API | 1 | - | 9.9 | |

- **First feed, all 31 game-books:** The Odds API 29, SGO 2.
  - SGO carries only 2 of the 7 games, so for most openers it never competes.
- **Game-books seen on both feeds (4):**
  - **SGO first, twice:** 68 and 128 minutes ahead, both on Notre Dame-Villanova on Oct 28. The Odds API was polled
    every 10 minutes the whole time and did not have them, so this is a real feed difference.
  - **The Odds API first, twice:** 10 and 22 minutes ahead. Both leads are shorter than SGO's 30-minute poll gap, so
    they may be nothing more than SGO's polling.
- **Bracket**, 26 uncensored game-books: median 9.8, 75th percentile 10.0, 90th percentile 10.1, maximum 30.1
  minutes. In other words, the book posted at some point in the last poll interval.
- **The Odds API's timestamp age at our poll:** median 51 s, 90th percentile 181 s (516 quote-log rows).
  - This is the feed's own refresh lag, not the book's.

Alerts in `bets/bets.csv` within the window (the number is the book's opening number in all 8):

| alert (logged_at, ET) | book | pick | first quote of that number (ET) | lag (min) | upper bound (min) | cause |
|---|---|---|---|---|---|---|
| 10-25 21:53:02 | DraftKings | Ohio State +1.5 | 10-25 19:15:23 (SGO) | 157.7 | 181.3 | model change: 13 commits between (price-aware plays, market ratings, injury feed) |
| 10-25 22:28:35 | DraftKings | Purdue +4.5 | 10-25 22:28:26 | 0.1 | - (censored) | polling |
| 10-25 22:40:27 | Caesars | Florida -5.5 | 10-25 22:40:23 | 0.1 | 2.2 | polling |
| 10-26 09:53:44 | DraftKings | Under 156.5 | 10-25 22:28:26 | 685.3 | - (censored) | rule change (thresholds lowered, Oct 26) |
| 10-26 12:56:46 | DraftKings | Under 154.5 (void) | 10-25 22:28:26 | 868.3 | - | rule/model change |
| 10-26 12:56:50 | DraftKings | Under 160.5 (void) | 10-25 19:15:23 | 1061.5 | 1085.1 | rule/model change |
| 10-26 13:20:55 | DraftKings | Over 152.5 | 10-25 22:28:26 | 892.5 | - (censored) | rule/model change (opening-week totals shift) |
| 10-26 20:20:47 | Fanatics | Over 159.5 | 10-26 20:20:40 (feed 20:19:41) | 0.1 | 10.1 | polling; 1.1 min from the feed's timestamp |

**Lag distribution** (opener alerts, voids excluded; minutes):

| group | n | median | 75th | 90th | max | upper-bound median | upper-bound 90th |
|---|---|---|---|---|---|---|---|
| all opener alerts | 6 | 78.9 | 553.4 | 788.9 | 892.5 | 10.1 | 147.0 |
| cause = polling (alert in the first run that had the number) | 3 | 0.1 | 0.1 | 0.1 | 0.1 | 6.2 | 9.3 |
| cause = rule/model change | 3 | 685.3 | 788.9 | 851.0 | 892.5 | 181.3 | 181.3 |

**By ET hour of the first quote:**
- 7 pm: n 1, 157.7 minutes (rule change).
- 8 pm: n 1, 0.1.
- 10 pm: n 4, median 342.7, 90th percentile 830.3 (three of the four are rule changes).

**By book:**
- DraftKings: n 4, median 421.5.
- Caesars: n 1, 0.1.
- Fanatics: n 1, 0.1.

**Unobserved part (bracket) of openers, by hour:**
- 2 pm: 8.2 minutes.
- 3 pm: 9.8.
- 8 pm: 10.0.
- 10 pm: 2.1.
- 12-1 pm: 30.1. Those were the SGO-first lines, polled every 30 minutes.

**By book:**
- Caesars: 2.1.
- FanDuel: median 9.8, 90th percentile 18.2.
- Fanatics: 10.0.
- theScore Bet: median 8.2, 90th percentile 17.0.

**Reading:**
- **When the rules are fixed:** the card alerts in the first run that has the number, about 7 seconds after the pull
  (`bets/signal_log.csv`).
- **The whole lag is then polling.** The part we cannot see is up to one poll interval, about 10 minutes, median
  about 5.
- **The long lags were preseason rule and model changes:** the thresholds lowered on Oct 26 and the opening-week
  totals shift. They say nothing about polling. MODEL_FREEZE now blocks such changes.

## 2. When openers post (first card run, ET hour; 26 uncensored game-books)

| ET hour | 12 | 13 | 14 | 15 | 17 | 20 | 22 | all others |
|---|---|---|---|---|---|---|---|---|
| openers | 1 | 1 | 7 | 4 | 1 | 6 | 6 | 0 |
| posting batches | 1 | 1 | 2 | 2 | 1 | 1 | 2 | 0 |

- **Busiest three hours (any three):** 2 pm, 8 pm and 10 pm ET, with **73%** of openers.
- **Busiest consecutive three hours:** 1-4 pm ET, with 46%.
- **Per day:**
  - Oct 25: 100% in one hour (10 pm).
  - Oct 26: 100% in two hours (8 pm and 10 pm).
  - Oct 28: 92% (1-3 pm).
  - Oct 29: one opener.
- **Nothing posted between 11 pm and noon in this sample.**
- **Openers arrive in batches:** 10 batches carry 26 game-books. One book adds 1-6 games in a single poll.
- **Lead time:** openers were first seen 82-189 hours before tip (median 128). These are week-ahead season-opener
  lines.
  - In-season next-day openers should post far closer to tip, and possibly overnight (`research/edges/RESULTS.md`).
  - This histogram does not predict the in-season posting window.

## 3. Effective opener latency: from posting to our first poll that has it (minutes)

| scenario | median | 75th | 90th | max |
|---|---|---|---|---|
| Until Nov 25: line on SGO first, SGO polled about every 30 min (achieved) | 14.3 | 22.1 | 26.9 | 40.1 |
| Until Nov 25: line on both feeds (first poll of either) | 5.0 | 7.9 | 9.8 | 30.1 |
| After Nov 25: The Odds API alone, about every 10 min (achieved), line on The Odds API | 5.0 | 7.9 | 9.7 | 30.1 |
| After Nov 25: a line SGO would have had first (The Odds API's own lag of 68 and 128 min, n = 2, plus the poll) | about 73 and 133 | | | |
| The Odds API every 3 minutes | 1.4 | 2.1 | 2.6 | 2.8 |

**In the busiest consecutive window (1-4 pm ET):**
- SGO: 14.9 / 22.4 / 26.9 (median / 75th / 90th percentile).
- The Odds API: 4.2 / 6.9 / 8.7.

**Additional delays:**
- The Odds API's own refresh lag: median 51 s, 90th percentile 181 s.
- Card processing: about 7 s.
- Alert send: under 1 s.

**Reading:**
- **Until Nov 25:** SGO is only the faster source when The Odds API does not yet carry the line. In those cases the
  30-minute SGO cadence costs a median of 14 minutes.
- **After Nov 25:**
  - Lines The Odds API carries keep the same roughly 5-minute median.
  - Lines only SGO had early would be 1-2 hours late. This rests on 2 game-books from one game, too few to size.

## 4. Credits: a 3-minute cadence in the busiest 3-hour posting window

**Logged costs:**
- **Odds API card call:** 3 credits per call, whatever the number of games (512 of 512 calls).
- **Targeted spreads+totals call:** 2 credits (`lines/polls_targeted.csv`).
- **SGO:** 1 entity per event returned. That is 7-21 per call now, median 10. `update.yml` says about 200 per run in
  season, which is not verified.

**Calls per day:**
- **Now:** 18 card runs a day in a 3-hour window at a 10-minute cadence (22 achieved, counting push-triggered runs).
  SGO is pulled 6 times in the window.
- **At 3 minutes:** 60 calls a day in the window.

| feed | extra per day | extra per 30 days | quota | balance / use now |
|---|---|---|---|---|
| The Odds API (3-credit card call) | +42 calls = **+126 credits** (window total 180) | +3,800 | 100,000 a month, renews Nov 25 | 57,649 left (Oct 29 23:30 UTC); card use about 384 a day (128 calls) |
| The Odds API (2-credit spreads+totals call between card runs) | +84 credits | +2,500 | same | same |
| SGO, at today's 10 events a call | +54 calls = +540 entities | +16,200 | 100,000 entities a month, shared with the NFL model; 95% stop | 86,109 left; all users about 3,070 a day (ours about 505) |
| SGO, at about 200 events a call in season | **+10,800 entities** | quota gone in about 8 days | same | not workable; SGO ends Nov 25 anyway |

**For comparison:** a 3-minute cadence all day on The Odds API is 480 calls × 3 = 1,440 credits a day (about 43,000
a month).

**The Odds API against the 50,000 research floor:**
- The balance is only 7,649 above the floor.
- Live use already projected to Nov 25 (20,000-32,000, `audit/OPERATIONS.md`) takes it below the floor by
  mid-November whatever the cadence.
- A 3-minute window from Nov 13 to Nov 25 adds about 1,600 credits. That brings forward the date the floor is
  crossed by about 3 days.
- After the Nov 25 renewal, +3,800 a month fits well inside 100,000.

**SGO:** in season it can only be done at preseason event counts, and it ends Nov 25.

## 5. Pre-set action for the Nov 12 read (written Oct 29, before any game)

"If the median first-quote-to-alert lag is over 5 minutes, or the 90th percentile over 20, propose 3-minute polling in the posting window with the credit cost in front of Chad. No cadence change before Nov 12 and none without his approval (it is a freeze entry)."

Notes for applying it. These are not part of the action.

- **Which measure the script reports:** `out/measure.txt` prints the check for two windows.
  - **The default window (since Oct 26) triggers today:** median 78.9, 90th percentile 788.9. This comes entirely
    from the 3 preseason alerts logged after rule and model changes.
  - **The in-season window (alerts logged from Nov 1 ET)** has no data yet.
  - **Recommendation:** read the in-season window on Nov 12 and show the split by cause next to it.
- **"First quote" as measured is the first card run that showed the number:**
  - On that measure, an alert in the same run is about 0.1 minutes. Polling alone can never push the median over 5.
  - The polling cost sits in the unobserved bracket: median about 5, 90th percentile about 10 at the current
    cadence.
  - Before Nov 12, Chad should confirm which reading the rule means: from our first sighting, or from the upper
    bound that includes the poll gap. On the upper bound, the median sits right at the 5-minute line.

## Limitations

- **Sample:** 4 preseason days, 7 games, 26 uncensored game-books in 10 batches and 6 non-void alerts. Of those 6,
  3 are polling-caused and 1 is censored.
  - The feed comparison rests on 4 game-books from 2 games.
  - No percentile here is stable. Hour and book tables have 1-7 rows per cell.
- **Not measurable yet:**
  - **When the book itself posted:** only bounded, by the bracket.
  - **The feed's own timestamp of an opener:** available for 1 of 31. The quote log keeps only watched games, and
    closing.csv has no feed timestamps.
  - **Odds API copies on SGO runs:** whether The Odds API also had a line on a run where SGO showed it. Those copies
    are hidden.
  - **In-season posting hours:** including overnight posting, which no data covers yet.
  - **In-season SGO event counts:** these drive SGO's per-call cost.
  - **The SGO and Odds API quota reset dates:** SGO's is not verified. The Odds API's is Nov 25 per Chad.
- **Line-level only:** a number counts as quoted when `closing.csv` has it. Quotes older than 12 hours by the feed's
  timestamp are left out of `closing.csv`, so an untouched line could first "appear" when its book updates it.
- **Lags measure logging, not betting:** each one is time to the logged alert, not to a bet being placed or still
  being available.
