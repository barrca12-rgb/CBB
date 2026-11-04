# Operational readiness for the forward test (checked Oct 26, 2026)

Facts below come from the code, the repository's logs and git history, and the feeds' own response headers. Anything
not verified is marked as such.

## Line feeds

| | SportsGameOdds (SGO) | The Odds API |
|---|---|---|
| Used by | card runs (`odds.py`), every third run at most (25-minute gap) | card runs (`odds_api.py`, every run: `ODDS_API_EVERY_RUN=1`) and targeted polls (`poll_targets.py`) |
| Allowance | monthly entities, shared with the NFL model; `odds.py` stops pulling at 95% | 100,000 credits a month. The account went 500 -> 20,000 -> 100,000 on Oct 26 (headers: 95,604 left, 4,396 used at 20:20 UTC) |
| Reset date | monthly (not re-checked here) | not verified. The plan started Oct 26, so the 26th is expected; Chad's account page shows it |
| Other consumers | the NFL model | none seen: consecutive card pulls decrement exactly 3 credits each |
| Price | Chad's existing plan, ends Nov 25 | **not verified from the pricing page.** the-odds-api.com cannot be reached from this environment: DNS fails, and the host is not on the network allowlist. A third-party review lists the 100K tier at $59/month |
| Events, books | all books in the frozen set where offered | in preseason only DraftKings and Caesars carry NCAAB lines. The other 5 books are requested every call and appear when they post (books the API refuses are skipped automatically) |
| Markets, prices | spreads, totals, moneylines with prices | spreads and totals with prices (card runs also moneylines and links) |
| Source timestamps | per-quote `lastUpdatedAt` | per-market `last_update` |
| Status | explicit `available: false`, plus event started/ended/cancelled | none: a book that drops a quote is simply missing. The logger records it as "absent" against the books present in that poll |

**What SGO ending Nov 25 means:** from then on (or earlier, if its 95% stop or an error hits), the SGO pull raises an
error. `odds.pull` catches it and builds the card from The Odds API alone, because The Odds API is due on every run.
Nothing else changes. SGO's explicit "unavailable" status disappears from the quote log; "absent" rows remain.

**To verify on Nov 1:** which books The Odds API carries for NCAAB in season. With fewer than 7 books, every book
listed above that is missing simply never contributes. That is a property of the feed, not of the model.

## Projected Odds API usage

| Consumer | Cost | Projection |
|---|---|---|
| Card runs | 3 credits a call (spreads, totals, moneylines; one region) | 123 runs in the last 22 hours (below): about 135 a day, so about 400 credits a day and **about 12,100 a month** |
| Targeted polls | 2 credits a call (spreads, totals), only when a game is watched | at most 480 calls a day (every 3 minutes, all day) = 960 credits a day, **at most about 29,800 a month**. Realistically, a day with 10-15 signal games watched about 115 minutes each is 150-250 calls, so 300-500 credits |
| **Total** | | **at most about 42,000 a month against 100,000.** No upgrade or purchase is needed |

`odds_api.due()` stops card pulls, and `poll_targets` stops targeted polls, below **10,000** credits left (live reserve, Chad, Oct 30); one phone alert goes out the first time the balance falls below **20,000** (`lines/odds_api_alert.json`). The 50,000 floor applies to research pulls only, all scheduled after the Nov 25 renewal.

## Achieved cadence

**Card runs:** git history of card commits, Oct 25 22:16 to Oct 26 20:20 UTC, 123 runs.
- Median gap 8.1 minutes, 90th percentile 29.9, maximum 30.2.
- The 30-minute gaps are the overnight stretch (03:00-12:30 UTC, 11 pm-8:30 am ET).
- Since 10:00 UTC, the median gap is 8.8 minutes.

**Targeted polls:** no achieved cadence yet. The workflow is pushed, but this session cannot dispatch it: the GitHub
integration returns 403 on workflow dispatch. The 3-minute cron-job.org job that drives it has not been created.
Its first runs will show in `lines/polls_targeted.csv`. Until it has, delay windows
rely on card pulls (about every 9 minutes). Many 5-10 and 15-25 minute windows will then be "missing", and they are
reported that way.

## Failure handling

