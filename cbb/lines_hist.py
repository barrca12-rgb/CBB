"""Historical pregame spreads and totals from ESPN's odds feed, for the backtest.

sports.core.api.espn.com keeps, per game, the last pregame line from every book it tracked. Coverage from a
40-game sample per season:

    2012        none
    2013-2018   about 70% of games (2014-2017 include Pinnacle and an "Opening" line)
    2019-2024   about 100%, 8-13 books per game
    2024-2026   about 100%, with opening and closing lines (one book: ESPN BET, then DraftKings)

    python -m cbb.lines_hist --start 2013 --end 2026      # writes data/lines/espn_<season>.csv

`consensus()` keeps real sportsbooks only (see NOT_BOOKS), which leaves nothing for 2013.

One row per (game, book): home_spread and total (closing, sportsbook convention: -3 = home favored by 3),
home_ml/away_ml, and open_home_spread/open_total where ESPN has the opener. Games with no line get one row
with an empty book so reruns skip them. In-game ("Live Odds") feeds are dropped.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from . import data

URL = ("https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/"
       "events/{0}/competitions/{0}/odds?limit=100")
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "lines")
# Projection sites and aggregates, not sportsbooks. numberfire stores 0 for a missing line, and teamrankings tracks
# results more closely than any book (likely updated after the close), so neither is a usable closing line. 2013
# has only these, so the betting backtest starts in 2014.
# Projection services and internal feeds that ESPN lists like books. accuscore alone has ~5,400 games a season from
# 2019 and moved the median closing line by half a point or more in up to 2.6% of games.
NOT_BOOKS = {"consensus", "numberfire", "teamrankings", "accuscore", "Fantasy911.com", "betegy",
             "Sportradar Internal Odds(ISE)", "unknown"}
COLS = ["game_id", "book", "home_spread", "total", "home_ml", "away_ml", "open_home_spread", "open_total"]


def _num(x):
    try:
        v = float(str(x).replace("+", ""))
    except (TypeError, ValueError):
        return np.nan
    return v


def _american(side: dict, when: str, field: str):
    return _num(((side.get(when) or {}).get(field) or {}).get("american"))


def game_lines(game_id: int) -> list[dict]:
    for attempt in range(4):
        try:
            req = urllib.request.Request(URL.format(game_id), headers={"User-Agent": "cbb-model"})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
            break
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    rows = []
    for p in d.get("items") or []:
        book = (p.get("provider") or {}).get("name", "")
        if "live" in book.lower():
            continue
        h, a = p.get("homeTeamOdds") or {}, p.get("awayTeamOdds") or {}
        close_sp = _american(h, "close", "pointSpread")
        close_tot = _num(((p.get("close") or {}).get("total") or {}).get("american"))
        r = {
            "game_id": game_id, "book": book,
            "home_spread": close_sp if close_sp == close_sp else _num(p.get("spread")),
            "total": close_tot if close_tot == close_tot else _num(p.get("overUnder")),
            "home_ml": _num(h.get("moneyLine")) or np.nan,
            "away_ml": _num(a.get("moneyLine")) or np.nan,
            "open_home_spread": _american(h, "open", "pointSpread"),
            "open_total": _num(((p.get("open") or {}).get("total") or {}).get("american")),
        }
        if r["home_spread"] == r["home_spread"] or r["total"] == r["total"]:
            rows.append(r)
    return rows or [{"game_id": game_id, "book": ""}]


def season_lines(season: int, workers: int = 8) -> pd.DataFrame:
    path = os.path.join(OUT, f"espn_{season}.csv")
    done = pd.read_csv(path) if os.path.exists(path) else pd.DataFrame(columns=COLS)
    g, _ = data.season_games(season)
    todo = sorted(set(g["game_id"]) - set(done["game_id"]))
    if todo:
        with ThreadPoolExecutor(workers) as ex:
            new = [r for rows in ex.map(game_lines, todo) for r in rows]
        done = pd.concat([done, pd.DataFrame(new, columns=COLS)], ignore_index=True)
        os.makedirs(OUT, exist_ok=True)
        done.sort_values(["game_id", "book"]).to_csv(path, index=False)
    return done


def orient_openers(lines: pd.DataFrame, meta: pd.DataFrame | None, mode: str = "flip") -> tuple[pd.DataFrame, dict]:
    """Check each opening spread against the moneylines recorded with it, never against the close. 2024-26: the
    opening record's own moneylines (audit/b8_open_meta.py, `meta`); 2014-17: the "Opening" pseudo-book row's own
    moneylines. The opening favourite is the side with the shorter moneyline. An opener favouring the other team is
    mis-oriented: mode "flip" corrects its sign, "drop" removes it. Openers that cannot be checked (no moneylines,
    equal moneylines, or a spread within 1 point, where a small disagreement can be genuine) are the residue: kept,
    or removed with mode "drop_residue". Returns (lines, counts)."""
    l = lines.copy()
    if meta is not None and len(meta):
        m = meta.drop_duplicates(["game_id", "book"]).set_index(["game_id", "book"])[["open_home_ml", "open_away_ml"]]
        key = pd.MultiIndex.from_frame(l[["game_id", "book"]])
        hml, aml = m["open_home_ml"].reindex(key).to_numpy(), m["open_away_ml"].reindex(key).to_numpy()
    else:
        hml, aml = np.full(len(l), np.nan), np.full(len(l), np.nan)
    op = (l["book"] == "Opening").to_numpy()
    hml = np.where(op, l["home_ml"], hml)
    aml = np.where(op, l["away_ml"], aml)
    hml = np.where(hml == 0, np.nan, hml)
    aml = np.where(aml == 0, np.nan, aml)
    col = np.where(op, "home_spread", "open_home_spread")
    o = np.where(op, l["home_spread"], l["open_home_spread"]).astype(float)
    has = ~np.isnan(o) & (op | l["book"].fillna("").ne("").to_numpy())
    # implied win chance from each American price; the favourite is the side with the higher one
    imp = lambda x: np.where(x < 0, -x / (100 - np.minimum(x, 0)), 100 / (np.maximum(x, 0) + 100))
    fav = np.sign(imp(hml) - imp(aml))                     # +1 home favourite, -1 away, 0 even, nan unknown
    spread_fav = -np.sign(o)                               # home spread < 0: home favoured
    checkable = has & ~np.isnan(fav) & (fav != 0) & (np.abs(o) > 1)
    wrong = checkable & (spread_fav != fav)
    residue = has & ~checkable
    counts = {"openers": int(has.sum()), "checked": int(checkable.sum()), "mis-oriented": int(wrong.sum()),
              "residue (not checkable)": int(residue.sum())}
    for c in ("home_spread", "open_home_spread"):
        sel = wrong & (col == c)
        if mode == "flip":
            l.loc[sel, c] = -l.loc[sel, c]
        else:
            l.loc[sel, c] = np.nan
        if mode == "drop_residue":
            l.loc[residue & (col == c), c] = np.nan
    return l, counts


def consensus(lines: pd.DataFrame, opener_rule: str = "close", open_meta: pd.DataFrame | None = None) -> pd.DataFrame:
    """One closing line per game: the median across books (robust to one stale or off-market book).

    opener_rule "close" (the default, used by the live code through context.py) keeps the original opener cleaning,
    which compares the opener with the later close. "flip", "drop" and "drop_residue" instead orient openers with
    their own moneylines (orient_openers) and use the close for nothing: the historical reporting rule (protocol
    item 7). Closing numbers are the same under every rule."""
    if opener_rule != "close":
        lines, consensus.counts = orient_openers(lines, open_meta, opener_rule)
    l = lines[~lines["book"].fillna("").isin(NOT_BOOKS | {"", "Opening"})].copy()
    l.loc[l["total"] <= 0, "total"] = np.nan
    # Drop a book whose spread is far from the others on the same game (side flipped or stale).
    med = l.groupby("game_id")["home_spread"].transform("median")
    l.loc[(l["home_spread"] - med).abs() > 5, "home_spread"] = np.nan
    agg = l.groupby("game_id").agg(home_spread=("home_spread", "median"), total=("total", "median"),
                                   open_home_spread=("open_home_spread", "median"),
                                   open_total=("open_total", "median"), books=("book", "nunique"))
    # ESPN's "Opening" pseudo-book (2014-2017) fills in openers where no book has one.
    op = lines[lines["book"] == "Opening"].drop_duplicates("game_id").set_index("game_id")
    agg["open_home_spread"] = agg["open_home_spread"].fillna(op["home_spread"])
    agg["open_total"] = agg["open_total"].fillna(op["total"])
    if opener_rule == "close":
        # ESPN sometimes stores the opener from the other team's side (Virginia +4.5 open, -6.5 close). An opener
        # closer to the mirrored close than to the close itself is treated as that error and dropped.
        o, c = agg["open_home_spread"], agg["home_spread"]
        flipped = ((o + c).abs() < (o - c).abs()) & (c.abs() >= 2)
        agg.loc[flipped, "open_home_spread"] = np.nan
    else:
        # drop-only plausibility, from the opener alone: spreads within +-60, totals 100-200
        agg.loc[agg["open_home_spread"].abs() > 60, "open_home_spread"] = np.nan
        agg.loc[~agg["open_total"].between(100, 200), "open_total"] = np.nan
    return agg.reset_index()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2013)
    ap.add_argument("--end", type=int, default=2026)
    a = ap.parse_args()
    for s in range(a.start, a.end + 1):
        c = consensus(season_lines(s))
        print(f"{s}: {c['home_spread'].notna().sum()} games with a spread, {c['open_home_spread'].notna().sum()} "
              f"with an opener", flush=True)


if __name__ == "__main__":
    main()
