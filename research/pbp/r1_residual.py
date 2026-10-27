"""R1: market-residual correction (pre-registered in LOG.md). Needs the P1/P2 caches from p_features.py.

    python -m research.pbp.r1_residual
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import evaluate
from research.originator.d_common import OUT as ORIG, clv, frames, info_beyond_close, oriented_openers, walk_forward
from research.pbp.p_features import OUT, add, season_to_date, team_games, win_pct

XM = ["luck_margin", "garbage_margin", "lineup_margin"]
XT = ["luck_total", "garbage_total", "lineup_total"]


def main() -> None:
    train, pred = frames()
    dates = pd.to_datetime(train.drop_duplicates("game_id").set_index("game_id")["date"])
    feats = pd.concat([season_to_date(team_games(s), dates) for s in range(2014, 2027)]).drop_duplicates(["game_id", "team_id"])
    base = oriented_openers(walk_forward(train, pred))
    d = add(base, feats)
    a = pd.read_csv(os.path.join(ORIG, "b_adjustments.csv.gz")).drop(columns="season")
    d = d.merge(a.rename(columns={"team_id": "home_id", "adj_off": "h_off", "adj_def": "h_def"}), on=["game_id", "home_id"], how="left") \
         .merge(a.rename(columns={"team_id": "away_id", "adj_off": "a_off", "adj_def": "a_def"}), on=["game_id", "away_id"], how="left")
    for c in ("h_off", "h_def", "a_off", "a_def"):
        d[c] = d[c].fillna(0.0)
    d["lineup_margin"] = (d["h_off"] + d["h_def"]) - (d["a_off"] + d["a_def"])
    d["lineup_total"] = (d["h_off"] + d["a_off"]) - (d["h_def"] + d["a_def"])
    d["res_m"] = (d["home_pts"] - d["away_pts"]) + d["home_spread"]
    d["res_t"] = (d["home_pts"] + d["away_pts"]) - d["total"]
    ok = ~evaluate.swapped(d.assign(pred_margin=d["final_margin"]))
    ch = d.copy()
    coefs = []
    for s in range(2015, 2027):
        tr = d[(d["season"] >= 2014) & (d["season"] < s) & ok]
        te = d["season"] == s
        for xs, y, col in ((XM, "res_m", "final_margin"), (XT, "res_t", "final_total")):
            t = tr.dropna(subset=[y])
            X = np.column_stack([np.ones(len(t)), t[xs].to_numpy(float)])
            b, *_ = np.linalg.lstsq(X, t[y].to_numpy(float), rcond=None)
            ch.loc[te, col] = d.loc[te, col] + b[0] + d.loc[te, xs].to_numpy(float) @ b[1:]
            coefs.append({"season": s, "market": y, **dict(zip(["intercept"] + xs, np.round(b, 4)))})
    ch, base = ch[ch["season"] >= 2015], base[base["season"] >= 2015]
    rows = []
    for tag, w in (("frozen", base), ("R1", ch)):
        r = {"model": tag}
        for era, ss in (("dev 2015-17", range(2015, 2018)), ("conf 2024-26", range(2024, 2027))):
            c = clv(w, ss)
            r[f"spread CLV {era}"], r[f"total CLV {era}"] = round(c["spread CLV"], 3), round(c["total CLV"], 3)
        wd, wh = win_pct(w, [2015, 2016, 2017, 2024]), win_pct(w, [2025, 2026])
        r.update({"spread win% dev": round(wd["spread win%"], 2), "spread win% holdout": round(wh["spread win%"], 2),
                  "total win% dev": round(wd["total win%"], 2), "total win% holdout": round(wh["total win%"], 2),
                  "spread n dev/hold": f"{wd['spread n']}/{wh['spread n']}", "total n dev/hold": f"{wd['total n']}/{wh['total n']}"})
        if tag == "R1":
            r.update(info_beyond_close(ch, base, range(2020, 2027)))
        rows.append(r)
    t = pd.DataFrame(rows).set_index("model")
    f, x = t.loc["frozen"], t.loc["R1"]
    passes = {cm: (x[f"{cm} CLV dev 2015-17"] - f[f"{cm} CLV dev 2015-17"] >= 0.05)
              and (x[f"{cm} CLV conf 2024-26"] - f[f"{cm} CLV conf 2024-26"] >= 0.05)
              and (x[f"{cm} win% holdout"] >= f[f"{cm} win% holdout"]) for cm in ("spread", "total")}
    t.loc["R1", "verdict"] = "PASS " + ",".join(k for k, v in passes.items() if v) if any(passes.values()) else "KILL"
    t.T.to_csv(os.path.join(OUT, "r1_result.csv"))
    pd.DataFrame(coefs).to_csv(os.path.join(OUT, "r1_coefs.csv"), index=False)
    pd.set_option("display.width", 250)
    print(pd.DataFrame(coefs).tail(4).to_string(index=False))
    print(t.T.to_string())


if __name__ == "__main__":
    main()
