# Moneylines: log

## Test 1 (Oct 30): a book's moneyline against its own spread. FAILS, closed.
`test1.py`, exactly as `PLAN.md`. Full tables in `out/test1.txt`; signals in `out/test1_bets.csv`.

- **Data:** 321,500 closing quotes with a spread and both moneylines on D-I games with a result, 2014-2024. After the
  clean-quote rules, 310,617 quotes on 49,920 games remain. Dropped: off-market spread 6,931; overround outside 0-15%
  3,028; moneyline favorite opposite the spread favorite 924.
- **Fit (2014-2017, frozen):** P(home wins) = Phi((-s + 0.09 x home_site) / 10.42). Calibration in 2018-2024 is close
  to the diagonal in every decile, within about 3 points.
- **Result, confirm 2018-2024, best signal per game and side:** 8,515 bets won 56.4% against an expected 60.1%.
  Units -228.4, ROI -2.68%, 95% interval [-4.88%, -0.52%]. Every-quote version: ROI -2.44%, [-4.72%, -0.11%].
- **Dev 2014-2017 (in-sample fit):** 2,281 bets, ROI -0.31%, [-7.06%, +6.58%].
- **By cut (confirm):**
  - favorites -0.65%; underdogs -16.8%; +300 or longer -27.9%;
  - no book, price band or season clears the bar with an interval above 0, except Caesars (New Jersey), 103 bets;
    one cell out of about 30 is what chance alone produces.
  - 2019 is the worst season (-25%): it is dominated by Caesars Sportsbook rows, worth a data check if this is ever
    revisited.
- **Reading:** at the close, when a book's moneyline disagrees with its own spread, the moneyline is the better
  predictor. The signals won 3-4 points less often than the spread said they would. Books do not leave their
  moneylines stale against their spreads at the close; if anything, the spread is the stale number.
- **Not a test result:** "the spread is the stale one, so bet the spread side when its own moneyline disagrees" is a
  new hypothesis. It would need its own plan; nothing is acted on.
- **Kill rule:** ROI under +1% and the interval below 0. Closed.

## Test 2 (Oct 30): a book's moneyline against the other books' moneylines. FAILS, closed.
`test2.py`, exactly as `PLAN.md`. Tables in `out/test2.txt`.

- **Data:** 234,445 clean quotes with 3+ other clean books on the game (31,529 games, 2018-2024).
- **Result, confirm 2021-2024, best signal per game and side:** 6,651 bets won 19.3% against an expected 21.4%.
  ROI -7.72%, 95% interval [-13.91%, -1.32%]. Dev 2018-2020: ROI -26.8%.
- **Why:** 95% of the signals are underdogs, median +500. With the vig removed proportionally, the other books'
  consensus overstates longshots (the favorite-longshot bias). Its calibration shows favorites winning more often than
  priced (deciles 7-10: predicted 0.72 to 0.92, actual 0.76 to 0.95). So an underdog priced above the consensus looks
  like value and isn't.
- **Not acted on (post hoc, outside the plan):** favorites and near pick'em prices among the signals did well:
  favorites +11.1% on 311 bets; -149 to +149 +11.5% on 428. Small cells picked after seeing the table; a hypothesis
  for a future plan, not a finding.
- Closed.

## Test 3 (Oct 30): the model's win probability against the market. FAILS, closed (with one caveat).
`test3.py`, exactly as `PLAN.md`. Tables in `out/test3.txt`.

- **Fit (2014-2017, frozen):** P(home wins) = Phi(model margin / 10.32). Calibration in 2024-2026 is within about 3
  points in every decile.
- **Result, confirm 2024-2026:** EV +3% or more at the best clean closing price across books gave 7,540 bets. They
  won 49.8% against an expected 54.8%. ROI -1.83%, 95% interval [-4.68%, +1.02%]. Dev 2014-2017: ROI +1.52%,
  [-2.02%, +5.31%]. By season: 2024 +1.0%, 2025 -0.5%, 2026 -7.9%.
- **Caveat:** the plan compares the model with the CLOSING moneyline. The model's measured edge is against the
  opener, which the market corrects by the close.
  - The same 1,156 underdog games where v1 has a spread play (edge 2.5+ at the opener): the spread at the opener
    returned +13.6% (at an assumed -110). The moneyline on the same dog at the best closing price returned -3.4%,
    [-13.9%, +7.9%].
  - So the test says the model has no moneyline edge left at the close. It says nothing about moneylines at the
    opener.
  - History has almost no opening moneylines (2025-26 only, one book), so that question can only be read from the
    live log `lines/ml/`, which records every book's first moneyline from Oct 30.
- Closed as pre-registered.
- **Possible follow-up (needs its own plan and Chad's go):** a live shadow of "v1's underdog spread plays, also logged
  at the opening moneyline", read against the result and the closing moneyline after enough games.