| | |
|---|---|
| Retries | feed calls are not retried within a run; the next run (minutes later) is the retry. Pushes retry 3 times with a rebase |
| Overlap | `update.yml` and `quotes.yml` each have their own concurrency group (`cancel-in-progress: false`): runs of one workflow queue, never overlap |
| Concurrent writes | the two workflows write different files (`lines/obs/` and `polls.csv` vs `lines/obs_targeted/` and `polls_targeted.csv`). Shared append-only logs use `merge=union` (`.gitattributes`). Finished days are gzipped once and never rewritten |
| Idempotency | the signal log is keyed by `bet_id` (first row wins); an observation is written once per poll and game (`quotelog.LOGGED`); the evaluation sorts and de-duplicates deterministically |
| Budgets | SGO 95% stop; The Odds API live reserve 10,000 (card and targeted polls stop below it; alert at 20,000); research pulls keep a 50,000 floor; targeted polls spend nothing when no game is watched |
| Failure logging | every card-run poll attempt (ok, skipped, error with text) is in `lines/polls.csv`, and every targeted poll that calls the API (ok or error) in `lines/polls_targeted.csv`; every alert attempt in `bets/alert_log.csv`. Every logger call catches its own errors, so logging can never stop a card run |

## Discord record

The channel and its webhook secret exist. Posting has worked since the 18:41 UTC run on Oct 26: 8 signals, 2 voids
and 4 notes posted (`bets/discord_posted.json`). Every new signal posts when it is logged.

## Out of scope

The proposed 15-unit daily cap and any staking change are not part of this work.

## 2026-10-27: push collisions (operational fix, no model or rule change)

- **What happened:** card run 246 (13:40 UTC) failed. A research commit was pushed in the 0.6 seconds between the
  job's pull and its push, so GitHub rejected the push. That card update was not saved. The 13:50 run succeeded,
  so no card was lost for more than one cycle.
- **Cause:** `update.yml`, `injuries.yml` and the research pulls pushed only once. `quotes.yml`, `shadow_v2.yml`
  and `history_sample.yml` retried three times, but their loop reported success even if every try failed.
- **Fix, in every workflow:** up to 6 tries of pull-rebase-then-push, waiting 4, 8, 12, 16 and 20 seconds between
  tries. Any half-finished rebase is aborted between tries. The step fails only if all 6 fail, so a real failure
  still shows.

## 2026-10-27: Odds API renewal date

- **Renewal:** Chad confirmed the plan renews on **Nov 25**. Balance after the Oct 27 research pulls was about 58,800.
- **Projected use to Nov 25:** live use (card about 400 a day, plus targeted polls once the season starts) is about
  20,000-32,000, leaving about 27,000-39,000 at renewal.
- **Research pulls** keep their 50,000 floor.

## 2026-10-27: line shopping on the card (display only)

- **What it shows:** each play on the card lists the other books on the same side under the bet, best number first,
  then best price ("Also: DraftKings +3.5 (-110) · ..."). The Book column still shows the book with the best EV, as
  before.
- **Unchanged:** picks, edges, stakes, alerts and the bet log. `cbb/report_html.py` only; not a fingerprinted file.
- **Approved by Chad, Oct 27.** Backed by `research/market/LOG.md` (best of four books: +1.1% ROI per spread bet).

## 2026-10-27: Placed button on the card (approved by Chad)

- **What it is:** each logged play on the card has a **Placed** button. It opens a short form pre-filled from the
  bet log (book, line, odds, units); Chad edits what differs and saves.
- **What happens on save:** the page starts `.github/workflows/placed.yml` with the browser's GitHub token (the same
  one as Update). That runs `cbb/placed.py`, which:
  - sets `placed` to yes on that row of `bets/bets.csv`;
  - writes the book, line, odds, stake and time to `bets/accepted.csv` (cohort C, one row per bet; a second save
    replaces it).
- **Unchanged:** picks, lines, edges, stakes and grading in the bet log. Bad input (unknown bet, non-American odds,
  stake outside 0-20 units) is refused.
- **Health line:** the Monday line counts "placed with the card button".
- **Tested:** in a browser with GitHub mocked (exact dispatch payload checked), and the script on a copy of the bet
  log (only the `placed` column changed).

## 2026-10-27: record page lists placed bets only (Chad)

- **Change:** the "Every play" table is now "Bets placed": only rows marked `placed` = yes, no voids.
- **Unchanged:** the summary, KPIs, cohorts and monthly rows on the same page, and the bet log itself. Voided and
  unplaced plays stay in `bets/bets.csv` (linked under "Check it") and on Discord.

