"""Extra second-stage inputs: market ratings, referees, and travel/altitude. Every one uses only information from
before the game.

market ratings   What earlier closing lines say about each team (the NFL model's market.py idea): a time-decayed
                 ridge fit of past closing spreads (home margin = hca + r[home] - r[away]) and closing totals
                 (total = t0 + s[home] + s[away]), refit each day on this season's games before it. Closing lines
                 carry what box scores miss (injuries, lineups, sharp opinion). The line being bet is never used.
referees         Each official's tendency from his earlier games (all seasons): fouls per game and points versus our
                 ratings model's total, shrunk toward 0; the crew's average. hoopR officials (ESPN), ~97% coverage.
travel/altitude  Time zones the visiting team crossed from its home state, and a flag for home courts at altitude.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from . import data

data.FILES.setdefault("officials", "espn_mens_college_basketball_officials/officials_{season}.parquet")

MARKET_HALF_LIFE = 45.0     # days
MARKET_PRIOR = 4.0          # ridge penalty in games
REF_PRIOR = 30.0            # games of shrinkage for an official's tendency

# Home courts at 4,000+ feet (ESPN ids): Air Force, Colorado, Colorado State, Denver, Northern Colorado, Wyoming,
# Utah, Utah State, BYU, Utah Valley, Weber State, Southern Utah, Northern Arizona, New Mexico, Idaho State,
# Nevada, Montana State, UNLV (2,000 ft, excluded).
ALTITUDE = {2005, 38, 36, 2172, 2458, 2751, 254, 328, 252, 3084, 2692, 253, 2464, 167, 304, 2440, 147}

STATE_TZ = {**{s: -5 for s in "CT DE DC FL GA IN KY ME MD MA MI NH NJ NY NC OH PA RI SC VT VA WV".split()},
            **{s: -6 for s in "AL AR IL IA KS LA MN MS MO NE ND OK SD TN TX WI".split()},
            **{s: -7 for s in "AZ CO ID MT NM UT WY".split()},
            **{s: -8 for s in "CA NV OR WA".split()}, "AK": -9, "HI": -10}
STATE_NAMES = {"Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO",
               "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA",
               "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
               "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA",
               "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT",
               "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM",
               "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
               "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
               "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
               "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY"}


def _tz(state) -> float:
    s = str(state).strip()
    s = STATE_NAMES.get(s, s)
    return STATE_TZ.get(s, np.nan)


# ---------------------------------------------------------------- market ratings

def _ridge(rows_h, rows_a, venue, y, w, k, both_plus: bool):
    n = len(y)
    X = np.zeros((n, 2 + k))
    X[:, 0] = 1.0
    X[:, 1] = venue
    X[np.arange(n), 2 + rows_h] += 1.0
    X[np.arange(n), 2 + rows_a] += 1.0 if both_plus else -1.0
    lam = np.full(2 + k, MARKET_PRIOR * w.mean())
    lam[:2] = 1e-6
    XtW = X.T * w
    return np.linalg.solve(XtW @ X + np.diag(lam), XtW @ y)


def market(games: pd.DataFrame, closes: pd.DataFrame) -> pd.DataFrame:
    """games: game_id, season, date, home_id, away_id, neutral. closes: same keys plus close_margin (closing line's
    home margin) and close_total, for earlier games. Returns game_id, mkt_margin, mkt_total (deviation from the
    average total), mkt_n (fewest earlier lined games of the two teams)."""
    out = []
    c = closes.dropna(subset=["close_margin"]).copy()
    for season, gs in games.groupby("season"):
        cs = c[c["season"] == season]
        for day, gd in gs.groupby("date"):
            h = cs[cs["date"] < day]
            if len(h) < 30:
                out.append(pd.DataFrame({"game_id": gd["game_id"], "mkt_margin": 0.0, "mkt_total": 0.0, "mkt_n": 0}))
                continue
            teams = pd.Index(sorted(set(h["home_id"]) | set(h["away_id"]) | set(gd["home_id"]) | set(gd["away_id"])))
            k = len(teams)
            hi, ai = teams.get_indexer(h["home_id"]), teams.get_indexer(h["away_id"])
            w = 0.5 ** ((day - h["date"]).dt.days.to_numpy() / MARKET_HALF_LIFE)
            v = (~h["neutral"].astype(bool)).astype(float).to_numpy()
            bm = _ridge(hi, ai, v, h["close_margin"].to_numpy(float), w, k, False)
            ht = h.dropna(subset=["close_total"])
            if len(ht) >= 30:
                wt = 0.5 ** ((day - ht["date"]).dt.days.to_numpy() / MARKET_HALF_LIFE)
                bt = _ridge(teams.get_indexer(ht["home_id"]), teams.get_indexer(ht["away_id"]),
                            (~ht["neutral"].astype(bool)).astype(float).to_numpy(), ht["close_total"].to_numpy(float), wt, k, True)
            else:
                bt = np.zeros(2 + k)
            gh, ga = teams.get_indexer(gd["home_id"]), teams.get_indexer(gd["away_id"])
            gv = (~gd["neutral"].astype(bool)).astype(float).to_numpy()
            cnt = pd.concat([h["home_id"], h["away_id"]]).value_counts()
            out.append(pd.DataFrame({
                "game_id": gd["game_id"].to_numpy(),
                "mkt_margin": bm[1] * gv + bm[2 + gh] - bm[2 + ga],
                "mkt_total": bt[2 + gh] + bt[2 + ga],
                "mkt_n": np.minimum(gd["home_id"].map(cnt).fillna(0).to_numpy(), gd["away_id"].map(cnt).fillna(0).to_numpy()),
            }))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["game_id", "mkt_margin", "mkt_total", "mkt_n"])


def backtest_closes(seasons) -> pd.DataFrame:
    """Closing lines for the backtest (ESPN consensus, lines_hist.py) with the game keys market() needs."""
    from . import lines_hist
    parts = []
    for s in seasons:
        path = os.path.join(lines_hist.OUT, f"espn_{s}.csv")
        if not os.path.exists(path):
            continue
        c = lines_hist.consensus(pd.read_csv(path))
        g, _ = data.season_games(s)
        c = c.merge(g[["game_id", "season", "date", "home_id", "away_id", "neutral"]], on="game_id")
        parts.append(c.assign(close_margin=-c["home_spread"], close_total=c["total"]))
    return pd.concat(parts, ignore_index=True)


# ---------------------------------------------------------------- referees

def official_games(seasons) -> pd.DataFrame:
    """One row per (game, official) with the game's total fouls and points."""
    parts = []
    for s in seasons:
        try:
            o = data.fetch("officials", s)
        except Exception:
            continue
        box = data.fetch("team_box", s)
        f = box.groupby("game_id").agg(fouls=("fouls", "sum"), pts=("team_score", "sum"))
        o = o[["game_id", "official_display_name"]].rename(columns={"official_display_name": "official"})
        parts.append(o.merge(f, left_on="game_id", right_index=True).assign(season=s))
    return pd.concat(parts, ignore_index=True)


