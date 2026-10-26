# Experiment log

Every specification tried, in order, with its result. Nothing is removed from this file.

## 2026-10-26: step 1, sample and completeness check

- Sample dates fixed by rule before any pull. The rule's first Saturday of November falls before every season's
  opening day (Nov 5, 2022; Nov 4, 2023; Nov 2, 2024; Nov 1, 2025: zero games). Declared replacement, before
  pulling: the first Saturday on or after the season's first game.
- Credit cost computed from the schedule: 101,680 credits for the sample as specified. **Not pulled** (see
  STEP1_REPORT.md).

## 2026-10-26: step 2a, model edge vs favourable quote (ESPN multi-book, no new data)

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
