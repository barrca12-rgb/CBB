"""Two quick news checks for each play, both free:

  news_url    an X (Twitter) live search for either team's injury news, one tap from the alert or the card. Beat
              writers post there first, especially at low majors that the injury sites cover late.
  sharp move  the line moving 1.5+ points against our side in the last hour (median across books, from
              lines/moves.csv). A move like that with nothing on the injury report usually means news we don't
              have yet, so the play is flagged "check news first".
"""
from __future__ import annotations

import os
import urllib.parse

import numpy as np
import pandas as pd

from . import odds, teams

WINDOW = pd.Timedelta(hours=1)
SHARP = 1.5   # points against us within WINDOW


def news_url(home_id: int, away_id: int) -> str:
    names = teams.load().set_index("espn_id")["espn_name"]
    q = " OR ".join(f'"{names.get(int(i), "")}"' for i in (away_id, home_id) if names.get(int(i)))
    q = f"({q}) (injury OR injured OR out OR questionable OR \"will not play\" OR status)"
    return "https://x.com/search?" + urllib.parse.urlencode({"q": q, "f": "live"})


def _moves(card: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    """Per game_key: median change across books over the last WINDOW in spread (from the lower-id team's side) and
    total. A book whose first number came within the window counts from its first number."""
    if not os.path.exists(odds.MOVES):
        return pd.DataFrame(columns=["game_key", "d_spread", "d_total"])
    m = pd.read_csv(odds.MOVES)
    m["pulled_at"] = pd.to_datetime(m["pulled_at"], utc=True, format="ISO8601")
    m = m[m["game_key"].isin(set(odds.game_key(card)))].sort_values("pulled_at")
    rows = []
    for (gk, bk), g in m.groupby(["game_key", "book"]):
        before = g[g["pulled_at"] <= now - WINDOW]
        start = before.iloc[-1] if len(before) else g.iloc[0]
        last = g.iloc[-1]
        rows.append((gk, last["spread"] - start["spread"], last["total"] - start["total"]))
    d = pd.DataFrame(rows, columns=["game_key", "d_spread", "d_total"])
    return d.groupby("game_key").median().reset_index()


def annotate(card: pd.DataFrame, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Add news_url, and spread_warn / total_warn (text, or empty) for plays and watches."""
    if not len(card):
        return card
    now = now or pd.Timestamp.now(tz="UTC")
    card = card.copy()
    card["news_url"] = [news_url(h, a) for h, a in zip(card["home_id"], card["away_id"])]
    card["spread_warn"], card["total_warn"] = "", ""
    mv = _moves(card, now).set_index("game_key")
    for i, g in card.iterrows():
        gk = odds.game_key(card.loc[[i]]).iloc[0]
        if gk not in mv.index:
            continue
        ds, dt = mv.loc[gk, "d_spread"], mv.loc[gk, "d_total"]
        lo = min(int(g["home_id"]), int(g["away_id"]))
        if g.get("spread_verdict") in ("BET", "WATCH") and pd.notna(ds):
            pick = int(g["home_id"]) if g.get("spread_side") == "home" else int(g["away_id"])
            gain = ds if pick == lo else -ds   # + = more points for our team
            if gain <= -SHARP:
                card.loc[i, "spread_warn"] = f"Line moved {-gain:g} pts against us in the last hour: check news first"
        if g.get("total_verdict") in ("BET", "WATCH") and pd.notna(dt):
            against = dt if str(g.get("total_pick")).lower() == "over" else -dt
            if against >= SHARP:
                card.loc[i, "total_warn"] = f"Total moved {against:g} pts against us in the last hour: check news first"
    try:   # team news and the eligibility watchlist (team_news.py); information only, never stops the card
        from . import team_news
        card = team_news.annotate(card, now)
    except Exception as e:
        print(f"Team news failed ({e}); continuing.")
    return card
