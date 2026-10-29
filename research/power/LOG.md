# Attacking noise: log (Oct 29, 2026)

Research only. Nothing live changed. These seasons were examined in earlier studies: every number here is a
re-measurement, not a fresh test, and nothing is promoted.

## 1-2, 7. Scorecard (`scorecard.py`): CLV first, all games, units second
**Per-bet noise at the opener** (v1's own bets, `out/rescore.txt`):

| Market, era | Bets | Units: SD, t | Result vs line: SD, t | **CLV: SD, t** | Bets needed vs units |
|---|---|---|---|---|---|
| Spreads, development | 2,653 | 0.94, 4.9 | 11.1 pts, 10.0 | **1.6 pts, 36.8** | **0.018×** |
| Spreads, holdout 2024-26 | 1,599 | 0.94, 4.3 | 11.4 pts, 6.5 | **2.0 pts, 26.6** | **0.026×** |
| Totals, development | 4,694 | 0.94, 6.6 | 17.1 pts, 12.5 | **2.3 pts, 37.4** | **0.031×** |
| Totals, holdout 2024-26 | 2,579 | 0.95, 3.4 | 17.0 pts, 7.1 | **2.8 pts, 33.6** | **0.010×** |

- **The headline:** CLV separates strategies 30-100 times faster than units on the same bets.
- **The caveat:** CLV pays only if the close is efficient. Here our bets beat the line by more than their CLV
  (spreads 1.85 vs 1.34 points), so far consistent with that.
- **The scorecard's three views:**
  - paired CLV against a baseline;
  - the all-games regression of the result vs the close on (forecast − close);
  - units as a check, with date-clustered intervals and a bets-needed calculator.

## 8. Re-score at the ESPN opener (`rescore.py`)
| Candidate vs v1 | Era | Games where picks differ | **Total CLV diff (95%)** | Units diff (95%) | Incremental beyond-close slope (SE) |
|---|---|---|---|---|---|
| **Lineup v2**, spreads | development | 658 | **+255 (+170, +346)** | +38 (−12, +89) | 0.54 (0.21) |
| **Lineup v2**, spreads | holdout | 398 | **+122 (+55, +191)** | +0.7 (−34, +36) | 0.70 (0.21) |
| **E2**, totals | development | 785 | **+209 (+66, +346)** | +45 (−8, +101) | 0.56 (0.33) |
| **E2**, totals | holdout | 562 | **+151 (+36, +271)** | +34 (−11, +78) | 0.38 (0.33) |
| C2, totals | development | 1,516 | −347 (−546, −148) | +5 | −0.21 (0.07) |
| C2, totals | holdout | 995 | −169 (−342, +9) | −18 | −0.28 (0.08) |

**What it shows:**
- **v2 and E2:** both gain CLV over v1 in both eras, with every interval above 0. In units they were "can't tell".
- **C2:** loses CLV in both eras, and the close says it carries negative information.
- **v1 totals:** have no information beyond the close in 2024-26 (slope −0.03, SE 0.06). Totals profit comes from
  beating early numbers, not from knowing more than the close.

## 4. Sequential reads, 2026-27 (`SEQUENTIAL_PLAN.md`, `sequential.py`)
**The read:** weekly paired-CLV comparison of the lineup v2 shadow against v1.
- **Boundaries:** Haybittle-Peto, |z| ≥ 3.29 at interim looks and 1.96 at the Mar 14 final.
- **Schedule:** Mondays from Nov 9, 2026.
- **Expected power:** about 80% by about 230 differing games, near season's end. Units would need several seasons.

**Drafted, not active:** Amendment 3 would make this v2's decision endpoint. It needs Chad's approval before the
first game.

**Data fix:** `lines/closing.csv` keeps only the latest pull, so v2-only plays had no close. `closing_history.py`
rebuilds every pull from git history (631 pulls so far). `research/v2_lineup/evaluate.py` now reads it: a plumbing
fix, with the rule unchanged.

## 3, 9. Luck-adjusted outcomes (`LUCK_PLAN.md`, `luck.py`): NOT ADOPTED (pre-registered rule)
| | Spreads | Totals |
|---|---|---|
| Outcome SD vs close, actual → luck-adjusted | 10.9-11.3 → 8.7-8.9 (−22%) | 16.3-16.9 → 12.1-12.9 (−25%) |
| SE of v1's beyond-close slope, ratio | 0.87 (needed ≤ 0.80) | 0.91 (needed ≤ 0.80) |
| Do incremental slopes agree? | v2: 0.56 actual vs −0.26 luck-adjusted, **no** | E2 0.69 vs −0.39, C2 −0.19 vs +0.24, **no** |

**Why it fails:**
- **It removes signal as well as noise.** Lineup and matchup effects work partly through shot-making, so their
  measured value flips sign.
- **It has a built-in bias.** The make-rate estimate has no home-court term, so luck-adjusted margins run 2.6-3.2
  points below actual.

A version with a venue term would be a new pre-registered study, not launched. CLV stays the primary scoreboard.

## 5. More independent bets (`SCOPING_markets.md`, a Sonnet agent)
| Option | Finding | Status |
|---|---|---|
| Opener totals | Already bet by the card; same games as the spreads, so no new samples | Already live |
| First-half lines | Tested and killed Oct 27; about 7% hold | Low |
| Women's D-I | Results data free and reachable, but about 85% of historical lines missing; a thin market | A forward-only shadow log is the cheap start, if wanted |
