# ESPN wall clock as the actual tip: coverage and reliability

Generated 2026-10-28 17:01 UTC by `python -m audit.tipoff_study` from the cached play-by-play and schedules (completed Division I vs Division I games). Rule: `cbb/tipoff.classify`.

## Coverage by season

| Season | Games | With play-by-play | With a wall clock | Usable tip |
|---|---:|---:|---:|---:|
| 2020-21 | 3905 | 94.6% | 58.9% | 0.9% |
| 2021-22 | 5428 | 97.7% | 97.7% | 7.7% |
| 2022-23 | 5671 | 98.5% | 98.5% | 6.5% |
| 2023-24 | 5726 | 98.6% | 98.6% | 5.9% |
| 2024-25 | 5764 | 98.1% | 98.0% | 3.5% |
| 2025-26 | 5752 | 99.8% | 99.8% | 91.9% |

## Why games are excluded (all seasons)

| Reason | Games | Share |
|---|---:|---:|
| no period-1 play stamped at 20:00 | 20857 | 64.68% |
| no wall clock on period-1 plays | 1394 | 4.32% |
| wall clocks out of order (more than 5 s backwards) | 1281 | 3.97% |
| tip more than 30 min before or 60 min after the scheduled start (a whole-hour offset: a time-zone error in the stamps) | 1163 | 3.61% |
| no play-by-play | 625 | 1.94% |
| tip more than 30 min before or 60 min after the scheduled start | 159 | 0.49% |
| wall clock runs more than 30 s faster than the game clock (entry times, not play times) | 83 | 0.26% |
| game length on the wall clock outside 60-300 min | 38 | 0.12% |

Last season (2025-26), the format the live check will see:

| Reason | Games | Share |
|---|---:|---:|
| wall clocks out of order (more than 5 s backwards) | 387 | 6.73% |
| wall clock runs more than 30 s faster than the game clock (entry times, not play times) | 45 | 0.78% |
| no play-by-play | 12 | 0.21% |
| game length on the wall clock outside 60-300 min | 9 | 0.16% |
| tip more than 30 min before or 60 min after the scheduled start | 6 | 0.10% |
| no period-1 play stamped at 20:00 | 3 | 0.05% |
| tip more than 30 min before or 60 min after the scheduled start (a whole-hour offset: a time-zone error in the stamps) | 2 | 0.03% |

Usable: 6646 of 32246 (20.6%); last three seasons 33.8% of 17242. Excluded games are listed in `audit/tipoff_study_games.csv.gz` (`quality`, `reason`).

## Reliability, usable games

Actual tip minus scheduled start (minutes): p1 +0.2, p5 +1.1, p25 +2.2, p50 +3.0, p75 +5.8, p95 +12.5, p99 +26.5

- Tip before the scheduled start: 0.84%; more than 1 min before: 0.48%; more than 5 min before: 0.15%.
- Tip more than 30 min after the scheduled start: 0.78% (more than 15: 3.64%; more than 60: 0.00%).
- Start-of-game stamp to the jump-ball stamp (where both exist): median 1 s, p95 4 s.
- Wall clock running faster than the game clock over the first plays (wall-clock gap shorter than the game-clock gap): worst case per game median -2 s, p1 -23 s (negative = stamps are not play times).
- Game length on the wall clock: median 123 min, p1 101, p99 170.

## Effect of the proposed thresholds

Near-tip limit (cutoff = scheduled start, assumed correct): share of usable games whose actual tip is more than N minutes after the scheduled start, i.e. would be called "early":

| N (min) | 10 | 15 | 20 | 30 | 45 | 60 |
|---|---:|---:|---:|---:|---:|---:|
| early | 9.40% | 3.64% | 1.63% | 0.78% | 0.15% | 0.00% |

Uncertainty buffer: share of closes failing "last quote at least B seconds before the actual tip" when the last quote arrives uniformly 0-180 s before the scheduled start:

| B (s) | 0 | 30 | 60 | 120 | 300 |
|---|---:|---:|---:|---:|---:|
| fail | 0.47% | 0.66% | 1.02% | 4.24% | 53.54% |
