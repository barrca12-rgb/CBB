"""Own-ratings backtests (research/own_ratings/PLAN.md). Research only: cbb/ratings.py and the live model are
untouched; variants are built from a copy of ratings.fit with the pre-registered edits.

    python -m research.own_ratings.run stage1[:tag]   # stage-1 files: base (fresh rerun), level60/20/200, ownprior
    python -m research.own_ratings.run score      # all tables -> out/*.csv, printed
"""
from __future__ import annotations

import inspect
import os
import sys
import textwrap

import numpy as np
import pandas as pd

from cbb import backtest, data, ratings

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
BASE = os.path.join(HERE, "..", "..", "cbb", "output", "backtest_2013_2026.csv")
SEASONS = range(2013, 2027)


def level_fit(K: float):
    """ratings.fit with the efficiency and pace intercepts shrunk toward last season's league averages (K team-games)."""
    src = textwrap.dedent(inspect.getsource(ratings.fit))
    edits = [
        ("    lam[0] = 1e-6\n", f"    lam[0] = {K} * wbar\n"),
        ("beta0 = np.concatenate([[y.mean() if n else league[\"ppp\"], cfg.hca_prior]",
         "beta0 = np.concatenate([[league[\"ppp\"], cfg.hca_prior]"),
        ("    lamp[0] = 1e-6\n", f"    lamp[0] = {K} * wbar\n"),
        ("p0 = np.concatenate([[yp.mean() if n else league[\"pace\"]], pr[\"tempo\"]])",
         "p0 = np.concatenate([[league[\"pace\"]], pr[\"tempo\"]])"),
    ]
    for a, b in edits:
        assert src.count(a) == 1, a
        src = src.replace(a, b)
    src = src.replace("def fit(", f"def fit_level_{int(K)}(")
    ns = dict(vars(ratings))
    exec(src, ns)
    return ns[f"fit_level_{int(K)}"]


def stage1(tag: str, fit=None, prior_fn=None) -> str:
    """A stage-1 file for 2013-2026 through backtest.season with a swapped fit and/or prior."""
    path = os.path.join(OUT, f"stage1_{tag}.csv")
    if os.path.exists(path):
        return path
    f0, p0 = ratings.fit, backtest.preseason_prior
    try:
        if fit is not None:
            ratings.fit = fit
        if prior_fn is not None:
            backtest.preseason_prior = prior_fn
        parts = []
        for s in SEASONS:
            parts.append(backtest.season(s))
            print(tag, s, flush=True)
        pd.concat(parts).to_csv(path, index=False)
    finally:
        ratings.fit, backtest.preseason_prior = f0, p0
    return path


def own_prior(season: int, carry: float = 0.6) -> pd.DataFrame:
    """Last season's final stage-1 ratings (no outside prior), carried at `carry`: off, def, tempo deviations."""
    g, t = data.season_games(season - 1)
    ids = sorted(set(t["team_id"]))
    league = ratings.league_averages(data.season_games(season - 2)[1])
    r = ratings.fit(t, pd.to_datetime(g["date"]).max() + pd.Timedelta(days=1), ids, None, None, league)
    return pd.DataFrame({"off": r["off"], "def": r["def"], "tempo": r["tempo"]}) * carry


def _days(d: pd.DataFrame) -> pd.Series:
    dt = pd.to_datetime(d["date"])
    return (dt - dt.groupby(d["season"]).transform("min")).dt.days


def stage1_table(files: dict) -> pd.DataFrame:
    rows = []
    for tag, p in files.items():
        d = pd.read_csv(p).dropna(subset=["home_pts"])
        d = d[d["season"] >= 2014]
        d["act_t"], d["act_m"], d["day"] = d["home_pts"] + d["away_pts"], d["home_pts"] - d["away_pts"], _days(d)
        for lab, x in (("days 0-20", d[d["day"] <= 20]), ("full season", d)):
            rows.append({"variant": tag, "part": lab, "games": len(x),
                         "total MAE": round(float((x["pred_total"] - x["act_t"]).abs().mean()), 3),
                         "total bias": round(float((x["pred_total"] - x["act_t"]).mean()), 2),
                         "margin MAE": round(float((x["pred_margin"] - x["act_m"]).abs().mean()), 3)})
        per = d.groupby("season").apply(lambda x: pd.Series({
            "t": (x["pred_total"] - x["act_t"]).abs().mean(), "m": (x["pred_margin"] - x["act_m"]).abs().mean()}))
        per.to_csv(os.path.join(OUT, f"stage1_by_season_{tag}.csv"))
    return pd.DataFrame(rows)


