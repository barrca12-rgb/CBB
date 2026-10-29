"""Build step (PLAN.md): baseline and candidate predictions for every eligible game on the frozen dates, written
before any result is joined. Outcomes are dropped from the frame before the predictions file is written.

    python -m research.rotation_totals.build A      # Stage A dates -> out/predictions_A.csv (+ .sha256), out/build_A.txt
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from cbb import projection, teams
from research.market.s1_sample_report import lookup, schedule
from research.quant3.study import opening_week
from research.stage2_stability.common import frames as clean_frames

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
ROOT = os.path.join(HERE, "..", "..")
QDATA = os.path.join(ROOT, "research", "market", "data")
STAGES = {"A": {2025: ["2024-11-09", "2025-01-11", "2025-03-01"], 2026: ["2025-11-08", "2026-01-10", "2026-03-07"]},
          "B": {2025: ["2024-11-13", "2024-11-16", "2024-12-11", "2024-12-21", "2025-01-08", "2025-01-18", "2025-02-12",
                       "2025-02-15", "2025-03-05", "2025-03-08"],
                2026: ["2025-11-12", "2025-11-15", "2025-12-10", "2025-12-20", "2026-01-14", "2026-01-17", "2026-02-11",
                       "2026-02-21", "2026-03-04", "2026-03-14"]}}
LAM = 100.0
BASE_COLS = ["edge_model", "edge_s1", "edge_kp", "edge_bt", "poss", "q", "abs_spread", "log_gp", "neutral", "early",
             "rest_sum", "efg_sum", "tov_rate_sum", "orb_rate_sum", "ft_rate_sum", "altitude"]
MODS = ["log_gp", "poss", "neutral", "early"]
FEATS = BASE_COLS + [f"edge_x_{m}" for m in MODS] + ["rot_off", "rot_def"]


def lag1_season_avg(b: pd.DataFrame) -> pd.Series:
    """Season scoring average from games on dates before D-1 (200+ games), else last season's average, else the
    season's mean stage-1 total (2013 only, training-irrelevant)."""
    d = pd.to_datetime(b["date"])
    pts = b["home_pts"] + b["away_pts"]
    day = pd.DataFrame({"season": b["season"], "date": d, "pts": pts}).groupby(["season", "date"])["pts"].agg(["sum", "count"]).sort_index()
    cs = day.groupby(level=0).cumsum()                          # through each date, inclusive
    out = pd.Series(np.nan, index=b.index)
    for s, g in cs.groupby(level=0):
        g = g.droplevel(0)
        idx = g.index
        for D in d[b["season"] == s].unique():
            prior = g[idx <= D - pd.Timedelta(days=2)]            # dates up to D-2, i.e. before D-1
            if len(prior) and prior["count"].iloc[-1] >= 200:
                out[(b["season"] == s) & (d == D)] = prior["sum"].iloc[-1] / prior["count"].iloc[-1]
    prev = pts.groupby(b["season"]).mean()
    out = out.fillna(b["season"].map(prev.shift()))
    return out.fillna(b["pred_total"].groupby(b["season"]).transform("mean"))


def conservative_frame() -> pd.DataFrame:
    w = pd.read_pickle(os.path.join(ROOT, "audit", "out", "wf_safe_lag1.pkl"))
    w = w.drop(columns=["final_margin", "final_total"])
    w["season_avg_total"] = lag1_season_avg(w)
    return w


def baseline_forecast(safe: pd.DataFrame) -> pd.DataFrame:
    """Historical current-model totals: weights fit on 2013..s-1 of the production (leak-fixed) training frame,
    applied to the conservative inputs; then the live opening-week rule on each date's full slate."""
    train, _ = clean_frames(clean=True)
    train = train.assign(points=train["home_pts"] + train["away_pts"])
    out = safe[safe["season"] >= 2015].copy()
    tf = projection.TOTAL_FEATURES
    for s in sorted(out["season"].unique()):
        tr = train[train["season"].between(2013, s - 1)]
        c = projection.ridge(tr[tf].to_numpy(float), tr["points"].to_numpy(float))
        m = out["season"] == s
        out.loc[m, "final_total"] = c[0] + out.loc[m, tf].to_numpy(float) @ c[1:]
    return opening_week(out)


def rotation() -> pd.DataFrame:
    a = pd.read_csv(os.path.join(ROOT, "research", "originator", "out", "b_adjustments.csv.gz"))
    return a.set_index(["game_id", "team_id"])[["adj_off", "adj_def"]]


