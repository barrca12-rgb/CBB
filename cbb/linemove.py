"""Line-move research cell (opener rule, Nov 2; protocol v2.4). Display and reads only: never feeds the card's picks.

research/linemove/signals.csv holds every signal the opener rule stopped since it went live (run_day.log_linemove):
one row per game, market, side and bet type, at the number and price it would have been bet at. This grades them
like the bet log (final scores from the card's own reports/cbb_<date>.csv, 1 unit for v1 and 0.5 for band B at the
recorded price) and gives each a close: the median across books of closing.csv's last pregame number (the bet log's
primary close needs the quote log's watch windows, which only cover games with a logged bet), labeled as such.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from . import run_day, tracker

ROOT = os.path.join(os.path.dirname(__file__), "..")
REPORTS = os.path.join(ROOT, "reports")
CLOSING = os.path.join(ROOT, "lines", "closing.csv")


def _final(date: str, game_id, home_id=None) -> tuple | None:
    p = os.path.join(REPORTS, f"cbb_{date}.csv")
    if not os.path.exists(p):
        return None
    c = pd.read_csv(p, usecols=lambda k: k in ("game_id", "state", "home_id", "home_score", "away_score"))
    r = c[c["game_id"].astype(str) == str(game_id)]
    if not len(r) or r["state"].iloc[0] != "post" or pd.isna(r["home_score"].iloc[0]):
        return None
    hs, as_ = float(r["home_score"].iloc[0]), float(r["away_score"].iloc[0])
    # from the signal's own home team: a card that has since relisted the game the other way round is swapped (Nov 2)
    if home_id is not None and "home_id" in r and pd.notna(r["home_id"].iloc[0]) and int(r["home_id"].iloc[0]) != int(home_id):
        hs, as_ = as_, hs
    return hs, as_


def graded(path: str | None = None) -> pd.DataFrame:
    """The research signals with result (W/L/P), stake, profit, status (open/settled), close_line and clv_pts."""
    path = path or run_day.LINEMOVE_SIGNALS
    if not os.path.exists(path):
        return pd.DataFrame(columns=run_day.LINEMOVE_COLS + ["result", "stake", "profit", "status", "close_line", "clv_pts"])
    s = pd.read_csv(path)
    cl = pd.read_csv(CLOSING) if os.path.exists(CLOSING) else pd.DataFrame()
    rows = []
    for _, r in s.iterrows():
        d = r.to_dict()
        d["stake"] = tracker.BAND_B_STAKE if r["bet_type"] == "bandB" else 1.0
        fin = _final(str(r["date"]), r["game_id"], r.get("home_id"))
        line, side, mk = float(r["line"]), str(r["side"]), r["market"]
        # close: median of each book's last pregame number for the game (closing.csv), oriented to our side
        close = np.nan
        if len(cl):
            g = cl[(cl["date"].astype(str) == str(r["date"]))
                   & (((cl["home_id"] == r["home_id"]) & (cl["away_id"] == r["away_id"]))
                      | ((cl["home_id"] == r["away_id"]) & (cl["away_id"] == r["home_id"])))]
            if len(g):
                if mk == "spread":
                    hs = np.where(g["home_id"] == r["home_id"], g["home_spread"], -g["home_spread"])
                    v = pd.Series(hs).dropna()
                    close = float(v.median() * (1 if side == "home" else -1)) if len(v) else np.nan
                else:
                    v = g["total"].dropna()
                    close = float(v.median()) if len(v) else np.nan
        d["close_line"] = close
        if pd.notna(close):
            d["clv_pts"] = (line - close) if (mk == "spread" or side == "under") else (close - line)
        else:
            d["clv_pts"] = np.nan
        if fin is None:
            d.update(result=None, profit=np.nan, status="open")
        else:
            hs_, as_ = fin
            if mk == "spread":
                m = (hs_ - as_) if side == "home" else (as_ - hs_)
                cover = m + line
            else:
                pts = hs_ + as_
                cover = (pts - line) if side == "over" else (line - pts)
            res = "W" if cover > 0 else "L" if cover < 0 else "P"
            pay = tracker.payout(r["price"])
            d.update(result=res, profit=d["stake"] * (pay if res == "W" else -1.0 if res == "L" else 0.0), status="settled")
        rows.append(d)
    return pd.DataFrame(rows)


def summary(g: pd.DataFrame) -> dict:
    """The same fields as record_page.summary, for the research cell (close from closing.csv, see the module note)."""
    s = g[g["status"] == "settled"] if len(g) else g
    w, l, p = int((s["result"] == "W").sum()), int((s["result"] == "L").sum()), int((s["result"] == "P").sum())
    staked = float(s["stake"].sum()) if len(s) else 0.0
    units = float(s["profit"].sum()) if len(s) else 0.0
    d = s[s["result"].isin(["W", "L"])].dropna(subset=["clv_pts"]) if len(s) else s
    clv = float(d["clv_pts"].mean()) if len(d) else None
    beat = float((d["clv_pts"] > 0).mean()) if len(d) else None
    dec = int(s["result"].isin(["W", "L"]).sum()) if len(s) else 0
    return {"bets": int(len(s)), "rec": f"{w}-{l}" + (f"-{p}" if p else ""), "win": w / (w + l) if w + l else None,
            "units": units, "roi": units / staked if staked else None, "clv": clv, "beat": beat,
            "cov": f"{len(d)}/{dec}" if dec else "–"}
