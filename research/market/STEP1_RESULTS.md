# Step 1 results: the Option B historical sample (Oct 26, 2026)

**Sample:** 12 Saturdays, 2022-23 to 2025-26. Every NCAAB spread and total at every US book, every 30 minutes from
24 hours before the first tip; Jan 11, 2025 every 5 minutes. 24,060 credits from the existing plan.

## Coverage and books

| | |
|---|---|
| Games with any line | **100%** of ESPN's games on every January and March date. 64-87% on the November dates (early-season games, often against weak or non-Division I opponents, that books did not list). Before the 41 team names were matched (`oddsapi_aliases.csv`, research only), this read 54-87% |
| Small-conference games with lines | 100% in January and March; 59-81% in November |
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

## Step 2a again, on real prices and times (Oct 27)

`s2a_real.py`, pre-registered in LOG.md.
- **When:** at each game's "market open", the first snapshot with 3+ US books quoting it.
- **Pick:** the live rule (best EV across the four books at their real prices).
- **Reference:** the median of every other US book.

| | Spreads: picks, win %, ROI (real prices) | Totals: picks, win %, ROI |
|---|---|---|
| Current rule | 140, 54.3%, +3.2% (se 5.2) | 242, 57.7%, +10.1% (se 3.6) |
| Model opposes market, ordinary quote | 77, 58.4%, +11.7% | 156, 53.8%, +3.1% |
| Model opposes market, favorable quote | 19, 52.6%, -0.4% | 38, 71.1%, +34.8% |
| Model agrees, favorable quote (the book is off, not the model) | 42, 47.6%, -10.4% | 47, 58.7%, +11.5% |
| Market only: a book 1+ point off the others, no model | 207, 45.2%, -14.7% | 329, 51.1%, -2.7% |

- **Confirms the ESPN result with real prices: the edge is the model's forecast, not finding an off-market
  book.** Betting the outlier book alone loses at real prices.
- **For spreads, the weak cell is "model agrees, favorable quote"** (47.6%, 42 picks). Those picks qualify only
  because one book is off, not because the model disagrees with the market. It is a **candidate v2 filter, not
  established** (12 dates, wide errors; the ESPN close data showed no such weakness). Recorded for a future test
  only.
- **Timing again:** spreads at the 3-book market open (54.3%) did worse than at each book's own first quote
  (61.5% in the table above). The first book to post seems to carry more of the value than the market a little
  later. Speed at the very first posting may matter more than speed in general. The live logs will show how often
  our card catches a book's first quote.

## Next steps (no spend)

1. Done: alias map and coverage re-run (above).
2. Done: step 2a on real prices (above).
3. From Nov 1: the live logs show how often the card catches a book's very first quote, and the delay windows.
