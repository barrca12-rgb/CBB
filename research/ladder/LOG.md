# Ladder log

## Nov 23, 2026: stop-rule check (PLAN.md, Chad's Nov 1 brief item 2). Kept on, with a caveat.

`python -m research.ladder.read --through 2026-11-22`: 893 plays with a ladder row, 844 pulls, 212 credits
(0.25 per pull). Plays with rungs on their side: 106. A rung beat the main number by 0.5+ points of EV on 66 of 106
(62.3%; spreads 29 of 47, 61.7%; totals 37 of 59, 62.7%). Rule bar 10%: **kept on**.

**Caveat (found while checking the rule's output; the rule itself is unchanged):** the qualifying rungs are almost all
long shots. Of 68 plays clearing 0.5 points of EV, 60 are rungs priced +200 or longer, a median 12 points from the
main number. Their EV comes from cbb/ladder.py's normal cover probability with sigma 15.6 (spreads) and 28.5
(totals), which is set from the card's near-line win-rate slope; the actual spread of results around the close is
about 11.3 and 16.5. With a sigma that wide, any model edge makes far-away alternate lines look very profitable.
Counting only rungs priced between -150 and +150, 7 of 111 plays (6.3%) clear the bar, which is under 10%.
Credits are small either way (212 in three weeks). From Nov 25 the pull also stops below the 50,000 research floor.
Whether to keep it is Chad's call.
