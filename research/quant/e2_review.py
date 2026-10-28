"""E2 deployment review (Chad, Oct 28): the deployable version, its inputs at prediction time, double counting, and
before/after predictions and selections on the current cards. Read only; nothing live changes.

    python -m research.quant.e2_review        # -> out/e2_review.txt, out/e2_current_games.csv
"""
from __future__ import annotations

import json
import os
import re

import numpy as np
import pandas as pd

from cbb import projection, run_day
from research.quant.common import OUT, SEASONS, base_frames

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
TF_E2 = projection.TOTAL_FEATURES + ["neutral", "conf_game"]
COEF = json.load(open(os.path.join(OUT, "e2_coefficients.json")))


def prep(b: pd.DataFrame) -> pd.DataFrame:
    return b.assign(neutral=b["neutral"].astype(float), conf_game=b["conf_game"].astype(float))


def walk(train, pred, tf):
    """Production code path: projection.walk_forward with the totals feature list swapped (margin untouched)."""
    old = projection.TOTAL_FEATURES
    projection.TOTAL_FEATURES = tf
    try:
        w = projection.walk_forward(pd.concat([train.assign(_tr=1), pred.assign(_tr=0)]), first_train=2013)
    finally:
        projection.TOTAL_FEATURES = old
    return w


def wf(train, pred, tf):
    """Fit on train rows of seasons < s (2013 on), predict pred rows of season s, with projection.ridge."""
    out = pred.copy()
    out["final_total"] = np.nan
    for s in SEASONS:
        tr = train[(train["season"] < s) & (train["season"] >= 2013)]
        ct = projection.ridge(tr[tf].to_numpy(float), tr["points"].to_numpy(float))
        te = out["season"] == s
        out.loc[te, "final_total"] = ct[0] + out.loc[te, tf].to_numpy(float) @ ct[1:]
    return out[out["season"].isin(SEASONS)]


def opening_week(w: pd.DataFrame) -> pd.DataFrame:
    """The live opening-week rule applied to a backtest: through each season's first 7 days, shift every game's total
    by that day's mean gap to KenPom."""
    w = w.copy()
    d = pd.to_datetime(w["date"])
    first = d.groupby(w["season"]).transform("min")
    ow = d < first + pd.Timedelta(days=7)
    gap = (w["final_total"] - w["kp_total"]).groupby([w["season"], d]).transform("mean")
    w.loc[ow & gap.notna(), "final_total"] = w.loc[ow & gap.notna(), "final_total"] - gap[ow & gap.notna()]
    return w, ow


def current(day: str) -> pd.DataFrame:
    """One card day: v1 and E2 totals (before and after the opening-week shift) and both verdicts at the card's lines."""
    f = pd.read_csv(os.path.join(ROOT, "reports", f"features_{day}.csv"))
    card = pd.read_csv(os.path.join(ROOT, "reports", f"cbb_{day}.csv"))
    html = open(os.path.join(ROOT, "reports", f"cbb_{day}.html")).read()
    D = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))
    lines = {g["game_id"]: pd.DataFrame(g.get("book_lines") or []) for g in D["games"]}
    sl = run_day.slate(pd.Timestamp(day))                         # ESPN scoreboard: neutralSite, conferenceCompetition
    f = f.merge(sl[["game_id", "conf_game"]], on="game_id", how="left")
    f["neutral"] = f["neutral"].astype(float)
    f["conf_game"] = f["conf_game"].astype(float).fillna(0.0)
    f["e2_pre"] = COEF["intercept"] + sum(f[k].astype(float) * v for k, v in COEF.items() if k in TF_E2)
    f["v1_pre"] = f["final_total"]
    # opening-week rule, as run_day.opening_week_totals computes it for each version
    shift_v1, shift_e2 = 0.0, 0.0
    if "total_shift" in card and card["total_shift"].notna().any() and card["total_shift"].abs().max() > 0:
        shift_v1 = -(f["v1_pre"] - f["kp_total"]).mean()
        shift_e2 = -(f["e2_pre"] - f["kp_total"]).mean()
    f["v1_total"], f["e2_total"] = f["v1_pre"] + shift_v1, f["e2_pre"] + shift_e2
    k = card.set_index("game_id")
    rows = []
    for _, g in f.iterrows():
        l = lines.get(int(g["game_id"]), pd.DataFrame())
        r = {"date": day, "game": f"{g['away']} at {g['home']}" if not g["neutral"] else f"{g['away']} vs {g['home']}",
             "neutral": int(g["neutral"]), "conf": int(g["conf_game"]), "v1_total": round(g["v1_total"], 2),
             "e2_total": round(g["e2_total"], 2), "change": round(g["e2_total"] - g["v1_total"], 2),
             "card_model_total": round(float(k.loc[g["game_id"], "model_total"]), 2) if g["game_id"] in k.index else np.nan,
             "card_verdict": k.loc[g["game_id"], "total_verdict"] if g["game_id"] in k.index else None,
             "logged": k.loc[g["game_id"], "total_logged_pick"] if g["game_id"] in k.index and "total_logged_pick" in k else None}
        for tag, t in (("v1", g["v1_total"]), ("e2", g["e2_total"])):
            if len(l) and "total" in l:
                best = run_day._best(l, "total", {"over": ("total", lambda x, t=t: t - x, "over_odds"),
                                                  "under": ("total", lambda x, t=t: x - t, "under_odds")})
                if best:
                    side, row, edge, p, value = best
                    v, _ = run_day._call(edge, value, run_day.TOTAL_CALLS)
                    r[f"{tag}_pick"] = f"{side.title()} {row['total']:g} ({row['book']} {row.get(f'{side}_odds')})"
                    r[f"{tag}_edge"], r[f"{tag}_verdict"] = round(edge, 2), v
        rows.append(r)
    return pd.DataFrame(rows), shift_v1, shift_e2


