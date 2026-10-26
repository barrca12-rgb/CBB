"""Live injury report (ESPN's league-wide college basketball injuries feed), turned into expected missing minutes.

    site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/injuries

Each listed player counts as P(miss) x his share of the team's minutes this season (last season's share on the same
team before he has 3 games). Only players who played in the team's last game are added: anyone who sat out that
game is already in players.py's missing-minutes measure, which the projection weights at about -6 points of margin
per 1.0 of minutes missing (backtest coefficient).

P(miss) by status is a starting guess (no college history to fit it yet). Every pull is appended to
injuries/log.csv, so after a few weeks the guesses can be checked against who actually played.

The size of the effect is conservative: the -6 weight was learned from "missed the last game", which includes
players who come right back, so a confirmed absence is probably worth more (a star at 17% of minutes moves the
projection about 1 point; the market often moves 2-4). Calibrate once a season of logs and CLV exists.

The report comes from injury_sources.py, which pulls ESPN, RotoWire, Covers, CBS and Action Network every run and,
after 1-2 weeks of games, picks the one that reports injuries before the line moves most often. ESPN until then.
"""
from __future__ import annotations

import os

import pandas as pd

from . import data

LOG = os.path.join(os.path.dirname(__file__), "..", "injuries", "log.csv")
P_MISS = {"out": 1.0, "doubtful": 0.75, "questionable": 0.4, "day-to-day": 0.35, "probable": 0.1}


def fetch() -> pd.DataFrame:
    """Current report: team_id, athlete_id, player, status, p_miss, date, comment. ESPN's is logged to
    injuries/log.csv every run. The model uses the source in injuries/sources/choice.json (injury_sources.py picks the
    fastest after 1-2 weeks of games; ESPN until then), falling back to ESPN if that source fails this run."""
    from . import injury_sources
    esp = injury_sources.report("espn")
    inj = _model_rows(esp)
    if len(inj):
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        log = inj.assign(pulled_at=pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"))
        if os.path.exists(LOG):
            old = pd.read_csv(LOG)
            key = lambda x: x["athlete_id"].astype(str) + "|" + x["status"].astype(str) + "|" + x["date"].astype(str)
            log = pd.concat([old, log[~key(log).isin(set(key(old)))]], ignore_index=True)
        log.to_csv(LOG, index=False)
    src = injury_sources.choice()
    if src != "espn":
        alt = injury_sources.report(src)
        if alt is not None and (len(alt) or esp is None or not len(esp)):   # empty while ESPN isn't: broken parser
            return _model_rows(alt, normalized=True)
        print(f"Injury source {src} failed this run; using ESPN.")
    if esp is None:
        raise RuntimeError("ESPN injury feed unavailable")
    return inj


def _model_rows(df: pd.DataFrame | None, normalized: bool = False) -> pd.DataFrame:
    """injury_sources' report -> the model's columns. ESPN keeps its own status words (as logged since October);
    other outlets use the normalized status, which uses the same P_MISS keys."""
    cols = ["team_id", "athlete_id", "player", "status", "p_miss", "date", "comment"]
    if df is None or not len(df):
        return pd.DataFrame(columns=cols)
    d = df[df["team_id"].notna()].copy()
    d["status"] = d["status"].str.title() if normalized else d["status_raw"].astype(str)
    d["p_miss"] = d["status"].str.lower().map(P_MISS).fillna(0.5)
    d = d.assign(team_id=d["team_id"].astype(int), athlete_id=pd.to_numeric(d["athlete_id"], errors="coerce"),
                 date=d["source_date"], comment=d["comment"].fillna(""))
    return d[cols].reset_index(drop=True)


_SHARES: dict[int, pd.DataFrame] = {}


def shares(season: int) -> pd.DataFrame:
    """Each player's share of his team's minutes (this season, else last season on the same team) and whether he
    played in the team's most recent game: team_id, athlete_id, share, played_last. Computed once per run."""
    if season not in _SHARES:
        _SHARES[season] = _shares(season)
    return _SHARES[season]


def _shares(season: int) -> pd.DataFrame:
    out = []
    for s, current in ((season, True), (season - 1, False)):
        try:
            p = data.fetch("player_box", s, refresh=current)
        except Exception:
            continue
        p = p[p["athlete_id"].notna()].copy()
        p["min"] = pd.to_numeric(p["minutes"], errors="coerce").fillna(0)
        p = p[p["min"] > 0]
        tot = p.groupby("team_id")["min"].transform("sum")
        g = p.assign(sh=p["min"] / tot).groupby(["team_id", "athlete_id"]).agg(share=("sh", "sum"), games=("game_id", "nunique"))
        last = p[p["game_date"] == p.groupby("team_id")["game_date"].transform("max")]
        g["played_last"] = g.index.isin(pd.MultiIndex.from_frame(last[["team_id", "athlete_id"]])) if current else True
        g["current"] = current
        out.append(g.reset_index())
    if not out:
        return pd.DataFrame(columns=["team_id", "athlete_id", "share", "played_last"])
    sh = pd.concat(out)
    cur = sh[sh["current"] & (sh["games"] >= 3)]
    prev = sh[~sh["current"]]
    prev = prev[~prev.set_index(["team_id", "athlete_id"]).index.isin(cur.set_index(["team_id", "athlete_id"]).index)]
    # last season's share only for teams that haven't played 3 games yet this season
    started = set(cur["team_id"])
    prev = prev[~prev["team_id"].isin(started)]
    return pd.concat([cur, prev])[["team_id", "athlete_id", "share", "played_last"]]


def adjustment(season: int, inj: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(per team: extra expected missing minutes share, per player: who's listed and what he's worth).

    extra counts only players who played the team's last game (or, before a team's 3rd game, anyone listed)."""
    inj = fetch() if inj is None else inj
    if not len(inj):
        return pd.DataFrame(columns=["team_id", "injury_missing"]), inj.assign(share=[])
    sh = shares(season)
    j = inj.merge(sh, on=["team_id", "athlete_id"], how="left")
    j["share"] = j["share"].fillna(0.0)
    j["played_last"] = j["played_last"].fillna(True).astype(bool)
    j["expected"] = j["p_miss"] * j["share"] * j["played_last"]
    team = j.groupby("team_id")["expected"].sum().rename("injury_missing").reset_index()
    return team, j


def notes(players: pd.DataFrame, pts_per_share: float = 0.0) -> dict:
    """team_id -> "Name (Out, 24% of minutes, -1.5 pts); ..." for the card, biggest first. pts_per_share: the
    projection's margin weight on missing minutes, so each note shows what the player moves the projection."""
    if not len(players):
        return {}
    p = players[players["share"] > 0.02].sort_values("share", ascending=False)
    def one(r):
        pts = f", {-pts_per_share * r.expected:+.1f} pts" if pts_per_share and r.expected else ""
        return f"{r.player} ({r.status}, {r.share:.0%} of minutes{pts})"
    return {int(t): "; ".join(one(r) for r in g.itertuples()) for t, g in p.groupby("team_id")}
