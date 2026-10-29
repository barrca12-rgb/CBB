# CollegeBasketballData (CBBD) coverage check (Oct 29, 2026)

Research only; nothing live changed. The raw responses are in the private data repo
(`cbb-data/research/cbbd/coverage_2026-10-29/`), because CBBD's terms forbid redistributing raw data. This file
holds counts only. Script: `coverage.py`; the key is injected by the environment's proxy and never stored.

**Calls:** about 51 of the account's monthly allowance; the API reports 949 left.
- **This session:** 43 calls (providers 1, lines 13 plus one probe, lineup/substitution/plays checks 18,
  substitution sample 11).
- **Interrupted child session:** about 8 calls.

## Betting lines (`/lines`; sample: Jan 14-16 of each season)
**Providers listed:** ESPN BET, consensus, teamrankings, numberfire, Bovada, Draft Kings.

| Season | Games with lines | Closing spread | Opening spread | Providers |
|---|---|---|---|---|
| 2013-14 | 64 | 43 | 0 | consensus, numberfire, teamrankings |
| 2014-15 | 108 | 82 | 0 | same |
| 2015-16 | 106 | 85 | 0 | same |
| 2016-17 | 166 | 122 | 0 | same |
| 2017-18 | 81 | 59 | 0 | same |
| 2018-19 | 34 | 34 | 0 | numberfire, teamrankings |
| 2019-20 | 64 | 64 | 0 | consensus, numberfire, teamrankings |
| 2020-21 | 100 | 90 | 0 | same |
| 2021-22 | 185 | 174 | 0 | consensus, teamrankings |
| 2022-23 | 176 | 176 | 0 | ESPN BET, consensus, teamrankings |
| 2023-24 | 65 | 65 | 0 | ESPN BET |
| 2024-25 | 83 | 83 | 0 | ESPN BET |
| 2025-26 | 114 | 114 | **114** | Draft Kings, Bovada |

**Result: no opening lines for 2018-2023.** Openers appear only in 2025-26, where we already have them.
- **Closes 2014-2022:** come from aggregators (consensus, teamrankings, numberfire), not sportsbooks.
- **Overlap:** our ESPN odds feed already has sportsbook closes for every season (8-13 books per game from 2019).
- **Conclusion:** CBBD's lines add nothing.

## Lineups and substitutions (`/lineups/game/{id}`, `/substitutions/game/{id}`, `onFloor` in `/plays`)
| Season | Games tested | With substitutions |
|---|---|---|
| 2015-16 | 1 | 0 |
| 2018-19 | 1 | 0 |
| 2021-22 | 1 | 0 |
| 2022-23 | 3 | 0 |
| 2023-24 | 5 | 5 (53-90 substitution rows; lineup stints with offense/defense ratings and pace) |
| 2024-25 | 5 | 5 |
| 2025-26 | 1 | 1 |

**Result: on-court lineup data starts in 2023-24.**
- **Our ESPN play-by-play:** substitutions only from 2024-25, in 1,586 of 6,136 games, plus all of 2025-26.
- **What CBBD adds:** 2023-24, and apparently most of 2024-25.
- **Overall:** about three full seasons of who was on the floor, against one and a quarter now.
- **Sample size:** the per-season test is a small sample (5 games). A full count would come from the pull itself.
- **`onFloor` in plays:** empty in the tested older games.

## What this is good for
**Lineups:** the only new data here. Three seasons of on-court lineups is the input a player-impact model
(adjusted plus-minus) needs. That model would value an absent player by how the team actually plays without him,
in place of today's minutes-share rule.
- **Who could use it:** the injury-report study and lineup v2.
- **Status:** a new project. It needs a plan and approval before anything is pulled at scale.
