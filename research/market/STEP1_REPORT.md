# Step 1: sample and completeness check — cost report (nothing pulled)

**Status: stopped before spending.** The sample as specified would use more credits than the account has left
this month. The authorized amount in the instructions was blank. The provider's site also cannot be reached from
this environment. So no historical call was made, and none of the completeness questions can be answered yet.
This report gives the exact cost and the options.

## The predetermined sample

Rule, fixed before any pull: 3 dates per season, all NCAAB games that day, spreads and totals, all books, every
5-minute snapshot from 24 hours before the first tip to the last tip.

**Correction to the rule:** the "first Saturday of November" falls before opening day in every season, so it has no
games. It is replaced by the first Saturday on or after the season's first game, declared before pulling.

| Season | Date | Games (ESPN schedule) | 5-minute snapshots | Credits (spreads + totals) |
|---|---|---:|---:|---:|
| 2023 | Sat Nov 12, 2022 | 59 | 421 | 8,420 |
| 2023 | Sat Jan 14, 2023 | 152 | 433 | 8,660 |
| 2023 | Sat Mar 4, 2023 | 93 | 421 | 8,420 |
| 2024 | Sat Nov 11, 2023 | 58 | 427 | 8,540 |
| 2024 | Sat Jan 13, 2024 | 133 | 433 | 8,660 |
| 2024 | Sat Mar 2, 2024 | 136 | 409 | 8,180 |
| 2025 | Sat Nov 9, 2024 | 63 | 415 | 8,300 |
| 2025 | Sat Jan 11, 2025 | 143 | 411 | 8,220 |
| 2025 | Sat Mar 1, 2025 | 133 | 433 | 8,660 |
| 2026 | Sat Nov 8, 2025 | 68 | 415 | 8,300 |
| 2026 | Sat Jan 10, 2026 | 149 | 433 | 8,660 |
| 2026 | Sat Mar 7, 2026 | 92 | 433 | 8,660 |
| **Total** | | **1,279** | **5,084** | **101,680** |

## How the cost is computed

- **Price per snapshot:** a historical odds snapshot is priced at 10 credits per market per region. That is the
  "about ten times a live call" in the instructions. It is not verified on the provider's page, which is
  unreachable from here.
- **Per snapshot here:** spreads and totals in the US region (which carries DraftKings, FanDuel, BetMGM and
  Caesars) cost 20 credits.
- **Games per snapshot:** one snapshot returns every game listed at that moment, so the cost depends on the number
  of snapshots, not the number of games.
- **Snapshot count:** from the ESPN schedule, first tip minus 24 hours to the last tip, every 5 minutes. A late
  tip listed as 11:59 pm (often a placeholder) lengthens a day slightly.

## Why it stopped

- **Account balance:** 95,589 credits left at 20:55 UTC Oct 26. The live forward-test logger needs up to about
  42,000 a month. The sample alone (101,680) is more than the whole balance.
- **No authorization:** the authorized amount for the sample was left blank.
- **No route from this environment:** the-odds-api.com cannot be reached from here (DNS fails). A pull would run
  as a one-off GitHub Actions job using the repository's existing `ODDS_API_KEY`, as the live logger does. This
  session cannot start workflows (403), so a pull needs Chad to start it or a push-triggered job.

## Full pull, 2023-2026 (spreads, totals and moneylines, main markets)

| | |
|---|---:|
| Game days | 588 (141 + 148 + 152 + 147) |
| Unique 5-minute snapshots (24 h before each day's first tip to its last tip; overlapping days counted once) | 169,820 |
| Credits at 30 per snapshot (3 markets, 1 region) | **about 5.1 million** |
| Credits for spreads and totals only (20 per snapshot) | about 3.4 million |

**Dollar cost:** not verified. The provider's pricing page is not reachable from here, and the instructions require
the price from that page. 5.1 million credits is far above the current 100,000-a-month plan. It would need the
provider's largest monthly tiers for a month or more, or a custom quote.

**To get the number:** open the pricing page, or allow `the-odds-api.com` under this environment's Network access →
Allowed domains so it can be read here. Then note:
- the price of the smallest tier with at least 5.1M credits a month;
- whether historical data is included on that tier.

## Options for Chad (each needs an amount and a yes)

| Option | What it answers | Credits | Fits this month's headroom (about 53,000 after live logging)? |
|---|---|---:|---|
| A. The sample as specified | everything step 1 asks | 101,680 | no |
| B. The 12 dates at 30-minute snapshots, plus one date (Jan 2025) at 5-minute | coverage, books and prices, earliest quote per game, share of games quoted before the card's run times; cadence checked on one full day | about 26,000 | yes |
| C. The 4 January dates at 5-minute snapshots | every step 1 question, mid-season only | about 34,000 | yes |

Options B and C stay inside the existing plan, so they cost no extra dollars. Each still needs a yes, because the
authorized amount was blank and these credits share the allowance with the live logger. Nothing beyond step 1 is
pulled until the full pull's number has been seen and approved.
