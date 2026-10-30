# Opening-moneyline shadow on our spread plays: plan (written Oct 30, 2026, before any shadow number was computed)

Research log, approved by Chad. Nothing is bet, nothing on the card changes, and no frozen file is touched.
`research/moneyline/shadow/run.py` reads the bet log and the price log the card already writes (`lines/ml/`, from
`cbb/card_features.py`). It adds nothing to the card run.

## Why
- On our underdog spread plays, the spread at the opener returned +13.6% (test 3, 2024-26).
- The underdog moneyline at the close returned -3.4%.
- History cannot say what the moneyline at the opener does: there is one book for one season.
- The live price log records every book's moneyline from Oct 30, so the live season answers it.

## What is recorded, per v1 and band B spread play (`shadow/plays.csv`)
- **Identity:** bet id, bet type (v1 / band B), date, game, our side.
- **Dog or favorite:** decided by the logged spread line (positive = underdog; a pick'em is decided by the moneyline).
- **At the moment the play was logged** (the last price-log row for each book at or before `logged_at`):
  - our side's moneyline at the play's book, with that quote's timestamp;
  - the best moneyline on our side across the seven frozen books, with its book and timestamp.
- **Missing quotes:** a book with no row, or a row with a missing price, is "no quote"; it is never priced at -110.
  Plays logged before the price log started (Oct 30, 19:41 UTC) are "before the price log" and kept out of the reads.
- **Model win probability for our side, two versions, labeled:**
  - "conversion": the frozen spread-to-win conversion from test 1, applied to the model's projected margin m, with
    m taken from `bets.csv` `model` for the play:
    P(home wins) = Phi((m + 0.092 x home_site) / 10.422);
  - "margin": the model's own margin distribution from test 3: P(home wins) = Phi(m / 10.322).
- **Graded when the game settles:**
  - the moneyline result (win/loss);
  - units for 1 unit at the recorded price, at the play's book and at the best book;
  - moneyline CLV in percentage points = the no-vig closing probability on our side minus the no-vig probability of
    the recorded quote.
    - Closing: the median, across the books quoting it, of each book's last pre-tip pair, devigged with Shin's
      method.
    - Recorded: the recorded book's own pair at that moment, also devigged with Shin.
    - If the recorded quote has no opposite side, CLV is "unavailable".

## Weekly line (the Monday health report)
- Plays recorded, and moneyline units and ROI at the play's book and at the best book.
- Beside them, the same plays' spread units, split by underdog and favorite.
- Descriptive only; nothing is flagged.

## Pre-set read (Jan 15, 2027; fixed now)
- **Worth a proposal only if, on each side with 200+ graded plays:**
  - the moneyline ROI at recorded prices (best book) is within 3 points of the spread ROI on the same games; and
  - the mean moneyline CLV is above 0.
- **Otherwise closed.** A side short of 200 plays at Jan 15 is read at Mar 14 under the same rule.
- **A proposal, if any:** a hand bet beside the spread, never instead of it, and never a price longer than +250.

## Report
- The first week's table.
- The share of plays where a moneyline on our side was quoted at the play's book when the play was logged.
