"""Step 2a: is the historical edge forecasting, price selection, or both? (existing ESPN multi-book data)

Predeclared specification (written before any result was computed; every later change goes to LOG.md):

Data
  * Per-book numbers from ESPN (data/lines/espn_<season>.csv). Era "close" (2014-2023): each book's last line;
    the bet is at that book's closing number. Era "open" (2024): each book's own opening number; graded on it,
    line value measured to the all-book consensus close. 2025-26 carry one book per game and are not usable.
  * Book families: state and brand variants merged (e.g. every "Caesars Sportsbook (...)" is one family), so a
    book never appears in its own reference. Projection services (lines_hist.NOT_BOOKS) and "Opening" excluded.
    A family's number is the median of its variants. A family number more than 5 (spreads) or 10 (totals)
    points from the game's median is dropped (as lines_hist.consensus). Games need 3+ families.
  * Model: the frozen model's live-like walk-forward numbers (audit/out/wf_live_approx.pkl: crews 0, KenPom from
    the day before), final_margin and final_total.

Signals (the current rule without prices): for each game and market, every family whose number gives the model an
edge of 2.5+ (spreads) or 3+ (totals) qualifies; the signal is the family with the largest edge (ties: family
name order). Side = the model's side at that number.

Decomposition, points in the bettor's favour, reference = median of every OTHER family's number:
  D = model deviation from the reference (the edge the model would have against the reference itself)
  Q = the bet book's quote advantage over the reference.   D + Q = the signal's edge.

Cells (fixed before results): model "opposes" the market if D >= the market's threshold (2.5 / 3), else "agrees";
quote "favourable" if Q >= 0.5 points, else "ordinary".

Outcomes: win % (pushes excluded), ROI at an ASSUMED -110 (ESPN carries no spread or total prices: labelled
assumed), line value to the consensus close (open era only). Uncertainty: date-clustered bootstrap (5,000 draws).

Benchmarks: (1) the current rule (all signals); (2) market only, no model: for each game and market, the family
with the largest quote advantage over the others' median, bet when that advantage is >= 1 point.

Joint fit: logistic regression of win on D, Q and market dispersion (std of family numbers), per market and era.
Time to tip is not available in ESPN data (no timestamps): stated, not controlled.

    python -m research.market.s2a_decompose
"""
from __future__ import annotations

import os
import re

import numpy as np
import pandas as pd

from cbb import lines_hist

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(os.path.dirname(__file__), "out")
THR = {"spread": 2.5, "total": 3.0}
DROP = {"spread": 5.0, "total": 10.0}
FAV_Q = 0.5
MKT_ONLY_Q = 1.0
N_BOOT, SEED = 5000, 20261026
ERAS = {"close": list(range(2014, 2024)), "open": [2024]}


def family(book: str) -> str:
    b = re.sub(r"\(.*?\)", "", str(book)).lower().replace("'", "")
    b = re.sub(r"sportsbook|sports book|\.ag|\.eu|\.lv|\.com", "", b).strip()
    if b.startswith("caesar") or b.startswith("william hill"):
        return "caesars"
    return b.split()[0] if b else str(book).lower()


def book_numbers(season: int, era: str) -> pd.DataFrame:
    l = pd.read_csv(os.path.join(lines_hist.OUT, f"espn_{season}.csv"))
    l = l[~l["book"].fillna("").isin(lines_hist.NOT_BOOKS | {"", "Opening"}) & ~l["book"].fillna("").str.contains("live", case=False)]
    l["family"] = l["book"].map(family)
    cols = {"close": ("home_spread", "total"), "open": ("open_home_spread", "open_total")}[era]
    out = []
    for mk, col in zip(("spread", "total"), cols):
        x = l[["game_id", "family", col]].dropna().rename(columns={col: "num"})
        if mk == "total":
            x = x[x["num"] > 0]
        x = x.groupby(["game_id", "family"], as_index=False)["num"].median()
        med = x.groupby("game_id")["num"].transform("median")
        x = x[(x["num"] - med).abs() <= DROP[mk]]
        x = x[x.groupby("game_id")["family"].transform("nunique") >= 3]
        out.append(x.assign(market=mk))
    return pd.concat(out, ignore_index=True)


def consensus_close(season: int) -> pd.DataFrame:
    c = lines_hist.consensus(pd.read_csv(os.path.join(lines_hist.OUT, f"espn_{season}.csv")))
    return c[["game_id", "home_spread", "total"]].rename(columns={"home_spread": "close_spread", "total": "close_total"})


