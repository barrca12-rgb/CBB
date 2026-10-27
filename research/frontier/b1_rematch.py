"""B1: rematch effects (pre-registered in PLAN.md). Free check, then the features as stage-2 inputs on the standard
scoreboard.

    python -m research.frontier.b1_rematch
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.originator.d_common import clv, frames, info_beyond_close, mae, oriented_openers, walk_forward
from research.pbp.p_features import fit, win_pct

OUT = os.path.join(os.path.dirname(__file__), "out")
XM, XT = ["rm_resid", "rm_flag", "rm_flip"], ["rm_tresid", "rm_flag", "rm_flip"]


def rematch_features(g: pd.DataFrame) -> pd.DataFrame:
    """Per game: features from the most recent earlier meeting of the same two teams this season (conference
    games only), oriented to the current home team. Zeros when not a rematch."""
    g = g[["game_id", "season", "date", "home_id", "away_id", "conf_game", "home_pts", "away_pts", "home_spread", "total"]].copy()
    g["date"] = pd.to_datetime(g["date"])
    g["pair"] = [tuple(sorted((int(a), int(b)))) for a, b in zip(g["home_id"], g["away_id"])]
    g = g.sort_values(["season", "date", "game_id"])
    out = []
    for (_, _), x in g.groupby(["season", "pair"]):
        prev = None
        for _, r in x.iterrows():
            f = {"game_id": r["game_id"], "rm_resid": 0.0, "rm_tresid": 0.0, "rm_flag": 0.0, "rm_flip": 0.0, "rm_days": np.nan,
                 "rm_line_ok": False}
            if prev is not None and bool(r["conf_game"]) and bool(prev["conf_game"]):
                same = int(prev["home_id"]) == int(r["home_id"])
                res = (prev["home_pts"] - prev["away_pts"]) + prev["home_spread"]
                tres = (prev["home_pts"] + prev["away_pts"]) - prev["total"]
                f.update({"rm_flag": 1.0, "rm_flip": 0.0 if same else 1.0, "rm_days": (r["date"] - prev["date"]).days,
                          "rm_resid": float(res if same else -res) if pd.notna(res) else 0.0,
                          "rm_tresid": float(tres) if pd.notna(tres) else 0.0, "rm_line_ok": bool(pd.notna(res))})
            out.append(f)
            prev = r
    return pd.DataFrame(out)


def corr_ci(x, y):
    r = float(np.corrcoef(x, y)[0, 1])
    z, se = np.arctanh(r), 1 / np.sqrt(len(x) - 3)
    return r, float(np.tanh(z - 1.96 * se)), float(np.tanh(z + 1.96 * se)), len(x)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    train, pred = frames()
    rf = rematch_features(train)
    train, pred = train.merge(rf, on="game_id", how="left"), pred.merge(rf, on="game_id", how="left")
    for c in XM + XT + ["rm_days"]:
        for b in (train, pred):
            b[c] = b[c].fillna(0.0) if c != "rm_days" else b[c]
    lines = []
    rm = train[train["rm_flag"] == 1]
    lines.append(f"Rematches (conference, earlier meeting same season): {len(rm)} of {len(train)} games; "
                 f"earlier meeting had a closing line in {rm['rm_line_ok'].mean():.1%}; venue flipped in {rm['rm_flip'].mean():.1%}; "
                 f"median days between {rm['rm_days'].median():.0f}")

    # free check: frozen model's residual in rematches vs the first meeting's residual against the line
    base = walk_forward(train, pred)
    b = base[(base["rm_flag"] == 1) & base["rm_line_ok"].astype(bool)]
    for lab, res, x in (("margin", (b["home_pts"] - b["away_pts"]) - b["final_margin"], b["rm_resid"]),
                        ("total", (b["home_pts"] + b["away_pts"]) - b["final_total"], b["rm_tresid"]),
                        ("margin vs close", (b["home_pts"] - b["away_pts"]) + b["home_spread"], b["rm_resid"]),
                        ("total vs close", (b["home_pts"] + b["away_pts"]) - b["total"], b["rm_tresid"])):
        ok = res.notna() & x.notna()
        r, lo, hi, n = corr_ci(res[ok], x[ok])
        lines.append(f"Free check, {lab} residual vs earlier-meeting residual: r = {r:+.3f} [{lo:+.3f}, {hi:+.3f}], n = {n}")
    for lab, sel in (("same venue", b["rm_flip"] == 0), ("venue flipped", b["rm_flip"] == 1)):
        x = b[sel]; res = (x["home_pts"] - x["away_pts"]) - x["final_margin"]
        r, lo, hi, n = corr_ci(res, x["rm_resid"])
        lines.append(f"  {lab}: r = {r:+.3f} [{lo:+.3f}, {hi:+.3f}], n = {n}")

    # stage-2 inputs on the standard scoreboard
    ch = fit(train, pred, XM, XT)
    ob, oc = oriented_openers(base), oriented_openers(ch)
    rows = []
    for tag, w, ow in (("frozen", base, ob), ("B1 rematch", ch, oc)):
        r = {"model": tag, **{k: round(v, 4) for k, v in mae(w, range(2020, 2027)).items()}}
        for era, ss in (("dev 2014-17", range(2014, 2018)), ("conf 2024-26", range(2024, 2027))):
            c = clv(ow, ss)
            r[f"spread CLV {era}"], r[f"total CLV {era}"] = round(c["spread CLV"], 3), round(c["total CLV"], 3)
        wd, wh = win_pct(ow, [2014, 2015, 2016, 2017, 2024]), win_pct(ow, [2025, 2026])
        r.update({"spread win% dev": round(wd["spread win%"], 2), "spread win% holdout": round(wh["spread win%"], 2),
                  "total win% dev": round(wd["total win%"], 2), "total win% holdout": round(wh["total win%"], 2)})
        if tag != "frozen":
            r.update(info_beyond_close(ch, base, range(2020, 2027)))
        rows.append(r)
    t = pd.DataFrame(rows).set_index("model")
    # stage-2 coefficients with date-clustered SEs, fit on 2013-2025 (the last walk-forward fold)
    from cbb import projection
    tr = train[(train["season"] < 2026)].dropna(subset=["home_pts"])
    for mk, feats, extra, y in (("margin", projection.MARGIN_FEATURES, XM, tr["home_pts"] - tr["away_pts"]),
                                ("total", projection.TOTAL_FEATURES, XT, tr["home_pts"] + tr["away_pts"])):
        X = np.column_stack([np.ones(len(tr)), tr[feats + extra].to_numpy(float)])
        yy = y.to_numpy(float)
        bta = np.linalg.solve(X.T @ X + np.diag([0] + [1.0] * (X.shape[1] - 1)), X.T @ yy)
        e = yy - X @ bta
        bread = np.linalg.inv(X.T @ X)
        sc = pd.DataFrame(X * e[:, None]).groupby(tr["date"].to_numpy()).sum().to_numpy()
        se = np.sqrt(np.diag(bread @ (sc.T @ sc) @ bread))
        for j, f in enumerate(extra):
            k = 1 + len(feats) + j
            lines.append(f"Stage-2 {mk} coef {f}: {bta[k]:+.3f} (se {se[k]:.3f}) -> 95% CI [{bta[k] - 1.96 * se[k]:+.3f}, {bta[k] + 1.96 * se[k]:+.3f}]")
    f, x = t.loc["frozen"], t.loc["B1 rematch"]
    gains = {cm: (x[f"{cm} CLV dev 2014-17"] - f[f"{cm} CLV dev 2014-17"], x[f"{cm} CLV conf 2024-26"] - f[f"{cm} CLV conf 2024-26"]) for cm in ("spread", "total")}
    lines.append("Opener CLV gain (dev, conf): " + "; ".join(f"{k} {a:+.3f}, {c:+.3f}" for k, (a, c) in gains.items()))
    t.T.to_csv(os.path.join(OUT, "b1_result.csv"))
    txt = "\n".join(lines) + "\n\n" + t.T.to_string()
    open(os.path.join(OUT, "b1_run.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
