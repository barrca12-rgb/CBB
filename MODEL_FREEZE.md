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
