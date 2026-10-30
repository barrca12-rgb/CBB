"""Test 2 re-run with a proper devig and a price band (devig/PLAN.md). Research only.

    python -m research.moneyline.devig.run      # -> research/moneyline/devig/out/run.txt, bets.csv
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.moneyline import test1 as t1
from research.moneyline.devig_methods import METHODS, implied

OUT = os.path.join(os.path.dirname(__file__), "out")
DEV, HOLD = [2021, 2022, 2023], [2024, 2025, 2026]
GAP, LO, HI, MIN_OTHERS = 0.03, -200, 200, 3
BANDS = ([-1e9, -300, -150, 149.5, 299.5, 1e9], ["-300 or shorter", "-299 to -150", "-149 to +149", "+150 to +299", "+300 or longer"])
L: list[str] = []
t1.L = L
say = t1.say


def sides(d: pd.DataFrame, col_home: str) -> pd.DataFrame:
    """One row per quote and side, with that side's price, devigged probability (col_home for home) and result."""
    out = []
    for side in ("home", "away"):
        out.append(d[["game_id", "date", "season", "book", "home_spread"]].assign(
            side=side, price=d[f"{side}_ml"].to_numpy(),
            p=d[col_home].to_numpy() if side == "home" else 1 - d[col_home].to_numpy(),
            won=d["home_win"].to_numpy() if side == "home" else 1 - d["home_win"].to_numpy()))
    return pd.concat(out, ignore_index=True)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    d = t1.load(DEV + HOLD)
    ih, ia = implied(d["home_ml"]), implied(d["away_ml"])
    for name, f in METHODS.items():
        d[f"p_{name}"] = f(ih, ia)[0]
    # 1. calibration by price band, every method; choose on 2021-23 Brier only
    say("\n1. Calibration of each devig method by the side's price band (all clean quotes, both sides)")
    brier = {}
    for name in METHODS:
        s = sides(d, f"p_{name}")
        s["band"] = pd.cut(s["price"], *BANDS)
        for lab, ss in (("2021-23", DEV), ("2024", [2024])):
            x = s[s["season"].isin(ss)]
            if lab == "2021-23":
                brier[name] = float(((x["p"] - x["won"]) ** 2).mean())
            t = x.groupby("band", observed=True).agg(quotes=("p", "size"), devigged=("p", "mean"), won=("won", "mean"))
            t["gap pts"] = 100 * (t["won"] - t["devigged"])
            say(f"\n  {name}, {lab}:\n" + t.round(4).to_string())
    method = min(brier, key=brier.get)
    say("\n  2021-23 Brier score: " + ", ".join(f"{k} {v:.6f}" for k, v in brier.items()) + f"  =>  frozen method: {method}")
    # 2. reference: median devigged probability of the OTHER books on the game (3+ required)
    p = d[f"p_{method}"]
    g = d.assign(p=p).groupby("game_id")["p"]
    d["others"] = g.transform("count") - 1
    d["ref_home"] = g.transform(lambda x: pd.Series(
        [np.median(np.delete(x.to_numpy(), i)) if len(x) > 1 else np.nan for i in range(len(x))], index=x.index))
    d["p_home"] = p
    q = sides(d, "p_home")
    q["ref"] = np.concatenate([d["ref_home"].to_numpy(), 1 - d["ref_home"].to_numpy()])
    q["others"] = np.concatenate([d["others"].to_numpy(), d["others"].to_numpy()])
    q = q[q["others"] >= MIN_OTHERS]
    for s in HOLD[1:]:
        say(f"\n  {s}: {int((d['season'] == s).sum()):,} clean quotes but {int(((d['season'] == s) & (d['others'] >= MIN_OTHERS)).sum())} "
            f"with {MIN_OTHERS}+ other books: no reference possible (one book per game in ESPN's history)")
    # 3. signal: the book's own devigged probability 3+ points below the reference, price -200 to +200
    q["gap"] = q["ref"] - q["p"]
    sig = q[(q["gap"] >= GAP) & (q["price"] >= LO) & (q["price"] <= HI)].copy()
    sig["profit"] = np.where(sig["won"] == 1, t1.payout(sig["price"]), -1.0)
    best = sig.sort_values("gap", ascending=False).drop_duplicates(["game_id", "side"]).copy()
    best["fav_dog"] = np.where(best["price"] < 0, "favorite", "underdog")
    best["band"] = pd.cut(best["price"], [-200.5, -120.5, 120, 200.5], labels=["-200 to -121", "-120 to +120", "+121 to +200"])
    best.to_csv(os.path.join(OUT, "bets.csv"), index=False)
    say(f"\n3. Signals (3+ points under the other books, price -200 to +200): {len(sig):,}; best per game and side: {len(best):,}")
    dev = best[best["season"].isin(DEV)]
    say("\nDevelopment 2021-23, best per game and side: " + str(t1.summary(dev)))
    sig_dev = sig[sig["season"].isin(DEV)]
    say("Development 2021-23, every signal quote: " + str(t1.summary(sig_dev.assign(p=sig_dev["p"]))))
    for col in ("fav_dog", "band", "book", "season"):
        say(f"\n  development by {col}:")
        say(pd.DataFrame([{col: k, **t1.summary(v)} for k, v in dev.groupby(col, observed=True)]).to_string(index=False))
    # candidate structures, fixed in the plan; the frozen one: highest dev ROI with 300+ bets in every dev season
    cands = {"all signals": lambda x: x, "favorites only": lambda x: x[x["fav_dog"] == "favorite"],
             "underdogs only": lambda x: x[x["fav_dog"] == "underdog"],
             "band -200 to -121": lambda x: x[x["band"] == "-200 to -121"],
             "band -120 to +120": lambda x: x[x["band"] == "-120 to +120"],
             "band +121 to +200": lambda x: x[x["band"] == "+121 to +200"]}
    rows = []
    for name, f in cands.items():
        x = f(dev)
        per = x.groupby("season").size().reindex(DEV, fill_value=0)
        rows.append({"structure": name, **t1.summary(x), "min bets/season": int(per.min()), "qualifies": bool(per.min() >= 300)})
    ct = pd.DataFrame(rows)
    say("\nCandidate structures, development 2021-23:")
    say(ct.to_string(index=False))
    ok = ct[ct["qualifies"]]
    if not len(ok):
        say("\nNo candidate has 300+ bets in every development season  =>  FAILS at development: closed")
        open(os.path.join(OUT, "run.txt"), "w").write("\n".join(L) + "\n")
        return
    frozen = ok.sort_values("ROI %", ascending=False).iloc[0]["structure"]
    say(f"\nFrozen structure: {frozen}")
    hold = cands[frozen](best[best["season"] == 2024])
    s = t1.summary(hold)
    say(f"\nHOLDOUT 2024 (the only holdout season with a reference), {frozen}: {s}")
    say(pd.DataFrame([{"book": k, **t1.summary(v)} for k, v in hold.groupby("book")]).to_string(index=False))
    dead = s["ROI %"] < 2.0 or s["95% lo"] <= 0 or s["bets"] < 300
    say(f"\nKill rule: ROI {s['ROI %']}% (need +2%+), 95% interval [{s['95% lo']}, {s['95% hi']}] (must exclude 0), "
        f"{s['bets']} bets in 2024 (need 300+)  =>  {'FAILS: closed' if dead else 'SURVIVES: close-side price-selection layer, Mar 14 list'}")
    open(os.path.join(OUT, "run.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
