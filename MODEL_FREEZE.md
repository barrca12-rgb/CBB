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

## 2026-10-31: A qualifying quote is never passed over; missed-play safety net (approved by Chad Oct 31)

**What happened.** On Liberty at High Point (Nov 1, neutral; model High Point by 9.3), DraftKings and Caesars had
High Point -6.5 at -110: edge 2.8, EV +9.0%, a full play. theScore had -7.5 at +100, EV +9.07%, by 0.09 points the
higher. The card chose the single highest-EV quote and then judged its edge, 1.8, so the game fell to WATCH.

This is a live multi-book selection flaw. The backtest priced one line per game and never met it. A scan of the
Nov 1-2 cards found this one case.

- **Fix (`cbb/run_day.py` `_best`):** quotes are ranked in tiers, then by EV within a tier (then edge, then the
  preferred book):
  - first, quotes that make a BET (cutoff edge and +2% EV at that book's price);
  - then, quotes that make band B;
  - then, the rest (the WATCH display);
  - an edge above MAX_EDGE (REVIEW) ranks below all.

  When nothing qualifies, the choice is unchanged.
- **Safety net (`cbb/card_features.py`, the unfrozen wrapper):**
  - On every card run, every book's quote is re-checked independently of `_best`: cutoff edge, +2% EV, a real
    price, not off-market, not above MAX_EDGE.
  - A qualifying quote on a game and market the card does not play is written to `lines/missed_plays.csv` and sends
    one phone alert per game, market, book and number.
  - With the fix in place it should never fire; if it does, it is a bug, known within one run.
- **Checks:**
  - `audit/test_bad_quotes.py` uses the real High Point quotes: the qualifying quote wins at DraftKings -6.5; with
    nothing qualifying, the highest EV still drives WATCH; the safety net flags the Oct 31 card and stays silent on
    the fixed one.
  - Replays of 2025-11-15, 2026-01-17 and 2026-03-01 give byte-identical card CSVs.
  - 128 tests pass; the card check is OK.
- **Effect:** High Point -6.5 (DraftKings) becomes a play on the next run. No other current game changes.
- **Discord note:** `2026-10-31-qualifying-quote` in bets/announcements.json.
- **New fingerprint:**

```
d3b2ead5ef56cf6c4fa0c5426b3ab32384e964c24dc39022927963e21fdd5d6d  cbb/run_day.py
```

## 2026-10-31: Every play is logged as placed; the Placed option is removed (Chad, Oct 31)

Chad bets every play, so marking placed by hand was redundant.

- **`cbb/tracker.py` (fingerprinted):** `log()` and `log_band_b()` write `placed = "yes"` on every new play (was
  blank). Picks, lines, stakes, grading and the record are unchanged: the record already counted every play not
  marked "no" (`record_page`), and so did the execution tripwire.
- **Backfill:** the 55 open plays logged with a blank `placed` (40 v1, 15 band B) are set to "yes". Voided plays
  are untouched.
- **Card:** the Placed button, its dialog and `.github/workflows/placed.yml` are removed. "Bet to" shows the number
  again instead of "Placed".
  - `cbb/placed.py` stays, so a fill that differs from the alert can still be recorded by hand from the session
    (`bets/accepted.csv`, cohort C).
  - Without the button, cohort C only fills when Chad reports a different fill.
- **Card check:** `audit/card_logic.py` counts logged bets per bet type, since a band B play later joined by v1 on
  the same game is the approved overlap.
- **New fingerprint:**

```
4f4966cc0ee43f9b86200db7bab6e9b85ad6c663476ea75360fc16756b9390b7  cbb/tracker.py
```

## 2026-11-01: The card builds the whole coming week every run (Chad, Oct 31)

"Build out the week of games so we are ready when lines drop."

- **`cbb/run_day.py` `main()` (fingerprinted; non-picking):** an `--auto` run now builds each of the next 7 days that
  has games, whether or not books have posted lines. Before, only days that already had lines were built.
  - A day's model numbers are on the site before books post.
  - A day's first lines are priced, and any play logged, on the first run that sees them, exactly as before.
  - A day whose ESPN schedule fails to load is skipped for that run only.
- **`cbb/card_features.py` (the card's unfrozen wrapper):** the live fetches each day's build repeats (KenPom's
  current ratings, the injury report, the lineup downloads) are made once per run and reused. Within one run they
  return the same data, so results are unchanged.
- **`cbb/report_html.py` (display):** the day bar shows yesterday, today and the coming week.
- **Unchanged:** picks, rules, staking, the bet log and grading. Replays are untouched (the replay path does not
  build ahead).
- **Tests:** `audit/test_week_ahead.py` covers the seven-day loop (a day with no games or a failed schedule is
  skipped) and that each repeated fetch happens once per run.
- **New fingerprint:**

```
14f7260346b9ef6082ade27d826ac83547365bacaa62c002fe0099105c69e899  cbb/run_day.py
```

## 2026-11-01: The site refreshes itself (Chad, Nov 1)

"Wish the site would auto refresh."

- **Display only, no frozen file changed:** `cbb/autorefresh.py` (new), `cbb/report_html.py`, `cbb/record_page.py`.
  - Each card and the record page carry their build time.
  - While a page is on screen, it checks the published copy a few seconds after it opens, every 3 minutes, and
    whenever the tab or phone app comes back into view. If the published copy is newer, the page reloads itself.
  - The scroll position, the odds-board tab (Spread / Total / Moneyline) and "Plays only" are kept. The play sort
    was already remembered.
  - It never reloads while someone is typing. If a reload lands on an older cached copy, it waits 10 minutes before
    trying again. Replay cards have no auto refresh.
  - The "Updated … ago" stamp now counts up while the page is open.
- **Unchanged:** picks, rules, staking, the bet log, grading and alerts.
- **Tests:** `audit/test_autorefresh.py` serves a real card in Chromium and checks five things:
  - no reload when the build is the same;
  - a reload when a newer build is published, with the tab, the filter and the scroll kept and a clean URL;
  - a back-off after landing on an older copy;
  - no auto refresh on replay cards;
  - auto refresh on the record page.

  `audit/card_logic.py` renders cards without it.

## 2026-11-01: Notre Dame-Villanova Over 146 voided (Chad, Nov 1)

"Remove the Notre Dame over as a loss from the record. We already had the under; we didn't play both spots."

- **What happened:** Under 149.5 (DraftKings -110) was logged on Oct 25 under the pre-Oct 26 model, with a total
  of 139.8.
  - After the Oct 26 update the model had 149.4, so at 146 the card called the Over. It logged Over 146 (Fanatics
    -110) at 12:30 UTC on Nov 1 and alerted it.
  - The bet log blocks a repeat of the same bet id but not the other side of a game it already holds.
  - Final 74-70 (144): the Under won and the Over lost.
- **Void:** the Over 146 row (`2026-11-01|401920982|total|over`) stays in `bets/bets.csv` with status void, never
  deleted. Its grade (L, -1.0) and close fields are cleared.
  - The next run posts the Discord correction under the original post.
  - No "don't bet it" phone alert, since the game is over (`bets/void_alerted.json`).
  - Record: 1-0, +0.91 units (it was 1-1, -0.09).
- **Unchanged:** the Under 149.5 and its CLV (+4.00), picks, rules, staking and every frozen file.
- **Open:** the logging gap itself (an opposite side can still be logged). A guard in `cbb/tracker.py` waits on
  Chad's approval.

## 2026-11-01: The other side of a held game is never logged (approved by Chad, Nov 1)

"Yes add it" (the guard proposed after the Notre Dame-Villanova Over 146 was logged against a standing Under 149.5).

- **`cbb/tracker.py` `log()` (fingerprinted; non-picking):** a v1 play is not logged when the bet log already holds
  the other side of the same game and market.
  - "Held" means any bet that is not void: a v1 bet or a band B play.
  - The same side is not blocked, so a band B play later joined by v1 on that side remains the approved overlap.
  - A void bet does not hold a game, and the other market of the same game is not affected.
  - Band B's own logging already skipped any game and market v1 holds, and it is unchanged.
- **`cbb/report_html.py` (display):** the blocked side is never shown as a BET, a watch or a play. The held side
  shows as logged, as before.
- **`audit/card_logic.py`:** expects the same. Its data check now also flags a game with both sides held.
- **Unchanged:** picks, thresholds, staking, alerts and grading. Every bet already in the log is unchanged.
- **Tests:** `audit/test_opposite_side.py` covers eight cases:
  - a held Under blocks a later Over, and a held spread side blocks the other side;
  - band B blocks the other side, but the same side still joins band B;
  - a void bet does not block, and the other market is not blocked;
  - the real log blocks a fresh Over on Notre Dame-Villanova;
  - the card shows no BET on the blocked side (this case fails without the display change).

  All 147 audit tests pass.
- **Also today (display only):** the record page is wider and fits without sideways scrolling. Its play tables
  have result and market filters, sortable column headers and a running total (`cbb/record_page.py`,
  `audit/test_record_page.py`).
- **New fingerprint:**

```
4d1e03a599bc859019c077e3dc0348ed65a19a2a7ae7fed9bfde42683d713447  cbb/tracker.py
```

## 2026-11-01: Novig removed from the card (Chad, Nov 1)

"You can remove Novig."

- **`cbb/report_html.py` (display only):** the card no longer shows Novig anywhere: not the odds-board column, the
  watch list tiles, or the line under each play.
  - Novig was show-only (Oct 30, option 2) and never fed picks, Best or CLV, so nothing else changes.
- **Unchanged:** `cbb/odds_api.py` (frozen) still requests Novig in the same card call, at no extra credit cost.
  Removing that request would be a frozen-file change, and it costs nothing to keep.
- **Tests:** `audit/test_same_layout.py` checks two things:
  - every date on the site, today through the coming week, has the same layout once its own data is set aside;
  - Novig is gone from the template.

## 2026-11-02: Opener rule (approved by Chad, Nov 2, option 1; protocol v2.4)

From this run on, the card logs only plays that the frozen model would have made at the opener.

- **Rule (`cbb/run_day.py`, fingerprinted):** a live signal is logged only if it also qualifies against the game's
  opener with the current model. The opener is the best of each book's first quote on our side, from
  `lines/moves.csv`, with `lines/openers.csv` for the earliest sightings. It must clear 2.5 / 3.0 (2.0 for band B)
  and +2% EV at the opener's price.
  - A signal that fails is research only (`research/linemove/signals.csv`): not logged, alerted, posted or bet.
  - A first quote without a price is skipped, never assumed. With no usable first quote at all, the signal stands.
  - The rule only gates: the number bet is unchanged. A watch the rule would stop is not shown as a watch.
  - Full text: `FORWARD_TEST_PROTOCOL.md` Appendix C. `run_day.OPENER_RULE` is the switch the replay check turns off.
- **Plays already logged (`cbb/tracker.py`, fingerprinted; `audit/forward_eval.py`, fingerprinted):** the 38 that
  fail the same test as of their own logging time are listed in `bets/linemove_prerule.csv`: 31 v1 (13 spreads,
  18 totals) and 7 band B. They stay in `bets/bets.csv` as logged.
  - `tracker.load` and `forward_eval.load_signals` read them as their own cell, `linemove`. v1 and band B (the
    record, CLV, stake cap, tripwires, reviews) exclude them.
  - The card shows them in their own block. The record page and weekly chart give them their own line and tile.
  - The research cell is graded by `cbb/linemove.py`.
- **Unchanged:** thresholds, the EV rule, the win-probability rule, stakes, books, the log format and grading.
- **Evidence** (`research/linemove/out/backtest_split.txt`): plays that qualified only after an adverse move won
  50.1% (spreads) and 48.4% (totals) in 2024-26, against 57.8% and 55.8% at the opener. The 0.5-1 point band was
  below 54% in both eras, so there is no tolerance.
- **Replay** (`research/linemove/out/replay.txt`): rule off vs on, from the repo's own history.
  - Byte-identical on three runs with no line-move play: Nov 1 card at Oct 31 13:51 and Nov 1 06:02, Nov 2 card at
    Oct 27 02:50 (231 plays).
  - The Nov 1 19:22 run: exactly 9 plays removed, none added.
- **Coverage** (`research/linemove/out/coverage.txt`): 92 of the 99 lined games on the card have every book's first
  quote in `moves.csv`.
  - 6 games posted Oct 25-26, before `moves.csv` began: DraftKings and Caesars are skipped (first number, no price).
  - In 1 game, BetMGM's first quote is missing.
  - The other books carry the test in all 7.
- **Tests:** `audit/test_opener_rule.py` (12): qualified at the opener, qualified by a model move, line-move only;
  missing first quotes; band B; totals; watches; replays.
  - The selection tests in `audit/test_bad_quotes.py` and `audit/test_band_b.py` run with the rule switched off.
  - All 154 audit tests pass. The card check passes on every day.
- **Discord note:** `bets/announcements.json` "2026-11-02-opener-rule".
- **New fingerprints:**

```
78c62cd16f6d9710937da16f930f2d5cdde541d5d904272eaa714244dc1b38d4  cbb/run_day.py
20225ab64eb8b619ad763ab31b8edb87d9f6018a48b81237c53c8b74a84373a1  cbb/tracker.py
b137cda36e7f459c127bc4316adb8e1589ca6bfba9c6124ce07c5557b54ac22a  FORWARD_TEST_PROTOCOL.md
e6fe6f6b690c2da50e22b649752a4e5c826bbb4f0514df4916167913ad9be856  audit/forward_eval.py
5f6eafc20f6c09bd891cc1a160dc5d11bf71b9c4f52880be7a8872136793289c  audit/test_band_b.py
```

## 2026-11-02: Opener rule, research log saved (operational fix, same approval)

- **What went wrong:** the first card run on the rule (01:07 UTC) wrote `research/linemove/signals.csv` on the
  runner. `.github/workflows/update.yml` commits only `reports`, `lines`, `bets`, `injuries` and the Barttorvik
  files, so the file was dropped.
- **`.github/workflows/update.yml` (fingerprinted):** the commit step adds `research/linemove`.
- **`cbb/run_day.py` `log_linemove` (fingerprinted; research log only):** a game and market the log already holds
  (any bet not void) is not written. The rule stopped nothing there, because the log would refuse it anyway.
  `FORWARD_TEST_PROTOCOL.md` Appendix C says so.
- **Nothing was lost.** `research/linemove/backfill.py` replayed the 8 card runs since 01:06. Each of their 15
  stopped signals was on a game already held: 14 by pre-rule line-move plays and 1 by a v1 play. So the research
  cell is correctly empty so far.
- **Unchanged:** picks, the gate, the bet log, stakes and alerts.
- **Tests:** `audit/test_opener_rule.py` adds the held-game case (13 tests). `audit/test_same_layout.py` checks
  today and the coming week, since past days are never rebuilt.
  - 154 of 155 audit tests pass on the full run. The 155th, `test_band_b.py::test_v1_figures_ignore_band_b_rows`,
    failed once on a stake-cap `refreshed_at` second boundary and passed 3 of 3 reruns.
- **Discord note:** `2026-11-02-opener-rule-log`.
- **New fingerprints:**

```
74ea3a8b427daeba8ee0033c305d4a7249c8d8825d13c14804647403e7504793  cbb/run_day.py
92a8c380ef4d34198c0bd62668b22013d39116720067682b6e3770f4a85e28fa  .github/workflows/update.yml
101cdcc777b24dd06a5900aa01e17755d75cda2f24ecce3aff964a0325f28f1d  FORWARD_TEST_PROTOCOL.md
```

## 2026-11-02: Notifications carry main plays only (Chad, Nov 2)

"Only main plays in the notifications, no band B or line moves."

- **`cbb/run_day.py` (fingerprinted):** a new band B play is logged as before, with no phone alert and no Discord
  post.
- **`cbb/tracker.py` `alert_voided` (fingerprinted):** cancellation alerts go out for main plays only.
- **`cbb/record.py` (Discord):** posts main plays only, as `tracker.load("v1")`: each play when logged, its
  result, voids and reinstatements. Band B and the pre-rule line-move plays are never posted.
- **`cbb/injury_watch.py`, `cbb/tipcheck.py`:** injury and tip-time alerts are for main plays only. The tip check
  still checks and logs every open bet.
- **Unchanged:**
  - Band B and line-move plays are still logged, graded and shown in their own sections on the card and the
    record page.
  - The official record already excluded both, checked by marking one of each a win on a copy of the log: the
    record, card tiles, record page, weekly chart, recent results and stake sizing did not move.
  - Picks, rules and staking.
- **Tests:**
  - `audit/test_notifications.py`: Discord, cancellation alerts and the band B path.
  - `audit/test_band_b.py`: its v1-unchanged check ignores the stake cap's clock-time `refreshed_at`, which had
    made it fail when a run crossed a second.
  - All 158 audit tests pass.
- **Discord note:** `2026-11-02-main-only`.
- **New fingerprints:**

```
a8632b5516e7eff8579e2b454208b5bd6761f90bfb82086a8bb69abf91f9c773  cbb/run_day.py
17633634506b05b3b145865a36c244cf98e99697aadb7bb1d7f4589ada9953b8  cbb/tracker.py
32ee4b3a2ba9df3ca86ce81f63a3a2909f00c729ddc0d1757426959786e1a4fc  audit/test_band_b.py
```

## 2026-11-02: Barttorvik access, whitelisted by Bart Torvik (Chad, Nov 2)

Bart Torvik replied to Chad's request (Nov 1): a request whose User-Agent includes the string he gave is
whitelisted. This is his sanctioned access path. Before it, GitHub's runners were refused, and the card kept using
the Oct 31 file.

- **`cbb/barttorvik.py` (fingerprinted):** the time-machine and live-ratings requests add the string to the
  User-Agent (`headers()`).
  - The string is the repo secret `BARTTORVIK_UA_TOKEN` (added by Chad), never in this public repo; a test checks
    that.
  - With no secret set, every request is byte-for-byte as before.
- **`.github/workflows/update.yml` (fingerprinted):** passes the secret to the card build, like the other keys.
- **`local/fetch_barttorvik.py`:** uses the string too when it is set on Chad's machine. That fetcher should no
  longer be needed.
- **Not a model change.** The protocol already defines Barttorvik as the newest non-empty time-machine file in
  the 7 days before the card day, else the live file. This restores that input, so `bt_margin` and `bt_total` move
  from the Oct 31 file to the newest one. Picks, rules, staking and the record are otherwise unchanged.
- **Tests:** `audit/test_barttorvik_ua.py` covers the string sent when the secret is set, unchanged without it, and
  not in the repo. No network is used. All 161 audit tests pass.
- **Discord note:** `2026-11-02-barttorvik-access`.
- **New fingerprints:**

```
a5a849f6f7ab7bd2450a51ba9b053770afd9864acf952d6cf072b7171981dc97  cbb/barttorvik.py
9a8704d4be0130821134c525ce94bce6d519e456d4ecdb2e355f55e601ed3a9d  .github/workflows/update.yml
```

## 2026-11-02: Injury timing report and injury-check save step (operational fixes, Chad, Nov 2)

- **`cbb/injury_sources.py` (fingerprinted; report only):** the timing report (`injuries/sources/timing.md`) failed
  on every run from 17:30 UTC on. Two jobs had pulled ESPN in the same second, so `health.csv` held two ESPN rows
  with one stamp, and `_online` could not look the stamp up. It now keeps the larger ESPN count per stamp.
  `_online` feeds only the timing report and the source recommendation, which never switches the source on its own.
- **`.github/workflows/injuries.yml` (not fingerprinted):** the 23:10 UTC injury check sent its alert, then failed
  to save. Another tracked file had changed outside `injuries/`, so `git pull --rebase` refused on all 6 retries.
  The save step now lists any such file in the log and drops it before pulling. The job only ever saves
  `injuries/`. The alert's record was saved by the 23:12 card run, so nothing was lost.
- **Unchanged:** the injury source (ESPN), the alerts, picks, stakes and the record.
- **Test:** `audit/test_injury_timing.py`. The duplicate-stamp case fails on the old code and passes on the new.
- **Discord note:** `2026-11-02-injury-housekeeping`.
- **New fingerprint:**

```
c779e188f209c32f11ae15eff7439443f44d4d003b7e7cef5d36ee3b18dcebc8  cbb/injury_sources.py
```

## 2026-11-02: Spread CLV read from the wrong team at some neutral sites (bug fix; Chad, Nov 2)

- **What went wrong:** the quote log labels spread sides by the odds feed's home team. ESPN, which the bet log uses,
  can name the other team at a neutral site. The close was then read from the wrong team. Florida -5.5 (Miami vs
  Florida) showed close +6.5 and CLV -12.0; the close was Florida -6.5, CLV +1.0.
- **`audit/forward_eval.py` (fingerprinted; the protocol's own close code):**
  - `load_obs` adds `feed_home`: the team id of each feed event's "home" side. It comes from `lines/moves.csv`,
    which records the lower-id team's spread by team id: a "home" quote equal to it at the same book and time
    means the lower id, its negative means the higher id. It takes the majority over the event's quotes.
  - `orient` relabels a game's spread quotes from the bet's home team. It is used by the close (`assess`), the
    execution check and, through `cbb/clv_primary.py` and `audit/clv_example.py`, everything the site shows.
  - The close rule itself (books, window, ages, median) is unchanged.
- **Scope:**
  - Of 114 feed events, the feed's home team differs from ESPN's in 8, all neutral sites. It matches in all 100
    true home games.
  - Bets whose primary close changed: Florida -5.5 (open; -12.0 to +1.0), Purdue +4.5 (open; +10.0 to -1.0) and
    Villanova +7.5 (void, excluded).
  - No settled main play changed: the official record, its CLV average, the tripwire and every Discord post stand.
  - Totals are unaffected.
- **Tests:** `audit/test_clv_orientation.py`.
- **Discord note:** `2026-11-02-clv-orientation`.
- **New fingerprint:**

```
ad963b313e7e36af173dc366089760bc1a18f175a45322d6007d5cdc91f77112  audit/forward_eval.py
```

## 2026-11-02: Tip-time conflicts settled by the actual tip (protocol v2.5; Chad, Nov 2)

- **What was open:**
  - Five plays tonight had the feed's start 15 to 40 minutes after ESPN's. Two were "conflict", three "review".
  - 47 closes were "unverified" and 23 had "in-play risk": the actual tip was fetched only once a play was graded.
  - A game still in progress was rejected as "shorter than 60 minutes".
  - Where the real tip came before the feed's start, the close could include in-play quotes (Over 148.5: feed
    01:30, tip 01:19; Alcorn State +31.5: feed 01:45, tip 01:32).
- **`cbb/tipoff.py` (not fingerprinted):**
  - The actual tip is fetched for every open play's game that ESPN shows as started, every 5 minutes until found,
    as well as for graded plays.
  - A game in progress keeps every check except the 60-minute minimum length.
- **`audit/forward_eval.py` (fingerprinted):**
  - `tip_cutoff` takes the verified actual tip ("jump ball" quality only) when it is earlier than the scheduled
    cutoff; a later tip never moves the cutoff. It is used by the close and the execution check.
  - `PROTOCOL_VERSION` is "2.5" (it still read 2.3).
- **`cbb/clv_primary.py`:**
  - The start checks compare the scheduled cutoff.
  - A play whose actual tip is known reads "resolved" instead of "review" or "conflict".
  - The reason line names an actual-tip cutoff.
- **`FORWARD_TEST_PROTOCOL.md` (v2.5):** section 7 states the actual-tip cutoff and the spread-sides rule.
- **Result on tonight's log:** pregame verified 39 to 93, unverified 47 to 4, in-play risk 23 to 3 (games not yet
  tipped).
  - Over 148.5 and Alcorn State +31.5 close at their actual tips ("resolved").
  - Ohio State and Florida A&M resolve when they tip.
  - No settled main play's close changed: the record, tripwire and Discord posts stand.
- **Tests:** `audit/test_tip_cutoff.py`.
- **Discord note:** `2026-11-02-tip-cutoff`.
- **New fingerprints:**

```
c4040ab035bd573aad7bd3ff977500ae48a5e437b9d4d16f405ad9e6c4fffb50  audit/forward_eval.py
63dff849dc7bcb865fbe9a6e3afeba8046053ce72a2bb4405d32feb5c414970b  FORWARD_TEST_PROTOCOL.md
```

## 2026-11-02: Plays graded by team when ESPN relists which team is home (bug fix; Chad, Nov 2)

- **What went wrong:**
  - Purdue +4.5 (Purdue vs Gonzaga, neutral site) was logged on Oct 26 while ESPN listed Purdue at home. ESPN later
    listed Gonzaga at home. The bet log keeps the play as "home side, Purdue".
  - The grader read ESPN's home score as Purdue's, so a Gonzaga win by 6 would have graded Purdue +4.5 a win.
  - The card applied the model's Gonzaga number to the play: a now-edge of +8.0, where the true one is +1.0.
- **`cbb/tracker.py` `settle` (fingerprinted):** when the scoreboard names the bet's away team as home, the scores
  are swapped, so a play is always graded from its own team. Every other play grades exactly as before.
- **`cbb/report_html.py` (display) and `cbb/linemove.py` (research):**
  - The card shows a relisted logged spread from the card's side and recomputes its now-edge, win chance and EV
    for the team actually bet; the bet id keeps the side it was logged under.
  - The line-move research grader swaps relisted scores the same way.
- **Scope:** one play, Purdue +4.5 (open while this was fixed). No graded play changed.
- **Tests:** `audit/test_relisted_home.py`.
- **Discord note:** `2026-11-02-relisted-home`.
- **New fingerprint:**

```
2236dc3da92cdefd81dd216c7782f5b2cf8eb6e3a44b0f056c3727fd56cdbfed  cbb/tracker.py
```

## 2026-11-03: Closing lines collected for every play (logging; Chad approved the extra SGO pulls, Nov 3)

The audit of every play's CLV (`audit/clv_audit_all.py`) found two collection gaps: 7 of 132 graded plays had no close.
Every close that was collected matched the site to the decimal (125 of 125).

- **Games a feed starts after midnight ET (1 play: Hawai'i-Seattle U, 11:59 pm ET on ESPN).** The quote log files a
  game under the ET date of the feed's start, so this one was filed under Nov 3 while the bet was dated Nov 2. The
  pre-tip polls never watched it, and the close could not find its quotes.
  - `cbb/quotelog.py` (fingerprinted, logging): `watched_games` also matches the next day's key.
  - `audit/forward_eval.py` (fingerprinted): `game_obs` reads a bet's key and the same teams' key one day later.
    It is used by the close and the execution check, and through `cbb/clv_primary.py` and `audit/clv_example.py`.
- **Games only SportsGameOdds carries (6 plays on Nov 2).** The 3-minute pre-tip polls use The Odds API, and SGO was
  pulled at most every 25 minutes, so no quote landed in the final 15 minutes.
  - `cbb/poll_targets.py` (fingerprinted, logging): a game in its last 20 minutes with no Odds API quote is polled
    from SGO by event id, one entity per game.
  - If SGO returns far more events than asked, the poll stands down and logs it.
  - `cbb/odds.py` (fingerprinted, logging): `fetch(event_ids=...)`. The card run never passes it.
  - `.github/workflows/quotes.yml` (fingerprinted): passes `SGO_API_KEY`.
  - SGO's 95% monthly stop still applies.
- **Unchanged:** the card, picks, staking, the close rule itself and the bet log. Plays already graded without a
  close stay "no close": their quotes were never collected, and the protocol never substitutes `closing.csv`.
- **Tests:** `audit/test_close_coverage.py`. All 192 audit tests pass.
- **New fingerprints:**

```
121af7536c03dd577cbc1d1942711175e39b820f4f65ee1443c4157a59391302  audit/forward_eval.py
99f034f70be0a0ff4b40bf185da4d513faca71f8bed2c1506fd2a09efcd8a03d  cbb/quotelog.py
e39b5c9f0718696bce4e2250034543219f77b4bc5226c57f9fb1f4053257fb42  cbb/poll_targets.py
afdf2c2e24e68904e25b85e6caf43c3a11dc07e1f7b3a95ad4369f7cc50d7c36  cbb/odds.py
c21b8b7367e66c4e701a03a2eb73c4df3a5c8e3ada02146c985bcf43fe52b20d  .github/workflows/quotes.yml
```

## 2026-11-04: Complete-ratings rule built, switched off pending Chad's decision (protocol v2.6 Appendix D)

- **Approved by Chad (Nov 4).** A play for a game on ET date D logs and alerts only once the ratings include every
  game before D: from 6 am ET on D with Barttorvik's file for D-1 in use, or from 10 am ET if Barttorvik has not
  posted it. Before that it shows as pending on the card.
- **`cbb/run_day.py` (fingerprinted):** `ratings_ready` and a gate in `plays()` beside the opener rule
  (`RATINGS_RULE`). With the switch off, selection is unchanged.
- **`cbb/report_html.py`:** a "PENDING" tag for gated signals.
- **Tests:** `audit/test_ratings_rule.py`. `audit/conftest.py` keeps the clock-dependent rule off in other tests.
  All 196 audit tests pass.
- **Why it is off.** Before switching it on, the promised check of live plays (Nov 2 to 3) was run:
  - early plays that would not qualify the next morning: CLV +2.13, 72% beat the close (25 plays);
  - early plays that still qualify: +1.66, 67% (57);
  - plays logged on game day: -0.22, 20% (15).
  - The market moved toward the early numbers. Switching it on now would drop the strongest-CLV plays and move the
    rest to later, worse numbers. Chad decides; it is a one-line switch.
- **New fingerprints:**

```
dbde82c9455c32510b675f8b7e594f35e9cc0f71f76ae321c26974623af8dcb0  cbb/run_day.py
d4cbbc9931bf8a57ae77532ebe50fd6b5e17d8e333ca0fc738c6beaad84af666  FORWARD_TEST_PROTOCOL.md
```

## 2026-11-04: Input snapshots per alert and the morning shadow (logging only; Chad, Nov 4: "Go ahead with 1-3")

**Unchanged:**
- Live selection, thresholds, staking, alerts, Discord posts and the bet log.
- The complete-ratings rule stays off (`run_day.RATINGS_RULE = False`).
- No fingerprinted code file changed.

**`cbb/snapshots.py` (new).** Every logged play gets one row per input in `bets/input_snapshots.csv`:
- the input and its source;
- its date label;
- the sha256 of the exact table;
- where the table is stored;
- retrieval time;
- first observed by our system (`bets/snapshots/seen.csv`, written every run);
- `provider_published_at` = unknown;
- code and model version.

Where the tables are kept:
- Public tables (Barttorvik, stage-1 ratings, injuries, referees, market context, features, the play's quotes) are
  stored once per hash under `bets/snapshots/`.
- Licensed KenPom tables stay out of the repo. They are kept in the private runner cache `cbb/cache/snapshots/`,
  which is not permanent (`audit/TIMING_AUDIT.md` section 5).

**`cbb/morning_shadow.py` (new).** The pre-registered morning shadow (`research/morning_shadow/PLAN.md`). One
decision per game and market on game day, copied from the live card's own output at the first morning run with
updated inputs, to `bets/shadow_morning.csv`. It logs no play and sends nothing.

**`cbb/card_features.py`** installs both hooks in the card run. They pass every result through unchanged, and a
failure prints and continues.

**`FORWARD_TEST_PROTOCOL.md` Appendix D:** a status paragraph:
- the rule stays off;
- the morning shadow's Jan 15 read is descriptive and its Mar 14 review is the decision;
- the weekly early-plays read is description only (the 40-close trigger is withdrawn).

**Also:**
- `audit/TIMING_AUDIT.md`: the timing audit.
- Tests: `audit/test_snapshots.py` and `audit/test_morning_shadow.py`.
- Discord note: `2026-11-04-input-snapshots`.

**New fingerprint:**

```
e8c9fa8e8eeca99904904a8fc53949956946d037f0b4077495e1247275add259  FORWARD_TEST_PROTOCOL.md
```

## 2026-11-04: Box-score failure holds plays instead of silently rating on the preseason prior (Chad, Nov 4)

- **Before.** If the box-score download failed after the season started, `run_day.project` caught the error with
  no message. It rated every team on the preseason prior alone, zeroed market context, and still logged and alerted
  plays.
- **Now** (`run_day.load_box_scores`):
  1. A failed download falls back to the last downloaded copy, which is still valid input, with a log line.
  2. Only if no valid copy loads, and games have been played, the card day is held (`INPUT_HOLD`). A qualifying
     play shows on the card as "HELD" and is not logged, alerted or posted. The missed-play safety net skips it.
     One phone alert per held day says what failed and which plays are held.
  3. Before the season's first game, no box scores is normal and holds nothing.
- **Unchanged.** A source that has not published yet never holds anything, and every other selection rule is the
  same.
- **Tests:** `audit/test_input_hold.py`. Discord note: `2026-11-04-input-hold`.
- **New fingerprint:**

```
c3772c044b4754b2616b4db93f80d2fd860df88bd2bde90e478ecd7857980983  cbb/run_day.py
```

## 2026-11-04: Card run retries a busy site publish instead of failing (operational)

- **Problem.** GitHub Pages takes one publish at a time. When a live-results refresh was still publishing, the card
  run's own publish failed with "in progress deployment": 4 runs on Nov 3 and 2 on Nov 4 (18:50 and 19:00 UTC).
  The card, bet log and alerts were already saved, but the run showed as failed and the shadow tests skipped that
  cycle.
- **Fix in `.github/workflows/update.yml`.**
  - The publish step is retried after 45 seconds, then after 90 more.
  - If it still cannot publish, the run logs a warning instead of failing.
  - The next refresh or card run publishes the site.
- **Unchanged:** picks, logging, alerts and every other step.
- **Discord note:** `2026-11-04-site-publish`.
- **New fingerprint:**

```
00664478f36d8d34125c6d63cc0946ffe8fc30ec03c4b918deebca4e590809ca  .github/workflows/update.yml
```

## 2026-11-05: BetRivers shown on the odds board; bet365 removed (display and book list)

- **BetRivers (Chad, Nov 5: "add bet rivers to the odds board for plays").**
  - `cbb/odds_api.py` requests `betrivers` as a show-only book (DISPLAY_BOOKS, beside Novig) in the same card call.
    The call stays within one region, so it costs no extra credits.
  - Its prices go to `lines/novig_latest.csv` only. They never reach the card's lines, the quote log or a close,
    so BetRivers never picks a play, sets its book or number, or enters CLV.
  - The card's odds board has a BetRivers column, and it appears in line shopping ("Also:") and the "Best" cell.
  - `display_quote` takes a `book` argument; the phone alert's Novig line stays Novig only.
- **bet365 (Chad, Nov 5: "remove bet365").** Removed from both feeds' book lists (`cbb/odds.py`,
  `cbb/odds_api.py`) and from the board. Neither feed ever returned a bet365 price (no rows in any line file), so no
  play, number or close changes.
- **Tests:** `audit/test_novig.py::test_betrivers_is_show_only_and_kept_apart_from_novig`.
- **Discord note:** `2026-11-05-books`.
- **New fingerprints:**

```
a589adfa5985cd18402ae2c77c7ef6b7833a371a06d295d5bcecc74de5c4ad65  cbb/odds_api.py
56939f803f56c9fcf27ff1da9e6cc2acfe765a5dd9f74ab8efe006a24a885e96  cbb/odds.py
```

## 2026-11-05 (later): BetRivers becomes a play book (selection)

- **Change (Chad, Nov 5: "betrivers can be a play").** `cbb/odds_api.py` moves `betrivers` from DISPLAY_BOOKS into
  BOOKS. BetRivers prices from The Odds API now enter the card's lines and the quote log like the other six books,
  so a play can be logged at BetRivers when it has the best number or price. The SGO feed (`cbb/odds.py`) is
  unchanged: BetRivers comes from The Odds API only.
- **Cost:** none. Seven play books plus Novig stay within one region.
- **Close and CLV:** unchanged. The frozen protocol's close (`audit/forward_eval.BOOKS`) still takes the last valid
  quote across its own book list, which does not include BetRivers. A BetRivers play is graded against that close
  like any other play.
- **Card:** the BetRivers column is now a normal book column; the show-only path from earlier today is removed.
- **Tests:** `audit/test_novig.py::test_betrivers_is_a_card_book_and_novig_stays_show_only`.
- **Discord note:** `2026-11-05-betrivers-play`.
- **New fingerprint:**

```
c8a9865f7838b6078306152e16ea506f4848b79f3ab0950a19384193cf7f0a89  cbb/odds_api.py
```

## 2026-11-05: Novig change log fix and longer push retries (operational)

- **Novig change log (`cbb/odds_api.py`).** Under pandas 3, a Novig row with a missing number (no spread posted)
  made the change log fail ("Show-only prices failed ... expected str instance, float found"). The latest-prices
  file still updated; only `lines/novig_log.csv` missed those pulls. Each value is now turned into text before the
  join. Test: `audit/test_novig.py::test_change_log_handles_a_missing_number`.
- **Card run push (`.github/workflows/update.yml`).** GitHub rejected every push for about a minute and a half on
  Nov 5 at 23:22 UTC ("fatal error in commit_refs"), so that card run failed after 6 tries. The loop now makes 10
  tries over about 5 minutes. The next run's card and log were complete; the failed run's work was redone 10
  minutes later.
- **Unchanged:** picks, lines, stakes, alerts and closes.
- **Discord note:** none (no effect on plays).
- **New fingerprints:**

```
358e403da049f5bded46b8c94bd9e6f4dfa6835515a5ac74f816e52123c7745e  cbb/odds_api.py
b3375e4f142675a95e9c0d93f35d041dba4c5b4a33a655b1a0b5ea2513dfe87c  .github/workflows/update.yml
```

## 2026-11-06: card runs check out the latest branch commit (operational)

- **Problem.** A card run that waited in the concurrency queue still checked out the commit that triggered it, so it
  worked from a bet log without the previous run's plays and alerted them again. Four plays were alerted twice
  (Nov 2 Over 401910998; Nov 4 Coastal Carolina +38.5 and Penn State -15.5; Nov 6 Alabama Under 173.5). The
  second run's row replaced the first, so each play is logged once, with the later time.
- **Fix in `.github/workflows/update.yml`:** `actions/checkout` now checks out the branch tip when the job starts.
- **Unchanged:** picks, lines, stakes and the bet log format.
- **Discord note:** none.
- **New fingerprint:**

```
ef3744b1a4c7be3ae2bf2142c6883a19f9182b88a67a4411ca53ca3af3d8ce2c  .github/workflows/update.yml
```

## 2026-11-06: roster-prior shadow added (research only, no live change)

- New: `cbb/shadow_rp4.py`, `.github/workflows/shadow_rp4.yml`, `data/shadow_rp4.json`, `data/shadow_rp4_base.json`.
  After each card run it logs what the F2 blended prior (research/roster_prior PLAN_v4) would play, next to the live
  model and a matched refit, to `bets/shadow_rp4/`. Read plan: `research/roster_prior/SHADOW_PLAN.md`.
- **Unchanged:** the live model, the card, picks, stakes, alerts, the bet log and every fingerprinted file.

## 2026-11-06: Pinnacle quotes logged for a no-vig close (logging only)

- **Why (Chad, Nov 6):** "I only want to measure clv with pinnacles no vig close". Test call (2 credits): The Odds
  API prices college basketball at Pinnacle (34 of 56 events with spreads and totals; DraftKings 47).
- **Change (`cbb/odds_api.py`):** the card call and the targeted poll also request `pinnacle` (9 and 8 books,
  so no extra credits). Its quotes go only to `lines/pinnacle_log.csv` (a row on any change, and every quote in
  the 45 minutes before the start). Pinnacle never reaches the card's lines, the board, the quote log, a close or
  any pick.
- **Unchanged:** picks, books, stakes, alerts, closes and the official CLV, until the Pinnacle measure is built.
- **Tests:** `audit/test_novig.py::test_pinnacle_is_logged_apart_and_never_reaches_the_card`.
- **New fingerprint:**

```
a2e08b50ed4ac26994be2c2f1705674cf684a0336c8724736f5d7bbd23653c52  cbb/odds_api.py
```

## 2026-11-06: targeted quote poll fixed (ops only, no change to plays)

- **Why:** from 14:54 UTC every targeted quote poll failed at push ("cannot pull with rebase: You have unstaged
  changes"). The poll also logs Pinnacle (entry above) to `lines/pinnacle_log.csv`, a file its workflow never
  committed, so `git pull --rebase` refused to run. Those runs' quote observations and Pinnacle rows were lost.
- **Change:**
  - `cbb/odds_api.py`: the targeted poll's Pinnacle rows go to their own `lines/pinnacle_log_targeted.csv`. That keeps
    two jobs from appending to one CSV and conflicting on push.
  - `.github/workflows/quotes.yml`: commits that file, and pulls with `--autostash` so a stray file can't block a
    push again.
  - `cbb/clv_pinnacle.py`: reads both logs.
- **Unchanged:** picks, books, stakes, alerts, closes, the card and the Pinnacle CLV method.
- **New fingerprints:**

```
e5837fad5b54ec8d4806e0b992a844a63e2054297b14c1cebb54ef8df99201b4  cbb/odds_api.py
308c9e7003432cc52e55f81c8708d1fb57fa96e071f5078fc60e3206a6d2acb5  .github/workflows/quotes.yml
```

## 2026-11-06: The Odds API team names (Chad: "add the names")

- **Why:** 13 schools' games were dropped from The Odds API because their names there did not match ours (listed
  as unmatched in lines/last_pull.txt). They reached the card only through SGO: 5 books, pulled every 30 minutes.
  Example: Mississippi Valley State +40.5 at BetMGM while Caesars was at +42 (Chad, Nov 6).
- **Change (`data/team_aliases.csv`):** 13 `oddsapi` rows (American, Boston University, CSUN, Cal Baptist, FIU,
  Loyola Maryland, Mississippi Valley State, Mount St. Mary's, Northern Colorado, Nicholls, St. Thomas,
  Texas A&M-Corpus Christi, Kansas City). Each was checked to map to the right ESPN id.
- **Effect:** those games now get all 7 play books, refreshed every card run. The model, edges, thresholds and
  stakes are unchanged; a play's book or number can change because more books are seen. Discord note:
  `2026-11-06-oddsapi-names`.
- **New fingerprint:**

```
766dde543fe3481a3c1e41cec8c3b39812b4c2da5f8888d0e90848fa45748584  data/team_aliases.csv
```

## 2026-11-06: Barttorvik stale file falls back to his live ratings (Chad: "do both")

- **Why:** on Nov 6 the card used Barttorvik's Nov 4 time-machine file for Nov 6 and Nov 7 games, because the Nov 5
  and Nov 6 files never downloaded. The site flagged it "Barttorvik 44h". The code did not record why a file was
  missing.
- **Change (`cbb/barttorvik.py`):**
  - Each missing day's reason is recorded and printed in the run log: not published (404), refused (HTTP code),
    not a ratings file, network error, or still missing at the hourly retry.
  - For live games, when the newest time-machine file is more than one day older than the games, the model uses
    Barttorvik's live ratings file instead (fetched before tip, same columns).
  - Past days and backtests still use the time machine only.
- **Change (`cbb/freshness.py`):** the Barttorvik input time is the live file's fetch time when it was used.
- **Effect:** Barttorvik's inputs to the model are current instead of up to several days old. KenPom, the model's
  weights, thresholds and stakes are unchanged. Discord note: `2026-11-06-barttorvik-live`.
- **New fingerprints:**

```
bcf75b0897c2a361188d30bd524fb7c25854b9187a23f47edfd4ede270e0f026  cbb/barttorvik.py
d5e3cb8a9a1e8ad8b957ef4ed5ef363a8d9247d8aa60c47c86d933ed7ea101d1  cbb/freshness.py
```

## 2026-11-07: blowout correction in the live model (Chad: "make the correction to the live model")

- **Why:** research/blowout_unders Part 2. When the model projects a big margin, the favorite outscores the
  projection (1.6 points at 25-30, 2.5 at 30+ in 2015-26 closes; mostly 2023-26), so the margin is too small and the
  total too low. Live: dogs getting 25+ were 9-12 with Pinnacle CLV -4% to -5%.
- **Change (`cbb/projection.py`, `apply_saved` -> `blowout`):** x = 0.16 x max(0, |projected margin| - 16) extra
  points for the favorite, added to the favorite's margin and to the total. Logged as `blowout_pts` in the saved
  stage-2 output.
- **Test (research/blowout_fix, plan written first):** walk-forward on 2023-2026 (each season fit on the three
  before). Games with projected margin 20+: margin error 9.911 -> 9.893, total error 13.305 -> 13.237 (bias +2.13 ->
  +1.58). All games: 8.8854 -> 8.8841 and 13.0710 -> 13.0660. Opener plays 2024-26: spreads 57.77% -> 57.79%, totals
  57.39% -> 57.52%; at |spread| 20+ the close now moves our way more (spreads +0.88 -> +1.28, totals +1.32 -> +1.62).
  Ship rule met. Live constants from the fit on 2023-2026: T = 16, k = 0.16.
- **Effect:** at a 30-point projected margin the favorite gets +2.2 points (margin and total); nothing below 16.
  Fewer big-dog and big-mismatch Under plays. Stage-2 weights, thresholds, stakes and books are unchanged. Plays
  already logged keep their numbers. Shadows that refit stage 2 themselves (ridge-1,000) do not carry the correction.
  Discord note: `2026-11-07-blowout-correction`.
- **New fingerprint:**

```
128e00d5b450d18cac0421181e3be87bf225190e21f2e8863dcfc2ec546a0b55  cbb/projection.py
```

## 2026-11-09: stakes by edge (Chad: "improve the results now", then "push it")

- **Test (research/selection_cut, plan written first):** walk-forward frame with the blowout correction, seasons
  2015-17 and 2024-26. Stake 1u at the bar (spreads 2.5, totals 3), 1.5u from bar + 1, 2u from bar + 2:
  spreads 191.0u -> 271.7u (ROI 9.09% -> 9.83%) and 249.1u -> 325.1u (10.44% -> 11.02%); totals 426.7u -> 648.0u
  (11.18% -> 11.38%) and 422.0u -> 662.4u (9.77% -> 11.02%). Rule (more units AND higher ROI in both periods) met.
- **Not adopted (same plan):** a higher edge bar (fewer units in every case); dropping plays at the closing number
  (2024-26 win 52.0-53.4%, rule not met for spreads; the opener rule already limits plays to openers).
- **Change:** `cbb/run_day.py` `_call` multiplies a BET's units by `edge_tier` (1 / 1.5 / 2); `cbb/tracker.py` logs
  the card's units (tier x stake multiplier) as the stake, else the multiplier. Thresholds, EV rule, selection, the
  stake multiplier and the stake cap are unchanged. 219 tests pass.
- Discord note: `2026-11-09-edge-stakes`.
- **New fingerprints:**

```
dc8604d87794a5cc49c9edc93978cd66895f73a63452168de8eadc76780257a7  cbb/run_day.py
8c027a0fcd447a99ed76089bdbf711741d3dd2185f66a09542c6909540dc3c3a  cbb/tracker.py
```

## 2026-11-09: roster-based spreads live (Chad: "yes do it, test it and push it")

- **Why:** live 2026-27 spreads 65-66; underdogs 24-32 with Pinnacle CLV -2.0%, favorites 41-34 with +6.5%. In the
  backtest, November underdogs are the weakest group of the portal era (2024-26: 53.7%, 245 plays). Early ratings miss
  roster turnover.
- **What:** research/roster_prior R3v4, the blend the rp4 shadow has run since Nov 5. Each team's stage-1 start is
  the average of the current preseason prior and our roster-based prior (F2, ridge on returning-minutes and box-rate
  features, walk-forward), with that blend's stage-2 margin weights (`data/shadow_rp4.json`), then the blowout
  correction. **Spreads only;** totals stay v1 (the blend missed its early-totals rule by 0.005).
- **Backtest (PLAN_v4.md, plan written first):** opener spreads 57.51% -> 57.63% (2015-17, 1,933 plays) and
  57.69% -> 58.28% (2024-26, 2,301), ROI 9.56% -> 9.75% and 10.10% -> 11.23%; early-season margin error (days 0-20)
  9.174 -> 9.150; all games 8.770 -> 8.766.
- **Live check:** `run_day.roster_spreads` reproduces the shadow's rp4 margins to 0.0005 on all 335 games of Nov 9-16;
  it moves spreads by 0.6 points on average (max 3.2). The roster prior is built once a day (about 30 s) and cached in
  `cbb/cache/rp4/`. On any failure the run keeps v1's margin and prints why. 219 tests pass.
- **Changes:** `cbb/run_day.py` (`project` -> `roster_spreads`; `v1_final_margin` kept beside it); `cbb/shadow_rp4.py` (its
  v1 check applies the blowout correction like the saved inputs). The rp4 shadow keeps running; its rp4 rows now match
  live spreads.
- Discord note: `2026-11-09-roster-spreads`.
- **New fingerprints:**

```
82a455feeb33eeee964222b890b44a9436b5f4aa05c5b3ce545be88ffbba6f94  cbb/run_day.py
0688be9010cee69f389cadb601c5de624b1257c248fd3288fb322823d272a469  cbb/shadow_rp4.py
ffe70f4835b50220d8050f2134df31c94f4d1544d2f417bfe51e0ad928e02708  data/shadow_rp4.json
```
