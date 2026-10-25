"""Daily bet card: today's slate, the model's numbers, live lines from SportsGameOdds, and the plays.

    python -m cbb.run_day                        # today (US Eastern), live lines
    python -m cbb.run_day --date 2026-11-14      # another day
    python -m cbb.run_day --date 2026-01-17 --replay   # a past day with ESPN's stored closing lines (to check the page)
    python -m cbb.run_day --auto                 # what the scheduled runs use: tomorrow's card after 8pm ET

Writes reports/cbb_<date>.html (the bet card), reports/cbb_<date>.csv (every number), and reports/days.json.

Calls, from the 2024-2026 backtest against opening lines (BACKTEST.md):

    spread  edge 3+ points  BET 1u    (57.5% at the opener)     edge 2-3  SMALL 0.5u (54.9% at 2+)
    total   edge 4+ points  BET 1u    (56.1%)                   edge 3-4  SMALL 0.5u (55.1% at 3+)

The edge held against the opener, not the close, so the card is meant to be acted on early: each play shows the
worst number it's still a play at ("good down to").
"""
from __future__ import annotations

import argparse
import json
import math
import os
import urllib.request

import numpy as np
import pandas as pd

from . import backtest, data, kenpom, odds, players, projection, ratings, report_html, teams

REPORTS = os.path.join(os.path.dirname(__file__), "..", "reports")
SCOREBOARD = ("https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
              "?dates={}&groups=50&limit=500")
SPREAD_CALLS = [(3.0, "BET", 1.0), (2.0, "SMALL", 0.5)]
TOTAL_CALLS = [(4.0, "BET", 1.0), (3.0, "SMALL", 0.5)]
WATCH_BELOW = 1.0      # within this many points of a SMALL: WATCH (becomes a play if the line moves)


def season_of(day: pd.Timestamp) -> int:
    return day.year + 1 if day.month >= 8 else day.year


def today_et() -> pd.Timestamp:
    return pd.Timestamp.now(tz="America/New_York").normalize().tz_localize(None)


