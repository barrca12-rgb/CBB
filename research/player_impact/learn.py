"""Learning step (PLAN.md): 8 rating variants, gamma fit on 2023-24, validated on 2024-25; freeze.

Reads only seasons 2023-24 and 2024-25 (features built with ratings.main(seasons=[2024, 2025])).

    python -m research.player_impact.learn       # -> out/validation.csv, out/frozen.json, out/learn.txt
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from research.persistent_disagreement.common import baseline
from research.player_impact.ratings import DATA, LAMS, OUT, RHOS

L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def frame(fe: pd.DataFrame, w: pd.DataFrame) -> pd.DataFrame:
    x = w.merge(fe[["game_id", "D_home", "D_away", "known_home", "known_away"]], on="game_id", how="left")
    for c in ("D_home", "D_away"):
        x[c] = x[c].fillna(0.0)
    for c in ("known_home", "known_away"):
        x[c] = x[c].fillna(False).astype(bool)
    x["J"] = (x["D_away"] - x["D_home"]) * x["pred_poss"] / 100.0
    x["resid"] = x["margin"] - x["final_margin"]
    return x


def main() -> None:
    OUT.mkdir(exist_ok=True)
    w = baseline()
    w = w[w["season"].isin([2024, 2025])]
    rows = []
    for lam in LAMS:
        for rho in RHOS:
            fe = pd.read_parquet(DATA / f"features_lam{int(lam)}_rho{rho}.parquet")
            assert not (fe["season"] == 2026).any()
            x = frame(fe, w)
            tr, va = x[x["season"] == 2024], x[x["season"] == 2025]
            g = float((tr["J"] * tr["resid"]).sum() / (tr["J"] ** 2).sum()) if (tr["J"] ** 2).sum() > 0 else 0.0
            mse = float(((va["resid"] - g * va["J"]) ** 2).mean())
            rows.append({"lam": lam, "rho": rho, "gamma_2024": g, "val_mse": mse, "none_mse": float((va["resid"] ** 2).mean()),
                         "J_sd_2025": float(va["J"].std()), "J_nonzero_2025": int((va["J"] != 0).sum()),
                         "coverage_2025": float((va["known_home"] & va["known_away"]).mean())})
            say(f"lambda {lam:g} rho {rho}: gamma(2023-24) {g:+.3f}; 2024-25 MSE {mse:.4f} vs none {rows[-1]['none_mse']:.4f}; "
                f"J sd {rows[-1]['J_sd_2025']:.3f}; coverage {rows[-1]['coverage_2025']:.3f}")
    r = pd.DataFrame(rows)
    r.to_csv(OUT / "validation.csv", index=False)
    best = r.sort_values(["val_mse", "lam"]).iloc[0]
    frozen = {"choice": "none"}
    if best["val_mse"] < best["none_mse"]:
        fe = pd.read_parquet(DATA / f"features_lam{int(best['lam'])}_rho{best['rho']}.parquet")
        x = frame(fe, w)
        g = float((x["J"] * x["resid"]).sum() / (x["J"] ** 2).sum())
        frozen = {"choice": "rapm", "lam": float(best["lam"]), "rho": float(best["rho"]), "gamma": g,
                  "val_mse": float(best["val_mse"]), "none_mse": float(best["none_mse"]), "gamma_fit_seasons": [2024, 2025]}
    say(f"\nfrozen: {json.dumps(frozen)}")
    json.dump(frozen, open(OUT / "frozen.json", "w"), indent=1)
    open(OUT / "learn.txt", "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
