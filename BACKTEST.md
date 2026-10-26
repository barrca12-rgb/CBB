# Backtest 2013-2026

## Summary

**Promising historical results; live profitability and execution remain unverified.** The 2026-27 forward test
(FORWARD_TEST_PROTOCOL.md) is the evidence that counts; these tables come from seasons reused to design the model.

Model: ratings with 3-point luck regressed, plus KenPom, Barttorvik, Four Factors, rest, home edge, missing
players, market ratings from earlier closing lines, altitude, and referee crews.

Against the opener at the live card's cutoffs (spread edge 2.5+, total edge 3+; audit/b9_item7.py):

| | 2015-2017 | 2024-2026 |
|---|---:|---:|
| Spreads vs the opener, openers oriented by their own moneylines | 57.5% (2,039) | 58.1% (2,297) |
| Totals vs the opener, referee crews unknown at the open (inputs 0, weights unchanged) | 57.9% (3,611) | 56.2% (3,993) |

The spreads row sits in a **historical spread filtering-sensitivity range of about 56-58.7%**. That range spans
the two opener seasons sets above, the opener-orientation rules (57.5-58.7%: correcting, dropping, or dropping
uncheckable openers; 58.7% is 2024-26 with no orientation check, which is not stronger evidence), and the model
timing variants in audit/AUDIT_v2.md (56.2-57.6%). It is not a confidence interval, an expected live win rate, or
a result for totals.

| Against the closing line | Result | Bets |
|---|---:|---:|
| ATS vs closing line, edge 3+, 2020-2026 | 53.6% | 3,347 |
| Over/under vs closing line, edge 4+, 2020-2026 | 54.7% | 6,323 |
| Average miss on margin, 2020-2026 (model / closing line) | 8.88 / 8.84 | |
| Average miss on total, 2020-2026 (model / closing line) | 13.09 / 13.00 | |

Break-even at -110 is 52.4%. Closing lines exclude projection services listed as books (accuscore and others, Oct
2026 cleanup).

* **Openers:** since Oct 26, 2026 each opener is checked against the moneylines recorded with it (the shorter
  moneyline marks the favourite). An opener that favours the other team is corrected; nothing uses the later
  close. Openers within 1 point or without moneylines cannot be checked and are kept (counts in
  audit/out/item7.md). The earlier rule dropped openers that sat nearer the mirrored close.
* **Referees:** crews are usually posted near tip, after the openers, so opener tables for totals use crew inputs
  of 0 under the existing weights (no refit). With crews as recorded, totals vs the opener read 58.4% / 57.4%.
* **Caveats:** openers carry low limits; openers exist only for 2014-2017 and 2024-2026; historical opener plays
  were not priced, timed or filled; data cleaning removed several fake 70-85% edges, so treat anything above
  ~60% with suspicion.

Walk-forward: each game is predicted with ratings fit only on earlier games that season, starting from KenPom's and Barttorvik's preseason ratings averaged. Closing line = median of the books in ESPN's odds feed. KenPom = FanMatch predicted score. Records are against the closing line at -110 (break-even 52.4%).

Lines dropped as bad data (closing line and KenPom favor different teams by 3+ in more than 3% of games): Nov 2013 (8%), Nov 2017 (7%).

## Winners picked (straight up, pick'em lines excluded)

| | games | model | line favorite | KenPom |
|---|---:|---:|---:|---:|
| through 2019 | 23,445 | 73.7% | 73.6% | 73.2% |
| 2020 on | 37,351 | 72.9% | 73.0% | 72.3% |
| all | 60,796 | 73.2% | 73.2% | 72.7% |

## Accuracy (games with a line and a KenPom prediction)

| | games | margin MAE | total MAE |
|---|---:|---:|---:|
| model | 61,119 | 8.75 | 13.32 |
| closing line | 61,119 | 8.71 | 13.13 |
| KenPom | 61,119 | 8.85 | 13.38 |
| ratings only (before 2nd stage) | 61,119 | 8.77 | 13.26 |

## How much of the model's disagreement with the line shows up in the result

Slope of (result - line) on (model - line). 0 = the line already knows everything the model does; 1 = trust the model fully. Same idea as the NFL model's blend weight.

| season | margin | total |
|---|---:|---:|
| 2014 | 0.29 | 0.09 |
| 2015 | 0.23 | 0.68 |
| 2016 | 0.40 | 0.32 |
| 2017 | 0.56 | 0.45 |
| 2018 | 0.52 | 0.64 |
| 2019 | 0.63 | 0.32 |
| 2020 | 0.17 | 0.46 |
| 2021 | 0.43 | 0.27 |
| 2022 | 0.19 | 0.46 |
| 2023 | 0.97 | 0.52 |
| 2024 | 0.38 | 0.38 |
| 2025 | 0.21 | 0.14 |
| 2026 | 0.15 | 0.14 |
| all | 0.60 | 0.25 |