def referees(b: pd.DataFrame, og: pd.DataFrame | None = None) -> pd.DataFrame:
    """Crew tendencies for each game in b (needs game_id, date, season, pred_total, home_pts, away_pts):
    ref_fouls (fouls per game above the season average) and ref_pts (points above our ratings model's total),
    each official shrunk toward 0 and averaged over the crew, from his earlier games only."""
    og = official_games(sorted(b["season"].unique())) if og is None else og
    g = b[["game_id", "date", "season", "pred_total", "home_pts", "away_pts"]].copy()
    og = og.merge(g, on=["game_id", "season"], how="inner")
    og = og.sort_values(["date", "game_id"])
    # foul baseline: average fouls per game in this season's earlier games (no look-ahead); last season's before that
    per_game = og.drop_duplicates("game_id")[["game_id", "season", "date", "fouls"]]
    day_avg = per_game.groupby(["season", "date"])["fouls"].agg(["sum", "count"]).groupby(level=0).cumsum().groupby(level=0).shift()
    base = (day_avg["sum"] / day_avg["count"]).rename("foul_base").reset_index()
    prev = per_game.groupby("season")["fouls"].mean().shift()
    og = og.merge(base, on=["season", "date"], how="left")
    og["foul_base"] = og["foul_base"].fillna(og["season"].map(prev)).fillna(per_game["fouls"].mean())
    og["foul_dev"] = og["fouls"] - og["foul_base"]
    og["pts_dev"] = og["pts"] - og["pred_total"]
    # running sums per official, excluding the current date (games the same day aren't known yet)
    out = []
    sums: dict = {}
    for day, d in og.groupby("date", sort=True):
        f, p = [], []
        for name in d["official"]:
            s_ = sums.get(name, (0.0, 0.0, 0))
            f.append(s_[0] / (s_[2] + REF_PRIOR))
            p.append(s_[1] / (s_[2] + REF_PRIOR))
        out.append(d[["game_id"]].assign(of=f, op=p))
        for name, fd, pdv in zip(d["official"], d["foul_dev"], d["pts_dev"]):
            s_ = sums.get(name, (0.0, 0.0, 0))
            sums[name] = (s_[0] + fd, s_[1] + (pdv if pdv == pdv else 0.0), s_[2] + 1)
    r = pd.concat(out).groupby("game_id").agg(ref_fouls=("of", "mean"), ref_pts=("op", "mean")).reset_index()
    return r


