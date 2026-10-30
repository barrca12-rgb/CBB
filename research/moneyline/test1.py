"""Moneyline test 1 (PLAN.md): a book's moneyline against its own spread. Research only.

    python -m research.moneyline.test1      # -> research/moneyline/out/test1.txt, test1_bets.csv
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm

from cbb import data, lines_hist

OUT = os.path.join(os.path.dirname(__file__), "out")
DEV, CONFIRM = range(2014, 2018), range(2018, 2025)
EV_MIN, OFF_MARKET, MAX_OVERROUND = 0.03, 3.0, 0.15
L: list[str] = []


def say(s=""):
    L.append(str(s))
    print(s, flush=True)


def implied(ml):
    ml = np.asarray(ml, float)
    with np.errstate(divide="ignore"):
        return np.where(ml > 0, 100 / (ml + 100), -ml / (-ml + 100))


def payout(ml):
    ml = np.asarray(ml, float)
    return np.where(ml > 0, ml / 100, 100 / -ml)


def load(seasons=None) -> pd.DataFrame:
    out = []
    for s in (seasons or list(DEV) + list(CONFIRM)):
        l = pd.read_csv(os.path.join(lines_hist.OUT, f"espn_{s}.csv"))
        l = l[~l["book"].fillna("").isin(lines_hist.NOT_BOOKS | {"", "Opening"})]
        l = l.dropna(subset=["home_spread", "home_ml", "away_ml"])
        l = l[(l["home_ml"].abs() >= 100) & (l["away_ml"].abs() >= 100)]
        g = data.season_games(s)[0][["game_id", "date", "neutral", "home_pts", "away_pts"]].dropna(subset=["home_pts", "away_pts"])
        out.append(l.merge(g, on="game_id").assign(season=s))
    d = pd.concat(out, ignore_index=True).drop_duplicates(["game_id", "book"])
    n0 = len(d)
    # off-market: the book's spread 3+ points from the median of the other books on the game
    grp = d.groupby("game_id")["home_spread"]
    n, tot = grp.transform("count"), grp.transform("sum")
    med_others = d.groupby("game_id")["home_spread"].transform(lambda x: pd.Series(
        [np.median(np.delete(x.to_numpy(), i)) if len(x) > 1 else np.nan for i in range(len(x))], index=x.index))
    off = (n > 1) & ((d["home_spread"] - med_others).abs() >= OFF_MARKET)
    over = implied(d["home_ml"]) + implied(d["away_ml"]) - 1
    bad_vig = (over < 0) | (over > MAX_OVERROUND)
    s = d["home_spread"]
    wrong_side = ((s < 0) & (d["home_ml"] > d["away_ml"])) | ((s > 0) & (d["away_ml"] > d["home_ml"]))
    say(f"Quotes with spread and both moneylines, D-I games with a result, {d['season'].min()}-{d['season'].max()}: {n0:,}")
    say(f"  dropped: off-market spread {int(off.sum()):,}; overround outside 0-15% {int((bad_vig & ~off).sum()):,}; "
        f"moneyline favorite opposite the spread favorite {int((wrong_side & ~off & ~bad_vig).sum()):,}")
    d = d[~off & ~bad_vig & ~wrong_side].copy()
    d["med_spread"] = d.groupby("game_id")["home_spread"].transform("median")
    d["home_win"] = (d["home_pts"] > d["away_pts"]).astype(int)
    d["home_site"] = (~d["neutral"].astype(bool)).astype(int)
    say(f"  clean quotes: {len(d):,} on {d['game_id'].nunique():,} games")
    return d


def fit(games: pd.DataFrame) -> tuple[float, float]:
    """MLE of P(home wins) = Phi((-s + c * home_site) / sigma) on one row per game."""
    s, h, y = games["med_spread"].to_numpy(), games["home_site"].to_numpy(), games["home_win"].to_numpy()

    def nll(t):
        c, logs = t
        p = np.clip(norm.cdf((-s + c * h) / np.exp(logs)), 1e-9, 1 - 1e-9)
        return -np.sum(y * np.log(p) + (1 - y) * np.log(1 - p))
    r = minimize(nll, [0.0, np.log(11.0)], method="Nelder-Mead")
    return float(r.x[0]), float(np.exp(r.x[1]))


def boot(b: pd.DataFrame, n=2000, seed=0) -> tuple[float, float]:
    if not len(b):
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    by = b.groupby(b["date"].astype(str))["profit"].agg(["sum", "count"])
    s, c = by["sum"].to_numpy(), by["count"].to_numpy()
    idx = rng.integers(0, len(by), size=(n, len(by)))
    roi = s[idx].sum(1) / c[idx].sum(1)
    return float(np.percentile(roi, 2.5)), float(np.percentile(roi, 97.5))


def summary(b: pd.DataFrame) -> dict:
    lo, hi = boot(b)
    return {"bets": len(b), "win %": round(100 * b["won"].mean(), 1) if len(b) else None,
            "exp win %": round(100 * b["p"].mean(), 1) if len(b) else None, "avg price": round(float(b["price"].median()), 0) if len(b) else None,
            "units": round(float(b["profit"].sum()), 1), "ROI %": round(100 * float(b["profit"].mean()), 2) if len(b) else None,
            "95% lo": round(100 * lo, 2), "95% hi": round(100 * hi, 2)}


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    d = load()
    games = d.drop_duplicates("game_id")
    c, sigma = fit(games[games["season"].isin(DEV)])
    say(f"\nFit on 2014-2017 ({int(games['season'].isin(DEV).sum()):,} games), frozen: c = {c:+.3f} points, sigma = {sigma:.3f}")
    # each quote, both sides, from the book's own spread
    p_home = norm.cdf((-d["home_spread"] + c * d["home_site"]) / sigma)
    sides = []
    for side, p, ml, won in (("home", p_home, d["home_ml"], d["home_win"]), ("away", 1 - p_home, d["away_ml"], 1 - d["home_win"])):
        x = d[["game_id", "date", "season", "book", "home_spread", "home_ml", "away_ml"]].assign(
            side=side, p=p, price=ml, won=won)
        x["ev"] = x["p"] * payout(x["price"]) - (1 - x["p"])
        sides.append(x)
    q = pd.concat(sides, ignore_index=True)
    q["profit"] = np.where(q["won"] == 1, payout(q["price"]), -1.0)
    sig = q[q["ev"] >= EV_MIN]
    best = sig.sort_values("ev", ascending=False).drop_duplicates(["game_id", "side"])
    best.to_csv(os.path.join(OUT, "test1_bets.csv"), index=False)
    say(f"Quotes x sides: {len(q):,}; signals (EV >= +3%): {len(sig):,}; best per game and side: {len(best):,}")
    # calibration of the fit on the confirm era (all quotes' home side at the median spread)
    gc = games[games["season"].isin(CONFIRM)].copy()
    gc["p"] = norm.cdf((-gc["med_spread"] + c * gc["home_site"]) / sigma)
    gc["bin"] = pd.qcut(gc["p"], 10, duplicates="drop")
    cal = gc.groupby("bin", observed=True).agg(games=("p", "size"), predicted=("p", "mean"), actual=("home_win", "mean")).round(3)
    say("\nCalibration of the spread fit, confirm era 2018-2024 (home side, by decile):")
    say(cal.to_string())
    for era, ss in (("dev 2014-2017 (in-sample fit)", DEV), ("CONFIRM 2018-2024", CONFIRM)):
        say(f"\n== {era} ==")
        for lab, b in (("(ii) best per game/side [primary]", best), ("(i) every signal quote", sig)):
            say(f"{lab}: {summary(b[b['season'].isin(ss)])}")
    cb = best[best["season"].isin(CONFIRM)].copy()
    cb["dog"] = np.where(cb["price"] > 0, "underdog", "favorite")
    cb["band"] = pd.cut(cb["price"], [-1e9, -300, -150, 149.5, 299.5, 1e9],
                        labels=["-300 or shorter", "-299 to -150", "-149 to +149", "+150 to +299", "+300 or longer"])
    cb["spread_band"] = pd.cut(cb["home_spread"].abs(), [-0.1, 2.5, 5.5, 9.5, 14.5, 99], labels=["0-2.5", "3-5.5", "6-9.5", "10-14.5", "15+"])
    for col in ("dog", "band", "spread_band", "book", "season"):
        rows = [{col: k, **summary(v)} for k, v in cb.groupby(col, observed=True)]
        say(f"\nConfirm era by {col}:")
        say(pd.DataFrame(rows).to_string(index=False))
    s = summary(cb)
    dead = s["bets"] < 200 or s["ROI %"] < 1.0 or s["95% lo"] <= 0
    say(f"\nKill rule (confirm, best per game/side): bets {s['bets']} (need 200+), ROI {s['ROI %']}% (need +1%+), "
        f"95% interval [{s['95% lo']}, {s['95% hi']}] (must exclude 0)  =>  {'FAILS: closed' if dead else 'SURVIVES: goes to a live shadow'}")
    open(os.path.join(OUT, "test1.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
