# College basketball model

Men's Division I projections (margin, total, win probability) for every game, compared against live sportsbook
lines. Built the same way as the [NFL model](https://github.com/barrca12-rgb/NFL), which stays separate.

## Plan

1. **Data check** (done, see [`DATA.md`](DATA.md)): hoopR game results and box scores 2012-2026, KenPom,
   Barttorvik, ESPN historical lines, SportsGameOdds live lines, and a team-name table across them.
2. **Ratings** (done): opponent-adjusted offense, defense, tempo and Four Factors by time-decayed ridge
   regression (the NFL model's method), KenPom preseason prior, plus a second stage (`projection.py`).
3. **Backtest 2014-2026** (done, see [`BACKTEST.md`](BACKTEST.md)): about break-even against closing lines (totals 54.4% with referee crews); 58.6% ATS and
   57.5% on totals against opening lines in 2024-2026.
4. **Website** (done): the daily card below, with an NFL | CBB link between the two sites.

## Daily card (live)

Published at **https://barrca12-rgb.github.io/CBB/** by the `Update CBB card` workflow
(`.github/workflows/update.yml`): five runs a day October-April (7:37am, 11:37am, 4:07pm ET, and 8:37pm and 11:37pm ET for
the next day's openers), from the Actions tab, or from the page's **Update now** button.

```bash
python -m cbb.run_day                         # today's card with live SportsGameOdds lines
python -m cbb.run_day --date 2026-01-17 --replay   # a past day with ESPN's stored lines (checks the page)
```

Each run: ratings from every box score so far (KenPom preseason prior), the second stage from
`data/projection.json` (KenPom FanMatch or KenPom ratings, Barttorvik, Four Factors, rest, home edge, missing
players), then edges against every book. Calls come from the 2024-2026 backtest against opening lines:

| Market | BET (1u) | WATCH (not a play) | Backtest at the opener |
|---|---|---|---|
| Spread | edge 3+ pts | 2-3 | 58.6% at 3+ |
| Total | edge 4+ pts | 3-4 | 57.5% at 4+ |

The edge is against openers, not closing lines, so bet early and only at the "good down to" number or better.
`lines/openers.csv` keeps the first number seen at each book (and when), `lines/closing.csv` the last pregame number.

**Context** (`cbb/context.py`): market ratings from this season's earlier closing lines (`lines/closing.csv`),
an altitude flag, and the referee crew when ESPN posts it (tendencies from every official's past games,
`data/referees.csv`, refit with the projection). Unknown crews count as average.

**Injuries** (`cbb/injuries.py`): each run reads ESPN's college basketball injury report. A listed player who
played the team's last game adds P(miss) x his share of team minutes to the projection's missing-minutes input
(Out 100%, Doubtful 75%, Questionable 40%, Day-To-Day 35%, Probable 10%; starting guesses). The card shows who's
listed and what each moves the projection. Every report is logged to `injuries/log.csv` for calibration. The size
of the effect is conservative (about 1 point for a player with 17% of team minutes) until a season of logs and CLV
says otherwise.

**Tracker** (`cbb/tracker.py`, like the NFL model's): every run grades earlier bets, logs today's BETs in
`bets/bets.csv` at the number they first appeared, and shows the record, ROI and closing line value on the card.
Stakes scale down automatically if a market's live win rate slides toward break-even. Edit `bets/bets.csv` to the
number you actually got, or set `placed` to `no` for one you skipped.

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
