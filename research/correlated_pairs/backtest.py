"""Same-game spread + total pairs: correlation and stake (PLAN.md, pre-registered Nov 5, 2026). Research only.

    python -m research.correlated_pairs.backtest     # -> out/results.txt, out/schedules.csv, out/pairs.csv
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.persistent_disagreement.common import baseline
from research.stake_bands.backtest import MIN_EV, PERIODS, boot_diff, grade, max_dd, opener_plays

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
SEED, REPS = 20261105, 10_000
L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def structural(w: pd.DataFrame) -> pd.DataFrame:
    """All games with both openers: correlation of the favorite's cover margin with the over margin."""
    d = w[~w["swapped"]].dropna(subset=["open_home_spread", "open_total", "margin", "points"])
    d = d[d["open_home_spread"] != 0]
    fav_cover = -np.sign(d["open_home_spread"]) * (d["margin"] + d["open_home_spread"])
    over = d["points"] - d["open_total"]
    size = d["open_home_spread"].abs()
    grp = pd.cut(size, [0, 4.75, 9.75, 19.75, 99], labels=["under 5", "5-9.5", "10-19.5", "20+"])
    rows = [{"favorite": "all", "games": len(d), "corr": np.corrcoef(fav_cover, over)[0, 1]}]
    for g in grp.cat.categories:
        m = (grp == g).to_numpy()
        rows.append({"favorite": g, "games": int(m.sum()), "corr": np.corrcoef(fav_cover[m], over[m])[0, 1]})
    return pd.DataFrame(rows)


def tag_pairs(p: pd.DataFrame) -> pd.DataFrame:
    """Each play's role: aligned / opposed (a spread and a total play in the same game), pick (pick'em spread in a
    pair), solo (no other play in that game)."""
    p = p.copy()
    sp = p[p["market"] == "spread"].set_index("game_id")
    to = p[p["market"] == "total"].set_index("game_id")
    both = sp.index.intersection(to.index)
    bet_spread = (sp.loc[both, "side"] * sp.loc[both, "line"])            # the bet side's opener spread
    fav = np.sign(-bet_spread)                                             # +1 favorite, -1 underdog, 0 pick'em
    over = to.loc[both, "side"]                                            # +1 over, -1 under
    role = pd.Series(np.where(fav == 0, "pick", np.where(fav * over > 0, "aligned", "opposed")), index=both)
    kind = pd.Series(np.where(fav > 0, "favorite", np.where(fav < 0, "underdog", "pick'em")), index=both) + " + " + \
        pd.Series(np.where(over > 0, "Over", "Under"), index=both)
    p["role"] = p["game_id"].map(role).fillna("solo")
    p["pair"] = p["game_id"].map(kind)
    return p


def pair_frame(p: pd.DataFrame) -> pd.DataFrame:
    """One row per paired game: both legs' results."""
    x = p[p["role"].isin(["aligned", "opposed"])]
    s = x[x["market"] == "spread"].set_index("game_id")
    t = x[x["market"] == "total"].set_index("game_id")
    return pd.DataFrame({"date": s["date"], "role": s["role"], "pair": s["pair"], "s": s["cover"], "t": t.loc[s.index, "cover"]})


def corr_ci(f: pd.DataFrame) -> tuple[float, float, float, int]:
    """Correlation of the two legs' results (win 1, loss 0; any push left out), date-clustered bootstrap 95%."""
    f = f[(f["s"] != 0) & (f["t"] != 0)]
    a, b = (f["s"] > 0).astype(float).to_numpy(), (f["t"] > 0).astype(float).to_numpy()
    est = float(np.corrcoef(a, b)[0, 1]) if len(f) > 2 else np.nan
    dates = f["date"].to_numpy()
    u, inv = np.unique(dates, return_inverse=True)
    # per date sums for a, b, a*b, a^2, b^2, n -> correlation of a resample
    g = np.zeros((len(u), 6))
    for k, v in enumerate((a, b, a * b, a * a, b * b, np.ones(len(a)))):
        g[:, k] = np.bincount(inv, weights=v, minlength=len(u))
    idx = np.random.default_rng(SEED).integers(0, len(u), size=(REPS, len(u)))
    s = g[idx].sum(axis=1)
    n = s[:, 5]
    cov = s[:, 2] / n - (s[:, 0] / n) * (s[:, 1] / n)
    va, vb = s[:, 3] / n - (s[:, 0] / n) ** 2, s[:, 4] / n - (s[:, 1] / n) ** 2
    r = cov / np.sqrt(va * vb)
    return est, float(np.nanpercentile(r, 2.5)), float(np.nanpercentile(r, 97.5)), len(f)


