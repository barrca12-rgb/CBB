"""Daily bet card: today's slate, the model's numbers, live lines from SportsGameOdds, and the plays.

    python -m cbb.run_day                        # today (US Eastern), live lines
    python -m cbb.run_day --date 2026-11-14      # another day
    python -m cbb.run_day --date 2026-01-17 --replay   # a past day with ESPN's stored closing lines (to check the page)
    python -m cbb.run_day --auto                 # what the scheduled runs use: tomorrow's card after 8pm ET

Writes reports/cbb_<date>.html (the bet card), reports/cbb_<date>.csv (every number), and reports/days.json.

Calls, from the 2024-2026 backtest against opening lines (BACKTEST.md):

    spread  edge 3+ points  BET 1u    (58.6% at the opener)     edge 2-3  WATCH
    total   edge 4+ points  BET 1u    (57.5%)                   edge 3-4  WATCH

and at least +2% expected value at the book's price, from the backtest's win rate for that edge (win_prob). The
book is the one with the best expected value (number and price together); an edge that's there but at a bad price
is a WATCH.

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

from . import backtest, context, data, injuries, kenpom, odds, players, projection, ratings, report_html, review, teams, tracker

REPORTS = os.path.join(os.path.dirname(__file__), "..", "reports")
SCOREBOARD = ("https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
              "?dates={}&groups=50&limit=500")
SPREAD_CALLS = [(3.0, "BET", 1.0)]
TOTAL_CALLS = [(4.0, "BET", 1.0)]
WATCH_BELOW = 1.0      # within this many points of a BET: WATCH (becomes a play if the line moves)
# Win chance by edge against the opener, 2014-2017 and 2024-2026 backtest (capped: bigger edges didn't win more):
# spreads 54.7% at 2-3 pts, 58.0% at 3-4, flat after; totals 54.2% at 3-4, 56.8-57.3% at 4-6.
WIN_PROB = {"spread": (0.0255, 0.58), "total": (0.014, 0.565)}
MIN_EV = 0.02          # a play also needs +2% expected value at the book's price (3-pt spread edge: fine to -125)


def win_prob(market: str, edge: float) -> float:
    slope, cap = WIN_PROB[market]
    return float(min(max(0.5 + slope * edge, 0.5), cap))


def ev(p: float, odds) -> float:
    o = -110.0 if odds is None or (isinstance(odds, float) and math.isnan(odds)) else float(odds)
    return p * (o / 100 if o > 0 else 100 / -o) - (1 - p)


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
    last = data.season_games(season - 1)
    r = ratings.fit(tg, day, ids, backtest.kenpom_prior(season), league=ratings.league_averages(last[1]))
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
        # injury report: expected missing minutes for listed players who played the last game (injuries.py)
        try:
            inj_team, inj_players = injuries.adjustment(season)
        except Exception as e:
            print(f"Injury report unavailable ({e}); using last game's lineups only.")
            inj_team, inj_players = pd.DataFrame(columns=["team_id", "injury_missing"]), pd.DataFrame()
        av = av.merge(inj_team, on="team_id", how="left").fillna({"injury_missing": 0.0})
        av["excess_missing"] = av["excess_missing"] + av["injury_missing"]
        im = inj_team.set_index("team_id")["injury_missing"] if len(inj_team) else pd.Series(dtype=float)
        with open(projection.SAVED) as fh:
            miss_w = json.load(fh)["margin"].get("miss_diff", 0.0)   # points per 1.0 of minutes missing (home side)
        nt = injuries.notes(inj_players, abs(miss_w)) if len(inj_players) else {}
        for sd in ("home", "away"):
            b[f"{sd}_injury_missing"] = b[f"{sd}_id"].map(im).fillna(0.0)
            b[f"{sd}_injuries"] = b[f"{sd}_id"].map(nt).fillna("")
    played = hist[(hist["date"] < day)].dropna(subset=["home_pts"]) if len(hist) else hist
    # scoring environment: this season's average total once it has 200 games, before that last season's
    last_avg = float((last[0]["home_pts"] + last[0]["away_pts"]).mean())
    live = {"team_hca": projection.saved_team_hca(), "season": season,
            "season_avg_total": float((played["home_pts"] + played["away_pts"]).mean()) if len(played) >= 200 else last_avg}
    if av is not None:
        live["availability"] = av[["game_id", "team_id", "excess_missing"]]
    # context: market ratings from this season's closing lines, referee crews if posted (context.py)
    keys = b[["game_id", "season", "date", "home_id", "away_id", "neutral"]]
    closes = context.live_closes(os.path.join(odds.LINES, "closing.csv"), hist) if len(hist) else pd.DataFrame()
    ctx = context.market(keys, closes) if len(closes) else keys[["game_id"]].assign(mkt_margin=0.0, mkt_total=0.0, mkt_n=0)
    refs = context.live_referees(b["game_id"], projection.REFEREES) if day >= today_et() - pd.Timedelta(days=1) else \
        pd.DataFrame(columns=["game_id", "ref_fouls", "ref_pts", "crew"])
    live["context"] = ctx.merge(refs[["game_id", "ref_fouls", "ref_pts"]], on="game_id", how="left")
    b = b.merge(refs[["game_id", "crew"]], on="game_id", how="left")
    f = projection.apply_saved(projection.add_features(b, live))
    return f, ratings.table(r)


def _best(lines: pd.DataFrame, market: str, sides: dict):
    """Best (side, book row, edge, win prob, EV) across books and both sides, by expected value at each book's
    price. sides: side -> (line column, edge function of the line, odds column)."""
    best = None
    for side, (col, edge_fn, odds_col) in sides.items():
        for _, row in lines.dropna(subset=[col]).iterrows():
            e = float(edge_fn(row[col]))
            if e <= 0:
                continue
            p = win_prob(market, e)
            v = ev(p, row.get(odds_col))
            if best is None or (v, e) > (best[4], best[2]):
                best = (side, row, e, p, v)
    return best


def _call(edge: float, value: float, calls) -> tuple[str, float]:
    thr, name, units = calls[0]
    if edge >= thr and value >= MIN_EV:
        return name, units
    if edge >= thr - WATCH_BELOW:   # close on the number, or there on the number but not the price
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
                               "home_score", "away_score", "note", "home_injuries", "away_injuries",
                               "home_injury_missing", "away_injury_missing", "crew"] if k in g}
        r.update(model_margin=m, model_total=t, model_home_spread=-m,
                 model_home_pts=(t + m) / 2, model_away_pts=(t - m) / 2, kp_margin=g.get("kp_margin"),
                 raw_margin=g.get("pred_margin"), home_missing=g.get("home_missing"), away_missing=g.get("away_missing"),
                 p_home_win=0.5 * (1 + math.erf(m / 11.0 / math.sqrt(2))), n_books=l["book"].nunique())
        r["book_lines"] = l.drop(columns=[c for c in ("home_id", "away_id", "sgo_event", "start") if c in l]).to_dict("records")
        if len(l):
            r["line_home_spread"] = float(l["home_spread"].median()) if l["home_spread"].notna().any() else np.nan
            r["line_total"] = float(l["total"].median()) if l["total"].notna().any() else np.nan
            if "open_home_spread" in l:
                r["open_home_spread"] = float(l["open_home_spread"].median()) if l["open_home_spread"].notna().any() else np.nan
            # spread: home edge at line s is m + s; away edge is -(m + s)
            sp = _best(l, "spread", {"home": ("home_spread", lambda s_: m + s_, "home_spread_odds"),
                                     "away": ("home_spread", lambda s_: -(m + s_), "away_spread_odds")})
            if sp:
                side, row, edge, p, value = sp
                v, units = _call(edge, value, SPREAD_CALLS)
                line = row["home_spread"] if side == "home" else -row["home_spread"]
                thr = SPREAD_CALLS[0][0]
                r.update(spread_pick=g["home"] if side == "home" else g["away"], spread_side=side, spread_line=line,
                         spread_book=row["book"], spread_odds=row.get(f"{side}_spread_odds"), spread_edge=edge,
                         spread_p=p, spread_ev=value, spread_link=row.get(f"{side}_spread_link"), spread_verdict=v,
                         spread_units=units, spread_good_to=(thr - m) if side == "home" else (thr + m))
            to = _best(l, "total", {"over": ("total", lambda x: t - x, "over_odds"),
                                    "under": ("total", lambda x: x - t, "under_odds")})
            if to:
                side, row, edge, p, value = to
                v, units = _call(edge, value, TOTAL_CALLS)
                thr = TOTAL_CALLS[0][0]
                r.update(total_pick=side.title(), total_line=row["total"], total_book=row["book"],
                         total_odds=row.get(f"{side}_odds"), total_edge=edge, total_p=p, total_ev=value,
                         total_link=row.get(f"{side}_link"), total_verdict=v, total_units=units,
                         total_good_to=(t - thr) if side == "over" else (t + thr))
        out.append(r)
    return pd.DataFrame(out)


def replay_lines(day: pd.Timestamp, f: pd.DataFrame) -> pd.DataFrame:
    """ESPN's stored lines for a past day, shaped like odds.pull() (no prices or links), to preview the page."""
    from . import lines_hist
    path = os.path.join(lines_hist.OUT, f"espn_{season_of(day)}.csv")
    l = pd.read_csv(path)
    l = l[l["game_id"].isin(f["game_id"]) & ~l["book"].fillna("").isin(lines_hist.NOT_BOOKS | {"", "Opening"})].copy()
    # ESPN's names for our books ("Caesars Sportsbook", "DraftKings Sportsbook (NJ)") -> the card's
    for ours in ("FanDuel", "DraftKings", "BetMGM", "Caesars"):
        l.loc[l["book"].str.startswith(ours), "book"] = ours
    l = l[l["book"].isin(odds.BOOKS.values())].drop_duplicates(["game_id", "book"])
    return l.merge(f[["game_id", "home_id", "away_id"]], on="game_id")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (default: today, US Eastern)")
    ap.add_argument("--replay", action="store_true", help="past day with ESPN's stored lines instead of live ones")
    ap.add_argument("--auto", action="store_true", help="after 8pm ET, build tomorrow's card (openers post overnight); "
                    "on a day without games, the next day that has them")
    a = ap.parse_args()
    day = pd.Timestamp(a.date) if a.date else today_et()
    if a.auto and not a.date and pd.Timestamp.now(tz="America/New_York").hour >= 20:
        day += pd.Timedelta(days=1)
    if not (os.environ.get("KENPOM_API_KEY") or os.path.isdir(kenpom.CACHE)):
        raise SystemExit("KENPOM_API_KEY is not set (add it as a repository secret for the scheduled runs).")
    games = slate(day)
    if a.auto and not a.date:   # off day (or preseason): show the next day with games, up to two weeks out
        for _ in range(14):
            if len(games):
                break
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
    record = None
    if not a.replay:
        # grade earlier days, scale stakes by each market's live record, then log today's plays
        try:
            tracker.settle()
        except Exception as e:
            print(f"Settling bets failed ({e}); continuing.")
        st = tracker.status()
        for mk in ("spread", "total"):
            if f"{mk}_units" in card:
                card[f"{mk}_units"] = card[f"{mk}_units"] * st[mk]["multiplier"]
        tracker.log(card, day, {mk: st[mk]["multiplier"] for mk in st})
        try:
            rv = review.summary()
        except Exception as e:
            print(f"Loss review failed ({e}); continuing.")
            rv = {}
        record = {"status": tracker.status(), "recent": tracker.recent(), "review": rv}
    os.makedirs(REPORTS, exist_ok=True)
    stem = os.path.join(REPORTS, f"cbb_{day:%Y-%m-%d}")
    card.drop(columns=["book_lines"]).to_csv(stem + ".csv", index=False)
    names = teams.load().set_index("espn_id")["espn_location"]
    rt = rt.assign(team=names.reindex(rt.index).to_numpy())
    with open(stem + ".html", "w") as fh:
        fh.write(report_html.build(card, rt, day, season_of(day), replay=a.replay, record=record))
    days_path = os.path.join(REPORTS, "days.json")
    days = json.load(open(days_path)) if os.path.exists(days_path) else {"days": []}
    days["days"] = sorted(set(days["days"]) | {f"{day:%Y-%m-%d}"})
    days["current"] = f"{day:%Y-%m-%d}"
    with open(days_path, "w") as fh:
        json.dump(days, fh)
    n = lambda col, v: int((card.get(col) == v).sum()) if col in card else 0
    print(f"{day:%Y-%m-%d}: {len(card)} games, {int((card['n_books'] > 0).sum())} with lines; "
          f"{n('spread_verdict', 'BET')} spread and {n('total_verdict', 'BET')} total plays -> {stem}.html")


if __name__ == "__main__":
    main()
