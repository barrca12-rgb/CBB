# Alternate-line ladder at the opener: plan (written Nov 1, 2026, before any ladder was pulled)

Research only. Nothing is bet on it this season, and it is not shown on the card. The March read decides whether
it becomes a price-selection layer.

## Why
An opener's alternate ladder is derived from its main line, which is stale by design. With the model's distribution,
the best EV on the ladder is sometimes a point off the main number at a better price.

## Cost (The Odds API; SGO ends Nov 25)
- **Per pull:** the per-event odds endpoint, `markets=alternate_spreads,alternate_totals`, one region, the play's
  book and the best-price book for the main number. Ten books count as one region, so a pull is 2 credits.
- **Event id:** from this run's Odds API line rows, else the Novig file, else The Odds API's events list, which
  uses no credits (added Nov 1 before any pull: `odds.py` drops the Odds API rows for books SGO already quotes, so
  the line rows alone would skip SGO-covered games).
- **Per play:** one pull, never repeated. Two plays on the same game in the same card run share it.
- **Per day:** about 15 v1 and 4 band B plays a game day (2023-26 backtest), so roughly 24-38 credits. That is under
  the brief's 40-credit stop.
- **Guards (`cbb/ladder.py`):**
  - Skip any pull whose reported cost exceeds 2 credits, and switch the logger off.
  - Skip when the Odds API balance is below 20,000 before Nov 25, or below the 50,000 research floor from Nov 25.

## What is logged (`lines/ladder/`, which the card workflow commits; this folder holds the plan and the reads)
- **`ladders.csv`:** every rung returned, with book, market, side, point, price, the provider's last_update, our pull
  time, bet id and the game's start.
- **`plays.csv`:** one row per play:
  - the main number and price;
  - the model's cover probability and EV at the main number and at every rung on the play's side, at the play's book
    and the best-price book;
  - the best rung, its EV and price, and the gain over the main number.

## Distribution
The rule is the live win-probability rule's own normal form: cover probability = Φ(edge / σ).
- **σ is set so the slope at an edge of 0 equals the live rule:** spreads 0.0255 per point gives σ = 15.6 points;
  totals 0.014 gives σ = 28.5.
- **Why not the capped rule itself:** its 58% / 56.5% cap is a ceiling for calibration, not a distribution. On a
  ladder it would score every rung beyond the cap as equally likely to cover, and so favor worse numbers at better
  prices.
- **Recorded as a secondary column:** the capped rule's EV.
- **Pushes:** none (continuous). Whole-number rungs are noted.

## Prior
The best rung beats the main number by 0.5 points of EV (0.005 in EV per unit) on about 10% of plays.

## March read (Mar 14)
On plays where the ladder's best rung beat the main number by 0.5+ points of EV, did that rung outperform the main
number?
- **Measures:** units at recorded prices (graded on the result) and CLV, with the Odds API's close for that rung as
  the reference (the last alternate quote before tip from the same book's main-line close pull; if no rung close
  exists, CLV is reported as unavailable and counted).

## Kill rule
Either of these ends it:
- under 10% of plays have a rung beating the main number by 0.5+ points of EV;
- on those plays, the better rungs did not outperform the main number at recorded prices.

## Stop rule
After three weeks (Nov 23), if under 10% of plays have such a rung, the pull is switched off, with a note in this
log. The credits are better spent on the card.