def crew_tendencies(og: pd.DataFrame, b_hist: pd.DataFrame) -> pd.DataFrame:
    """Every official's shrunk tendency from all history (for live games): official, ref_fouls, ref_pts."""
    g = b_hist[["game_id", "season", "pred_total"]]
    og = og.merge(g, on=["game_id", "season"], how="inner")
    og["foul_dev"] = og["fouls"] - og.groupby("season")["fouls"].transform("mean")
    og["pts_dev"] = og["pts"] - og["pred_total"]
    a = og.groupby("official").agg(f=("foul_dev", "sum"), p=("pts_dev", "sum"), n=("game_id", "size"))
    return pd.DataFrame({"official": a.index, "ref_fouls": a["f"] / (a["n"] + REF_PRIOR),
                         "ref_pts": a["p"] / (a["n"] + REF_PRIOR)})


# ---------------------------------------------------------------- travel and altitude

def home_states(seasons) -> pd.Series:
    """Each team's home state: the most common venue state of its non-neutral home games."""
    parts = []
    for s in seasons:
        g, _ = data.season_games(s)
        parts.append(g[~g["neutral"]][["home_id", "venue_state"]])
    h = pd.concat(parts).dropna()
    return h.groupby("home_id")["venue_state"].agg(lambda x: x.mode().iloc[0])


def travel(b: pd.DataFrame, states: pd.Series) -> pd.DataFrame:
    """game_id, away_tz (time zones the visitor crossed to the venue), home_tz (same for the home team, 0 unless
    neutral), altitude (1 if the home team plays at altitude at home and the visitor doesn't)."""
    venue_state = b["venue_state"].where(b["venue_state"].notna(), b["home_id"].map(states))
    vt = venue_state.map(_tz)
    at = b["away_id"].map(states).map(_tz)
    ht = b["home_id"].map(states).map(_tz)
    return pd.DataFrame({
        "game_id": b["game_id"],
        "away_tz": (vt - at).abs().fillna(0),
        "home_tz": (vt - ht).abs().fillna(0),
        "altitude": (b["home_id"].isin(ALTITUDE) & ~b["away_id"].isin(ALTITUDE) & ~b["neutral"].astype(bool)).astype(float),
    })


# ---------------------------------------------------------------- live

SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event={}"


def live_officials(game_ids) -> pd.DataFrame:
    """game_id, official for today's games, from ESPN's game pages (usually posted close to tip; often empty for
    games further out)."""
    import json
    import urllib.request
    from concurrent.futures import ThreadPoolExecutor

    def one(gid):
        try:
            req = urllib.request.Request(SUMMARY.format(gid), headers={"User-Agent": "cbb-model"})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
            return [(int(gid), o.get("displayName")) for o in (d.get("gameInfo") or {}).get("officials") or []]
        except Exception:
            return []
    with ThreadPoolExecutor(8) as ex:
        rows = [r for rs in ex.map(one, list(game_ids)) for r in rs]
    return pd.DataFrame(rows, columns=["game_id", "official"])


def live_referees(game_ids, table_path: str) -> pd.DataFrame:
    """Crew averages for today's games from the saved table (projection.fit writes data/referees.csv). Officials
    with no history count as 0; games with no crew posted are left out (treated as an average crew)."""
    off = live_officials(game_ids)
    if not len(off) or not os.path.exists(table_path):
        return pd.DataFrame(columns=["game_id", "ref_fouls", "ref_pts", "crew"])
    t = pd.read_csv(table_path)
    off = off.merge(t, on="official", how="left").fillna({"ref_fouls": 0.0, "ref_pts": 0.0})
    return off.groupby("game_id").agg(ref_fouls=("ref_fouls", "mean"), ref_pts=("ref_pts", "mean"),
                                      crew=("official", lambda x: ", ".join(x))).reset_index()


def live_closes(closing_csv: str, games: pd.DataFrame) -> pd.DataFrame:
    """This season's closing lines from lines/closing.csv (last pregame number at each book), consensus per game,
    with season/date/neutral from the schedule (games: home_id, away_id, date, neutral, season)."""
    if not os.path.exists(closing_csv):
        return pd.DataFrame(columns=["season", "date", "home_id", "away_id", "neutral", "close_margin", "close_total"])
    c = pd.read_csv(closing_csv)
    c["date"] = pd.to_datetime(c["date"])
    c = c.groupby(["date", "home_id", "away_id"]).agg(hs=("home_spread", "median"), close_total=("total", "median")).reset_index()
    c["close_margin"] = -c["hs"]
    g = games[["date", "home_id", "away_id", "neutral", "season"]].drop_duplicates()
    c = c.merge(g, on=["date", "home_id", "away_id"], how="inner")
    return c[["season", "date", "home_id", "away_id", "neutral", "close_margin", "close_total"]]
