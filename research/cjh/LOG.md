# CJH reads log

## Nov 20, 2026: Read 2, opening-week injury cross-check (PLAN.md, run as pre-registered)

`python -m research.cjh.injury_check`. Snapshot 2026-10-29T1835Z, the latest before the first 2026-27 tip (Nov 1,
14:34 UTC); sha256 matched snapshots.csv. The Nov 2 snapshot came after the first tip and is not used. Player values
come from the private snapshot and are not copied here.

| Player | Team | Valued from | Material | In a box score Nov 3-9 | On ESPN's report at T-60 |
|---|---|---|---|---|---|
| Donnie Freeman | St. John's | 2025-26 line (Syracuse) | yes | no | no |
| Brandon McCoy | Michigan | projection | yes | no | no |
| Asa Thomas | Illinois Chicago | 2025-26 line (Furman) | yes | no | no |
| Sean Register Jr. | Liberty | unvalued | no | no | no |
| Tye Dorset | Merrimack | projection | yes | no | no |
| L.J. Cason | Miami FL | 2025-26 line (Michigan) | yes | no | no |
| Ty Rodgers | Boise St. | unvalued | no | no | no |
| Nick Anderson | San Diego St. | 2025-26 line (Rice) | yes | no | no |
| Jordan McCullum | East Tennessee St. | projection | yes | no | no |
| Zac Foster | Clemson | projection | yes | no | no |

- **List accuracy:** none of the 10 appeared in a 2026-27 box score Nov 3-9. The list was right.
- **ESPN:** no player was on ESPN's report, because ESPN's injuries feed returned an empty list on every pull this season
  (injuries/log.csv was never written; research/injury_reports/PLUMBING.md).
- **Market vs our model, first two games of the 8 teams with a material player out (11 team-games with a close and a
  verified tip):** market margin minus our projection -0.41 points on average (all other 449 opening-week team-games
  +0.01). Result minus close -10.73 (others +0.26): descriptive, 11 games.
- **Our logged plays on those games:** 12 (8 main, 3 band B, 1 total listed twice by game), 5-7 overall.
- **Decision rule:** material players mostly absent from ESPN's report: yes. Close at least 1 point further against
  those teams than our projection: no (-0.41). **Result: not needed.** The market did not price these absences
  differently from our model in the opening week, so a preseason long-term-injury input is not built.
