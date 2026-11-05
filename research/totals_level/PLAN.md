# Totals: tracking the season's scoring level (pre-registered)

Written Nov 5, 2026, before any result was computed. Chad, Nov 5: "do 2 and 3" (2 = totals study). Backtest only;
nothing live changes.

## Why

Totals are where the model trails the closing line most: correlation with the final score 0.465 against the
close's 0.484 in the first 21 days (backtest 2015-2026), and 0.36 against 0.40 live Nov 1-4. Live games have landed
2.7 points under the closing total. The model's view of the season's scoring level comes from:
- stage 1's intercepts (the opening-day fix in research/own_ratings Study A shrinks them toward last season; it
  helped only this season's thin opening day and is ready to propose for next season);
- stage 2's `season_avg_total`: last season's average total until 200 games are played, then this season's average
  so far (a hard switch).

## Variants (all on the production walk-forward frame, `audit/common.frame` with the own-ratings base stage 1)

- **T0, base.**
- **T1, primary: recent-miss correction.** final total + k x (average of actual minus model total over every D-I
  game in the same season played in the previous 7 days, needing at least 50 such games; otherwise no correction),
  k = 0.5. Only games before the play's date are used. Sensitivity (reported, not chosen from): k = 0.25 and 1.0,
  and a 14-day window at k = 0.5.
- **T2, secondary: smooth scoring environment.** `season_avg_total` = (last season's average x 400 + this season's
  points so far) / (400 + games so far), instead of the 200-game switch; stage 2 refit walk-forward.

## Measured (2015-2026)

- Final total average miss and bias: days 0-20, days 21-60, all.
- Opener totals at 3+ points (`audit/a2_timing.score`): plays, win %, ROI at -110 and line move toward us, 2015-17
  and 2024-26.

## Proposal rule (all three)

- Total average miss lower than T0 in days 0-20 and over all games.
- Opener totals win % not lower than T0 by more than 0.3 points in either period.
- Opener totals win % higher than T0 in at least one period.

A passing variant goes to Chad as a proposal (MODEL_FREEZE entry, Discord note). If both pass, the one with the
lower all-games miss.

## Limits stated now

- T1 uses results the live card has by the morning of each day; the backtest uses every game on earlier dates,
  which matches that.
- Opener plays assume -110.
