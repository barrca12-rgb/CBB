"""Ridge-1,000 with recency weights (PLAN.md). Research only.

    python -m research.r1000w.backtest      # -> out/results.txt
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from audit.common import bets, frame, record
from cbb import projection as P

OUT = os.path.join(os.path.dirname(__file__), "out")
HS = (1, 2, 3, 5, 8)
L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def wridge(X, y, w, lam):
    X1 = np.column_stack([np.ones(len(X)), X])
    pen = np.full(X1.shape[1], lam)
    pen[0] = 0
    Xw = X1 * w[:, None]
    return np.linalg.solve(X1.T @ Xw + np.diag(pen), Xw.T @ y)


def coefs(tr: pd.DataFrame, s: int, lam: float, H: float | None) -> tuple:
    w = np.ones(len(tr)) if H is None else 0.5 ** ((s - 1 - tr["season"].to_numpy()) / H)
    w = w / w.mean()
    cm = wridge(tr[P.MARGIN_FEATURES].to_numpy(float), tr["margin"].to_numpy(float), w, lam)
    ct = wridge(tr[P.TOTAL_FEATURES].to_numpy(float), tr["points"].to_numpy(float), w, lam)
    return cm, ct


def walk(w: pd.DataFrame, lam: float, H: float | None, seasons) -> pd.DataFrame:
    parts = []
    for s in seasons:
        tr = w[w["season"] < s].dropna(subset=["margin", "points"])
        cm, ct = coefs(tr, s, lam, H)
        te = w[w["season"] == s].copy()
        te["final_margin"] = cm[0] + te[P.MARGIN_FEATURES].to_numpy(float) @ cm[1:]
        te["final_total"] = ct[0] + te[P.TOTAL_FEATURES].to_numpy(float) @ ct[1:]
        parts.append(te)
    return pd.concat(parts)


def mae(d: pd.DataFrame) -> tuple[float, float]:
    d = d.dropna(subset=["margin", "points"])
    return (float((d["margin"] - d["final_margin"]).abs().mean()), float((d["points"] - d["final_total"]).abs().mean()))


def main() -> None:
    w = frame(tag="base")
    sel, hold = range(2019, 2023), range(2023, 2027)
    variants = {"live (penalty 1)": (1.0, None), "ridge-1,000": (1000.0, None)}
    variants.update({f"ridge-1,000, half-life {h}": (1000.0, h) for h in HS})
    rows, frames = [], {}
    for name, (lam, H) in variants.items():
        a, b = walk(w, lam, H, sel), walk(w, lam, H, hold)
        frames[name] = b
        (sm, st), (hm, ht) = mae(a), mae(b)
        rows.append({"model": name, "2019-22 margin": round(sm, 4), "2019-22 total": round(st, 4),
                     "2023-26 margin": round(hm, 4), "2023-26 total": round(ht, 4)})
    A = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    say("Mean absolute error, walk-forward (choose on 2019-22, judge on 2023-26):\n" + A.to_string(index=False))
    cand = A[A["model"].str.contains("half-life")].copy()
    cand["sel"] = cand["2019-22 margin"] + cand["2019-22 total"]
    best = cand.sort_values("sel")["model"].iat[0]
    say(f"\nChosen on 2019-22: {best}")
    prow = []
    for name in ("live (penalty 1)", "ridge-1,000", best):
        for mk, thr in (("spread", 2.5), ("total", 3.0)):
            r = record(bets(frames[name], mk, "open", thr, (2024, 2026)))
            bb = bets(frames[name], mk, "open", thr, (2024, 2026))
            prow.append({"model": name, "market": mk, "plays": r["plays"], "win%": round(r["win%"], 2),
                         "ROI%": r["ROI%"], "move to us": round(bb["clv"].mean(), 3)})
    Pl = pd.DataFrame(prow)
    say("\nOpener plays 2024-26:\n" + Pl.to_string(index=False))
    g = lambda m, c: A[A["model"] == m][c].iat[0]
    c1 = g(best, "2023-26 margin") < g("ridge-1,000", "2023-26 margin") and g(best, "2023-26 total") < g("ridge-1,000", "2023-26 total")
    pw = lambda m, mk: Pl[(Pl["model"] == m) & (Pl["market"] == mk)]["win%"].iat[0]
    c2 = all(pw(best, mk) >= pw("ridge-1,000", mk) - 0.3 for mk in ("spread", "total"))
    say(f"\nShadow rule: 2023-26 errors below ridge-1,000 {c1}; opener win % within 0.3 {c2} -> "
        f"{'RUN AS SHADOW' if c1 and c2 else 'do not run'}")
    os.makedirs(OUT, exist_ok=True)
    A.to_csv(os.path.join(OUT, "accuracy.csv"), index=False)
    Pl.to_csv(os.path.join(OUT, "plays.csv"), index=False)
    open(os.path.join(OUT, "results.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
