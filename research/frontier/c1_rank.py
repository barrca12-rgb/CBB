"""C1-rank (pre-registered in LOG.md): Haslametrics' daily overall/offense/defense ranks (2015-2026 archive) as
stage-2 inputs on the standard scoreboard.

    python -m research.frontier.c1_rank
"""
from __future__ import annotations

import gzip
import os
import re
from statistics import NormalDist

import numpy as np
import pandas as pd

from research.frontier.common import clv_gains, coefs, scoreboard
from research.originator.d_common import frames, walk_forward
from research.pbp.p_features import fit

HERE = os.path.dirname(__file__)
ARCH = os.path.join(HERE, "snapshots", "haslametrics_archive")
OUT = os.path.join(HERE, "out")
XM, XT = ["hs_net"], ["hs_tot"]


def daily_z(season: int) -> pd.DataFrame:
    """Rows: espn_id, date, z_all, z_off, z_def (rank as of the end of that day)."""
    x = gzip.open(os.path.join(ARCH, f"ratings{season - 2000}.xml.gz")).read().decode("utf-8", "replace")
    labels = re.search(r'<trd data="([^"]*)"', x).group(1).split(",")
    m0, d0 = map(int, labels[0].split("/"))
    start = pd.Timestamp(season - 1 if m0 >= 8 else season, m0, d0)
    ids = {t: int(i) for t, i in re.findall(r'<mr [^>]*?t="([^"]+)" [^>]*?id="(\d+)"', x)}
    n = len(ids)
    inv = NormalDist().inv_cdf
    out = {}
    for tag, col in (("tr", "z_all"), ("otr", "z_off"), ("dtr", "z_def")):
        for t, data in re.findall(rf'<{tag} t="([^"]+)" data="([^"]*)"', x):
            if t not in ids:
                continue
            for k, v in enumerate(data.split(",")):
                if v.strip():
                    out.setdefault((ids[t], start + pd.Timedelta(days=k)), {})[col] = inv(1 - (int(v) - 0.5) / n)
    d = pd.DataFrame([{"espn_id": a, "date": b, **v} for (a, b), v in out.items()])
    return d


def main() -> None:
    z = pd.concat([daily_z(s) for s in range(2015, 2027)], ignore_index=True)
    z["date"] = z["date"] + pd.Timedelta(days=1)            # a game on day D uses the ranks at the end of D-1
    train, pred = frames()
    lines = []
    feats = []
    for b in (train, pred):
        b["date_ts"] = pd.to_datetime(b["date"])
        h = b[["game_id", "date_ts", "home_id"]].merge(z.rename(columns={"espn_id": "home_id", "date": "date_ts"}), how="left")
        a = b[["game_id", "date_ts", "away_id"]].merge(z.rename(columns={"espn_id": "away_id", "date": "date_ts"}), how="left")
        h, a = h.set_index("game_id"), a.set_index("game_id")
        b["hs_ok"] = (h["z_all"].notna() & a["z_all"].notna()).reindex(b["game_id"]).to_numpy()
        h, a = h.fillna(0.0), a.fillna(0.0)
        b["hs_net"] = (h["z_all"] - a["z_all"]).reindex(b["game_id"]).to_numpy()
        b["hs_tot"] = (h["z_off"] + a["z_off"] - h["z_def"] - a["z_def"]).reindex(b["game_id"]).to_numpy()
        b.drop(columns="date_ts", inplace=True)
    cov = train.groupby("season")["hs_ok"].mean().round(3)
    lines.append("Share of games with both teams' day-before ranks:\n" + cov.to_string())
    lines += coefs(train, XM, XT)
    t = scoreboard({"frozen": walk_forward(train, pred), "C1 Haslametrics ranks": fit(train, pred, XM, XT)})
    g = clv_gains(t, "C1 Haslametrics ranks")
    lines.append("Opener CLV gain (dev, conf): " + "; ".join(f"{k} {a:+.3f}, {c:+.3f}" for k, (a, c) in g.items()))
    t.T.to_csv(os.path.join(OUT, "c1_rank_result.csv"))
    txt = "\n".join(lines) + "\n\n" + t.T.to_string()
    open(os.path.join(OUT, "c1_rank_run.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
