"""Part 3 (PLAN.md): round 2 totals candidates (e) drift correction, (f) recent form, (g) market anchor by month,
(h) blowout term, against the frozen model. Same scoring and kill rule as Part 2.

    python -m research.totals_late.round2
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import projection
from research.originator.d_common import frames, oriented_openers, walk_forward
from research.totals_late.candidates import ERAS, score
from research.totals_late.diag import OUT, plays


def with_totals(base: pd.DataFrame, new_total: pd.Series) -> pd.DataFrame:
    return base.assign(final_total=new_total.to_numpy(float))


def drift(w: pd.DataFrame, k: float) -> pd.DataFrame:
    """(e) model total + k x mean(actual - model) over the same season's games in the previous 14 days (>= 100)."""
    d = w[["season", "date", "home_pts", "away_pts", "final_total"]].copy()
    d["date"] = pd.to_datetime(d["date"])
    d["res"] = d["home_pts"] + d["away_pts"] - d["final_total"]
    b = pd.Series(0.0, index=d.index)
    for s, g in d.groupby("season"):
        day = g.groupby("date")["res"].agg(["sum", "count"]).asfreq("D", fill_value=0)
        roll = day.rolling(14, min_periods=1).sum().shift(1).fillna(0)       # previous 14 days, not today
        mean = np.where(roll["count"] >= 100, roll["sum"] / roll["count"].where(roll["count"] > 0), 0.0)
        b.loc[g.index] = pd.Series(mean, index=roll.index).reindex(g["date"]).to_numpy()
    return with_totals(w, w["final_total"] + k * b)


def add_form(df: pd.DataFrame) -> pd.DataFrame:
    """(f) per team: mean of (actual total - stage-1 predicted total) over its last 10 games this season, before
    the game; 0 under 3 games. form_sum = home + away."""
    res = df["home_pts"] + df["away_pts"] - df["pred_total"]
    long = pd.concat([pd.DataFrame({"game_id": df["game_id"], "season": df["season"], "date": pd.to_datetime(df["date"]),
                                    "team": df[c], "res": res, "slot": c}) for c in ("home_id", "away_id")])
    long = long.sort_values(["date", "game_id"])
    g = long.groupby(["season", "team"])["res"]
    long["form"] = g.transform(lambda x: x.shift(1).rolling(10, min_periods=3).mean()).fillna(0.0)
    f = long.pivot_table(index="game_id", columns="slot", values="form", aggfunc="first")
    out = df.copy()
    out["form_sum"] = out["game_id"].map(f["home_id"]).fillna(0) + out["game_id"].map(f["away_id"]).fillna(0)
    return out


def refit(train: pd.DataFrame, pred: pd.DataFrame, extra: str) -> pd.DataFrame:
    tf = projection.TOTAL_FEATURES
    try:
        projection.TOTAL_FEATURES = tf + [extra]
        return walk_forward(train, pred)
    finally:
        projection.TOTAL_FEATURES = tf


def anchored_plays(w: pd.DataFrame) -> pd.DataFrame:
    """(g) January-April totals edges scaled by k_month / k_NovDec (capped at 1), k from earlier seasons' closes."""
    d = w.dropna(subset=["total"]).copy()
    d["x"] = d["final_total"] - d["total"]
    d["y"] = d["home_pts"] + d["away_pts"] - d["total"]
    m = pd.to_datetime(d["date"]).dt.month
    d["grp"] = np.where(m.isin([11, 12]), "early", np.where(m == 1, "jan", np.where(m == 2, "feb", "mar")))
    p = plays(w)
    pm = pd.to_datetime(p["date"]).dt.month
    p["grp"] = np.where(pm.isin([11, 12]), "early", np.where(pm == 1, "jan", np.where(pm == 2, "feb", "mar")))
    ratio = pd.Series(1.0, index=p.index)
    rows = []
    for s in sorted(p["season"].unique()):
        prior = d[d["season"] < s]
        if not len(prior):
            continue
        k = prior.groupby("grp").apply(lambda g: (g["x"] * g["y"]).sum() / (g["x"] ** 2).sum())
        for grp in ("jan", "feb", "mar"):
            r = min(1.0, k.get(grp, np.nan) / k.get("early", np.nan)) if "early" in k else 1.0
            r = 1.0 if not np.isfinite(r) else max(r, 0.0)
            ratio[(p["season"] == s) & (p["grp"] == grp)] = r
            rows.append({"season": s, "month": grp, "k": k.get(grp), "k_early": k.get("early"), "ratio": r})
    p = p[(p["edge"].abs() * ratio) >= 3]
    return p, pd.DataFrame(rows)