def live_replay(K_list=(None, 60, 20, 200)) -> pd.DataFrame:
    """Stage-1 totals for the live Nov 2-4, 2026 games: current fit vs the level variants (frozen 2027 prior)."""
    from research.morning_shadow import compare as C
    from cbb import teams
    season = 2027
    hist, tg = data.season_games(season)
    L = ratings.league_averages(data.season_games(season - 1)[1])
    pr = pd.read_csv(os.path.join(HERE, "..", "..", "audit", "out", "frozen_preseason_prior_2027.csv")).set_index("espn_id")
    ids = sorted(set(teams.load()["espn_id"]) | set(tg["team_id"]))
    g = hist[hist["date"] >= "2026-11-02"]
    rows = []
    for K in K_list:
        fit = ratings.fit if K is None else level_fit(K)
        preds = []
        for day, gd in g.groupby("date"):
            r = fit(tg, day, ids, pr, None, L)
            p = ratings.predict(r, gd["home_id"], gd["away_id"], gd["neutral"])
            preds.append(pd.DataFrame({"pred": p["total"].to_numpy(), "act": (gd["home_pts"] + gd["away_pts"]).to_numpy()}))
        x = pd.concat(preds)
        rows.append({"variant": "current" if K is None else f"level{K}", "games": len(x),
                     "total MAE": round(float((x["pred"] - x["act"]).abs().mean()), 2),
                     "total bias": round(float((x["pred"] - x["act"]).mean()), 2)})
    return pd.DataFrame(rows)


def zero(cols):
    return lambda b: b.assign(**{c: 0.0 for c in cols})


BT = ["bt_margin", "bt_total"]
KP = ["kp_margin", "kp_total", "kp_margin_x_early", "kp_total_x_early"]


def final_tables(frames: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    from audit.a2_timing import score
    acc, plays = [], []
    for tag, w in frames.items():
        w = w[w["season"] >= 2015].copy()
        w["day"] = _days(w)
        for lab, x in (("days 0-20", w[w["day"] <= 20]), ("all", w)):
            acc.append({"variant": tag, "part": lab, "games": len(x),
                        "margin MAE": round(float((x["final_margin"] - x["margin"]).abs().mean()), 3),
                        "total MAE": round(float((x["final_total"] - x["points"]).abs().mean()), 3)})
        plays += score(w, tag)
    return pd.DataFrame(acc), pd.DataFrame(plays)


def main(step: str) -> None:
    os.makedirs(OUT, exist_ok=True)
    pd.set_option("display.width", 250)
    if step.startswith("stage1"):
        which = step.split(":")[1] if ":" in step else "all"
        jobs = {"base": {}, "level60": {"fit": level_fit(60)}, "level20": {"fit": level_fit(20)},
                "level200": {"fit": level_fit(200)}, "ownprior": {"prior_fn": own_prior}}
        for tag, kw in jobs.items():
            if which in ("all", tag):
                stage1(tag, **kw)
        return
    from audit.common import frame
    files = {"base": stage1("base"), "level60": stage1("level60"), "level20": stage1("level20"), "level200": stage1("level200"),
             "ownprior": stage1("ownprior")}
    s1 = stage1_table(files)
    lr = live_replay()
    frames = {"base": frame(stage1=files["base"], tag="own_base"),
              "A level60": frame(stage1=files["level60"], tag="own_level60"),
              "B1 no_bt": frame(stage1=files["base"], tag="own_no_bt", features=zero(BT)),
              "B2 no_kp": frame(stage1=files["base"], tag="own_no_kp", features=zero(KP)),
              "B3 own_stage2": frame(stage1=files["base"], tag="own_stage2", features=zero(BT + KP)),
              "B4 own_only": frame(stage1=files["ownprior"], tag="own_only", features=zero(BT + KP))}
    acc, plays = final_tables(frames)
    for name, t in (("stage1", s1), ("live_replay", lr), ("final_accuracy", acc), ("opener_plays", plays)):
        t.to_csv(os.path.join(OUT, f"{name}.csv"), index=False)
        print(f"\n== {name}\n{t.to_string(index=False)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "score")
