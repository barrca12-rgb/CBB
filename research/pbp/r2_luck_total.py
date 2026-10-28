"""R2: luck-only totals market-residual correction, no intercept (pre-registered in LOG.md). Needs the P1 caches.

    python -m research.pbp.r2_luck_total
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import evaluate
from research.originator.d_common import clv, frames, oriented_openers, walk_forward
from research.pbp.p_features import OUT, add, season_to_date, team_games, win_pct


def beyond_close_total(ch: pd.DataFrame, base: pd.DataFrame, seasons) -> dict:
    """Scorecard reference (as d_common.info_beyond_close, totals only: the margin adjustment is zero here)."""
    d = base[["game_id", "date", "season", "home_pts", "away_pts", "total", "final_total"]].merge(
        ch[["game_id", "final_total"]], on="game_id", suffixes=("", "_ch"))
    d = d[d["season"].isin(list(seasons))].dropna(subset=["total"])
    adj = d["final_total_ch"] - d["final_total"]
    X = np.column_stack([np.ones(len(d)), adj, d["final_total"] - d["total"]])
    y = ((d["home_pts"] + d["away_pts"]) - d["total"]).to_numpy(float)
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    bread = np.linalg.inv(X.T @ X)
    sm = pd.DataFrame(X * e[:, None]).groupby(d["date"].to_numpy()).sum().to_numpy()
    se = np.sqrt(np.diag(bread @ (sm.T @ sm) @ bread))
    return {"total: adjustment coef (se)": f"{b[1]:.3f} ({se[1]:.3f})", "total: adjustment SD": round(float(adj.std()), 3)}


def main() -> None:
    train, pred = frames()
    dates = pd.to_datetime(train.drop_duplicates("game_id").set_index("game_id")["date"])
    feats = pd.concat([season_to_date(team_games(s), dates) for s in range(2014, 2027)]).drop_duplicates(["game_id", "team_id"])
    base = oriented_openers(walk_forward(train, pred))
    d = add(base, feats)
    d["res_t"] = (d["home_pts"] + d["away_pts"]) - d["total"]
    ok = ~evaluate.swapped(d.assign(pred_margin=d["final_margin"]))
    ch, coefs = d.copy(), []
    for s in range(2015, 2027):
        t = d[(d["season"] < s) & ok].dropna(subset=["res_t", "luck_total"])
        x, y = t["luck_total"].to_numpy(float), t["res_t"].to_numpy(float)
        b = float(x @ y / (x @ x))                                  # least squares through the origin
        te = d["season"] == s
        ch.loc[te, "final_total"] = d.loc[te, "final_total"] + b * d.loc[te, "luck_total"].fillna(0.0)
        coefs.append({"season": s, "luck_total": round(b, 4),
                      "correction_sd": round(float((b * d.loc[te, "luck_total"].fillna(0.0)).std()), 3)})
    ch, base = ch[ch["season"] >= 2015], base[base["season"] >= 2015]
    rows = []
    for tag, w in (("frozen", base), ("R2", ch)):
        r = {"model": tag}
        for era, ss in (("dev 2015-17", range(2015, 2018)), ("conf 2024-26", range(2024, 2027))):
            r[f"total CLV {era}"] = round(clv(w, ss)["total CLV"], 3)
        wd, wh = win_pct(w, [2015, 2016, 2017, 2024]), win_pct(w, [2025, 2026])
        r.update({"total win% dev": round(wd["total win%"], 2), "total win% holdout": round(wh["total win%"], 2),
                  "total n dev/hold": f"{wd['total n']}/{wh['total n']}"})
        if tag == "R2":
            r.update(beyond_close_total(ch, base, range(2020, 2027)))
        rows.append(r)
    t = pd.DataFrame(rows).set_index("model")
    f, x = t.loc["frozen"], t.loc["R2"]
    ok_ = (x["total CLV dev 2015-17"] - f["total CLV dev 2015-17"] >= 0.05 and
           x["total CLV conf 2024-26"] - f["total CLV conf 2024-26"] >= 0.05 and
           x["total win% holdout"] >= f["total win% holdout"])
    t.loc["R2", "verdict"] = "PASS total" if ok_ else "KILL"
    t.T.to_csv(os.path.join(OUT, "r2_result.csv"))
    pd.DataFrame(coefs).to_csv(os.path.join(OUT, "r2_coefs.csv"), index=False)
    txt = pd.DataFrame(coefs).to_string(index=False) + "\n\n" + t.T.to_string() + "\n"
    open(os.path.join(OUT, "r2_run.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
