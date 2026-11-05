# Same-game spread + total pairs: results (pre-registered in PLAN.md, Nov 5, 2026)

Backtest only. Nothing live changes. Rerun: `python -m research.correlated_pairs.backtest` (output in
`out/results.txt`, `out/schedules.csv`, `out/pairs.csv`). Opener plays at an assumed -110, v1 plus band B.

## Verdict: does not pass. No proposal.

| Test | 2024-26 | 2014-17 | Needed |
|---|---|---|---|
| Aligned pairs linked (pooled) | corr +0.028, 95% -0.015 to +0.071 | | above 0 with the interval above 0: **no** |
| Return kept with (b) | -0.13 pts | -0.01 pts | no more than 0.5 below: yes |
| Risk lower with (b) | daily sd 0.2130 vs 0.2139, drawdown 43.8 vs 42.7 | daily sd 0.2159 vs 0.2134, drawdown 54.3 vs 51.2 | both lower: **no** |

## What the data shows

1. **The two results are almost independent.** Across every game with both openers, the favorite's cover margin
   and the over margin barely move together: correlation -0.013 (2024-26) and -0.004 (2014-17).
   - The one exception is **favorites of 20+ points**: +0.10 and +0.15. There, a blowout does lift the total.
   - Below 20 points it is zero or slightly negative.
2. **Our paired plays split about half the time, whatever the combination.**
   - Aligned pairs split 47-48% and opposed pairs 48-50%.
   - Favorite + Under split 51% (2024-26) and 49% (2014-17).
   - No pair type has a correlation reliably different from 0.
3. **No double counting.** Legs in aligned pairs win about as often as solo plays at the same edge band (for
   example, 2024-26 spreads in the core band: 60.9% aligned, 55.8% solo; totals 4+: 59.3% vs 56.6%).
4. **Trimming aligned pairs costs units and does not lower risk.** At 0.75x, the daily swing and drawdown per unit
   staked are the same or slightly worse. A pair of nearly independent bets already diversifies, so cutting one
   kind of pair just bets less.

## The live split

Nov 1-4, 2026: favorite + Under split 6 of 11 and favorite + Over 2 of 8. Against a historical split rate near 50%
for every pair type, that is 21 games of noise. Yesterday's four favorite + Under splits were not a structural
hedge.

**Correction to what I told Chad on Nov 5.** I said favorite + Under pairs tend to split because a blowout lifts the
total. History says that only holds for favorites of 20+ points, and even there the link is small. For ordinary
spreads the two results are essentially independent, so staking each leg on its own is right.

## Limits

- Openers at an assumed -110; live plays are at real prices and pass the opener rule against the current line too.
- The 20+ favorite link is real but small (about 0.1-0.15), and few of our pairs fall there. It does not justify a
  stake rule.
