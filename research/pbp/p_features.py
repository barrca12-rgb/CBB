"""Play-by-play challengers P1 (shot-quality luck) and P2 (garbage time), pre-registered in LOG.md.

    python -m research.pbp.p_features
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import projection
from research.originator.d_common import clv, frames, info_beyond_close, mae, oriented_openers, walk_forward

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
PBP = os.path.join(HERE, "..", "..", "cbb", "cache", "pbp")
COLS = ["game_id", "type_text", "text", "scoring_play", "score_value", "team_id", "home_team_id", "away_team_id",
        "home_score", "away_score", "period_number", "clock_display_value", "shooting_play"]
PRIOR = 5.0
P1 = ["luck_margin", "luck_total"]
P2 = ["garbage_margin", "garbage_total"]


def team_games(season: int) -> pd.DataFrame:
    """Per game and team: fg_pts, exp_pts (shot-quality expected FG points), garbage_for, garbage_against."""
    path = os.path.join(OUT, f"tg_{season}.pkl")
    if os.path.exists(path):
        return pd.read_pickle(path)
    p = pd.read_parquet(os.path.join(PBP, f"play_by_play_{season}.parquet"), columns=COLS)
    p = p.reset_index(drop=True)
    # garbage time: margin before the play above 20, second half or overtime, 10 minutes or less left
    prev_m = (p["home_score"] - p["away_score"]).groupby(p["game_id"]).shift(1).fillna(0)
    # time left from the period clock: end_game_seconds_remaining is wrong in the files before 2023
    clk = p["clock_display_value"].astype(str).str.split(":", expand=True)
    secs = pd.to_numeric(clk[0], errors="coerce") * 60 + pd.to_numeric(clk[1], errors="coerce")
    garb = (prev_m.abs() > 20) & (p["period_number"] >= 2) & (secs <= 600)
    sc = p[p["scoring_play"] & garb & p["team_id"].notna()]
    g = sc.assign(home=sc["team_id"] == sc["home_team_id"]).groupby(["game_id", "home"])["score_value"].sum().unstack(fill_value=0)
    g = g.reindex(columns=[True, False], fill_value=0)
    # field-goal attempts by class
    tt, tx = p["type_text"].astype(str), p["text"].astype(str)
    fga = p["shooting_play"] & ~tt.str.contains("FreeThrow|Free Throw") & ~tx.str.contains("Free Throw") & p["team_id"].notna()
    s = p[fga].copy()
    three = tt[fga].str.contains("Three") | tx[fga].str.contains("Three Point")
    rim = tt[fga].isin(["LayUpShot", "DunkShot", "TipShot"])
    s["cls"] = np.where(three, "three", np.where(rim, "rim", "jumper2"))
    s["pts"] = np.where(s["cls"] == "three", 3, 2)
    s["made"] = s["scoring_play"].astype(bool)
    rate = s.groupby("cls")["made"].mean()
    s["fg_pts"] = s["made"] * s["pts"]
    s["exp_pts"] = s["cls"].map(rate) * s["pts"]
    s["team_id"] = s["team_id"].astype(int)
    out = s.groupby(["game_id", "team_id"])[["fg_pts", "exp_pts"]].sum().reset_index()
    ha = p.drop_duplicates("game_id").set_index("game_id")[["home_team_id", "away_team_id"]]
    out = out.join(ha, on="game_id")
    out["home"] = out["team_id"] == out["home_team_id"]
    out = out[out["home"] | (out["team_id"] == out["away_team_id"])]
    gf = np.where(out["home"], out["game_id"].map(g[True]), out["game_id"].map(g[False]))
    ga = np.where(out["home"], out["game_id"].map(g[False]), out["game_id"].map(g[True]))
    out["garbage_for"], out["garbage_against"] = np.nan_to_num(gf), np.nan_to_num(ga)
    opp = out[["game_id", "home", "fg_pts", "exp_pts"]].assign(home=~out["home"]).rename(columns={"fg_pts": "opp_fg", "exp_pts": "opp_exp"})
    out = out.merge(opp, on=["game_id", "home"])
    out["luck_off"] = out["fg_pts"] - out["exp_pts"]
    out["luck_def"] = out["opp_fg"] - out["opp_exp"]
    out = out[["game_id", "team_id", "luck_off", "luck_def", "garbage_for", "garbage_against"]]
    out.to_pickle(path)
    return out


def season_to_date(tg: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    """Before each game: per-game sums of earlier games shrunk toward 0 with PRIOR games."""
    tg = tg.assign(date=tg["game_id"].map(dates)).dropna(subset=["date"]).sort_values(["team_id", "date", "game_id"])
    cols = ["luck_off", "luck_def", "garbage_for", "garbage_against"]
    grp = tg.groupby("team_id")
    n = grp.cumcount().to_numpy(float)
    res = tg[["game_id", "team_id"]].copy()
    for c in cols:
        res[c] = (grp[c].cumsum() - tg[c]).to_numpy() / (n + PRIOR)
    return res


def add(frame: pd.DataFrame, feats: pd.DataFrame) -> pd.DataFrame:
    h = feats.rename(columns={c: f"h_{c}" for c in feats if c not in ("game_id",)}).rename(columns={"h_team_id": "home_id"})
    a = feats.rename(columns={c: f"a_{c}" for c in feats if c not in ("game_id",)}).rename(columns={"a_team_id": "away_id"})
    b = frame.merge(h, on=["game_id", "home_id"], how="left").merge(a, on=["game_id", "away_id"], how="left")
    f = lambda c: b[c].fillna(0.0)
    b["luck_margin"] = (f("h_luck_off") - f("h_luck_def")) - (f("a_luck_off") - f("a_luck_def"))
    b["luck_total"] = f("h_luck_off") + f("h_luck_def") + f("a_luck_off") + f("a_luck_def")
    b["garbage_margin"] = (f("h_garbage_for") - f("h_garbage_against")) - (f("a_garbage_for") - f("a_garbage_against"))
    b["garbage_total"] = f("h_garbage_for") + f("h_garbage_against") + f("a_garbage_for") + f("a_garbage_against")
    b["pbp_ok"] = b["h_luck_off"].notna() & b["a_luck_off"].notna()
    return b


def fit(train, pred, extra_m, extra_t):
    mf, tf = projection.MARGIN_FEATURES, projection.TOTAL_FEATURES
    try:
        projection.MARGIN_FEATURES, projection.TOTAL_FEATURES = mf + extra_m, tf + extra_t
        return walk_forward(train, pred)
    finally:
        projection.MARGIN_FEATURES, projection.TOTAL_FEATURES = mf, tf


def win_pct(w: pd.DataFrame, seasons) -> dict:
    from cbb import evaluate
    d = w[w["season"].isin(list(seasons))]
    d = d[~evaluate.swapped(d.assign(pred_margin=d["final_margin"]))]
    sp = d.dropna(subset=["open_home_spread"])
    e = sp["final_margin"] + sp["open_home_spread"]
    s = sp[e.abs() >= 2.5]
    m = (s["home_pts"] - s["away_pts"] + s["open_home_spread"]) * np.sign(e[e.abs() >= 2.5])
    to = d.dropna(subset=["open_total"])
    e = to["final_total"] - to["open_total"]
    t = to[e.abs() >= 3]
    mt = (t["home_pts"] + t["away_pts"] - t["open_total"]) * np.sign(e[e.abs() >= 3])
    return {"spread n": int((m != 0).sum()), "spread win%": 100 * float((m > 0).sum() / max((m != 0).sum(), 1)),
            "total n": int((mt != 0).sum()), "total win%": 100 * float((mt > 0).sum() / max((mt != 0).sum(), 1))}


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    train, pred = frames()
    dates = pd.to_datetime(train.drop_duplicates("game_id").set_index("game_id")["date"])
    feats = []
    for s in range(2014, 2027):
        feats.append(season_to_date(team_games(s), dates))
        print(s, "aggregated", flush=True)
    feats = pd.concat(feats, ignore_index=True).drop_duplicates(["game_id", "team_id"])
    train, pred = add(train, feats), add(pred, feats)
    print("pbp coverage of frames 2014-26:", round(float(train.loc[train["season"] >= 2014, "pbp_ok"].mean()), 3))
    fits = {"frozen": walk_forward(train, pred),
            "P1": fit(train, pred, ["luck_margin"], ["luck_total"]),
            "P2": fit(train, pred, ["garbage_margin"], ["garbage_total"]),
            "P1+P2": fit(train, pred, ["luck_margin", "garbage_margin"], ["luck_total", "garbage_total"])}
    base = oriented_openers(fits["frozen"])
    rows = []
    test = range(2020, 2027)
    for tag, w in fits.items():
        ow = oriented_openers(w)
        r = {"model": tag, **{k: round(v, 4) for k, v in mae(w, test).items()}}
        c_dev, c_conf = clv(ow, range(2014, 2018)), clv(ow, range(2024, 2027))
        for era, c in (("dev", c_dev), ("conf", c_conf)):
            r[f"spread CLV {era}"] = round(c["spread CLV"], 3)
            r[f"total CLV {era}"] = round(c["total CLV"], 3)
        wd, wh = win_pct(ow, [2014, 2015, 2016, 2017, 2024]), win_pct(ow, [2025, 2026])
        r.update({"spread win% dev": round(wd["spread win%"], 2), "spread win% holdout": round(wh["spread win%"], 2),
                  "total win% dev": round(wd["total win%"], 2), "total win% holdout": round(wh["total win%"], 2),
                  "spread n dev/hold": f"{wd['spread n']}/{wh['spread n']}", "total n dev/hold": f"{wd['total n']}/{wh['total n']}"})
        if tag != "frozen":
            r.update(info_beyond_close(w, fits["frozen"], test))
        rows.append(r)
    t = pd.DataFrame(rows).set_index("model")
    f = t.loc["frozen"]
    verdict = {}
    for tag in ("P1", "P2", "P1+P2"):
        x = t.loc[tag]
        ok = []
        for mk, cm in (("margin", "spread"), ("total", "total")):
            b, se = (float(v) for v in x[f"{mk}: adjustment coef (se)"].replace("(", "").replace(")", "").split())
            ci = abs(b) > 1.96 * se
            gain = (x[f"{cm} CLV dev"] - f[f"{cm} CLV dev"] >= 0.05) and (x[f"{cm} CLV conf"] - f[f"{cm} CLV conf"] >= 0.05)
            ok.append(ci and gain)
        verdict[tag] = "PASS" if any(ok) else "KILL"
    t["verdict"] = pd.Series(verdict)
    t.T.to_csv(os.path.join(OUT, "p_result.csv"))
    pd.set_option("display.width", 250, "display.max_rows", 200)
    print(t.T.to_string())


if __name__ == "__main__":
    main()