## 2026-10-27: the record counts placed bets only (Chad)

- **What counts:** the record page's numbers (record, win %, units, ROI, CLV, monthly rows, chart, open plays) now
  use only bets marked `placed` = yes, voids excluded. At the change these were exactly Chad's 7 Pikkit bets.
- **Unchanged:**
  - every play is still logged in `bets/bets.csv` and posted to Discord;
  - the forward test's cohorts A/B/C (FORWARD_TEST_PROTOCOL.md) on the same page still use every signal;
  - the card's stake multipliers (`tracker.status`, frozen) still read every play.
- **Safeguard:** `cbb/placed.py` refuses to mark a bet placed once its game has tipped (start time from that day's
  card), so the placed-only record cannot be edited after results are known. A late entry is done by hand in the
  session and shows in the log's commit history.

## 2026-10-27: every play counts as placed (Chad, replaces the entry above)

- **Rule:** Chad bets every play, so the record counts every logged play except voids and any row marked
  `placed` = "no".
- **Why the placed filter existed:** it came from the Oct 26 unders mix-up. That is handled by voiding (the two voids
  stay out).
- **Placed button:** now optional, for recording the actual book, price and stake (cohort C). Its before-tip check
  stays.
- **Matching counts:** the card tiles, Discord and the record page count the same plays again.

## 2026-10-27: news and injury automation (approved by Chad; information only)

1. **Team news scanner** (`cbb/team_news.py`, called from `news.annotate`):
   - each card run reads ESPN's free per-team news feed for both teams of every play or watch;
   - it keeps articles tagged with that team from the last 7 days whose headline or summary matches eligibility,
     suspension, season-ending injury or left-the-team keywords;
   - a hit shows as a warning under the play and in its phone alert, and is logged once to
     `injuries/news_log.csv`;
   - adds about 5 seconds a run, and a failed feed is skipped.
2. **Injury status in every new-bet alert:** Out / Doubtful / Questionable players for both teams from every
   injury source (`injuries/sources/current.csv`), with the sources named, or "none listed".
3. **Eligibility watchlist** (`data/eligibility_watch.csv`): 17 teams with a key player's eligibility or an
   announced absence unresolved, from Greg Peterson's 2026-27 preview (plus ESPN for Auburn). Plays involving them
   carry the warning until Dec 15, or until the row is removed when the case resolves.

- **Unchanged:** no projection, pick, stake or rule. No fingerprinted file changed (run_day.py and tracker.py
  hashes match). ESPN covers mostly high-majors; low-major news still relies on the X link on each play.
- **First live hit:** today's Arizona at UCLA play, with "Arizona's Lloyd fumes over fifth-year F RJ Godfrey's
  eligibility limbo" (ESPN, Oct 21).

## 2026-11-02: Weekly health check follows the main-plays-only notifications

