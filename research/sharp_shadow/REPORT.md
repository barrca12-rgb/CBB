# Sharp-market shadow: forward read, Nov 24, 2026 (PLAN.md, written Nov 10)

**Result: does not pass.** Two of the three pre-registered conditions fail. Per the plan the shadow keeps running to
the Dec 15 checkpoint, because the CLV gap has not gone away. Nothing live changes.

Sample: main plays logged from 2026-11-10 15:00 UTC, settled through Nov 23 (427 plays). Flag = a sharp line (Novig
real market, Pinnacle or BetOnline) was up when the play was logged and the model was 2+ points off it
(`cbb/shadow_sharp.py`). CLV = Pinnacle no-vig CLV (`cbb/clv_pinnacle.py`); SE clustered by date.

| Group | Plays | W-L-P | Flat units | Per play | Staked units | Pinnacle CLV | Beat the close |
|---|---|---|---|---|---|---|---|
| Flagged | 321 | 189-131-1 | +41.71 | +0.130 | +59.49 | +2.58% (SE 0.52) | 53% |
| Not flagged | 106 | 46-58-2 | -16.58 | -0.156 | -16.19 | +8.01% (SE 1.74) | 68% |

By market: flagged spreads 68-49 (+12.63u, CLV +3.94%), totals 121-82 (+29.08u, +1.82%); not flagged spreads 25-31
(-8.76u, +7.48%), totals 21-27 (-7.82u, +8.64%).

| Condition (all three needed) | Result |
|---|---|
| 1. Flagged mean Pinnacle CLV below 0 | **Fails** (+2.58%) |
| 2. Flagged CLV at least 3 points below unflagged | Holds (5.43 points below) |
| 3. Flagged flat units per play below unflagged | **Fails** (+0.130 vs -0.156) |

**Reading:** when a sharp line is already up and the model disagrees with it, our plays still beat the close on
average (+2.6%), just by less than plays made before any sharp line exists (+8.0%). Skipping them would have given up
about 42 flat units over two weeks. The back-read's negative CLV for flagged plays (-3.6%, Oct 30 to Nov 9) has not
held up on the forward sample; part of it came from the old model before the Nov 9 changes.

**Next:** keep the shadow logging; read again on Dec 15 with the same three conditions. If condition 1 still fails
then, close the idea.
