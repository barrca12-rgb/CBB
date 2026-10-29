"""Win-probability rule re-fit (PLAN.md). Research only; nothing live is touched.

    python -m research.winprob.fit      # -> research/winprob/out/fit_run.txt and CSVs
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from research.market.s1_sample_report import lookup
from research.persistent_disagreement.common import baseline
from research.persistent_disagreement.score import dk_spreads
from research.rotation_totals.build import first_observed

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
ROOT = os.path.join(HERE, "..", "..")
BETS = os.path.join(ROOT, "bets", "bets.csv")
SEED = 20261029
NBOOT = 1000
MIN_EV = 0.02
LIVE = {"spread": (0.0255, 0.58), "total": (0.014, 0.565)}
THR = {"spread": 2.5, "total": 3.0}
DEV, DEV_S1, CHECK = [2014, 2015, 2016, 2017], [2015, 2016, 2017], [2024, 2025, 2026]
BANDS = [2, 2.5, 3, 4, 5, 6, 99]
BGRID = np.round(np.arange(0.0, 0.0501, 0.0001), 4)
CGRID = np.round(np.arange(0.50, 0.7501, 0.0025), 4)
EDGES = {"spread": [2.5, 3, 3.5, 4, 4.5, 5, 6], "total": [3, 3.5, 4, 4.5, 5, 6]}
QDATES = {2023: ["2022-11-12", "2023-01-14", "2023-03-04"], 2024: ["2023-11-11", "2024-01-13", "2024-03-02"],
          2025: ["2024-11-09", "2025-01-11", "2025-03-01"], 2026: ["2025-11-08", "2026-01-10", "2026-03-07"]}
L: list[str] = []


def say(s=""):
    L.append(str(s))
    print(s, flush=True)


def payout(o):
    o = np.asarray(o, float)
    return np.where(o > 0, o / 100, 100 / -o)


def prob(e, b, c):
    return np.minimum(np.maximum(0.5 + b * np.abs(e), 0.5), c)


def ev(p, o):
    return p * payout(o) - (1 - p)


def break_price(p: float) -> float:
    """Worst American price that still clears MIN_EV (run_day.price_needed's rounding)."""
    pay = (MIN_EV + 1 - p) / p
    return float(np.ceil(100 * pay)) if pay >= 1 else -float(np.floor(100 / pay))


# ------------------------------------------------------------------ opener sides
def sides(w: pd.DataFrame, mk: str) -> pd.DataFrame:
    """Every non-swapped game with an opener: edge from the model's side, result, CLV (opener to close)."""
    line, close = ("open_home_spread", "home_spread") if mk == "spread" else ("open_total", "total")
    d = w[~w["swapped"] & w[line].notna()].copy()
    if mk == "spread":
        e = d["final_margin"] + d[line]
        r = d["margin"] + d[line]
        clv_home = d[line] - d[close]                       # home bettor: more points than the close is good
    else:
        e = d["final_total"] - d[line]
        r = d["points"] - d[line]
        clv_home = d[close] - d[line]                       # over bettor: close above the bet number is good
    side = np.sign(e)
    clv = side * clv_home
    clv = clv.where(clv.abs() <= 20)                         # data-error closes (e.g. a -125 spread) dropped from CLV
    out = pd.DataFrame({"game_id": d["game_id"], "season": d["season"], "date": d["date"].dt.strftime("%Y-%m-%d"),
                        "e": e.abs(), "side": side, "res": side * r, "clv": clv})
    return out[out["e"] > 0]


# ------------------------------------------------------------------ fitting
def loglik_grid(e: np.ndarray, y: np.ndarray, wt: np.ndarray) -> np.ndarray:
    """Weighted binomial log-likelihood of p = min(0.5 + b e, c) over BGRID x CGRID. e sorted ascending."""
    W = np.concatenate([[0], np.cumsum((wt * y)[::-1])])[::-1]          # wins at index >= k
    Lw = np.concatenate([[0], np.cumsum((wt * (1 - y))[::-1])])[::-1]   # losses at index >= k
    ll = np.full((len(BGRID), len(CGRID)), -np.inf)
    lc, l1c = np.log(CGRID), np.log(1 - CGRID)
    for i, b in enumerate(BGRID):
        q = 0.5 + b * e
        cq = np.concatenate([[0], np.cumsum(wt * (y * np.log(q) + (1 - y) * np.log(1 - q)))])
        k = np.searchsorted(q, CGRID, side="left")                      # obs with q < c use q; others use c
        ll[i] = cq[k] + W[k] * lc + Lw[k] * l1c
    return ll


def fit(s: pd.DataFrame, fix_b=None, fix_c=None, boot=False):
    s = s.sort_values("e")
    e, y = s["e"].to_numpy(float), (s["res"] > 0).to_numpy(float)
    dates = s["date"].to_numpy()
    u, inv = np.unique(dates, return_inverse=True)

    def one(wt):
        ll = loglik_grid(e, y, wt)
        if fix_b is not None:
            ll = np.where(np.isclose(BGRID, fix_b)[:, None], ll, -np.inf)
        if fix_c is not None:
            ll = np.where(np.isclose(CGRID, fix_c)[None, :], ll, -np.inf)
        i, j = np.unravel_index(np.argmax(ll), ll.shape)
        return BGRID[i], CGRID[j], ll[i, j]

    b, c, ll = one(np.ones(len(e)))
    res = {"b": b, "c": c, "ll": ll, "n": len(e), "c_binds_from": (c - 0.5) / b if b > 0 else np.inf,
           "max_e": e.max()}
    if boot:
        rng = np.random.default_rng(SEED)
        bs = []
        for _ in range(NBOOT):
            cnt = np.bincount(rng.integers(0, len(u), len(u)), minlength=len(u))
            bb, cc, _ = one(cnt[inv].astype(float))
            bs.append((bb, cc))
        bs = np.array(bs)
        res["b_lo"], res["b_hi"] = np.quantile(bs[:, 0], [.025, .975])
        res["c_lo"], res["c_hi"] = np.quantile(bs[:, 1], [.025, .975])
    return res


def ll_obs(s: pd.DataFrame, b, c) -> np.ndarray:
    p = prob(s["e"].to_numpy(), b, c)
    y = (s["res"] > 0).to_numpy()
    return np.where(y, np.log(p), np.log(1 - p))


def boot_mean(v, dates, n=NBOOT, seed=SEED):
    v = np.asarray(v, float)
    u, inv = np.unique(np.asarray(dates), return_inverse=True)
    sv, c = np.bincount(inv, v), np.bincount(inv)
    i = np.random.default_rng(seed).integers(0, len(u), (n, len(u)))
    r = sv[i].sum(1) / c[i].sum(1)
    return float(v.mean()), float(np.quantile(r, .025)), float(np.quantile(r, .975))


def boot_ratio(num, den, dates, n=NBOOT, seed=SEED):
    num, den = np.asarray(num, float), np.asarray(den, float)
    u, inv = np.unique(np.asarray(dates), return_inverse=True)
    sn, sd = np.bincount(inv, num), np.bincount(inv, den)
    i = np.random.default_rng(seed).integers(0, len(u), (n, len(u)))
    r = sn[i].sum(1) / np.maximum(sd[i].sum(1), 1e-12)
    return float(num.sum() / max(den.sum(), 1e-12)), float(np.quantile(r, .025)), float(np.quantile(r, .975))


def band_table(s: pd.DataFrame, rules: dict) -> pd.DataFrame:
    s = s.assign(band=pd.cut(s["e"], BANDS, right=False))
    rows = []
    for bnd, g in s.groupby("band", observed=True):
        r = {"band": str(bnd), "games": len(g), "observed": round(100 * (g["res"] > 0).mean(), 1)}
        for k, (b, c) in rules.items():
            r[k] = round(100 * prob(g["e"], b, c).mean(), 1)
        rows.append(r)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ recorded prices
def recorded(w: pd.DataFrame) -> pd.DataFrame:
    """Per quoted game on the 12 Odds API dates: DraftKings first-observed complete market with prices."""
    lk = lookup()
    wi = w.set_index("game_id")
    rows = []
    for season, dates in QDATES.items():
        for d in dates:
            q, _ = first_observed(d, season, lk)
            q = q[q["game_id"].isin(wi.index)].copy()
            q["home_id"] = q["game_id"].map(wi["home_id"]).astype(int)
            q["away_id"] = q["game_id"].map(wi["away_id"]).astype(int)
            sp = dk_spreads(d, q, lk)
            rows.append(q.merge(sp, on="game_id", how="left"))
    return pd.concat(rows, ignore_index=True)


def recorded_plays(q: pd.DataFrame, w: pd.DataFrame, mk: str) -> pd.DataFrame:
    wi = w.set_index("game_id")
    q = q[q["game_id"].isin(wi.index[~wi["swapped"]])].copy()
    g = wi.loc[q["game_id"]]
    if mk == "spread":
        q = q[q["dk_home_spread"].notna()]
        g = wi.loc[q["game_id"]]
        line = q["dk_home_spread"].to_numpy()
        e = g["final_margin"].to_numpy() + line
        side = np.sign(e)
        res = side * (g["margin"].to_numpy() + line)
        price = np.where(side > 0, q["home_price"], q["away_price"])
        clv = side * (line - g["home_spread"].to_numpy())
    else:
        line = np.where(g["final_total"].to_numpy() > q["dk_total"].to_numpy(), q["dk_total"], q["dk_under_total"])
        e = g["final_total"].to_numpy() - line
        side = np.sign(e)
        res = side * (g["points"].to_numpy() - line)
        price = np.where(side > 0, q["over_price"], q["under_price"])
        clv = side * (g["total"].to_numpy() - line)
    out = pd.DataFrame({"game_id": q["game_id"].to_numpy(), "season": q["season"].to_numpy(), "date": q["date"].to_numpy(),
                        "e": np.abs(e), "side": side, "res": res, "price": price.astype(float), "clv": clv})
    return out[out["e"] > 0]


def profit(res, price):
    return np.where(res > 0, payout(price), np.where(res < 0, -1.0, 0.0))


# ------------------------------------------------------------------ main
def main() -> None:
    np.seterr(divide="ignore", invalid="ignore")
    os.makedirs(OUT, exist_ok=True)
    pd.set_option("display.width", 250)
    w = baseline()
    say(f"frame: {len(w):,} games, swapped excluded: {int(w['swapped'].sum())}")
    fits, cand, all_rules = {}, {}, {}
    S = {mk: sides(w, mk) for mk in ("spread", "total")}

    # ---------------- 1. fit on development seasons, check on 2024-26
    spec_rows = []
    for mk in ("spread", "total"):
        s = S[mk]
        nopush = s[s["res"] != 0]
        dev = nopush[nopush["season"].isin(DEV) & (nopush["e"] >= 2)]
        chk = nopush[nopush["season"].isin(CHECK) & (nopush["e"] >= 2)]
        say(f"\n==== {mk}: dev games (|e|>=2, no push) {len(dev):,}; check games {len(chk):,}")
        specs = {
            "primary 2014-17, e>=2": (dev, None, None, True),
            "S1 2015-17, e>=2": (nopush[nopush["season"].isin(DEV_S1) & (nopush["e"] >= 2)], None, None, False),
            "S2 2014-17, 2<=e<6": (dev[dev["e"] < 6], None, None, False),
            "S3 slope only (live cap)": (dev, None, LIVE[mk][1], False),
            "S4 cap only (live slope)": (dev, LIVE[mk][0], None, False),
            "info: check seasons 2024-26 fit": (chk, None, None, False),
        }
        for name, (d, fb, fc, bt) in specs.items():
            r = fit(d, fix_b=fb, fix_c=fc, boot=bt)
            all_rules[(mk, name)] = (r["b"], r["c"])
            llc = ll_obs(chk, r["b"], r["c"]).mean()
            row = {"market": mk, "spec": name, "n": r["n"], "slope": r["b"], "cap": r["c"],
                   "cap binds from edge": round(r["c_binds_from"], 2), "max edge in sample": round(r["max_e"], 1),
                   "check ll/game": round(llc, 5)}
            if bt:
                row.update({"slope 95%": f"[{r['b_lo']:.4f}, {r['b_hi']:.4f}]", "cap 95%": f"[{r['c_lo']:.4f}, {r['c_hi']:.4f}]"})
                fits[mk] = r
            spec_rows.append(row)
        b, c = fits[mk]["b"], fits[mk]["c"]
        lb, lc_ = LIVE[mk]
        spec_rows.append({"market": mk, "spec": "live rule", "slope": lb, "cap": lc_,
                          "cap binds from edge": round((lc_ - 0.5) / lb, 2),
                          "check ll/game": round(ll_obs(chk, lb, lc_).mean(), 5),
                          "dev ll/game": round(ll_obs(dev, lb, lc_).mean(), 5)})
        # likelihood check with interval
        diff = ll_obs(chk, b, c) - ll_obs(chk, lb, lc_)
        m, lo, hi = boot_mean(diff, chk["date"])
        passed = m >= 0
        say(f"fitted {mk}: p = min(0.5 + {b:.4f} e, {c:.4f}); slope 95% [{fits[mk]['b_lo']:.4f}, {fits[mk]['b_hi']:.4f}], "
            f"cap 95% [{fits[mk]['c_lo']:.4f}, {fits[mk]['c_hi']:.4f}]; cap binds from {fits[mk]['c_binds_from']:.2f} pts")
        say(f"check 2024-26 log-lik/game, fitted minus live: {m:+.5f} [{lo:+.5f}, {hi:+.5f}] -> {'PASS' if passed else 'FAIL'}")
        fits[mk]["check_pass"] = passed
        fits[mk]["check_diff"] = (m, lo, hi)
        # band tables
        for per, d in (("dev 2014-17", dev), ("check 2024-26", chk)):
            t = band_table(d, {"live": LIVE[mk], "fitted": (b, c)})
            t["candidate"] = [min(x, y) for x, y in zip(t["live"], t["fitted"])]
            say(f"band table {mk}, {per}:\n{t.to_string(index=False)}")
            t.assign(market=mk, period=per).to_csv(os.path.join(OUT, f"bands_{mk}_{per.split()[0]}.csv"), index=False)
        cand[mk] = (b, c)
    specs_df = pd.DataFrame(spec_rows)
    specs_df.to_csv(os.path.join(OUT, "specs.csv"), index=False)
    say("\nall specifications:\n" + specs_df.to_string(index=False))

    def p_live(mk, e):
        return prob(e, *LIVE[mk])

    def p_cand(mk, e, rule=None):
        b, c = rule or cand[mk]
        return np.minimum(p_live(mk, e), prob(e, b, c))

    # ---------------- 2. break prices
    say("\n==== break prices (worst price clearing +2%); removed = price between the two")
    br = []
    for mk in ("spread", "total"):
        for e in EDGES[mk]:
            pl, pc = float(p_live(mk, e)), float(p_cand(mk, e))
            br.append({"market": mk, "edge": e, "live p": round(100 * pl, 1), "candidate p": round(100 * pc, 1),
                       "live break": break_price(pl), "candidate break": break_price(pc)})
    br = pd.DataFrame(br)
    br.to_csv(os.path.join(OUT, "break_prices.csv"), index=False)
    say(br.to_string(index=False))

    # ---------------- 3. recorded prices
    say("\n==== recorded prices: DraftKings first-observed complete market, Odds API dates")
    q = recorded(w)
    q.to_csv(os.path.join(OUT, "recorded_quotes.csv"), index=False)
    say(f"quoted games in frame: {len(q):,} ({q.groupby('season').size().to_dict()}); with DK spread prices: "
        f"{int(q['home_price'].notna().sum()):,}")
    dist = {}
    for mk in ("spread", "total"):
        px = np.concatenate([q["home_price"].dropna(), q["away_price"].dropna()]) if mk == "spread" else \
            np.concatenate([q["over_price"].dropna(), q["under_price"].dropna()])
        vc = pd.Series(px).value_counts(normalize=True).sort_index()
        dist[mk] = vc
        say(f"DK {mk} side prices (n={len(px)}): -110 or better {100 * (px >= -110).mean():.1f}%, "
            f"-111..-114 {100 * ((px < -110) & (px > -115)).mean():.1f}%, -115..-119 {100 * ((px <= -115) & (px > -120)).mean():.1f}%, "
            f"-120..-124 {100 * ((px <= -120) & (px > -125)).mean():.1f}%, -125 or worse {100 * (px <= -125).mean():.1f}%")
        vc.rename("share").to_csv(os.path.join(OUT, f"price_dist_{mk}.csv"))
    rec_rows = []
    for mk in ("spread", "total"):
        r = recorded_plays(q, w, mk)
        r = r[r["season"].isin(CHECK)]
        r["ev_live"] = ev(p_live(mk, r["e"]), r["price"])
        r["ev_cand"] = ev(p_cand(mk, r["e"]), r["price"])
        v1 = r[(r["e"] >= THR[mk]) & (r["ev_live"] >= MIN_EV)]
        rem = v1[v1["ev_cand"] < MIN_EV]
        kept = v1[v1["ev_cand"] >= MIN_EV]
        games = len(r)
        opener_games = S[mk][S[mk]["season"].isin(CHECK)].groupby("season").size().mean()
        for name, d in (("v1 plays", v1), ("removed", rem), ("kept", kept)):
            dec = d[d["res"] != 0]
            pr = profit(d["res"], d["price"])
            rec_rows.append({"market": mk, "set": name, "plays": len(d), "W": int((d["res"] > 0).sum()),
                             "L": int((d["res"] < 0).sum()), "P": int((d["res"] == 0).sum()),
                             "win%": round(100 * (dec["res"] > 0).mean(), 1) if len(dec) else np.nan,
                             "units": round(pr.sum(), 2), "ROI%": round(100 * pr.mean(), 1) if len(d) else np.nan,
                             "CLV pts": round(d["clv"].mean(), 2) if len(d) else np.nan,
                             "median price": d["price"].median() if len(d) else np.nan,
                             "per season (scaled)": round(len(d) / games * opener_games, 1)})
        r.to_csv(os.path.join(OUT, f"recorded_{mk}.csv"), index=False)
        say(f"{mk}: {games} quoted 2024-26 games (opener games/season {opener_games:.0f})")
        if len(rem):
            say("removed plays:\n" + rem[["date", "game_id", "e", "price", "res", "clv"]].to_string(index=False))
    rec = pd.DataFrame(rec_rows)
    rec.to_csv(os.path.join(OUT, "removal_recorded.csv"), index=False)
    say(rec.to_string(index=False))
    # bets.csv
    bt = pd.read_csv(BETS)
    graded = bt[bt["result"].notna()] if "result" in bt else bt.iloc[0:0]
    say(f"bets/bets.csv: {len(bt)} rows, {len(graded)} graded; prices {sorted(bt['odds'].dropna().unique().tolist())}")

    # ---------------- 4. assumed price distribution on all 2024-26 opener plays
    say("\n==== ASSUMED prices: every 2024-26 v1 opener play priced from the DK first-observed distribution")
    am_rows = []
    for mk in ("spread", "total"):
        s = S[mk]
        pl = s[s["season"].isin(CHECK) & (s["e"] >= THR[mk])].copy()
        prices, share = dist[mk].index.to_numpy(float), dist[mk].to_numpy(float)
        for rname, rule in [("primary", None)] + [(k[1], v) for k, v in all_rules.items() if k[0] == mk and not k[1].startswith("primary")]:
            e = pl["e"].to_numpy()[:, None]
            ok_live = ev(p_live(mk, e), prices[None, :]) >= MIN_EV
            ok_cand = ev(p_cand(mk, e, rule), prices[None, :]) >= MIN_EV
            win = (ok_live & ~ok_cand) * share[None, :]                     # P(removed, price) per play
            wt = win.sum(1)
            prof = (win * np.where(pl["res"].to_numpy()[:, None] > 0, payout(prices)[None, :],
                                   np.where(pl["res"].to_numpy()[:, None] < 0, -1.0, 0.0))).sum(1)
            v1w = (ok_live * share[None, :]).sum(1)
            dec = pl["res"].to_numpy() != 0
            per_season = pl.assign(wt=wt).groupby("season")["wt"].sum()
            roi, lo, hi = boot_ratio(prof, wt, pl["date"])
            winr = (wt * (pl["res"].to_numpy() > 0))[dec].sum() / max(wt[dec].sum(), 1e-12)
            clv_ok = pl["clv"].notna().to_numpy()
            am_rows.append({"market": mk, "rule": rname, "v1 plays/season (exp.)": round(v1w.sum() / 3, 1),
                            "removed/season (exp.)": round(wt.sum() / 3, 1),
                            "by season": {int(k): round(v, 1) for k, v in per_season.items()},
                            "removed win%": round(100 * winr, 1),
                            "removed W-L (exp.)": f"{(wt * (pl['res'] > 0)).sum():.1f}-{(wt * (pl['res'] < 0)).sum():.1f}",
                            "removed ROI%": round(100 * roi, 1), "ROI 95%": f"[{100 * lo:.1f}, {100 * hi:.1f}]",
                            "removed CLV pts": round((wt * pl["clv"].fillna(0)).sum() / max(wt[clv_ok].sum(), 1e-12), 2),
                            "all v1 CLV pts": round(pl["clv"].mean(), 2)})
            if rname == "primary":
                pl.assign(p_removed=wt, exp_profit_if_removed=prof).to_csv(os.path.join(OUT, f"assumed_{mk}.csv"), index=False)
    am = pd.DataFrame(am_rows)
    am.to_csv(os.path.join(OUT, "removal_assumed.csv"), index=False)
    say(am.to_string(index=False))

    # ---------------- 5. verdict
    say("\n==== verdict (PLAN.md kill rule)")
    for mk in ("spread", "total"):
        a = am[(am["market"] == mk) & (am["rule"] == "primary")].iloc[0]
        rr = rec[(rec["market"] == mk) & (rec["set"] == "removed")].iloc[0]
        reasons = []
        if not fits[mk]["check_pass"]:
            reasons.append("fails the 2024-26 likelihood check")
        if a["removed/season (exp.)"] < 20:
            reasons.append(f"{a['removed/season (exp.)']} removed a season (< 20; recorded-price scaled {rr['per season (scaled)']})")
        if not (a["removed ROI%"] < 0):
            reasons.append(f"removed plays did not lose (ROI {a['removed ROI%']}%)")
        say(f"{mk}: {'CLOSED: ' + '; '.join(reasons) if reasons else 'Mar 14 candidate'}")
    with open(os.path.join(OUT, "fit_run.txt"), "w") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
