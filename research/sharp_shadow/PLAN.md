# Sharp-market shadow (Chad, Nov 10, 2026: "shadow it")

Written before any forward result. Research only: nothing here changes the card, picks or stakes.

## Rule under test

A main play is **flagged** when, at the moment it was logged, a sharp line (Novig, Pinnacle or BetOnline) was
already up for that game and market, and the model still disagreed with it by 2+ points:
`edge - gap >= 2`, where `gap` = how many points better our number was than that sharp number on our side
(the largest gap across the sharp books that were up). If it went live, a flagged play would be skipped or kept at
minimum stake.

Code: `cbb/shadow_sharp.py`, run after every card in `update.yml`, writes `bets/shadow_sharp.csv`.
Test: `audit/test_shadow_sharp.py`.

## Data fix found while building it

Novig is an exchange. With no money on a game, the feed lists an empty ladder rung at a fake line (prices like
-9900 or -100000; e.g. Wisconsin-Delaware total "131.5" with the market at 152.5). These are dropped: a Novig number
counts only when both sides are priced within +/-200. The Nov 9 step-1 read (STEP1.md) did not drop them; see the
correction there.

## Back-read (in-sample, rule chosen after looking; a lead, not proof). Main plays Oct 30 - Nov 9, settled

| group | W-L | flat units | staked units | Pinnacle CLV | beat no-vig close |
|---|---|---|---|---|---|
| flagged: sharp up, model 2+ off it | 30-38 | -10.23 | -7.70 | -3.63% | 28% |
| not flagged (no sharp line yet, or within 2) | 138-110 | +15.24 | +15.89 | +3.01% | 52% |

Flagged by market: spreads 8-11 (CLV -3.07%), totals 22-27 (CLV -3.84%).

## Forward read (the test)

- Sample: main plays logged from **2026-11-10 15:00 UTC** on.
- Read on **Nov 24, 2026** (or at 30 flagged settled plays, if later), and report every number in REPORT.md.
- **Pass** (bring to Chad to go live) only if all hold on the forward sample:
  1. flagged plays' mean Pinnacle CLV is below 0;
  2. flagged plays' Pinnacle CLV is at least 3 points (percent) below unflagged plays';
  3. flagged plays' flat units are below unflagged plays' flat units per play.
- Otherwise: keep shadowing to Dec 15 (the agreed checkpoint) and read again, or drop it if the CLV gap is gone.
- Results alone (W-L) are not enough at this sample size; CLV is the main measure.