def main() -> None:
    L = []
    train, pred = base_frames()
    train, pred = prep(train), prep(pred)
    # 1. the deployable version: production ridge, the exact feature list, fit 2013-2026
    c = projection.ridge(train[train["season"].between(2013, 2026)][TF_E2].to_numpy(float),
                         train[train["season"].between(2013, 2026)]["points"].to_numpy(float))
    frozen = np.array([COEF["intercept"]] + [COEF[k] for k in TF_E2])
    L.append(f"1. Deployable coefficients (projection.ridge, 2013-26, {len(TF_E2)} total features) vs frozen "
             f"out/e2_coefficients.json: max diff {np.abs(c - frozen).max():.1e}")
    # its walk-forward through the production ridge reproduces the reported gains
    b, e = wf(train, pred, projection.TOTAL_FEATURES), wf(train, pred, TF_E2)
    ev = b["season"] >= 2020
    gain = (b["points"] - b["final_total"]).abs() - (e["points"] - e["final_total"]).abs()
    L.append(f"   Walk-forward with projection.ridge: 2020-26 totals MAE {np.abs(b.loc[ev, 'points'] - b.loc[ev, 'final_total']).mean():.4f} -> "
             f"{np.abs(e.loc[ev, 'points'] - e.loc[ev, 'final_total']).mean():.4f} (gain {gain[ev].mean():+.4f}); by season "
             + ", ".join(f"{s} {gain[b['season'] == s].mean():+.4f}" for s in range(2020, 2027)))
    # the frozen v1 totals are unchanged by the refactor (v1 path reproduces the live coefficients)
    live = json.load(open(os.path.join(ROOT, "data", "projection.json")))
    cv = projection.ridge(train[train["season"].between(2013, 2026)][projection.TOTAL_FEATURES].to_numpy(float),
                          train[train["season"].between(2013, 2026)]["points"].to_numpy(float))
    L.append(f"   v1 totals refit vs live projection.json: max diff "
             f"{max(abs(cv[0] - live['total']['intercept']), *(abs(cv[1 + i] - live['total'][k]) for i, k in enumerate(projection.TOTAL_FEATURES))):.1e}")
    # 2. availability: the training flags and the live flags are the same ESPN fields
    L.append("2. Inputs at prediction time: training uses the ESPN schedule's neutral_site and conference_competition "
             "(cbb/data.py); the live card reads the same ESPN scoreboard fields, neutralSite and conferenceCompetition "
             "(cbb/run_day.slate), before tip. Both reach the stage-2 frame (run_day.project joins the slate).")
    # 3. double counting: other site-aware inputs, residuals after E2
    nt = e["neutral"] == 1
    L.append("3. Double counting:")
    L.append(f"   stage-1 pred_total: the home edge enters +/- for the two teams and cancels in the total; altitude is 0 at "
             f"neutral sites (context.py); E2's neutral coefficient {COEF['neutral']:+.2f} is fit with every v1 input present.")
    for tag, w in (("v1", b), ("E2", e)):
        r = w["points"] - w["final_total"]
        L.append(f"   2020-26 mean residual, {tag}: neutral {r[ev & nt].mean():+.2f} (n {int((ev & nt).sum())}), "
                 f"home/away {r[ev & ~nt].mean():+.2f}; March neutral {r[ev & nt & (pd.to_datetime(w['date']).dt.month == 3)].mean():+.2f}")
    # the live opening-week rule (shift each day's totals to KenPom's mean) applied to both, 2020-26
    bo, ow = opening_week(b)
    eo, _ = opening_week(e)
    m = ev & ow
    L.append(f"   With the live opening-week rule, opening-week games 2020-26 (n {int(m.sum())}): MAE v1 "
             f"{np.abs(bo.loc[m, 'points'] - bo.loc[m, 'final_total']).mean():.3f}, E2 {np.abs(eo.loc[m, 'points'] - eo.loc[m, 'final_total']).mean():.3f} "
             f"(without the rule: v1 {np.abs(b.loc[m, 'points'] - b.loc[m, 'final_total']).mean():.3f}, E2 {np.abs(e.loc[m, 'points'] - e.loc[m, 'final_total']).mean():.3f}); "
             f"all 2020-26 with the rule: v1 {np.abs(bo.loc[ev, 'points'] - bo.loc[ev, 'final_total']).mean():.4f}, E2 {np.abs(eo.loc[ev, 'points'] - eo.loc[ev, 'final_total']).mean():.4f}")
    # 4. current games
    cur, shifts = [], []
    for day in ("2026-11-01", "2026-11-02"):
        if os.path.exists(os.path.join(ROOT, "reports", f"features_{day}.csv")):
            t, s1, s2 = current(day)
            cur.append(t)
            shifts.append(f"{day}: opening-week shift v1 {s1:+.2f}, E2 {s2:+.2f}")
    cur = pd.concat(cur, ignore_index=True)
    cur.to_csv(os.path.join(OUT, "e2_current_games.csv"), index=False)
    L.append("4. Current cards (" + "; ".join(shifts) + ")")
    L.append(f"   v1 total reproduces the card's model_total: max diff {np.abs(cur['v1_total'] - cur['card_model_total']).max():.3f}; "
             f"v1 verdict reproduces the card: {int((cur['v1_verdict'] == cur['card_verdict']).sum())} of {int(cur['card_verdict'].notna().sum())}")
    L.append(f"   Change E2 - v1: neutral games mean {cur.loc[cur['neutral'] == 1, 'change'].mean():+.2f} (n {int((cur['neutral'] == 1).sum())}), "
             f"home/away mean {cur.loc[cur['neutral'] == 0, 'change'].mean():+.2f} (n {int((cur['neutral'] == 0).sum())}), "
             f"range {cur['change'].min():+.2f} to {cur['change'].max():+.2f}")
    priced = cur[cur["v1_pick"].notna()]
    flips = priced[(priced["v1_verdict"] != priced["e2_verdict"]) | (priced["v1_pick"] != priced["e2_pick"])]
    L.append(f"   Games with a priced total on the cards: {len(priced)}")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 50)
    cols = ["date", "game", "neutral", "v1_total", "e2_total", "change", "v1_pick", "v1_edge", "v1_verdict", "e2_pick",
            "e2_edge", "e2_verdict", "logged"]
    L.append(f"   Games whose total pick or verdict changes ({len(flips)}):\n" + (flips[cols].to_string(index=False) if len(flips) else "   none"))
    marquee = cur[cur["logged"].notna() | cur["v1_verdict"].isin(["BET", "WATCH"]) | cur["e2_verdict"].isin(["BET", "WATCH"])]
    L.append("   Every game with a logged total, a BET or a WATCH under either version:\n" + marquee[cols].to_string(index=False))
    txt = "\n".join(L) + "\n"
    open(os.path.join(OUT, "e2_review.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