def pair_table(f: pd.DataFrame, by: str) -> pd.DataFrame:
    rows = []
    for g, x in f.groupby(by):
        d = x[(x["s"] != 0) & (x["t"] != 0)]
        res = (d["s"] > 0).map({True: "W", False: "L"}) + (d["t"] > 0).map({True: "W", False: "L"})
        r = corr_ci(x)
        rows.append({by: g, "pairs": len(x), "WW": int((res == "WW").sum()), "LL": int((res == "LL").sum()),
                     "split": int(res.isin(["WL", "LW"]).sum()), "split %": round(100 * res.isin(["WL", "LW"]).mean(), 1),
                     "corr": round(r[0], 3), "95% lo": round(r[1], 3), "95% hi": round(r[2], 3)})
    return pd.DataFrame(rows)


def band_lab(p: pd.DataFrame) -> pd.Series:
    v1 = np.where(p["market"] == "spread", 2.5, 3.0)
    return pd.Series(np.where(p["edge"] < v1, "B", np.where(p["edge"] < 4.0, "core", "4+")), index=p.index)


def double_count(p: pd.DataFrame) -> pd.DataFrame:
    p = p.assign(b=band_lab(p))
    rows = []
    for (mk, b, role), x in p[p["role"] != "pick"].groupby(["market", "b", "role"]):
        d = x[x["cover"] != 0]
        rows.append({"market": mk, "band": b, "role": role, "plays": len(x), "win %": round(100 * (d["cover"] > 0).mean(), 1)})
    return pd.DataFrame(rows)


def metrics(p: pd.DataFrame, st: np.ndarray) -> dict:
    on = st > 0
    u = grade(p["cover"].to_numpy(), st)
    day = pd.DataFrame({"d": p["date"].to_numpy(), "u": u, "r": st}).groupby("d").sum()
    risked = float(st.sum())
    return {"plays": int(on.sum()), "risked": round(risked, 1), "won": round(float(u.sum()), 1),
            "won/risked %": round(100 * u.sum() / risked, 2),
            "daily sd / avg daily risked": round(float(day["u"].std() / day["r"].mean()), 4),
            "max DD / avg stake": round(max_dd(u) / (risked / on.sum()), 1)}


def schedules(p: pd.DataFrame, rho_other: float) -> dict[str, np.ndarray]:
    base = np.where(p["v1"], 1.0, 0.5)
    al = (p["role"] == "aligned").to_numpy()
    k = 1 / np.sqrt(1 + max(rho_other, 0.0))
    return {"(a) current": base, "(b) aligned x0.75 (primary)": np.where(al, 0.75, 1.0) * base,
            "(c) aligned x0.5": np.where(al, 0.5, 1.0) * base,
            f"(d) aligned x{k:.3f} (rho {rho_other:+.3f}, other period)": np.where(al, k, 1.0) * base}