def slate(day: pd.Timestamp) -> pd.DataFrame:
    """Every D-I game on `day` from ESPN's scoreboard."""
    req = urllib.request.Request(SCOREBOARD.format(day.strftime("%Y%m%d")), headers={"User-Agent": "cbb-model"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    rows = []
    for ev in d.get("events") or []:
        c = (ev.get("competitions") or [{}])[0]
        side = {t.get("homeAway"): t for t in c.get("competitors") or []}
        if "home" not in side or "away" not in side:
            continue
        st = (ev.get("status") or {}).get("type") or {}
        rows.append({
            "game_id": int(ev["id"]), "start": ev.get("date"), "home_id": int(side["home"]["team"]["id"]),
            "away_id": int(side["away"]["team"]["id"]), "home": side["home"]["team"].get("location"),
            "away": side["away"]["team"].get("location"), "neutral": bool(c.get("neutralSite")),
            "conf_game": bool(c.get("conferenceCompetition")), "state": st.get("state", "pre"),
            "home_score": pd.to_numeric(side["home"].get("score"), errors="coerce"),
            "away_score": pd.to_numeric(side["away"].get("score"), errors="coerce"),
            "note": "; ".join(n.get("headline", "") for n in c.get("notes") or [] if n.get("headline")),
        })
    return pd.DataFrame(rows)


def project(day: pd.Timestamp, games: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Final margin and total for each game, and the ratings table, using only games before `day`."""
    season = season_of(day)
    data.fetch("schedule", season, refresh=day >= today_et() - pd.Timedelta(days=1))
    try:
        hist, tg = data.season_games(season, refresh=day >= today_et() - pd.Timedelta(days=1))
    except Exception:          # season hasn't started: no box scores yet
        hist = pd.DataFrame({"home_pts": [], "away_pts": [], "date": pd.to_datetime([])})
        tg = pd.DataFrame({c: [] for c in ["team_id", "opp_id", "venue", "ppp", "pace"] + ratings.FACTORS}).assign(
            date=pd.to_datetime([]))
    ids = sorted(set(teams.load()["espn_id"]) | set(tg.get("team_id", [])))
    games = games[games["home_id"].isin(ids) & games["away_id"].isin(ids)].copy()
    r = ratings.fit(tg, day, ids, backtest.kenpom_prior(season))
    p = ratings.predict(r, games["home_id"], games["away_id"], games["neutral"])
    p.index = games.index
    b = games.join(p.add_prefix("pred_")).assign(season=season, date=day, games_before=r["games"],
                                                 home_pts=np.nan, away_pts=np.nan)

    # KenPom: FanMatch once it's published for the day, else KenPom's current ratings with the same method.
    kp = None
    try:
        kp = kenpom.fanmatch(day.strftime("%Y-%m-%d")) if day <= today_et() else None
    except Exception:
        kp = None
    if kp is not None and len(kp):
        from .evaluate import fanmatch as fm
        kp = fm(b[["game_id", "date", "home_id", "away_id"]])
    else:
        kp = kenpom.predict_from_ratings(b, season)
    b = b.merge(kp, on="game_id", how="left")

    av = players.next_excess_missing(season) if day >= today_et() - pd.Timedelta(days=1) else None
    if av is not None:   # going-into-next-game availability, attached to today's game for each team
        sides = pd.concat([b[["game_id", c]].rename(columns={c: "team_id"}) for c in ("home_id", "away_id")])
        av = sides.merge(av, on="team_id", how="left").fillna({"excess_missing": 0.0})
    played = hist[(hist["date"] < day)].dropna(subset=["home_pts"]) if len(hist) else hist
    live = {"team_hca": projection.saved_team_hca(), "season": season,
            "season_avg_total": float((played["home_pts"] + played["away_pts"]).mean()) if len(played) >= 200 else None}
    if av is not None:
        live["availability"] = av[["game_id", "team_id", "excess_missing"]]
    f = projection.apply_saved(projection.add_features(b, live))
    return f, ratings.table(r)


def _best(lines: pd.DataFrame, value_fn, line_col: str):
    """Best (book, line, edge) for a side: value_fn(line) = edge at that line."""
    l = lines.dropna(subset=[line_col])
    if not len(l):
        return None
    e = l[line_col].map(value_fn)
    i = e.idxmax()
    return l.loc[i], float(e.loc[i])


def _call(edge: float, calls) -> tuple[str, float]:
    for thr, name, units in calls:
        if edge >= thr:
            return name, units
    if edge >= calls[-1][0] - WATCH_BELOW:
        return "WATCH", 0.0
    return "PASS", 0.0


def plays(f: pd.DataFrame, lines: pd.DataFrame) -> pd.DataFrame:
    """One row per game: the best spread and total play across books."""
    out = []
    for _, g in f.iterrows():
        l = lines[(lines["home_id"] == g["home_id"]) & (lines["away_id"] == g["away_id"])]
        flip = lines[(lines["home_id"] == g["away_id"]) & (lines["away_id"] == g["home_id"])]
        if not len(l) and len(flip):   # book lists the teams the other way round (neutral sites)
            l = flip.rename(columns={"home_spread_odds": "away_spread_odds", "away_spread_odds": "home_spread_odds",
                                     "home_spread_link": "away_spread_link", "away_spread_link": "home_spread_link",
                                     "home_ml": "away_ml", "away_ml": "home_ml"}).assign(
                home_spread=-flip["home_spread"], open_home_spread=-flip.get("open_home_spread", np.nan))
        m, t = g["final_margin"], g["final_total"]
        r = {k: g[k] for k in ["game_id", "start", "home", "away", "home_id", "away_id", "neutral", "state",
                               "home_score", "away_score", "note"] if k in g}
        r.update(model_margin=m, model_total=t, model_home_spread=-m, kp_margin=g.get("kp_margin"),
                 raw_margin=g.get("pred_margin"), home_missing=g.get("home_missing"), away_missing=g.get("away_missing"),
                 p_home_win=0.5 * (1 + math.erf(m / 11.0 / math.sqrt(2))), n_books=l["book"].nunique())
        r["book_lines"] = l.drop(columns=[c for c in ("home_id", "away_id", "sgo_event", "start") if c in l]).to_dict("records")
        if len(l):
            r["line_home_spread"] = float(l["home_spread"].median()) if l["home_spread"].notna().any() else np.nan
            r["line_total"] = float(l["total"].median()) if l["total"].notna().any() else np.nan
            if "open_home_spread" in l:
                r["open_home_spread"] = float(l["open_home_spread"].median()) if l["open_home_spread"].notna().any() else np.nan
            # spread: home edge at line s is m + s; away edge is -(m + s)
            hb, ab = _best(l, lambda s: m + s, "home_spread"), _best(l, lambda s: -(m + s), "home_spread")
            if hb or ab:
                side, (row, edge) = ("home", hb) if (hb and (not ab or hb[1] >= ab[1])) else ("away", ab)
                v, units = _call(edge, SPREAD_CALLS)
                line = row["home_spread"] if side == "home" else -row["home_spread"]
                thr = SPREAD_CALLS[0][0] if v == "BET" else SPREAD_CALLS[-1][0]
                r.update(spread_pick=g["home"] if side == "home" else g["away"], spread_side=side, spread_line=line,
                         spread_book=row["book"], spread_odds=row.get(f"{side}_spread_odds"), spread_edge=edge,
                         spread_link=row.get(f"{side}_spread_link"), spread_verdict=v, spread_units=units,
                         spread_good_to=(thr - m) if side == "home" else (thr + m))
            ob, ub = _best(l, lambda x: t - x, "total"), _best(l, lambda x: x - t, "total")
            if ob or ub:
                side, (row, edge) = ("over", ob) if (ob and (not ub or ob[1] >= ub[1])) else ("under", ub)
                v, units = _call(edge, TOTAL_CALLS)
                thr = TOTAL_CALLS[0][0] if v == "BET" else TOTAL_CALLS[-1][0]
                r.update(total_pick=side.title(), total_line=row["total"], total_book=row["book"],
                         total_odds=row.get(f"{side}_odds"), total_edge=edge, total_link=row.get(f"{side}_link"),
                         total_verdict=v, total_units=units, total_good_to=(t - thr) if side == "over" else (t + thr))
        out.append(r)
    return pd.DataFrame(out)


def replay_lines(day: pd.Timestamp, f: pd.DataFrame) -> pd.DataFrame:
    """ESPN's stored lines for a past day, shaped like odds.pull() (no prices or links), to preview the page."""
    from . import lines_hist
    path = os.path.join(lines_hist.OUT, f"espn_{season_of(day)}.csv")
    l = pd.read_csv(path)
    l = l[l["game_id"].isin(f["game_id"]) & ~l["book"].fillna("").isin(lines_hist.NOT_BOOKS | {"", "Opening"})]
    return l.merge(f[["game_id", "home_id", "away_id"]], on="game_id")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (default: today, US Eastern)")
    ap.add_argument("--replay", action="store_true", help="past day with ESPN's stored lines instead of live ones")
    ap.add_argument("--auto", action="store_true", help="after 8pm ET, build tomorrow's card (openers post overnight)")
    a = ap.parse_args()
    day = pd.Timestamp(a.date) if a.date else today_et()
    if a.auto and not a.date and pd.Timestamp.now(tz="America/New_York").hour >= 20:
        day += pd.Timedelta(days=1)
    games = slate(day)
    if not len(games):
        print(f"No games on {day:%Y-%m-%d}.")
        return
    f, rt = project(day, games)
    if a.replay:
        lines = replay_lines(day, f)
    else:
        try:
            lines = odds.pull()
        except Exception as e:   # no key or SportsGameOdds down: still publish the model's numbers
            print(f"Live lines unavailable ({e}); card has model numbers only.")
            lines = pd.DataFrame(columns=["book", "home_id", "away_id", "home_spread", "total"])
    card = plays(f, lines)
    os.makedirs(REPORTS, exist_ok=True)
    stem = os.path.join(REPORTS, f"cbb_{day:%Y-%m-%d}")
    card.drop(columns=["book_lines"]).to_csv(stem + ".csv", index=False)
    names = teams.load().set_index("espn_id")["espn_location"]
    rt = rt.assign(team=names.reindex(rt.index).to_numpy())
    with open(stem + ".html", "w") as fh:
        fh.write(report_html.build(card, rt, day, season_of(day), replay=a.replay))
    days_path = os.path.join(REPORTS, "days.json")
    days = json.load(open(days_path)) if os.path.exists(days_path) else {"days": []}
    days["days"] = sorted(set(days["days"]) | {f"{day:%Y-%m-%d}"})
    days["current"] = f"{day:%Y-%m-%d}"
    with open(days_path, "w") as fh:
        json.dump(days, fh)
    n = lambda col, v: int((card.get(col) == v).sum()) if col in card else 0
    print(f"{day:%Y-%m-%d}: {len(card)} games, {int((card['n_books'] > 0).sum())} with lines; spreads "
          f"{n('spread_verdict', 'BET')} BET / {n('spread_verdict', 'SMALL')} SMALL, totals "
          f"{n('total_verdict', 'BET')} BET / {n('total_verdict', 'SMALL')} SMALL -> {stem}.html")


if __name__ == "__main__":
    main()
