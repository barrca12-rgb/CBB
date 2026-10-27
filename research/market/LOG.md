# Experiment log

Every specification tried, in order, with its result. Nothing is removed from this file.

## 2026-10-26: step 1, sample and completeness check

- Sample dates fixed by rule before any pull. The rule's first Saturday of November falls before every season's
  opening day (Nov 5, 2022; Nov 4, 2023; Nov 2, 2024; Nov 1, 2025: zero games). Declared replacement, before
  pulling: the first Saturday on or after the season's first game.
- Credit cost computed from the schedule: 101,680 credits for the sample as specified. **Not pulled** (see
  STEP1_REPORT.md).

## 2026-10-26: step 2a, model edge vs favorable quote (ESPN multi-book, no new data)

Specification as declared in `s2a_decompose.py`'s docstring, fixed before the first run.
- **Run 1:** crashed in the by-season summary (a pandas groupby column error); no results were read. Fixed and
  re-run.
- **Run 2:** complete. One label fix afterwards: the book "Sportsbook.com" had been mapped to an empty family
  name. It was already its own family, so no number changed. Re-run (run 3) is the reported output
  (`out/s2a_run.txt`).
- **Cell construction note:** "model agrees / ordinary quote" is near-empty by construction. A signal needs
  D + Q >= threshold, so D below the threshold with Q below 0.5 leaves only a half-point band: 118 and 121 bets at
  the close, 7 and 7 at the 2024 openers.

## 2026-10-26: step 4, shooting-night overreaction (closes and box scores, no new data)

Specification as declared in `s4_shooting.py`'s docstring, fixed before the first run. One run, reported as
is (`out/s4_run.txt`). Both surprise definitions (league rate; team- and opponent-adjusted) were declared before
the run.

## 2026-10-26: Option B approved by Chad

- **The plan** (`sample_plan.json`), fixed before any pull: 12 dates.
  - 30-minute snapshots from 24 hours before each day's first tip to its last tip.
  - Jan 11, 2025 at 5-minute snapshots.
  - Spreads and totals, US region.
  - 1,203 snapshots, about 24,060 credits.
- **The pull:** `pull_sample.py`, run once by `.github/workflows/history_sample.yml`, started by hand.
- **Guards:** it stops before leaving fewer than 50,000 credits, and spends at most 27,000.
- **Stored:** a change log per date (new, changed, absent quotes) plus a list of every snapshot served.

## 2026-10-26: Option B pulled and analysed

- **The pull:** complete, all 12 dates, 24,060 credits, 71,466 credits left afterwards. The served snapshots sat a
  few minutes before each requested time, as the API documents.
- **Analysis run 1:** crashed (the schedule file already has a `game_id` column, so the rename made a duplicate).
  Fixed; run 2 is reported (`out/s1_coverage.csv`, `out/s1_picks_at_first_quote.csv`).
- **Added checks, declared after run 2:**
  - how many games were already quoted at the first snapshot (truncation);
  - team names that did not match;
  - how long opening numbers lasted on the 5-minute day;
  - for the model's picks, minutes until the picked number got worse. A game leaving the feed at tip counts as
    "worse", so "never worse" is 0 by construction.

  Output: `out/s1b_run.txt`.

## 2026-10-27: alias map and step 2a on real quotes (declared before running)

- **Alias map:** `oddsapi_aliases.csv` maps 41 Odds API team names (research only; the live alias file is frozen).
  Coverage re-run: `out/s1_run2.txt`.
- **Step 2a on the Option B sample (`s2a_real.py`):**
  - **When:** for each game and market, the "market open" is the first snapshot with 3+ US books quoting it.
    State at that snapshot = each book's latest quote so far.
  - **Pick:** the live rule. Across DraftKings, FanDuel, BetMGM and Caesars, the side and book with the best EV at
    the book's real price (frozen win-chance table). A BET needs edge >= 2.5 / 3 and EV >= +2%.
  - **Reference:** the median number of every OTHER US book at that snapshot.
  - **Decomposition:** D = model deviation from the reference, Q = the bet book's quote advantage, in points.
    Cells as in s2a (D >= threshold "opposes", Q >= 0.5 "favorable").
  - **Outcomes:** win % and ROI at the real price. Line value to the last pregame snapshot's median across books.
  - **Benchmark:** market only, the book furthest from the others (1+ points), on its favorable side, at its
    price.
  - **Uncertainty:** date-clustered; only 12 dates, so wide.
- **s2a_real run 1** (`out/s2a_real_run.txt`), reported as is. Line value is shown in the table output but not
  relied on: "last pregame snapshot" can be many hours after the open, and it was not pre-specified beyond that.

