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

## Follow-up: spread edges of 5+ points (Oct 26)

**Data problem found.**
- **What:** 67 of the historical spread plays are home/away swaps between ESPN's odds and the game records. The
  line favours one team while the model and KenPom both have the other by 10+.
- **Where:** 88% at neutral sites. The result sided with the model in 55 of them, so the line is the flipped side.
- **Effect:** all 67 sit in the 7+ edge band and won 90%. They are fake edges, and the moneyline orientation check
  cannot catch them, because the whole record is flipped, moneyline included.
- **Live is not affected:** the card matches lines by team IDs and handles reversed home/away.
- **Headline effect (live-like model, spreads at the opener):** 2015-17 goes from 57.1% to 56.8%; 2024-26
  unchanged (57.8%). The historical reports should exclude these games. Proposed below, not applied.

**Without the swaps:**

| Spread plays | Development | Holdout 2025-26 |
|---|---|---|
| Edge 2.5-3.5 | 56.5% (2,069) | 57.1% (1,034) |
| Edge 3.5-5 | 54.2% (982) | 57.6% (455) |
| Edge 5-7 | 64.8% (214) | 57.0% (79) |
| Edge 7+ | 74.7% (73) | 80.6% (31) |
| Edge 5+, graded at the close instead | 62.1% (287) | 49.1% (110) |

- **The big-edge advantage is genuine but smaller than it looked, and it is an opener effect.** By the close, the
  market had moved to the model's side; in 2025-26, graded at the close, the same plays were 49%.
- **The development fit** (win chance by edge, swaps removed) is 53.9% at 2.5, 56.6% at 3.5, 60.6% at 5 and 65.8%
  at 7. The live table caps at 58%.
- **The holdout's 5-7 band** (57.0%, 79 plays) does not confirm the higher numbers. Only the small 7+ band does.
- **Verdict:** not enough to raise the cap now. Revisit at Jan 15 with the forward data's large-edge plays.

**Neutral-site spreads hold up.**
- **Excluding every game where the model and KenPom both favour the other team** (a stricter swap filter):
  neutral sites read 60.0% in development (499) and 59.6% in the holdout (193), against 56.2% and 57.6% at home
  courts.
- **Possible explanations:**
  - early-season tournament games, where the market leans on reputation;
  - neutral-court home-edge handling.
- **Caveat:** neutral-site records are also where the residual data problems sit, so a few undetected swaps may
  remain.
- **Verdict:** the strongest candidate from this search. Track it in the forward data. If it holds at Jan 15, it
  is a v2 staking proposal, not a selection change.

**Reporting correction, applied Oct 26:** `BACKTEST.md` now leaves the likely swapped games out of every spread
table, opener and close, with the pregame rule above: 152 games in 2013-2026. Spreads vs the opener at the live
cutoffs move from 57.5% to 57.3% (2015-17) and from 58.1% to 58.0% (2024-26). Totals are unchanged. No live play
changes.

## Execution timing: which picks must be taken now? (Oct 26)

Opener picks by what the line did by the close (swapped records excluded), graded at the opener vs at the close
(-110 assumed):

| Spreads | Share (dev / holdout) | Opener win % (dev / holdout) | Close win % (dev / holdout) |
|---|---|---|---|
| Chased (close moved 1+ toward us) | 58% / 64% | 60.3% / 61.1% | 52.8% / 52.6% |
| Stable | 33% / 23% | 52.0% / 53.7% | 51.7% / 53.7% |
| Faded (moved 1+ away) | 9% / 12% | 51.5% / 47.2% | 57.7% / 51.8% |

| Totals | Share (dev / holdout) | Opener win % (dev / holdout) | Close win % (dev / holdout) |
|---|---|---|---|
| Chased | 46% / 69% | 59.9% / 59.0% | 53.4% / 50.8% |
| Stable | 32% / 15% | 53.9% / 54.0% | 53.7% / 54.0% |
| Faded | 22% / 16% | 48.3% / 41.8% | 55.2% / 44.5% |

- **The edge is almost entirely "take it now".**
  - **Chased picks:** most picks are chased, and they win about 60% at the opener but about 52-53% at the close.
    The market finds the same thing the model found, and the value is gone by tip.
  - **Stable picks:** about break-even to 54% at either time.
  - **Faded picks** (the market moved against the model) are the losers at the opener.
- **It cannot be told in advance which picks will be chased.** A model using edge size, market, month, neutral
  site, conference, spread size and KenPom's agreement scored AUC 0.63 in development and 0.49 (chance) on the
  2025-26 holdout. Every pick should be treated as "act at once"; nothing is gained by waiting.
- **Graded at the close, holdout picks are 50.7-51.8% in every predicted group.** Without the opener there is no
  edge in this data.

**What this means:** the question that decides whether the edge is real money is no longer prediction. It is
availability: whether the opener could be bet, at what price and limit, and for how many minutes after our card
saw it. The answer can only come from timestamps:
- the live delay windows from Nov 1 (5-10 / 15-25 / 30-45 / 60-80 minutes);
- the historical snapshot sample (Option B in `research/market/STEP1_REPORT.md`, about 26,000 credits, no extra
  dollars), which would also show when openers post relative to the card's runs.

**Operational gap:**
- **Card cadence:** the card runs every 30 minutes from midnight to 8 am ET, and about every 10 minutes the rest
  of the day.
- **When openers post:** this preseason, openers first appeared in our feed in the evening (6-10 pm ET, only 7
  games so far).
- **The risk:** if in-season openers post overnight, a 30-minute gap costs part of the edge. The live logs will
  show when openers post.
- **The fix, and why it waits for Chad:** a 10-minute overnight cadence costs about 2,900 credits a month. It
  changes when signals are logged, so it is a decision for Chad (forward-test protocol section 8), not a logging
  fix.
