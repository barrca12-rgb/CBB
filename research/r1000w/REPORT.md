# Ridge-1,000 variants: report (Nov 7, 2026)

Plan: PLAN.md (variant 1 and, after it failed, variant 2, each written before its run). Numbers: out/.

## Variant 1: recency weights. No.
Half-life chosen on 2019-22: 1 season. 2023-26 errors beat ridge-1,000 (margin 8.8893 vs 8.8923; total 13.0653 vs
13.0694), but opener spreads 2024-26 fell 57.34% -> 56.80% (limit 0.3). Totals rose 57.20% -> 57.35%. Lead only:
recency weighting for totals alone (not tested; it came from these results).

## Variant 2: ridge-1,000 + blowout term. Runs as a shadow (r1000b).
Walk-forward fits (T, k): 2023: 28, 0.10; 2024: 24, 0.08; 2025: 20, 0.08; 2026: 16, 0.10; fit on 2023-26 = (16,
0.16), the same as live.

| 2023-26 | ridge-1,000 | + blowout |
|---|---|---|
| margin error, all | 8.8923 | 8.8913 |
| total error, all | 13.0694 | 13.0645 |
| margin error, projected 20+ | 9.9459 | 9.9088 |
| total error, projected 20+ | 13.2685 | 13.1503 |
| opener spreads 2024-26 | 57.34% (2,016), move +1.050 | 57.14% (2,016), move +1.098 |
| opener totals 2024-26 | 57.20% (4,179), move +1.488 | 57.40% (4,157), move +1.514 |

Rule met. `cbb/shadow_r1000.py` now prices v1 (with the live blowout correction, as the card), r1000 (unchanged)
and r1000b against the same quotes; r1000b rows are `model = r1000b` in bets/shadow_r1000/signals.csv. Read with
ridge-1,000 at Jan 15.