## 2026-10-27: helpers' review follow-ups (pre-registered before running; `s3_followups.py`)

### 1. Matched first-book comparison

- **Sample:** for each game and market in the Option B sample, the "first book" is the first of the four to post
  that game (earliest first quote). A pick is the frozen rule at the first book's first quote (spread edge 2.5+,
  total 3+, no EV rule; the original comparison also had none).
- **Pairing:** each pick is paired with every later book's first quote on the SAME side (same game, side and
  prediction). Each pair is graded at both quotes, at recorded prices.
- **Report:**
  - the paired ROI difference (first minus later) with a date-clustered interval;
  - the mean number difference;
  - the same restricted to pairs where the number is equal (only time and price vary).
- **Also shown:** the original unmatched 58.5% vs 54.4% cohorts, to show how much was selection.

### 4. Reconciliation table

One row per headline figure, each from its own source, in the order: corrected full backtest; live-like model;
12-Saturday sample at first quotes; picks with quotes at the four books at the 3-book market open; picks still at
the number after each delay window (30-45 and 60-80 minutes on all 12 dates at 30-minute snapshots; all four
windows on Jan 11 at 5-minute); results at the observed quote.

- **Signal time** = the first book's first-quote snapshot. "Still at the number" = the same book, same side,
  number equal or better and payout at least as good, at the first snapshot in the window. Pregame only.
- **s3_followups run 1** (`out/s3_run.txt`), reported as is. At 30-minute cadence the 5-10 and 15-25 minute
  windows have no snapshot except on Jan 11.

## 2026-10-27: line-shopping test (pre-registered before running; `s5_shopping.py`)

**Question:** with the same picks at the same moment, how much does taking the best of several books add over
betting at one book? This isolates shopping from timing.

**Sample:** the 12 Option B dates. Each book's state at a snapshot is its latest quote at or before the snapshot,
unless marked absent. Pregame only.

**Pick moment and side:**
- For each game and market, the pick moment is the first snapshot at which at least two of the big four
  (DraftKings, FanDuel, BetMGM, Caesars) quote the market.
- The frozen live-like model's edge vs the median of those books' numbers must meet the rule (spread 2.5+,
  total 3+).
- One pick per game and market, on the model's side. No EV rule.

**Compared at the pick moment, same side:**
- **one book:** each quoting big-four book separately. The headline is the average over books, i.e. "you have one
  account". Each named book is also shown.
- **best of four:** the bettor's best number among the quoting big-four books; ties go to the better price.
- **best of all:** the same over every book in the data (adds Bovada, BetRivers, BetOnline, LowVig, MyBookie,
  BetUS). Secondary.

**Measures, best vs one book:**
1. mean points of number gained, and the share of picks where best beats the single book;
2. **primary, expected value:** each quote is graded against the outcome distribution of historical games with
   the same closing number (wf_live_approx 2014-2026; spreads keyed on the oriented closing spread, totals on the
   closing total rounded to the nearest point, with ±2 points if fewer than 300 games). Win, push and loss
   probabilities at the quote's number, then EV in units at its price. This measures the value of the number and
   price alone, without the 12 dates' luck.
3. actual paired results at recorded prices (noisy, 12 dates), with a game-level bootstrap interval.

**Reported:** spreads and totals separately.

**Worth acting on:** best-of-four EV gain of +1.0% per bet or more on spreads, with a game-level 95% interval
excluding 0.
- **Implementation note (before running):** for both markets, historical games are matched on the same closing
  number (same half-point). If fewer than 300 match, the match widens to ±1 and then ±2 points in whole-point steps,
  with the outcome shifted by the difference so pushes stay on whole numbers. This replaces "rounded to the nearest
  point" for totals.
- **Run 1 fix:** a few extreme totals had no historical games within ±2 points, which left their EV undefined and
  the totals summary blank. Those picks are dropped from the EV measures only, and the count is shown. Spreads were
  unaffected. Run 2 is the reported one.

### Line-shopping results (run 2; `out/s5_result.csv`, `out/s5_by_book.csv`, `out/s5_run.txt`)

| | spreads: best of 4 | spreads: best of all | totals: best of 4 | totals: best of all |
|---|---|---|---|---|
| picks | 133 | 133 | 236 (235 with EV) | 236 (235) |
| points of number gained vs one book | 0.19 | 0.26 | 0.21 | 0.33 |
| **EV gain per bet (primary)** | **+1.14%** [0.92, 1.37] | **+2.41%** [2.05, 2.78] | **+0.92%** [0.74, 1.11] | **+1.68%** [1.46, 1.90] |
| win% at the number, historical (one book -> best) | 49.55 -> 50.22 | 49.55 -> 50.51 | 50.26 -> 50.74 | 50.26 -> 51.04 |
| actual ROI gain on the 12 dates | -0.29% [-0.60, -0.01] | +0.43% [0.01, 0.86] | +0.63% [-0.13, 1.77] | +1.69% [0.40, 3.34] |

