# Win-probability rule re-fit: log and result (Oct 29, 2026)

Research only (`research/winprob/`, pre-registration `PLAN.md`, script `fit.py`, outputs `out/`, run log
`out/fit_run.txt`). Nothing live changed. 2024-26 was used in earlier research (`research/calibration/LOG.md`), so
the check is exploratory, not an untouched holdout.

## Verdict: closed, both markets
| Market | Fitted rule (2014-17) | 2024-26 check (log-lik/game, fitted − live) | Removed v1 plays/season | Removed plays | Kill rule |
|---|---|---|---|---|---|
| Spreads | min(50% + **1.97%**·e, cap not binding below 12.7 pts) | +0.00071 [−0.00045, +0.00179] pass | **5.7** (assumed prices); 3 plays in the recorded sample (≈19/season scaled) | assumed: 54.3%, ROI −0.2% [−7.5, +7.0], CLV +0.71 pts; recorded: 1-2, −1.18 u | **closed:** < 20/season |
| Totals | min(50% + **1.38%**·e, 56.0%) | −0.00003 [−0.00013, +0.00006] fail | **3.5** (assumed); 0 recorded | assumed: 52.4%, ROI −2.5% [−18.6, +13.3], CLV +1.70 | **closed:** check fails; < 20/season |

- **Spreads:** the rule is about 1.5 pp generous at edges 2-4 in development, as the prior said, but the fitted
  slope (1.97% per point) gives ≥ 58% from 4 points, so the candidate (min of live and fitted) only lowers p at
  edges 2.5-4. At −110 nothing changes. The candidate removes a play only at −117 to −123 (edge 2.5), −122 to −129
  (edge 3) or −127 to −131 (edge 3.5). DraftKings first-observed spread prices are that bad for about 3-4% of sides
  (−118: 2.9%, −120 or worse: 0.9%), so about 6 plays a season would go, and they did not lose clearly.
- **Totals:** the fit reproduces the live rule (1.38%/56.0% vs 1.4%/56.5%). There is nothing to re-fit.
- **Prior vs data:** the prior's "dozens a season at −120 and worse" fails because DraftKings rarely posts −120 or
  worse on these markets (0.9% of spread sides, 0.2% of total sides on the 12 sampled dates), and the live card
  shops across books, so real prices are, if anything, better than this.
- **The request's band table** is not reproduced exactly in this frame. Development (2014-17) spread opener rates are
  55.5 / 54.9 / 55.8 / 54.3% at 2-2.5 / 2.5-3 / 3-4 / 4-5, against 55.7 / 57.0 / 58.0 / 58.0% from the rule. In
  2024-26 they are 54.0 / 56.0 / 58.4 / 59.4%, so the rule is generous only below 3 points there. The quoted totals
  rates (55.3-56.2% at 2-4) were above the live totals rule, as PLAN.md noted before computing.

## Fitted rule (binomial MLE, 2014-17 openers, |edge| ≥ 2, pushes out, swaps out; date-clustered bootstrap, 1,000)
| Market | Games | Slope (95%) | Cap (95%) | Cap binds from |
|---|---|---|---|---|
| Spreads | 4,039 | 0.0197 [0.0156, 0.0268] | 0.750 = grid edge [0.575, 0.750]: not identified | 12.7 pts (beyond nearly all data) |
| Totals | 9,259 | 0.0138 [0.0056, 0.0237] | 0.560 [0.5475, 0.750] | 4.35 pts |
| Live | | spreads 0.0255, totals 0.014 | 0.58, 0.565 | 3.14, 4.64 pts |

Candidate rule = min(live p, fitted p), so it can only remove plays.

