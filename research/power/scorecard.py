"""Power scorecard: the standard way every study and shadow scores a candidate against a baseline (research only).

Why: a bet's result swings ~11 points around the line, so units (and wins) need years to separate two models.
Closing-line value (how far the line moved toward the pick before the close) has ~2 points of noise per bet and
separates them ~40 times faster on the same bets (research/power/LOG.md). Units stay as the secondary check,
because CLV only becomes profit if the close is efficient.

Everything here works on one frame with one row per game and these columns:
    date        game date (clusters for the bootstrap)
    open, close the line the bet is taken at, and the closing line (home spread for spreads, total for totals)
    result      final home margin (spreads) or total points (totals)
    fc_<name>   each strategy's forecast (home margin or total)

    scorecard(frame, market, strategies, baseline)   -> dict of tables (per strategy, paired vs baseline,
                                                        all-games information beyond the line, power)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

THRESHOLD = {"spread": 2.5, "total": 3.0}
Z95, Z80 = 1.959964, 0.841621
SEED, REPS = 20261029, 4000


def edge(fc, line, market):
    """Forecast minus the line, positive = home (spreads) or over (totals)."""
    return fc + line if market == "spread" else fc - line


def picks(f: pd.DataFrame, name: str, market: str) -> pd.Series:
    """+1 home/over, -1 away/under, 0 no bet. The fixed rule at assumed -110 (EV never binds above the threshold)."""
    e = edge(f[f"fc_{name}"], f["open"], market)
    return pd.Series(np.where(e.abs() >= THRESHOLD[market], np.sign(e), 0.0), index=f.index).fillna(0.0)


def per_bet(f: pd.DataFrame, side: pd.Series, market: str) -> pd.DataFrame:
    """CLV (points of line gained by the close), cover (points beaten the bet line by) and units at -110, per game
    (0 where no bet)."""
    if market == "spread":
        clv = side * (f["open"] - f["close"])
        cover = side * (f["result"] + f["open"])
    else:
        clv = side * (f["close"] - f["open"])
        cover = side * (f["result"] - f["open"])
    units = np.where(side == 0, 0.0, np.where(cover > 0, 100 / 110, np.where(cover < 0, -1.0, 0.0)))
    return pd.DataFrame({"bet": side != 0, "clv": np.where(side != 0, clv, 0.0), "cover": np.where(side != 0, cover, 0.0),
                         "units": units}, index=f.index)


def cluster_boot(values: pd.Series, dates: pd.Series, stat="sum") -> tuple[float, float, float]:
    """Total (or per-bet mean) with a 95% bootstrap interval resampling whole dates."""
    g = pd.DataFrame({"v": values.to_numpy(), "d": dates.to_numpy()})
    by = g.groupby("d")["v"].agg(["sum", "count"])
    s, c = by["sum"].to_numpy(), by["count"].to_numpy()
    idx = np.random.default_rng(SEED).integers(0, len(s), (REPS, len(s)))
    if stat == "sum":
        draws = s[idx].sum(1)
        est = s.sum()
    else:
        draws = s[idx].sum(1) / np.maximum(c[idx].sum(1), 1)
        est = s.sum() / max(c.sum(), 1)
    return float(est), float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def clustered_ols(y, X, groups):
    """OLS with intercept; coefficients and date-clustered SEs."""
    X = np.column_stack([np.ones(len(y)), np.asarray(X, float).reshape(len(y), -1)])
    y = np.asarray(y, float)
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    XtXi = np.linalg.pinv(X.T @ X)
    meat = np.zeros((X.shape[1], X.shape[1]))
    for gv in pd.unique(groups):
        m = groups == gv
        s = X[m].T @ e[m]
        meat += np.outer(s, s)
    return b, np.sqrt(np.diag(XtXi @ meat @ XtXi))


def bets_needed(delta: float, sd: float) -> float:
    """Bets for a two-sided 5% test to detect a per-bet difference delta with 80% power (paired per-bet noise sd)."""
    return float(((Z95 + Z80) * sd / delta) ** 2) if delta else float("inf")


def scorecard(f: pd.DataFrame, market: str, strategies: list[str], baseline: str) -> dict:
    f = f.dropna(subset=["open", "close", "result"]).copy()
    dates = f["date"].astype(str)
    side = {s: picks(f, s, market) for s in strategies}
    pb = {s: per_bet(f, side[s], market) for s in strategies}
    rows = []
    for s in strategies:
        x = pb[s][pb[s]["bet"]]
        d = dates[x.index]
        clv_m = cluster_boot(x["clv"], d, "mean")
        rows.append({"strategy": s, "bets": len(x), "CLV/bet": clv_m[0], "CLV lo": clv_m[1], "CLV hi": clv_m[2],
                     "CLV SD": float(x["clv"].std()), "cover/bet": float(x["cover"].mean()),
                     "win %": 100 * float((x["cover"] > 0).sum() / max((x["cover"] != 0).sum(), 1)),
                     "units": float(x["units"].sum()), "ROI %": 100 * float(x["units"].mean()) if len(x) else np.nan})
    per = pd.DataFrame(rows)
    paired = []
    for s in strategies:
        if s == baseline:
            continue
        d_clv = pb[s]["clv"] - pb[baseline]["clv"]
        d_units = pb[s]["units"] - pb[baseline]["units"]
        changed = (side[s] != side[baseline])
        e_clv = cluster_boot(d_clv, dates)
        e_u = cluster_boot(d_units, dates)
        ch = changed[changed].index
        # per changed game: how much CLV the switch gained (the paired noise that sets power)
        sd = float(d_clv[ch].std()) if len(ch) > 1 else np.nan
        paired.append({"candidate": s, "games where picks differ": int(changed.sum()),
                       "total CLV diff (pts)": e_clv[0], "CLV lo": e_clv[1], "CLV hi": e_clv[2],
                       "units diff": e_u[0], "units lo": e_u[1], "units hi": e_u[2],
                       "CLV diff per changed game": float(d_clv[ch].mean()) if len(ch) else np.nan,
                       "SD per changed game": sd})
    pair = pd.DataFrame(paired)
    # all games: does the forecast know something the closing line doesn't?
    y = f["result"] + f["close"] if market == "spread" else f["result"] - f["close"]
    beyond = []
    base_e = edge(f[f"fc_{baseline}"], f["close"], market)
    for s in strategies:
        e = edge(f[f"fc_{s}"], f["close"], market)
        ok = e.notna() & y.notna()
        b, se = clustered_ols(y[ok], e[ok], dates[ok].to_numpy())
        row = {"strategy": s, "games": int(ok.sum()), "slope on (fc - close)": b[1], "SE": se[1]}
        if s != baseline:
            ok2 = ok & base_e.notna()
            b2, se2 = clustered_ols(y[ok2], np.column_stack([base_e[ok2], (e - base_e)[ok2]]), dates[ok2].to_numpy())
            row["incremental slope on (fc - baseline)"], row["incremental SE"] = b2[2], se2[2]
        beyond.append(row)
    return {"per_strategy": per, "paired": pair, "beyond_close": pd.DataFrame(beyond), "n_games": len(f)}


def noise_table(f: pd.DataFrame, market: str, name: str) -> pd.DataFrame:
    """Per-bet noise and evidence strength of units, cover points and CLV for one strategy's bets."""
    f = f.dropna(subset=["open", "close", "result"])
    x = per_bet(f, picks(f, name, market), market)
    x = x[x["bet"]]
    n = len(x)
    out = []
    for c, lab in (("units", "units"), ("cover", "result vs bet line (pts)"), ("clv", "CLV (pts)")):
        m, sd = float(x[c].mean()), float(x[c].std())
        out.append({"measure": lab, "bets": n, "mean": m, "SD": sd, "t": m / sd * np.sqrt(n) if sd else np.nan})
    t = pd.DataFrame(out)
    t["bets needed vs units"] = (t["t"].iloc[0] / t["t"]) ** 2
    return t
