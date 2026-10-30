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
