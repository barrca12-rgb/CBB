"""Scoring step (PLAN.md): 2025-26 predictions for pools A, B and C from the frozen settings, written and hashed before
any result is joined (outcome columns are dropped).

    python -m research.persistent_disagreement.score    # -> out/predictions.csv (+ .sha256), out/score.txt
"""
from __future__ import annotations

import hashlib
import json
import os

import numpy as np
import pandas as pd

from cbb import barttorvik, kenpom, projection, teams
from research.market.s1_sample_report import lookup
from research.persistent_disagreement.common import OUT, ROOT, baseline, design, feats
from research.quant.common import base_frames, fit_predict
from research.quant3.study import opening_week
from research.rotation_totals.build import conservative_frame
from research.stage2_stability.common import frames as clean_frames

DAY = pd.Timedelta(days=1)
QDATA = os.path.join(ROOT, "research", "market", "data")
L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def model_preds(d0, f, cfg):
    mu, sd = pd.Series(cfg["mu"]), pd.Series(cfg["sd"])
    b = np.array(cfg["candidate_coefs[D0, D0*V, D0*Sdir, S]"])
    return design(np.asarray(d0, float), f, mu, sd) @ b, cfg["comparator_c"] * np.asarray(d0, float)


def e2_totals() -> pd.Series:
    """E2 specification: walk-forward with neutral + conference-game terms, opening-week rule (frozen E2 untouched)."""
    train, pred = base_frames()
    t2, p2 = train.copy(), pred.copy()
    for d in (t2, p2):
        d["neutral"], d["conf_game"] = d["neutral"].astype(float), d["conf_game"].astype(float)
    e2 = opening_week(fit_predict(t2, p2, tf=projection.TOTAL_FEATURES + ["neutral", "conf_game"]))
    return e2.set_index("game_id")["final_total"]


def v2_margin() -> pd.DataFrame:
    from research.v2_lineup.backtest import frame
    v = frame()
    return v.set_index("game_id")[["final_margin", "beta", "adj", "v2_margin"]]


def strict_margins(dates) -> pd.DataFrame:
    """Pool C model margins: conservative frame (stage 1 before D-1, market ratings before D-1, crews 0) with KenPom
    from the archive dated D-2 and Torvik dated D-3 or earlier (strict rule for day-before decisions), and with the
    D-1 archive / D-2 file (the conservative frame as is) for game-day decisions; walk-forward v1 margin weights."""
    safe = conservative_frame()
    train, _ = clean_frames(clean=True)
    train = train.assign(margin=train["home_pts"] - train["away_pts"])
    mf = projection.MARGIN_FEATURES
    c = projection.ridge(train[train["season"].between(2013, 2025)][mf].to_numpy(float),
                         train[train["season"].between(2013, 2025)]["margin"].to_numpy(float))
    s = safe[pd.to_datetime(safe["date"]).isin(pd.to_datetime(dates))].copy()
    orig = s.copy()
    orig_before = barttorvik.before
    for date in dates:
        D = pd.Timestamp(date)
        m = pd.to_datetime(s["date"]) == D
        g = s.loc[m, ["game_id", "home_id", "away_id", "neutral", "date"]]
        k = kenpom._predict(kenpom.archive((D - 2 * DAY).strftime("%Y-%m-%d")), g).set_index("game_id")
        s.loc[m, "kp_margin"] = s.loc[m, "game_id"].map(k["kp_margin"]).fillna(s.loc[m, "pred_margin"]).to_numpy()
        s.loc[m, "kp_margin_x_early"] = s.loc[m, "kp_margin"] * s.loc[m, "early"]
        barttorvik.before = lambda day: orig_before(pd.Timestamp(day) - 2 * DAY)
        try:
            bt = barttorvik.predict(g).set_index("game_id")
        finally:
            barttorvik.before = orig_before
        s.loc[m, "bt_margin"] = s.loc[m, "game_id"].map(bt["bt_margin"]).fillna(s.loc[m, "kp_margin"]).to_numpy()
    out = pd.DataFrame({"game_id": s["game_id"].to_numpy(),
                        "strict_margin": c[0] + s[mf].to_numpy(float) @ c[1:],
                        "gameday_margin": c[0] + orig[mf].to_numpy(float) @ c[1:]})
    return out.set_index("game_id")