- `audit/health.py`: since Nov 2, 01:30 UTC only main plays are posted to Discord (MODEL_FREEZE "Notifications carry
  main plays only"). The missing-post flag now counts only band B bets logged before that time, so band B plays
  logged later are not flagged as missing. Every count is unchanged. Operational only.
- `research/quant/e2_shadow.py score`: a card built before books post has no `open_total` column, which made the
  score read fail. That column is now read as empty. Research only.

## 2026-11-02: Past days' cards brought up to date

- **Why:** the card run rebuilds today and the coming week, never a past day. Nov 1's page kept the scores and
  record from its last build, at 00:50 UTC Nov 2, before High Point finished.
- **The fix:** `report_html.refresh_past`, called by `cbb/card_features.py` after each run (unfrozen; display
  only). For the last 3 past days it updates:
  - the final scores and game state from ESPN (`run_day.slate`);
  - the record block from today's fresh card;
  - the pre-rule line-move list and results;
  - the layout, to today's.
- **Unchanged:** picks and logged numbers.
- **Test:** `audit/test_same_layout.py`.

## 2026-11-02: Season record tile at the top of the card (Chad, Nov 2)

- **What:** a "Season record" tile leads the card's top row: the official record across spreads and totals, every
  day so far (Nov 1's Notre Dame-Villanova Under included), with win %. On a phone it spans the full width.
  The Spreads and Totals tiles stay.
- **Source:** the same record block as those tiles (`record.status`, main plays only), so they always agree.
- **Display only** (`cbb/report_html.py`, unfrozen). Past days pick it up through `refresh_past`.
- **Tests:** `audit/test_same_layout.py`. `audit/test_opposite_side.py` now picks a game with no spread play. Its
  first pick from tonight's live card had gained a spread play, which failed the test with or without this change.

## 2026-11-02: Live scores and a results-only refresh between card runs (Chad, Nov 2)

- **Why:** a final reached the site only through the 10-minute card run, then the publish, then the page's 3-minute
  check, so up to about 15 minutes after the buzzer.
- **`cbb/live_refresh.py` + `.github/workflows/live_refresh.yml` (new; display only):** runs after every 3-minute
  targeted quote poll.
  - It reads ESPN's free scoreboard for live and final scores and the game clock, and grades finished plays with
    the card's own grader (`tracker.settle`, run on the runner only).
  - It rebuilds the record block (tiles, record table, recent results) and today's, the coming week's and the last
    few past days' cards. When a play was graded, it also rebuilds the record page. Then it publishes.
  - After 8 pm ET the current card is tomorrow's, so the day before also gets live scores.
  - **No credits:** no Odds API, SportsGameOdds, KenPom or Barttorvik call, and no model run. Picks, lines and
    logged numbers are untouched.
  - **Never commits:** the bet log, Discord results and phone alerts stay with the card run, which grades the same
    games and remains the record of truth. The workflow has no secrets, so it cannot post or alert.
  - It publishes only when something changed, and skips publishing if a card run saved a newer card meanwhile.
- **Card (`cbb/report_html.py`):**
  - Play rows and band B rows show the score with the clock (red dot while live), then a W/L/P badge once final,
    graded the way the bet log grades. The odds board shows live scores too.
  - The record block is built by `report_html.record_block`, shared with the card build, so both show the same
    numbers.
  - The card's "Updated" time stays the card run's (when lines were last pulled).
- **`cbb/autorefresh.py`:** open pages check for a newer copy every minute (was 3).
- **Unchanged:** no fingerprinted file changed (`update.yml`, `run_day.py` and `tracker.py` as they were).
- **Tests:** `audit/test_live_refresh.py`:
  - the site build matches the card run's;
  - the workflow has no secrets, push or commit, and the module imports no odds or posting code;
  - scores, clock and record land on the right days;
  - the card's own time is kept;
  - play rows grade W and L like the bet log.

## 2026-11-02: "Line time not recorded" on the card

- **What it was:** the card's freshness note is about each game's current line. Once a game tips, books take their
  lines down, so every started game read "line time not recorded", as did pregame games with no line up anywhere.
  The plays themselves were fine: each logged play keeps its own number, price and logged time in the bet log.
- **Fix (`cbb/report_html.py`, display only):**
  - no freshness note once a game has started;
  - a pregame game says "no book has a line up right now", or "no current line at <book>" when other books have one.
  - Freshness alerts and `bets/inputs.csv` are unchanged.
- **Test:** `audit/test_live_refresh.py`.
- **Follow-up, same night:** each 10-minute card run rebuilt the card without the game clock, and the results
  refresh correctly held off publishing until the next pass, so "2nd half · 15:48 left" disappeared for 3-5
  minutes after every card run. The card build (`report_html.build`) now reads the clock from ESPN's free
  scoreboard when any game has started (display only; a failure leaves scores only).
- **Follow-up 2 ("time not updating"):** a 3-minute publish makes the clock jump in steps. The card page now reads
  ESPN's free scoreboard itself every 30 seconds while a game on it is on (ESPN allows browser reads), and repaints
  scores, the clock and the final W/L in place. It also reads it on open and when the tab comes back into view.
  Display only: the published card, record and bet log update as before. Test: `audit/test_live_refresh.py`.

## 2026-11-02: Home page stays on tonight until the last game is final (Chad, Nov 2)

- **Why:** after 8 pm ET the card run makes tomorrow's card the current one (run_day `--auto`, unchanged), so the
  home page jumped to tomorrow while tonight's games were still on.
- **`live_refresh.hold_tonight` (display only):**
  - While any game on the day before the card's current day is live, or still to tip (no more than 3 hours past
    its start), days.json's `current` (the day the site build copies to index.html) stays on that day.
  - The card run's own choice is kept in `held_from`.
  - Once every game is final, postponed or long past its tip, `current` goes back to the card run's day.
  - Applied by `cbb/card_features.py` after each card build, and by each results refresh. The refresh is what
    switches the home page within ~3 minutes of the last final.
- **Unchanged:** run_day still builds, prices and logs tomorrow's card exactly as before; no fingerprinted file
  changed.
- **Tests:** `audit/test_live_refresh.py`.

## 2026-11-02: Records not matching across tabs

- **What it was:** every published page carried the same record (checked live: 15-13, +0.54 units on each date tab
  and the record page). The site is served with a 10-minute browser cache, though. A date tab opened from a copy
  the browser had kept showed an older record until the page's own refresh replaced it a few seconds later.
- **Fix (`cbb/autorefresh.py`, display only):** links between the site's pages (date bar, record, charts, back to
  the card) open the newest copy (`?t=` added on click and dropped again on arrival).
