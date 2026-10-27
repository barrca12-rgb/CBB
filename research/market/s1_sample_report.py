"""Step 1 report on the Option B sample (research/market/data/): coverage, books and prices, observed cadence,
when each book's first quote appears relative to tip, opener prices, how long an opening number lasts, and the
frozen model's opener picks on these dates at real first quotes.

    python -m research.market.s1_sample_report   -> research/market/out/s1_*.csv, printed summary
"""
from __future__ import annotations

import glob
import json
import os

import numpy as np
import pandas as pd

from cbb import odds_api, teams

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "out")
ROOT = os.path.join(HERE, "..", "..")
POWER = {"ACC", "B10", "B12", "BE", "SEC", "P12"}
FOUR = {"draftkings": "DraftKings", "fanduel": "FanDuel", "betmgm": "BetMGM", "williamhill_us": "Caesars"}


def lookup() -> dict:
    """The live card's Odds API name lookup plus research/market/oddsapi_aliases.csv (research only: the live
    alias file is frozen). Two schools there (Hartford, St. Francis Brooklyn) left Division I in 2023."""
    lk = odds_api._lookup()
    a = pd.read_csv(os.path.join(HERE, "oddsapi_aliases.csv"))
    lk.update({teams.norm(n): int(i) for n, i in zip(a["oddsapi_name"], a["espn_id"])})
    return lk


