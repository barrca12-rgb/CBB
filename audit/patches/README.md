# Proposed changes awaiting Chad's approval (none applied)

Each diff applies cleanly to the branch as of Oct 26, 2026 (`git apply --check`). Nothing here changes a prediction,
a selection, a threshold, a stake or the frozen model's fingerprints. Applying any of them is recorded under "Changes
during the freeze" in `MODEL_FREEZE.md`, together with this validation.

| Diff | What it changes | Effect on plays this week | Needs from Chad | Validation |
|---|---|---|---|---|
| `logging_reporting.diff` | Adds `cbb/quotelog.py`, `cbb/poll_targets.py` and `.github/workflows/quotes.yml`. Adds logging calls to `odds.py`, `odds_api.py`, `notify.py`, `record.py` and `run_day.py`. Adds cohorts A, B and C to the record page, `bets/accepted.csv`, and union-merge rules for the new logs | None: the Nov 2 card and the bet log are identical with and without it | Approval to apply; a cron-job.org job dispatching `quotes.yml` every 3 minutes; Odds API spend of up to about 960 credits a day (about 29,800 a month) on top of the card runs' about 13,400 a month | `logging_reporting_validation.txt` (reproduce with `validate_card_unchanged.py` in two trees, and `validate_logging.py`) |
| `referee_fix.diff` | `evaluate.py`: adds `final_at_open()`, which predicts with crew inputs at 0 (crews are not posted when openers are) using unchanged weights, and adds a "totals vs the opener with crews unknown" table to `BACKTEST.md` | None: evaluation only; the live card already has crews at 0 until ESPN posts them | Approval | `fixes_validation.txt`: totals vs opener 2024-26 go from 57.39% to 56.22% (4,256 to 3,993 selections); spreads unchanged |
| `opener_cleaning_fix.diff` | `lines_hist.consensus()`: removes the close-based opener correction and keeps a drop-only plausibility rule (spreads within +-60, totals within 100-200) | None: backtest and `BACKTEST.md` only; live openers never used this function | Approval | `fixes_validation.txt`: spreads vs opener 2024-26 go from 57.77% to 58.73% (2,229 to 2,361); totals unchanged |

Not proposed as a change, only documented:
- **Barttorvik placeholder files:** `barttorvik.snapshot` caches an empty file for a date requested before its file
  exists and never re-requests it. In practice the live card falls back to Barttorvik's live ratings file, which is
  current. The forward-test log records which source each signal used.
- **SGO in season:** at 1 entity per event per pull, the card runs alone will reach the code's 95% monthly stop
  within days of the season starting. The allowance is shared with the NFL model, and the subscription ends Nov 25
  (reminder set for Nov 24). The Odds API covers both cases.