## Spreads: betting the model's side vs the closing line, by size of disagreement

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge 0-1 pts, 2013-2019 | 10,631 | 51.2% | -2.27 |
| edge 0-1 pts, 2020-2026 | 16,921 | 50.7% | -3.23 |
| edge 1-2 pts, 2013-2019 | 7,209 | 52.0% | -0.64 |
| edge 1-2 pts, 2020-2026 | 11,319 | 50.9% | -2.75 |
| edge 2-3 pts, 2013-2019 | 3,381 | 52.5% | 0.17 |
| edge 2-3 pts, 2020-2026 | 5,543 | 51.6% | -1.46 |
| edge 3-4 pts, 2013-2019 | 1,244 | 51.4% | -1.78 |
| edge 3-4 pts, 2020-2026 | 2,108 | 53.5% | 2.07 |
| edge 4-6 pts, 2013-2019 | 581 | 54.6% | 4.16 |
| edge 4-6 pts, 2020-2026 | 1,071 | 53.3% | 1.78 |
| edge 6-+ pts, 2013-2019 | 157 | 70.7% | 34.97 |
| edge 6-+ pts, 2020-2026 | 159 | 54.7% | 4.46 |

### Spreads, edge 3+ points, by month

| | bets | win% | roi% |
|---|---:|---:|---:|
| Nov | 1,896 | 53.4% | 1.90 |
| Dec | 1,258 | 54.1% | 3.19 |
| Jan | 979 | 52.9% | 1.01 |
| Feb | 708 | 54.9% | 4.89 |
| Mar | 478 | 54.2% | 3.44 |

### Spreads, edge 3+ points, by season

| | bets | win% | roi% |
|---|---:|---:|---:|
| 2014 | 221 | 54.8% | 4.52 |
| 2015 | 333 | 51.1% | -2.54 |
| 2016 | 414 | 51.4% | -1.78 |
| 2017 | 346 | 56.6% | 8.15 |
| 2018 | 198 | 51.0% | -2.62 |
| 2019 | 470 | 56.8% | 8.45 |
| 2020 | 528 | 53.4% | 1.96 |
| 2021 | 399 | 52.4% | 0.00 |
| 2022 | 453 | 51.7% | -1.38 |
| 2023 | 413 | 59.8% | 14.18 |
| 2024 | 537 | 55.7% | 6.30 |
| 2025 | 485 | 53.6% | 2.34 |
| 2026 | 532 | 49.4% | -5.62 |

## Totals: betting the model's side vs the closing line, by size of disagreement

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge 0-1 pts, 2013-2019 | 5,073 | 51.3% | -2.01 |
| edge 0-1 pts, 2020-2026 | 10,170 | 49.7% | -5.03 |
| edge 1-2 pts, 2013-2019 | 4,438 | 52.1% | -0.50 |
| edge 1-2 pts, 2020-2026 | 8,860 | 50.5% | -3.53 |
| edge 2-3 pts, 2013-2019 | 3,569 | 52.1% | -0.45 |
| edge 2-3 pts, 2020-2026 | 7,044 | 52.3% | -0.24 |
| edge 3-4 pts, 2013-2019 | 2,519 | 54.3% | 3.75 |
| edge 3-4 pts, 2020-2026 | 4,896 | 51.1% | -2.40 |
| edge 4-6 pts, 2013-2019 | 2,713 | 54.0% | 3.09 |
| edge 4-6 pts, 2020-2026 | 4,635 | 54.2% | 3.55 |
| edge 6-+ pts, 2013-2019 | 4,186 | 54.5% | 4.07 |
| edge 6-+ pts, 2020-2026 | 1,688 | 56.0% | 6.88 |

### Totals, edge 3+ points, by month

| | bets | win% | roi% |
|---|---:|---:|---:|
| Nov | 3,753 | 52.9% | 0.92 |
| Dec | 3,746 | 53.8% | 2.79 |
| Jan | 5,349 | 54.3% | 3.61 |
| Feb | 4,669 | 54.3% | 3.57 |
| Mar | 3,075 | 52.5% | 0.20 |

### Totals, edge 3+ points, by season

| | bets | win% | roi% |
|---|---:|---:|---:|
| 2014 | 3,130 | 53.0% | 1.19 |
| 2015 | 1,072 | 59.7% | 13.98 |
| 2016 | 1,386 | 53.6% | 2.34 |
| 2017 | 1,163 | 55.5% | 5.88 |
| 2018 | 849 | 53.6% | 2.31 |
| 2019 | 1,818 | 53.6% | 2.28 |
| 2020 | 1,931 | 55.0% | 5.09 |
| 2021 | 1,268 | 52.3% | -0.18 |
| 2022 | 1,766 | 52.9% | 1.08 |
| 2023 | 1,525 | 55.5% | 5.91 |
| 2024 | 1,556 | 53.8% | 2.69 |
| 2025 | 1,477 | 49.4% | -5.77 |
| 2026 | 1,696 | 52.4% | 0.07 |

## Line movement: does the model predict which way the opener moves?

24,950 games where the line moved (seasons 2014, 2015, 2016, 2017, 2024, 2025, 2026). The line moved toward the model's side in 66.3%; 84.7% when the model disagreed with the opener by 3+.

Betting the model's side at the **opening** number:

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge vs opener 0+ | 24,563 | 52.8% | 0.83 |
| edge vs opener 2+ | 6,414 | 56.8% | 8.46 |
| edge vs opener 3+ | 2,491 | 58.9% | 12.51 |
| edge vs opener 4+ | 922 | 61.3% | 16.99 |
| edge vs opener 6+ | 156 | 69.9% | 33.39 |


## Totals vs the opener with crews unknown (as at the open)

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge 3+ pts, 2024-2026 | 3,981 | 56.2% | 7.32 |
| edge 4+ pts, 2024-2026 | 1,985 | 56.8% | 8.39 |
