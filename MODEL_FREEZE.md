# Model freeze: Oct 26, 2026 to Jan 15, 2027

Approved by Chad on Oct 26, 2026. From the commit below until the January 15, 2027 checkpoint, nothing that decides a
play changes: the ratings code and settings, the second-stage weights (data/projection.json), team home edges,
referee tendencies, the preseason prior, the opening-week totals rule, the spread and total cutoffs (2.5 / 3), the
+2% EV minimum and the win-chance table. The ratings still update from every result, as the frozen code does.

Allowed during the freeze: fixes to data feeds, alerts, the site, the bet log and the record (not to how plays are
picked), and logging. Any exception is versioned, announced in the Discord channel the day it goes live, and noted
here.

Frozen at commit: dfb4bc7196d4f72cdeb933abdfcbc87c951122b5

File fingerprints (sha256) at the freeze:

```
03b23da31156a2b5bb2c4931c1569296743b96bd7305920ba77559d748189856  cbb/backtest.py
2c478acb4b1d8a1f29e9a2d984779f9916196507ec1524c43f9f06c2d27a272b  cbb/barttorvik.py
acdc8c627b7b0d63a521a8cef45f9a826f13e6ae88f2d4370cb4dfc71f8dfb8e  cbb/kenpom.py
f324ffdafcc522ed5996ed8e99912ad296c3a44c2a60bdc1b9e570bac16bff23  cbb/ratings.py
8080e931e4face9a615dd4e8b8f7726741cf225bc01bd8959fd5a6b3779b4304  cbb/projection.py
11c8e18f0bb8ab6f447a46e52026fbd9c3d26a1b74fbd9b67707768d4d70e898  cbb/context.py
a61befe042dc8071466223b4b824e2d99bdb55f20dfdea60ed2e67342f3627d1  cbb/players.py
810146943b07047e527cdafd518ec32d314df5c9d199ed5cfe343ee653493e06  cbb/injuries.py
9c27151379e46355a1b29eec0279013544c5e1c94b3e3eca0c2269ba5733e280  cbb/run_day.py
d2fefc7bce0c77a7d550ddf73f50fe6d2db7f9ca7a1a5f900015d0cf42b85dd3  data/projection.json
6862f2ed74a114b1a23fb00eff9d0f4ce468a596e761399ebabc065fec06c040  data/referees.csv
b01cf85d894b68542db7483c9eec54329156fb619ef4b61385f67931757c4f58  data/barttorvik_preseason_2027.csv
3525ba4a52316c323e311c8411912497470720ec40c5d8e38ffdd21f2ae8262e  data/teams.csv
446346d90b515a8271ce9ca592708f797311de3181e10f4d618f380b05e7de50  data/team_aliases.csv
```

Check at the checkpoint: `sha256sum -c` on the lines above (run_day.py may differ only by non-picking changes, each
listed below).

## Selection-affecting code outside the list above (added Oct 26, protocol v2.0)

The forward test needs the frozen definition to cover all selection-affecting behaviour, including the feeds that
supply numbers and prices, book selection, the bet log's logging rule, the injury source and the run schedule. These
files decide a selection too. Their fingerprints at the freeze commit:

```
8264472ee3259f6f315ffbc9c5e576b63cac863d8ab226f7e4552cd461aaad45  cbb/odds.py
1b420ca8ee69d4dd33c67b4748cd057325ae6902aaade1d8d0cda58ebaf5ed4f  cbb/odds_api.py
a206296c0155b2c41de6f8e6d0bb7b59ac9a626dddd4bdc77c8d6714602856d4  cbb/tracker.py
0832624c596e25d4ca58f36ec743de3d8f4a4a6267b4bb2fe2a402147856f82b  cbb/teams.py
4e2bf0059b49f434f1be1729f7698e31630b891f0b92e7c5929ea2e829fb4e73  cbb/data.py
9a1c3aac86d4c22a98df98a74d0adb91fb4de28945b45992ce924ee411c03b1c  cbb/injury_sources.py
75b754c7b350f85138e4685af5e6b882836dd26d61aee0606317c8a3c41a5ea4  .github/workflows/update.yml
```

`odds.py` and `odds_api.py` are listed at the freeze commit. Their logging-only changes since are below.

Also frozen:
- **Injury source:** `injuries/sources/choice.json` does not exist, so the injury report comes from ESPN. Writing it
  (`injury_sources.py` only recommends a switch) is a model change.
- **Thresholds and EV:** the spread and total cutoffs, the +2% EV rule and the win-chance table are in `run_day.py`
  (above). `audit/forward_eval.py` copies them for the delayed-EV check, and a test checks the copy against this
  commit.
- **Book selection:** the 7-book set, the DraftKings tie-break and the feeds' 12-hour staleness rule are in
  `run_day.py`, `odds.py` and `odds_api.py`.

## Forward-test declaration (protocol v2.0, Oct 26, 2026, before the first games on Nov 1)

The primary forward-test configuration is model v1: the live card on the files fingerprinted above. Its configuration
is in `FORWARD_TEST_PROTOCOL.md`, section 1. Cohort v1 starts at this freeze commit's time, 2026-10-26T19:20:50Z;
the 8 signals logged earlier are the pre-freeze cohort, reported separately. All other variants are research
comparisons. v2.0 supersedes v1.1 before any forward data existed. The v1.1 fingerprints are kept below for the
record.

```
6e3f80813e6bb6e51412a5737a68a582b457216997bdca7d9c99aacd9beeb3c2  FORWARD_TEST_PROTOCOL.md
86cbcef72e8a3a9d74f9b2edc6d063b04c21cfb65c6dd42cb0c1b8ff9154a152  audit/forward_eval.py
a7a56f811a7cf402a9161e0c93be66dd4bdeb61fa4cb1c6c4bd6391f41578b1e  audit/test_forward_eval.py
e7438f0999e6e95dd7328d128797cc675fb5bdd5308280dc47d08f6e02e0fd24  cbb/quotelog.py
dddbaf58ed33761e567c9806a23d7d51988a94112fda91195e34233e08a2c957  cbb/poll_targets.py
7d557cd0e580fbd80ed9406794c67680dec53a1b6414c27755a389f6a1542d99  .github/workflows/quotes.yml
2531cec9e0509d9f511025f3ad8e36359d4624978f5817be743460c127fc36ca  audit/out/frozen_preseason_prior_2027.csv
```

