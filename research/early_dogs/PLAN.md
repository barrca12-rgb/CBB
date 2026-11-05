# Early-season underdog spread plays (pre-registered)

Written Nov 5, 2026, before any result was computed. Chad, Nov 5: "yes backtest it". Backtest only: picks,
stakes, the bet log and the stage-2 weights are unchanged. Any change would be a proposal to Chad, then a
MODEL_FREEZE entry and a Discord note.

## Why

Nov 1-4, 2026, live spread plays:

| | Record | Beat the close by (avg) | KenPom on our side | Barttorvik on our side |
|---|---|---|---|---|
| Favorites | 34-23 | +2.04 | 49% | 12% |
| Underdogs | 15-21 | +0.53 | 92% | 81% |

Barttorvik rates first-week mismatches much closer than the market (20+ point spreads: 8.6 points less than the
line live, 7.4 in 2024-26). The question is whether early-season underdog plays carried by the outside ratings,
not by our own ratings, are weaker, and whether a rule would help.

## Data

- **Plays:** spread plays at the ESPN opener from `research/persistent_disagreement/common.baseline`, as in the
  stake-band study: v1 (2.5+) and band B (2.0-2.49), +2% EV at an assumed -110, swapped records excluded.
- **Early:** days 0-20 of each season (the window the own-ratings study used).
- **Periods:** 2014-17 and 2024-26, reported separately.
- **Underdog:** the play's side has a positive opener spread. Pick'em plays are left out of the underdog group.
- **Our own rating:** the stage-1 margin (`pred_margin`), the ratings built only from box scores.

## Variants

- **V0, current:** every play.
- **V1, primary:** in days 0-20, an underdog play also needs our stage-1 margin on the underdog's side of the
  opener. Everything else is unchanged, including all favorite plays and every play from day 21 on.
- **V2, secondary:** stage 2 refit without the Barttorvik inputs (the own-ratings study's cached walk-forward
  frames, `audit/out/wf_own_no_bt.pkl` against `wf_own_base.pkl`, same pipeline, 2015-2026). Early underdog plays
  are compared between the two frames.

## Measured

- Early underdog plays: count, win %, mean line move toward us (opener to close), units at -110 (v1 1 unit, band B
  0.5).
- Under V1: the removed plays (count, win %, line move) against the kept ones.
- Early spread plays and full-season spread plays: units and win % under V0 and V1.
- Descriptive: early underdog plays split by whether KenPom, Barttorvik and our stage-1 rating are on our side.

## Proposal rule (all three required)

- **Enough plays:** at least 60 removed plays, both periods pooled. Fewer: "too few to tell".
- **Removed plays are weak:** pooled, they win below 52.4% (break-even at -110) and their line move toward us is
  below the kept underdog plays'.
- **No harm:** V1's early-spread units are not lower than V0's in either period.

V2 is reported, not chosen from.

## Limits stated now

- Openers at an assumed -110; live plays are at real prices and also pass the opener rule against the current line.
- The backtest's KenPom and Barttorvik inputs follow the production frame (game-day FanMatch for KenPom); live uses
  the numbers available before the play.