def main() -> None:
    train, pred = frames()
    base = pd.read_pickle(os.path.join(OUT, "frozen_wf.pkl"))
    variants = {"frozen": plays(base)}
    for k in (0.5, 1.0):
        variants[f"(e) drift k={k}"] = plays(drift(base, k))
    tf, pf = add_form(train), add_form(pred)
    form = oriented_openers(refit(tf, pf, "form_sum"))
    variants["(f) recent form"] = plays(base.drop(columns=["final_total"]).merge(form[["game_id", "final_total"]], on="game_id"))
    gp, ks = anchored_plays(base)
    variants["(g) market anchor by month"] = gp
    tb, pb = (x.assign(abs_margin=x["pred_margin"].abs()) for x in (train, pred))
    blow = oriented_openers(refit(tb, pb, "abs_margin"))
    variants["(h) blowout term"] = plays(base.drop(columns=["final_total"]).merge(blow[["game_id", "final_total"]], on="game_id"))

    rows = []
    for name, p in variants.items():
        for era, ss in ERAS.items():
            q = p[p["season"].isin(ss)]
            dec = q["res_open"][q["res_open"] != 0]
            rows.append({"variant": name, "era": era, **score(q), "season plays": len(q),
                         "season win%": 100 * (dec > 0).mean(), "season CLV": q["clv"].mean()})
    t = pd.DataFrame(rows)
    f = t[t["variant"] == "frozen"].set_index("era")
    for c in ("Jan-Mar win%", "Jan-Mar CLV", "Nov-Dec win%", "Nov-Dec CLV", "season win%"):
        t[f"d {c}"] = t.apply(lambda r: r[c] - f.loc[r["era"], c], axis=1)
    t["late plays kept"] = t.apply(lambda r: r["Jan-Mar plays"] / f.loc[r["era"], "Jan-Mar plays"], axis=1)

    def verdict(v: str) -> str:
        x = t[t["variant"] == v].set_index("era")
        ok = all((x.loc[e, "d Jan-Mar win%"] >= 1.0) and (x.loc[e, "d Jan-Mar CLV"] > -0.1)
                 and (x.loc[e, "d Nov-Dec CLV"] > -0.1) and (x.loc[e, "d Nov-Dec win%"] > -1.0) for e in ERAS)
        return "SURVIVES" if ok else "KILL"
    # (e): k chosen on dev January-April win %, then only the chosen k is judged
    e = t[t["variant"].str.startswith("(e)") & (t["era"] == "dev")].sort_values("Jan-Mar win%", ascending=False)
    chosen_e = e["variant"].iloc[0]
    judged = [chosen_e, "(f) recent form", "(g) market anchor by month", "(h) blowout term"]
    verdicts = {v: verdict(v) for v in judged}
    pd.set_option("display.width", 260)
    cols = ["variant", "era", "Jan-Mar plays", "Jan-Mar win%", "Jan-Mar ROI%", "Jan-Mar CLV", "Nov-Dec plays",
            "Nov-Dec win%", "Nov-Dec CLV", "season win%", "d Jan-Mar win%", "d Jan-Mar CLV", "d Nov-Dec win%",
            "d Nov-Dec CLV", "d season win%", "late plays kept"]
    txt = (t[cols].round(3).to_string(index=False) + f"\n\n(e) k chosen on dev: {chosen_e}\nVerdicts: "
           + "; ".join(f"{k}: {v}" for k, v in verdicts.items())
           + "\n\n(g) month ratios k_month / k_NovDec by season:\n" + ks.round(3).to_string(index=False))
    open(os.path.join(OUT, "round2.txt"), "w").write(txt)
    t.to_csv(os.path.join(OUT, "round2.csv"), index=False)
    print(txt)


if __name__ == "__main__":
    main()
