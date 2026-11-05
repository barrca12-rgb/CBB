"""Weekly improvement review (CLAUDE.md): live results against the backtests, by segment. Research only.

    python -m research.weekly_review                 # last 7 ET days -> research/weekly/<today>.md
    python -m research.weekly_review --days 14

Reads bets/bets.csv (via cbb.tracker), reports/cbb_<date>.csv, lines/closing.csv and ESPN's free scoreboard for
finals. Calls no paid API. The backtest references are fixed numbers from the reports named beside them.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request

import numpy as np
import pandas as pd

from cbb import tracker

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(os.path.dirname(__file__), "weekly")
ET = "America/New_York"
SEASON_START = "2026-11-01"
# Backtest references (opener plays at -110, research/stake_bands/out/plays.csv and research/early_dogs, 2024-26)
REF = {"spread win %": 56.3, "total win %": 57.5, "favorite win %": 56.2, "underdog win %": 56.4,
       "early favorite win %": 57.9, "early underdog win %": 55.2, "line move (spreads)": 0.95,
       "first-4-days total MAE gap to close": 0.68, "first-4-days margin MAE gap to close": 0.18}
SB = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"


def finals(dates) -> dict:
    out = {}
    for d in dates:
        try:
            req = urllib.request.Request(f"{SB}?dates={d.replace('-', '')}&groups=50&limit=500", headers={"User-Agent": "cbb-model"})
            j = json.load(urllib.request.urlopen(req, timeout=60))
        except Exception:
            continue
        for e in j.get("events", []):
            k = e["competitions"][0]
            if k["status"]["type"]["name"] != "STATUS_FINAL":
                continue
            s = {t["homeAway"]: int(t["score"]) for t in k["competitors"]}
            out[int(e["id"])] = (s["home"], s["away"])
    return out


def closes() -> pd.DataFrame:
    cl = pd.read_csv(os.path.join(ROOT, "lines", "closing.csv"))
    cl["start"] = pd.to_datetime(cl["start"], utc=True, format="ISO8601")
    cl["pulled_at"] = pd.to_datetime(cl["pulled_at"], utc=True, format="ISO8601")
    cl = cl[cl["pulled_at"] < cl["start"]]
    last = cl.sort_values("pulled_at").groupby(["home_id", "away_id", "book"]).tail(1)
    return last.groupby(["home_id", "away_id"])[["home_spread", "total"]].median()


def accuracy(dates) -> str:
    cards = [pd.read_csv(os.path.join(ROOT, "reports", f"cbb_{d}.csv")) for d in dates
             if os.path.exists(os.path.join(ROOT, "reports", f"cbb_{d}.csv"))]
    if not cards:
        return "No cards in the window."
    c = pd.concat(cards).drop_duplicates("game_id", keep="last")
    f = finals(dates)
    c = c[c["game_id"].isin(f)].copy()
    c["mar"] = c["game_id"].map(lambda g: f[g][0] - f[g][1])
    c["pts"] = c["game_id"].map(lambda g: f[g][0] + f[g][1])
    c = c.join(closes().rename(columns={"home_spread": "c_spread", "total": "c_total"}), on=["home_id", "away_id"])
    x = c.dropna(subset=["c_spread", "c_total", "model_margin", "model_total"])
    if not len(x):
        return "No graded games with a closing line."
    mt, ct = (x["model_total"] - x["pts"]).abs().mean(), (x["c_total"] - x["pts"]).abs().mean()
    mm, cm = (x["model_margin"] - x["mar"]).abs().mean(), (-x["c_spread"] - x["mar"]).abs().mean()
    return (f"{len(x)} games. Totals: model miss {mt:.2f}, close {ct:.2f} (gap {mt - ct:+.2f}; first-week backtest gap "
            f"+{REF['first-4-days total MAE gap to close']}). Margins: model {mm:.2f}, close {cm:.2f} (gap {mm - cm:+.2f}; "
            f"backtest +{REF['first-4-days margin MAE gap to close']}). Games vs closing total: "
            f"{(x['pts'] - x['c_total']).mean():+.2f} points (positive = overs).")


def plays(since: str) -> pd.DataFrame:
    b = pd.concat([tracker.load("v1").assign(kind="main"), tracker.load("bandB").assign(kind="band B")])
    b = b[(b["status"] == "settled") & (b["date"].astype(str) >= since) & b["result"].isin(["W", "L"])].copy()
    b["line"] = b["line"].astype(float)
    b["side_grp"] = np.where(b["market"] == "total", b["side"].astype(str).str.capitalize(),
                             np.where(b["line"] < 0, "favorite", "underdog"))
    b["size"] = np.where(b["market"] == "spread", pd.cut(b["line"].abs(), [-1, 6.75, 14.75, 99],
                                                          labels=["<7", "7-14.5", "15+"]).astype(str), "-")
    b["edge_band"] = np.where(b["market"] == "spread", pd.cut(b["edge"].astype(float), [0, 2.49, 3.99, 99], labels=["2-2.5", "2.5-4", "4+"]).astype(str),
                              pd.cut(b["edge"].astype(float), [0, 2.99, 3.99, 99], labels=["2-3", "3-4", "4+"]).astype(str))
    st = pd.read_csv(os.path.join(ROOT, "lines", "closing.csv"), usecols=["home_id", "away_id", "start"]).drop_duplicates(["home_id", "away_id"])
    st["start"] = pd.to_datetime(st["start"], utc=True, format="ISO8601")
    b = b.merge(st, on=["home_id", "away_id"], how="left")
    lead = (b["start"] - pd.to_datetime(b["logged_at"], utc=True, format="ISO8601")).dt.total_seconds() / 3600
    b["posted"] = pd.cut(lead, [-1, 6, 18, 999], labels=["<6h before tip", "6-18h", "18h+"]).astype(str)
    b["w"] = (b["result"] == "W").astype(int)
    return b


def table(b: pd.DataFrame, by) -> str:
    g = b.groupby(by).agg(plays=("w", "size"), win=("w", "mean"), units=("profit", "sum"), move=("clv_pts", "mean"))
    g["win"] = (100 * g["win"]).round(1)
    return g.round(2).to_string()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args()
    today = pd.Timestamp.now(tz=ET).normalize().tz_localize(None)
    start = max(today - pd.Timedelta(days=a.days), pd.Timestamp(SEASON_START))
    dates = [f"{d:%Y-%m-%d}" for d in pd.date_range(start, today - pd.Timedelta(days=1))]
    out = [f"# Weekly review, {today:%b %-d, %Y} (window {dates[0]} to {dates[-1]})", ""]
    for lab, since in (("Window", dates[0]), ("Season", SEASON_START)):
        b = plays(since)
        if lab == "Window":
            b = b[b["date"].astype(str) <= dates[-1]]
        m = b[b["kind"] == "main"]
        out += [f"## {lab}: main {int(m['w'].sum())}-{int(len(m) - m['w'].sum())}, {m['profit'].sum():+.2f}u, "
                f"line move {m['clv_pts'].mean():+.2f}; band B {int(b.loc[b['kind'] == 'band B', 'w'].sum())}-"
                f"{int((b['kind'] == 'band B').sum() - b.loc[b['kind'] == 'band B', 'w'].sum())}", ""]
        for by in (["kind", "market"], ["market", "side_grp"], ["market", "size"], ["market", "edge_band"], ["posted"], ["book"]):
            out += ["```", table(b, by), "```", ""]
    out += ["## All games against the closing line (window)", "", accuracy(dates), "",
            "## Backtest references (opener, -110)", "", ", ".join(f"{k} {v}" for k, v in REF.items()), ""]
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{today:%Y-%m-%d}.md")
    open(path, "w").write("\n".join(out) + "\n")
    print("\n".join(out))
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
