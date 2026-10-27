"""The standard scoreboard for the frontier tests (PLAN.md): forecast MAE 2020-26, opener CLV dev 2014-17 and
conf 2024-26, opener win % dev and holdout, information beyond the close 2020-26, and stage-2 coefficients with
date-clustered intervals."""
from __future__ import annotations

import numpy as np
import pandas as pd

from cbb import projection
from research.originator.d_common import clv, info_beyond_close, mae, oriented_openers
from research.pbp.p_features import win_pct


def scoreboard(fits: dict, base_key: str = "frozen") -> pd.DataFrame:
    base = fits[base_key]
    rows = []
    for tag, w in fits.items():
        ow = oriented_openers(w)
        r = {"model": tag, **{k: round(v, 4) for k, v in mae(w, range(2020, 2027)).items()}}
        for era, ss in (("dev 2014-17", range(2014, 2018)), ("conf 2024-26", range(2024, 2027))):
            c = clv(ow, ss)
            r[f"spread CLV {era}"], r[f"total CLV {era}"] = round(c["spread CLV"], 3), round(c["total CLV"], 3)
        wd, wh = win_pct(ow, [2014, 2015, 2016, 2017, 2024]), win_pct(ow, [2025, 2026])
        r.update({"spread win% dev": round(wd["spread win%"], 2), "spread win% holdout": round(wh["spread win%"], 2),
                  "total win% dev": round(wd["total win%"], 2), "total win% holdout": round(wh["total win%"], 2),
                  "spread n dev/hold": f"{wd['spread n']}/{wh['spread n']}", "total n dev/hold": f"{wd['total n']}/{wh['total n']}"})
        if tag != base_key:
            r.update(info_beyond_close(w, base, range(2020, 2027)))
        rows.append(r)
    return pd.DataFrame(rows).set_index("model")


def clv_gains(t: pd.DataFrame, tag: str, base_key: str = "frozen") -> dict:
    f, x = t.loc[base_key], t.loc[tag]
    return {cm: (float(x[f"{cm} CLV dev 2014-17"] - f[f"{cm} CLV dev 2014-17"]), float(x[f"{cm} CLV conf 2024-26"] - f[f"{cm} CLV conf 2024-26"]))
            for cm in ("spread", "total")}


def coefs(train: pd.DataFrame, xm: list[str], xt: list[str], last: int = 2026) -> list[str]:
    """Stage-2 coefficients of the added features (ridge lam=1, as live), fit on seasons before `last`, with
    date-clustered 95% intervals."""
    tr = train[train["season"] < last].dropna(subset=["home_pts"])
    out = []
    for mk, feats, extra, y in (("margin", projection.MARGIN_FEATURES, xm, tr["home_pts"] - tr["away_pts"]),
                                ("total", projection.TOTAL_FEATURES, xt, tr["home_pts"] + tr["away_pts"])):
        if not extra:
            continue
        X = np.column_stack([np.ones(len(tr)), tr[feats + extra].to_numpy(float)])
        yy = y.to_numpy(float)
        b = np.linalg.solve(X.T @ X + np.diag([0] + [1.0] * (X.shape[1] - 1)), X.T @ yy)
        e = yy - X @ b
        bread = np.linalg.inv(X.T @ X)
        sc = pd.DataFrame(X * e[:, None]).groupby(tr["date"].to_numpy()).sum().to_numpy()
        se = np.sqrt(np.diag(bread @ (sc.T @ sc) @ bread))
        for j, f in enumerate(extra):
            k = 1 + len(feats) + j
            out.append(f"Stage-2 {mk} coef {f}: {b[k]:+.3f} (se {se[k]:.3f}) -> 95% CI [{b[k] - 1.96 * se[k]:+.3f}, {b[k] + 1.96 * se[k]:+.3f}]")
    return out
