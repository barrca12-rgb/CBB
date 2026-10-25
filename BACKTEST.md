# Backtest 2013-2026

## Summary (tuned model: ratings + KenPom + Barttorvik + Four Factors + rest + home edge + availability)

| | 2014-2019 | 2020-2026 | 2024-2026 |
|---|---:|---:|---:|
| Winners picked (model / line favorite) | 73.4% / 73.6% | 72.7% / 73.0% | |
| ATS vs closing line, edge 3+ | 52.4% | 52.3% | 52.3% |
| Over/under vs closing line, edge 3+ | 54.8% | 50.9% | 49.0% |
| **ATS vs opening line, edge 3+** | 56.9% (2014-17) | | **57.5%** (1,288 bets) |
| **Over/under vs opening line, edge 3+** | | | **54.2%** (3,925 bets) |

Break-even at -110 is 52.4%.

* **Winners:** the model picks winners as well as the closing-line favorite (73%) and better than KenPom.
* **Closing lines: no edge.** Spreads and totals both land at or below break-even against the close.
* **Opening lines: the edge.** The line moves toward the model 79% of the time when it disagrees with the
  opener by 3+ points, and betting the model's side at the opener won 57.4%, 57.7% and 57.2% in 2024, 2025 and
  2026 (2+ points: 54.9%; 4+: 58.6%). Totals at the opener: 54.2% at 3+, 55.8% at 4+. Same lesson as the NFL
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
| model | 61,463 | 8.78 | 13.23 |
| closing line | 61,463 | 8.71 | 13.13 |
| KenPom | 61,463 | 8.85 | 13.39 |
| ratings only (before 2nd stage) | 61,463 | 8.82 | 13.30 |

## How much of the model's disagreement with the line shows up in the result

Slope of (result - line) on (model - line). 0 = the line already knows everything the model does; 1 = trust the model fully. Same idea as the NFL model's blend weight.

| season | margin | total |
|---|---:|---:|
| 2014 | 0.23 | 0.59 |
| 2015 | 0.10 | 0.68 |
| 2016 | 0.32 | 0.24 |
| 2017 | 0.49 | 0.35 |
| 2018 | 0.40 | 0.55 |
| 2019 | 0.57 | 0.25 |
| 2020 | 0.12 | 0.26 |
| 2021 | 0.36 | 0.20 |
| 2022 | 0.11 | 0.40 |
| 2023 | 0.94 | 0.32 |
| 2024 | 0.30 | 0.19 |
| 2025 | 0.14 | -0.03 |
| 2026 | 0.09 | 0.01 |
| all | 0.54 | 0.26 |

## Spreads: betting the model's side vs the closing line, by size of disagreement

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge 0-1 pts, 2013-2019 | 10,410 | 50.6% | -3.41 |
| edge 0-1 pts, 2020-2026 | 16,132 | 51.0% | -2.65 |
| edge 1-2 pts, 2013-2019 | 7,351 | 51.4% | -1.96 |
| edge 1-2 pts, 2020-2026 | 11,368 | 49.9% | -4.71 |
| edge 2-3 pts, 2013-2019 | 3,540 | 51.4% | -1.80 |
| edge 2-3 pts, 2020-2026 | 5,825 | 50.9% | -2.79 |
| edge 3-4 pts, 2013-2019 | 1,422 | 50.5% | -3.61 |
| edge 3-4 pts, 2020-2026 | 2,386 | 51.3% | -1.99 |
| edge 4-6 pts, 2013-2019 | 628 | 51.9% | -0.90 |
| edge 4-6 pts, 2020-2026 | 1,217 | 52.9% | 1.02 |
| edge 6-+ pts, 2013-2019 | 150 | 72.7% | 38.73 |
| edge 6-+ pts, 2020-2026 | 173 | 58.4% | 11.46 |

### Spreads, edge 3+ points, by month

| | bets | win% | roi% |
|---|---:|---:|---:|
| Nov | 1,828 | 53.0% | 1.20 |
| Dec | 1,342 | 51.3% | -1.98 |
| Jan | 1,269 | 50.1% | -4.32 |
| Feb | 944 | 54.6% | 4.15 |
| Mar | 588 | 53.7% | 2.60 |

