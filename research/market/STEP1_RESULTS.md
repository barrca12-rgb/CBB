# Step 1 results: the Option B historical sample (Oct 26, 2026)

**Sample:** 12 Saturdays, 2022-23 to 2025-26. Every NCAAB spread and total at every US book, every 30 minutes from
24 hours before the first tip; Jan 11, 2025 every 5 minutes. 24,060 credits from the existing plan.

## Coverage and books

| | |
|---|---|
| Games with any line | 54-87% of ESPN's games per date, lowest on the November dates. This is understated: 41 Odds API team names (mostly small schools such as "Boston Univ. Terriers" and "Loyola (Chi) Ramblers") do not match our team table yet |
| Small-conference games with lines | 59-77% of them (same caveat) |
| DraftKings, FanDuel, BetMGM, Caesars | all four present on every date, on nearly every listed game, all with prices |
| Other books seen | Fanatics, BetRivers, Bovada, Circa, PointsBet, Unibet, SuperBook, WynnBET, BetOnline, LowVig and more |
| Snapshot cadence served | exactly as requested (30 minutes, or 5 on Jan 11) |

## When openers post

- **Timing:** the four big books' first quotes come a median 18-21 hours before tip, mostly the previous evening.
  BetMGM is latest, DraftKings earliest.
- **Truncation:** the window starts 24 hours before the first tip, so some openers came even earlier. About half
  the November games and about 10% of mid-season games were already up at the first snapshot.

## Opening prices

- **Price mix:** 58% of opening spreads at the four books are -110. The rest range from -102 to -120.
- **Scale:** the assumed -110 in the backtests is right for most openers but not all. The live card already uses
  real prices.

## How long an opening number lasts (Jan 11, 2025, 5-minute snapshots)

| | Still at the opening number after 10 min | 15 min | 30 min | 60 min | Median life |
|---|---|---|---|---|---|
| All opening spreads (four books) | 96% | 92% | 85% | 77% | about 4 hours |
| All opening totals | 97% | 96% | 89% | 81% | about 6 hours |
| **The model's spread picks** (59) | 98% | 90% | 83% | 71% | about 2.75 hours |
| **The model's total picks** (76) | 97% | 96% | 91% | 80% | about 9.5 hours |

Openers do not vanish in minutes. The model's spread picks move a little sooner than spreads in general, but 9 in
10 were still there 15 minutes later.

**Card frequency (one Saturday only):** going from every 10 minutes to every 5 would catch very little extra; about
2-4% of openers change within 10 minutes. The Nov 12 review will confirm this with live data.

## The model's picks at real first quotes

The frozen model (live-like variant) against each game's first quote at the best of the four books, at the price
actually offered:

| | Picks (12 dates) | Win % | ROI at real prices |
|---|---|---|---|
| Spreads (edge 2.5+) | 193 | 61.5% | +17.2% |
| Totals (edge 3+) | 297 | 54.5% | +4.3% |

**Caveats:**
- 12 dates is a small sample.
- These seasons were part of the model's development history.
- This is observed availability on a feed, not accepted bets: limits at the open are unknown.

**What it does show:** the opener edge was quotable at named books with real prices, for long enough to act on.

## What this changes

- **The biggest open question narrows.** "Was the historical opener ever a real, bettable quote?" Yes: at
  DraftKings, FanDuel, BetMGM and Caesars, mostly at -110, and usually for hours. Bet limits at the open remain
  untested.
- **Timing:** speed matters at the scale of tens of minutes, not seconds. The card's 10-minute runs are adequate.
  The 30-minute overnight runs matter only for openers that post overnight, which the live logs will show.
- **Full pull:** 2023-2026, about 5.1M credits, price still unverified. Not needed to answer the availability
  question at this level. It would matter only for a large-sample, real-price re-grade of every historical pick.

## Next steps (no spend)

1. Add the 41 team names to a research-only alias map (the live alias file is frozen) and re-run the coverage
   figures.
2. Re-run step 2a's edge-vs-quote decomposition on these dates with real prices and times.
