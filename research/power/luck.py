"""Luck-adjusted outcomes (research/power/LUCK_PLAN.md): expected points from shot attempts and pre-game make
rates, then the plan's Q1 (noise) and Q2 (validity) and the Q3 adoption rule.

    python -m research.power.luck build      # -> research/power/out/expected_points.parquet (per team-game)
    python -m research.power.luck evaluate   # -> research/power/out/luck.txt
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(os.path.dirname(__file__), "out")
PBP = os.path.join(ROOT, "cbb", "cache", "pbp")
GS = os.path.join(ROOT, "research", "game_state", "out")
SEASONS = list(range(2014, 2027))
CLASSES = {"rim": 2, "j2": 2, "three": 3, "ft": 1}
K = {"rim": 300.0, "j2": 300.0, "three": 300.0, "ft": 150.0}
COLS = ["game_id", "game_play_number", "type_text", "text", "team_id", "home_team_id", "away_team_id", "scoring_play",
        "shooting_play", "game_date"]
L: list[str] = []


def say(s=""):
    L.append(s)
    print(s, flush=True)


def team_games(season: int) -> pd.DataFrame:
    """Attempts and makes per class for each team-game (valid games only)."""
    p = pd.read_parquet(os.path.join(PBP, f"play_by_play_{season}.parquet"), columns=COLS)
    G = pd.read_parquet(os.path.join(GS, f"games_{season}.parquet"))
    p = p[p["game_id"].isin(G.loc[G["valid"], "game_id"])]
    tt, tx = p["type_text"].astype(str), p["text"].astype(str)
    ft = tt.eq("MadeFreeThrow") | tx.str.contains("Free Throw", regex=False)
    fga = p["shooting_play"].fillna(False).astype(bool) & ~ft
    three = tt.str.contains("Three") | tx.str.contains("Three Point", regex=False)
    rim = tt.isin(["LayUpShot", "DunkShot", "TipShot"])
    cls = np.select([ft, fga & three, fga & rim, fga], ["ft", "three", "rim", "j2"], "")
    s = p[cls != ""].assign(cls=cls[cls != ""], made=p["scoring_play"].fillna(False).astype(bool))
    s = s[s["team_id"].notna()]
    s["team_id"] = s["team_id"].astype(int)
    agg = s.groupby(["game_id", "team_id", "cls"])["made"].agg(["size", "sum"]).unstack("cls", fill_value=0)
    agg.columns = [f"{'att' if a == 'size' else 'mk'}_{c}" for a, c in agg.columns]
    agg = agg.reset_index()
    for c in CLASSES:
        for a in ("att", "mk"):
            if f"{a}_{c}" not in agg:
                agg[f"{a}_{c}"] = 0
    ha = p.drop_duplicates("game_id").set_index("game_id")[["home_team_id", "away_team_id", "game_date"]]
    agg = agg.join(ha, on="game_id")
    agg = agg[(agg["team_id"] == agg["home_team_id"]) | (agg["team_id"] == agg["away_team_id"])]
    agg["opp_id"] = np.where(agg["team_id"] == agg["home_team_id"], agg["away_team_id"], agg["home_team_id"]).astype(int)
    agg["home"] = agg["team_id"] == agg["home_team_id"]
    agg["date"] = pd.to_datetime(agg["game_date"])
    agg["season"] = season
    return agg.drop(columns=["home_team_id", "away_team_id", "game_date"])


def prior_rates(t: pd.DataFrame, key: str, prefix: str) -> pd.DataFrame:
    """Season-to-date attempts and makes per class for `key` (team for offense, opp for defense), from games on
    earlier dates only."""
    out = pd.DataFrame(index=t.index)
    daily = t.groupby([key, "date"])[[f"{a}_{c}" for c in CLASSES for a in ("att", "mk")]].sum().sort_index()
    cum = daily.groupby(level=0).cumsum() - daily            # through the previous date
    m = t[[key, "date"]].merge(cum, left_on=[key, "date"], right_index=True, how="left")
    for c in CLASSES:
        out[f"{prefix}att_{c}"] = m[f"att_{c}"].fillna(0).to_numpy()
        out[f"{prefix}mk_{c}"] = m[f"mk_{c}"].fillna(0).to_numpy()
    return out


def build() -> None:
    os.makedirs(OUT, exist_ok=True)
    parts, prev = [], None
    for s in SEASONS:
        t = team_games(s).reset_index(drop=True)
        o = prior_rates(t, "team_id", "o_")
        d = prior_rates(t, "opp_id", "d_")                     # what this team's opponent has allowed before
        # league rate from earlier dates; before any games, last season's rate (2013-14 uses its own first week)
        day = t.groupby("date")[[f"{a}_{c}" for c in CLASSES for a in ("att", "mk")]].sum().sort_index()
        cum = day.cumsum() - day
        lg = t[["date"]].merge(cum, left_on="date", right_index=True, how="left")
        E = np.zeros(len(t))
        for c, v in CLASSES.items():
            base = prev[c] if prev is not None else float(t[f"mk_{c}"].sum() / max(t[f"att_{c}"].sum(), 1))
            la, lm = lg[f"att_{c}"].to_numpy(float), lg[f"mk_{c}"].to_numpy(float)
            L_ = np.where(la >= 500, lm / np.maximum(la, 1), base)
            oa, om = o[f"o_att_{c}"].to_numpy(float), o[f"o_mk_{c}"].to_numpy(float)
            da, dm = d[f"d_att_{c}"].to_numpy(float), d[f"d_mk_{c}"].to_numpy(float)
            ro = np.where(oa > 0, om / np.maximum(oa, 1), L_)
            rd = np.where(da > 0, dm / np.maximum(da, 1), L_)
            p = L_ + oa / (oa + K[c]) * (ro - L_)
            if c != "ft":
                p = p + da / (da + K[c]) * (rd - L_)
            p = np.clip(p, 0.01, 0.99)
            t[f"p_{c}"] = p
            E += t[f"att_{c}"].to_numpy(float) * p * v
        t["exp_pts"] = E
        t["act_pts"] = sum(t[f"mk_{c}"] * v for c, v in CLASSES.items())
        prev = {c: float(t[f"mk_{c}"].sum() / max(t[f"att_{c}"].sum(), 1)) for c in CLASSES}
        parts.append(t)
        print(s, len(t), round(float((t["exp_pts"] - t["act_pts"]).mean()), 3), flush=True)
    pd.concat(parts, ignore_index=True).to_parquet(os.path.join(OUT, "expected_points.parquet"), index=False)


def evaluate() -> None:
    from research.persistent_disagreement.common import baseline
    from research.persistent_disagreement.score import e2_totals, v2_margin
    from research.power.scorecard import clustered_ols
    ep = pd.read_parquet(os.path.join(OUT, "expected_points.parquet"))
    h = ep[ep["home"]].set_index("game_id")
    a = ep[~ep["home"]].set_index("game_id")
    w = baseline()
    w = w[~w["swapped"]].set_index("game_id")
    gid = w.index.intersection(h.index).intersection(a.index)
    w = w.loc[gid].copy()
    # pbp home must be the frame's home: check by actual points (play-by-play final = official final in valid games)
    same = (h.loc[gid, "act_pts"] == w["home_pts"]) & (a.loc[gid, "act_pts"] == w["away_pts"])
    say(f"games with valid play-by-play and a baseline row: {len(gid)}; pbp home = frame home and points match: {int(same.sum())}")
    w = w[same.to_numpy()]
    gid = w.index
    w["la_margin"] = h.loc[gid, "exp_pts"].to_numpy() - a.loc[gid, "exp_pts"].to_numpy()
    w["la_points"] = h.loc[gid, "exp_pts"].to_numpy() + a.loc[gid, "exp_pts"].to_numpy()
    w["v2"] = v2_margin()["v2_margin"].reindex(gid)
    w["E2"] = e2_totals().reindex(gid)
    w["C2"] = w["final_total"] - 0.61
    eras = {"2014-15..2018-19": range(2015, 2020), "2019-20..2022-23": range(2020, 2024), "2023-24..2025-26": range(2024, 2027)}
    say("\nQ1 noise: SD of (result - closing line)")
    q1 = []
    for era, ss in eras.items():
        x = w[w["season"].isin(list(ss))]
        sp = x.dropna(subset=["home_spread"])
        tt = x.dropna(subset=["total"])
        q1.append({"era": era, "games (spread)": len(sp),
                   "spread actual": float((sp["margin"] + sp["home_spread"]).std()), "spread luck-adj": float((sp["la_margin"] + sp["home_spread"]).std()),
                   "games (total)": len(tt),
                   "total actual": float((tt["points"] - tt["total"]).std()), "total luck-adj": float((tt["la_points"] - tt["total"]).std()),
                   "mean(la - actual) margin": float((x["la_margin"] - x["margin"]).mean()),
                   "mean(la - actual) total": float((x["la_points"] - x["points"]).mean())})
    say(pd.DataFrame(q1).round(3).to_string(index=False))
    say("\nQ2 validity: beyond-close slopes with actual vs luck-adjusted outcomes (date-clustered SEs), all eras pooled 2014-15..2025-26")
    rows, se_ratio, agree = [], {}, True
    for market, line, act, la, items in (("spread", "home_spread", "margin", "la_margin", [("v1", "final_margin", None), ("v2 incremental", "v2", "final_margin")]),
                                         ("total", "total", "points", "la_points", [("v1", "final_total", None), ("E2 incremental", "E2", "final_total"), ("C2 incremental", "C2", "final_total")])):
        x = w.dropna(subset=[line]).copy()
        for lab, col, base in items:
            x2 = x.dropna(subset=[col])
            sgn = 1.0 if market == "spread" else -1.0
            e_base = x2[base if base else col] + (x2[line] if market == "spread" else -x2[line])
            res = {}
            for outname, oc in (("actual", act), ("luck-adj", la)):
                y = x2[oc] + x2[line] if market == "spread" else x2[oc] - x2[line]
                if base is None:
                    b, se = clustered_ols(y, e_base, x2["date"].astype(str).to_numpy())
                    res[outname] = (b[1], se[1])
                else:
                    b, se = clustered_ols(y, np.column_stack([e_base, x2[col] - x2[base]]), x2["date"].astype(str).to_numpy())
                    res[outname] = (b[2], se[2])
            (ba, sa), (bl, sl) = res["actual"], res["luck-adj"]
            ok = abs(ba - bl) <= 2 * np.sqrt(sa ** 2 + sl ** 2)
            agree &= ok
            if base is None:
                se_ratio[market] = sl / sa
            rows.append({"market": market, "slope": lab, "games": len(x2), "actual": ba, "SE actual": sa, "luck-adj": bl,
                         "SE luck-adj": sl, "SE ratio": sl / sa, "agree within 2 SE": ok})
    say(pd.DataFrame(rows).round(3).to_string(index=False))
    adopt = all(r <= 0.8 for r in se_ratio.values()) and agree
    say(f"\nQ3 adoption rule: SE of v1's slope falls >= 20% in both markets ({', '.join(f'{k} ratio {v:.3f}' for k, v in se_ratio.items())}) "
        f"and every pair agrees ({agree})  =>  {'ADOPT as the secondary result scoreboard' if adopt else 'NOT ADOPTED'}")
    open(os.path.join(OUT, "luck.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    {"build": build, "evaluate": evaluate}[sys.argv[1]]()
