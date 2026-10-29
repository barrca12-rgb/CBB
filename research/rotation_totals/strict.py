"""Strict-cutoff rebuild of Stage A (Chad's review, Oct 29): every input dated before the actual decision timestamp.

Finding (out/strict_A.txt): 565 of 597 decisions were made on the day before the game (earliest 11:55 ET). Stage-1
ratings, Four Factors, season average, rotation and market closes stop at games of D-2 (the last D-2 tip was at
least 11.9 h before the earliest decision). KenPom's archive dated D-1 holds ratings at the start of D-1 (checked:
the opening-day archive equals the preseason ratings), but its publication time on D-1 is not verifiable; the same
holds for Torvik's file dated D-2. So for decisions made on D-1 this rebuild uses KenPom's archive dated D-2 and the
latest Torvik file dated D-3 or earlier, both published before any D-1 decision. Decisions made on game day keep
the D-1 archive and the D-2 file (published the day before). The candidate (out/candidate_<season>.json) and the
baseline's stage-2 weights are unchanged (frozen); only these inputs and the opening-week day mean move.

    python -m research.rotation_totals.strict      # -> out/predictions_A_strict.csv (+ .sha256), out/strict_A.txt
    python -m research.rotation_totals.grade A_strict
"""
from __future__ import annotations

import hashlib
import json
import os

import numpy as np
import pandas as pd

from cbb import barttorvik, kenpom
from research.rotation_totals.build import (FEATS, OUT, add_interactions, baseline_forecast, conservative_frame, features,
                                            payout, rotation)

DAY = pd.Timedelta(days=1)


def strict_inputs(safe: pd.DataFrame, dates: list[str]) -> pd.DataFrame:
    """KenPom from the archive dated D-2 and Torvik from the latest file dated D-3 or earlier, for the full slate of
    each evaluation date (the opening-week rule averages over the slate)."""
    s = safe.copy()
    d = pd.to_datetime(s["date"])
    orig_before = barttorvik.before
    for date in dates:
        D = pd.Timestamp(date)
        m = d == D
        g = s.loc[m, ["game_id", "home_id", "away_id", "neutral", "date"]]
        k = kenpom._predict(kenpom.archive((D - 2 * DAY).strftime("%Y-%m-%d")), g).set_index("game_id")
        s.loc[m, "kp_total"] = s.loc[m, "game_id"].map(k["kp_total"]).fillna(s.loc[m, "pred_total"]).to_numpy()
        s.loc[m, "kp_total_x_early"] = s.loc[m, "kp_total"] * s.loc[m, "early"]
        barttorvik.before = lambda day: orig_before(pd.Timestamp(day) - 2 * DAY)   # file dated D-3 or earlier
        try:
            bt = barttorvik.predict(g).set_index("game_id")
        finally:
            barttorvik.before = orig_before
        s.loc[m, "bt_total"] = s.loc[m, "game_id"].map(bt["bt_total"]).fillna(s.loc[m, "kp_total"]).to_numpy()
    return s


def main() -> None:
    p = pd.read_csv(os.path.join(OUT, "predictions_A.csv"), parse_dates=["decision_at"])
    et = p["decision_at"].dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None)
    p["decision_day"] = (et - pd.to_datetime(p["date"])).dt.days          # -1 = day before, 0 = game day
    safe = conservative_frame()
    base_orig = baseline_forecast(safe).set_index("game_id")
    strict = strict_inputs(safe, sorted(p["date"].unique()))
    base_strict = baseline_forecast(strict).set_index("game_id")
    rot = rotation()
    L = [f"decisions by day relative to the game (ET): {p['decision_day'].value_counts().sort_index().to_dict()}"]
    rows = []
    for season, g in p.groupby("season"):
        c = json.load(open(os.path.join(OUT, f"candidate_{season}.json")))
        w, mu, sd, mods = np.array(c["intercept_and_coefs"]), pd.Series(c["mean"]), pd.Series(c["sd"]), c["moderator_means"]
        g = g.reset_index(drop=True)
        use = np.where(g["decision_day"] == -1, "strict", "orig")
        b = pd.concat([base_strict.loc[[gid]] if u == "strict" else base_orig.loc[[gid]] for gid, u in zip(g["game_id"], use)]).reset_index()
        fe = add_interactions(features(b, pd.Series(g["dk_total"].to_numpy()), pd.Series(g["dk_abs_spread"].to_numpy()), rot), mods)
        z = w[0] + ((fe[FEATS] - mu[FEATS]) / sd[FEATS]).to_numpy(float) @ w[1:]
        p_over = 1 / (1 + np.exp(-z))
        g["inputs"] = use
        g["kp_change"] = b["kp_total"].to_numpy() - base_orig.loc[g["game_id"], "kp_total"].to_numpy()
        g["model_total"] = b["final_total"].to_numpy()
        edge = g["model_total"] - g["dk_total"]
        price_b = np.where(edge > 0, g["over_price"], g["under_price"])
        pb = np.minimum(0.5 + 0.014 * edge.abs(), 0.565)
        evb = pb * np.array([payout(o) for o in price_b]) - (1 - pb)
        g["base_side"], g["base_edge"], g["base_p"], g["base_ev"], g["base_price"] = np.where(edge > 0, "over", "under"), edge.abs(), pb, evb, price_b
        g["base_bet"] = (edge.abs() >= 3) & (evb >= 0.02)
        pc = np.where(p_over >= 0.5, p_over, 1 - p_over)
        price_c = np.where(p_over >= 0.5, g["over_price"], g["under_price"])
        evc = pc * np.array([payout(o) for o in price_c]) - (1 - pc)
        g["cand_p_over"], g["cand_side"], g["cand_ev"], g["cand_price"] = p_over, np.where(p_over >= 0.5, "over", "under"), evc, price_c
        g["cand_bet"] = evc >= 0.02
        rows.append(g)
    q = pd.concat(rows, ignore_index=True)
    a = pd.read_csv(os.path.join(OUT, "predictions_A.csv"))
    L.append(f"rows rebuilt with D-2 KenPom / D-3 Torvik: {int((q['inputs'] == 'strict').sum())}; KenPom total change "
             f"mean |{q.loc[q['inputs'] == 'strict', 'kp_change'].abs().mean():.2f}| pts")
    for who in ("base", "cand"):
        same = (a[f"{who}_bet"].to_numpy() == q[f"{who}_bet"].to_numpy()) & ((~q[f"{who}_bet"]) | (a[f"{who}_side"].to_numpy() == q[f"{who}_side"].to_numpy()))
        L.append(f"{who}: bets {int(a[f'{who}_bet'].sum())} -> {int(q[f'{who}_bet'].sum())}; games whose decision changed: {int((~same).sum())}")
    path = os.path.join(OUT, "predictions_A_strict.csv")
    q.to_csv(path, index=False)
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(path + ".sha256", "w").write(f"{h}  predictions_A_strict.csv\n")
    L.append(f"predictions_A_strict.csv sha256 {h}")
    open(os.path.join(OUT, "strict_A.txt"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
