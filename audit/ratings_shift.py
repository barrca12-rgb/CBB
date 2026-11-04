"""Weekly read for the complete-ratings rule (protocol v2.6 Appendix D, switched off by Chad on Nov 4 pending this
evidence): do plays logged before the overnight ratings update, which would not qualify at the next morning's model,
beat the close as often as the rest?

Groups (main plays, not void):
- logged on game day, at or after 6:00 ET on the game's date (the rule's timing);
- logged earlier and still qualifying at the morning model (the card built nearest after 12:00 UTC on game day);
- logged earlier and NOT qualifying at the morning model (the plays the rule would have blocked).
"Qualifies" means the morning model's edge at the logged number meets the threshold (2.5 spreads, 3 totals).

    python -m audit.ratings_shift [--through YYYY-MM-DD]    # -> audit/out/ratings_shift.txt
"""
from __future__ import annotations

import argparse
import io
import os
import subprocess

import numpy as np
import pandas as pd

from cbb import clv_primary, tracker

ROOT = os.path.join(os.path.dirname(__file__), "..")
THR = {"spread": 2.5, "total": 3.0}


def _morning_card(day: str) -> pd.DataFrame | None:
    rel = f"reports/cbb_{day}.csv"
    h = subprocess.run(["git", "log", "-1", "--format=%h", f"--before={day}T12:05:00Z", "--", rel],
                       capture_output=True, text=True, cwd=ROOT).stdout.strip()
    if not h:
        return None
    out = subprocess.run(["git", "show", f"{h}:{rel}"], capture_output=True, text=True, cwd=ROOT).stdout
    return pd.read_csv(io.StringIO(out)) if out else None


def frame(through: str | None = None) -> pd.DataFrame:
    b = tracker.load("v1")
    b = b[b["status"] != "void"].copy()
    if through:
        b = b[b["date"] <= through]
    la = pd.to_datetime(b["logged_at"], utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
    b["early"] = la < pd.to_datetime(b["date"]) + pd.Timedelta(hours=6)
    edges = {}
    for day, g in b.groupby("date"):
        c = _morning_card(day)
        if c is None:
            continue
        c = c.set_index("game_id")
        for i, r in g.iterrows():
            if r["game_id"] not in c.index:
                continue
            x = c.loc[r["game_id"]]
            if r["market"] == "spread":
                m = x["model_margin"] if int(x["home_id"]) == int(r["home_id"]) else -x["model_margin"]
                e = (m if r["side"] == "home" else -m) + float(r["line"])
            else:
                e = (x["model_total"] - r["line"]) if r["side"] == "over" else (r["line"] - x["model_total"])
            edges[i] = e
    b["morning_edge"] = pd.Series(edges)
    b["group"] = np.where(~b["early"], "logged on game day (rule's timing)",
                          np.where(b["morning_edge"].isna(), "early, no morning card",
                                   np.where(b["morning_edge"] >= b["market"].map(THR), "early, still qualifies next morning",
                                            "early, NOT qualifying next morning")))
    p = clv_primary.primary(b).set_index("bet_id")
    return b.join(p[["clv_primary"]], on="bet_id")


def summary(b: pd.DataFrame) -> pd.DataFrame:
    def one(g):
        d = g[(g["status"] == "settled") & g["result"].isin(["W", "L"])]
        c = g["clv_primary"].dropna()
        return pd.Series({"plays": len(g), "W-L": f"{(d['result'] == 'W').sum()}-{(d['result'] == 'L').sum()}",
                          "units": round(d["profit"].sum(), 2), "with close": len(c),
                          "avg CLV": round(c.mean(), 2) if len(c) else np.nan,
                          "beat close": f"{100 * (c > 0).mean():.0f}%" if len(c) else "-"})
    return b.groupby("group").apply(one)


def main(through: str | None = None) -> None:
    b = frame(through)
    s = summary(b)
    txt = (f"Complete-ratings rule, weekly read (main plays{', through ' + through if through else ''}; rule OFF)\n"
           + s.to_string() + "\n\nBy market, plays the rule would have blocked:\n"
           + summary(b[b["group"] == "early, NOT qualifying next morning"].assign(group=lambda x: x["market"])).to_string())
    os.makedirs(os.path.join(os.path.dirname(__file__), "out"), exist_ok=True)
    open(os.path.join(os.path.dirname(__file__), "out", "ratings_shift.txt"), "w").write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--through")
    main(ap.parse_args().through)