def live_sample() -> None:
    from cbb import tracker
    b = tracker.load("v1")
    b = b[(b["status"] == "settled") & (b["date"].astype(str) >= "2026-11-01")]
    rows = []
    for gid, x in b.groupby("game_id"):
        if set(x["market"]) != {"spread", "total"}:
            continue
        s, t = x[x["market"] == "spread"].iloc[0], x[x["market"] == "total"].iloc[0]
        line = float(s["line"])
        fav = "favorite" if line < 0 else "underdog" if line > 0 else "pick'em"
        rows.append({"pair": f"{fav} + {str(t['side']).capitalize()}", "res": str(s["result"]) + str(t["result"])})
    r = pd.DataFrame(rows)
    say(f"\nLive 2026-27 main plays (Nov 1 to date), games with both a spread and a total play: {len(r)}")
    if len(r):
        say(r.assign(split=r["res"].isin(["WL", "LW"])).groupby("pair").agg(
            games=("res", "size"), split=("split", "sum")).to_string())


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    w = baseline()
    say("Same-game spread + total pairs (PLAN.md, pre-registered Nov 5, 2026). Openers at an assumed -110.")
    plays, frames, rho = {}, {}, {}
    for name, ss in PERIODS.items():
        p = opener_plays(w[w["season"].isin(ss)])
        p = tag_pairs(p[p["ev"] >= MIN_EV].reset_index(drop=True))
        plays[name], frames[name] = p, pair_frame(p)
        rho[name] = corr_ci(frames[name][frames[name]["role"] == "aligned"])[0]

    say("\n1. Structural link, all games with both openers: corr(favorite cover margin, over margin)")
    for name, ss in PERIODS.items():
        say(f"  {name}:\n  " + structural(w[w["season"].isin(ss)]).round(3).to_string(index=False).replace("\n", "\n  "))

    say("\n2. Pair outcomes (legs: win 1 / loss 0, pushes out; date-clustered 95%)")
    for name in PERIODS:
        f = frames[name]
        say(f"  {name}: plays {len(plays[name])}, roles {plays[name]['role'].value_counts().to_dict()}")
        say("  " + pair_table(f, "role").to_string(index=False).replace("\n", "\n  "))
        say("  " + pair_table(f, "pair").to_string(index=False).replace("\n", "\n  "))
    pooled = pd.concat(frames.values())
    r, lo, hi, n = corr_ci(pooled[pooled["role"] == "aligned"])
    linked = r > 0 and lo > 0
    say(f"  pooled aligned pairs: corr {r:+.3f} (95% {lo:+.3f} to {hi:+.3f}), {n} decided pairs -> linked: {'yes' if linked else 'no'}")
    r2, lo2, hi2, n2 = corr_ci(pooled[pooled["role"] == "opposed"])
    say(f"  pooled opposed pairs: corr {r2:+.3f} (95% {lo2:+.3f} to {hi2:+.3f}), {n2} decided pairs")

    say("\n3. Double counting: win % by role and edge band")
    for name in PERIODS:
        t = double_count(plays[name]).pivot_table(index=["market", "band"], columns="role", values=["plays", "win %"])
        say(f"  {name}:\n  " + t.to_string().replace("\n", "\n  "))

    say("\n4. Schedules on identical plays")
    rows, kept, lower = [], {}, {}
    for name in PERIODS:
        p = plays[name]
        other = [k for k in PERIODS if k != name][0]
        S = schedules(p, rho[other])
        say(f"  {name}:")
        m = {}
        for k, st in S.items():
            m[k] = metrics(p, st)
            rows.append({"period": name, "schedule": k, **m[k]})
            say(f"    {k:48s} " + "  ".join(f"{a} {v}" for a, v in m[k].items()))
        a, b = m["(a) current"], m["(b) aligned x0.75 (primary)"]
        est, blo, bhi = boot_diff(p, S["(b) aligned x0.75 (primary)"], S["(a) current"])
        say(f"    (b) minus (a) won/risked {100 * est:+.2f} pts (95% {100 * blo:+.2f} to {100 * bhi:+.2f}, date-clustered)")
        kept[name] = 100 * est >= -0.5
        lower[name] = (b["daily sd / avg daily risked"] < a["daily sd / avg daily risked"]) and \
            (b["max DD / avg stake"] <= a["max DD / avg stake"])
        say(f"    return kept: {'yes' if kept[name] else 'no'}; risk lower: {'yes' if lower[name] else 'no'}")

    passed = linked and all(kept.values()) and all(lower.values())
    say(f"\nProposal rule: linked {'yes' if linked else 'no'}; return kept {kept}; risk lower {lower} -> "
        f"{'PASS: propose (b) to Chad' if passed else 'does not pass: no proposal'}")
    live_sample()

    pd.DataFrame(rows).to_csv(os.path.join(OUT, "schedules.csv"), index=False)
    pd.concat([f.assign(period=k) for k, f in frames.items()]).to_csv(os.path.join(OUT, "pairs.csv"))
    open(os.path.join(OUT, "results.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
