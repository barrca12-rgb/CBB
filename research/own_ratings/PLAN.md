# Own ratings: scoring-level fix and less reliance on KenPom/Barttorvik (pre-registered)

Written Nov 4, 2026, before any of these variants was run. Chad, Nov 4: "do both but only backtest. no model
changes." Nothing here touches the live model, the card, `cbb/ratings.py` or `data/projection.json`. Every variant
and every number goes in `REPORT.md`, including the ones that lose.

## Why

On the first live week our own ratings' totals missed by 15.4 points (KenPom 13.5). The cause is one edge case:
- **The opening day had 2 games.** The season opened with 2 games on Nov 1, and the stage-1 intercepts for
  efficiency and pace are fit with almost no regularization (`lam[0] = 1e-6`).
- **So the scoring level came from those 2 games.** The Nov 2 league level was set by 2 games (an average game:
  138 points; last season 148).
- **Historically there is no weakness to fix.** From 2014 to 2026 our totals and margins beat KenPom's in every
  season and at every point of the season.

## Study A: scoring level shrunk toward last season

**Variant `level60`.** Two intercepts are shrunk toward last season's league average with a prior worth K = 60
team-games (30 games):
- **Efficiency intercept** (`b0`), toward last season's points per 100 possessions.
- **Pace intercept** (`p0`), toward last season's pace.

The prior weight is scaled by the average game weight, like the team priors. With 2 games in, the level stays near
last season's. By about 100 games it is the current season's.

**What does not change:** everything else in `ratings.fit`, including the Four Factors intercepts.

**Sensitivity (reported, not chosen from):** K = 20 and K = 200.

**Measured:**
- **Stage 1:** totals and margin average miss in each season's first 21 days and over the full season, 2014-2026,
  plus a replay of the live Nov 2-4, 2026 games.
- **Final model:** the production walk-forward (`audit/common.frame`), with average miss and the audit's
  opener-play table (`audit/a2_timing.score`).

**Primary:** stage-1 totals average miss, days 0-20, pooled 2014-2026, together with the live Nov 2-4 replay.

**"Adopt" (a proposal to Chad, not a change) requires all three:**
- the primary improves;
- no season's full-year totals or margin average miss gets worse by more than 0.02;
- the final model's opener plays are not worse.

## Study B: the final model with less KenPom and Barttorvik

The stage-2 ridge is refit chronologically (`projection.walk_forward`: each season trained on earlier seasons
only), with inputs switched off by setting them constant, so the ridge gives them no weight:

| Variant | What is switched off |
|---|---|
| `B1 no_bt` | the Barttorvik margin and total |
| `B2 no_kp` | the KenPom margin and total, and their early-season terms |
| `B3 own_stage2` | B1 and B2 together. Stage 1 still uses the KenPom/Barttorvik preseason prior |
| `B4 own_only` | B3, plus a stage-1 preseason prior from our own ratings: last season's final ratings (fit with no outside prior), carried at 60% (fixed now, not tuned) |

**Measured, for each variant against the current model (base):**
- final margin and total average miss, overall and in days 0-20, for 2015-2026;
- the opener-play table: spreads at 2.5+, totals at 3+, 2015-17 and 2024-26, with win %, ROI at -110, and the mean
  line move toward our side by the close.

**Reading.** A variant counts as "no worse" when:
- both average misses are within 0.05 of base;
- every opener-play win % is within 1 point of base;
- the mean move toward us is within 0.1 point of base.

Anything better or worse is described as measured. No variant goes live from this study. Any change is a new
model version with its own shadow run and Chad's approval.

## Limits stated now

- **The production backtest is not exactly live.** It uses game-day FanMatch for KenPom (`audit/AUDIT_v2.md`), so
  the KenPom variants are compared on that frame.
- **The opening-week totals shift is live only.** The shift to KenPom's level is not in the backtest.
- **B4's prior factor of 0.6 is a guess, fixed in advance.** A different factor could do better. Testing that would
  be a separate, pre-registered step.
