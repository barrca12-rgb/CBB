"""Roster-prior shadow (research/roster_prior/SHADOW_PLAN.md). Run after each card run by
.github/workflows/shadow_rp4.yml.

The blend under test (research/roster_prior PLAN_v4.md, R3v4): stage 1 starts each team from the average of the
current preseason prior and our own roster-based prior (F2), and stage 2 uses coefficients fit on that blend's
backtest (data/shadow_rp4.json). For every game on today's and later cards it reads the stage-2 inputs the card run
saved (reports/features_<date>.csv), refits stage 1 as of that day with each prior, carries the change in the stage-1
margin and total into the saved inputs, and prices the game three ways against the latest quotes with the card's own
rule (run_day.opening_week_totals, then run_day.plays):
  v1    the live coefficients on the saved inputs (a check that matches the card)
  base  coefficients refit on the current prior's backtest the same way as the blend's (data/shadow_rp4_base.json)
  rp4   the blend: blended stage 1 and its own stage 2
Each new BET is logged once to bets/shadow_rp4/signals.csv. Never alerts, posts, stakes or touches bets/bets.csv, the
card, the site's record or any frozen file.

    python -m cbb.shadow_rp4 [--now ISO]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import tempfile

import numpy as np
import pandas as pd

from . import backtest, data, projection, ratings, run_day, teams

ROOT = os.path.join(os.path.dirname(__file__), "..")
DIR = os.path.join(ROOT, "bets", "shadow_rp4")
SIGNALS = os.path.join(DIR, "signals.csv")
RUNS = os.path.join(DIR, "runs.csv")
GAMES = os.path.join(DIR, "games_latest.csv")
PRIOR = os.path.join(DIR, "prior_latest.csv")
COEF = {"base": os.path.join(ROOT, "data", "shadow_rp4_base.json"), "rp4": os.path.join(ROOT, "data", "shadow_rp4.json")}
FROZEN = os.path.join(ROOT, "audit", "out", "frozen_preseason_prior_{season}.csv")
COLS = ["bet_id", "model", "market", "pick", "game", "date", "game_id", "start", "side", "book", "line", "odds", "edge",
        "ev", "v1_margin", "base_margin", "rp4_margin", "v1_total", "base_total", "rp4_total", "signals_in",
        "lines_pulled_at", "logged_at"]


def current_prior(season: int) -> pd.DataFrame:
    path = FROZEN.format(season=season)
    if os.path.exists(path):
        return pd.read_csv(path).set_index("espn_id")[["off", "def", "tempo"]]
    return backtest.preseason_prior(season)


def roster_prior(season: int) -> pd.DataFrame:
    """F2 for `season` (walk-forward on 2015..season-1), with rosters from each team's games so far (up to 5). The
    research caches are copied to a scratch folder, so the season's files are rebuilt each run and the repository
    copy is never changed."""
    from research.roster_prior import build as v1, build_v2 as v2, build_v3 as v3, build_v4 as v4
    tmp = tempfile.mkdtemp(prefix="rp4_")
    shutil.copytree(v1.OUT, tmp, dirs_exist_ok=True)
    for f in glob.glob(os.path.join(tmp, f"*_{season}.parquet")):
        os.remove(f)
    olds = (v1.OUT, v2.OUT, v3.OUT, v4.OUT)
    try:
        v1.OUT = v2.OUT = v3.OUT = v4.OUT = tmp
        v3.use("V3a")
        fr = {s: v2.design(s, "V3a").join(v4.f1_features(s), how="left") for s in range(v1.FIRST, season + 1)}
    finally:
        v3.use("V2a")
        v1.OUT, v2.OUT, v3.OUT, v4.OUT = olds
        shutil.rmtree(tmp, ignore_errors=True)
    for s in fr:
        fr[s] = fr[s].fillna({c: fr[s][c].median() for c in fr[s].columns if c.startswith("box_")})
    train = pd.concat([fr[s] for s in range(v1.FIRST, season)]).dropna(subset=["off_now", "def_now", "tempo_now"])
    d = fr[season]
    p = pd.DataFrame(index=d.index)
    for c in ("off", "def", "tempo"):
        cc = v4.cols("F2", c)
        p[c] = v4.model("F2", train[cc].to_numpy(float), train[f"{c}_now"].to_numpy(float))(d[cc].to_numpy(float))
    return p


def blended(cur: pd.DataFrame, f2: pd.DataFrame) -> pd.DataFrame:
    """Average of the two priors where F2 exists (F2 centered on the same teams' current-prior average); the current
    prior elsewhere."""
    f2 = f2 - f2.mean() + cur.reindex(f2.index).mean()
    j = cur.join(f2, rsuffix="_r", how="left")
    return pd.DataFrame({c: j[[c, c + "_r"]].mean(axis=1) for c in ("off", "def", "tempo")})


def apply(f: pd.DataFrame, coef: dict) -> pd.DataFrame:
    f = f.copy()
    f["final_margin"] = coef["margin"]["intercept"] + sum(f[k] * v for k, v in coef["margin"].items() if k != "intercept")
    f["final_total"] = coef["total"]["intercept"] + sum(f[k] * v for k, v in coef["total"].items() if k != "intercept")
    return f


def with_blend(f: pd.DataFrame, day: pd.Timestamp, tg, ids, league, cur, bl) -> pd.DataFrame:
    """The saved inputs with the stage-1 margin and total moved by (blended - current) as of `day`."""
    r0 = ratings.fit(tg, day, ids, cur, None, league)
    r1 = ratings.fit(tg, day, ids, bl, None, league)
    p0 = ratings.predict(r0, f["home_id"], f["away_id"], f["neutral"].astype(bool))
    p1 = ratings.predict(r1, f["home_id"], f["away_id"], f["neutral"].astype(bool))
    early = float(np.clip(1 - r0["games"] * 2 / 360 / 15, 0, 1))
    g = f.copy()
    g["pred_margin"] = g["pred_margin"] + (p1["margin"].to_numpy() - p0["margin"].to_numpy())
    g["pred_total"] = g["pred_total"] + (p1["total"].to_numpy() - p0["total"].to_numpy())
    g["pred_margin_x_early"] = g["pred_margin"] * early
    g["pred_total_x_early"] = g["pred_total"] * early
    return g


def latest_lines(now: pd.Timestamp) -> pd.DataFrame:
    c = pd.read_csv(os.path.join(ROOT, "lines", "closing.csv"))
    c["pulled"] = pd.to_datetime(c["pulled_at"], utc=True, errors="coerce", format="ISO8601")
    c["st"] = pd.to_datetime(c["start"], utc=True, errors="coerce", format="ISO8601")
    c = c[c["pulled"] == c["pulled"].max()]
    return c[c["st"] > now].drop(columns=["pulled", "st"])


def bets(card: pd.DataFrame) -> dict:
    out = {}
    for mk in ("spread", "total"):
        col = f"{mk}_verdict"
        if col in card:
            for _, r in card[card[col] == "BET"].iterrows():
                out[(mk, int(r["game_id"]))] = r
    return out


def main(now: pd.Timestamp | None = None) -> None:
    now = now or pd.Timestamp.now(tz="UTC")
    os.makedirs(DIR, exist_ok=True)
    have = set(pd.read_csv(SIGNALS)["bet_id"]) if os.path.exists(SIGNALS) else set()
    run = {"run_at": now.isoformat(timespec="seconds"), "days": 0, "games": 0, "teams_f2": 0, "v1_check_max_diff": None,
           "signals": 0, "error": ""}
    try:
        today = now.tz_convert("America/New_York").strftime("%Y-%m-%d")
        season = run_day.season_of(pd.Timestamp(today))
        data.fetch("player_box", season, refresh=True)
        hist, tg = data.season_games(season, refresh=True)
        live = json.load(open(projection.SAVED))
        coef = {k: json.load(open(p)) for k, p in COEF.items()}
        cur = current_prior(season)
        f2 = roster_prior(season)
        bl = blended(cur, f2)
        run["teams_f2"] = int(len(f2))
        bl.assign(f2_off=f2["off"], f2_def=f2["def"]).to_csv(PRIOR)
        league = ratings.league_averages(data.season_games(season - 1)[1])
        ids = sorted(set(teams.load()["espn_id"]) | set(tg["team_id"]))
        lines = latest_lines(now)
        new, gl, diffs = [], [], []
        for path in sorted(glob.glob(os.path.join(ROOT, "reports", "features_*.csv"))):
            d = os.path.basename(path)[9:19]
            if d < today:
                continue
            f = pd.read_csv(path)
            if not len(f):
                continue
            day = pd.Timestamp(d)
            run["days"] += 1
            run["games"] += len(f)
            fb = with_blend(f, day, tg, ids, league, cur, bl)
            V = {"v1": run_day.opening_week_totals(apply(f, live), day),
                 "base": run_day.opening_week_totals(apply(f, coef["base"]), day),
                 "rp4": run_day.opening_week_totals(apply(fb, coef["rp4"]), day)}
            diffs.append(float((V["v1"]["final_margin"] - f["final_margin"]).abs().max()))
            st = pd.to_datetime(f["start"], utc=True, errors="coerce")
            pre = (st > now).to_numpy()
            M = {k: v.set_index("game_id") for k, v in V.items()}
            for i in np.where(pre)[0]:
                gid = int(f["game_id"].iloc[i])
                gl.append({"game_id": gid, "date": d, "start": f["start"].iloc[i], "home": f["home"].iloc[i],
                           "away": f["away"].iloc[i],
                           **{f"{k}_margin": round(float(M[k].loc[gid, "final_margin"]), 3) for k in M},
                           **{f"{k}_total": round(float(M[k].loc[gid, "final_total"]), 3) for k in M},
                           "updated_at": now.isoformat(timespec="seconds")})
            if not len(lines) or not pre.any():
                continue
            B = {k: bets(run_day.plays(v[pre], lines)) for k, v in V.items()}
            for model, mine in B.items():
                for (mk, gid), r in mine.items():
                    side = r["spread_side"] if mk == "spread" else str(r["total_pick"]).lower()
                    bid = f"{d}|{gid}|{mk}|{side}|{model}"
                    if bid in have:
                        continue
                    line = r["spread_line"] if mk == "spread" else r["total_line"]
                    pick = f"{r['spread_pick']} {line:+g}" if mk == "spread" else f"{r['total_pick']} {line:g}"
                    agree = [k for k, b in B.items()
                             if (mk, gid) in b and (b[(mk, gid)]["spread_side"] if mk == "spread" else str(b[(mk, gid)]["total_pick"]).lower()) == side]
                    new.append({"bet_id": bid, "model": model, "market": mk, "pick": pick, "game": f"{r['away']} at {r['home']}",
                                "date": d, "game_id": gid, "start": r["start"], "side": side, "book": r[f"{mk}_book"],
                                "line": line, "odds": r[f"{mk}_odds"], "edge": round(float(r[f"{mk}_edge"]), 3),
                                "ev": round(float(r[f"{mk}_ev"]), 4),
                                **{f"{k}_margin": round(float(M[k].loc[gid, "final_margin"]), 3) for k in M},
                                **{f"{k}_total": round(float(M[k].loc[gid, "final_total"]), 3) for k in M},
                                "signals_in": "+".join(agree), "lines_pulled_at": str(lines["pulled_at"].iloc[0]),
                                "logged_at": now.isoformat(timespec="seconds")})
                    have.add(bid)
        run["v1_check_max_diff"] = max(diffs) if diffs else None
        if new:
            pd.DataFrame(new).reindex(columns=COLS).to_csv(SIGNALS, mode="a", header=not os.path.exists(SIGNALS), index=False)
        if gl:
            old = pd.read_csv(GAMES) if os.path.exists(GAMES) else pd.DataFrame(columns=list(gl[0]))
            cur_g = pd.DataFrame(gl).drop_duplicates("game_id", keep="last")
            pd.concat([old[~old["game_id"].isin(cur_g["game_id"])], cur_g], ignore_index=True).sort_values(
                ["date", "game_id"]).to_csv(GAMES, index=False)
        run["signals"] = len(new)
    except Exception as e:      # the shadow never stops anything; failures are logged
        run["error"] = str(e)[:300]
        print(f"shadow_rp4 failed: {e}")
    finally:
        pd.DataFrame([run]).to_csv(RUNS, mode="a", header=not os.path.exists(RUNS), index=False)
        print(run)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--now")
    a = ap.parse_args()
    main(pd.Timestamp(a.now) if a.now else None)
