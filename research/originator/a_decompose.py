"""Part A: decompose the frozen model's (and the closing line's) misses into possessions, home and away offence
efficiency (with overtime points shown inside them) and personnel; then test each component's predictability and
whether the closing line already carries it. Specification in LOG.md (pre-registered).

    python -m research.originator.a_decompose
"""
from __future__ import annotations

import ast
import os

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(os.path.dirname(__file__), "out")
CACHE = os.path.join(ROOT, "cbb", "cache")
HIGH = {"ACC", "B10", "B12", "BE", "SEC", "P12"}
MID = {"A10", "MWC", "WCC", "Amer", "MVC"}
DEV, TEST = range(2014, 2020), range(2020, 2027)


# ------------------------------------------------------------------ inputs
def actual_poss(season: int) -> pd.DataFrame:
    t = pd.read_parquet(os.path.join(CACHE, f"team_box_{season}.parquet"))
    t = t.drop_duplicates(["game_id", "team_id"])
    t["poss"] = t["field_goals_attempted"] - t["offensive_rebounds"] + t["total_turnovers"] + 0.475 * t["free_throws_attempted"]
    return t.groupby("game_id")["poss"].mean().rename("P").reset_index()


def ot_points(season: int) -> pd.DataFrame:
    s = pd.read_parquet(os.path.join(CACHE, f"mbb_schedule_{season}.parquet")).drop_duplicates("game_id")

    def extra(x):
        try:
            v = [float(d["value"]) for d in ast.literal_eval(str(x).replace("} {", "}, {"))]
            return sum(v[2:]) if len(v) > 2 else 0.0
        except Exception:
            return np.nan
    if "home_linescores" not in s:   # older schedule files carry no period scores: overtime points unknown
        s = s.assign(home_linescores=None, away_linescores=None)
    return pd.DataFrame({"game_id": s["game_id"].astype(int), "home_ot": s["home_linescores"].map(extra),
                         "away_ot": s["away_linescores"].map(extra),
                         "ot": pd.to_numeric(s["status_period"], errors="coerce") > 2})


def personnel(season: int) -> pd.DataFrame:
    """Per team-game: share of usual minutes missing (absent) and share of tonight's minutes from newly present
    players, against each player's average over the team's previous 3 games."""
    p = pd.read_parquet(os.path.join(CACHE, f"player_box_{season}.parquet"),
                        columns=["game_id", "game_date", "team_id", "athlete_id", "minutes"])
    p["minutes"] = pd.to_numeric(p["minutes"], errors="coerce").fillna(0.0)
    p = p.groupby(["team_id", "game_id", "game_date", "athlete_id"], as_index=False)["minutes"].sum()
    out = []
    for tid, g in p.groupby("team_id"):
        m = g.pivot_table(index=["game_date", "game_id"], columns="athlete_id", values="minutes", aggfunc="sum").fillna(0.0)
        m = m.sort_index()
        usual = m.shift(1).rolling(3, min_periods=3).mean()
        for (gd, gid), tonight in m.iterrows():
            u = usual.loc[(gd, gid)]
            if u.isna().all():
                continue
            u = u.fillna(0.0)
            tot_u, tot_t = u.sum(), tonight.sum()
            absent = u[(u >= 10) & (tonight < 0.5 * u)].sum() / tot_u if tot_u > 0 else np.nan
            new = tonight[(tonight > 0) & (u < 0.5 * tonight)].sum() / tot_t if tot_t > 0 else np.nan
            out.append({"game_id": int(gid), "team_id": int(tid), "absent": absent, "new": new})
    return pd.DataFrame(out)


def frame() -> pd.DataFrame:
    w = pd.read_pickle(os.path.join(ROOT, "audit", "out", "wf_live_approx.pkl"))
    w = w[w["season"].between(2014, 2026)].dropna(subset=["final_margin", "final_total", "pred_poss"])
    parts, pers = [], []
    for s in range(2014, 2027):
        parts.append(actual_poss(s).merge(ot_points(s), on="game_id", how="left"))
        pers.append(personnel(s))
        print("inputs", s, flush=True)
    w = w.merge(pd.concat(parts), on="game_id", how="left")
    pe = pd.concat(pers)
    w = w.merge(pe.rename(columns={"team_id": "home_id", "absent": "h_absent", "new": "h_new"}), on=["game_id", "home_id"], how="left")
    w = w.merge(pe.rename(columns={"team_id": "away_id", "absent": "a_absent", "new": "a_new"}), on=["game_id", "away_id"], how="left")
    t = pd.read_csv(os.path.join(ROOT, "data", "teams.csv")).drop_duplicates("espn_id").set_index("espn_id")["kenpom_conf"]
    tier = lambda c: c.map(lambda x: 2 if x in HIGH else (1 if x in MID else 0))
    th, ta = tier(w["home_id"].map(t)), tier(w["away_id"].map(t))
    w["tier"] = np.select([(th == 2) & (ta == 2), np.minimum(th, ta) == 0], ["high", "low"], "mid/mixed")
    w["month"] = pd.to_datetime(w["date"]).dt.month.map({11: "Nov", 12: "Dec", 1: "Jan", 2: "Feb"}).fillna("Mar+")
    return w.dropna(subset=["P"])