def dk_spreads(date: str, decision: pd.DataFrame, lk: dict) -> pd.DataFrame:
    """DraftKings spread number and both prices at each game's recorded decision snapshot (state rebuilt from the
    change-only log: latest row per outcome at or before the snapshot; 'absent' removes it)."""
    q = pd.read_csv(os.path.join(QDATA, f"quotes_{date}.csv.gz"))
    q = q[(q["book"] == "draftkings") & (q["market"] == "spreads")].copy()
    q["snapshot"] = pd.to_datetime(q["snapshot"], utc=True, format="ISO8601")
    q["tid"] = q["outcome"].map(lambda n: lk.get(teams.norm(n or "")))
    rows = []
    for _, r in decision.iterrows():
        x = q[(q["event_id"] == r["event_id"]) & (q["snapshot"] <= r["decision_at"])].sort_values("snapshot")
        st = x.groupby("outcome").tail(1)
        st = st[st["status"] != "absent"]
        h, a = st[st["tid"] == r["home_id"]], st[st["tid"] == r["away_id"]]
        if len(h) != 1 or len(a) != 1:
            rows.append({"game_id": r["game_id"], "dk_home_spread": np.nan})
            continue
        rows.append({"game_id": r["game_id"], "dk_home_spread": float(h["point"].iloc[0]),
                     "home_price": float(h["price"].iloc[0]), "away_price": float(a["price"].iloc[0])})
    return pd.DataFrame(rows)


