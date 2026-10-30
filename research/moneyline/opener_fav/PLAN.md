# Opener favorite moneylines, live log: plan (written Oct 30, 2026, before any signal was logged)

Research log, approved by Chad on Oct 30. Nothing is bet, nothing on the card changes, and no frozen file is touched.

## Why
- The Oct 26 edge search (`research/edges/out/e1_run.txt`, idea 1) priced every opening moneyline with the model's
  win probability, Phi(margin / 11), and bet EV +5% or better at the best price.
- Favorites returned +5.34% in 2024 (1,306 bets, se 1.76) and +5.14% in 2025-26 (1,458 bets, se 1.92).
  Underdogs returned +1.95% and -2.56%.
- Favorites were a reported split, not that test's primary rule, and the opener data covers 2024-26 only. A live
  confirmation is needed before anything else.

## The signal (frozen now; it is the Oct 26 rule, restricted to favorites)
- **When:** a book's FIRST moneyline on a game, as the card's own pull sees it. That is the first row with both
  prices for that game and book in the price log (`lines/ml/`).
  - Games and books already in the log when it started (Oct 30, 19:41 UTC) are not openers and are never signals.
  - A book first logged as "missing" becomes an opener at its first priced row.
- **Side:** the favorite at that book (the negative price).
- **Model win probability:** Phi(m / 11), with m the card's projected margin for that side at that run. That is the
  live card's own mapping, the one the Oct 26 test used.
- **Signal:** EV = p x payout(price) - (1 - p) of +5% or more.
- **Recorded** at the moment of the card run to `lines/ml/opener_fav.csv`: run time, game, date, tip, book, the side's
  team, price, the other side's price, p, EV and m. This is written by `cbb/card_features.py` (the card's unfrozen
  wrapper), which only copies what `run_day.plays` sees.

## Grading (`research/moneyline/opener_fav/run.py`)
- **Bet unit:** one per game and side, the first qualifying quote (earliest; on a tie, the best price), 1 unit at that
  price. Every qualifying quote is reported too, per book.
- **Result:** the final score from the card's own report (`reports/cbb_<date>.csv`, state "post").
- **Moneyline CLV, in points:** the Shin no-vig closing probability on the side minus the Shin no-vig probability of
  the recorded pair.
  - Closing probability: the median across books of each book's last priced pair before tip.
  - Recorded pair: the price and the other side's price, from the same row.
- **Uncertainty:** 95% date-clustered bootstrap intervals (2,000 draws).

## Reads (fixed now)
- **Weekly (Monday health line), descriptive only:** signals, graded bets, record, units, ROI, mean CLV.
- **Jan 15, a stop check only:** with 200+ graded bets and ROI below 0, the log stops and the question is closed.
  Otherwise it continues.
- **Mar 14, the decision read:** worth a proposal only if all of these hold:
  - ROI at the recorded prices is +2% or more, with the 95% interval above 0;
  - there are 300+ graded bets;
  - mean moneyline CLV is above 0.

  Otherwise closed.
- **A proposal, if any:** a hand bet at the opener on favorites only, with its own cell in the record, never mixed
  with v1. It needs Chad's approval, a MODEL_FREEZE entry and a Discord note.

## Caveats written now
- **Timing:** "first seen by the card" is not always the book's true opener. The card pulls every 10 minutes, so a
  price can move before the first pull sees it. The lag between a book's first spread and its first moneyline is
  reported as a check.
- **Limits:** opener limits are low, and this is about whether the price was beatable, not about size.