**Pre-registered bar (spreads, best of four, +1.0% and CI above 0): met.**

**Caveats:**
- The EV interval reflects pick-to-pick variation only, not the fact that this is 12 dates.
- At the pick moment only about 2.1 of the big four were quoting. Shopping later, with more books up, may gain
  more, but that conflicts with betting at the open; not tested.
- "All books" includes offshore books (Bovada, BetOnline, LowVig, MyBookie, BetUS) that may not be available.
- On the 12 dates, the best-of-four number sometimes came with a worse price and results rarely landed in the gap,
  so the actual gain is about 0. The EV measure is the pre-registered primary.
- The one-book EV is negative because this measure prices the number only (vig included, no model edge). Only the
  difference matters.

Per book, best of four vs that book alone, spread EV gain: DraftKings +1.39%, FanDuel +1.20%, BetMGM +0.82%,
Caesars +0.70%.

## 2026-10-27: first-half lines, cost estimate (nothing pulled)

- **Price:** The Odds API's historical event odds cost 10 credits per market per region per call, one call per game
  per moment (confirmed by the Oct 26 second-half pulls, about 20 credits a game for one market at up to two
  moments). First-half spreads plus totals = 20 credits per game per moment. Games with no first-half lines should
  not be charged, so the figures below are upper bounds.
- **Available dates:** the Option B dates from the 2023-24 season on: 9 dates, 975 games. The archive's extra
  markets start in 2023.
- **Balance:** 71,138 credits at 13:20 UTC Oct 27 (lines/odds_api_usage.json). The guard floor used for Option B is
  50,000, which leaves about 21,000 to spend.

| option | games | moments per game | credits, at most |
|---|---|---|---|
| pilot: 20 games, 2025-26 | 20 | 2 | 800 |
| A: 5 recent dates (2025-26) | 585 | 1 (near tip) | 11,700 |
| B: all 9 dates | 975 | 1 (near tip) | 19,500 |
| C: 5 recent dates | 585 | 2 (game-day morning + near tip) | 23,400 (above the floor) |
| D: all 9 dates | 975 | 2 | 39,000 (above the floor) |

## 2026-10-27: first-half pilot (approved by Chad; `h1_pilot.py`, `research_h1_pilot.yml`)

- **Games, fixed before the pull** (`data/h1_pilot_games.csv`, seed 20261027): from the 2025-26 Option B dates
  (Nov 8, Jan 10, Mar 7), tip at or after 17:00 UTC. 10 with a power-conference team and 10 without, drawn at random.
- **Moments:** game day 15:00 UTC, and tip - 15 minutes. Spreads_h1 and totals_h1, all US-region books.
- **Guards:** at most 800 credits; stops before leaving fewer than 50,000.
- **Purpose: coverage only, no betting test.** How many games have pregame first-half lines, at which books, and
  whether they are up by the morning. That decides whether option A is worth pulling. The betting test will be
  pre-registered before any larger pull.

### First-half pilot results (`data/h1_pilot_status.csv`, `data/h1_pilot_lines.csv`)

- **Cost:** 760 credits. The 2 calls that found no lines were not charged.
- **Near tip (tip - 15 min):** all 20 games had first-half spreads and totals. DraftKings 20/20, FanDuel 20/20,
  BetMGM 17-20/20, Bovada 19, BetOnline and BetUS 15. Caesars had none.
- **Game-day morning (15:00 UTC):** 18 of 20 games had a line somewhere. DraftKings 13, FanDuel 11, BetMGM 5-6,
  offshore books 14-15. The two games with nothing were low-majors (Wagner, Stetson). By tip, lines had moved in
  several games (e.g. Syracuse -15.5 -> -14.5).
- **Hold (both sides' implied probabilities minus 100%):** DraftKings and BetMGM 6.9%, FanDuel 5.6%, offshore
  4.7%. A -110/-110 full-game line is 4.8%. Break-even is about 54.1% at DraftKings and BetMGM vs 52.4% on full
  games.
- **Reading:** coverage near tip is essentially complete, so option A (5 recent dates, near tip) would pull
  close to its 11,700-credit estimate. The higher hold means first halves need a bigger edge to profit.
