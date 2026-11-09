# Selection cut: report (Nov 9, 2026)

Plan: PLAN.md (tests 1-2 first; test 3 added before it ran). Numbers: out/results.csv, out/tiers.csv.

1. **Late plays (model vs the closing number):** 2015-17 spreads 52.33% (2.5+), totals 56.13%; 2024-26 spreads
   52.76%, totals 52.02%. Opener plays: 57.25-58.33% and 57.52-57.88%. The edge is in the opener. Rule (both
   periods under 52.4%) not met for spreads, so nothing cut.
2. **Higher bar:** win % rises (spreads 4+: 61.03% / 60.12%) but units fall at every step. Not adopted.
3. **Stakes by edge (1 / 1.5 / 2u):** more units and higher ROI in both periods and both markets
   (spreads 2024-26 +249.1u -> +325.1u, totals +422.0u -> +662.4u). Passed.

**Status: not live.** The change (`live_patch.diff`: `cbb/run_day.py` edge tiers, `cbb/tracker.py` logs the card's
units) passed all 219 tests but is waiting on Chad's go-ahead to deploy (with a MODEL_FREEZE entry and a Discord
note).