def loo(x: pd.DataFrame) -> pd.Series:
    """Median of every other family's number, per row."""
    out = np.empty(len(x))
    for _, idx in x.groupby("game_id").indices.items():
        v = x["num"].to_numpy()[idx]
        for k, i in enumerate(idx):
            out[i] = np.median(np.delete(v, k))
    return pd.Series(out, index=x.index)


def oriented(x: pd.DataFrame, model: pd.Series) -> pd.DataFrame:
    """Per family row: the model's side at that number, its edge, D and Q, all from the bettor's side."""
    mk = x["market"].iloc[0]
    n, r = x["num"], x["ref"]
    if mk == "spread":
        e_home = model + n
        side = np.where(e_home > 0, "home", "away")
        sgn = np.where(side == "home", 1, -1)
        edge = sgn * e_home
        d = sgn * (model + r)
        q = sgn * (n - r)
    else:
        e_over = model - n
        side = np.where(e_over > 0, "over", "under")
        sgn = np.where(side == "over", 1, -1)
        edge = sgn * e_over
        d = sgn * (model - r)
        q = sgn * (r - n)
    return x.assign(side=side, edge=edge, D=d, Q=q)


def grade(df: pd.DataFrame) -> pd.Series:
    mk = df["market"]
    hs, as_ = df["home_pts"], df["away_pts"]
    m = np.where(mk == "spread", np.where(df["side"] == "home", hs - as_ + df["num"], as_ - hs - df["num"]),
                 np.where(df["side"] == "over", hs + as_ - df["num"], df["num"] - hs - as_))
    return pd.Series(np.where(m > 0, "W", np.where(m < 0, "L", "P")), index=df.index)


def line_value(df: pd.DataFrame) -> pd.Series:
    """Open era: points the consensus close moved toward the bet from the bet number."""
    sp = df["market"] == "spread"
    lv_sp = np.where(df["side"] == "home", df["num"] - df["close_spread"], df["close_spread"] - df["num"])
    lv_to = np.where(df["side"] == "over", df["close_total"] - df["num"], df["num"] - df["close_total"])
    return pd.Series(np.where(sp, lv_sp, lv_to), index=df.index)


def boot(v, dates) -> dict:
    d = pd.DataFrame({"v": np.asarray(v, float), "d": np.asarray(dates)}).dropna()
    if d["d"].nunique() < 2:
        return {"n": len(d), "mean": float(d["v"].mean()) if len(d) else np.nan, "se": np.nan}
    g = d.groupby("d")["v"].agg(["sum", "count"]).to_numpy()
    idx = np.random.default_rng(SEED).integers(0, len(g), size=(N_BOOT, len(g)))
    s = g[idx].sum(axis=1)
    draws = s[:, 0] / s[:, 1]
    return {"n": len(d), "mean": float(d["v"].mean()), "se": float(draws.std(ddof=1)),
            "lo95": float(np.quantile(draws, .025)), "hi95": float(np.quantile(draws, .975))}


def summarize(b: pd.DataFrame, era: str) -> dict:
    dec = b[b["res"] != "P"]
    win = (dec["res"] == "W").astype(float)
    u = np.where(b["res"] == "W", 100 / 110, np.where(b["res"] == "L", -1.0, 0.0))
    r = {"bets": len(b), "win%": 100 * win.mean() if len(dec) else np.nan,
         "win% se (date-clustered)": 100 * boot(win, dec["date"])["se"],
         "ROI% at assumed -110": 100 * boot(u, b["date"])["mean"],
         "ROI% se": 100 * boot(u, b["date"])["se"]}
    if era == "open":
        lv = boot(b["lv"], b["date"])
        r.update({"line value pts": lv["mean"], "line value se": lv["se"]})
    return r