Superseded (protocol v1.1):

```
5aa4d6487a95a7feb5b4b32899b617a3e556dcc707a3eafaf309b38339da63dd  FORWARD_TEST_PROTOCOL.md (v1.1)
308631d1a1f6d5c923de3256d9043c4247c6fab71e13ab4ec4b985eeca46b422  audit/forward_eval.py (v1.1)
```

The prior file is `backtest.preseason_prior(2027)` dumped at the freeze. If a live run ever computes a different
prior, that is a data-integrity event under protocol section 8.

## Changes during the freeze

None to how plays are picked. Additions that do not touch any prediction or selection:
- the Discord freeze announcement (`bets/announcements.json`);
- audit scripts and reports (`audit/`);
- the protocol and these fingerprints.

**Oct 26, 2026: forward-test logging applied** (`audit/patches/logging_reporting.diff`, approved by Chad in the
forward-test v2 instructions). It adds:
- `cbb/quotelog.py`, `cbb/poll_targets.py` and `.github/workflows/quotes.yml`;
- logging calls in `odds.py`, `odds_api.py`, `notify.py`, `record.py` and `run_day.py`;
- cohorts and an assumed-price note on the record page;
- `bets/accepted.csv`, and union-merge rules for the new logs.

**Validation** (`audit/patches/logging_reporting_validation.txt`): the Nov 2 card was built in a tree at the
pre-change commit and in the changed tree, with the clock fixed and alerts off. The card CSV, the card HTML and
`bets/bets.csv` are byte-identical, both with the existing bet log and starting from an empty one (2 new signals
logged). The changed selection-path files are now:

```
db63530c8bca29b8a1029820ede41c5e9ae47b947b87023f83784a6dd644ff3a  cbb/run_day.py
c1c0175a5a244a33fdae4b27d80d20614f391269f7ca5642f829408aa0513a46  cbb/odds.py
86a33ef2db6b3a46e6cbf1604cb3e322fb1ceef4e2d71b6629b56e6b62a7f5a8  cbb/odds_api.py
```

What changed in each:
- `run_day.py` and `odds.py`: logging calls only.
- `odds_api.py`: logging calls and a separate quote-only fetch.

The checkpoint check therefore runs:
- `sha256sum -c` on the original list, with `run_day.py` expected to differ;
- `sha256sum -c` on these three new lines.

**Oct 27, 2026: lineup v2 shadow test added** (Chad's request; `research/v2_lineup/PLAN.md`). It adds
`cbb/lineup.py`, `cbb/shadow_v2.py` and `.github/workflows/shadow_v2.yml`, which runs after each card run.
- **No effect on v1:** none of the fingerprinted files changed, and the live card imports neither module, so no
  v1 prediction, selection, alert or log changes.
- **Logging:** v2's spread signals go only to `bets/shadow_v2/`.
- **Status:** v2 is a shadow strategy. A switch would follow protocol section 8, with v1 continuing as a shadow.

## 2026-10-27: ridge-1,000 shadow added (approved by Chad; no effect on v1)

- **Card command:** the card workflow now runs `python -m cbb.card_features`. It calls `cbb.run_day.main()`
  unchanged and copies each day's stage-2 inputs to `reports/features_<date>.csv`.
- **Shadow:** `cbb/shadow_r1000.py` (`shadow_r1000.yml`) logs both versions' plays to `bets/shadow_r1000/`, behind
  the scenes. Plan: `research/r1000/PLAN.md`.
- **Unchanged:** no fingerprinted file, `data/projection.json`, the selection rules, staking, the bet log or the
  forward-test protocol.

## 2026-10-27: Placed button (approved by Chad; no effect on picks)

- **What it does:** the card's Placed button (`cbb/report_html.py`, `.github/workflows/placed.yml`,
  `cbb/placed.py`) sets `placed` in `bets/bets.csv` and records the accepted book, line, odds, stake and time in
  `bets/accepted.csv` (cohort C).
- **Unchanged:** no fingerprinted file, selection rule, staking or grading.

## 2026-10-27: `.github/workflows/update.yml` no longer matches its v2.0 fingerprint (recorded; re-fingerprinting is Chad's call)

`update.yml` is on the v2.0 fingerprint list (run schedule). Since the freeze commit it has changed four times, none
of them in the schedule, the selection, staking, the bet log or grading:
- `fc454fb`: the save step retries the push up to 6 times (fails only if all fail);
- `0484e63`: the card step runs `python -m cbb.card_features`, which calls `cbb.run_day.main()` unchanged and also
  saves each day's stage-2 inputs for the ridge-1,000 shadow (the note above said "no fingerprinted file"; this
  workflow file is one);
- `bf2c6a8`: the site build copies `site/assets/` (Off The Glass brand files);
- `f0d6e65`: the site build copies `site/record/` (weekly record charts) and `reports/verify.html`.
The cron schedule is identical to the freeze commit. The Jan 15 `sha256sum -c` will flag this file; the full diff
is `git diff dfb4bc7 -- .github/workflows/update.yml`.

## 2026-10-27: weekly record chart (helper prompt; no effect on picks)

`cbb/record_chart.py` and `.github/workflows/record_chart.yml` (Monday 8:00 ET) draw two PNGs from `bets/bets.csv`
into `site/record/weekly/`; the record page shows them; `record/verify.html` (unlisted) carries the cohort table and
the verification links. Reads and displays only: no selection, staking, logging or grading change.

**Oct 27, 2026: `update.yml` re-fingerprinted** (Chad: "use your judgement"). The four changes listed above are build,
command-wrapper and push-retry steps; the cron schedule and everything that decides a play are as frozen. New
fingerprint, as of commit `f0d6e65`:

```
f064ccda9a2464dd33b6b7fea18c3b45554e9b76c8e4184272dab84d536743bf  .github/workflows/update.yml
```

The Jan 15 check runs `sha256sum -c` on this line in place of the v2.0 line for `update.yml`. Any later edit to
`update.yml` gets its own dated entry here with its new fingerprint, and a change to its schedule is a model change.

## 2026-10-27: displayed CLV uses the protocol's primary close (display only; grader unchanged)

- **Found:** the grader (`cbb/tracker.py`, fingerprinted) writes `clv_pts` in `bets/bets.csv` against
  `lines/closing.csv`: the last pregame number at the bet's book, or the median of all books, with no 15-minute
  window or feed-age check. The forward-test protocol's primary endpoint (section 7) uses the strict close: per
  eligible book, the last valid observation within 15 minutes of the tip cutoff with a feed timestamp at most 300
  seconds old, median across books.
