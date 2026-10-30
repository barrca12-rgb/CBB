"""The 3-4 totals band on live-like inputs (PLAN.md, Oct 31). Research only.

    python -m research.totals_band.run      # -> research/totals_band/out/run.txt, bands.csv
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import run_day
from research.band_b.replay import plays
from research.persistent_disagreement.common import baseline
from research.quant.common import base_frames, fit_predict
from research.originator.d_common import oriented_openers

OUT = os.path.join(os.path.dirname(__file__), "out")
ERAS = {"2014-17": [2015, 2016, 2017], "2024-26": [2024, 2025, 2026]}
BANDS = [(3.0, 3.5, "3-3.49"), (3.5, 4.0, "3.5-3.99"), (4.0, 5.0, "4-4.99"), (5.0, 99.0, "5+"), (3.0, 4.0, "3-3.99")]
L: list[str] = []


def say(s=""):
    L.append(str(s))
    print(s, flush=True)


def cell(y: pd.DataFrame) -> dict:
    dec = y[y["cover"] != 0]
    win = (dec["cover"] > 0).astype(float)
    n = len(win)
    m = float(win.mean()) if n else np.nan
    se = float(np.sqrt(((win - m).groupby(dec["date"].astype(str).to_numpy()).sum() ** 2).sum()) / n) if n > 1 else np.nan
    return {"plays": len(y), "win %": round(100 * m, 1), "95% ±": round(196 * se, 1),
            "ROI % at -110": round(100 * (m * 100 / 110 - (1 - m)), 1), "CLV": round(float(y["clv"].mean()), 2)}


def table(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    rows = []
    for era, ss in ERAS.items():
        d = plays(frame[frame["season"].isin(ss)], "total")
        for lo, hi, name in BANDS:
            y = d[(d["edge"] >= lo) & (d["edge"] < hi)]
            for side in ("all", "overs", "unders"):
                yy = y if side == "all" else y[y["group"] == side]
                rows.append({"frame": label, "era": era, "band": name, "side": side, **cell(yy)})
    return pd.DataFrame(rows)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    live = baseline()
    live = live[~live["swapped"]]
    train, _ = base_frames()
    prod = fit_predict(train, oriented_openers(train.copy()))          # as recorded: game-day crews and KenPom
    prod["swapped"] = False if "swapped" not in prod else prod["swapped"]
    prod = prod.merge(live[["game_id"]], on="game_id")                  # same games as the live-like frame
    prod["date"] = pd.to_datetime(prod["date"])
    t_live, t_prod = table(live, "live-like"), table(prod, "production")
    t = pd.concat([t_live, t_prod], ignore_index=True)
    t.to_csv(os.path.join(OUT, "bands.csv"), index=False)
    say("Totals bands at the ESPN opener. Live-like = crews unknown, KenPom from the day before, the live opening-week rule.")
    say("Production = the same walk-forward fits on the frame as recorded (game-day crews and KenPom), same games.")
    say("Win % with pushes out (95% ± date-clustered); ROI at an assumed -110; CLV = opener to close, points.\n")
    say(t_live.to_string(index=False))
    # check against the Oct 26 table (production frame, both eras pooled)
    d = plays(prod[prod["season"].isin(ERAS["2014-17"] + ERAS["2024-26"])], "total")
    y = d[(d["edge"] >= 3) & (d["edge"] < 4)]
    say(f"\nProduction frame 3-4, both eras: overs {cell(y[y['group'] == 'overs'])}, unders {cell(y[y['group'] == 'unders'])}"
        f"\n  Oct 26 table: overs 56.2% (1,860), CLV +1.10; unders 54.8% (1,561), CLV +0.77")
    # the leak per band: production minus live-like
    k = ["era", "band", "side"]
    m = t_live.merge(t_prod, on=k, suffixes=("_live", "_prod"))
    m["leak win pts"] = (m["win %_prod"] - m["win %_live"]).round(1)
    m["leak CLV"] = (m["CLV_prod"] - m["CLV_live"]).round(2)
    say("\nLeak per band (production minus live-like):")
    say(m[m["side"] == "all"][k + ["plays_live", "win %_live", "win %_prod", "leak win pts", "CLV_live", "CLV_prod", "leak CLV"]].to_string(index=False))
    m.to_csv(os.path.join(OUT, "leak.csv"), index=False)
    # kill rule on 3-3.49
    k3 = t_live[(t_live["band"] == "3-3.49") & (t_live["side"] == "all")].set_index("era")
    pooled = plays(live[live["season"].isin(ERAS["2014-17"] + ERAS["2024-26"])], "total")
    pooled = pooled[(pooled["edge"] >= 3) & (pooled["edge"] < 3.5)]
    clv = float(pooled["clv"].mean())
    fail_win = bool((k3["win %"] <= 53.0).all())
    fail_clv = clv < 0.3
    say(f"\nKill rule on 3-3.49: win % {k3['win %'].to_dict()} (fails only if <= 53.0 in both eras: {fail_win}); "
        f"pooled opener CLV {clv:+.2f} (fails if under +0.3: {fail_clv})  =>  "
        f"{'NOT SUPPORTED' if (fail_win or fail_clv) else 'SUPPORTED: the Oct 26 decision stands on live-like evidence'}")
    # recorded prices: DraftKings first-observed, after the +2% EV rule
    say("\nRecorded DraftKings prices (first-observed quotes, research/rotation_totals), after the +2% EV rule:")
    rt = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "rotation_totals", "out", "predictions_A_strict.csv"))
    pts = live.set_index("game_id")["points"]
    rt["points"] = rt["game_id"].map(pts)
    rows = []
    for season, lab in ((2026, "2025-26"), (2025, "2024-25")):
        r = rt[(rt["season"] == season) & rt["points"].notna() & rt["dk_total"].notna()].copy()
        e = r["model_total"] - r["dk_total"]
        side = np.where(e > 0, "over", "under")
        price = np.where(e > 0, r["over_price"], r["under_price"])
        p = np.array([run_day.win_prob("total", abs(x)) for x in e])
        ok = np.array([run_day.ev(pp, o) for pp, o in zip(p, price)]) >= run_day.MIN_EV
        res = np.sign(e) * (r["points"] - r["dk_total"])
        pay = np.where(price > 0, price / 100, 100 / np.abs(price))
        for lo, hi, name in BANDS[:4]:
            b = ((e.abs() >= lo) & (e.abs() < hi)).to_numpy()
            s = b & ok
            w_, l_ = int((res[s] > 0).sum()), int((res[s] < 0).sum())
            u = float(np.where(res[s] > 0, pay[s], np.where(res[s] < 0, -1.0, 0.0)).sum())
            rows.append({"season": lab, "band": name, "edges": int(b.sum()), "pass +2% EV": int(s.sum()),
                         "W-L": f"{w_}-{l_}", "units": round(u, 2), "median price": float(np.median(price[s])) if s.any() else None})
    say(pd.DataFrame(rows).to_string(index=False))
    say("  (3 dates a season; too few plays to read a win rate)")
    open(os.path.join(OUT, "run.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
