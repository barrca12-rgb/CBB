# Backtest 2013-2026

## Summary

Model: ratings with 3-point luck regressed, plus KenPom, Barttorvik, Four Factors, rest, home edge, missing
players, market ratings from earlier closing lines, altitude, and referee crews.

| | Result | Bets |
|---|---:|---:|
| **ATS vs opening line, edge 3+, 2024-2026** | **58.6%** | 1,220 |
| **Over/under vs opening line, edge 4+, 2024-2026** (crew unknown at the open: 57.4% without referees) | 60.4% | 2,133 |
| ATS vs closing line, edge 3+, 2020-2026 | 53.0% | 3,346 |
| **Over/under vs closing line, edge 4+, 2020-2026** | **54.4%** | 5,965 |
| Average miss on margin, 2020-2026 (model / closing line) | 8.88 / 8.84 | |
| Average miss on total, 2020-2026 (model / closing line) | 13.08 / 13.00 | |

Break-even at -110 is 52.4%.

* **Opening lines are the edge** on spreads and totals. Referee crews usually aren't posted when openers are, so
  the realistic opener number for totals is ~57.4%.
* **Closing lines:** referee crews took totals from 52.4% to 54.4% (positive in 8 of 11 seasons, but weaker
  lately: 2024 55.3%, 2025 47.6%, 2026 53.0%). Spreads at the close are just above break-even.
* **What moved it:** 3-point luck regression (spreads at the opener 57.5% -> 58.2%), market ratings and altitude
  (-> 58.6%), referees (totals at the close 52.4% -> 54.4%). Tested and left out: free-throw luck, blowout
  weighting, time zones, height/experience/continuity, production-weighted absences.
* **Caveats:** openers carry low limits; openers exist only for 2014-2017 and 2024-2026; data cleaning removed
  several fake 70-85% edges, so treat anything above ~60% with suspicion.

Walk-forward: each game is predicted with ratings fit only on earlier games that season, starting from KenPom's preseason ratings. Closing line = median of the books in ESPN's odds feed. KenPom = FanMatch predicted score. Records are against the closing line at -110 (break-even 52.4%).

Lines dropped as bad data (closing line and KenPom favor different teams by 3+ in more than 3% of games): Nov 2013 (8%), Nov 2017 (6%).

## Winners picked (straight up, pick'em lines excluded)

| | games | model | line favorite | KenPom |
|---|---:|---:|---:|---:|
| through 2019 | 23,809 | 73.4% | 73.6% | 73.2% |
| 2020 on | 37,366 | 72.8% | 73.0% | 72.3% |
| all | 61,175 | 73.1% | 73.2% | 72.6% |

## Accuracy (games with a line and a KenPom prediction)

| | games | margin MAE | total MAE |
|---|---:|---:|---:|
| model | 61,463 | 8.75 | 13.31 |
| closing line | 61,463 | 8.71 | 13.13 |
| KenPom | 61,463 | 8.85 | 13.39 |
| ratings only (before 2nd stage) | 61,463 | 8.78 | 13.26 |

## How much of the model's disagreement with the line shows up in the result

Slope of (result - line) on (model - line). 0 = the line already knows everything the model does; 1 = trust the model fully. Same idea as the NFL model's blend weight.

| season | margin | total |
|---|---:|---:|
| 2014 | 0.30 | 0.09 |
| 2015 | 0.15 | 0.67 |
| 2016 | 0.38 | 0.30 |
| 2017 | 0.53 | 0.45 |
| 2018 | 0.51 | 0.69 |
| 2019 | 0.64 | 0.32 |
| 2020 | 0.19 | 0.44 |
| 2021 | 0.39 | 0.28 |
| 2022 | 0.12 | 0.51 |
| 2023 | 0.96 | 0.51 |
| 2024 | 0.44 | 0.41 |
| 2025 | 0.24 | 0.12 |
| 2026 | 0.17 | 0.15 |
| all | 0.60 | 0.26 |

## Spreads: betting the model's side vs the closing line, by size of disagreement

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge 0-1 pts, 2013-2019 | 10,789 | 51.8% | -1.12 |
| edge 0-1 pts, 2020-2026 | 16,914 | 50.5% | -3.56 |
| edge 1-2 pts, 2013-2019 | 7,297 | 52.1% | -0.61 |
| edge 1-2 pts, 2020-2026 | 11,449 | 50.7% | -3.19 |
| edge 2-3 pts, 2013-2019 | 3,404 | 51.7% | -1.35 |
| edge 2-3 pts, 2020-2026 | 5,401 | 51.6% | -1.45 |
| edge 3-4 pts, 2013-2019 | 1,276 | 50.0% | -4.55 |
| edge 3-4 pts, 2020-2026 | 2,136 | 51.7% | -1.33 |
| edge 4-6 pts, 2013-2019 | 579 | 54.4% | 3.86 |
| edge 4-6 pts, 2020-2026 | 1,054 | 54.8% | 4.69 |
| edge 6-+ pts, 2013-2019 | 156 | 71.2% | 35.84 |
| edge 6-+ pts, 2020-2026 | 147 | 55.8% | 6.49 |

