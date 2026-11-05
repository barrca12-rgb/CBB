# Same-game spread + total plays: correlation and stake (pre-registered)

Written Nov 5, 2026, before any result was computed. Chad, Nov 5: "yes backtest it". Backtest only: picks,
stakes, the bet log, the tracker's multiplier and CLV cap, and the tripwires are unchanged. Any change would be a
proposal to Chad, then a MODEL_FREEZE entry and a Discord note.

## Why

When the model has a spread play and a total play in the same game, the two results can be linked:
- **Aligned pairs** (expected to win or lose together): favorite + Over, underdog + Under. A blowout tends to lift
  the total, and a close game tends to keep it down.
- **Opposed pairs** (expected to split): favorite + Under, underdog + Over.

Each leg is staked as if it were independent. If aligned legs move together, an aligned pair is close to a single
bet at double size. Nov 1-4, 2026 (live, 21 games with both): favorite + Over split 2 of 8, favorite + Under split
6 of 11. That sample is too small to act on.

## Data

- **Plays:** the stake-band study's opener plays (`research/stake_bands/backtest.opener_plays` on
  `research/persistent_disagreement/common.baseline`): v1 (spreads 2.5+, totals 3+) and band B (spreads 2.0-2.49,
  totals 2.0-2.99) at the ESPN opener, +2% EV at an assumed -110, swapped records excluded.
- **Periods:** 2014-17 and 2024-26, reported separately (the same periods as the stake-band study).
- **Stakes, current schedule:** v1 1 unit, band B 0.5 unit (what is live, before the tracker's multiplier).
- **Favorite:** the side whose opener spread is negative. A pick'em spread (0) is not classed, and its pair is left
  out of both groups.

## Measured

1. **Structural link, all games with both openers:** the correlation between the favorite's cover margin and the
   total's over margin (points), overall and by favorite size (under 5, 5-9.5, 10-19.5, 20+).
2. **Pair outcomes:** for each group (aligned, opposed), the number of pairs, how often the legs split, and the
   correlation of the two legs' results (win 1, loss 0; pushes left out), with a date-clustered 95% bootstrap
   interval.
3. **Double counting:** win % of legs in aligned pairs, in opposed pairs and of solo plays (no other play in that
   game), by edge band (band B, 2.5/3-4, 4+).
4. **Schedules on identical plays:**
   - (a) current: each leg at its own stake;
   - (b) **primary:** each leg of an aligned pair at 0.75 x its stake;
   - (c) sensitivity: aligned legs at 0.5 x;
   - (d) sensitivity: aligned legs at 1/sqrt(1 + rho), with rho the aligned-pair result correlation estimated in
     the other period only.
   For each: plays, units risked, units won, won per unit risked, standard deviation of daily units per unit
   risked, and maximum drawdown per average stake.
5. **Live 2026-27 sample:** the same pair table for the logged main plays, descriptive only.

## Proposal rule (all three required, in both periods unless stated)

- **Linked:** the aligned-pair result correlation is above 0, with its 95% interval above 0 (both periods pooled).
- **Return kept:** (b)'s won per unit risked is no more than 0.5 points below (a)'s (date-clustered bootstrap
  point estimate), in each period.
- **Risk lower:** (b)'s daily-units standard deviation per unit risked is lower than (a)'s, and its maximum
  drawdown per average stake is not higher, in each period.

If the rule passes, (b) goes to Chad as a proposal. (c) and (d) are reported and not chosen from. Opposed pairs are
not trimmed or raised in any schedule: only aligned pairs are in question.

## Limits stated now

- Openers at an assumed -110; live plays are at real prices and pass the opener rule against the current line too.
- The live tracker's stake multiplier and CLV cap scale every stake; they are left out here and would apply on top.
- One play per market per game, as live.
