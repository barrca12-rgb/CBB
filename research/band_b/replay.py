"""Band B replay on the historical opener record (MODEL_FREEZE.md, Oct 29 entry; FORWARD_TEST_PROTOCOL.md appendix B).

Band B = the frozen v1 projection's edge against the opener of 2.0-2.49 points on a spread or 2.0-2.99 on a total,
plus the live +2% EV rule with the live win-probability rule. Openers at assumed -110 (ESPN's opener has no price),
2014-15..2016-17 and 2023-24..2025-26, swapped records excluded, pushes out of win rates. Also the EV-trim count at
real DraftKings prices on the dated 2024-25 / 2025-26 sample (research/rotation_totals first-observed quotes).

    python -m research.band_b.replay      # -> research/band_b/out/replay.txt
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import run_day
from research.persistent_disagreement.common import baseline

OUT = os.path.join(os.path.dirname(__file__), "out")
ERAS = {"2014-15..2016-17": [2015, 2016, 2017], "2023-24..2025-26": [2024, 2025, 2026]}
BANDS = {"spread": (2.0, 2.5), "total": (2.0, 3.0)}
L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def plays(w: pd.DataFrame, market: str) -> pd.DataFrame:
    if market == "spread":
        d = w.dropna(subset=["open_home_spread", "home_spread"]).copy()
        e = d["final_margin"] + d["open_home_spread"]
        d["side"] = np.where(e > 0, "home", "away")
        d["cover"] = np.sign(e) * (d["margin"] + d["open_home_spread"])
        d["clv"] = np.sign(e) * (d["open_home_spread"] - d["home_spread"])
        d["group"] = np.where(d["neutral"].astype(bool), "neutral", "home site")
    else:
        d = w.dropna(subset=["open_total", "total"]).copy()
        e = d["final_total"] - d["open_total"]
        d["side"] = np.where(e > 0, "over", "under")
        d["cover"] = np.sign(e) * (d["points"] - d["open_total"])
        d["clv"] = np.sign(e) * (d["total"] - d["open_total"])
        d["group"] = np.where(e > 0, "overs", "unders")
    d["edge"] = e.abs()
    d["p"] = [run_day.win_prob(market, x) for x in d["edge"]]
    d["ev110"] = [run_day.ev(p, -110.0) for p in d["p"]]
    return d


def table(d: pd.DataFrame, lo: float, hi: float) -> pd.DataFrame:
    x = d[(d["edge"] >= lo) & (d["edge"] < hi)]
    rows = []
    for g, y in x.groupby("group"):
        dec = y[y["cover"] != 0]
        rows.append({"group": g, "plays": len(y), "win %": round(100 * (dec["cover"] > 0).mean(), 1) if len(dec) else np.nan,
                     "CLV": round(y["clv"].mean(), 2), "pass +2% EV at -110": int((y["ev110"] >= run_day.MIN_EV).sum())})
    return pd.DataFrame(rows)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    w = baseline()
    w = w[~w["swapped"]]
    for mk, (lo, hi) in BANDS.items():
        d = plays(w[w["season"].isin(ERAS["2014-15..2016-17"] + ERAS["2023-24..2025-26"])], mk)
        say(f"\n{mk}s, band B ({lo}-{hi - 0.01:.2f}) at the opener, both eras pooled (target: Oct 26 band table)")
        say(table(d, lo, hi).to_string(index=False))
        for era, ss in ERAS.items():
            say(f"  {era}:")
            say("  " + table(plays(w[w["season"].isin(ss)], mk), lo, hi).to_string(index=False).replace("\n", "\n  "))
        per = d[(d["edge"] >= lo) & (d["edge"] < hi)].groupby("season").size()
        say(f"  plays per season (before the EV rule): {per.to_dict()}")
    # EV trim at real prices: DraftKings first-observed quotes on the dated sample
    rt = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "rotation_totals", "out", "predictions_A_strict.csv"))
    pc = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "persistent_disagreement", "out", "predictions.csv"))
    pc = pc[pc["pool"].str.startswith("C")]
    say("\nEV trim at real DraftKings prices (dated sample, 2025-26 dates 2025-11-08, 2026-01-10, 2026-03-07):")
    t = rt[rt["season"] == 2026]
    e = t["model_total"] - t["dk_total"]
    price = np.where(e > 0, t["over_price"], t["under_price"])
    band = (e.abs() >= 2.0) & (e.abs() < 3.0)
    p = np.array([run_day.win_prob("total", x) for x in e.abs()])
    ok = np.array([run_day.ev(pp, o) for pp, o in zip(p, price)]) >= run_day.MIN_EV
    say(f"  totals: {int(band.sum())} band-B edges, {int((band & ok).sum())} pass the +2% EV rule at the recorded price, "
        f"{int((band & ~ok).sum())} trimmed")
    e = (pc["edge_baseline"]).to_numpy()
    price = np.where(e > 0, pc["price_pos"], pc["price_neg"])
    band = (np.abs(e) >= 2.0) & (np.abs(e) < 2.5)
    p = np.array([run_day.win_prob("spread", abs(x)) for x in e])
    ok = np.array([run_day.ev(pp, o) for pp, o in zip(p, price)]) >= run_day.MIN_EV
    say(f"  spreads: {int(band.sum())} band-B edges, {int((band & ok).sum())} pass, {int((band & ~ok).sum())} trimmed")
    say("\nnote: at -110 the EV rule needs a totals edge of about 2.45+ (win_prob 0.5343); spreads clear it from 2.0.")
    open(os.path.join(OUT, "replay.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
