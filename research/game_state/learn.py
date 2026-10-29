"""Learning step (PLAN.md): every variant, both stage-2 families, validation seasons 2019-2025 only; freeze.

Never reads 2025-26: deltas exist only for 2014-2025 at this point, and validation stops at 2025.

    python -m research.game_state.learn     # -> out/validation.csv, out/learn.txt, out/frozen.json
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from research.game_state.common import NAMES, OUT, deltas, forecast, frames, grade, select, shift

VAL = list(range(2019, 2026))
L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def close_units(w: pd.DataFrame, market: str) -> tuple[float, int]:
    d = w[w["season"].isin(VAL) & ~w["swapped"]]
    if market == "spread":
        d = d.dropna(subset=["home_spread"])
        edge, cover = d["final_margin"] + d["home_spread"], d["margin"] + d["home_spread"]
    else:
        d = d.dropna(subset=["total"])
        edge, cover = d["final_total"] - d["total"], d["points"] - d["total"]
    p = np.full(len(d), -110.0)
    bet, side, price = select(edge.to_numpy(), p, p, market)
    return float(grade(side[bet], cover.to_numpy()[bet], price[bet]).sum()), int(bet.sum())


def main() -> None:
    train, pred = frames()
    D = deltas(0, range(2014, 2026))
    assert not (D["season"] == 2026).any()
    pred = pred[pred["season"] <= 2025]
    rows = []
    base_sd = {}
    v = pred["season"].isin(VAL)
    base_sd["margin"], base_sd["total"] = pred.loc[v, "pred_margin"].std(), pred.loc[v, "pred_total"].std()
    for fam in ("F", "R"):
        tr0 = train if fam == "F" else train[train["season"] >= 2014]
        for name in NAMES:
            p_ = shift(pred, D, name)
            t_ = tr0 if fam == "F" else shift(tr0, D, name)
            w = forecast(t_, p_)
            x = w[w["season"].isin(VAL)]
            um, nm = close_units(w, "spread")
            ut, nt = close_units(w, "total")
            vv = p_["season"].isin(VAL)
            rows.append({"family": fam, "variant": name,
                         "margin_mse": float(((x["margin"] - x["final_margin"]) ** 2).mean()),
                         "total_mse": float(((x["points"] - x["final_total"]) ** 2).mean()),
                         "margin_bias": float((x["margin"] - x["final_margin"]).mean()),
                         "total_bias": float((x["points"] - x["final_total"]).mean()),
                         "s1_margin_sd_ratio": float(p_.loc[vv, "pred_margin"].std() / base_sd["margin"]),
                         "s1_total_sd_ratio": float(p_.loc[vv, "pred_total"].std() / base_sd["total"]),
                         "close_spread_units": um, "close_spread_bets": nm, "close_total_units": ut, "close_total_bets": nt,
                         "games": len(x)})
            say(f"{fam} {name:10s} margin MSE {rows[-1]['margin_mse']:.4f}  total MSE {rows[-1]['total_mse']:.4f}  "
                f"sd ratio m {rows[-1]['s1_margin_sd_ratio']:.3f} t {rows[-1]['s1_total_sd_ratio']:.3f}  "
                f"close units spread {um:+.1f} ({nm})  total {ut:+.1f} ({nt})")
    r = pd.DataFrame(rows)
    r.to_csv(os.path.join(OUT, "validation.csv"), index=False)
    order = {n: i for i, n in enumerate(NAMES)}            # tie-break: earlier = smaller adjustment
    frozen = {}
    for market, col, sdc in (("spread", "margin_mse", "s1_margin_sd_ratio"), ("total", "total_mse", "s1_total_sd_ratio")):
        pick = {}
        for fam in ("F", "R"):
            g = r[r["family"] == fam].assign(o=lambda d: d["variant"].map(order)).sort_values([col, "o"])
            best = g.iloc[0]
            ctrl = g[g["variant"] == "none"].iloc[0]
            pick[fam] = {"variant": best["variant"], "val_mse": float(best[col]), "control_mse": float(ctrl[col]),
                         "mse_gain": float(ctrl[col] - best[col]), "scale_ratio": float(best[sdc])}
        sr = pick["R"]["scale_ratio"]
        decision = "R" if not (0.95 <= sr <= 1.05) else "F"
        frozen[market] = {"families": pick, "decision_family": decision,
                          "rule": "F unless R's selected variant changes the stage-1 input SD outside [0.95, 1.05]"}
        say(f"\n{market}: F selects {pick['F']['variant']} (MSE gain {pick['F']['mse_gain']:+.4f}); R selects "
            f"{pick['R']['variant']} (gain vs refit control {pick['R']['mse_gain']:+.4f}, scale ratio {sr:.3f}); "
            f"decision family {decision}")
    json.dump(frozen, open(os.path.join(OUT, "frozen.json"), "w"), indent=1)
    open(os.path.join(OUT, "learn.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