def features(b: pd.DataFrame, q: pd.Series, abs_spread: pd.Series, rot: pd.DataFrame) -> pd.DataFrame:
    f = pd.DataFrame(index=b.index)
    f["edge_model"] = b["final_total"] - q
    f["edge_s1"] = b["pred_total"] - q
    f["edge_kp"] = b["kp_total"] - q
    f["edge_bt"] = b["bt_total"] - q
    f["poss"] = b["pred_poss"]
    f["q"] = q
    f["abs_spread"] = abs_spread
    f["log_gp"] = np.log1p(b["games_before"])
    f["neutral"] = b["neutral"].astype(float)
    for c in ("early", "rest_sum", "efg_sum", "tov_rate_sum", "orb_rate_sum", "ft_rate_sum", "altitude"):
        f[c] = b[c].astype(float)
    kh = list(zip(b["game_id"], b["home_id"]))
    ka = list(zip(b["game_id"], b["away_id"]))
    ro_h, ro_a = rot.reindex(kh), rot.reindex(ka)
    f["rot_missing"] = ro_h["adj_off"].isna().to_numpy() | ro_a["adj_off"].isna().to_numpy()
    f["rot_off"] = ro_h["adj_off"].fillna(0).to_numpy() + ro_a["adj_off"].fillna(0).to_numpy()
    f["rot_def"] = ro_h["adj_def"].fillna(0).to_numpy() + ro_a["adj_def"].fillna(0).to_numpy()
    return f


def add_interactions(f: pd.DataFrame, mod_means: dict) -> pd.DataFrame:
    f = f.copy()
    for m in MODS:
        f[f"edge_x_{m}"] = f["edge_model"] * (f[m] - mod_means[m])
    return f


def fit_logit(X: np.ndarray, y: np.ndarray, lam: float = LAM):
    """Summed logistic loss + lam/2 * sum(beta^2) (intercept unpenalized), X already standardized."""
    X1 = np.column_stack([np.ones(len(X)), X])

    def fg(w):
        z = X1 @ w
        p = 1 / (1 + np.exp(-z))
        loss = np.sum(np.logaddexp(0, z) - y * z) + lam / 2 * np.sum(w[1:] ** 2)
        g = X1.T @ (p - y)
        g[1:] += lam * w[1:]
        return loss, g
    r = minimize(fg, np.zeros(X1.shape[1]), jac=True, method="L-BFGS-B", options={"gtol": 1e-6, "maxiter": 5000})
    w = r.x
    pen = np.full(X1.shape[1], lam)
    pen[0] = 0.0
    for _ in range(50):                    # Newton steps on the same convex objective, to the frozen gradient criterion
        p = 1 / (1 + np.exp(-(X1 @ w)))
        g = X1.T @ (p - y) + pen * w
        if np.linalg.norm(g) < 1e-6:
            break
        H = (X1 * (p * (1 - p))[:, None]).T @ X1 + np.diag(pen)
        w = w - np.linalg.solve(H, g)
    r.x, r.jac, r.success, r.message = w, g, bool(np.linalg.norm(g) < 1e-6), "Newton refinement"
    return w, r


