# Kalshi as an eighth price (pre-registered Oct 28, 2026; Chad approved the logger)

**Question:** on the card's own plays, how much expected value would Kalshi's spread and total contracts add on top
of the best of the seven books the card already shops? Research only: the logger reads Kalshi's public market data
(no account, no key) and never touches the card, the picks, the bet log, the line feeds or the protocol.

## Logging (`research/kalshi/logger.py`, `.github/workflows/kalshi_quotes.yml`)

- **When:** after every "Update CBB card" run (about every 10 minutes), like the shadows.
- **Which games:** games on today's and later cards (`reports/cbb_<date>.csv`) with a BET or WATCH in either
  market, plus games with an open logged bet. Kalshi events are matched to them by date and both team names
  (`cbb.teams.norm`, plus `research/kalshi/aliases.csv`; the frozen `data/team_aliases.csv` is not touched); unmatched Kalshi games on card dates
  go to `research/kalshi/data/unmatched.csv` so aliases can be added.
- **What:** every rung of the game's spread (`KXNCAAMBSPREAD`) and total (`KXNCAAMBTOTAL`) ladder within 6 points
  of the card's number: yes bid, yes ask, their sizes, volume. A row is written only when a rung's quote changed
  since the last logged row (`research/kalshi/data/quotes.csv`), plus the first sighting of each rung, so the log
  also records when Kalshi's lines open.

## Evaluation (about three weeks of plays; read once, around Nov 23)

For each card BET logged in `bets/bets.csv` (cohort v1), the first Kalshi snapshot within 15 minutes after
`logged_at`:
- **Kalshi on our side:** spread plays use the rung that is our side at the same number or better (favorite -5.5 =
  "wins by over 5.5" YES; underdog +4.5 = the favorite's "wins by over 4.5" NO); totals use "Over N" YES / NO.
  Cost per $1 payout = ask (YES) or 1 - YES bid (NO), plus the taker fee 0.07 x p x (1 - p).
- **EV at each venue:** the card's own win chance for the edge at that number (`run_day.win_prob`), paid at the
  price; the book side uses the logged book, number and price.
- **Gain per play:** max(0, EV at Kalshi - EV at the best book) (you only use Kalshi when it is better); plays
  with no Kalshi market yet count as 0.

**Bar:** mean EV gain per play of +0.5% or more across all plays, with a date-clustered 95% interval above 0, and at
least 40 plays. Also reported: share of plays with a Kalshi market at all, share where Kalshi was better, gain by
market, and the same with a resting limit order at the bid (maker fee 0.0175 x p x (1 - p)), labeled as an upper
bound because fills are not guaranteed.

**If it clears:** a proposal to Chad to add Kalshi to the card's price shopping (a line-feed change: his approval, a
MODEL_FREEZE entry and a Discord note). **If not:** the logger is switched off and the result recorded.

**Prior:** low-moderate. At the posted price Kalshi was about -112 on its main line in a 60-game 2025-26 sample, so
the gain has to come from disagreement on our side, and its lines open only about 24 hours before tip, after many of
our plays are alerted.