## Band tables (opener, win % with pushes excluded; `out/bands_*.csv`)
| Spreads band | Dev games | Dev observed | 2024-26 games | 2024-26 observed | Live | Fitted | Candidate |
|---|---|---|---|---|---|---|---|
| 2-2.5 | 1,438 | 55.5 | 1,521 | 54.0 | 55.7 | 54.4 | 54.4 |
| 2.5-3 | 951 | 54.9 | 978 | 56.0 | 57.0 | 55.4 | 55.4 |
| 3-4 | 977 | 55.8 | 868 | 58.4 | 58.0 | 56.7 | 56.7 |
| 4-5 | 418 | 54.3 | 283 | 59.4 | 58.0 | 58.7 | 58.0 |
| 5-6 | 146 | 67.1 | 79 | 59.5 | 58.0 | 60.6 | 58.0 |
| 6+ | 109 | 69.7 | 60 | 66.7 | 58.0 | 65.8 | 58.0 |

| Totals band | Dev games | Dev observed | 2024-26 games | 2024-26 observed | Live | Fitted |
|---|---|---|---|---|---|---|
| 2-2.5 | 1,054 | 52.5 | 1,904 | 51.3 | 53.1 | 53.1 |
| 2.5-3 | 992 | 54.1 | 1,477 | 52.8 | 53.8 | 53.8 |
| 3-4 | 1,487 | 55.2 | 1,829 | 55.2 | 54.9 | 54.8 |
| 4-5 | 998 | 55.4 | 988 | 55.2 | 56.2 | 55.9 |
| 5-6 | 722 | 55.4 | 421 | 58.4 | 56.5 | 56.0 |
| 6+ | 4,006 | 56.0 | 398 | 57.0 | 56.5 | 56.0 |

