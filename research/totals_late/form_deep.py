"""Part 4 (PLAN.md): deep dive on (f) recent form. Robustness and mechanism only; the Part 3 verdict stands.

    python -m research.totals_late.form_deep
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import projection
from research.originator.d_common import frames, oriented_openers, ridge_w
from research.totals_late.diag import OUT, plays
from research.totals_late.round2 import refit

ERAS = {"dev": [2014, 2015, 2016, 2017, 2024], "holdout": [2025, 2026]}


def add_form(df: pd.DataFrame, n: int) -> pd.DataFrame:
    res = df["home_pts"] + df["away_pts"] - df["pred_total"]
    long = pd.concat([pd.DataFrame({"game_id": df["game_id"], "season": df["season"], "date": pd.to_datetime(df["date"]),
                                    "team": df[c], "res": res, "slot": c}) for c in ("home_id", "away_id")])
    long = long.sort_values(["date", "game_id"])
    long["form"] = long.groupby(["season", "team"])["res"].transform(
        lambda x: x.shift(1).rolling(n, min_periods=3).mean()).fillna(0.0)
    f = long.pivot_table(index="game_id", columns="slot", values="form", aggfunc="first")
    out = df.copy()
    out["form_sum"] = out["game_id"].map(f["home_id"]).fillna(0) + out["game_id"].map(f["away_id"]).fillna(0)
    return out


def beyond_close(ch: pd.DataFrame, base: pd.DataFrame, seasons) -> tuple[float, float, float]:
    """Totals half of d_common.info_beyond_close (its margin half is singular here: form leaves margins unchanged).
    OLS of (actual - close) on (form total - frozen total), control frozen total - close; date-clustered SE."""
    d = base[["game_id", "date", "season", "home_pts", "away_pts", "total", "final_total"]].merge(
        ch[["game_id", "final_total"]], on="game_id", suffixes=("", "_ch"))
    d = d[d["season"].isin(list(seasons))].dropna(subset=["total"])
    adj = (d["final_total_ch"] - d["final_total"]).to_numpy(float)
    X = np.column_stack([np.ones(len(d)), adj, (d["final_total"] - d["total"]).to_numpy(float)])
    y = (d["home_pts"] + d["away_pts"] - d["total"]).to_numpy(float)
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    bread = np.linalg.inv(X.T @ X)
    sc = pd.DataFrame(X * e[:, None]).groupby(d["date"].to_numpy()).sum().to_numpy()
    se = np.sqrt(np.diag(bread @ (sc.T @ sc) @ bread))
    return float(b[1]), float(se[1]), float(adj.std())


def rec(p: pd.DataFrame) -> dict:
    dec = p["res_open"][p["res_open"] != 0]
    return {"plays": len(p), "win%": 100 * (dec > 0).mean() if len(dec) else np.nan, "CLV": p["clv"].mean()}


def main() -> None:
    train, pred = frames()
    base = pd.read_pickle(os.path.join(OUT, "frozen_wf.pkl"))
    fp = plays(base)
    txt, fits = [], {}
    for n in (5, 10, 20):
        tf, pf = add_form(train, n), add_form(pred, n)
        w = oriented_openers(refit(tf, pf, "form_sum"))
        fits[n] = (tf, w)
    pd.set_option("display.width", 250)

    # per season, window 10
    w10 = fits[10][1]
    p10 = plays(base.drop(columns=["final_total"]).merge(w10[["game_id", "final_total"]], on="game_id"))
    rows = []
    for s in [2014, 2015, 2016, 2017, 2024, 2025, 2026]:
        for half in ("Jan-Mar", "all"):
            a = fp[(fp["season"] == s) & ((fp["half"] == half) if half != "all" else True)]
            b = p10[(p10["season"] == s) & ((p10["half"] == half) if half != "all" else True)]
            ra, rb = rec(a), rec(b)
            rows.append({"season": s, "part": half, "frozen plays": ra["plays"], "frozen win%": ra["win%"],
                         "form plays": rb["plays"], "form win%": rb["win%"], "d win%": rb["win%"] - ra["win%"],
                         "frozen CLV": ra["CLV"], "form CLV": rb["CLV"]})
    txt.append("## Per season (window 10)\n" + pd.DataFrame(rows).round(2).to_string(index=False))

    # information beyond the close, per era and window
    rows = []
    for n, (_, w) in fits.items():
        for era, ss in ERAS.items():
            coef, se, sd = beyond_close(w, base, ss)
            m = base[base["season"].isin(ss)][["game_id", "home_pts", "away_pts", "final_total"]].merge(
                w[["game_id", "final_total"]], on="game_id", suffixes=("", "_f"))
            act = m["home_pts"] + m["away_pts"]
            rows.append({"window": n, "era": era, "beyond-close coef": float(coef), "se": float(se),
                         "z": coef / se, "adjustment SD": sd,
                         "MAE frozen": (act - m["final_total"]).abs().mean(),
                         "MAE form": (act - m["final_total_f"]).abs().mean()})
    txt.append("## Information beyond the close and accuracy\n" + pd.DataFrame(rows).round(3).to_string(index=False))

    # window sensitivity on win %
    rows = []
    for n, (_, w) in fits.items():
        pn = plays(base.drop(columns=["final_total"]).merge(w[["game_id", "final_total"]], on="game_id"))
        for era, ss in ERAS.items():
            for half in ("Jan-Mar", "all"):
                a = fp[fp["season"].isin(ss) & ((fp["half"] == half) if half != "all" else True)]
                b = pn[pn["season"].isin(ss) & ((pn["half"] == half) if half != "all" else True)]
                rows.append({"window": n, "era": era, "part": half, "d win%": rec(b)["win%"] - rec(a)["win%"],
                             "d CLV": rec(b)["CLV"] - rec(a)["CLV"], "plays": rec(b)["plays"]})
    txt.append("## Window sensitivity\n" + pd.DataFrame(rows).round(2).to_string(index=False))

    # coefficient stability (window 10): each walk-forward fit
    tf = fits[10][0]
    feats = projection.TOTAL_FEATURES + ["form_sum"]
    tf = tf.assign(points=tf["home_pts"] + tf["away_pts"])
    rows = []
    for s in range(2014, 2027):
        t = tf[(tf["season"] < s) & (tf["season"] >= 2013)]
        c = ridge_w(t[feats].to_numpy(float), t["points"].to_numpy(float), np.ones(len(t)))
        rows.append({"predicting": s, "form_sum coef": c[1 + feats.index("form_sum")]})
    txt.append("## form_sum coefficient by walk-forward fit (window 10)\n" + pd.DataFrame(rows).round(4).to_string(index=False))

    # side and half (window 10)
    rows = []
    for era, ss in ERAS.items():
        for half in ("Nov-Dec", "Jan-Mar"):
            for side in ("over", "under"):
                sel = lambda p: p[p["season"].isin(ss) & (p["half"] == half) & (p["side"] == side)]
                ra, rb = rec(sel(fp)), rec(sel(p10))
                rows.append({"era": era, "half": half, "side": side, "frozen plays": ra["plays"], "frozen win%": ra["win%"],
                             "form plays": rb["plays"], "form win%": rb["win%"]})
    txt.append("## Side and half (window 10)\n" + pd.DataFrame(rows).round(2).to_string(index=False))
    out = "\n\n".join(txt)
    open(os.path.join(OUT, "form_deep.txt"), "w").write(out)
    print(out)


if __name__ == "__main__":
    main()
