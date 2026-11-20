# Plumbing run, Nov 20, 2026 (counts only; no slopes, intervals, records or miss rates read)

`python -m research.injury_reports.evaluate --plumbing --through 2026-11-19` runs end to end.

| Check | Result |
|---|---|
| 2026-27 player box scores | load: 33,736 rows, 1,068 games, through Nov 19 |
| Verified tips (lines/tipoffs.csv) | 580 games; 203 of 689 v1-priced games since Nov 3 have none and are excluded |
| v1 games scored (Nov 3-19) | 486, all with a final score and a v1 total; 470 with a closing spread |
| **ESPN listings (`injuries/log.csv`)** | **0. The file does not exist: ESPN's injuries feed returned an empty list on all 5,092 pulls this season (injuries/sources/health.csv).** |
| RotoWire listings (first_seen.csv) | 851 matched; 62 listings at T-60 (59 questionable, 3 out); J != 0 in 19 games at T-60, 3 at T-open |
| Covers listings | 0 matched (rows carry no ESPN athlete id) |

## What this means

- **The live injury adjustment has been zero all season.** The model reads ESPN (injuries/sources/choice: ESPN;
  recommendation.json kept ESPN on Nov 14 because "only 6 injuries matched to a line move"). With ESPN empty,
  `home_injury_missing` and `away_injury_missing` are 0 on all 1,145 card game-rows Nov 1-19.
- **The Dec 15 read is blocked as pre-registered:** the primary source has no listings, so Q1 has no data and Q2 has
  no games with J != 0. RotoWire is the only source with usable rows, and at its current pace (19 games with J != 0
  through Nov 19) Q2 would not reach its 300-game minimum by Jan 15 either.
- **Not changed:** the live source, the plan's definitions, thresholds or reads. Switching the live source or using
  RotoWire as the study's primary source is Chad's call (the first is a model change under the freeze).

## Implementation notes (set before any result)

- `injuries/log.csv` and `first_seen.csv` keep a row the first time a player+status+report date is seen, so "listed
  at T" = the player's latest row at or before T, within 7 days, with an injury status. A latest "cleared" or
  "available" row means off the report.
- Minutes shares use only games before each date (this season once a team has 3 games, else last season on the same
  team), and a player counts only if he played the team's last game, as in cbb/injuries.py.
