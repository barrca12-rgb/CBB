# Research summary (Oct 26-27, 2026)

All research only. Nothing here changed live v1, the card, selection rules, staking, the bet log or the
forward-test protocol. Details, pre-registrations and logs: `research/market/`, `research/edges/`,
`research/originator/`.

## Bottom line

- **The opener edge is real.** The frozen model's spread edge at the opener holds historically: 57.3% (2015-17)
  and 58.0% (2024-26) on the backtest's corrected tables; 57.7% at the opener in the 2025-26 holdout.
- **The openers were bettable quotes.** The historical sample shows them at the big four books (DraftKings,
  FanDuel, BetMGM, Caesars), mostly at -110, and usually for hours.
- **The model is near its ceiling with this data.** Its misses break down like the market's, and none of the
  model or filter changes tested improved it.
- **The edge exists only at the opener.** Picks win about 60% at the opening number and about 52% at the close,
  because the market moves toward the model before tip.
- **What remains:** speed and book choice, and whether bets are accepted at the open at real stakes. The live logs
  and the Pikkit bet records answer that from Nov 1.

## Corrections to the historical record

- **Openers:** oriented by the moneylines recorded with them, never by the close.
- **Swapped records:** 152 games with home and away reversed in ESPN's odds (mostly neutral sites) are excluded
  from the spread tables. They had shown up as fake big wins. The live card was never affected.
- **Referee crews:** zeroed for opener totals, as at the open. Totals at the opener 2024-26: 56.2%.

## Tests

| Test | Result | Verdict |
|---|---|---|
| Model edge vs catching an off-market book (ESPN multi-book; real quotes) | The edge is the model's forecast; an outlier book alone loses (-15% spreads at real prices) | Model is the source |
| Market overreaction to a shooting night | The close moves slightly with the surprise; it never reverses profitably | Closed |
| Moneylines at real prices | +3.0% development, -4.9% holdout at the close; opener +3.4% / +0.8% | No edge |
| Where the opener edge concentrates (month, tier, size, site, side) | Broadly flat; neutral-site spreads about 60% vs 57% | Watch neutral sites |
| Totals matchup features (pace mismatch, three-point attempt interplay) | Real but about 0.15 points; win % +0.2-0.4 | Closed |
| Spread edges of 5+ points | Inflated by the swapped records; the real part is smaller and opener-only | Revisit at Jan 15 (win-chance cap) |
| Spread agreement and situation filters (KenPom, Barttorvik, market ratings, rest, conference, injuries) | None raised the win rate | Closed |
| Which picks can wait (execution timing) | None; which picks get chased cannot be predicted (holdout AUC 0.49) | Bet at once |
| Historical odds sample (12 Saturdays, real quotes) | 100% coverage mid-season; 90% of spread picks still at the number 15 minutes later; first book to post 58.5% vs later books 54.4% | Openers were bettable |
| Error decomposition (61,450 games) | Same shape for model and line; pace and efficiency misses unpredictable | Near the ceiling |
| Rotation adjustment (player values x minutes change) | Coefficient 0.42 (CI 0.32-0.52) but R2 0.0014 | Failed the gate |
| Recency-weighted and two-regime stage 2 | Opener CLV change -0.01 to +0.03 points | Killed |
| Tier-specific stage-1 settings | Low-major MAE +0.0004 | Killed |

## Actions

1. Bet as soon as an alert lands, at the first book to post (usually DraftKings).
2. On spread edges of 5+, take a better number at another book by hand if one is up at a similar price; the
   logged signal stays the same.
3. Log every bet in Pikkit; acceptance and limits at the open are the main unknown.

## Scheduled

- **Nov 12:** card-frequency review with live data.
- **Jan 15:** win-chance cap for big edges, neutral-site pattern.
- **Open idea:** a player-rating injury model, which needs EvanMiya history or play-by-play.