(Rule columns are the mean p over the band's games, so they differ slightly between periods.)

## Where each rule starts removing plays (worst price that clears +2%; `out/break_prices.csv`)
| Edge | Spreads live | Spreads candidate | Totals live | Totals candidate |
|---|---|---|---|---|
| 2.5 | −123 | −116 | | |
| 3 | −129 | −121 | −113 | −113 |
| 3.5 | −131 | −126 | −116 | −116 |
| 4 | −131 | −131 | −119 | −119 |
| 4.5 | −131 | −131 | −123 | −121 |
| 5+ | −131 | −131 | −124 | −121 |

A play is removed only when its price is worse than the candidate number and no worse than the live number.

## Removal table, 2024-26 v1 plays
**R, recorded prices** (DraftKings first-observed complete market, Odds API change logs, 9 dates in 2024-26, 923
quoted games in the frame; graded at the DraftKings number and price; CLV = that number to the ESPN close):

| Market | Set | Plays | W-L-P | Win % | Units | ROI | CLV pts | Median price |
|---|---|---|---|---|---|---|---|---|
| Spreads | v1 plays | 102 | 59-43-0 | 57.8 | +10.05 | +9.9% | +0.87 | −110 |
| Spreads | removed | **3** | 1-2-0 | 33.3 | −1.18 | −39.3% | +0.67 | −122 |
| Totals | v1 plays | 175 | 102-72-1 | 58.6 | +20.87 | +11.9% | +1.38 | −110 |
| Totals | removed | **0** | | | | | | |

The removed spread plays: 2025-11-08 game 401827504 (edge 3.3, −125, lost), 2026-03-07 401825564 (2.8, −122, lost),
2026-03-07 401823834 (2.6, −122, won). Scaled to a season, about 19 spread and 0 total removals, but this is
3 plays: **too sparse** (PLAN.md threshold 30), so A carries the count.
`bets/bets.csv`: 9 live bets, none graded yet (prices −105 to −118); nothing to use.

**A, ASSUMED prices** (every 2024-26 v1 opener play, ESPN opener, priced from the pooled DraftKings first-observed
side-price distribution of the 12 quote dates 2022-26, independent of edge and outcome; expected values):

| Market | v1 plays/season | Removed/season (2024 / 2025 / 2026) | Removed W-L | Win % | ROI at own price (95%) | CLV pts removed / all v1 |
|---|---|---|---|---|---|---|
| Spreads | 759 | **5.7** (5.8 / 5.9 / 5.2) | 9.2-7.7 | 54.3 | −0.2% [−7.5, +7.0] | +0.71 / +1.13 |
| Totals | 1,197 | **3.5** (3.4 / 3.3 / 3.8) | 5.5-5.0 | 52.4 | −2.5% [−18.6, +13.3] | +1.70 / +1.67 |

DraftKings first-observed side prices (2,384 sides each; `out/price_dist_*.csv`): spreads −110 or better 78.6%,
−111 to −114 9.6%, −115 to −119 11.0%, −120 to −124 0.8%, −125 or worse 0.1%. Totals: 80.4%, 11.0%, 8.4%, 0.2%, 0.0%.

## Every specification run (one run of `fit.py`; nothing re-run or changed after seeing results)
| Market | Spec | n | Slope | Cap | 2024-26 ll/game | Removed/season (assumed) | Removed ROI |
|---|---|---|---|---|---|---|---|
| Spreads | **primary** 2014-17, e ≥ 2 | 4,039 | 0.0197 | 0.75 (edge of grid) | −0.68388 | 5.7 | −0.2% |
| Spreads | S1 2015-17 | 2,976 | 0.0203 | 0.75 (edge) | −0.68383 | 3.6 | +1.4% |
| Spreads | S2 2 ≤ e < 6 | 3,930 | 0.0184 | 0.61 | −0.68446 | 9.9 | +2.6% |
| Spreads | S3 slope only, cap 0.58 | 4,039 | 0.0170 | 0.58 | −0.68479 (worse than live) | 25.7 | +2.4% [−3.6, +8.6] |
| Spreads | S4 cap only, slope 0.0255 | 4,039 | 0.0255 | 0.75 (edge) | −0.68409 | 0 | |
| Spreads | info: fit on 2024-26 itself | 3,789 | 0.0218 | 0.75 (edge) | −0.68379 | 1.0 | +1.0% |
| Spreads | live | | 0.0255 | 0.58 | −0.68458 | | |
| Totals | **primary** 2014-17, e ≥ 2 | 9,259 | 0.0138 | 0.56 | −0.68944 | 3.5 | −2.5% |
| Totals | S1 2015-17 | 5,609 | 0.0158 | 0.62 | −0.68973 | 0 | |
| Totals | S2 2 ≤ e < 6 | 5,253 | 0.0134 | 0.5575 | −0.68944 | 9.0 | +4.4% |
| Totals | S3 slope only, cap 0.565 | 9,259 | 0.0143 | 0.565 | −0.68944 | 0 | |
| Totals | S4 cap only, slope 0.014 | 9,259 | 0.014 | 0.56 | −0.68945 | 0.6 | +3.7% |
| Totals | info: fit on 2024-26 itself | 7,017 | 0.0122 | 0.5725 | −0.68931 | 39.8 | +6.5% [+0.8, +12.2] |
| Totals | live | | 0.014 | 0.565 | −0.68941 | | |

- **No specification passes the kill rule.** The only development specification with 20+ removals a season is
  spreads S3. It fits 2024-26 worse than live and removes plays that won (+2.4% ROI at their price). The totals
  2024-26 self-fit (40/season, informational only) removes plays that won clearly (+6.5%).
- **Failures and caveats:**
  - The spread cap is not identified: the MLE pushes it to the grid edge (0.75). With the slope at 1.97% it would
    bind only above about 12.7 points, so it is effectively "no cap". It does not matter for removals, because
    the candidate takes min(live, fitted) and the live 58% cap binds first.
  - Recorded-price forecasts are live-like, not the strict D−2 inputs of the rotation-totals study. First-observed
    quotes are not proven openers, and DraftKings alone understates the prices the card would actually take
    (it shops across books).
  - CLV drops closes more than 20 points from the opener as data errors (e.g. a −125 spread in the frame).
  - The opener frames assume −110 at the ESPN opener, so the full-season count rests on the assumed price
    distribution.