def logit(X: np.ndarray, y: np.ndarray, iters: int = 50) -> tuple[np.ndarray, np.ndarray]:
    """Plain Newton-Raphson logistic regression with an intercept; returns coefficients and their SEs."""
    X = np.column_stack([np.ones(len(X)), X])
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ b))
        W = p * (1 - p)
        H = X.T @ (X * W[:, None])
        b_new = b + np.linalg.solve(H, X.T @ (y - p))
        if np.max(np.abs(b_new - b)) < 1e-8:
            b = b_new
            break
        b = b_new
    p = 1 / (1 + np.exp(-X @ b))
    cov = np.linalg.inv(X.T @ (X * (p * (1 - p))[:, None]))
    return b, np.sqrt(np.diag(cov))


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    w = pd.read_pickle(os.path.join(ROOT, "audit", "out", "wf_live_approx.pkl"))
    w = w[["game_id", "season", "date", "home_pts", "away_pts", "final_margin", "final_total"]].dropna()
    signals, mkt_only, rows = [], [], []
    for era, seasons in ERAS.items():
        for s in seasons:
            x = book_numbers(s, era)
            x = x.merge(w[w["season"] == s], on="game_id")
            if era == "open":
                x = x.merge(consensus_close(s), on="game_id", how="left")
            for mk in ("spread", "total"):
                m = x[x["market"] == mk].sort_values(["game_id", "family"]).reset_index(drop=True)
                if not len(m):
                    continue
                m["ref"] = loo(m)
                disp = m.groupby("game_id")["num"].transform("std")
                m = oriented(m, m["final_margin"] if mk == "spread" else m["final_total"]).assign(disp=disp, era=era)
                q = m[m["edge"] >= THR[mk]].sort_values(["game_id", "edge", "family"], ascending=[True, False, True])
                signals.append(q.drop_duplicates("game_id"))
                # market-only benchmark: the family furthest from the others, on its favourable side, no model
                mm = m.assign(adv=(m["num"] - m["ref"]).abs())
                mm = mm.sort_values(["game_id", "adv", "family"], ascending=[True, False, True]).drop_duplicates("game_id")
                mm = mm[mm["adv"] >= MKT_ONLY_Q].copy()
                if mk == "spread":   # home bettor wants a higher number than the others
                    mm["side"] = np.where(mm["num"] > mm["ref"], "home", "away")
                else:
                    mm["side"] = np.where(mm["num"] < mm["ref"], "over", "under")
                mkt_only.append(mm)
            print(era, s, "done", flush=True)
    sig = pd.concat(signals, ignore_index=True)
    sig["res"] = grade(sig)
    sig["opposes"] = np.where(sig["D"] >= sig["market"].map(THR), "model opposes market", "model agrees")
    sig["quote"] = np.where(sig["Q"] >= FAV_Q, "favourable quote", "ordinary quote")
    if "close_spread" in sig:
        sig["lv"] = line_value(sig)
    mo = pd.concat(mkt_only, ignore_index=True)
    mo["res"] = grade(mo)
    if "close_spread" in mo:
        mo["lv"] = line_value(mo)
    sig.to_csv(os.path.join(OUT, "s2a_signals.csv"), index=False)

    for era in ERAS:
        for mk in ("spread", "total"):
            b = sig[(sig["era"] == era) & (sig["market"] == mk)]
            rows.append({"era": era, "market": mk, "group": "current rule (all signals)", **summarize(b, era)})
            for (o, qq), g in b.groupby(["opposes", "quote"]):
                rows.append({"era": era, "market": mk, "group": f"{o} / {qq}", **summarize(g, era)})
            bm = mo[(mo["era"] == era) & (mo["market"] == mk)]
            rows.append({"era": era, "market": mk, "group": f"market only (quote {MKT_ONLY_Q:g}+ pts off the others, no model)",
                         **summarize(bm, era)})
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(OUT, "s2a_cells.csv"), index=False)

    fits = []
    for era in ERAS:
        for mk in ("spread", "total"):
            b = sig[(sig["era"] == era) & (sig["market"] == mk) & (sig["res"] != "P")].dropna(subset=["disp"])
            if len(b) < 50:
                continue
            X = b[["D", "Q", "disp"]].to_numpy(float)
            coef, se = logit(X, (b["res"] == "W").to_numpy(float))
            fits.append({"era": era, "market": mk, "n": len(b),
                         **{f"{k} coef": c for k, c in zip(["intercept", "D", "Q", "dispersion"], coef)},
                         **{f"{k} z": c / s for k, c, s in zip(["intercept", "D", "Q", "dispersion"], coef, se)}})
            if era == "open":
                y = b["lv"].to_numpy(float)
                ok = ~np.isnan(y)
                A = np.column_stack([np.ones(ok.sum()), X[ok]])
                beta, *_ = np.linalg.lstsq(A, y[ok], rcond=None)
                fits[-1].update({f"line value OLS {k}": v for k, v in zip(["intercept", "D", "Q", "dispersion"], beta)})
    f = pd.DataFrame(fits)
    f.to_csv(os.path.join(OUT, "s2a_fit.csv"), index=False)
    bys = pd.DataFrame([{"era": e, "market": mk, "season": se, **summarize(g, e)}
                        for (e, mk, se), g in sig.groupby(["era", "market", "season"])])
    bys.to_csv(os.path.join(OUT, "s2a_by_season.csv"), index=False)
    pd.set_option("display.width", 220)
    print(t.round(2).to_string(index=False))
    print(f.round(3).to_string(index=False))
    print(sig.groupby(["era", "market", "family"]).size().sort_values(ascending=False).head(20).to_string())


if __name__ == "__main__":
    main()
