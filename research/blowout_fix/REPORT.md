# Blowout correction: report (Nov 7, 2026)

Plan: PLAN.md (written first). Script: `python -m research.blowout_fix.backtest`; all numbers in out/.

**Verdict: ship (rule met). Live since Nov 7 (MODEL_FREEZE.md).**

- Walk-forward fits (season: T, k): 2023: 26, 0.12; 2024: 24, 0.10; 2025: 20, 0.10; 2026: 16, 0.10. Live fit on
  2023-2026: T = 16, k = 0.16.
- Out of sample 2023-2026, projected margin 20+ (1,545 games): margin error 9.9113 -> 9.8930; total error 13.3046 ->
  13.2365; total bias +2.13 -> +1.58. Projected margin 25+ (689): 9.9194 -> 9.8751; 13.5176 -> 13.3780; bias +3.43 ->
  +2.49. All games (22,948): 8.8854 -> 8.8841; 13.0710 -> 13.0660.
- Opener plays 2024-26: spreads 2,229 at 57.77% -> 2,230 at 57.79%; totals 4,256 at 57.39% -> 4,242 at 57.52%.
  |spread| 20+: spreads 57.36% -> 57.76% (close move +0.88 -> +1.28); totals 55.77% -> 57.14% (+1.32 -> +1.62).
- The correction is conservative: even after it, the total in 25+ games still runs 2.5 points low. A larger k or a
  total-only term is a follow-up, read on live results first.
- Nov 7 card, games it would have moved: Morehead State +38.5 at Louisville, dog edge -5.3 -> -2.5 and Under edge
  -3.0 -> -0.2 (both no longer plays); Omaha at Utah State Under -3.5 -> -1.6.
