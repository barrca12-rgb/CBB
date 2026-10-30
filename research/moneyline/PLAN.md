# Moneylines: is a book's number wrong, and can we take it? Plan (written Oct 30, 2026, before any moneyline result was computed)

Research only. Nothing is bet on it and nothing goes on the card. A version that survives becomes a proposal for Chad,
which would need a live shadow, a freeze entry and a Discord note before any money.

Chad's question (Oct 30): can we model the moneyline, find where a book's number is wrong, and take advantage? Three
separate ways a moneyline can be wrong, each tested on its own, with no picking the best afterwards.

## Data
- **History:** ESPN's per-book closing lines, `data/lines/espn_<season>.csv`. These hold each book's own closing
  spread, home moneyline and away moneyline.
  - 2014-2017: several offshore books, Pinnacle among them.
  - 2018-2024: 8-13 US books per game.
  - Rows whose `book` is in `lines_hist.NOT_BOOKS` (consensus and pick services), "Opening", or empty are dropped.
- **Results:** final scores from `data.season_games` (D-I vs D-I, completed). Overtime counts as played, the way a
  moneyline grades.
- **Clean quotes only**, the same idea as the live bad-quote guards:
  - the book's spread is within 3 points of the median of the other books on the game;
  - the moneyline pair's overround is between 0% and 15%;
  - the spread favorite is the moneyline favorite (a pick'em spread is allowed either way);
  - both prices are present and at least 100 in absolute value.
- **Live:** `lines/ml/` (from Oct 30) records every book's moneyline as the card pulls it, change-only. It is used for
  timing, meaning how long a mispriced moneyline stays up, and for a live shadow if a test survives.

Signal threshold for all tests: a side's EV of at least +3% at the book's own price, fixed now. One unit flat at the
book's price. Results are reported as ROI per bet, with a 95% date-clustered bootstrap interval (2,000 draws).

## Test 1: a book's moneyline against its own spread (primary)
Books often set the moneyline from the spread with a conversion table. Where the table and the result disagree, the
moneyline is mispriced against the book's own number.
- **Fair win probability from the spread, fit on 2014-2017 only, then frozen:**
  - Model: P(home wins) = Phi((-s + c * home_site) / sigma), where s is the game's median closing home spread across
    books, home_site is 1 for a non-neutral game, and c and sigma come from maximum likelihood.
  - c is expected to be about 0. The spread already holds home court; it stays in only to catch a table that prices
    home court differently.
- **Signal:** for each clean quote, p_side comes from that book's own spread through the frozen fit; EV = p_side x
  payout(ML_side) - (1 - p_side).
- **Bet unit, reported two ways:**
  - (i) every quote with a signal;
  - (ii) primary: the best signal per game and side across books, as a bettor shopping would take it.
- **Eras:**
  - dev 2014-2017 (the fit's own seasons, so optimistic, reported for shape only);
  - confirm 2018-2024 (out of sample; this is the read).
- **Kill rule (confirm era, bet unit ii):** test 1 fails if any of these holds:
  - fewer than 200 signals;
  - ROI under +1%;
  - the 95% interval includes 0.
- **Reported alongside:** by underdog / favorite, by price band (-300 or shorter, -299 to -150, -149 to +149, +150 to
  +299, +300 or longer), by spread band, by book and by season, plus realized win rate against p_side (calibration).

## Test 2: a book's moneyline against the other books' moneylines
- **Fair win probability:** the median of the other books' no-vig probabilities for the side (multiplicative vig
  removal), with at least 3 other clean books on the game.
- **Signal:** EV of at least +3% at this book's price.
- **Eras:** dev 2018-2020, confirm 2021-2024. Earlier seasons are skipped because they have too few books per game.
- **Kill rule:** the same as test 1, on the confirm era.
- **Reported alongside:** how often the outlier book's own spread was also off-market, since that would make it a
  broken quote rather than a price.

## Test 3: the model's win probability against the market
- **Win probability from the frozen model's margin,** on the live-like frame used across this research
  (`research.persistent_disagreement.common.baseline`, swapped records out):
  - P(home wins) = Phi(final_margin / sigma_m), with sigma_m fit on dev 2014-2017 only, then frozen;
  - calibration is reported by decile.
- **Signal:** EV of at least +3% against the best clean closing price across books.
- **Eras:** dev 2014-2017, confirm 2024-2026 (the same eras as the spread research).
- **Kill rule:** the same as test 1, on the confirm era.
- **Also reported:** on games where v1 already has a spread play on an underdog, whether that underdog's moneyline
  had the higher EV than the spread (ROI of each on the same games).

## Order and what happens next
- Test 1 runs first (Oct 30). Tests 2 and 3 follow under this plan.
- A test that survives gets a live shadow from `lines/ml/` before anything else: signals logged with time posted and
  time gone, and graded on the result.
- The read is at least 4 weeks after the shadow starts. That read gives the share of signals still available 10
  minutes after the quote first appeared, and ROI at the logged prices.
- A test that fails is closed, with its tables kept.

## Caveats written now
- Closing quotes are the last number before tip. At a closing number there is little time to act, and limits on
  moneylines can be low.
- Historical prices carry no timestamps, so availability is measured only on the live log.
- The spread-to-win mapping is the market's own. Test 1 measures whether a book's moneyline disagrees with its own
  spread, not whether the spread is right.