def first_observed(date: str, season: int, lk: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per ESPN target game: the first snapshot with both DraftKings spread sides and both total sides present."""
    q = pd.read_csv(os.path.join(QDATA, f"quotes_{date}.csv.gz"))
    s = pd.read_csv(os.path.join(QDATA, f"snapshots_{date}.csv"))
    for c in ("snapshot", "commence_time"):
        q[c] = pd.to_datetime(q[c], utc=True, format="ISO8601")
    snaps = sorted(pd.to_datetime(s["snapshot"], utc=True, format="ISO8601").unique())
    sch = schedule(date, season)
    q["h"] = q["home_team"].map(lambda n: lk.get(teams.norm(n or "")))
    q["a"] = q["away_team"].map(lambda n: lk.get(teams.norm(n or "")))
    ev = q.dropna(subset=["h", "a"]).drop_duplicates("event_id")[["event_id", "h", "a", "commence_time", "home_team"]]
    ev[["h", "a"]] = ev[["h", "a"]].astype(int)
    m1 = sch.merge(ev, left_on=["home_id", "away_id"], right_on=["h", "a"])
    m2 = sch.merge(ev, left_on=["home_id", "away_id"], right_on=["a", "h"])
    m = pd.concat([m1.assign(flip=False), m2.assign(flip=True)]).drop_duplicates("game_id")
    dk = q[q["book"] == "draftkings"].sort_values("snapshot")
    rows, status = [], []
    for _, g in sch.iterrows():
        mm = m[m["game_id"] == g["game_id"]]
        if mm.empty:
            status.append({"game_id": g["game_id"], "date": date, "season": season, "status": "not in the quote feed"})
            continue
        e = mm.iloc[0]
        d = dk[dk["event_id"] == e["event_id"]]
        state, found = {}, None
        for t in snaps:
            for _, r in d[d["snapshot"] == t].iterrows():
                state[(r["market"], r["outcome"])] = None if r["status"] == "absent" else r
            sp = [v for (mk, _), v in state.items() if mk == "spreads" and v is not None and pd.notna(v["price"]) and pd.notna(v["point"])]
            ov, un = state.get(("totals", "Over")), state.get(("totals", "Under"))
            if len(sp) >= 2 and ov is not None and un is not None and pd.notna(ov["price"]) and pd.notna(un["price"]):
                found = (t, sp, ov, un)
                break
        tip = min(g["tip"], e["commence_time"])
        if found is None:
            status.append({"game_id": g["game_id"], "date": date, "season": season, "status": "no complete DraftKings market"})
            continue
        t, sp, ov, un = found
        if t >= tip:
            status.append({"game_id": g["game_id"], "date": date, "season": season, "status": "first complete market after tip"})
            continue
        status.append({"game_id": g["game_id"], "date": date, "season": season, "status": "quoted"})
        rows.append({"game_id": g["game_id"], "date": date, "season": season, "event_id": e["event_id"], "decision_at": t,
                     "tip": tip, "left_censored": bool(t == snaps[0]), "first_snapshot": snaps[0],
                     "dk_total": float(ov["point"]), "dk_under_total": float(un["point"]),
                     "over_price": float(ov["price"]), "under_price": float(un["price"]),
                     "dk_abs_spread": float(abs(sp[0]["point"])), "spread_points": "/".join(str(x["point"]) for x in sp)})
    return pd.DataFrame(rows), pd.DataFrame(status)


def payout(o: float) -> float:
    return o / 100 if o > 0 else 100 / -o


def main() -> None:
    stage = sys.argv[1] if len(sys.argv) > 1 else "A"
    os.makedirs(OUT, exist_ok=True)
    L = []
    safe = conservative_frame()
    base = baseline_forecast(safe)
    rot = rotation()
    # ---- quotes on the frozen dates (no outcomes involved)
    lk = lookup()
    quotes, status = [], []
    for season, dates in STAGES[stage].items():
        for d in dates:
            if not os.path.exists(os.path.join(QDATA, f"quotes_{d}.csv.gz")):
                L.append(f"{d}: no quote file (stage {stage} not pulled)")
                continue
            r, st = first_observed(d, season, lk)
            quotes.append(r)
            status.append(st)
    quotes, status = pd.concat(quotes, ignore_index=True), pd.concat(status, ignore_index=True)
    # ---- eligibility against the conservative frame
    bi = base.set_index("game_id")
    quotes["in_frame"] = quotes["game_id"].isin(bi.index)
    st = status.set_index("game_id")
    st.loc[quotes.loc[~quotes["in_frame"], "game_id"], "status"] = "outside the frame (non-D-I or missing inputs)"
    qq = quotes[quotes["in_frame"]].copy()
    played = (bi.loc[qq["game_id"], "home_rest"].to_numpy() <= 1) | (bi.loc[qq["game_id"], "away_rest"].to_numpy() <= 1)
    st.loc[qq.loc[played, "game_id"], "status"] = "team played the day before (rotation timing)"
    qq = qq[~played]
    st.loc[qq["game_id"], "status"] = "eligible"
    status = st.reset_index()
    # ---- predictions per evaluation season
    preds = []
    for season in sorted(qq["season"].unique()):
        trs = base[base["season"].between(season - 3, season - 1)].copy()
        trs = trs[trs["total"].notna() & trs["home_spread"].notna()]
        trs = trs[(trs["home_pts"] + trs["away_pts"]) != trs["total"]]              # pushes dropped
        y = ((trs["home_pts"] + trs["away_pts"]) > trs["total"]).astype(float).to_numpy()
        ftr = features(trs, trs["total"], trs["home_spread"].abs(), rot)
        mod_means = {m: float(ftr[m].mean()) for m in MODS}
        ftr = add_interactions(ftr, mod_means)
        mu, sd = ftr[FEATS].mean(), ftr[FEATS].std(ddof=0).replace(0, 1.0)
        w, res = fit_logit(((ftr[FEATS] - mu) / sd).to_numpy(float), y)
        L.append(f"season {season}: trained on {season - 3}-{season - 1}, {len(trs)} games, over rate {y.mean():.3f}, "
                 f"rotation missing {100 * ftr['rot_missing'].mean():.1f}%; converged {res.success} ({res.message}), "
                 f"grad norm {np.linalg.norm(res.jac):.2e}")
        L.append("  standardized coefficients: " + ", ".join(f"{k} {v:+.3f}" for k, v in zip(["intercept"] + FEATS, w)))
        json.dump({"season": int(season), "train": [int(season - 3), int(season - 1)], "lambda": LAM, "features": FEATS,
                   "intercept_and_coefs": [float(x) for x in w], "mean": mu.to_dict(), "sd": sd.to_dict(), "moderator_means": mod_means},
                  open(os.path.join(OUT, f"candidate_{season}.json"), "w"), indent=1)
        g = qq[qq["season"] == season].copy()
        b = bi.loc[g["game_id"]].reset_index()
        fe = add_interactions(features(b, pd.Series(g["dk_total"].to_numpy()), pd.Series(g["dk_abs_spread"].to_numpy()), rot), mod_means)
        z = w[0] + ((fe[FEATS] - mu) / sd).to_numpy(float) @ w[1:]
        p_over = 1 / (1 + np.exp(-z))
        g = g.reset_index(drop=True)
        g["rot_missing"] = fe["rot_missing"].to_numpy()
        g["kp_fallback"] = (b["kp_total"] == b["pred_total"]).to_numpy()
        g["bt_fallback"] = (b["bt_total"] == b["kp_total"]).to_numpy()
        g["model_total"] = b["final_total"].to_numpy()
        # baseline (live rule)
        edge = g["model_total"] - g["dk_total"]
        side_b = np.where(edge > 0, "over", "under")
        price_b = np.where(edge > 0, g["over_price"], g["under_price"])
        pb = np.minimum(0.5 + 0.014 * edge.abs(), 0.565)
        evb = pb * np.array([payout(o) for o in price_b]) - (1 - pb)
        g["base_side"], g["base_edge"], g["base_p"], g["base_ev"] = side_b, edge.abs(), pb, evb
        g["base_bet"] = (edge.abs() >= 3) & (evb >= 0.02)
        # candidate
        side_c = np.where(p_over >= 0.5, "over", "under")
        pc = np.where(p_over >= 0.5, p_over, 1 - p_over)
        price_c = np.where(p_over >= 0.5, g["over_price"], g["under_price"])
        evc = pc * np.array([payout(o) for o in price_c]) - (1 - pc)
        g["cand_p_over"], g["cand_side"], g["cand_ev"] = p_over, side_c, evc
        g["cand_bet"] = evc >= 0.02
        g["base_price"], g["cand_price"] = price_b, price_c
        preds.append(g)
    preds = pd.concat(preds, ignore_index=True)
    assert not {"home_pts", "away_pts", "points"} & set(preds.columns)
    path = os.path.join(OUT, f"predictions_{stage}.csv")
    preds.to_csv(path, index=False)
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(path + ".sha256", "w").write(f"{h}  predictions_{stage}.csv\n")
    status.to_csv(os.path.join(OUT, f"eligibility_{stage}.csv"), index=False)
    L.append(f"\npredictions_{stage}.csv sha256 {h}")
    L.append("eligibility by season:\n" + status.groupby(["season", "status"]).size().unstack(fill_value=0).to_string())
    L.append(f"eligible games {len(preds)}; left-censored {int(preds['left_censored'].sum())}; rotation missing {int(preds['rot_missing'].sum())}; "
             f"KenPom fallback {int(preds['kp_fallback'].sum())}; Torvik fallback {int(preds['bt_fallback'].sum())}; "
             f"total number differs Over/Under {int((preds['dk_total'] != preds['dk_under_total']).sum())}")
    L.append(f"bets: baseline {int(preds['base_bet'].sum())}, candidate {int(preds['cand_bet'].sum())}")
    open(os.path.join(OUT, f"build_{stage}.txt"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
