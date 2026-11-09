# Selection cut (pre-registered Nov 9, 2026, before any result; Chad: "improve the results now")

Live 2026-27: plays logged on game day (after the market has moved) have Pinnacle CLV +0.42, 45% beat the close;
only 47% of all plays beat Pinnacle's close. Question: which plays carry the model's edge?

**Tests (walk-forward frame, production model with the Nov 7 blowout correction applied, seasons with openers
2015-17 and 2024-26):**
1. Late plays: the same model's plays made against the closing number (stand-in for game-day plays) vs against the
   opener, by threshold. If plays at the close win under 52.4% in both periods, game-day plays are cut.
2. Edge bar: opener plays at spread thresholds 2.5 / 3 / 3.5 / 4 and total thresholds 3 / 3.5 / 4 / 4.5.
   A higher bar is adopted only if it wins more AND makes more units (ROI x volume) in BOTH periods.

**Live check:** the same cuts on this season's logged plays (record, units, Pinnacle CLV), descriptive.
Anything adopted goes live with a MODEL_FREEZE entry and a Discord note.

## Test 3 (added before running it, after tests 1-2)
Stake by edge instead of cutting plays: 1u at the bar, 1.5u at bar+1, 2u at bar+2 (spreads bar 2.5, totals 3).
Adopt only if units AND ROI per unit risked both beat flat 1u in BOTH periods.
