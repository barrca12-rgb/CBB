# The 3-4 totals band on live-like inputs: plan (written Oct 31, 2026, before this run)

Research only. Nothing live changes. v1's totals cutoff of 3 is frozen, and the Nov 16 read judges it on live data.

## Why
The Oct 26 band table lowered the live totals cutoff from 4 to 3 ("totals at 3-4 win about 55.5% with CLV
+0.95"). It came from the production frame, which knew each game's referee crew and game-day KenPom. The opener never
has either. The Oct 28 three-season backtest of the pooled 3+ band was live-like. The question here is the 3-4 band
alone, and within it the 3-3.49 half.

## Disclosure (before running)
The live-like 3-3.5 and 3.5-4 numbers were already computed on Oct 30 (`research/band_b/LOG.md`): 3-3.5 won 55.5%
in 2014-17 and 53.6% in 2024-26. So this is not a blind test of 3-3.49.
- **Set by the brief, not chosen after seeing those numbers:** the kill rule, the bands and the eras.
- **New in this run:** the 4-4.99 and 5+ split, the band-by-band production-frame comparison, and the recorded-price
  rows.

## Prior (the brief's)
The leak inflated 2-3 by about 2.5 points, so 3-3.5 is probably about 53-54% on the live-like frame.

## Kill rule (the brief's, fixed now)
The 3-3.49 band is **not supported** if either holds:
- its win rate at the opener is at or below 53.0% in **both** eras (2014-17 and 2024-26);
- its mean opener CLV is under +0.3 points (both eras pooled).

## What is computed (`run.py`)
1. **Live-like frame** (`research/persistent_disagreement` baseline): crews unknown, KenPom from the day before, the
   live opening-week totals rule, swapped records out.
   - ESPN opener plays in seasons 2015-2017 and 2024-2026, for totals bands 3-3.49, 3.5-3.99, 4-4.99 and 5+.
   - By era, overs and unders separately: plays, win % (pushes out), ROI at −110, mean opener-to-close CLV.
   - A date-clustered interval on win %.
2. **Production frame,** for the leak line: the same walk-forward stage-2 fits applied to the training frame as
   recorded (game-day crews and KenPom), same bands.
   - Its 3-4 rows are checked against the Oct 26 table (overs 56.2% on 1,860 plays, unders 54.8% on 1,561).
   - The leak per band is production minus live-like, in win-rate points and CLV.
3. **Recorded 2025-26 prices** (the only recorded sample: DraftKings first-observed quotes on Nov 8, Jan 10 and
   Mar 7, `research/rotation_totals`):
   - per band: edges, plays passing +2% EV at the recorded price, and their W-L and units.
   - Descriptive only; the sample is small.

## Verdict rules
- **3-3.49 clears the kill rule:** no change. The Oct 26 decision stands on live-like evidence.
- **3-3.49 fails:** v1's cutoff is not changed. From Nov 3, totals plays at edge 3.0-3.49 are tagged `t3` in the bet
  log, with a protocol appendix: descriptive at Nov 16; at Jan 15, a primary CLV below 0 on 100+ plays sends a
  proposal to raise the cutoff to 3.5 to Chad.
