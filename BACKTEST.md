# Backtest 2013-2026

## Summary (ratings with 3-point luck regressed + KenPom + Barttorvik + Four Factors + rest + home edge + availability)

| | Result | Bets |
|---|---:|---:|
| **ATS vs opening line, edge 3+, 2024-2026** | **58.2%** (2024 58.0, 2025 59.1, 2026 57.4) | 1,271 |
| **Over/under vs opening line, edge 4+, 2024-2026** | **57.5%** (2024 56.2, 2025 59.2, 2026 57.1) | 1,484 |
| ATS vs closing line, edge 3+, 2020-2026 | 53.2% | 3,436 |
| Average miss on margin, 2020-2026 (model / closing line) | 8.88 / 8.84 | |
| Average miss on total, 2020-2026 (model / closing line) | 13.12 / 13.00 | |

Break-even at -110 is 52.4%.

* **Opening lines are the edge.** Every season 2024-2026 is profitable at the opener on both spreads and totals.
* **Closing lines:** just above break-even on spreads, not on totals. The market is sharper by tip-off.
* **What moved it:** regressing 3-point makes 35% toward the league rate (opponents' 3P% is mostly luck, KenPom)
  took spreads at the opener from 57.5% to 58.2% and totals from 56.7% to 57.5%.
* **Caveats:** openers carry low limits; openers exist only for 2014-2017 and 2024-2026; data cleaning removed
  several fake 70-85% edges, so treat anything above ~60% with suspicion.

Walk-forward: each game is predicted with ratings fit only on earlier games that season, starting from KenPom's preseason ratings. Closing line = median of the books in ESPN's odds feed. KenPom = FanMatch predicted score. Records are against the closing line at -110 (break-even 52.4%).

Lines dropped as bad data (closing line and KenPom favor different teams by 3+ in more than 3% of games): Nov 2013 (8%), Nov 2017 (6%).

## Winners picked (straight up, pick'em lines excluded)

| | games | model | line favorite | KenPom |
|---|---:|---:|---:|---:|
| through 2019 | 23,809 | 73.5% | 73.6% | 73.2% |
| 2020 on | 37,366 | 72.9% | 73.0% | 72.3% |
| all | 61,175 | 73.1% | 73.2% | 72.6% |

## Accuracy (games with a line and a KenPom prediction)

| | games | margin MAE | total MAE |
|---|---:|---:|---:|
| model | 61,463 | 8.76 | 13.33 |
| closing line | 61,463 | 8.71 | 13.13 |
| KenPom | 61,463 | 8.85 | 13.39 |
| ratings only (before 2nd stage) | 61,463 | 8.78 | 13.26 |

## How much of the model's disagreement with the line shows up in the result

Slope of (result - line) on (model - line). 0 = the line already knows everything the model does; 1 = trust the model fully. Same idea as the NFL model's blend weight.

| season | margin | total |
|---|---:|---:|
| 2014 | 0.31 | 0.08 |
| 2015 | 0.16 | 0.71 |
| 2016 | 0.37 | 0.27 |
| 2017 | 0.51 | 0.41 |
| 2018 | 0.51 | 0.56 |
| 2019 | 0.62 | 0.23 |
| 2020 | 0.17 | 0.28 |
| 2021 | 0.38 | 0.23 |
| 2022 | 0.14 | 0.44 |
| 2023 | 0.96 | 0.37 |
| 2024 | 0.39 | 0.24 |
| 2025 | 0.20 | -0.06 |
| 2026 | 0.15 | -0.04 |
| all | 0.58 | 0.19 |

## Spreads: betting the model's side vs the closing line, by size of disagreement

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge 0-1 pts, 2013-2019 | 10,696 | 51.4% | -1.96 |
| edge 0-1 pts, 2020-2026 | 16,652 | 50.8% | -3.11 |
| edge 1-2 pts, 2013-2019 | 7,339 | 51.5% | -1.59 |
| edge 1-2 pts, 2020-2026 | 11,547 | 50.9% | -2.92 |
| edge 2-3 pts, 2013-2019 | 3,437 | 52.8% | 0.76 |
| edge 2-3 pts, 2020-2026 | 5,475 | 50.8% | -2.99 |
| edge 3-4 pts, 2013-2019 | 1,277 | 49.6% | -5.22 |
| edge 3-4 pts, 2020-2026 | 2,185 | 51.6% | -1.44 |
| edge 4-6 pts, 2013-2019 | 594 | 52.9% | 0.92 |
| edge 4-6 pts, 2020-2026 | 1,092 | 55.3% | 5.59 |
| edge 6-+ pts, 2013-2019 | 158 | 70.3% | 34.12 |
| edge 6-+ pts, 2020-2026 | 150 | 58.0% | 10.73 |

### Spreads, edge 3+ points, by month

| | bets | win% | roi% |
|---|---:|---:|---:|
| Nov | 1,845 | 53.6% | 2.34 |
| Dec | 1,211 | 51.4% | -1.94 |
| Jan | 1,067 | 52.4% | 0.02 |
| Feb | 805 | 54.0% | 3.16 |
| Mar | 522 | 52.7% | 0.57 |

### Spreads, edge 3+ points, by season

| | bets | win% | roi% |
|---|---:|---:|---:|
| 2014 | 213 | 54.0% | 3.07 |
| 2015 | 382 | 48.2% | -8.04 |
| 2016 | 353 | 47.9% | -8.60 |
| 2017 | 414 | 55.6% | 6.06 |
| 2018 | 253 | 48.6% | -7.19 |
| 2019 | 414 | 57.5% | 9.75 |
| 2020 | 402 | 54.2% | 3.53 |
| 2021 | 402 | 51.2% | -2.17 |
| 2022 | 527 | 50.9% | -2.92 |
| 2023 | 425 | 58.1% | 10.95 |
| 2024 | 530 | 53.6% | 2.30 |
| 2025 | 549 | 53.4% | 1.89 |
| 2026 | 601 | 51.9% | -0.89 |

## Totals: betting the model's side vs the closing line, by size of disagreement

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge 0-1 pts, 2013-2019 | 5,688 | 51.6% | -1.56 |
| edge 0-1 pts, 2020-2026 | 11,354 | 50.8% | -3.10 |
| edge 1-2 pts, 2013-2019 | 4,879 | 51.0% | -2.65 |
| edge 1-2 pts, 2020-2026 | 9,821 | 50.3% | -4.03 |
| edge 2-3 pts, 2013-2019 | 3,628 | 53.3% | 1.77 |
| edge 2-3 pts, 2020-2026 | 7,164 | 49.9% | -4.68 |
| edge 3-4 pts, 2013-2019 | 2,471 | 53.0% | 1.13 |
| edge 3-4 pts, 2020-2026 | 4,327 | 51.3% | -2.01 |
| edge 4-6 pts, 2013-2019 | 2,318 | 53.1% | 1.47 |
| edge 4-6 pts, 2020-2026 | 3,522 | 52.8% | 0.88 |
| edge 6-+ pts, 2013-2019 | 3,824 | 53.6% | 2.39 |
| edge 6-+ pts, 2020-2026 | 1,102 | 51.1% | -2.47 |

### Totals, edge 3+ points, by month

| | bets | win% | roi% |
|---|---:|---:|---:|
| Nov | 3,297 | 52.2% | -0.29 |
| Dec | 3,255 | 53.1% | 1.47 |
| Jan | 4,373 | 52.7% | 0.54 |
| Feb | 3,711 | 53.5% | 2.07 |
| Mar | 2,877 | 51.0% | -2.59 |

### Totals, edge 3+ points, by season

| | bets | win% | roi% |
|---|---:|---:|---:|
| 2014 | 3,137 | 52.9% | 1.08 |
| 2015 | 873 | 57.0% | 8.90 |
| 2016 | 1,102 | 54.7% | 4.46 |
| 2017 | 1,049 | 54.6% | 4.28 |
| 2018 | 865 | 52.1% | -0.46 |
| 2019 | 1,587 | 50.8% | -3.04 |
| 2020 | 1,661 | 53.2% | 1.49 |
| 2021 | 1,001 | 50.8% | -2.92 |
| 2022 | 1,431 | 54.4% | 3.79 |
| 2023 | 1,154 | 54.2% | 3.40 |
| 2024 | 1,064 | 51.8% | -1.14 |
| 2025 | 1,157 | 48.1% | -8.09 |
| 2026 | 1,483 | 50.0% | -4.48 |

## Line movement: does the model predict which way the opener moves?

24,311 games where the line moved (seasons 2014, 2015, 2016, 2017, 2024, 2025, 2026). The line moved toward the model's side in 64.9%; 82.2% when the model disagreed with the opener by 3+.

Betting the model's side at the **opening** number:

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge vs opener 0+ | 23,936 | 52.4% | 0.00 |
| edge vs opener 2+ | 6,057 | 56.6% | 8.05 |
| edge vs opener 3+ | 2,275 | 58.8% | 12.20 |
| edge vs opener 4+ | 798 | 58.8% | 12.20 |
| edge vs opener 6+ | 128 | 76.6% | 46.16 |

