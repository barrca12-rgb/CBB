# Do early-season ratings understate mismatches? (pre-registered Nov 3, 2026, before any result below was computed)

Research only. Nothing live changes because of this study. Asked by Chad on Nov 3 (option 2 of the Nov 2 spreads
diagnosis). On Nov 2 the live model leaned toward the underdog in games with a line of 17.5 or more: −0.5 points
against the close, over 61 games. The backtested v1 leaned the other way, about +1 point toward the favorite. Big
underdogs went 6-9 (−3.5 units) with no CLV.

## Question
In a season's first 14 days, are v1's predicted margins too small in big mismatches? That is, do favorites beat the
model by more than they do later in the season, and by more than they beat the market?

## Data (fixed now)
- **Forecasts:** `research/persistent_disagreement/common.baseline()`. This is the live-like walk-forward v1
  (frozen stage-2, fit on seasons before each test season) for 2014-2026. Model margin = `final_margin` (home); actual
  = `margin`; opener = `open_home_spread`; close = `home_spread`.
- **Rows:** records flagged `swapped` are dropped.
- **Periods:** "early" is days 0-13 of each season (day 0 = the season's first game date); "later" is day 14 on.
- **Caveat, stated now:** the backtest's early-season inputs are KenPom's day-before ratings, which carry KenPom's own
  preseason prior. The live 2026-27 model uses a frozen average of the KenPom and Barttorvik preseason ratings. The
  test is therefore about v1's structure early in a season, not an exact replay of the live prior.

## Tests (each reported with a 95% interval, bootstrap by game date, 2,000 draws, seed 7)
1. **Calibration slope (H1).** Regress the actual home margin on the model's home margin, with an intercept, early
   vs later and by era (2014-17, 2024-26 where lines exist; all seasons 2014-2026 for H1). A slope above 1 means the
   model understates margins. The test is the early slope minus the later slope.
2. **Big lines against the market (H2).** Games with |opener| >= 17.5, early vs later. Two quantities, both from the
   favorite's side: the lean is model minus opener, and the outcome is actual minus opener (the same with the close
   as a check). Mismatches are understated against the market if, early, the lean is below the outcome.
3. **The betting rule (H3).** v1 plays at the opener (edge >= 2.5, the live spread threshold) grouped as underdogs of
   17.5+, other underdogs, favorites of 17.5+, other favorites; early vs later; win % and 95% Wilson interval.
4. **Live reference:** the same lean, model minus close for the favorite, on the 2026-27 cards so far.

## Decision rule (fixed now)
Report only. A rule change, such as skipping big underdogs early or stretching early-season margins, would be a
separate pre-registered proposal that needs Chad's approval and a MODEL_FREEZE entry. I propose one only if all three
hold:
- (a) the early-minus-later slope in H1 is above 0 with its 95% interval excluding 0, in both eras with lines;
- (b) H2's early lean is below its early outcome in both eras;
- (c) H3's early big-underdog plays win under 52.4% in the pooled eras.

Otherwise the finding is "no reliable evidence" and nothing changes. Every number is reported, whichever way it falls.
