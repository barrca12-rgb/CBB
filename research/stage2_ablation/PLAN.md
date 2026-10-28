# Stage-2 ablation: what KenPom (and Barttorvik) are worth — pre-registration

Written Oct 28, 2026, before the run. Research only; no live change.

- **Benchmark:** the frozen live-like stage 2 (research/originator/d_common `frames()` + `walk_forward()`: ridge lam=1,
  each season fit on earlier seasons only; KenPom inputs as of the day before).
- **Variants** (same features otherwise, same walk-forward):
  - (a) no KenPom: drop `kp_margin`, `kp_margin_x_early`, `kp_total`, `kp_total_x_early`;
  - (b) no Barttorvik: drop `bt_margin`, `bt_total` (run earlier; rerun here so every row uses one harness);
  - (c) neither.
- **Scoreboard**, per market (spreads, totals), per era (development 2014-2017, confirmation 2024-2026), overall and
  split November-December vs January-March (tournaments included in the second half): opener CLV of the frozen rule
  (spread 2.5+, total 3+) with date-clustered standard errors, opener win % with n, and margin MAE (and total MAE).
- **Kill rule for "KenPom is needed":** if variant (a) is within 0.1 opener CLV and 0.02 margin MAE of the frozen
  model in both eras and both halves of the season, KenPom is not needed (killed). Any cell outside either bound
  means KenPom is needed there; the verdict names which months.
- **Prior:** KenPom matters most in November-December, when our own ratings are still mostly preseason prior and
  KenPom's in-season updates and adjustments carry information; by January-March our ratings have caught up and
  KenPom's added value is small.
