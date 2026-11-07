# Ridge-1,000, recency-weighted (pre-registered Nov 7, 2026; Chad: "another shadow of ridge 1000 with different
weights while keeping the current ridge 1000")

**Why this change:** ridge-1,000 fits 2013-2026 with every season counted equally. The blowout study
(research/blowout_unders) found the game has shifted since 2023 (favorites in mismatches outscore what older seasons
imply). Counting recent seasons more lets the weights follow that drift without new inputs.

**Variant:** same inputs, same penalty (1,000); each training game weighted 0.5^(seasons back / H), weights scaled
to average 1. H (half-life in seasons) chosen from {1, 2, 3, 5, 8}.

**Walk-forward:** every test season is fit only on seasons before it. Live (penalty 1, equal weights) and ridge-1,000
(equal weights) are scored the same way.

**Choose H on 2019-2022** (lowest margin + total mean absolute error). **Judge on 2023-2026**, untouched while
choosing.

**Shadow rule (fixed now):** run it as a second ridge-1,000 shadow only if, on 2023-2026, its margin and total
errors are both below ridge-1,000's, and its opener win % (2024-26, spreads 2.5+, totals 3+) is no more than 0.3
points below ridge-1,000's in either market. Otherwise report and do not run it.

## Variant 2 (added Nov 7 after variant 1 failed its rule; written before running it)

**Change:** ridge-1,000 weights unchanged, plus the blowout term the live model got on Nov 7
(research/blowout_fix): favorite +k x max(0, |margin| - T) on margin and total. (T, k) fit walk-forward on the
three seasons before each test season, on ridge-1,000's own projections, grid as in research/blowout_fix.

**Same shadow rule:** 2023-2026 margin and total errors both below ridge-1,000, opener win % within 0.3 points in
both markets (2024-26). Variant 1's totals-only gain is noted as a lead, not tested here (it came from the results).
