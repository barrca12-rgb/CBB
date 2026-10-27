# Results so far (Oct 26, 2026)

## Step 1: not pulled

The sample as specified costs 101,680 Odds API credits, more than the account's balance. The authorized amount was
blank, and the provider is not reachable from this environment. Full pull: about 5.1M credits; the dollar price
needs the provider's page. Details and two affordable sample options are in `STEP1_REPORT.md`.

## Step 2a: is the edge forecasting or price selection?

**Data:** ESPN per-book numbers. Prices are not in the data, so ROI is at an assumed -110.

| Era | Market | Current rule | Market only (no model) | Model opposes / favorable | Model opposes / ordinary | Model agrees / favorable |
|---|---|---|---|---|---|---|
| Closes 2014-2023 | spread | 53.7% (8,778) | 52.4% (6,976) | 54.3% (2,621) | 53.9% (3,560) | 53.3% (2,479) |
| Closes 2014-2023 | total | 54.1% (19,887) | 52.7% (17,318) | 54.5% (9,432) | 53.3% (6,407) | 54.1% (3,927) |
| Openers 2024 | spread | 57.7% (1,389) | 52.9% (3,088) | 59.1% (409) | 59.6% (198) | 56.7% (775) |
| Openers 2024 | total | 58.4% (1,987) | 53.1% (3,884) | 58.2% (714) | 58.2% (328) | 58.5% (938) |

- **The edge is forecasting, not price selection.** Win % fitted jointly on the model's deviation from the other
  books (D), the bet book's quote advantage (Q) and market dispersion:

  | Era, market | D | Q |
  |---|---|---|
  | Closes 2014-2023, spreads | predicts strongly (z 8.8) | z 1.3 |
  | Closes 2014-2023, totals | predicts (z 3.7) | z -0.8 |
  | Openers 2024 | z 1.1 or less, too few bets to separate the two | z 0.9 or less |

  Betting the outlier book with no model is break-even at the close (52.4-52.7%) and about 53% at the 2024
  openers. Those 2024 outlier quotes still show about +1 point of line value, so a favorable number moves the
  right way but does not win by itself.
- **No weak cell.** At the 2024 openers, "model opposes the market, ordinary quote" won 59.6% (spreads, 198) and
  58.2% (totals, 328), no worse than the rest. There is no candidate filter for v2 from this decomposition.
- **Limits:**
  - prices are assumed;
  - books are ESPN's last lines (closes) before 2024, so the close era is a closing-line test;
  - one opener season;
  - no time-to-tip control (no timestamps).

  The snapshot data (step 2, if approved) would repeat this with recorded prices and times.

## Step 4: does the market overreact to a shooting night?

Slope of the next game's close minus the model, and of the result minus the close, on the previous games' net
3-point surprise. Controls: model margin, missing players, neutral site. Date-clustered SEs.

| Era | Close moves with the surprise (pts per surprise point) | Result vs close (pts per point) |
|---|---|---|
| 2014-2018 | +0.011 (z 9.1); adjusted +0.008 (z 6.1) | -0.012 (z -1.9); adjusted -0.009 (z -1.4) |
| 2019-2022 | +0.008 (z 8.1); adjusted +0.005 (z 4.7) | -0.007 (z -1.2); adjusted -0.004 (z -0.6) |
| 2023-2026 | +0.005 (z 3.7); adjusted +0.003 (z 1.9) | -0.005 (z -0.8); adjusted -0.001 (z -0.1) |

**The market moves slightly with a team's last shooting night.** A typical surprise (1 SD = 13.6 points) shifts
the close by 0.04-0.15 points relative to the model. The effect shrinks every era.

**It is not an exploitable overreaction.** The result against the close shows no reliable reversal in any era,
and none at all since 2019. **Closed.**
