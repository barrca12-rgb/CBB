# Stake by edge band: proposal for the Jan 15, 2027 read

To Chad. Research only; nothing live changes before Jan 15. Plan written first: `PLAN.md`. Script:
`backtest.py` (output in `out/results.txt`, `out/summary.csv`, `out/bands.csv`, `out/plays.csv`).

**Proposed schedule:** units by opener edge.

| Band | Spreads | Totals | Stake |
|---|---|---|---|
| B | 2.0 to 2.49 | 2.0 to 2.99 | 0.5 |
| Core | 2.5 to 3.99 | 3.0 to 3.99 | 1 |
| Top | 4+ | 4+ | 1.25 |

The top band is capped at 1.25 because the 5+ band's 64% rests on about 300 plays. Once band B is live, the only
change this makes is the 1.25 top band. The stakes multiply the tracker's existing stake multiplier and CLV cap,
which stay as they are.

## Backtest
- **Plays:** ESPN opener, in date order, with live-like walk-forward v1 forecasts. Records flagged as swapped are
  excluded.
- **Prices:** −110 assumed, because openers have no recorded prices.
- **v1 check:** v1's plays reproduce the stored 2024-26 record exactly: spreads 1310-958-8, totals 2028-1608-9.
- **Drawdown in units:** the largest peak-to-trough fall, in play order.

| Stakes | Plays | Risked | Won | **Won / risked** | Max DD | Spreads: won/risked (DD) | Totals: won/risked (DD) | 2014-17: won/risked (DD) |
|---|---|---|---|---|---|---|---|---|
| (a) flat 1, v1 only | 5,921 | 5,921 | +468.5 | **+7.91%** | 21.8 | +10.23% (17.6) | +6.46% (20.1) | +6.59% (49.8) |
| (b) flat 1, v1 + band B | 9,113 | 9,113 | +529.2 | **+5.81%** | 49.5 | +7.40% (32.2) | +4.67% (35.8) | +6.14% (44.3) |
| (b′) live once band B starts (1 / 0.5) | 9,113 | 7,517 | +498.9 | **+6.64%** | 35.2 | +8.46% (22.2) | +5.40% (24.5) | +6.34% (45.9) |
| (c) schedule | 9,113 | 8,075 | +549.2 | **+6.80%** | 36.3 | +8.69% (23.0) | +5.60% (27.5) | +6.45% (58.5) |
| (d) schedule + drawdown rule | 9,113 | 8,005 | +543.5 | **+6.79%** | 36.3 | +8.82% (23.0) | +5.50% (27.5) | +7.15% (37.3) |

The main columns are 2023-24 to 2025-26. The 2014-17 era is the second check.

- **Schedule (c) vs live (b′):**
  - Return per unit risked is +0.16 points higher. The date-clustered 95% interval is −0.06 to +0.39.
  - That adds about 50 units over three seasons on 7% more money risked.
  - Drawdown per unit of average stake is 41.0, against 42.7 for (b′).
  - The gain shows in both markets.
  - In 2014-17 the sign holds (+0.11 points), but the maximum drawdown is larger: 58.5 against 45.9. That comes from
    totals: in that era 69% of totals plays had edges of 4+.
  - **Verdict:** small and not yet distinguishable from zero. It passes the plan's test.
- **Why it can work, by band (2024-26, at 1 unit):**

  | Market | Band B: win %, return | Core: win %, return | Top: win %, return |
  |---|---|---|---|
  | Spreads | 54.0%, +3.2% | 57.2%, +9.1% | 60.4%, +15.4% |
  | Totals | 52.8%, +0.7% | 55.2%, +5.4% | 56.3%, +7.5% |

  Mean opener-to-close CLV is +0.80 in band B, +1.10 in core and +2.06 in top. The return rises with edge size,
  which is what staking by band relies on.
- **Band B's cost:** v1 alone has the best return per unit risked (+7.91%). At 0.5 unit, band B lowers that to
  +6.64% and adds about 30 units. Band B totals are close to break-even.
- **Totals band B is narrower than approved:** at −110 the +2% EV rule removes totals edges below 2.45, which is
  1,726 plays over three seasons. So band B for totals is in effect 2.45 to 2.99. At better prices, more of those
  plays would qualify.
- **Drawdown rule (d), not proposed: it fails the plan's test on 2024-26.**
  - **How it works:** stakes halve when the trailing 150-play mean CLV is below +0.4 and restore above +0.7. In
    between, the state carries over. Each day's state is set from earlier dates only.
  - **2024-26:** it fired once (Nov 8-11, 2025, 140 plays). It did not change the maximum drawdown and cost 0.01
    points.
  - **2014-17:** half stakes applied to 30% of plays, mostly the 2014 season, when the model had one training season.
    It cut the maximum drawdown from 58.5 to 37.3 and raised the return to +7.15%.
  - **Your call:** you can add it as insurance. Its +0.4 trigger is the same as the live tripwire's review level.
- **Recorded prices for 2025-26 can't be tested for the full season.**
  - DraftKings recorded prices exist only for 3 dated samples. Those are first-observed quotes, not the ESPN opener,
    and the sample holds spreads only.
  - That sample has 62 plays, 19 of them band B. The schedule returns +20.5% against +20.3% for (b′), which is too
    few plays to read.
- **Caveats:**
  - Openers have no timestamps and no prices.
  - 2025-26 has been used in earlier research.
  - The CLV here runs from the opener to the close. The protocol's primary CLV (below) is measured differently.

## What band B's first 300 live plays must show by Jan 15
The count covers band B plays in both markets that have a primary close. In the backtest, band B reached 300 plays
by Dec 6-8 each season, and about 550 by Jan 14.

The schedule is proposed only if all of the following hold:

1. **Mean primary CLV at least +0.40 points.** In the backtest, band B averaged +0.80 with a standard deviation of
   1.84, a standard error of about 0.11 at 300 plays. No 300-play stretch in the backtest fell below +0.43. +0.40 is
   also the live tripwire's review level.
2. **Win rate at least 47.5% of decided plays (at least 143 of 300).** The backtest rate was 53.4%. At 300 plays the
   win rate cannot confirm an edge, because 13% of the backtest's 300-play stretches fell below 47.5%. If test 1
   passes and this one fails, wait for 600 plays rather than drop the schedule.
3. **The edge ordering holds over the same dates:**
   - v1 plays' mean primary CLV is above band B's.
   - 4+ plays' mean primary CLV is at least +0.3 points above 2.5-3.99 plays'.

   Before Jan 15 in the backtest seasons, those gaps were +0.48 to +1.03 and +0.59 to +1.70.

If test 1 fails, there is no schedule, and band B itself goes to review.

If the schedule is adopted, it would be versioned and announced the same way as the Oct 28 stake-cap change.

## Note added Oct 29 by the main session, after this proposal was written (no number above changes)
Chad switched totals band B off on Oct 29: band B is live for spreads only (protocol Appendix B). This changes two
things at Jan 15.
- **Count:** the 300-play count above is for both markets. Band B spreads alone reached about 285 plays by Jan 14
  in each backtest season (273 / 294 / 287). So Jan 15 will show about 300 spread plays or slightly fewer. Tests 1-3
  read on whatever count exists, and the count is stated.
- **Live comparison:** the right comparison is (b′) for spreads, with band B totals removed. The schedule's live
  change is then the 1.25-unit top band in both markets. A totals band B stake would apply only if totals band B is
  ever switched on.