### Spreads, edge 3+ points, by season

| | bets | win% | roi% |
|---|---:|---:|---:|
| 2014 | 267 | 53.9% | 2.96 |
| 2015 | 405 | 49.9% | -4.78 |
| 2016 | 382 | 47.1% | -10.04 |
| 2017 | 436 | 53.7% | 2.46 |
| 2018 | 284 | 51.8% | -1.18 |
| 2019 | 426 | 57.7% | 10.24 |
| 2020 | 425 | 51.5% | -1.63 |
| 2021 | 423 | 51.3% | -2.06 |
| 2022 | 528 | 49.4% | -5.63 |
| 2023 | 478 | 56.9% | 8.63 |
| 2024 | 584 | 53.6% | 2.32 |
| 2025 | 637 | 50.9% | -2.90 |
| 2026 | 710 | 52.5% | 0.29 |

## Totals: betting the model's side vs the closing line, by size of disagreement

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge 0-1 pts, 2013-2019 | 6,986 | 50.7% | -3.26 |
| edge 0-1 pts, 2020-2026 | 12,165 | 50.7% | -3.27 |
| edge 1-2 pts, 2013-2019 | 5,865 | 51.4% | -1.96 |
| edge 1-2 pts, 2020-2026 | 10,168 | 49.7% | -5.03 |
| edge 2-3 pts, 2013-2019 | 4,123 | 52.6% | 0.39 |
| edge 2-3 pts, 2020-2026 | 6,782 | 51.1% | -2.46 |
| edge 3-4 pts, 2013-2019 | 2,588 | 53.7% | 2.54 |
| edge 3-4 pts, 2020-2026 | 3,996 | 51.0% | -2.68 |
| edge 4-6 pts, 2013-2019 | 2,299 | 55.9% | 6.79 |
| edge 4-6 pts, 2020-2026 | 3,199 | 51.2% | -2.19 |
| edge 6-+ pts, 2013-2019 | 947 | 54.9% | 4.83 |
| edge 6-+ pts, 2020-2026 | 980 | 49.9% | -4.74 |

### Totals, edge 3+ points, by month

| | bets | win% | roi% |
|---|---:|---:|---:|
| Nov | 3,256 | 51.8% | -1.03 |
| Dec | 2,565 | 53.1% | 1.37 |
| Jan | 3,309 | 51.9% | -1.00 |
| Feb | 2,734 | 54.8% | 4.67 |
| Mar | 2,108 | 50.9% | -2.82 |

### Totals, edge 3+ points, by season

| | bets | win% | roi% |
|---|---:|---:|---:|
| 2014 | 691 | 58.2% | 11.06 |
| 2015 | 842 | 56.9% | 8.61 |
| 2016 | 1,236 | 54.4% | 3.95 |
| 2017 | 1,026 | 56.3% | 7.55 |
| 2018 | 692 | 52.2% | -0.41 |
| 2019 | 1,347 | 52.2% | -0.36 |
| 2020 | 1,039 | 53.7% | 2.53 |
| 2021 | 655 | 50.8% | -2.94 |
| 2022 | 1,067 | 53.7% | 2.52 |
| 2023 | 1,025 | 53.8% | 2.63 |
| 2024 | 1,163 | 51.9% | -0.85 |
| 2025 | 1,460 | 47.2% | -9.91 |
| 2026 | 1,766 | 48.5% | -7.36 |

## Line movement: does the model predict which way the opener moves?

24,311 games where the line moved (seasons 2014, 2015, 2016, 2017, 2024, 2025, 2026). The line moved toward the model's side in 62.0%; 78.8% when the model disagreed with the opener by 3+.

Betting the model's side at the **opening** number:

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge vs opener 0+ | 23,936 | 51.7% | -1.31 |
| edge vs opener 2+ | 5,691 | 55.0% | 5.07 |
| edge vs opener 3+ | 2,082 | 57.9% | 10.58 |
| edge vs opener 4+ | 676 | 60.1% | 14.66 |
| edge vs opener 6+ | 127 | 70.9% | 35.29 |

