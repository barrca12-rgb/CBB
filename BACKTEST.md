# Backtest 2013-2026

## Summary

Model: ratings with 3-point luck regressed, plus KenPom, Barttorvik, Four Factors, rest, home edge, missing
players, market ratings from earlier closing lines, altitude, and referee crews.

| | Result | Bets |
|---|---:|---:|
| **ATS vs opening line, edge 3+, 2024-2026** | **58.7%** | 1,228 |
| **Over/under vs opening line, edge 4+, 2024-2026** (crew unknown at the open: 57.4% without referees) | 60.1% | 2,142 |
| ATS vs closing line, edge 3+, 2020-2026 | 53.1% | 3,338 |
| **Over/under vs closing line, edge 4+, 2020-2026** | **54.3%** | 5,952 |
| Average miss on margin, 2020-2026 (model / closing line) | 8.88 / 8.84 | |
| Average miss on total, 2020-2026 (model / closing line) | 13.08 / 13.00 | |

Break-even at -110 is 52.4%. Closing lines exclude projection services listed as books (accuscore and others, Oct
2026 cleanup). Neutral-site spreads bet from 2.5 points live (see run_day.py).

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

Lines dropped as bad data (closing line and KenPom favor different teams by 3+ in more than 3% of games): Nov 2013 (8%), Nov 2017 (7%).

## Winners picked (straight up, pick'em lines excluded)

| | games | model | line favorite | KenPom |
|---|---:|---:|---:|---:|
| through 2019 | 23,445 | 73.5% | 73.6% | 73.2% |
| 2020 on | 37,351 | 72.9% | 73.0% | 72.3% |
| all | 60,796 | 73.1% | 73.2% | 72.7% |

## Accuracy (games with a line and a KenPom prediction)

| | games | margin MAE | total MAE |
|---|---:|---:|---:|
| model | 61,119 | 8.75 | 13.31 |
| closing line | 61,119 | 8.71 | 13.13 |
| KenPom | 61,119 | 8.85 | 13.38 |
| ratings only (before 2nd stage) | 61,119 | 8.78 | 13.25 |

## How much of the model's disagreement with the line shows up in the result

Slope of (result - line) on (model - line). 0 = the line already knows everything the model does; 1 = trust the model fully. Same idea as the NFL model's blend weight.

| season | margin | total |
|---|---:|---:|
| 2014 | 0.29 | 0.09 |
| 2015 | 0.15 | 0.68 |
| 2016 | 0.38 | 0.30 |
| 2017 | 0.53 | 0.45 |
| 2018 | 0.50 | 0.63 |
| 2019 | 0.64 | 0.32 |
| 2020 | 0.19 | 0.45 |
| 2021 | 0.41 | 0.28 |
| 2022 | 0.11 | 0.51 |
| 2023 | 0.96 | 0.51 |
| 2024 | 0.44 | 0.40 |
| 2025 | 0.24 | 0.12 |
| 2026 | 0.17 | 0.15 |
| all | 0.60 | 0.25 |

## Spreads: betting the model's side vs the closing line, by size of disagreement

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge 0-1 pts, 2013-2019 | 10,698 | 51.6% | -1.42 |
| edge 0-1 pts, 2020-2026 | 16,902 | 50.4% | -3.72 |
| edge 1-2 pts, 2013-2019 | 7,206 | 51.9% | -0.86 |
| edge 1-2 pts, 2020-2026 | 11,505 | 50.9% | -2.76 |
| edge 2-3 pts, 2013-2019 | 3,327 | 51.4% | -1.88 |
| edge 2-3 pts, 2020-2026 | 5,385 | 51.6% | -1.51 |
| edge 3-4 pts, 2013-2019 | 1,246 | 50.9% | -2.86 |
| edge 3-4 pts, 2020-2026 | 2,128 | 51.8% | -1.05 |
| edge 4-6 pts, 2013-2019 | 568 | 53.2% | 1.50 |
| edge 4-6 pts, 2020-2026 | 1,052 | 54.8% | 4.71 |
| edge 6-+ pts, 2013-2019 | 158 | 71.5% | 36.54 |
| edge 6-+ pts, 2020-2026 | 149 | 56.4% | 7.63 |

### Spreads, edge 3+ points, by month

