"""The flipped idea (flip/PLAN.md): bet the spread when a book's own moneyline disagrees with it. Research only.

    python -m research.moneyline.flip.run      # -> research/moneyline/flip/out/run.txt, bets.csv
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
from scipy.stats import norm

from research.moneyline import test1 as t1
from research.moneyline.devig_methods import implied, shin

OUT = os.path.join(os.path.dirname(__file__), "out")
FLOOR, DEV, HOLD = list(range(2014, 2018)), list(range(2018, 2022)), list(range(2022, 2027))
C, SIGMA = 0.092, 10.422               # the frozen 2014-17 conversion from test 1, not re-fit
L: list[str] = []
t1.L = L
say = t1.say


def summary(b: pd.DataFrame) -> dict:
    dec = b[b["cover"] != 0]
    w = int((dec["cover"] > 0).sum())
    lo, hi = t1.boot(b.assign(profit=b["units"])) if len(b) else (np.nan, np.nan)
    return {"bets": len(b), "W-L-P": f"{w}-{len(dec) - w}-{len(b) - len(dec)}",
            "win %": round(100 * w / len(dec), 1) if len(dec) else None,
            "ROI % at -110": round(100 * float(b["units"].mean()), 2) if len(b) else None,
            "95% lo": round(100 * lo, 2), "95% hi": round(100 * hi, 2)}


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    d = t1.load(FLOOR + DEV + HOLD)
    d["p_home"] = shin(implied(d["home_ml"]), implied(d["away_ml"]))[0]
    d["implied_spread"] = C * d["home_site"] - SIGMA * norm.ppf(d["p_home"].clip(1e-6, 1 - 1e-6))
    d["gap"] = d["home_spread"] - d["implied_spread"]          # > 0: the moneyline rates home stronger than the spread
    f = d[d["season"].isin(FLOOR)]
    say(f"\n1. Inversion noise floor, 2014-17 ({len(f):,} quotes): mean |implied spread - book spread| "
        f"{f['gap'].abs().mean():.2f} pts, median {f['gap'].abs().median():.2f}, mean signed {f['gap'].mean():+.2f}")
    say("\n2. Gap distribution by season (share of quotes):")
    rows = []
    for s, x in d.groupby("season"):
        a = x["gap"].abs()
        rows.append({"season": s, "quotes": len(x), "books": x["book"].nunique(), "mean |gap|": round(a.mean(), 2),
                     "0.5+ %": round(100 * (a >= 0.5).mean(), 1), "1+ %": round(100 * (a >= 1).mean(), 1), "2+ %": round(100 * (a >= 2).mean(), 1)})
    say(pd.DataFrame(rows).to_string(index=False))
    bk = d[d["season"].isin(DEV + HOLD)].groupby("book")["gap"].agg(quotes="size", mean_abs=lambda g: g.abs().mean(),
                                                                       share_1=lambda g: 100 * (g.abs() >= 1).mean())
    say("\n   by book (2018-2026):\n" + bk.round(2).sort_values("quotes", ascending=False).to_string())
    # the consensus closing spread from the OTHER books on the game
    g = d.groupby("game_id")["home_spread"]
    d["consensus_others"] = g.transform(lambda x: pd.Series(
        [np.median(np.delete(x.to_numpy(), i)) if len(x) > 1 else np.nan for i in range(len(x))], index=x.index))
    d["margin"] = d["home_pts"] - d["away_pts"]

    def bets(thr: float) -> pd.DataFrame:
        x = d[d["gap"].abs() >= thr].copy()
        x = x.reindex(x["gap"].abs().sort_values(ascending=False).index).drop_duplicates("game_id")
        x["side"] = np.where(x["gap"] > 0, "home", "away")
        sgn = np.where(x["side"] == "home", 1, -1)
        x["cover"] = sgn * (x["margin"] + x["home_spread"])
        x["units"] = np.where(x["cover"] > 0, 100 / 110, np.where(x["cover"] < 0, -1.0, 0.0))
        x["cover_vs_consensus"] = sgn * (x["margin"] + x["consensus_others"])
        side_spread = sgn * x["home_spread"]
        x["fav_dog"] = np.where(side_spread < 0, "favorite", np.where(side_spread > 0, "underdog", "pick'em"))
        x["gap_band"] = pd.cut(x["gap"].abs(), [0, 1, 2, 99], right=False, labels=["<1", "1-2", "2+"])
        return x
    b = bets(1.0)
    b.to_csv(os.path.join(OUT, "bets.csv"), index=False)
    for era, ss in (("DEVELOPMENT 2018-21", DEV), ("HOLDOUT 2022-26", HOLD)):
        x = b[b["season"].isin(ss)]
        say(f"\n3. {era}, |gap| 1+, one bet per game at the book's spread, -110 assumed: {summary(x)}")
        for col in ("gap_band", "fav_dog", "season"):
            say(f"   by {col}:\n" + pd.DataFrame([{col: k, **summary(v)} for k, v in x.groupby(col, observed=True)]).to_string(index=False))
        say("   by book (10+ bets):\n" + pd.DataFrame([{"book": k, **summary(v)} for k, v in x.groupby("book") if len(v) >= 10]).to_string(index=False))
        for thr in (0.5, 1.5):
            say(f"   robustness, |gap| {thr}+: {summary(bets(thr).query('season in @ss'))}")
        c = x.dropna(subset=["consensus_others"])
        dec = c[c["cover_vs_consensus"] != 0]
        say(f"   4. beyond the close: against the other books' median spread ({len(c):,} bets with one): "
            f"side wins {100 * (dec['cover_vs_consensus'] > 0).mean():.1f}% of {len(dec):,} decided"
            if len(dec) else "   4. beyond the close: no other books on these games")
    h = b[b["season"].isin(HOLD)]
    dec = h[h["cover"] != 0]
    win = 100 * (dec["cover"] > 0).mean() if len(dec) else 0
    per = h.groupby("season").size().reindex(HOLD, fill_value=0)
    dead = win < 53.0 or per.min() < 150
    say(f"\nKill rule (holdout, 1-point gap): win {win:.1f}% (need 53%+); bets per season {per.to_dict()} (need 150+ each)"
        f"  =>  {'FAILS: closed' if dead else 'SURVIVES: close-time spread play, Mar 14 write-up'}")
    open(os.path.join(OUT, "run.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