- **Change:** the record page, its verification page and the weekly chart now compute CLV with the protocol's own
  code (`audit/forward_eval.py`, imported read-only) through `cbb/clv_primary.py`, so they match the March read by
  construction. A play with no valid observation in the window shows no CLV, as in the protocol.
- **Unchanged:** `cbb/tracker.py`, `bets/bets.csv` (its `clv_pts` stays as the per-book benchmark close), every
  fingerprinted file, selection, staking and grading of results.
- Same day: the chart writes a fixed caption (`site/record/CAPTION.md`, `site/record/weekly/<date>-caption.txt`),
  and `site/record/PROFILE.md` holds the X bio and pinned-post drafts. Posting is by hand.

## 2026-10-27: live card cadence recorded (Chad's cron-job.org schedule; in place before the first games)

- **Live cadence:** a card run every 10 minutes around the clock, started by Chad's external cron-job.org job
  (workflow dispatch of "Update CBB card"). The cron lines in `.github/workflows/update.yml` (12 runs a day) are a
  backup only.
- **Measured from card run times:** overnight (midnight to 8 am ET) every 30 minutes on the night of Oct 25-26, every
  10 minutes from midnight Oct 27 on (50 runs that night, longest gap 19 minutes). Daytime has been every 10 minutes
  since Oct 26.
- **Status:** set by Chad before the first games (Nov 1); no play was logged under the 30-minute overnight schedule
  after the protocol's start. The schedule is outside the repo, so it has no fingerprint: any later change to it gets a
  dated entry here, and the weekly health line counts card runs, which shows a change within a week.

## 2026-10-28: forward-test protocol v2.1, final read moved to March 14 (Chad's request; before any game)

- **Change:** the final read runs on 2027-03-14 (Selection Sunday), after every game through that day is graded and
  before the NCAA tournament starts on 2027-03-16; it was "on or after 2027-03-16". `audit/forward_eval.py`
  `FINAL_READ_ON` is now "2027-03-14", and the test that the final read cannot run early now uses March 13.
- **Unchanged:** the game window (Nov 1 through Mar 14), endpoints, tests, thresholds, the model, selection, staking,
  the bet log and grading. No game had been played or graded and no result computed.
- **Shadow plans:** `research/v2_lineup/PLAN.md` and `research/r1000/PLAN.md` decision reads move to March 14 too.
- **New protocol fingerprints (v2.1);** the v2.0 lines above are kept for the record:

```
e56a5bd377ced61f64ee7df2068b695e3faea3ce44c40cb93310db79aa2b2416  FORWARD_TEST_PROTOCOL.md
4a63f6e6baa2e3f0a7f5ed385d07b9ada66e07524a58a9deaf917eba311a22f5  audit/forward_eval.py
58e75584ee9efb986211b1f041b00be71eaa4ae8b50ba3f2286113685be63551  audit/test_forward_eval.py
```

## 2026-10-28: Kalshi quote logger added (research only; approved by Chad; no effect on v1)

- **What:** `research/kalshi/logger.py` and `.github/workflows/kalshi_quotes.yml` run after each card run and log
  Kalshi's public spread and total quotes for the card's BET / WATCH games to `research/kalshi/data/`. Plan and the
  pre-registered read (about Nov 23): `research/kalshi/PLAN.md`.
- **Unchanged:** no fingerprinted file (Kalshi name aliases live in `research/kalshi/aliases.csv`, not the frozen
  `data/team_aliases.csv`), the line feeds, selection, staking, the bet log and the protocol. Adding Kalshi to the
  card's price shopping would be a separate change needing Chad's approval.

## 2026-10-28: one CLV everywhere, the protocol's primary close; model-check tripwire moved to it (Chad approved A and B)

Before any game (first tip Nov 1, 14:30 UTC). Predictions, bet selection, staking, the bet log and the frozen
primary-close definition (`audit/forward_eval.py` strict_close and its window, freshness and book rules) are unchanged.

- **A, display only (no fingerprinted file):** the Discord result posts (`cbb/record.py`), the card's Avg CLV tile, its
  record table and its recent-results table (`cbb/report_html.py`), the loss review (`cbb/review.py`), the record and
  verification pages (`cbb/record_page.py`) and the weekly charts and caption (`cbb/record_chart.py`,
  `site/record/CAPTION.md`) all take CLV from `cbb/clv_primary.py`, which calls the protocol's own close. Averages are
  over decided plays with a primary close, shown with coverage ("close for n of N decided"); a play without one shows
  "n/a" / "unavailable" with the reason and is never given the grader's close or zero. The grader's same-book CLV stays
  in `bets/bets.csv` and is shown only as "Same-book CLV (diagnostic)". `bets/clv_primary.csv` (derived, rebuilt every
  run) stores each play's close, book count, quote ages, status and reason. CLV is shown to 2 decimals everywhere. The
  verification page now reports model v1 cohorts A, B and C separately from the pre-freeze signals, and grades cohort C
  at the accepted number. Every CLV figure carries the status "built, not verified" until the first-game report
  (`audit/CLV_VERIFICATION.md`).
- **B, the model-check tripwire (`cbb/tracker.py`, fingerprinted):** judged on the primary-close CLV. Bets without a
  primary close are excluded from the trailing 150 and counted, never treated as zero; it cannot fire until 150 bets
  have a primary close (`TRIP_MIN_CLOSES = 150`); if the closes cannot be read it reports "unavailable" and keeps its
  last state. The execution tripwire is unchanged. The weekly health line reports settled plays, with and without a
  primary close, and flags any missing one with its reason.
- **Not changed (staking):** `tracker.status()` still caps a market's stake multiplier at 0.5 when its same-book CLV
  averages below 0 after 25 bets. Moving that input to the primary close would change staking, so it waits for Chad's
  decision (listed in `audit/CLV_VERIFICATION.md`).
- **Label fix:** `audit/forward_eval.py` `PROTOCOL_VERSION` read "2.0" after the Oct 28 v2.1 amendment; it now reads
  "2.1". Output label only.
- **Discord note:** `bets/announcements.json`, id `2026-10-28-clv-definition`.
- **New fingerprints:**