# ------------------------------------------------------------------ decomposition
def decompose(w: pd.DataFrame, T_hat: pd.Series, M_hat: pd.Series, tag: str) -> pd.DataFrame:
    P_hat = w["pred_poss"]
    eh, ea = (T_hat + M_hat) / 2 / P_hat, (T_hat - M_hat) / 2 / P_hat
    P = w["P"]
    ah, aa = w["home_pts"] / P, w["away_pts"] / P
    d = pd.DataFrame(index=w.index)
    d[f"{tag}_poss_T"] = (P - P_hat) * (eh + ea)
    d[f"{tag}_hoff"] = P * (ah - eh)
    d[f"{tag}_aoff"] = P * (aa - ea)
    d[f"{tag}_poss_M"] = (P - P_hat) * (eh - ea)
    d[f"{tag}_miss_T"] = (w["home_pts"] + w["away_pts"]) - T_hat
    d[f"{tag}_miss_M"] = (w["home_pts"] - w["away_pts"]) - M_hat
    return d


def shares(d: pd.DataFrame, w: pd.DataFrame, tag: str) -> list[dict]:
    rows = []
    groups = [("all", slice(None))] + [(f"month {m}", w["month"] == m) for m in ["Nov", "Dec", "Jan", "Feb", "Mar+"]] + \
             [(f"tier {t}", w["tier"] == t) for t in ["high", "mid/mixed", "low"]]
    for name, idx in groups:
        x, ww = d.loc[idx], w.loc[idx]
        for mk, parts in (("total", [("possessions", f"{tag}_poss_T"), ("home offence", f"{tag}_hoff"), ("away offence", f"{tag}_aoff")]),
                          ("margin", [("possessions", f"{tag}_poss_M"), ("home offence", f"{tag}_hoff"), ("away offence (negative)", f"{tag}_aoff")])):
            miss = x[f"{tag}_miss_{mk[0].upper()}"]
            v = miss.var()
            r = {"forecaster": tag, "group": name, "market": mk, "games": len(x), "MAE": miss.abs().mean(), "miss SD": np.sqrt(v)}
            for lab, col in parts:
                c = x[col] if "negative" not in lab else -x[col]
                r[lab] = np.cov(c, miss)[0, 1] / v
            known = ww["home_ot"].notna() & ww["away_ot"].notna()
            ot = (ww["home_ot"] + ww["away_ot"]) if mk == "total" else (ww["home_ot"] - ww["away_ot"])
            r["of which overtime points (seasons with period scores)"] = (np.cov(ot[known], miss[known])[0, 1] / miss[known].var()) if known.sum() > 100 else np.nan
            ok = ww[["h_absent", "h_new", "a_absent", "a_new"]].notna().all(axis=1)
            X = np.column_stack([np.ones(ok.sum()), ww.loc[ok, ["h_absent", "h_new", "a_absent", "a_new"]].to_numpy(float)])
            y = miss[ok].to_numpy(float)
            b, *_ = np.linalg.lstsq(X, y, rcond=None)
            r["personnel (R2, overlaps)"] = 1 - ((y - X @ b) ** 2).sum() / ((y - y.mean()) ** 2).sum()
            rows.append(r)
    return rows


