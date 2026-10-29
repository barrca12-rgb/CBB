# Stake by edge band (written Oct 29, 2026, before any result was computed)

Research only (`research/stake_bands/`). Nothing live changes: picks, thresholds, the bet log, the tracker's stake
multiplier and CLV cap, and the tripwires are untouched. This is a proposal for the Jan 15, 2027 read. The Oct 26
quarter-Kelly answer (0.5 / 1 / 1.25 / 2 units with a CLV drawdown rule) was never adopted; live stakes are flat 1
unit, and band B (0.5 unit) goes live separately.

## Question
Does staking by edge band return more per unit risked than flat staking, without a worse drawdown per unit risked?

## Schedules compared (identical plays within each pair, chronological order)
| | Plays | Stake |
|---|---|---|
| (a) | v1 only (spreads 2.5+, totals 3+) | flat 1 |
| (b) | v1 + band B | flat 1 |
| (b') | v1 + band B | v1 1, band B 0.5 (what is live once band B starts; reported for reference) |
| (c) | v1 + band B | the schedule below |
| (d) | v1 + band B | the schedule with the drawdown rule |

**Schedule (units by opener edge, points):**
| Band | Spreads | Totals | Stake |
|---|---|---|---|
| B | 2.0 to < 2.5 | 2.0 to < 3.0 | 0.5 |
| core | 2.5 to < 4.0 | 3.0 to < 4.0 | 1.0 |
| top | 4.0+ | 4.0+ | 1.25 |

- **Totals mapping:** the lower band is band B in each market (it ends at that market's v1 cutoff, 2.5 for spreads
  and 3 for totals); the 1-unit band runs from the v1 cutoff to 4 in both markets; 4+ is 1.25 in both.
- **Cap at 1.25:** the 5+ spread band's 64% rests on about 300 plays (research/edges, Oct 26), so no band goes higher.

**Drawdown rule (d), exact implementation:**
- Window: the trailing 150 plays of schedule (d) itself (v1 + band B, both markets pooled, like the live model
  tripwire), each play's CLV = opener-to-close move toward the bet, in points (spreads: side x (opener home spread
  - close home spread); totals: side x (close total - opener total)), unweighted by stake. Pushes count.
- Timing: the state for date D is set before D's plays from plays on earlier dates only (no same-day information).
- Before 150 plays exist the state is "full". Then: full -> **half** when the trailing mean is **below +0.4**;
  half -> **full** when it is **above +0.7**; between +0.4 and +0.7 the state carries over (hysteresis).
- Half state: every stake of schedule (c) is multiplied by 0.5 (0.25 / 0.5 / 0.625).
- The window carries over season boundaries within a period; each period (2024-26, 2014-17) starts fresh.

## Data and plays
- **Frame:** `research/persistent_disagreement/common.baseline()`: live-like walk-forward v1 forecasts (stage-2 fit
  on 2013..s-1), the opening-week totals rule.
- **Periods:** primary 2023-24 to 2025-26 (seasons 2024-2026); second check 2014-2017 (the ESPN "Opening" era).
  2018-2023 have no openers.
- **Lines:** ESPN opener (`open_home_spread`, `open_total`); close for CLV (`home_spread`, `total`). Records flagged
  `swapped` are excluded in both markets (as `research/quant/common.plays`). A play needs the opener, the close is
  needed only for CLV (a play without a close has no CLV and is skipped by the window).
- **Edge:** spreads final_margin + open_home_spread (home side); totals final_total - open_total (over side).
- **Selection:** |edge| at or above the band floor and EV >= +2% at the price, win chance from `run_day.win_prob`
  (spreads 0.5 + 0.0255 x edge capped 0.58; totals 0.5 + 0.014 x edge capped 0.565).
- **Price:** openers have no recorded price: **assumed -110** both sides. Note (known before running, from the
  formula): at -110 the +2% EV rule needs a win chance of 53.43%, so it never binds on spreads at 2.0+ but drops
  totals edges below 2.45. Band B for totals is therefore effectively 2.45 to < 3.0 at -110; reported as is.
- **Grading:** cover = side x (result - line); a win pays stake x 100/110, a loss costs the stake, a push 0. Units
  risked = sum of stakes, pushes included.
- **Order:** by date, then game_id, spreads before totals within a game.

## Metrics (per schedule; all, spreads, totals; per period)
- plays, units risked, units won, **units won per unit risked (key number)**, win % (pushes out), mean CLV;
- maximum drawdown in units (largest peak-to-trough fall of cumulative units in play order, peak starting at 0) and
  drawdown per unit of average stake;
- for (d): share of plays staked in the half state and the number of state changes;
- by band: plays, win %, mean CLV, ROI at 1 unit (the gradient the schedule relies on);
- a date-clustered bootstrap (10,000 draws, seed 20261029) 95% interval for the per-unit-risked return of (c) minus
  (b'), the schedule's only change relative to what will be live.
- **By market under (d):** the rule's state is pooled, so a market's figures are its share of the pooled run.

## Recorded prices (2025-26)
Recorded prices exist only for dated DraftKings samples (`research/market/data`; 2025-26 dates 2025-11-08,
2026-01-10, 2026-03-07), first-observed quotes, not the ESPN opener. A full-season 2025-26 result at recorded prices
is not feasible. Reported as a size check only: the spread plays on those dates from
`research/persistent_disagreement` pool C (strict pre-quote inputs, recorded prices), plays and units under each
schedule. No conclusion is drawn from it.

## Jan 15 criterion (fixed here, before results)
Band B's first 300 live plays are judged on the protocol's primary CLV; thresholds are set in PROPOSAL.md from the
backtest's band-B CLV spread (standard deviation) and stated as numbers the Jan 15 read can check directly.

## Decision rule for the proposal
The schedule is proposed only if, at 2024-26, (c) returns more per unit risked than (b') and (b) in both markets or
pooled with neither market worse by more than 1 point of ROI, and its drawdown per unit of average stake is not
worse than (b')'s. The 2014-17 check must not reverse the sign of (c) minus (b'). The drawdown rule (d) is proposed
only if it lowers the maximum drawdown without lowering units won per unit risked by more than 0.5 points.
