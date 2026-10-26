# Edge search results (Oct 26, 2026)

**Holdout:** seasons 2025-2026, read once per idea with the specification fixed beforehand. They are "unseen" only
for this search. The frozen model itself was built while looking at backtests that include those seasons.

## Idea 1: moneylines at real prices. No reliable edge.

Rule: the model's win probability (the card's own mapping) against the best moneyline across books; bet at EV
+5% or more.

| | Development 2014-2024 | Holdout 2025-2026 |
|---|---|---|
| At the close | +3.0% ROI (23,456 bets, se 1.4) | **-4.9%** (3,516, se 2.8) |
| At the opener (2024 only in development) | +3.4% (3,023, se 2.8) | +0.8% (3,351, se 2.3) |
| Opener favourites only (a split, not the rule) | +5.3% (1,306, se 1.8) | +5.1% (1,458, se 1.9) |

- **Verdict:** the closing-line result reversed in the holdout, and the opener result is within noise.
- **Opener favourites:** the one consistent pattern is moneyline favourites at the opener, +5% in both periods.
  That is a split examined after the fact, and close to what the spread edge already captures. **Watch, don't
  adopt.**
- **Calibration:** the model's win probabilities carry real information beyond the market (z 15 at the close),
  consistent with the spread edge. They are not better than the market alone (log loss 0.5299 vs 0.5306).

## Idea 2: where the opener edge concentrates. Mostly evenly spread.

**Overall, the frozen rule at the opener** (-110 assumed):

| Market | Development (2014-17, 2024) | Holdout 2025-26 |
|---|---|---|
| Spreads | 57.4% (3,399) | 57.7% (1,605) |
| Totals | 55.4% (8,482) | 55.6% (2,604) |

**Segments:** 38 tested, 3 flagged at 2 SEs, about 1.7 expected by chance.

| Flagged in development | Development | Holdout | Read |
|---|---|---|---|
| Spreads at neutral sites | 63.9% (657), +6.6 vs all | 60.4% (227), +2.7, se 3.0 | same direction, weaker. Watch |
| Spreads with edge 5+ | 71.3% (348), +13.9 | 63.8% (116), +6.1, se 4.6 | same direction. Bigger edges winning more argues the live win-chance cap (58% for spreads) is too low; a staking question, not a new edge. Large edges are also where bad openers hide, so check the data before acting |
| Totals: overs | 57.4%, +2.0 | 55.2%, -0.3 | did not hold |

Nothing else stands out: by month, conference tier, spread size and total level the edge is broadly flat.

## Idea 4: totals matchup features. Real but too small to matter. Closed.

- **Fit:** walk-forward on residuals against the close.
  - **Three-point interplay** (one team's 3PA rate against the other's 3PA rate allowed): consistently positive,
    z about 2.
  - **Pace mismatch:** slightly negative, z up to -2.1 in the latest fits.
- **Size:** each moves the expected total by about 0.15 points per standard deviation.
- **Totals vs the opener with the features added:** 57.4% vs 57.2% in development, 55.9% vs 55.6% in the
  holdout. That is noise-level, not worth a model change.

## What survives

**Nothing that justifies a v2 change on its own.** Worth tracking in the forward data:
1. Spreads at neutral sites.
2. Opener moneyline favourites.
3. **The edge-size gradient.** It is the most actionable: if large edges really win more than 58%, the staking
   and win-chance table could be revisited at the Jan 15 checkpoint, with Chad's approval and its own backtest.
