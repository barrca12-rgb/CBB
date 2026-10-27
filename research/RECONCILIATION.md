# Reconciliation of the headline figures (Oct 27, 2026)

Each spread figure quoted in the doc traces to exactly one row. The rows run from the full backtest down to
results at observed quotes. ROI is at -110 unless "recorded prices" is stated.

| # | Population | Model | Spreads | Totals | Source |
|---|---|---|---|---|---|
| 1 | Full backtest at the opener, live cutoffs (2.5 / 3), openers oriented by moneyline, swapped records out | production | **57.3%** (2015-17, 2,020) / **58.0%** (2024-26, 2,291) | 57.9% / 56.2% (crews unknown) | `BACKTEST.md`, `audit/b9_item7.py` + `evaluate.swapped` |
| 2 | Same, live-like model (crews 0, KenPom from the day before) | live-like | 56.8% (2014-17 + 2024, 3,338) / 57.7% (2025-26 holdout, 1,599) | 55.4% / 55.6% | `research/edges/e7`, `e2` |
| 3a | Row 2, neutral sites only, likely swaps excluded by the strict filter | live-like | **60.0%** (499) / 59.6% (193) vs 56.2% / 57.6% at home courts | | `research/edges/out/e5d_neutral.txt` |
| 3b | Row 2, picks the market later moved 1+ point toward (defined after the fact, not selectable) | live-like | 60.3% / 61.1% at the opener, 52.8% / 52.6% at the close | 59.9% / 59.0% | `research/edges/e6_timing.py` |
| 4 | 12 Saturdays 2022-26, picks at the four books' first quotes, best number per game | live-like | 58.8% (229) | | `research/market/out/s1b_run.txt` |
| 5 | Row 4 split by first book to post vs later books, unmatched (as first reported; **superseded by 6**) | live-like | **58.5%** (229) vs 54.4% (311) | | `research/edges/out/e8_first_book.txt` |
| 6 | Matched: picks at the first book to post, graded at its quote vs each later book's quote, same game and side | live-like | 54.4% vs 51.7% paired (362 pairs); ROI +4.6% [1.3, 8.4], all from a 0.69-point better number; equal number: 0.0 | 58.4% vs 54.9%; ROI +6.6% [3.0, 9.7], from 0.89 points | `research/market/out/s3_run.txt` |
| 7 | 3-book market open, live rule at real prices (best EV across the four) | live-like | 54.3% (140), ROI +3.2% recorded prices | 57.7% (242), +10.1% | `research/market/out/s2a_real_run.txt` |
| 8 | Row 6's first-book picks still at the number or better, same book, at the first snapshot in the window | live-like | 30-45 min: 89%; 60-80 min: 81% (Jan 11 at 5-min: 100% at 5-10, 74% at 15-25) | 85%; 77% | `s3_run.txt` |
| 9 | Row 8's available picks graded at the observed quote, recorded prices | live-like | ROI +3.6% (30-45), +2.4% (60-80) | +9.2%, +10.9% | `s3_run.txt` |

- **"57-58%"** = row 1.
- **"About 60%"** = row 3a (neutral sites) or row 3b (an after-the-fact class, never a selection rule).
- **"58.5%"** = row 5, superseded by row 6.
- **Rows 4-9** are 12 dates, with wide intervals.