### Spreads, edge 3+ points, by month

| | bets | win% | roi% |
|---|---:|---:|---:|
| Nov | 1,825 | 54.0% | 3.04 |
| Dec | 1,204 | 52.0% | -0.74 |
| Jan | 1,042 | 52.0% | -0.70 |
| Feb | 760 | 52.5% | 0.23 |
| Mar | 515 | 54.4% | 3.80 |

### Spreads, edge 3+ points, by season

| | bets | win% | roi% |
|---|---:|---:|---:|
| 2014 | 218 | 54.1% | 3.34 |
| 2015 | 388 | 48.5% | -7.50 |
| 2016 | 339 | 49.0% | -6.52 |
| 2017 | 399 | 55.9% | 6.70 |
| 2018 | 263 | 48.7% | -7.09 |
| 2019 | 404 | 59.7% | 13.88 |
| 2020 | 426 | 53.1% | 1.28 |
| 2021 | 403 | 50.9% | -2.89 |
| 2022 | 509 | 50.7% | -3.23 |
| 2023 | 427 | 56.9% | 8.64 |
| 2024 | 516 | 53.9% | 2.85 |
| 2025 | 508 | 55.3% | 5.60 |
| 2026 | 557 | 50.6% | -3.35 |

## Totals: betting the model's side vs the closing line, by size of disagreement

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge 0-1 pts, 2013-2019 | 5,075 | 52.4% | 0.06 |
| edge 0-1 pts, 2020-2026 | 10,377 | 50.6% | -3.43 |
| edge 1-2 pts, 2013-2019 | 4,671 | 51.8% | -1.05 |
| edge 1-2 pts, 2020-2026 | 9,159 | 50.0% | -4.62 |
| edge 2-3 pts, 2013-2019 | 3,605 | 51.3% | -2.03 |
| edge 2-3 pts, 2020-2026 | 7,072 | 52.0% | -0.74 |
| edge 3-4 pts, 2013-2019 | 2,558 | 53.6% | 2.40 |
| edge 3-4 pts, 2020-2026 | 4,717 | 52.4% | 0.13 |
| edge 4-6 pts, 2013-2019 | 2,740 | 55.1% | 5.28 |
| edge 4-6 pts, 2020-2026 | 4,404 | 53.9% | 2.82 |
| edge 6-+ pts, 2013-2019 | 4,159 | 54.2% | 3.56 |
| edge 6-+ pts, 2020-2026 | 1,561 | 55.7% | 6.40 |

### Totals, edge 3+ points, by month

| | bets | win% | roi% |
|---|---:|---:|---:|
| Nov | 3,634 | 53.5% | 2.13 |
| Dec | 3,661 | 54.6% | 4.19 |
| Jan | 5,200 | 54.0% | 3.16 |
| Feb | 4,551 | 54.6% | 4.24 |
| Mar | 3,048 | 52.2% | -0.35 |

### Totals, edge 3+ points, by season

| | bets | win% | roi% |
|---|---:|---:|---:|
| 2014 | 3,125 | 53.0% | 1.17 |
| 2015 | 1,089 | 60.0% | 14.48 |
| 2016 | 1,387 | 53.6% | 2.27 |
| 2017 | 1,142 | 55.0% | 4.98 |
| 2018 | 962 | 55.0% | 4.98 |
| 2019 | 1,752 | 53.1% | 1.34 |
| 2020 | 1,822 | 55.4% | 5.72 |
| 2021 | 1,190 | 52.0% | -0.70 |
| 2022 | 1,679 | 54.7% | 4.38 |
| 2023 | 1,478 | 55.6% | 6.18 |
| 2024 | 1,458 | 53.3% | 1.74 |
| 2025 | 1,436 | 49.7% | -5.08 |
| 2026 | 1,619 | 52.9% | 1.06 |

## Line movement: does the model predict which way the opener moves?

24,311 games where the line moved (seasons 2014, 2015, 2016, 2017, 2024, 2025, 2026). The line moved toward the model's side in 65.7%; 82.7% when the model disagreed with the opener by 3+.

Betting the model's side at the **opening** number:

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge vs opener 0+ | 23,936 | 52.5% | 0.21 |
| edge vs opener 2+ | 6,082 | 56.7% | 8.17 |
| edge vs opener 3+ | 2,246 | 58.7% | 12.03 |
| edge vs opener 4+ | 778 | 59.4% | 13.37 |
| edge vs opener 6+ | 127 | 76.4% | 45.81 |