```
020fa36910e1d22a6b480ff6aa6901a35b5a6b3429171b8b2406d32c635f8c16  cbb/tracker.py
9624e9c612f01bea7f40e801d799936e2fca211ce2423fbf0a3ff1d539fdabda  audit/forward_eval.py
58e75584ee9efb986211b1f041b00be71eaa4ae8b50ba3f2286113685be63551  audit/test_forward_eval.py
e56a5bd377ced61f64ee7df2068b695e3faea3ce44c40cb93310db79aa2b2416  FORWARD_TEST_PROTOCOL.md
```

## 2026-10-28: stake cap moved to the primary close (Chad's decision); tip-time check (no change)

Before any game. Predictions, bet selection, the win-chance rule, the bet log, grading and the primary-close
definition are unchanged.

- **Stake cap (`cbb/tracker.py`, fingerprinted):** the cap that holds a market's stake multiplier at 0.5 when its
  CLV averages below 0 after 25 bets now reads the protocol's primary-close CLV (`cbb/clv_primary.py`), the same
  figure the pages, Discord and the model-check tripwire use. Its numbers are unchanged (25 bets, below 0, 0.5); only
  the input changes. Bets without a primary close are excluded from the average and counted, and the 25 counts only
  bets with one; if the closes cannot be read the cap keeps its last state (`bets/stake_cap.json`, state "held").
  **Consequence:** the cap can fire later than before, because it waits for 25 bets with a primary close rather than
  25 settled bets. `status()`'s same-book CLV fields are renamed `clv_same_book` / `clv_prob_same_book`
  (diagnostic; no rule reads them). The card's record table shows the cap next to the stake multiplier ("cap off
  (primary CLV +x.xx on n of N plays)" / "cap on" / "cap held"), and the weekly health line reports the same.
  No open play's stake changes: no bet has settled, so both multipliers are 1.0 under either input.
