"""Early-season underdog spread plays (PLAN.md, pre-registered Nov 5, 2026). Research only.

    python -m research.early_dogs.backtest     # -> out/results.txt, out/plays.csv
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.persistent_disagreement.common import baseline, payout

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
AUD = os.path.join(HERE, "..", "..", "audit", "out")
PERIODS = {"2014-17": [2014, 2015, 2016, 2017], "2024-26": [2024, 2025, 2026]}
EARLY, FLOOR, V1 = 20, 2.0, 2.5
WIN = payout(-110.0)
L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def plays(w: pd.DataFrame) -> pd.DataFrame:
    d = w.dropna(subset=["open_home_spread", "final_margin", "margin"]).copy()
    if "swapped" in d:
        d = d[~d["swapped"]]
    d["date"] = pd.to_datetime(d["date"])
    d["day"] = (d["date"] - d.groupby("season")["date"].transform("min")).dt.days
    e = d["final_margin"] + d["open_home_spread"]
    d = d[e.abs() >= FLOOR].copy()
    e = e[e.abs() >= FLOOR]
    side = np.sign(e)
    d["edge"] = e.abs()
    d["side"] = side
    d["bet_line"] = side * d["open_home_spread"]
    d["grp"] = np.where(d["bet_line"] > 0, "underdog", np.where(d["bet_line"] < 0, "favorite", "pick"))
    d["cover"] = side * (d["margin"] + d["open_home_spread"])
    d["clv"] = side * (d["open_home_spread"] - d["home_spread"])
    d["stake"] = np.where(d["edge"] >= V1, 1.0, 0.5)
    d["units"] = np.where(d["cover"] > 0, d["stake"] * WIN, np.where(d["cover"] < 0, -d["stake"], 0.0))
    d["own_agrees"] = side * (d["pred_margin"] + d["open_home_spread"]) > 0
    for k in ("kp", "bt"):
        if f"{k}_margin" in d:
            d[f"{k}_agrees"] = side * (d[f"{k}_margin"] + d["open_home_spread"]) > 0
    d["early"] = d["day"] <= EARLY
    d["v1_drop"] = d["early"] & (d["grp"] == "underdog") & ~d["own_agrees"]
    return d


def summ(x: pd.DataFrame) -> dict:
    dec = x[x["cover"] != 0]
    return {"plays": len(x), "win %": round(100 * (dec["cover"] > 0).mean(), 1) if len(dec) else np.nan,
            "move": round(x["clv"].mean(), 2) if len(x) else np.nan, "units": round(x["units"].sum(), 1)}


def row(lab, x):
    s = summ(x)
    say(f"    {lab:44s} plays {s['plays']:5d}  win {s['win %']:5.1f}%  move {s['move']:+.2f}  units {s['units']:+7.1f}")
    return s


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    w = baseline()
    say("Early-season underdog spread plays (PLAN.md, pre-registered Nov 5, 2026). Openers at an assumed -110.")
    allp, removed, harm = [], [], {}
    for name, ss in PERIODS.items():
        p = plays(w[w["season"].isin(ss)])
        allp.append(p.assign(period=name))
        e, dog = p[p["early"]], p[p["early"] & (p["grp"] == "underdog")]
        say(f"\n{name}")
        say("  Early (days 0-20) spread plays:")
        row("favorites", e[e["grp"] == "favorite"])
        row("underdogs (V0)", dog)
        row("underdogs kept by V1 (own rating agrees)", dog[~dog["v1_drop"]])
        row("underdogs removed by V1", dog[dog["v1_drop"]])
        removed.append(dog[dog["v1_drop"]])
        say("  Early underdogs by who is on our side:")
        for keys, x in dog.groupby(["own_agrees", "kp_agrees", "bt_agrees"]):
            row(f"own {'Y' if keys[0] else 'n'} / KenPom {'Y' if keys[1] else 'n'} / Barttorvik {'Y' if keys[2] else 'n'}", x)
        say("  Totals:")
        a = row("early spreads, V0", e)
        b = row("early spreads, V1", e[~e["v1_drop"]])
        row("full-season spreads, V0", p)
        row("full-season spreads, V1", p[~p["v1_drop"]])
        harm[name] = b["units"] >= a["units"]

    r = pd.concat(removed)
    kept = pd.concat([x[x["early"] & (x["grp"] == "underdog") & ~x["v1_drop"]] for x in allp])
    rs, ks = summ(r), summ(kept)
    enough = rs["plays"] >= 60
    weak = rs["win %"] < 52.4 and rs["move"] < ks["move"]
    say(f"\nPooled: removed {rs}, kept underdogs {ks}")
    if not enough:
        verdict = "too few to tell"
    else:
        verdict = "PASS: propose V1 to Chad" if (weak and all(harm.values())) else "does not pass: no proposal"
    say(f"Proposal rule: enough plays {'yes' if enough else 'no'} ({rs['plays']}); removed plays weak "
        f"{'yes' if weak else 'no'}; no harm {harm} -> {verdict}")

    # V2: stage 2 without Barttorvik (own-ratings study frames, 2015-2026)
    say("\nV2 (secondary): stage 2 refit without Barttorvik, early underdog plays (audit/out frames, 2015-2026)")
    base, nobt = (pd.read_pickle(os.path.join(AUD, f)) for f in ("wf_own_base.pkl", "wf_own_no_bt.pkl"))
    for name, ss in PERIODS.items():
        say(f"  {name}:")
        for lab, f in (("with Barttorvik (base)", base), ("without Barttorvik", nobt)):
            p = plays(f[f["season"].isin(ss)])
            e = p[p["early"]]
            row(f"{lab}: early underdogs", e[e["grp"] == "underdog"])
            row(f"{lab}: early favorites", e[e["grp"] == "favorite"])
            row(f"{lab}: all early spreads", e)

    pd.concat(allp).drop(columns=[c for c in ("pred_poss",) if c in allp[0]]).to_csv(os.path.join(OUT, "plays.csv"), index=False)
    open(os.path.join(OUT, "results.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
