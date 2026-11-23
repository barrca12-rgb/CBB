# Kalshi log

## Nov 23, 2026: price read (PLAN.md, pre-registered Oct 28). Result: does not clear; logger stays off.

`python -m research.kalshi.evaluate`. Logger ran Oct 28 15:01 to Nov 21 03:29 UTC (switched off Nov 21 on Chad's
call after failed-run emails); 721 v1 plays were logged in that window.

| Measure | Result |
|---|---|
| Plays with a Kalshi market on our side at the alert (first snapshot within 15 min) | 305 of 721 (42%) |
| Plays where Kalshi (taker) beat the logged book | 10 (1%) |
| **Taker: mean EV gain per play (the bar)** | **+0.02%**, date-clustered 95% [+0.00%, +0.04%] |
| By market (taker) | spreads +0.01% (n 333, market 34%); totals +0.03% (n 388, market 49%) |
| Where Kalshi had a market: Kalshi minus book EV | median -13.77%, mean -18.20% |
| Maker upper bound (resting bid, 0.0175 fee, two-sided rungs only) | +0.75% [+0.57%, +0.93%]; spreads +0.50%, totals +0.97% |
| Kalshi line open before our alert | 20% of plays; median lead 5.6 h when open |

- **Bar** (mean taker gain >= +0.5%, interval above 0, n >= 40): **not met** (+0.02%).
- **Maker bound:** the first run used every rung and gave +193% per play, driven by empty rungs (bid 0.03 / ask 0.97)
  that no one would fill. The bound now uses rungs with a bid-ask spread of 10 cents or less. Even so it is an upper
  bound with unknown fill rates, and it is not the pre-registered bar.
- **Gaps:** research/kalshi/data/unmatched.csv listed Nicholls St. and University at Albany (14 events); aliases added
  to research/kalshi/aliases.csv for any future run.
- **Decision (per PLAN.md):** not added to the card's price shopping; the logger stays switched off (done Nov 21).
