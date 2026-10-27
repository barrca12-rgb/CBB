"""B2: public-team bias (pre-registered in PLAN.md). Needs b2_fetch.py's output.

    python -m research.frontier.b2_public
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import evaluate
from research.frontier.common import clv_gains, coefs, scoreboard
from research.originator.d_common import frames, oriented_openers, walk_forward
from research.pbp.p_features import fit

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
PRIMARY = {"espn", "espn2", "abc", "cbs", "fox", "fs1", "tnt", "tbs", "trutv", "nbc"}
BROAD = PRIMARY | {"espnu", "cbssn", "btn", "sec network", "secn", "acc network", "accn", "pac-12 network", "pac12",
                   "big ten network", "fs2"}
XM, XT = ["rk_diff", "tv_nat"], ["rk_any", "tv_nat"]


def nets(s: str) -> set[str]:
    return {x.split(":", 1)[-1].strip().lower() for x in str(s or "").split("|") if x}


def wl(m: pd.Series) -> tuple[float, float, int]:
    m = m[m != 0]
    n = len(m)
    p = float((m > 0).mean()) if n else np.nan
    return 100 * p, 100 * np.sqrt(p * (1 - p) / n) if n else np.nan, n


def main() -> None:
    e = pd.read_csv(os.path.join(OUT, "b2_espn.csv.gz"))
    train, pred = frames()
    e["rk_home"], e["rk_away"] = (e["home_rank"] <= 25).astype(float), (e["away_rank"] <= 25).astype(float)
    n = e["broadcasts"].map(nets)
    e["tv_nat"] = n.map(lambda s: float(bool(s & PRIMARY)))
    e["tv_broad"] = n.map(lambda s: float(bool(s & BROAD)))
    e["has_bc"] = n.map(lambda s: float(bool(s)))
    e["rk_diff"], e["rk_any"] = e["rk_home"] - e["rk_away"], ((e["rk_home"] + e["rk_away"]) > 0).astype(float)
    cols = ["game_id", "rk_home", "rk_away", "rk_diff", "rk_any", "tv_nat", "tv_broad", "has_bc"]
    train, pred = train.merge(e[cols], on="game_id", how="left"), pred.merge(e[cols], on="game_id", how="left")
    for b in (train, pred):
        b[cols[1:]] = b[cols[1:]].fillna(0.0)
    lines = []
    cov = train[train["season"] >= 2014].groupby("season").agg(games=("game_id", "size"), matched=("has_bc", "size"),
        with_broadcast=("has_bc", "mean"), national_tv=("tv_nat", "mean"), broad_tv=("tv_broad", "mean"), any_ranked=("rk_any", "mean"))
    cov["matched"] = train[train["season"] >= 2014].groupby("season")["game_id"].apply(lambda g: g.isin(e["game_id"]).mean())
    lines.append("Coverage by season (share of frame games):\n" + cov.round(3).to_string())

    base = oriented_openers(walk_forward(train, pred))
    d = base[base["season"] >= 2014]
    d = d[~evaluate.swapped(d.assign(pred_margin=d["final_margin"]))].dropna(subset=["open_home_spread", "home_spread"])
    edge = d["final_margin"] + d["open_home_spread"]
    p = d[edge.abs() >= 2.5].copy()
    side = np.sign(edge[edge.abs() >= 2.5])              # +1 play home, -1 play away
    marg = p["home_pts"] - p["away_pts"]
    p["res_open"] = (marg + p["open_home_spread"]) * side
    p["res_close"] = (marg + p["home_spread"]) * side
    p["side"] = side

    one = p[(p["rk_home"] + p["rk_away"]) == 1]
    on_ranked = ((one["rk_home"] == 1) & (one["side"] > 0)) | ((one["rk_away"] == 1) & (one["side"] < 0))
    lines.append("\nSplit (a): frozen-rule spread plays, exactly one team ranked")
    for lab, sel in (("play ON the ranked side", on_ranked), ("play AGAINST the ranked side", ~on_ranked)):
        for ln in ("open", "close"):
            w, se, k = wl(one.loc[sel, f"res_{ln}"])
            lines.append(f"  {lab:30s} at {ln:5s}: {w:5.1f}% (se {se:.1f}), n = {k}")
    a_on, a_ag = wl(one.loc[on_ranked, "res_open"]), wl(one.loc[~on_ranked, "res_open"])
    diff_a, se_a = a_ag[0] - a_on[0], np.hypot(a_on[1], a_ag[1])
    lines.append(f"  against minus on, at the opener: {diff_a:+.1f} pts of win % (se {se_a:.1f})")

    g1 = d[(d["rk_home"] + d["rk_away"]) == 1]
    mv = (g1["open_home_spread"] - g1["home_spread"]) * np.where(g1["rk_home"] == 1, 1, -1)   # + = moved toward ranked side
    lines.append(f"  Line move open -> close toward the ranked side (all one-ranked games): {mv.mean():+.3f} pts "
                 f"(se {mv.std() / np.sqrt(len(mv)):.3f}), n = {len(mv)}")

    lines.append("\nSplit (b): frozen-rule spread plays on vs against the home side, national TV (primary) vs not")
    diffs = {}
    for tv_lab, tv in (("national TV", p["tv_nat"] == 1), ("not national TV", p["tv_nat"] == 0)):
        x = p[tv]
        for lab, sel in (("on home", x["side"] > 0), ("on away", x["side"] < 0)):
            for ln in ("open", "close"):
                w, se, k = wl(x.loc[sel, f"res_{ln}"])
                lines.append(f"  {tv_lab:16s} {lab:8s} at {ln:5s}: {w:5.1f}% (se {se:.1f}), n = {k}")
        h, a = wl(x.loc[x["side"] > 0, "res_open"]), wl(x.loc[x["side"] < 0, "res_open"])
        diffs[tv_lab] = (a[0] - h[0], np.hypot(h[1], a[1]))
    dd = diffs["national TV"][0] - diffs["not national TV"][0]
    dse = np.hypot(diffs["national TV"][1], diffs["not national TV"][1])
    lines.append(f"  (away minus home) on national TV minus off it, at the opener: {dd:+.1f} (se {dse:.1f})")

    lines += [""] + coefs(train, XM, XT)
    t = scoreboard({"frozen": walk_forward(train, pred), "B2 public": fit(train, pred, XM, XT)})
    g = clv_gains(t, "B2 public")
    lines.append("Opener CLV gain (dev, conf): " + "; ".join(f"{k} {a:+.3f}, {c:+.3f}" for k, (a, c) in g.items()))
    t.T.to_csv(os.path.join(OUT, "b2_result.csv"))
    txt = "\n".join(lines) + "\n\n" + t.T.to_string()
    open(os.path.join(OUT, "b2_run.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
