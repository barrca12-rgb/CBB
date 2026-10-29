"""Re-score existing candidates on paired closing-line value (descriptive; nothing is promoted).

Spreads at the ESPN opener: v1 vs lineup v2. Totals at the ESPN opener: v1 vs E2 (neutral + conference terms) and
C2 (v1 - 0.61). Same splits as the v2 backtest: development 2014-15..2016-17 + 2023-24, holdout 2024-25 + 2025-26.
All of these seasons were examined in earlier studies; this re-measures, it does not test anything new.

    python -m research.power.rescore      # -> research/power/out/rescore.txt
"""
from __future__ import annotations

import os

import pandas as pd

from research.persistent_disagreement.common import baseline
from research.persistent_disagreement.score import e2_totals, v2_margin
from research.power.scorecard import noise_table, scorecard

OUT = os.path.join(os.path.dirname(__file__), "out")
SPLITS = {"development 2014-15..2016-17 + 2023-24": [2015, 2016, 2017, 2024], "holdout 2024-25 + 2025-26": [2025, 2026]}
L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def show(sc: dict) -> None:
    say(sc["per_strategy"].round(3).to_string(index=False))
    say("paired vs baseline (totals over all games; 95% date-clustered bootstrap):")
    say(sc["paired"].round(3).to_string(index=False))
    say("all games, result vs the CLOSE regressed on (forecast - close); incremental = on (candidate - v1) given v1:")
    say(sc["beyond_close"].round(3).to_string(index=False))


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    w = baseline()
    w = w[~w["swapped"]].copy()
    v2 = v2_margin()["v2_margin"]
    e2 = e2_totals()
    sp = pd.DataFrame({"date": w["date"], "season": w["season"], "open": w["open_home_spread"], "close": w["home_spread"],
                       "result": w["margin"], "fc_v1": w["final_margin"], "fc_v2": w["game_id"].map(v2)})
    tt = pd.DataFrame({"date": w["date"], "season": w["season"], "open": w["open_total"], "close": w["total"],
                       "result": w["points"], "fc_v1": w["final_total"], "fc_E2": w["game_id"].map(e2),
                       "fc_C2": w["final_total"] - 0.61})
    for lab, seasons in SPLITS.items():
        say(f"\n{'=' * 100}\nSPREADS at the opener, {lab}")
        f = sp[sp["season"].isin(seasons)].dropna(subset=["fc_v2"])
        say("noise of v1's own bets:\n" + noise_table(f, "spread", "v1").round(3).to_string(index=False))
        show(scorecard(f, "spread", ["v1", "v2"], "v1"))
        say(f"\n{'=' * 100}\nTOTALS at the opener, {lab}")
        f = tt[tt["season"].isin(seasons)].dropna(subset=["fc_E2"])
        say("noise of v1's own bets:\n" + noise_table(f, "total", "v1").round(3).to_string(index=False))
        show(scorecard(f, "total", ["v1", "E2", "C2"], "v1"))
    open(os.path.join(OUT, "rescore.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