def main() -> None:
    cfg = json.load(open(os.path.join(OUT, "frozen.json")))
    w = baseline()
    h0, h1 = pd.read_pickle(os.path.join(OUT, "history_lag0.pkl")), pd.read_pickle(os.path.join(OUT, "history_lag1.pkl"))
    s = w[(w["season"] == 2026) & ~w["swapped"]]
    preds = []
    # ---- pool A: closing totals, assumed -110
    ct = cfg["total"]
    a = s[s["total"].notna() & s["final_total"].notna()]
    d0 = a["final_total"] - a["total"]
    f = feats(h0[ct["N"]].loc[a.index], d0, "total", ct["k"])
    cand, comp = model_preds(d0, f, ct)
    e2 = a["game_id"].map(e2_totals())
    preds.append(pd.DataFrame({"pool": "A closing totals", "game_id": a["game_id"].to_numpy(), "date": a["date"].dt.strftime("%Y-%m-%d").to_numpy(),
                               "line": a["total"].to_numpy(), "price_pos": -110.0, "price_neg": -110.0, "price_kind": "assumed -110",
                               "edge_baseline": d0.to_numpy(), "edge_comparator": comp, "edge_candidate": cand,
                               "edge_existing": (e2 - a["total"]).to_numpy(), "existing": "E2 specification",
                               "edge_c2": (d0 - 0.61).to_numpy(), "S": f["S"].to_numpy(), "V": f["V"].to_numpy(), "n_hist": h0[ct["N"]].loc[a.index, "n"].to_numpy()}))
    # ---- pool B: early spreads at the ESPN opener (untimestamped), assumed -110
    cs = cfg["spread"]
    b = s[s["open_home_spread"].notna() & s["home_spread"].notna() & s["final_margin"].notna()]
    d0 = b["final_margin"] + b["open_home_spread"]
    f = feats(h1[cs["N"]].loc[b.index], d0, "spread", cs["k"])
    cand, comp = model_preds(d0, f, cs)
    v2 = v2_margin()
    chk = (b["game_id"].map(v2["final_margin"]) - b["final_margin"]).abs().max()
    say(f"pool B: lineup v2 frame's v1 margin vs ours, max difference {chk:.2e}; v2 beta 2025-26 {v2['beta'].dropna().loc[b['game_id']].iloc[0]:.4f}")
    preds.append(pd.DataFrame({"pool": "B early spreads (ESPN opener)", "game_id": b["game_id"].to_numpy(), "date": b["date"].dt.strftime("%Y-%m-%d").to_numpy(),
                               "line": b["open_home_spread"].to_numpy(), "price_pos": -110.0, "price_neg": -110.0, "price_kind": "assumed -110",
                               "edge_baseline": d0.to_numpy(), "edge_comparator": comp, "edge_candidate": cand,
                               "edge_existing": (b["game_id"].map(v2["v2_margin"]) + b["open_home_spread"]).to_numpy(), "existing": "lineup v2",
                               "S": f["S"].to_numpy(), "V": f["V"].to_numpy(), "n_hist": h1[cs["N"]].loc[b.index, "n"].to_numpy()}))
    # ---- pool C: DraftKings first-observed spreads on the dated 2025-26 sample, recorded prices
    rt = pd.read_csv(os.path.join(ROOT, "research", "rotation_totals", "out", "predictions_A.csv"), parse_dates=["decision_at"])
    rt = rt[rt["season"] == 2026]          # eligible: complete DraftKings market before tip, D-I, no team played D-1
    wi = w.set_index("game_id")
    rt["home_id"], rt["away_id"] = rt["game_id"].map(wi["home_id"]), rt["game_id"].map(wi["away_id"])
    lk = lookup()
    q = pd.concat([dk_spreads(d, g, lk) for d, g in rt.groupby("date")]).set_index("game_id")
    sm = strict_margins(sorted(rt["date"].unique()))
    et = rt["decision_at"].dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None)
    dayb = (et - pd.to_datetime(rt["date"])).dt.days == -1
    rt["model"] = np.where(dayb, rt["game_id"].map(sm["strict_margin"]), rt["game_id"].map(sm["gameday_margin"]))
    rt = rt.join(q, on="game_id")
    excl = rt["dk_home_spread"].isna() | rt["model"].isna() | ~rt["game_id"].isin(wi.index)
    say(f"pool C: {len(rt)} eligible games from the dated sample; excluded {int(excl.sum())} (no DraftKings spread pair at the snapshot or no model row)")
    c = rt[~excl].copy()
    idx = w.reset_index().set_index("game_id").loc[c["game_id"], "index"].to_numpy()
    d0 = c["model"].to_numpy() + c["dk_home_spread"].to_numpy()
    f = feats(h1[cs["N"]].loc[idx].reset_index(drop=True), pd.Series(d0), "spread", cs["k"])
    cand, comp = model_preds(d0, f, cs)
    adj = c["game_id"].map(v2["adj"]).fillna(0.0).to_numpy()
    beta = float(v2["beta"].dropna().loc[b["game_id"]].iloc[0])
    preds.append(pd.DataFrame({"pool": "C early spreads (DraftKings first observed)", "game_id": c["game_id"].to_numpy(), "date": c["date"].to_numpy(),
                               "line": c["dk_home_spread"].to_numpy(), "price_pos": c["home_price"].to_numpy(), "price_neg": c["away_price"].to_numpy(),
                               "price_kind": "recorded", "edge_baseline": d0, "edge_comparator": comp, "edge_candidate": cand,
                               "edge_existing": d0 + beta * adj, "existing": "lineup v2", "S": f["S"].to_numpy(), "V": f["V"].to_numpy(),
                               "n_hist": h1[cs["N"]].loc[idx, "n"].to_numpy(), "decision_at": c["decision_at"].astype(str).to_numpy()}))
    p = pd.concat(preds, ignore_index=True)
    assert not {"home_pts", "away_pts", "margin", "points"} & set(p.columns)
    path = os.path.join(OUT, "predictions.csv")
    p.to_csv(path, index=False)
    hsh = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(path + ".sha256", "w").write(f"{hsh}  predictions.csv\n")
    say(f"opportunities: " + ", ".join(f"{k}: {v}" for k, v in p.groupby("pool").size().items()))
    say(f"predictions.csv sha256 {hsh}")
    open(os.path.join(OUT, "score.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
