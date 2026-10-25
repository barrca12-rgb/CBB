# College basketball model

Men's Division I projections (margin, total, win probability) for every game, compared against live sportsbook
lines. Built the same way as the [NFL model](https://github.com/barrca12-rgb/NFL), which stays separate.

## Plan

1. **Data and APIs** (see [`DATA.md`](DATA.md)): hoopR game results and box scores 2012-2026; KenPom ratings,
   point-in-time archive, preseason and FanMatch predictions 2012-2027; Barttorvik ratings and daily time machine;
   all matched to ESPN team ids. SportsGameOdds client written, waiting on `SGO_API_KEY`.
2. **Ratings:** opponent-adjusted offense, defense and pace per 100 possessions by time-decayed ridge regression
   (the NFL model's `ratings.py` method), with KenPom as a preseason prior, a second opinion and a benchmark.
3. **Backtest 2012-2025** walk-forward against closing lines: spreads and totals, early season vs conference play,
   neutral sites, by size of edge.
4. **Website:** a CBB site at `barrca12-rgb.github.io/CBB/` with the daily slate, model plays and betslip links,
   its own Update button, and an NFL | CBB link between the two sites.

## Usage

```bash
pip install -r requirements.txt
python -m cbb.coverage            # download 2012-2026 hoopR data (cached in cbb/cache/) and rewrite DATA.md
```

```python
from cbb import data, kenpom, torvik, sgo
games, team_games = data.load(range(2012, 2027))
kenpom.archive("2025-02-15")       # KenPom ratings as of a date (point-in-time prior for backtests)
kenpom.preseason(2027)             # preseason ratings
kenpom.fanmatch("2026-02-14")      # KenPom's predictions for a day's games; kenpom.match_games() adds game_id
torvik.time_machine("2025-02-15")  # Barttorvik ratings as of a date (from 2014-11-20)
sgo.lines()                        # live NCAAB spreads/totals/moneylines by book, with deep links
```

Everything downloaded is cached in `cbb/cache/`: past seasons and dates for good, the current season for 6 hours.

`team_games` has two rows per game (offense `team_id` vs defense `opp_id`) with possessions, points per 100
possessions and the Four Factors: the input to the ratings. Teams are keyed by ESPN id; `data/teams.csv` maps them
to KenPom names and ids; `data/team_aliases.csv` covers renamed teams (Detroit -> Detroit Mercy, ...). Barttorvik
uses KenPom's names.

## API keys

| Variable | Used for |
|---|---|
| `KENPOM_API_KEY` | KenPom ratings, archive ratings by date, FanMatch predictions (sent as a Bearer token; not needed where a proxy adds it) |
| `SGO_API_KEY` | SportsGameOdds live lines and betslip links (sent as `x-api-key`) |

Barttorvik and hoopR need no key.

Set them as GitHub Actions secrets for the scheduled runs, and as environment variables for local or cloud runs.
Never commit them.
