# Speed to the opener: first live read (Nov 5, 2026)

Backlog item 2 (research/IMPROVEMENT_BACKLOG.md). Measurement only; nothing live changed and no API was called.
Window: Oct 31 to Nov 5, 16:00 UTC. 1,123 game-book openers and 211 alerts (main and band B).
Scripts: `python -m research.speed.measure --since 2026-10-31T00:00Z` (fixed a duplicate-row lookup in the signal
log) and `python research/speed/decay.py`.

## 1. From a book posting to our alert: about 5 minutes

| Step | Time |
|---|---|
| Book posts -> our next Odds API poll | median 4.7 min, 90% within 8.9 min (10-minute cadence) |
| Poll -> alert logged | median 30 seconds |
| Alerts sent in the same run that first showed the number | 163 of 211 (77%) |
| Alerts within one more run | 19 |
| Later alerts | 29: 14 caused by a model or rule change between the first quote and the alert, 15 where the edge appeared later (ratings, injuries, crews) |

73% of alerts were at the book's opening number.

## 2. How long the alerted number stays up

Share of alerts still available at the alerted number (or better), at the same book and at any play book:

| After the alert | Same book | Any play book | Points lost at the same book (avg) |
|---|---|---|---|
| 10 min | 97% | 98% | -0.04 |
| 30 min | 88% | 90% | -0.14 |
| 1 hour | 82% | 86% | -0.20 |
| 2 hours | 75% | 80% | -0.27 |
| 4 hours | 63% | 69% | -0.43 |
| 15 min before tip | 38% | 43% | |

By time of the alert (same book):

| Alert time (ET) | Alerts | 30 min | 1 hour | 4 hours | Points lost at 4 hours |
|---|---|---|---|---|---|
| Midnight-7 am | 44 | 100% | 98% | 88% (95% still there at 8 am) | -0.15 |
| 8-11 am | 17 | 94% | 100% | 82% | +0.21 |
| Noon-5 pm | 98 | 86% | 78% | 51% | -0.66 |
| 6-11 pm | 51 | 80% | 71% | 57% | -0.43 |

## Reading

- **Polling is not where we lose the edge.** 97% of numbers are still there 10 minutes after the alert. Polling every
  3 minutes instead of 10 would cut the median delay from 4.7 to about 1.4 minutes and save roughly 1-2% of plays.
  Credits are not the constraint (95,516 Odds API credits left on Nov 5, renewal Nov 25; a 3-minute cadence costs
  about 1,440 a day), but every card run also redeploys the site, so this is a later, small gain.
- **Placing the bet is where we lose it.** Afternoon and evening alerts lose about 1 in 7 numbers within 30 minutes
  and half within 4 hours. Overnight alerts (books posting around 3 am ET) mostly survive until morning.
- **We cannot yet measure when bets are actually placed.** `bets/accepted.csv` is empty: the card's Placed button has
  not been used. Without placement times, the record assumes every play was taken at the alerted number.

## Next steps

1. Record real fills: press Placed on the card (book, line, odds, time), or import Pikkit history if Chad exports it.
   That gives the true execution delay and the real number taken.
2. Afternoon and evening alerts are the ones to act on first.
3. Revisit a 3-5 minute cadence for openers after the fills show how much of the edge survives to placement.