| | bets | win% | roi% |
|---|---:|---:|---:|
| Nov | 1,823 | 54.0% | 3.15 |
| Dec | 1,185 | 52.3% | -0.12 |
| Jan | 1,038 | 52.2% | -0.32 |
| Feb | 742 | 53.1% | 1.37 |
| Mar | 511 | 54.0% | 3.11 |

### Spreads, edge 3+ points, by season

| | bets | win% | roi% |
|---|---:|---:|---:|
| 2014 | 221 | 54.8% | 4.52 |
| 2015 | 385 | 48.3% | -7.77 |
| 2016 | 340 | 48.8% | -6.79 |
| 2017 | 398 | 55.8% | 6.49 |
| 2018 | 224 | 49.1% | -6.25 |
| 2019 | 404 | 60.4% | 15.30 |
| 2020 | 427 | 53.6% | 2.38 |
| 2021 | 404 | 50.7% | -3.13 |
| 2022 | 505 | 51.1% | -2.47 |
| 2023 | 422 | 57.6% | 9.93 |
| 2024 | 512 | 53.3% | 1.79 |
| 2025 | 510 | 55.3% | 5.56 |
| 2026 | 558 | 50.7% | -3.18 |

## Totals: betting the model's side vs the closing line, by size of disagreement

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge 0-1 pts, 2013-2019 | 5,006 | 52.4% | -0.01 |
| edge 0-1 pts, 2020-2026 | 10,401 | 50.3% | -3.97 |
| edge 1-2 pts, 2013-2019 | 4,556 | 52.3% | -0.10 |
| edge 1-2 pts, 2020-2026 | 9,117 | 50.3% | -4.03 |
| edge 2-3 pts, 2013-2019 | 3,563 | 51.2% | -2.32 |
| edge 2-3 pts, 2020-2026 | 7,085 | 52.0% | -0.76 |
| edge 3-4 pts, 2013-2019 | 2,529 | 53.5% | 2.14 |
| edge 3-4 pts, 2020-2026 | 4,738 | 52.5% | 0.25 |
| edge 4-6 pts, 2013-2019 | 2,701 | 55.1% | 5.24 |
| edge 4-6 pts, 2020-2026 | 4,394 | 53.9% | 2.88 |
| edge 6-+ pts, 2013-2019 | 4,143 | 54.2% | 3.45 |
| edge 6-+ pts, 2020-2026 | 1,558 | 55.5% | 5.87 |

### Totals, edge 3+ points, by month

| | bets | win% | roi% |
|---|---:|---:|---:|
| Nov | 3,619 | 53.4% | 1.92 |
| Dec | 3,621 | 54.5% | 4.13 |
| Jan | 5,187 | 54.0% | 3.17 |
| Feb | 4,537 | 54.6% | 4.14 |
| Mar | 3,054 | 52.2% | -0.29 |

### Totals, edge 3+ points, by season

| | bets | win% | roi% |
|---|---:|---:|---:|
| 2014 | 3,130 | 53.0% | 1.19 |
| 2015 | 1,092 | 60.2% | 14.86 |
| 2016 | 1,387 | 53.6% | 2.41 |
| 2017 | 1,142 | 55.0% | 4.98 |
| 2018 | 861 | 54.1% | 3.33 |
| 2019 | 1,761 | 53.0% | 1.15 |
| 2020 | 1,840 | 55.3% | 5.62 |
| 2021 | 1,183 | 52.4% | 0.05 |
| 2022 | 1,687 | 54.6% | 4.22 |
| 2023 | 1,469 | 55.5% | 6.05 |
| 2024 | 1,454 | 53.2% | 1.63 |
| 2025 | 1,438 | 49.7% | -5.08 |
| 2026 | 1,619 | 52.9% | 0.94 |

## Line movement: does the model predict which way the opener moves?

24,602 games where the line moved (seasons 2014, 2015, 2016, 2017, 2024, 2025, 2026). The line moved toward the model's side in 65.6%; 83.0% when the model disagreed with the opener by 3+.

Betting the model's side at the **opening** number:

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge vs opener 0+ | 24,225 | 52.5% | 0.19 |
| edge vs opener 2+ | 6,144 | 56.6% | 8.13 |
| edge vs opener 3+ | 2,270 | 58.5% | 11.77 |
| edge vs opener 4+ | 782 | 59.2% | 13.03 |
| edge vs opener 6+ | 125 | 76.0% | 45.09 |