- **Test:** `audit/test_autorefresh.py`.

## 2026-11-03: Run failures overnight (8 of 800 runs since 03:00 UTC)

- **Publish collisions (5):** GitHub Pages takes one publish at a time.
  - The card runs at 04:50, 08:50 and 12:50 UTC failed with "in progress deployment" while a results refresh was
    publishing.
  - Refreshes at 05:15 and 09:15 failed with "Unable to find artifact", the same collision from the other side.
  - Each card was built and saved; the next publish caught up.
  - **Fix (`.github/workflows/live_refresh.yml`, not fingerprinted):** the refresh does not publish while a card
    run is going, since the card run publishes itself. It no longer cancels an earlier refresh mid-publish. A
    GitHub-side publish error is logged instead of failing the run; the next refresh is 3 minutes away.
- **GitHub hiccup (1):** the refresh at 05:00 hit "Failed to get ID Token: socket hang up", covered by the change above.
- **Survivor (1):** the 03:30 run failed writing "W" into an empty result column (pandas 3 typing). `load_picks` and
  `grade` keep that column as text. Test: `audit/test_survivor_grade.py`.
- **Cancelled refresh (1):** replaced by a newer one; that no longer happens.

## 2026-11-03: Charts tab returned 404

- **Cause:** `record/charts.html` is built on the runner by `record_page.write` and never saved in the repo. A results
  refresh that graded nothing published the site without it. Every 3 minutes the Charts tab disappeared until the
  next card run rebuilt it. This began with the results refresh (Nov 2).
- **Fix (`cbb/live_refresh.py`):** every refresh builds the Charts page before publishing (about half a second).
- **Test:** `audit/test_live_refresh.py`.

## 2026-11-03: CLV marked verified (Chad)

- Chad signed off ("verify it then") after the Nov 1 first-game check passed and the Nov 2 CLV fixes. These were the
  neutral-site spread sides and the actual-tip cutoff.
- `cbb/clv_primary.VERIFICATION_STATUS` is "verified". The card, record page and Discord results no longer add a
  status note to CLV figures.
- `audit/CLV_VERIFICATION.md` records the sign-off. The section 7 caveats stay listed: the meaning of the provider
  timestamp, ESPN's stamp lag, and 6 of 7 books.
- Discord note: `2026-11-03-clv-verified`.

## 2026-11-03: Every play's CLV audited; closing-line collection gaps fixed

- `audit/clv_audit_all.py` recomputes every play's close and CLV independently (standard library, protocol v2.5) and
  compares with the site. Result: 125 of 125 closes match to the decimal.
- 7 graded plays had no close. One was a game the feed starts after midnight ET (filed under the next day). Six were
  games only SGO carries (no SGO quote in the last 15 minutes). Both are fixed for future games (MODEL_FREEZE, Nov 3).
- Re-run any time with `python -m audit.clv_audit_all`.

## 2026-11-04: Input snapshots, morning shadow and the timing audit

- Each logged play now records the exact input tables behind it (`bets/input_snapshots.csv`). The tables are in
  `bets/snapshots/`; KenPom's are in the private runner cache only.
- The morning shadow writes `bets/shadow_morning.csv` from 9 am ET on each game day. It is research only. Run
  `python -m research.morning_shadow.compare`.
- The timing audit for every changing input is `audit/TIMING_AUDIT.md`: confirmed vs assumed, safeguards and the
  historical odds inventory.
- The weekly health task's early-plays line is now description only (the 40-close trigger is withdrawn). It also
  reports the morning shadow and the snapshots.
