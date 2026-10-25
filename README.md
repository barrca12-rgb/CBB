# College basketball model

Men's Division I projections (margin, total, win probability) for every game, compared against live sportsbook
lines. Built the same way as the [NFL model](https://github.com/barrca12-rgb/NFL), which stays separate.

## Plan

1. **Data check** (done for hoopR, see [`DATA.md`](DATA.md)): hoopR game results and box scores 2012-2026, a
   team-name table across sources, then KenPom, Barttorvik and SportsGameOdds once they're reachable.
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
from cbb import data
games, team_games = data.load(range(2012, 2027))
```

`team_games` has two rows per game (offense `team_id` vs defense `opp_id`) with possessions, points per 100
possessions and the Four Factors: the input to the ratings. Teams are keyed by ESPN id; `data/teams.csv` maps them
to KenPom names (and later Barttorvik and SportsGameOdds names).

## API keys

| Variable | Used for |
|---|---|
| `KENPOM_API_KEY` | KenPom ratings, archive ratings by date, FanMatch predictions |
| `SGO_API_KEY` | SportsGameOdds live lines and betslip links |

Set them as GitHub Actions secrets for the scheduled runs, and as environment variables for local or cloud runs.
Never commit them.