# ------------------------------------------------------------------ predictability
def cluster_ols(X: np.ndarray, y: np.ndarray, groups: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    X = np.column_stack([np.ones(len(X)), X])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    bread = np.linalg.inv(X.T @ X)
    s = pd.DataFrame(X * e[:, None]).groupby(groups).sum().to_numpy()
    se = np.sqrt(np.diag(bread @ (s.T @ s) @ bread))
    return b, se


def team_rows(w: pd.DataFrame, d: pd.DataFrame) -> pd.DataFrame:
    """One row per team-game: its offence residual (model), the possessions residual, personnel, the line's
    disagreement with the model in that team's points, and the line's own residual."""
    rows = []
    T_L, M_L = w["total"], -w["home_spread"]
    for side, opp, sign in (("home", "away", 1), ("away", "home", -1)):
        pts_model = (w["final_total"] + sign * w["final_margin"]) / 2
        pts_line = (T_L + sign * M_L) / 2
        rows.append(pd.DataFrame({
            "game_id": w["game_id"], "season": w["season"], "date": w["date"], "team": w[f"{side}_id"], "opp": w[f"{opp}_id"],
            "off_res": d["model_hoff"] if side == "home" else d["model_aoff"],
            "poss_res": w["P"] - w["pred_poss"],
            "absent": w[f"{side[0]}_absent"], "new": w[f"{side[0]}_new"],
            "line_minus_model": pts_line - pts_model,
            "line_res": w[f"{side}_pts"] - pts_line}))
    t = pd.concat(rows, ignore_index=True).sort_values(["team", "date", "game_id"])
    g = t.groupby(["team", "season"])
    for c in ("off_res", "poss_res", "absent", "new"):
        t[f"{c}_mean"] = g[c].transform(lambda s: s.shift(1).expanding().mean())
        t[f"{c}_last"] = g[c].shift(1)
    # the opponent's offence residual ALLOWED so far (its defence), season to date
    allowed = t[["game_id", "opp", "season", "date", "off_res"]].rename(columns={"opp": "team", "off_res": "allowed"})
    allowed = allowed.sort_values(["team", "date", "game_id"])
    allowed["allowed_mean"] = allowed.groupby(["team", "season"])["allowed"].transform(lambda s: s.shift(1).expanding().mean())
    t = t.merge(allowed[["game_id", "team", "allowed_mean"]].rename(columns={"team": "opp", "allowed_mean": "opp_def_mean"}),
                on=["game_id", "opp"], how="left")
    return t


def predictability(t: pd.DataFrame) -> pd.DataFrame:
    specs = {"possessions residual": ("poss_res", ["poss_res_mean", "poss_res_last"]),
             "offence efficiency residual (points)": ("off_res", ["off_res_mean", "off_res_last", "opp_def_mean"]),
             "personnel: absent share": ("absent", ["absent_mean", "absent_last"]),
             "personnel: newly present share": ("new", ["new_mean", "new_last"])}
    rows = []
    for name, (y, xs) in specs.items():
        d = t.dropna(subset=[y] + xs + ["line_minus_model", "line_res"])
        tr, te = d[d["season"].isin(DEV)], d[d["season"].isin(TEST)]
        X = lambda f: np.column_stack([np.ones(len(f)), f[xs].to_numpy(float)])
        b, *_ = np.linalg.lstsq(X(tr), tr[y].to_numpy(float), rcond=None)
        pred = X(te) @ b
        r2 = 1 - ((te[y] - pred) ** 2).sum() / ((te[y] - te[y].mean()) ** 2).sum()
        r = {"component": name, "test rows": len(te), "out-of-sample R2 (2020-26)": r2}
        if y in ("poss_res", "off_res"):
            te = te.assign(pred=pred)
            b1, s1 = cluster_ols(te[["pred"]].to_numpy(float), te[y].to_numpy(float), te["date"].to_numpy())
            b2, s2 = cluster_ols(te[["pred", "line_minus_model"]].to_numpy(float), te[y].to_numpy(float), te["date"].to_numpy())
            # betting information: does the prediction explain the LINE's residual in that team's points?
            b3, s3 = cluster_ols(te[["pred", "line_minus_model"]].to_numpy(float), te["line_res"].to_numpy(float), te["date"].to_numpy())
            r.update({"coef on predictor": f"{b1[1]:.3f} ({s1[1]:.3f})",
                      "coef with line term": f"{b2[1]:.3f} ({s2[1]:.3f})",
                      "line term coef": f"{b2[2]:.3f} ({s2[2]:.3f})",
                      "predictor vs LINE residual": f"{b3[1]:.3f} ({s3[1]:.3f})"})
        rows.append(r)
    return pd.DataFrame(rows)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    w = frame()
    w = w.dropna(subset=["home_spread", "total"]).reset_index(drop=True)
    d = pd.concat([decompose(w, w["final_total"], w["final_margin"], "model"),
                   decompose(w, w["total"], -w["home_spread"], "line")], axis=1)
    sh = pd.DataFrame(shares(d, w, "model") + shares(d, w, "line"))
    t = team_rows(w, d)
    pr = predictability(t)
    sh.to_csv(os.path.join(OUT, "a_shares.csv"), index=False)
    pr.to_csv(os.path.join(OUT, "a_predictability.csv"), index=False)
    w[["game_id", "season", "date", "tier", "month", "P", "pred_poss", "ot", "h_absent", "h_new", "a_absent", "a_new"]].to_csv(
        os.path.join(OUT, "a_games.csv.gz"), index=False, compression={"method": "gzip", "mtime": 0})
    pd.set_option("display.width", 250)
    print(sh[sh["group"] == "all"].round(3).to_string(index=False))
    print(sh[sh["group"] != "all"].round(3).to_string(index=False))
    print(pr.round(4).to_string(index=False))
    print("games:", len(w), "overtime games:", int(w["ot"].sum()),
          "| late-game fouling and garbage time: not decomposable (no play-by-play stored)")


if __name__ == "__main__":
    main()
