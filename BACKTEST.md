# Backtest 2013-2026

## Summary (tuned model: ratings + KenPom + Barttorvik + Four Factors + rest + home edge + availability)

| | 2014-2019 | 2020-2026 | 2024-2026 |
|---|---:|---:|---:|
| Winners picked (model / line favorite) | 73.4% / 73.6% | 72.7% / 73.0% | |
| ATS vs closing line, edge 3+ | 52.4% | 52.3% | 52.3% |
| Over/under vs closing line, edge 3+ | 54.8% | 50.9% | 49.0% |
| **ATS vs opening line, edge 3+** | 56.9% (2014-17) | | **57.5%** (1,288 bets) |
| **Over/under vs opening line, edge 4+** | | | **56.7%** (1,433 bets) |

Break-even at -110 is 52.4%.

* **Winners:** the model picks winners as well as the closing-line favorite (73%) and better than KenPom.
* **Closing lines: no edge.** Spreads and totals both land at or below break-even against the close.
* **Opening lines: the edge.** The line moves toward the model 79% of the time when it disagrees with the
  opener by 3+ points, and betting the model's side at the opener won 57.4%, 57.7% and 57.2% in 2024, 2025 and
  2026 (2+ points: 54.9%; 4+: 58.6%). Totals at the opener: 56.7% at 4+. Same lesson as the NFL
  model: the value is in betting the model's number early, before the market moves to it.
* **Caveats:** openers carry low limits and move fast; openers exist only for 2014-2017 and 2024-2026; 6+ point
  edges are small samples. Data cleaning (projection sites, flipped openers, bad months) removed several fake
  70-85% edges, so treat anything above ~60% with suspicion.

Walk-forward: each game is predicted with ratings fit only on earlier games that season, starting from KenPom's preseason ratings. Closing line = median of the books in ESPN's odds feed. KenPom = FanMatch predicted score. Records are against the closing line at -110 (break-even 52.4%).

Lines dropped as bad data (closing line and KenPom favor different teams by 3+ in more than 3% of games): Nov 2013 (8%), Nov 2017 (6%).

## Winners picked (straight up, pick'em lines excluded)

| | games | model | line favorite | KenPom |
|---|---:|---:|---:|---:|
| through 2019 | 23,809 | 73.4% | 73.6% | 73.2% |
| 2020 on | 37,366 | 72.7% | 73.0% | 72.3% |
| all | 61,175 | 73.0% | 73.2% | 72.6% |

## Accuracy (games with a line and a KenPom prediction)

| | games | margin MAE | total MAE |
|---|---:|---:|---:|
| model | 61,463 | 8.78 | 13.34 |
| closing line | 61,463 | 8.71 | 13.13 |
| KenPom | 61,463 | 8.85 | 13.39 |
| ratings only (before 2nd stage) | 61,463 | 8.82 | 13.30 |

## How much of the model's disagreement with the line shows up in the result

Slope of (result - line) on (model - line). 0 = the line already knows everything the model does; 1 = trust the model fully. Same idea as the NFL model's blend weight.

| season | margin | total |
|---|---:|---:|
| 2014 | 0.23 | 0.08 |
| 2015 | 0.10 | 0.68 |
| 2016 | 0.33 | 0.26 |
| 2017 | 0.49 | 0.42 |
| 2018 | 0.40 | 0.54 |
| 2019 | 0.57 | 0.22 |
| 2020 | 0.12 | 0.28 |
| 2021 | 0.36 | 0.18 |
| 2022 | 0.11 | 0.39 |
| 2023 | 0.94 | 0.33 |
| 2024 | 0.30 | 0.17 |
| 2025 | 0.14 | -0.08 |
| 2026 | 0.09 | -0.04 |
| all | 0.54 | 0.18 |

## Spreads: betting the model's side vs the closing line, by size of disagreement

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge 0-1 pts, 2013-2019 | 10,405 | 50.7% | -3.22 |
| edge 0-1 pts, 2020-2026 | 16,128 | 50.9% | -2.73 |
| edge 1-2 pts, 2013-2019 | 7,354 | 51.3% | -2.03 |
| edge 1-2 pts, 2020-2026 | 11,361 | 49.9% | -4.77 |
| edge 2-3 pts, 2013-2019 | 3,537 | 51.4% | -1.93 |
| edge 2-3 pts, 2020-2026 | 5,831 | 51.0% | -2.70 |
| edge 3-4 pts, 2013-2019 | 1,426 | 50.1% | -4.28 |
| edge 3-4 pts, 2020-2026 | 2,388 | 51.1% | -2.47 |
| edge 4-6 pts, 2013-2019 | 628 | 52.2% | -0.29 |
| edge 4-6 pts, 2020-2026 | 1,219 | 53.3% | 1.80 |
| edge 6-+ pts, 2013-2019 | 151 | 72.8% | 39.07 |
| edge 6-+ pts, 2020-2026 | 174 | 58.6% | 11.91 |

