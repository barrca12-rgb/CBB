# Backtest 2013-2026

## Summary (first, untuned version)

* **No edge yet.** Against closing lines the model's side wins 49-52% at every size of disagreement, in both
  halves of the data (break-even 52.4%). Totals are the same.
* **Accuracy:** the model is as good as KenPom (margin miss 8.83 vs 8.85 points) but behind the closing line
  (8.71). Closing lines in college basketball are hard to beat with ratings alone.
* **Opening lines** (the NFL model's lesson): the line moves toward the model's side 60-75% of the time, so the model
  does see something the opener misses. Betting it at the opener won 54.5% at 3+ points in 2014-2017 but only
  51.4% in 2024-2026 (break-even 52.4%): the recent market corrects faster and the edge isn't there yet.
* **Data cleaning that mattered:** projection sites in ESPN's feed (numberfire, teamrankings) and openers stored
  from the wrong team's side both produced fake 70-85% win rates until removed.

Next: tune the model (decay, prior strength, blowout compression, per-team home edge, KenPom/Barttorvik blend)
and re-run this report. The threshold for betting anything is a result that holds in both halves of the data.

Walk-forward: each game is predicted with ratings fit only on earlier games that season, starting from KenPom's preseason ratings. Closing line = median of the books in ESPN's odds feed. KenPom = FanMatch predicted score. Records are against the closing line at -110 (break-even 52.4%).

Lines dropped as bad data (closing line and KenPom favor different teams by 3+ in more than 3% of games): Nov 2013 (8%), Nov 2017 (6%).

## Accuracy (games with a line and a KenPom prediction)

| | games | margin MAE | total MAE |
|---|---:|---:|---:|
| model | 61,391 | 8.83 | 13.30 |
| closing line | 61,391 | 8.71 | 13.13 |
| KenPom | 61,391 | 8.85 | 13.39 |

## How much of the model's disagreement with the line shows up in the result

Slope of (result - line) on (model - line). 0 = the line already knows everything the model does; 1 = trust the model fully. Same idea as the NFL model's blend weight.

| season | margin | total |
|---|---:|---:|
| 2014 | 0.08 | 0.36 |
| 2015 | 0.02 | 0.40 |
| 2016 | 0.11 | 0.21 |
| 2017 | 0.43 | 0.30 |
| 2018 | 0.28 | 0.24 |
| 2019 | 0.42 | 0.09 |
| 2020 | -0.00 | 0.09 |
| 2021 | 0.12 | -0.16 |
| 2022 | 0.08 | 0.09 |
| 2023 | 0.91 | -0.06 |
| 2024 | 0.14 | -0.03 |
| 2025 | -0.00 | -0.09 |
| 2026 | -0.03 | -0.08 |
| all | 0.41 | 0.06 |

## Spreads: betting the model's side vs the closing line, by size of disagreement

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge 0-1 pts, 2013-2019 | 10,196 | 49.5% | -5.43 |
| edge 0-1 pts, 2020-2026 | 14,802 | 49.9% | -4.69 |
| edge 1-2 pts, 2013-2019 | 7,101 | 49.4% | -5.74 |
| edge 1-2 pts, 2020-2026 | 11,105 | 49.7% | -5.09 |
| edge 2-3 pts, 2013-2019 | 3,667 | 50.0% | -4.47 |
| edge 2-3 pts, 2020-2026 | 6,213 | 49.7% | -5.05 |
| edge 3-4 pts, 2013-2019 | 1,564 | 51.6% | -1.49 |
| edge 3-4 pts, 2020-2026 | 2,890 | 50.0% | -4.48 |
| edge 4-6 pts, 2013-2019 | 771 | 49.0% | -6.40 |
| edge 4-6 pts, 2020-2026 | 1,774 | 50.1% | -4.33 |
| edge 6-+ pts, 2013-2019 | 202 | 63.4% | 20.97 |
| edge 6-+ pts, 2020-2026 | 317 | 51.1% | -2.44 |

### Spreads, edge 3+ points, by month

| | bets | win% | roi% |
|---|---:|---:|---:|
| Nov | 2,333 | 51.1% | -2.38 |
| Dec | 1,830 | 50.9% | -2.88 |
| Jan | 1,726 | 49.1% | -6.20 |
| Feb | 1,085 | 51.0% | -2.70 |
| Mar | 538 | 53.3% | 1.84 |

### Spreads, edge 3+ points, by season

| | bets | win% | roi% |
|---|---:|---:|---:|
| 2014 | 349 | 53.3% | 1.75 |
| 2015 | 484 | 48.3% | -7.70 |
| 2016 | 498 | 50.0% | -4.55 |
| 2017 | 371 | 55.3% | 5.49 |
| 2018 | 311 | 50.5% | -3.62 |
| 2019 | 524 | 53.8% | 2.74 |
| 2020 | 596 | 52.3% | -0.06 |
| 2021 | 611 | 50.2% | -4.08 |
| 2022 | 610 | 51.0% | -2.67 |
| 2023 | 620 | 51.3% | -2.08 |
| 2024 | 807 | 51.5% | -1.59 |
| 2025 | 819 | 49.0% | -6.53 |
| 2026 | 927 | 47.6% | -9.18 |

## Totals: betting the model's side vs the closing line, by size of disagreement

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge 0-1 pts, 2013-2019 | 7,513 | 50.2% | -4.20 |
| edge 0-1 pts, 2020-2026 | 10,938 | 49.4% | -5.78 |
| edge 1-2 pts, 2013-2019 | 6,040 | 50.6% | -3.47 |
| edge 1-2 pts, 2020-2026 | 9,445 | 50.2% | -4.19 |
| edge 2-3 pts, 2013-2019 | 4,132 | 50.8% | -3.07 |
| edge 2-3 pts, 2020-2026 | 6,804 | 50.2% | -4.24 |
| edge 3-4 pts, 2013-2019 | 2,350 | 52.1% | -0.56 |
| edge 3-4 pts, 2020-2026 | 4,507 | 51.0% | -2.58 |
| edge 4-6 pts, 2013-2019 | 2,004 | 52.3% | -0.07 |
| edge 4-6 pts, 2020-2026 | 4,157 | 47.8% | -8.75 |
| edge 6-+ pts, 2013-2019 | 769 | 55.4% | 5.76 |
| edge 6-+ pts, 2020-2026 | 1,439 | 49.9% | -4.74 |

### Totals, edge 3+ points, by month

| | bets | win% | roi% |
|---|---:|---:|---:|
| Nov | 3,616 | 51.4% | -1.80 |
| Dec | 2,948 | 49.9% | -4.74 |
| Jan | 3,556 | 50.4% | -3.69 |
| Feb | 2,942 | 50.6% | -3.31 |
| Mar | 2,130 | 50.2% | -4.10 |

### Totals, edge 3+ points, by season

| | bets | win% | roi% |
|---|---:|---:|---:|
| 2014 | 785 | 53.2% | 1.66 |
| 2015 | 708 | 54.7% | 4.35 |
| 2016 | 763 | 54.7% | 4.34 |
| 2017 | 830 | 53.1% | 1.43 |
| 2018 | 728 | 50.5% | -3.50 |
| 2019 | 1,309 | 51.0% | -2.58 |
| 2020 | 1,176 | 52.8% | 0.81 |
| 2021 | 1,046 | 48.2% | -8.01 |
| 2022 | 1,410 | 51.1% | -2.51 |
| 2023 | 1,388 | 48.5% | -7.43 |
| 2024 | 1,464 | 50.8% | -2.98 |
| 2025 | 1,670 | 47.4% | -9.46 |
| 2026 | 1,949 | 48.8% | -6.85 |

## Line movement: does the model predict which way the opener moves?

24,311 games where the line moved (seasons 2014, 2015, 2016, 2017, 2024, 2025, 2026). The line moved toward the model's side in 58.6%; 68.3% when the model disagreed with the opener by 3+.

Betting the model's side at the **opening** number:

| | bets | win% | roi% |
|---|---:|---:|---:|
| edge vs opener 0+ | 23,936 | 50.8% | -2.93 |
| edge vs opener 2+ | 5,852 | 52.1% | -0.60 |
| edge vs opener 3+ | 2,339 | 52.8% | 0.80 |
| edge vs opener 4+ | 921 | 52.3% | -0.09 |
| edge vs opener 6+ | 155 | 68.4% | 30.56 |

