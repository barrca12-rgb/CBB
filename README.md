# College basketball model

Men's Division I projections (margin, total, win probability) for every game, compared against live sportsbook
lines. Built the same way as the [NFL model](https://github.com/barrca12-rgb/NFL), which stays separate.

## Plan

1. **Data check** (done, see [`DATA.md`](DATA.md)): hoopR game results and box scores 2012-2026, KenPom,
   Barttorvik, ESPN historical lines, SportsGameOdds live lines, and a team-name table across them.
2. **Ratings** (done): opponent-adjusted offense, defense, tempo and Four Factors by time-decayed ridge
   regression (the NFL model's method), KenPom preseason prior, plus a second stage (`projection.py`).
3. **Backtest 2014-2026** (done, see [`BACKTEST.md`](BACKTEST.md)): no edge against closing lines; 57.5% ATS and
   55-56% on totals against opening lines in 2024-2026.
4. **Website** (done): the daily card below, with an NFL | CBB link between the two sites.

## Daily card (live)

Published at **https://barrca12-rgb.github.io/CBB/** by the `Update CBB card` workflow
(`.github/workflows/update.yml`): four runs a day October-April (7:37am, 11:37am, 4:07pm ET, and 8:37pm ET for the
next day's openers), from the Actions tab, or from the page's **Update now** button.

```bash
python -m cbb.run_day                         # today's card with live SportsGameOdds lines
python -m cbb.run_day --date 2026-01-17 --replay   # a past day with ESPN's stored lines (checks the page)
```

Each run: ratings from every box score so far (KenPom preseason prior), the second stage from
`data/projection.json` (KenPom FanMatch or KenPom ratings, Barttorvik, Four Factors, rest, home edge, missing
players), then edges against every book. Calls come from the 2024-2026 backtest against opening lines:

| Market | BET (1u) | WATCH (not a play) | Backtest at the opener |
|---|---|---|---|
| Spread | edge 3+ pts | 2-3 | 57.5% at 3+ |
| Total | edge 4+ pts | 3-4 | 56.1% at 4+ |

The edge is against openers, not closing lines, so bet early and only at the "good down to" number or better.
`lines/openers.csv` keeps the first number seen at each book; `lines/ncaab_<date>.csv` the day's latest pull.

**One-time setup:** in the CBB repo, Settings -> Secrets and variables -> Actions, add `SGO_API_KEY` and
`KENPOM_API_KEY`; Settings -> Pages -> Source: "GitHub Actions". For the page's button, paste a fine-grained token
(this repo only, Actions: Read and write) when it asks; it stays in that browser.

**After each season:** `python -m cbb.backtest`, then `python -m cbb.projection <next season>` to refit
`data/projection.json`, and `python -m cbb.evaluate` for BACKTEST.md.

## Usage

```bash
pip install -r requirements.txt
python -m cbb.coverage            # download 2012-2026 hoopR data (cached in cbb/cache/) and rewrite DATA.md
python -m cbb.lines_hist          # historical lines from ESPN's odds feed into data/lines/
OMP_NUM_THREADS=1 python -m cbb.backtest    # walk-forward ratings, every season
python -m cbb.evaluate            # BACKTEST.md
```