### Spreads, edge 3+ points, by month

| | bets | win% | roi% |
|---|---:|---:|---:|
| Nov | 1,836 | 53.1% | 1.28 |
| Dec | 1,342 | 51.2% | -2.27 |
| Jan | 1,268 | 50.1% | -4.39 |
| Feb | 945 | 54.6% | 4.24 |
| Mar | 590 | 53.4% | 1.93 |

### Spreads, edge 3+ points, by season

| | bets | win% | roi% |
|---|---:|---:|---:|
| 2014 | 266 | 54.1% | 3.35 |
| 2015 | 401 | 49.9% | -4.78 |
| 2016 | 379 | 47.0% | -10.34 |
| 2017 | 439 | 53.8% | 2.63 |
| 2018 | 286 | 51.0% | -2.54 |
| 2019 | 434 | 57.4% | 9.53 |
| 2020 | 428 | 51.9% | -0.98 |
| 2021 | 423 | 51.3% | -2.06 |
| 2022 | 531 | 49.2% | -6.16 |
| 2023 | 479 | 56.8% | 8.41 |
| 2024 | 582 | 53.6% | 2.34 |
| 2025 | 636 | 50.9% | -2.74 |
| 2026 | 711 | 52.5% | 0.15 |

## Totals: betting the model's side vs the closing line, by size of disagreement

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge 0-1 pts, 2013-2019 | 5,898 | 51.0% | -2.70 |
| edge 0-1 pts, 2020-2026 | 11,224 | 50.8% | -3.10 |
| edge 1-2 pts, 2013-2019 | 4,943 | 51.4% | -1.94 |
| edge 1-2 pts, 2020-2026 | 9,754 | 49.9% | -4.64 |
| edge 2-3 pts, 2013-2019 | 3,674 | 52.3% | -0.23 |
| edge 2-3 pts, 2020-2026 | 7,107 | 50.4% | -3.86 |
| edge 3-4 pts, 2013-2019 | 2,333 | 53.9% | 2.94 |
| edge 3-4 pts, 2020-2026 | 4,390 | 50.9% | -2.85 |
| edge 4-6 pts, 2013-2019 | 2,214 | 52.3% | -0.06 |
| edge 4-6 pts, 2020-2026 | 3,680 | 51.3% | -2.11 |
| edge 6-+ pts, 2013-2019 | 3,746 | 53.7% | 2.59 |
| edge 6-+ pts, 2020-2026 | 1,135 | 52.3% | -0.09 |

### Totals, edge 3+ points, by month

| | bets | win% | roi% |
|---|---:|---:|---:|
| Nov | 3,286 | 51.8% | -1.18 |
| Dec | 3,285 | 52.9% | 1.06 |
| Jan | 4,377 | 52.0% | -0.64 |
| Feb | 3,689 | 53.3% | 1.74 |
| Mar | 2,808 | 50.9% | -2.78 |

### Totals, edge 3+ points, by season

| | bets | win% | roi% |
|---|---:|---:|---:|
| 2014 | 3,136 | 52.9% | 1.06 |
| 2015 | 798 | 56.8% | 8.37 |
| 2016 | 1,017 | 56.1% | 7.19 |
| 2017 | 1,045 | 53.9% | 2.85 |
| 2018 | 795 | 52.5% | 0.14 |
| 2019 | 1,502 | 51.0% | -2.64 |
| 2020 | 1,837 | 53.0% | 1.22 |
| 2021 | 1,040 | 50.1% | -4.36 |
| 2022 | 1,398 | 53.6% | 2.42 |
| 2023 | 1,100 | 53.0% | 1.18 |
| 2024 | 1,109 | 51.9% | -0.84 |
| 2025 | 1,187 | 47.6% | -9.13 |
| 2026 | 1,534 | 48.6% | -7.16 |

## Line movement: does the model predict which way the opener moves?

24,311 games where the line moved (seasons 2014, 2015, 2016, 2017, 2024, 2025, 2026). The line moved toward the model's side in 62.0%; 78.8% when the model disagreed with the opener by 3+.

Betting the model's side at the **opening** number:

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge vs opener 0+ | 23,936 | 51.8% | -1.19 |
| edge vs opener 2+ | 5,698 | 55.0% | 5.00 |
| edge vs opener 3+ | 2,086 | 57.6% | 10.01 |
| edge vs opener 4+ | 673 | 60.3% | 15.17 |
| edge vs opener 6+ | 126 | 70.6% | 34.85 |

