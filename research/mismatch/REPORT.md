# Early-season mismatch study: result (Nov 3, 2026)

Plan: `research/mismatch/PLAN.md`, committed before any number was computed. Output: `out/report.txt` (`python -m
research.mismatch.study`). Research only; nothing live changed.

**Verdict: no reliable evidence that early-season ratings understate mismatches. Under the pre-registered rule,
nothing changes.** Of the three conditions, only (b) holds.

- **H1, calibration (a: no).** Early in a season, actual margins run about 4% wider than the model's (slope 1.04 in
  both eras). Later in the season they run 0-3% wider.
  - The early-minus-later difference is +0.040, 95% [-0.015, +0.103], in 2014-17 and +0.009 [-0.050, +0.071] in
    2024-26. Both intervals include 0.
- **H2, big lines against the market (b: yes, but not an early-season effect).** In games with |opener| >= 17.5, big
  favorites beat the opener by about 1 point in every period:
  - early: +1.04 in 2014-17, +1.32 in 2024-26;
  - later: +1.06, +0.73.
  - The model leans less toward them than that, early and later alike, and the gap is no larger early (+0.6 to +0.7)
    than later (+1.0 to +1.4).
- **H3, the betting rule (c: no).** Early-season v1 plays on underdogs of 17.5+ won 47.1% in 2014-17 (n=34) and 60.8%
  in 2024-26 (n=51), 55.3% pooled (47/85, 95% [44.7, 65.4]). That is the same as later in the season (55.6%). Early
  big-favorite plays won 59.6% (n=161).
- **Live check:** on the 2026-27 cards so far, the live model leans 0.46 points toward the underdog against the close
  in games of 17.5+ (n=75). The backtest's early 2024-26 lean against the close was -0.53. So the live model behaves
  as the backtested v1 did early in a season, a stretch in which its big-underdog plays still won 55-61% in the
  recent era.
- **Reading of Nov 2:** the 6-9 night on big underdogs fits this history as variance. It does not point to a flaw
  specific to the opening week.
- **Not tested here, a possible future pre-registered study:** big favorites beating the market by about 1 point
  all season (H2). The model only partly prices this. It is a market-wide pattern in buy games, not something this
  plan set out to test.
