"""Scoring step (PLAN.md): 2025-26 forecasts for pools A (closing spreads), B (ESPN openers, descriptive) and C
(DraftKings first observed, dated sample) from the frozen choice; written and hashed before any result is joined.

    python -m research.player_impact.score     # -> out/predictions.csv (+ .sha256), out/score.txt
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

from research.persistent_disagreement.common import baseline
from research.persistent_disagreement.score import v2_margin
from research.player_impact import ratings as R

L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def main() -> None:
    fr = json.load(open(R.OUT / "frozen.json"))
    say(f"frozen: {json.dumps(fr)}")
    wall = baseline()
    wall = wall[wall["season"] == 2026].set_index("game_id")          # every 2025-26 game (pool C may include swapped records)
    w = wall[~wall["swapped"]]
    if fr["choice"] == "none":
        fe = pd.DataFrame({"game_id": wall.index, "D_home": 0.0, "D_away": 0.0, "known_home": False, "known_away": False,
                           "DO_home": 0.0, "DO_away": 0.0, "DD_home": 0.0, "DD_away": 0.0})
        gamma = 0.0
    else:
        dbs = {s: R.load(s) for s in R.SEASONS}
        say("load: " + json.dumps({s: v[2] for s, v in dbs.items()}))
        fe = R.run_variant(fr["lam"], fr["rho"], dbs)
        fe = fe[fe["season"] == 2026]
        fe.to_parquet(R.DATA / "features_2026_frozen.parquet", index=False)
        gamma = fr["gamma"]
    fe = fe.set_index("game_id").reindex(wall.index)
    for c in ("D_home", "D_away", "DO_home", "DO_away", "DD_home", "DD_away"):
        fe[c] = fe[c].fillna(0.0)
    known = fe["known_home"].fillna(False).astype(bool) & fe["known_away"].fillna(False).astype(bool)
    J = (fe["D_away"] - fe["D_home"]) * wall["pred_poss"] / 100.0
    T = (-(fe["DO_home"] + fe["DO_away"]) + (fe["DD_home"] + fe["DD_away"])) * wall["pred_poss"] / 100.0   # descriptive
    v2 = v2_margin()
    say(f"lineup v2 frame's v1 margin vs baseline, max difference {(v2['final_margin'].reindex(w.index) - w['final_margin']).abs().max():.2e}")
    base = w["final_margin"]
    cand = base + gamma * J
    preds = []
    for pool, line_col, mask in (("A closing spreads", "home_spread", w["home_spread"].notna()),
                                 ("B ESPN opener spreads", "open_home_spread", w["open_home_spread"].notna() & w["home_spread"].notna())):
        x = w[mask]
        preds.append(pd.DataFrame({"pool": pool, "game_id": x.index, "date": x["date"].dt.strftime("%Y-%m-%d").to_numpy(),
                                   "line": x[line_col].to_numpy(), "price_pos": -110.0, "price_neg": -110.0, "price_kind": "assumed -110",
                                   "coverage": known.reindex(x.index).to_numpy(), "J": J.reindex(x.index).to_numpy(),
                                   "T_desc": T.reindex(x.index).to_numpy(), "fc_baseline": base.reindex(x.index).to_numpy(),
                                   "fc_candidate": cand.reindex(x.index).to_numpy(), "fc_v2": v2["v2_margin"].reindex(x.index).to_numpy()}))
    pc = pd.read_csv(R.OUT.parents[1] / "persistent_disagreement" / "out" / "predictions.csv")
    pc = pc[pc["pool"].str.startswith("C")].set_index("game_id")
    fb = pc["edge_baseline"] - pc["line"]                      # strict-input v1 margin (persistent_disagreement C)
    Jc = J.reindex(pc.index).fillna(0.0)
    assert J.reindex(pc.index).notna().all(), "pool C game without a baseline row"
    preds.append(pd.DataFrame({"pool": "C DraftKings first observed spreads", "game_id": pc.index, "date": pc["date"].to_numpy(),
                               "line": pc["line"].to_numpy(), "price_pos": pc["price_pos"].to_numpy(), "price_neg": pc["price_neg"].to_numpy(),
                               "price_kind": "recorded", "coverage": known.reindex(pc.index).fillna(False).to_numpy(), "J": Jc.to_numpy(),
                               "T_desc": T.reindex(pc.index).to_numpy(), "fc_baseline": fb.to_numpy(),
                               "fc_candidate": (fb + gamma * Jc).to_numpy(), "fc_v2": (pc["edge_existing"] - pc["line"]).to_numpy()}))
    p = pd.concat(preds, ignore_index=True)
    assert not {"home_pts", "away_pts", "margin", "points"} & set(p.columns)
    path = R.OUT / "predictions.csv"
    p.to_csv(path, index=False)
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    (R.OUT / "predictions.csv.sha256").write_text(f"{h}  predictions.csv\n")
    say("opportunities: " + ", ".join(f"{k}: {v}" for k, v in p.groupby("pool").size().items()))
    say("coverage share: " + ", ".join(f"{k[:1]} {v:.3f}" for k, v in p.groupby("pool")["coverage"].mean().items()))
    say(f"J: sd {p['J'].std():.3f}, nonzero {(p['J'] != 0).mean():.3f}; gamma {gamma:+.3f}")
    say(f"predictions.csv sha256 {h}")
    (R.OUT / "score.txt").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