def load(date: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    q = pd.read_csv(os.path.join(DATA, f"quotes_{date}.csv.gz"))
    s = pd.read_csv(os.path.join(DATA, f"snapshots_{date}.csv"))
    for c in ("snapshot", "commence_time", "last_update"):
        if c in q:
            q[c] = pd.to_datetime(q[c], utc=True, errors="coerce", format="ISO8601")
    s["snapshot"] = pd.to_datetime(s["snapshot"], utc=True, errors="coerce", format="ISO8601")
    return q, s


def schedule(date: str, season: int) -> pd.DataFrame:
    d = pd.read_parquet(os.path.join(ROOT, "cbb", "cache", f"mbb_schedule_{season}.parquet"))
    d = d[~d["status_type_name"].isin(["STATUS_POSTPONED", "STATUS_CANCELED"])]
    t = pd.to_datetime(d["date"], utc=True)
    d = d.assign(tip=t, day=t.dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d"))
    d = d[d["day"] == date]
    return d[["game_id", "tip", "home_id", "away_id"]].astype({"home_id": int, "away_id": int})


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    plan = json.load(open(os.path.join(HERE, "sample_plan.json")))
    lk = lookup()
    conf = teams.load().drop_duplicates("espn_id").set_index("espn_id")["kenpom_conf"]
    w = pd.read_pickle(os.path.join(ROOT, "audit", "out", "wf_live_approx.pkl"))[["game_id", "final_margin", "final_total", "home_pts", "away_pts"]]
    per_date, firsts, picks = [], [], []
    for d in plan["dates"]:
        if not os.path.exists(os.path.join(DATA, f"snapshots_{d['date']}.csv")):
            continue
        q, s = load(d["date"])
        sch = schedule(d["date"], d["season"])
        q["h"] = q["home_team"].map(lambda n: lk.get(teams.norm(n or "")))
        q["a"] = q["away_team"].map(lambda n: lk.get(teams.norm(n or "")))
        ev = q.dropna(subset=["h", "a"]).drop_duplicates("event_id")[["event_id", "h", "a", "commence_time"]]
        ev[["h", "a"]] = ev[["h", "a"]].astype(int)
        m1 = sch.merge(ev, left_on=["home_id", "away_id"], right_on=["h", "a"])
        m2 = sch.merge(ev, left_on=["home_id", "away_id"], right_on=["a", "h"])       # listed the other way round
        m = pd.concat([m1.assign(flip=False), m2.assign(flip=True)]).drop_duplicates("game_id")
        low = ~sch["home_id"].map(conf).isin(POWER) & ~sch["away_id"].map(conf).isin(POWER)
        gap = s["snapshot"].sort_values().diff().dt.total_seconds().div(60)
        books = sorted(q["book"].unique())
        pr = q[q["status"] != "absent"]
        # first quote per game, book and market: the "new" row's snapshot time vs tip
        f = pr[pr["status"] == "new"].merge(m[["event_id", "game_id", "tip", "flip"]], on="event_id")
        f = f.sort_values("snapshot").drop_duplicates(["game_id", "book", "market", "outcome"])
        f["hours_before_tip"] = (f["tip"] - f["snapshot"]).dt.total_seconds() / 3600
        firsts.append(f.assign(date=d["date"], season=d["season"]))
        per_date.append({
            "date": d["date"], "season": d["season"], "cadence planned": d["cadence"],
            "snapshots served": int(s["snapshot"].nunique()), "median gap min": float(gap.median()),
            "credits used": int(s["cost"].sum()), "ESPN games": len(sch), "games with any quote": int(m["game_id"].nunique()),
            "coverage": m["game_id"].nunique() / max(len(sch), 1),
            "low-major games": int(low.sum()), "low-major with any quote": int(sch.loc[low, "game_id"].isin(m["game_id"]).sum()),
            "books": ", ".join(books),
            **{f"{v} games": int(f.loc[f["book"] == k, "game_id"].nunique()) for k, v in FOUR.items()},
            "share of quotes priced": float(pr["price"].notna().mean()),
            "median first quote, hours before tip": float(f.groupby("game_id")["hours_before_tip"].max().median()) if len(f) else np.nan,
        })
        # the frozen model's opener picks at each of the four books' first spread/total quotes
        g = f[f["book"].isin(FOUR)].merge(w, on="game_id", how="left")
        for _, r in g.iterrows():
            if r["market"] == "spreads":
                side_home = (r["outcome"] == r["home_team"]) != r["flip"]       # outcome is the ESPN home team
                line = r["point"]
                model_for_side = r["final_margin"] if side_home else -r["final_margin"]
                edge = model_for_side + line
                if edge >= 2.5:
                    res = (r["home_pts"] - r["away_pts"]) * (1 if side_home else -1) + line
                    picks.append({"date": d["date"], "game_id": r["game_id"], "book": FOUR[r["book"]], "market": "spread",
                                  "line": line, "price": r["price"], "edge": edge, "hours_before_tip": r["hours_before_tip"],
                                  "res": "W" if res > 0 else ("L" if res < 0 else "P")})
            elif r["market"] == "totals":
                over = str(r["outcome"]).lower() == "over"
                edge = (r["final_total"] - r["point"]) * (1 if over else -1)
                if edge >= 3:
                    tot = r["home_pts"] + r["away_pts"]
                    res = (tot - r["point"]) * (1 if over else -1)
                    picks.append({"date": d["date"], "game_id": r["game_id"], "book": FOUR[r["book"]], "market": "total",
                                  "line": r["point"], "price": r["price"], "edge": edge, "hours_before_tip": r["hours_before_tip"],
                                  "res": "W" if res > 0 else ("L" if res < 0 else "P")})
        print(d["date"], "done", flush=True)
    t = pd.DataFrame(per_date)
    fa = pd.concat(firsts) if firsts else pd.DataFrame()
    pk = pd.DataFrame(picks)
    t.to_csv(os.path.join(OUT, "s1_coverage.csv"), index=False)
    fa.to_csv(os.path.join(OUT, "s1_first_quotes.csv.gz"), index=False, compression={"method": "gzip", "mtime": 0})
    pk.to_csv(os.path.join(OUT, "s1_picks_at_first_quote.csv"), index=False)
    pd.set_option("display.width", 250)
    print(t.drop(columns=["books"]).round(2).to_string(index=False))
    print("\nbooks seen:", sorted(set(", ".join(t["books"]).split(", "))))
    if len(fa):
        fb = fa[fa["book"].isin(FOUR)].groupby(["game_id", "book"])["hours_before_tip"].max().reset_index()
        fb["book"] = fb["book"].map(FOUR)
        print("\nfirst quote per game and book, hours before tip (quartiles):")
        print(fb.groupby("book")["hours_before_tip"].describe(percentiles=[.25, .5, .75])[["count", "25%", "50%", "75%"]].round(1).to_string())
        sp = fa[(fa["market"] == "spreads") & fa["book"].isin(FOUR)]
        print("\nopening spread prices at the four books (share):")
        print(sp["price"].value_counts(normalize=True).head(8).round(3).to_string())
    if len(pk):
        pk["u"] = np.where(pk["res"] == "W", np.where(pk["price"] > 0, pk["price"] / 100, 100 / -pk["price"]),
                           np.where(pk["res"] == "L", -1.0, 0.0))
        print("\nmodel picks at the books' first quotes (all four books counted separately):")
        print(pk.groupby(["market", "book"]).agg(picks=("res", "size"), win=("res", lambda x: (x == "W").sum() / max((x != "P").sum(), 1)),
                                                 roi=("u", "mean"), median_price=("price", "median")).round(3).to_string())


if __name__ == "__main__":
    main()
