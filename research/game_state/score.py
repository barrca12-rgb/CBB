"""Scoring step (PLAN.md): 2025-26 forecasts for every pool and strategy from the frozen selections, written and
hashed before any result is joined (no score columns in the output).

    python -m research.game_state.score     # -> out/predictions.csv (+ .sha256), out/score.txt
"""
from __future__ import annotations

import hashlib
import json
import os

import numpy as np
import pandas as pd

from cbb import barttorvik, data, kenpom, projection
from research.game_state.common import OUT, ROOT, deltas, forecast, frames, shift
from research.quant3.study import opening_week
from research.rotation_totals.build import baseline_forecast, conservative_frame
from research.rotation_totals.strict import strict_inputs
from research.stage2_stability.common import frames as clean_frames

DAY = pd.Timedelta(days=1)
L: list[str] = []
MF, TF = projection.MARGIN_FEATURES, projection.TOTAL_FEATURES
E2F = TF + ["neutral", "conf_game"]


def say(s=""):
    L.append(s)
    print(s, flush=True)


def ridge_fc(train: pd.DataFrame, pred: pd.DataFrame, feats, target: str, first: int = 2013) -> np.ndarray:
    """Season-2026 forecast from a ridge (lambda 1) fit on train seasons first..2025."""
    tr = train[train["season"].between(first, 2025)]
    c = projection.ridge(tr[feats].to_numpy(float), tr[target].to_numpy(float))
    return c[0] + pred[feats].to_numpy(float) @ c[1:]


def prep(f: pd.DataFrame) -> pd.DataFrame:
    f = f.copy()
    for c in ("neutral", "conf_game"):
        f[c] = f[c].astype(float)
    f["margin"] = f["home_pts"] - f["away_pts"]
    f["points"] = f["home_pts"] + f["away_pts"]
    return f


def conservative_models(safe: pd.DataFrame, clean_tr: pd.DataFrame, D0, D1, fr) -> pd.DataFrame:
    """2026 forecasts on a conservative-input frame (all 2026 rows, so the opening-week rule sees full slates):
    baseline, F candidates, R candidates and control, E2 and C2. Weights from the clean (leak-fixed) training frame."""
    s = prep(safe[safe["season"] == 2026])
    tr = prep(clean_tr)
    tr14 = tr[tr["season"] >= 2014]
    out = pd.DataFrame({"game_id": s["game_id"].to_numpy(), "date": pd.to_datetime(s["date"]).to_numpy(),
                        "kp_total": s["kp_total"].to_numpy(), "season": 2026})

    def tot(pred, train, feats=TF, first=2013):
        o = out[["game_id", "date", "kp_total", "season"]].copy()
        o["final_total"] = ridge_fc(train, pred, feats, "points", first)
        return opening_week(o)["final_total"].to_numpy()

    out["m_base"] = ridge_fc(tr, s, MF, "margin")
    out["t_base"] = tot(s, tr)
    out["m_F"] = ridge_fc(tr, shift(s, D1, fr["spread"]["families"]["F"]["variant"]), MF, "margin")
    out["t_F"] = tot(shift(s, D1, fr["total"]["families"]["F"]["variant"]), tr)
    rs, rt = fr["spread"]["families"]["R"]["variant"], fr["total"]["families"]["R"]["variant"]
    out["m_R"] = ridge_fc(shift(tr14, D0, rs), shift(s, D1, rs), MF, "margin", 2014)
    out["t_R"] = tot(shift(s, D1, rt), shift(tr14, D0, rt), TF, 2014)
    out["m_Rc"] = ridge_fc(tr14, s, MF, "margin", 2014)
    out["t_Rc"] = tot(s, tr14, TF, 2014)
    out["t_E2"] = tot(s, tr, E2F)
    out["t_C2"] = out["t_base"] - 0.61
    return out.set_index("game_id")


def strict_safe(safe: pd.DataFrame, dates) -> pd.DataFrame:
    """Conservative frame with KenPom from the archive dated D-2 and Torvik dated D-3 or earlier on `dates`, for
    margins and totals (rotation_totals Amendment 1; the totals part is strict.strict_inputs itself)."""
    s = strict_inputs(safe, dates)
    d = pd.to_datetime(s["date"])
    orig_before = barttorvik.before
    for date in dates:
        D = pd.Timestamp(date)
        m = d == D
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
    return s


def coverage(lag: int) -> pd.Series:
    """Per 2026 game: True if both teams have valid play-by-play for >= 90% of their earlier same-season games
    (games before D - lag)."""
    g, t = data.season_games(2026)
    G = pd.read_parquet(os.path.join(OUT, "games_2026.parquet"))
    valid = set(G.loc[G["valid"], "game_id"])
    t = t.assign(v=t["game_id"].isin(valid))
    res = {}
    for _, r in g.iterrows():
        cut = r["date"] - pd.Timedelta(days=lag)
        ok = True
        for team in (r["home_id"], r["away_id"]):
            h = t[(t["team_id"] == team) & (t["date"] < cut)]
            if len(h) and h["v"].mean() < 0.9:
                ok = False
        res[r["game_id"]] = ok
    return pd.Series(res)