- **Tip-time check (no change):** the 60-minute feed/ESPN start gap on Memphis vs Iowa State and Ohio State vs BYU
  is not a daylight-saving error. Of the 7 games with both times (all after the Nov 1 change), 4 agree, 2 differ by
  60 minutes and 1 has placeholder times on both sides; the two official times found (Las Vegas, 4:30 and 7:00 pm
  Pacific) match both sources. Both disputed games have no announced tip time ("TBD" on both schools' schedules), so
  both sources carry provisional times. They stay flagged per play (`start_gap_min`); protocol v2.1 is unchanged.
- **Discord note:** `bets/announcements.json`, id `2026-10-28-stake-cap`.
- **New fingerprint:**

```
6d206caaa739a9fda0da87dd32c086d797d9a068c9d916721bc44610fdbb89f0  cbb/tracker.py
```

## 2026-10-28: CLV audit gaps closed (metadata, alerts and diagnostics only; no rule change)

Before any game. Predictions, bet selection, staking (the cap's input, numbers, cohort and window), the bet log,
grading and the primary-close definition are unchanged. VERIFICATION_STATUS stays "built, not verified".

- **Stake cap refresh time (`cbb/tracker.py`, fingerprinted):** `bets/stake_cap.json` now records `refreshed_at`, the
  time of the last successful refresh of the persisted state, and `status()` returns it in each market's `cap`. A
  "held" state keeps the earlier time. Metadata only: the cap's decision is computed exactly as before.
- **Tip-time review before tip (`cbb/tipcheck.py`, new; not fingerprinted):** on each card run, an open play whose
  protocol cutoff differs from ESPN's start or from the feed's latest start by more than 10 minutes ("review") or by
  30 minutes or more ("conflict") sends one phone alert per distinct set of times and is logged to
  `bets/tip_review.csv`; the card shows the warning beside the play. Reads and alerts only; the cutoff is not moved.
- **Diagnostics (`cbb/clv_primary.py`, `audit/health.py`, `audit/clv_example.py`):** `bets/clv_primary.csv` adds
  `feed_latest_start`, `feed_gap_min` and `tip_check`; the health line counts open tip-time reviews and shows the
  cap's refresh time; the first-game example ends in an evidence checklist and reports "first live capture
  verified" only when every item passes.
- **Tests:** `audit/test_tip_correction.py` (start-time correction before, during and after the closing window;
  polling) and a cap refresh test. `python -m pytest -q audit/`: 51 passed.
- **Discord note:** none. No rule, pick, stake or displayed CLV changes.
- **New fingerprint:**

```
f88f4a2728f9bda5ffc740d718bb20d30d1268855432e7504eb39d45ec359913  cbb/tracker.py
```

## 2026-10-28: tip-time conflict polling and a diagnostic close at ESPN's start (Chad, option 2)

Before any game. Predictions, bet selection, staking, the bet log, grading and the primary-close definition (cutoff =
the feed's start carried by the latest pregame observation) are unchanged. VERIFICATION_STATUS stays "built, not
verified".

- **Polling (`cbb/quotelog.py`, fingerprinted):** when ESPN's scheduled start (reports/cbb_<date>.csv) differs from the
  feed's latest start (lines/closing.csv) by 30 minutes or more on an open play, the 20 minutes before ESPN's start
  are watched too (3-minute targeted polls). This adds logging to the watch windows described in
  FORWARD_TEST_PROTOCOL.md section 5; the protocol's windows themselves are unchanged. Reason: Chad confirmed Memphis
  vs Iowa State tips at 7:00 pm ET (ESPN's time); the feed says 6:00 pm ET and frozen polling would stop at it. Checked
  on the real game: watched 5:40-6:00 pm ET (feed) and 6:40-7:00 pm ET (ESPN).
- **Diagnostic close (`cbb/clv_primary.py`, not fingerprinted):** for a `tip_check = conflict` play,
  `bets/clv_primary.csv` adds `close_espn_start`, `clv_espn_start` and `books_espn_start`: the same strict-close rule
  with ESPN's start as the cutoff. Labeled "not the protocol's CLV" in the play's reason; no rule, page total, cap or
  tripwire reads it. Uncaptured windows give no value.
- **Tests:** 4 in `audit/test_tip_correction.py`. `python -m pytest -q audit/`: 55 passed.
- **Discord note:** `bets/announcements.json`, id `2026-10-28-tip-conflict-polling`.
- **New fingerprint:**

```
dbe854be36263f142ebc19171944a29eca5f00eede46c4d74b5f6bc59844e3aa  cbb/quotelog.py
```

## 2026-10-28: CLV inputs tightened (Chad's review): timestamps documented, labels, one-book flag, raw-quote trace; parser fix

Before any game. Predictions, bet selection, staking, the bet log, grading, the frozen minimum book count and the
primary-close definition are unchanged. No price conversion is introduced. VERIFICATION_STATUS stays "built, not
verified".

- **Parser (`cbb/odds_api.py`, fingerprinted; logging only):** `parse` dropped every event whose `commence_time` had
  passed, so the extra polling approved earlier today (option 2) would have logged nothing for Memphis vs Iowa State
  after the feed's 6:00 pm ET start. A started game's quotes are now passed to the quote log (kept only inside a
  watch window; excluded from the protocol's close as observed after their own start). The card's line rows and the
  unmatched-name report skip started games exactly as before. Test: `test_parser_passes_a_started_games_quotes_to_the_log_but_never_to_the_card`.
- **Labels (display):** the CLV figure is "Alert CLV (points)" on Discord, the card and the record page; prices at the
  close are shown beside it (Discord "Prices at close", record-page tooltip), never converted. One-book closes are
  flagged; coverage lines add "2+ books: n (avg), 1 book: n".
- **Trace (`audit/clv_example.py`):** independent recomputation of cutoff, books, close and CLV from the raw files
  (standard library only) is a checklist item; books 1+ point off the others are flagged; accepted CLV shown when a
  fill is confirmed. Tests: selected-side formula table and the recomputation-vs-protocol match.
- **Documentation:** `audit/CLV_VERIFICATION.md` defines `observed_at`, `source_updated_at`, `start` and the cutoff,
  states which timestamp each rule uses, and withdraws "never adds an old number" (a re-stamped stale price is not
  ruled out).
- **Tests:** `python -m pytest -q audit/`: 61 passed.
- **Discord note:** `bets/announcements.json`, id `2026-10-28-alert-clv-label`.
- **New fingerprint:**

```
9fe297f302dc0226f063930dad75106f864e9e5b01502aa4ee33b18581dddf08  cbb/odds_api.py
```

## 2026-10-28: `.github/workflows/quotes.yml` re-fingerprinted (save-step retry; recorded at the pre-season check)

The pre-season check found `quotes.yml` no longer matched its recorded fingerprint. The only change since that
fingerprint is `fc454fb` (Oct 27): the save step retries pull-rebase-push up to 6 times with growing waits and
fails only if every try fails (the old 3-try loop could report success when every push failed). The schedule, what
is polled, what is logged and every rule are unchanged. Recorded so the Jan 15 `sha256sum -c` reflects it; no
Discord note (no rule, pick, stake or displayed figure changes).

```
461900ea62b4eff539e1a3db615fe62e5ea500e3379cc0064ba1dcb08442089e  .github/workflows/quotes.yml
```

## 2026-10-29: E2 totals shadow added (approved by Chad; no effect on v1)

- **Shadow:** `cbb/shadow_e2.py` (`.github/workflows/shadow_e2.yml`, after each card run) logs E2's totals signals
  to `bets/shadow_e2/`, behind the scenes. Plan: `research/e2_shadow/PLAN.md`.
- **What E2 is:** v1's stage-2 totals plus neutral-site and conference-game terms. It uses the coefficients frozen
  Oct 28 in `research/quant/out/e2_coefficients.json`, never refit.
  - **Check:** a fresh fit reproduces them exactly, and v1's live totals coefficients to 9e-12.
- **How it's applied:** it adds its difference from v1's stage-2 total to the card's v1 total, then applies v1's
  totals rule unchanged.
- **Unchanged:** no fingerprinted file, `data/projection.json`, the selection rules, staking, the bet log, alerts
  or the forward-test protocol. The card imports nothing from the shadow.
- **Status:** E2 is a shadow strategy. A switch would follow protocol section 8, with v1 continuing as a shadow.

## 2026-10-29: Band B added, a separate 0.5-unit bet type (approved by Chad; v1 unchanged)

Approved by Chad on Oct 29, before any game and before any band B play was logged. Band B is a new, tagged bet
type beside v1, modeled on the Oct 26 neutral-site rule. It is not a change to v1: v1's projection, cutoffs (2.5 /
3), +2% EV rule, win-chance table, book selection, stakes, multiplier, stake cap, tripwires, log entries, grading,
record, alerts and posts are unchanged.

- **The rule (`cbb/run_day.py` `_band_b`; `cbb/tracker.py` `BAND_B_*`, `log_band_b`):** a band B play has all of
  these:
  - the card's best play (best book by EV) has an edge of 2.0 to 2.49 points on a spread;
  - it passes v1's +2% EV rule at that price, with v1's win-chance table;
  - it is not a v1 play.
- **Stake:** 0.5 unit flat, with no live-record multiplier and no stake cap.
- **Totals:** a totals band B (2.0 to 2.99) is built but switched off (`BAND_B_ON`). Chad chose spreads only on
  Oct 29 because the replay on inputs known at the opener did not support it.
- **Logging:** `bets/bets.csv` gets a new last column, `bet_type`. It is "bandB" for band B and empty for v1. A
  band B bet id ends in `|bandB`. A game and market v1 has already bet is never logged as band B.
- **What reads what:**
  - `tracker.load()` returns v1's rows only, so every v1 figure is computed exactly as before.
  - Grading, voids, the tip-time check, the Discord sync, the weekly chart and the quote logger read all rows.
- **Alerts and display:**
  - The phone alert title is "CBB BAND B (0.5u):" and the Discord title is "BAND B (0.5u) BET/WIN/...".
  - The card has its own block, "Band B (2-2.5 spreads, 2-3 totals, 0.5 u)", with a Placed button.
  - The record page has its own section. It appears only once a band B play exists.
  - The weekly CLV chart gets a seventh tile and a dashed line, also only once band B exists.
  - The X caption is unchanged. The per-play close table is `bets/clv_primary_bandB.csv`.
- **Forward test:** protocol v2.2, Appendix B, holds the pre-set decision rule. `audit/forward_eval.py` excludes
  band B from v1 and reads it with `--version bandB`. Band B plays are cohort A, with the same primary close, delay
  windows and accepted-price fields.
- **Monitoring:** `audit/health.py` reports band B's own counts and its trailing-100 primary-CLV line, flagged below
  0. It is never part of v1's tripwire.
- **Replay (`research/band_b/replay.py`, `out/replay.txt`):** spreads 2.0-2.49 at the opener reproduce the Oct 26
  band table for home sites, 54.2% / +0.76 CLV on 2,248 plays (table: 54.3% / +0.71).
  - Neutral sites came out 59.3% / +0.68 on 358 plays (table: 54.7% / +0.57).
  - Every spread band B play clears +2% EV at -110. At recorded DraftKings prices (3 dates), 0 of 19 were trimmed.
  - Totals were not confirmed on inputs known at the opener: 52.1% overs and 53.2% unders. At recorded prices 29
    of 45 were trimmed. Totals stay off.
- **v1 byte-identical check (`research/band_b/v1_identity.py`, `out/v1_identity.txt`):** the code before band B
  and this code give identical v1 output on every committed line pull × card date: 1,268 card runs, 76,480 game
  rows, with band B's new columns excluded. The same holds for:
  - the log view, status, tripwires and recent results;
  - the record and verification pages;
  - every Discord payload;
  - the chart statistics, the caption and both chart images.

  With band B rows added, the only differences are band B's own record section and its chart tile and line.
- **Tests:** `audit/test_band_b.py`. A 2.2-point spread signal is band B at 0.5 unit; a 2.5-point one is v1 at
  1 unit. Band B never enters v1's log view, status or forward-test signals. `python -m pytest -q audit/`: all
  passed.
- **Discord note:** `bets/announcements.json`, id `2026-10-29-band-b`.
- **New fingerprints:**

```
4b456414ae2215aba214f4989346beecef7d11eb3ee078feed7ab53025a1f81f  cbb/run_day.py
0f80f2e0a98a08acc12f754bd8976c425c72187a6b5e4def32c678764f5b2fd2  cbb/tracker.py
cd73d5f31ab149aa40c372947d368ef6fd00557ef4fcbde29f6a685886ee694d  audit/forward_eval.py
b4bce61c9074f07c41ce55128381437bc9045444e7c4fbdd3ed97a5ccd2828ee  FORWARD_TEST_PROTOCOL.md
148bea46722ffcd26aadab92282996b18ded2e6532df12aba10fbc2008624cd8  audit/test_band_b.py
```

## 2026-10-30: Odds API live credit reserve; band B labels, record line and overlap cell (Chad's decisions)

Before any game. Predictions, the selection rules, staking, band B's rule and every v1 figure are unchanged.

- **Credit reserve (`cbb/odds_api.py`, `cbb/poll_targets.py`; Chad, Oct 30):** card pulls and targeted quote polls
  may spend The Odds API down to 10,000 credits and stop below it. Before this, card pulls stopped only below 15.
  - One phone alert goes out the first time the balance falls below 20,000 (`lines/odds_api_alert.json`).
  - The 50,000 floor applies to research pulls only, all scheduled after the Nov 25 renewal.
  - At about 800 credits a day, live use is projected to leave about 25,000-37,000 credits at Nov 25 (57,637 on
    Oct 30), so neither line is expected to bind.
  - A stop can only remove pulls; it never changes how a pulled line is priced or picked.
- **Band B is spreads only, in every label:** the card block and record-page section now read "Band B (spreads, edge
  2-2.5, 0.5 u)", replacing the brief's "2-2.5 spreads, 2-3 totals" wording.
  - The card block shows band B's own season record (`tracker.band_b_status`).
  - The record page shows the band B section always, empty until the first play. Display only.
- **Overlap cell (protocol v2.3, Appendix B):** band B games later bet by v1 are reported as their own cell
  (`audit/band_b_read.py`): count, combined stake, and v1's record on them against v1 overall. If v1 wins below its
  overall rate there, the Jan 15 proposal is that a band B play blocks a later same-side v1 bet.
- **Tests:** `audit/test_band_b.py` adds the overlap case. `python -m pytest -q audit/`: 85 passed;
  `audit.card_logic`: all OK.
- **Discord note:** none. No rule, pick, stake or displayed figure of v1 changes, and band B's note already says
  spreads only.
- **New fingerprints:**

```
36d1d87e44df42889f3cfc57192b3a3ebb3a39b0e560818015d078880b586cf0  cbb/odds_api.py
ae67a70fd1200babae6a771599ec7796cefbad63e063250baabe1f2b3b7debb2  cbb/poll_targets.py
3b92a1e3908aaa3e23cb10e3c5b1ab3e00c12bfc8dcc4f1437aa114f7ff2bd0f  audit/forward_eval.py
b43ebb22ea3745b62f58bf54c1f3d5215b32898527aa54e222f107a8fed43c19  FORWARD_TEST_PROTOCOL.md
0398f07f4b3ed730d62d1be5ab6d691b9b99b61633a0c93b54abc4fa297a7bf1  audit/test_band_b.py
```

## 2026-10-30: Novig prices shown beside each play (show-only; Chad's option 2)

Before any game. Picks, the 7-book set, best-book selection, logged books and prices, stakes, alerts' picks,
grading, the quote log and every close (CLV) are unchanged.

- **Feed (`cbb/odds_api.py`):** the card's Odds API call also requests `novig` (DISPLAY_BOOKS), at no extra credit
  (8 books, up to 10 cost one region).
  - `parse()` still keeps only the 7 frozen books for the card's lines and the quote log, so Novig never enters
    `_best`, `openers.csv`, `closing.csv` or a close.
  - `parse_display()` keeps Novig apart: the latest prices go to `lines/novig_latest.csv`, and every change is
    appended to `lines/novig_log.csv` for the Jan 15 read.
- **Display:** the card shows "Novig <number> (<price>)" under each play and band B play, flagged "better price" or
  "better number" when it beats the play's number and price. The phone alert adds the same line. The odds board has a separate Novig
  column (spreads and totals), never counted in "Best" or a pick. A bet placed at
  Novig is recorded at its actual fill with the Placed button, as for any book.
- **Test pull (Oct 30, 3 credits, `data/research/books_check.json`):** key `novig` confirmed. Novig priced 1 of 7
  posted games; every sportsbook had all 7.
- **Tests:** `audit/test_novig.py` checks that Novig never reaches the card's lines or quote log, plus orientation,
  the change-only log and the labels. `python -m pytest -q audit/`: 89 passed; `audit.card_logic`: all OK.
- **Discord note:** none (no pick, rule, stake or record change).
- **New fingerprint:**

```
1df96b56a2c0d5ea43d7caf1899dc6b2adb8f776b85ae1bfbe0b13acf14d4c3d  cbb/odds_api.py
```

## 2026-10-31: Venue check of the neutral flag (reads and displays only)

Before any game. The model's neutral flag stays ESPN's, unchanged. Picks, numbers, thresholds, stakes, grading, the
card CSV and the bet log are byte-identical with the mark on and off (`audit/test_venue.py`).

- **What it does (`cbb/venue.py`, `data/home_arenas.csv`):** each game's venue is compared with both teams' home
  arenas. The result is confirmed, conflict or unknown, with "home city" and "reversed" labels.
  - The card shows a mark on every play, the phone alert gets a "Venue: …" line, and Discord gets a Venue field.
  - The check is cached in `reports/venue_<date>.csv`.
- **Findings (`research/venue/LOG.md`):**
  - November 2026 has 2 conflicts in 1,250 D-I games (0.2%).
  - On 20 conflict games over the last three Novembers, the venue-corrected flag did not beat the given one: the
    residual ran −1.72 points (SE 2.51), against the direction the correction predicts.
  - Neither data-fix trigger fires, so no flag correction is proposed.
- **Discord note:** none (display only).

## 2026-11-01: Input freshness stamp on every play (display only)

Before any game. Picks, numbers, thresholds, stakes, grading and `bets/bets.csv` are unchanged. The card CSV's
existing columns are byte-identical; the stamp only adds trailing columns (`audit/test_freshness.py`).

- **What it does (`cbb/freshness.py`):** pass-through wrappers record what each input the projection used actually
  returned, and when. That covers KenPom's DataThrough, the Barttorvik snapshot date, the injury fetch, the hoopR
  schedule and box-score download times, and the referee crew fetch. Each play's book carries this run's line pull
  time.
- **States:** a play is stale past its cadence (KenPom 36 h, Barttorvik 36 h, injuries 12 h, schedule 6 h, lines
  15 min, referees 24 h), unknown with no timestamp, else fresh.
- **Display and logging:**
  - The card shows a mark per play, the phone alert an "Inputs: …" line, and Discord an Inputs field.
  - `bets/inputs.csv` stores each logged play's stamp, keyed by bet id.
  - The Monday health line counts stale plays.
  - A feed stale for more than 24 hours sends one phone alert.
- **`cbb/run_day.py` (fingerprinted; non-picking):** installs the wrappers, stamps after pricing, logs each new
  play's stamp, and appends the trailing columns before writing the CSV.
- **Discord note:** none (display only).
- **New fingerprint:**

```
7b3e1bda77658a3c1d9e3596e5411d22ef361a3bc0e3dc64a77291beff4a9996  cbb/run_day.py
```

## 2026-11-01: Alternate-line ladder log and freshness fixes (research only)

Before any game. Picks, numbers, thresholds, stakes, grading, `bets/bets.csv` and the card CSV's existing columns are
unchanged. Plan: `research/ladder/PLAN.md` (pre-registered before any ladder was pulled).

- **What it does (`cbb/ladder.py`):** when a play is first logged (v1 or band B), the game's alternate spreads and
  totals are pulled once from The Odds API's per-event endpoint, at the play's book and the best-price book for the
  main number (2 credits). Every rung goes to `lines/ladder/ladders.csv`; the main-number and best-rung EVs go to
  `lines/ladder/plays.csv`. Never shown on the card; never changes a play; never raises.
- **Guards:** a pull reported above 2 credits switches the logger off (`lines/ladder/state.json`); no pull below
  20,000 credits before Nov 25 or the 50,000 research floor from Nov 25.
- **`cbb/run_day.py` (fingerprinted; non-picking):** calls `ladder.pull_for` after the v1 and band B plays are
  logged.
- **Freshness fixes (`cbb/freshness.py`, not fingerprinted):** a line from this run's pull takes the pull's time;
  a feed missing from the run is named ("Barttorvik: none this run (filled from KenPom)"); a feed missing for more
  than 24 hours sends one alert.
- **Discord note:** none (research only).
- **New fingerprint:**

```
3fdd80dd17933fd72e834e94a34b4d0e4caaa128bff2fdd85c778cca7bd5af5d  cbb/run_day.py
```

## 2026-10-30: Barttorvik and KenPom retry a missing answer for a recent date (approved by Chad Oct 30)

A data-fetch fix, not a model change: the frozen model was built and backtested with Barttorvik's time-machine file
for the day before each game, and this lets the live card actually get it.

- **The bug (`cbb/barttorvik.py`):** a date with no file yet was cached as missing for good. The card asks for a
  day's file before Barttorvik posts it (tonight's runs build the Nov 1-2 cards and ask for the Nov 1 file), and
  GitHub's cache carries that "missing" from run to run. Every live game so far has had Barttorvik's term filled
  from KenPom (all 121 games on the Nov 1-2 cards).
- **The fix:**
  - A missing file dated within 10 days of today is asked for again, at most once an hour, until it appears. The
    files already cached as missing heal the same way.
  - Older dates and files that exist are read exactly as before.
  - Each live run prints which Barttorvik file its games used, or why none was (including the live file's error),
    so the first in-season run shows whether GitHub's runners can reach Barttorvik.
- **KenPom check (`cbb/kenpom.py`):** the same pattern applied to FanMatch, which the card asks for on game day
  from 7:37 am ET and KenPom publishes by late morning. An empty answer for a date within 3 days of today is no
  longer cached. Every other response caches as before. No empty FanMatch file was found in the local cache; this
  is preventive.
- **Byte-identical check:** replays of 2025-11-15, 2026-01-17 and 2026-03-01 (`python -m cbb.run_day --date D
  --replay`) give byte-identical card CSVs before and after; the HTML differs only in its generated_at stamp.
  `audit/test_source_retry.py`: the retry rule, cached files read unchanged without a request, KenPom's empty
  answer for today not cached, old and undated answers cached as before.
- **Effect on live plays:** once Barttorvik posts files, games use them as the backtest did; until then KenPom
  fills, as now. Plays already logged are unchanged.
- **Discord note:** `2026-10-30-barttorvik-retry` in bets/announcements.json (added Oct 30 at Chad's request, so the
  verified record shows every change to a frozen file).
- **New fingerprints:**

```
48a9f26e5268c3a467d21cdff557bc36f1b2230f838ecd2f2fe4c4cca71cf8e3  cbb/barttorvik.py
7f7d4f58f22c7c167b43361b25237767c6a8b7557c7acd0648efbb289611b3bd  cbb/kenpom.py
```

## 2026-10-30: Barttorvik's daily file read from the repo (Chad's option 2, approved Oct 30)

The 16:10 UTC card run confirmed Barttorvik refuses GitHub's servers ("live file: failed (HTTP Error 403:
Forbidden)"). Nothing is done to get around that from GitHub. Instead:

- **`local/fetch_barttorvik.py` (runs on Chad's computer, not in the card):** three times a day it asks once for
  each of the last three dates with no file yet, five seconds apart. It keeps the four columns the model uses,
  commits them to `data/barttorvik_tm/<YYYYMMDD>.csv` and pushes. It uses the standard library only. Setup steps are
  in `local/README.md`.
- **`cbb/barttorvik.py`:** after a cached file with data, the card reads `data/barttorvik_tm/<YYYYMMDD>.csv` before
  any request. The run log names the source ("repo copy from Chad's machine" or "download").
- **Checks:**
  - The repo copy gives exactly the frame a direct download gives (`audit/test_source_retry.py`, no request made).
  - Replays of 2025-11-15, 2026-01-17 and 2026-03-01 give byte-identical card CSVs and pages against the code before
    this change (generated_at aside).
- **Discord note:** `2026-10-30-barttorvik-repo` in bets/announcements.json.
- **New fingerprint:**

```
6fc98f00663e8fcec13d2484fe8cd5df43761b0f4d77df0b7cd9aba6a66c0e95  cbb/barttorvik.py
```

## 2026-10-30: Bad-quote guards; Villanova +7.5 voided (approved by Chad Oct 30)

**What happened.** A backtest assumption leaked into live play. At 15:50 UTC the SGO feed carried a BetMGM row for
Notre Dame-Villanova (Nov 1) with the sign flipped and no price on one side: Notre Dame -7.5 (-110), where every other
book had Notre Dame +7.5. In the card's orientation that read Villanova +7.5 with no price. The model has Villanova by
7.3, so the edge was 14.8. `ev()` priced the missing price at -110, an assumption that exists because ESPN's historical
lines carry no prices. The play was logged (`2026-11-01|401920982|spread|home`), alerted and posted to Discord. It was
not placed.

- **Void:** the row stays in `bets/bets.csv` with status void, never deleted. The next run sends one CANCELLED phone
  alert and a Discord correction under the original post. The record page and chart count it in their void footers.
  The one real Nov 1 play, Notre Dame-Villanova Under 149.5 (placed), is unaffected.
- **Guard 1, no price means no play (live only):** a quote with no price on our side is skipped and logged as "no
  price". Replays of past days keep the -110 assumption.
- **Guard 2, off-market (live only):** with 3+ books quoting, a book 3+ points from the median of the other books is
  skipped and logged as "off-market", with the book's number, the median and the book count.
- **Guard 3, maximum plausible edge (live and replay):** a spread edge above 8 or a total edge above 10 is REVIEW.
  It is shown in the card's watch list as "REVIEW ... check the line", never a BET, never band B, never alerted or
  logged.
- **Skip log:** every skip goes to `lines/bad_quotes.csv`, once per quote, for the Nov 16 execution read (how often
  each guard fires, and at which book).
- **Season scan (`python -m audit.guard_scan`, `audit/out/guard_scan.csv`):** all 10 bets logged so far (v1; no band
  B yet), each with the books as the card saw them when it logged the bet. Only the Villanova +7.5 bet is caught, and
  it trips all three guards.
- **History, guard 3 (live-like frame, swapped records out):**
  - Spreads: 46 of 4,195 decided spread plays had an edge above 8 (22 in 2014-17, 24 in 2024-26). Without them, the win rate
    goes from 56.8% to 56.6% (2014-17) and from 57.8% to 57.5% (2024-26).
  - Totals: 87 of 7,219 decided total plays had an edge above 10. The win rate is unchanged (57.6% and 55.8% to 55.7%).
  - Many of these were bad ESPN openers rather than real disagreements: in 2024-26, 79% of the over-8 spread openers
    moved 5+ points by the close, and 9 of 24 sat on the opposite side of zero from the close (the same sign-flip
    defect).
  - Season 2014 totals (outside both eras) has 1,981 such plays: that season's model totals sit about 11 points under
    the line, a first-season artifact already excluded from the eras.
- **Checks:**
  - `audit/test_bad_quotes.py` covers each guard with the real BetMGM row, the replay -110 path and the skip log.
  - Replays of 2025-11-15, 2026-01-17 and 2026-03-01 give byte-identical card CSVs. The pages differ only by the three
    lines of REVIEW display code.
- **After the Nov 24 switch to The Odds API, the guards stay on.**
- **Discord note:** `2026-10-30-bad-quote-guards` in bets/announcements.json.
- **New fingerprint:**

```
b171aa8410e202e87361a4a61aee18c163fc23ff3a3d8920ac3562e29b9164d6  cbb/run_day.py
```

## 2026-10-30: Barttorvik answer that is not a ratings file no longer stops the card (fix to the retry above)

The retry for recent dates (this morning's entry) exposed an unguarded parse. At 18:20 UTC Barttorvik answered a
recent date with a page that was not JSON (status 200, probably a bot-check page), and the card run crashed before
building anything. That run's card, alerts and logging were skipped; the 18:30 run built normally. (Its separate
failure was GitHub Pages' own deploy step: "Deployment failed, try again later.")

- **Fix (`cbb/barttorvik.py`):**
  - An answer that is not a ratings file is treated as missing. A recent date is marked missing, so it is asked again
    at most hourly; an older one is not cached.
  - Any other Barttorvik failure during a run is printed, and KenPom fills, as it does for any missing file.
  - Nothing is done to get past the page itself.
- **Checks:**
  - `audit/test_source_retry.py` tests a non-JSON 200 answer and a failing lookup.
  - Replays of 2025-11-15, 2026-01-17 and 2026-03-01 give byte-identical card CSVs.
- **Discord note:** none. No play was affected: the crashed run logged nothing, and no new play appeared on the next
  run.
- **New fingerprint:**

```
b4e9fdbc9320906e3ab26397a9978fd66608a219b25bf874d7e7f8880102ceb7  cbb/barttorvik.py
```
