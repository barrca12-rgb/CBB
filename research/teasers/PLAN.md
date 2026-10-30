# Two-leg teasers on the card's spread plays: plan (written Nov 1, 2026, before any teaser number was computed)

Research only. Nothing is bet on it. If it survives, the output is a proposal for Chad at the Nov 16 read.

## Blocked until Chad's book list exists
The pricing is the whole question, so no step below runs, including the per-leg table, until Chad supplies the
following for each book he uses (DraftKings, FanDuel, BetMGM, Caesars, Fanatics, bet365, BetRivers). Screenshots
of each teaser menu are enough.
- whether college basketball teasers are offered;
- the point options (4, 4.5, 5, 5.5, 6, 7);
- the two-leg and three-leg prices at each option;
- whether totals legs are allowed;
- any leg restrictions (e.g. lines a leg may not start or cross);
- the maximum stake.

The list is saved as `research/teasers/books.csv` (one row per book × points × legs) before the run, and this plan
is not edited after that except to log the run.

## Frame
- **Data:** the live-like frame (crews unknown, KenPom from the day before, the live opening-week rule), the same
  one behind `research/totals_band/run.py` (`research.persistent_disagreement.common.baseline`, swapped games out).
- **Seasons:** 2014-17 and 2024-26, reported per era and never pooled for the kill rule.
- **Plays:** v1 spread plays (edge 2.5+) and band B spread plays (2.0-2.49) at the ESPN opener.
- **Books:** the history has one opener per game (ESPN's), not a per-book line. Each book's menu and price is applied
  to the same legs; "same book" in the pairing rule therefore means the same pairs priced at each book in turn.

## 1. Per-leg cover rate (reported first, with intervals, before any teaser arithmetic)
- The opener number moved 4, 4.5, 5, 5.5, 6 and 7 points in our favor; a leg wins if the margin beats the teased
  number, pushes are reported and then counted per each book's push rule (a push leg drops the teaser to one fewer
  leg, or loses, as the book states).
- Cut by edge band (2.0-2.49 band B, 2.5-2.99, 3-3.99, 4-4.99, 5+), by favorite / underdog at the opener, by era.
- **Interval:** 95%, date-clustered (the same clustered standard error as `research/totals_band/run.py`).
- The single at the opener's own number is in the same table, so each move's gain in cover rate is read directly.

## 2. Key-number density
The share of final margins landing on each number from 0 to 10, 2014-26 (all D-I games in the frame), so the write-up
says which teased legs cross the dense numbers and which do not.

## 3. Two-leg teasers versus the same two singles
- **Pairing rule (fixed now):** on each date, the two highest-edge spread plays (v1 and band B together) that are
  teasable under the book's restrictions form one pair; no other pairs are formed that day.
- **At each book's real price and each points option:** win rate, ROI and units per pair, and the same two plays as
  singles at the opener price (the card's -110 assumption where the price is not recorded; recorded prices where
  they exist, 2024-26).
- **The comparison that matters:** the difference in expected units per pair (teaser minus two singles), with a 95%
  date-clustered interval, per teaser size and book.
- **Stakes:** one unit on the teaser versus one unit on each single (two units risked) is reported, and so is
  equal-risk (two units on the teaser). The kill rule uses the equal-risk comparison per unit risked.
- **Three-leg:** the same way, top three plays per date, only where a book prices three-leg teasers.

## 4. Totals legs, separately
Where a book allows totals legs: the same per-leg table and pair comparison on total plays (v1 3.0+, the switched-off
band B 2.0-2.99 reported separately). Expect worse: 6 points on a total near 145 moves less of the distribution
than 6 points on a spread.

## Kill rule (fixed now)
Teasers are closed if either holds:
- the teaser's expected units per pair at a book's real price are not above the two singles' by at least 0.05 units,
  with an interval excluding zero, in both eras (checked per book and size; a size survives only if it passes in
  both eras);
- per-leg cover at +6 is under 72% for the edge bands the card plays.

## Outcomes
- **Survives (any book and size):** a proposal for Chad at the Nov 16 read as a hand bet. Chad places it when the
  pair exists; the singles stay as they are. It is tagged "teaser" in the log and judged on its own cell.
- **Fails:** closed, with the per-leg table and key-number table kept so the question never needs re-running.

## Report
The per-leg table, the key-number table, the teaser-versus-singles table per book and size, and the verdict in one
sentence.
