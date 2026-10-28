"""Step 3: E1-E3 as pre-registered in research/quant/PLAN.md. One run, no tuning.

    python -m research.quant.experiments      # -> out/exp_result.csv, out/exp_by_season.csv, out/exp_run.txt
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
from scipy.stats import norm

from cbb import projection
from research.originator.d_common import ridge_w
from research.quant.common import CONF, DEV, OUT, base_frames, fit_predict, plays

EVAL = list(range(2020, 2027))
SD = 10.9


def add(b: pd.DataFrame) -> pd.DataFrame:
    b = b.copy()
    b["p_tie"] = norm.pdf(b["pred_margin"] / SD) / SD
    b["neutral"] = b["neutral"].astype(float)
    b["conf_game"] = b["conf_game"].astype(float)
    b["venue_x_conf"] = b["venue"] * b["conf_game"]
    return b


EXPS = {"E1 endgame/OT (total)": dict(tf=projection.TOTAL_FEATURES + ["p_tie"], market="total", new=["p_tie"]),
        "E2 site context (total)": dict(tf=projection.TOTAL_FEATURES + ["neutral", "conf_game"], market="total",
                                        new=["neutral", "conf_game"]),
        "E3 conf home court (spread)": dict(mf=projection.MARGIN_FEATURES + ["venue_x_conf"], market="spread",
                                            new=["venue_x_conf"])}


def paired(base, ch, col_y, col_f, groups, n=4000, seed=20261028):
    """MAE(base) - MAE(challenger) (+ = challenger better), date-bootstrap intervals at 95% and 99.2%."""
    v = np.abs(base[col_y] - base[col_f]).to_numpy() - np.abs(ch[col_y] - ch[col_f]).to_numpy()
    u, inv = np.unique(np.asarray(groups), return_inverse=True)
    sv, c = np.bincount(inv, v), np.bincount(inv)
    i = np.random.default_rng(seed).integers(0, len(u), (n, len(u)))
    r = sv[i].sum(1) / c[i].sum(1)
    return float(v.mean()), np.quantile(r, [.025, .975]), np.quantile(r, [.004, .996])


def opener(w, mk, ss):
    p = plays(w[w["season"].isin(ss)], mk)
    x = p.dropna(subset=["win"])
    return len(x), 100 * x["win"].mean(), p["clv"].dropna().mean()


def closewin(w, mk, ss):
    x = plays(w[w["season"].isin(ss)], mk, "close").dropna(subset=["win"])
    return len(x), 100 * x["win"].mean()


def calib(w, mk, ss):
    d = w[w["season"].isin(ss) & ~w["swapped"]].dropna(subset=["home_spread", "total"])
    if mk == "spread":
        return np.polyfit(d["final_margin"] + d["home_spread"], d["margin"] + d["home_spread"], 1)[0]
    return np.polyfit(d["final_total"] - d["total"], d["points"] - d["total"], 1)[0]


def main() -> None:
    train, pred = base_frames()
    train, pred = add(train), add(pred)
    base = fit_predict(train, pred)
    rows, seas, L = [], [], []
    for name, e in EXPS.items():
        ch = fit_predict(train, pred, mf=e.get("mf"), tf=e.get("tf"))
        mk = e["market"]
        y, f = ("margin", "final_margin") if mk == "spread" else ("points", "final_total")
        ev_b, ev_c = base[base["season"].isin(EVAL)], ch[ch["season"].isin(EVAL)]
        gain, ci95, ci99 = paired(ev_b, ev_c, y, f, ev_b["date"])
        per = {s: paired(base[base["season"] == s], ch[ch["season"] == s], y, f, base.loc[base["season"] == s, "date"], n=10)[0]
               for s in EVAL}
        better = sum(v > 0 for v in per.values())
        ob, oc = opener(base, mk, CONF), opener(ch, mk, CONF)
        db, dc = opener(base, mk, DEV), opener(ch, mk, DEV)
        cb, cc = closewin(base, mk, EVAL), closewin(ch, mk, EVAL)
        tr = train[train["season"] < 2027]
        feats = e.get("mf") or e.get("tf")
        coef = ridge_w(tr[feats].to_numpy(float), tr["margin" if mk == "spread" else "points"].to_numpy(float), np.ones(len(tr)))
        coefs = {k: round(float(coef[1 + feats.index(k)]), 3) for k in e["new"]}
        ok = (gain >= 0.010 and ci99[0] > 0 and better >= 5 and oc[2] >= ob[2] - 0.02 and cc[1] >= cb[1])
        verdict = "CREDIBLE CANDIDATE (exploratory)" if ok else ("INCONCLUSIVE" if gain > 0 and ci95[0] > 0 else "ABSENT")
        rows.append({"experiment": name, "market": mk, "new coef (2013-26 fit)": coefs,
                     "MAE base 2020-26": round(float(np.abs(ev_b[y] - ev_b[f]).mean()), 4),
                     "MAE challenger": round(float(np.abs(ev_c[y] - ev_c[f]).mean()), 4),
                     "MAE gain": round(gain, 4), "gain 95%": np.round(ci95, 4).tolist(), "gain 99.2%": np.round(ci99, 4).tolist(),
                     "seasons better (of 7)": better,
                     "opener 2024-26 n/win%/CLV base": f"{ob[0]} / {ob[1]:.2f} / {ob[2]:.3f}",
                     "opener 2024-26 n/win%/CLV chall": f"{oc[0]} / {oc[1]:.2f} / {oc[2]:.3f}",
                     "opener 2015-17 (in-sample) base": f"{db[0]} / {db[1]:.2f} / {db[2]:.3f}",
                     "opener 2015-17 (in-sample) chall": f"{dc[0]} / {dc[1]:.2f} / {dc[2]:.3f}",
                     "close 2020-26 n/win% base": f"{cb[0]} / {cb[1]:.2f}", "close 2020-26 n/win% chall": f"{cc[0]} / {cc[1]:.2f}",
                     "calib slope vs close base/chall": f"{calib(base, mk, EVAL):.3f} / {calib(ch, mk, EVAL):.3f}",
                     "verdict": verdict})
        seas.append({"experiment": name, **{str(s): round(v, 4) for s, v in per.items()}})
    r = pd.DataFrame(rows)
    s = pd.DataFrame(seas)
    r.to_csv(os.path.join(OUT, "exp_result.csv"), index=False)
    s.to_csv(os.path.join(OUT, "exp_by_season.csv"), index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 60)
    txt = r.T.to_string() + "\n\nMAE gain by season (+ = challenger better):\n" + s.to_string(index=False) + "\n"
    open(os.path.join(OUT, "exp_run.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
