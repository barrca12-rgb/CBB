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

`odds_api.due()` stops card pulls below 15 credits left. Targeted polls stop when the API refuses (logged as errors).

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
| Budgets | SGO 95% stop; The Odds API 15-credit floor; targeted polls spend nothing when no game is watched |
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