def main() -> None:
    fr = json.load(open(os.path.join(OUT, "frozen.json")))
    D0 = deltas(0, range(2014, 2027))
    D1 = deltas(1, [2026])
    fF_s, fF_t = fr["spread"]["families"]["F"]["variant"], fr["total"]["families"]["F"]["variant"]
    fR_s, fR_t = fr["spread"]["families"]["R"]["variant"], fr["total"]["families"]["R"]["variant"]
    say(f"frozen: spreads F={fF_s}, R={fR_s}; totals F={fF_t}, R={fR_t}; decision families {fr['spread']['decision_family']}/{fr['total']['decision_family']}")
    cov0, cov1 = coverage(0), coverage(1)
    say(f"coverage pool (>=90% valid play-by-play for both teams' earlier games): lag 0 {cov0.mean():.4f}, lag 1 {cov1.mean():.4f} of 2025-26 games")

    # ---------- pool A: closing lines, live-like frame, lag-0 deltas
    train, pred = frames()
    base = forecast(train, pred)
    Fs = forecast(train, shift(pred, D0, fF_s))
    Ft = forecast(train, shift(pred, D0, fF_t))
    t14 = train[train["season"] >= 2014]
    Rc = forecast(t14, pred)
    Rs = forecast(shift(t14, D0, fR_s), shift(pred, D0, fR_s))
    Rt = forecast(shift(t14, D0, fR_t), shift(pred, D0, fR_t))
    from research.persistent_disagreement.score import e2_totals, v2_margin
    e2, v2 = e2_totals(), v2_margin()
    a = base[(base["season"] == 2026) & ~base["swapped"]].set_index("game_id")
    gi = a.index
    chk = (v2["final_margin"].reindex(gi) - a["final_margin"]).abs().max()
    say(f"pool A: lineup v2 frame's v1 margin vs baseline, max difference {chk:.2e}")
    preds = []
    at = a[a["total"].notna()]
    fc = {"baseline": at["final_total"], "F": Ft.set_index("game_id")["final_total"].reindex(at.index),
          "R": Rt.set_index("game_id")["final_total"].reindex(at.index), "Rctrl": Rc.set_index("game_id")["final_total"].reindex(at.index),
          "E2": e2.reindex(at.index), "C2": at["final_total"] - 0.61}
    preds.append(pd.DataFrame({"pool": "A-tot closing totals", "market": "total", "game_id": at.index, "date": at["date"].dt.strftime("%Y-%m-%d").to_numpy(),
                               "line": at["total"].to_numpy(), "price_pos": -110.0, "price_neg": -110.0, "price_kind": "assumed -110",
                               "coverage": at.index.map(cov0).to_numpy(), **{f"fc_{k}": v.to_numpy() for k, v in fc.items()}}))
    asp = a[a["home_spread"].notna()]
    fc = {"baseline": asp["final_margin"], "F": Fs.set_index("game_id")["final_margin"].reindex(asp.index),
          "R": Rs.set_index("game_id")["final_margin"].reindex(asp.index), "Rctrl": Rc.set_index("game_id")["final_margin"].reindex(asp.index),
          "v2": v2["v2_margin"].reindex(asp.index)}
    preds.append(pd.DataFrame({"pool": "A-spr closing spreads", "market": "spread", "game_id": asp.index, "date": asp["date"].dt.strftime("%Y-%m-%d").to_numpy(),
                               "line": asp["home_spread"].to_numpy(), "price_pos": -110.0, "price_neg": -110.0, "price_kind": "assumed -110",
                               "coverage": asp.index.map(cov0).to_numpy(), **{f"fc_{k}": v.to_numpy() for k, v in fc.items()}}))

    # ---------- pool B: ESPN openers (untimestamped; descriptive), conservative inputs, lag-1 deltas
    safe = conservative_frame()
    clean_tr, _ = clean_frames(clean=True)
    cm = conservative_models(safe, clean_tr, D0, D1, fr)
    bt = baseline_forecast(safe).set_index("game_id")
    say(f"pool B: conservative baseline totals vs rotation_totals.baseline_forecast, max difference "
        f"{(bt['final_total'].reindex(cm.index) - cm['t_base']).abs().max():.2e}")
    pb = pred[(pred["season"] == 2026) & ~pred["swapped"]].set_index("game_id")       # oriented openers, swap flag
    adj = v2["adj"]
    bta = pb[pb["open_total"].notna()].index.intersection(cm.index)
    preds.append(pd.DataFrame({"pool": "B-tot ESPN opener totals", "market": "total", "game_id": bta, "date": pb.loc[bta, "date"].astype(str).str[:10].to_numpy(),
                               "line": pb.loc[bta, "open_total"].to_numpy(), "price_pos": -110.0, "price_neg": -110.0, "price_kind": "assumed -110",
                               "coverage": bta.map(cov1).to_numpy(), **{f"fc_{k}": cm.loc[bta, c].to_numpy() for k, c in
                                                                        (("baseline", "t_base"), ("F", "t_F"), ("R", "t_R"), ("Rctrl", "t_Rc"), ("E2", "t_E2"), ("C2", "t_C2"))}}))
    bsa = pb[pb["open_home_spread"].notna() & pb["home_spread"].notna()].index.intersection(cm.index)
    beta = float(v2["beta"].dropna().iloc[-1])
    preds.append(pd.DataFrame({"pool": "B-spr ESPN opener spreads", "market": "spread", "game_id": bsa, "date": pb.loc[bsa, "date"].astype(str).str[:10].to_numpy(),
                               "line": pb.loc[bsa, "open_home_spread"].to_numpy(), "price_pos": -110.0, "price_neg": -110.0, "price_kind": "assumed -110",
                               "coverage": bsa.map(cov1).to_numpy(), **{f"fc_{k}": cm.loc[bsa, c].to_numpy() for k, c in
                                                                        (("baseline", "m_base"), ("F", "m_F"), ("R", "m_R"), ("Rctrl", "m_Rc"))},
                               "fc_v2": cm.loc[bsa, "m_base"].to_numpy() + beta * adj.reindex(bsa).fillna(0.0).to_numpy()}))
    say(f"lineup v2 beta 2025-26 {beta:.4f}")

    # ---------- pool C: DraftKings first observed (dated sample), recorded prices, strict inputs, lag-1 deltas
    rt = pd.read_csv(os.path.join(ROOT, "research", "rotation_totals", "out", "predictions_A_strict.csv"), parse_dates=["decision_at"])
    rt = rt[rt["season"] == 2026].set_index("game_id")
    dates = sorted(rt["date"].unique())
    st = strict_safe(safe, dates)
    cs = conservative_models(st, clean_tr, D0, D1, fr)            # strict inputs (day-before decisions)
    et = rt["decision_at"].dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None)
    dayb = ((et - pd.to_datetime(rt["date"])).dt.days == -1)
    pick = lambda col: np.where(dayb, cs.loc[rt.index, col], cm.loc[rt.index, col])
    chk = np.abs(pick("t_base") - rt["model_total"].to_numpy()).max()
    say(f"pool C totals: baseline vs rotation_totals strict model_total, max difference {chk:.2e}")
    preds.append(pd.DataFrame({"pool": "C-tot DraftKings first observed totals", "market": "total", "game_id": rt.index, "date": rt["date"].to_numpy(),
                               "line": rt["dk_total"].to_numpy(), "price_pos": rt["over_price"].to_numpy(), "price_neg": rt["under_price"].to_numpy(),
                               "price_kind": "recorded", "coverage": rt.index.map(cov1).to_numpy(),
                               **{f"fc_{k}": pick(c) for k, c in (("baseline", "t_base"), ("F", "t_F"), ("R", "t_R"), ("Rctrl", "t_Rc"), ("E2", "t_E2"), ("C2", "t_C2"))},
                               "rot_side": np.where(rt["cand_bet"], np.where(rt["cand_side"] == "over", 1, -1), 0),
                               "decision_at": rt["decision_at"].astype(str).to_numpy()}))
    pc = pd.read_csv(os.path.join(ROOT, "research", "persistent_disagreement", "out", "predictions.csv"))
    pc = pc[pc["pool"].str.startswith("C")].set_index("game_id")
    assert set(pc.index) == set(rt.index)
    ms = pick("m_base")
    pc_model = pc.loc[rt.index, "edge_baseline"].to_numpy() - pc.loc[rt.index, "line"].to_numpy()
    say(f"pool C spreads: baseline margin vs persistent_disagreement pool C strict margin, max difference {np.abs(ms - pc_model).max():.2e}")
    preds.append(pd.DataFrame({"pool": "C-spr DraftKings first observed spreads", "market": "spread", "game_id": rt.index, "date": rt["date"].to_numpy(),
                               "line": pc.loc[rt.index, "line"].to_numpy(), "price_pos": pc.loc[rt.index, "price_pos"].to_numpy(),
                               "price_neg": pc.loc[rt.index, "price_neg"].to_numpy(), "price_kind": "recorded", "coverage": rt.index.map(cov1).to_numpy(),
                               **{f"fc_{k}": pick(c) for k, c in (("baseline", "m_base"), ("F", "m_F"), ("R", "m_R"), ("Rctrl", "m_Rc"))},
                               "fc_v2": ms + beta * adj.reindex(rt.index).fillna(0.0).to_numpy(),
                               "decision_at": rt["decision_at"].astype(str).to_numpy()}))
    p = pd.concat(preds, ignore_index=True)
    assert not {"home_pts", "away_pts", "margin", "points"} & set(p.columns)
    path = os.path.join(OUT, "predictions.csv")
    p.to_csv(path, index=False)
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(path + ".sha256", "w").write(f"{h}  predictions.csv\n")
    say("opportunities: " + ", ".join(f"{k}: {v}" for k, v in p.groupby("pool").size().items()))
    say("coverage-pool share: " + ", ".join(f"{k[:5]} {v:.3f}" for k, v in p.groupby("pool")["coverage"].mean().items()))
    say(f"predictions.csv sha256 {h}")
    open(os.path.join(OUT, "score.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
