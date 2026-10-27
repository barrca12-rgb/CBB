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
