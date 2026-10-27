"""Ridge-1,000 shadow (research/r1000/PLAN.md). Run after each card run by .github/workflows/shadow_r1000.yml.

Reads the stage-2 inputs the card run saved (reports/features_<date>.csv, today and later; cbb/card_features.py)
and the latest pull in lines/closing.csv. Prices every game twice against the same quotes with the card's own rule
(run_day.opening_week_totals, then run_day.plays: best EV across books, spread 2.5+ / total 3+, EV +2%):
  v1     the live coefficients (data/projection.json), recomputed from the saved inputs as a check
  r1000  the same inputs with ridge-penalty-1,000 coefficients (data/shadow_r1000.json)
Each new BET from either version is logged once to bets/shadow_r1000/signals.csv. Never alerts, posts, stakes or
touches bets/bets.csv, the card, the site's record or any frozen file.

    python -m cbb.shadow_r1000 [--now ISO]
"""
from __future__ import annotations

import argparse
import glob
import json
import os

import pandas as pd

from . import projection, run_day

ROOT = os.path.join(os.path.dirname(__file__), "..")
DIR = os.path.join(ROOT, "bets", "shadow_r1000")
SIGNALS = os.path.join(DIR, "signals.csv")
RUNS = os.path.join(DIR, "runs.csv")
GAMES = os.path.join(DIR, "games_latest.csv")
COEF = os.path.join(ROOT, "data", "shadow_r1000.json")
COLS = ["bet_id", "model", "market", "pick", "game", "date", "game_id", "start", "side", "book", "line", "odds",
        "edge", "ev", "v1_margin", "r1000_margin", "v1_total", "r1000_total", "other_model_signal",
        "lines_pulled_at", "logged_at"]


def apply(f: pd.DataFrame, coef: dict) -> pd.DataFrame:
    f = f.copy()
    f["final_margin"] = coef["margin"]["intercept"] + sum(f[k] * v for k, v in coef["margin"].items() if k != "intercept")
    f["final_total"] = coef["total"]["intercept"] + sum(f[k] * v for k, v in coef["total"].items() if k != "intercept")
    return f


def latest_lines(now: pd.Timestamp) -> pd.DataFrame:
    c = pd.read_csv(os.path.join(ROOT, "lines", "closing.csv"))
    c["pulled"] = pd.to_datetime(c["pulled_at"], utc=True, errors="coerce", format="ISO8601")
    c["st"] = pd.to_datetime(c["start"], utc=True, errors="coerce", format="ISO8601")
    c = c[c["pulled"] == c["pulled"].max()]
    return c[c["st"] > now].drop(columns=["pulled", "st"])


def bets(card: pd.DataFrame) -> dict:
    """(market, game_id) -> card row, for every BET on a card from run_day.plays."""
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
    run = {"run_at": now.isoformat(timespec="seconds"), "days": 0, "games": 0, "v1_check_max_diff": None,
           "signals": 0, "error": ""}
    try:
        live, r1k = json.load(open(projection.SAVED)), json.load(open(COEF))
        today = now.tz_convert("America/New_York").strftime("%Y-%m-%d")
        lines = latest_lines(now)
        new, gl, diffs = [], [], []
        for path in sorted(glob.glob(os.path.join(ROOT, "reports", "features_*.csv"))):
            d = os.path.basename(path)[9:19]
            if d < today:
                continue
            f = pd.read_csv(path)
            if not len(f):
                continue
            run["days"] += 1
            run["games"] += len(f)
            day = pd.Timestamp(d)
            v1 = run_day.opening_week_totals(apply(f, live), day)
            rk = run_day.opening_week_totals(apply(f, r1k), day)
            diffs.append(float((v1["final_margin"] - f["final_margin"]).abs().max()))
            st = pd.to_datetime(f["start"], utc=True, errors="coerce")
            for i in range(len(f)):
                if st.iloc[i] > now:
                    gl.append({"game_id": int(f["game_id"].iloc[i]), "date": d, "start": f["start"].iloc[i],
                               "home": f["home"].iloc[i], "away": f["away"].iloc[i],
                               "v1_margin": round(float(v1["final_margin"].iloc[i]), 3), "r1000_margin": round(float(rk["final_margin"].iloc[i]), 3),
                               "v1_total": round(float(v1["final_total"].iloc[i]), 3), "r1000_total": round(float(rk["final_total"].iloc[i]), 3),
                               "updated_at": now.isoformat(timespec="seconds")})
            if not len(lines):
                continue
            pre = st > now
            b1 = bets(run_day.plays(v1[pre.to_numpy()], lines))
            bk = bets(run_day.plays(rk[pre.to_numpy()], lines))
            mv1 = v1.set_index("game_id")
            mrk = rk.set_index("game_id")
            for model, mine, other in (("v1", b1, bk), ("r1000", bk, b1)):
                for (mk, gid), r in mine.items():
                    side = r["spread_side"] if mk == "spread" else str(r["total_pick"]).lower()
                    bid = f"{d}|{gid}|{mk}|{side}|{model}"
                    if bid in have:
                        continue
                    o = other.get((mk, gid))
                    o_side = None if o is None else (o["spread_side"] if mk == "spread" else str(o["total_pick"]).lower())
                    line = r["spread_line"] if mk == "spread" else r["total_line"]
                    pick = f"{r['spread_pick']} {line:+g}" if mk == "spread" else f"{r['total_pick']} {line:g}"
                    new.append({"bet_id": bid, "model": model, "market": mk, "pick": pick, "game": f"{r['away']} at {r['home']}",
                                "date": d, "game_id": gid, "start": r["start"], "side": side, "book": r[f"{mk}_book"],
                                "line": line, "odds": r[f"{mk}_odds"], "edge": round(float(r[f"{mk}_edge"]), 3),
                                "ev": round(float(r[f"{mk}_ev"]), 4),
                                "v1_margin": round(float(mv1.loc[gid, "final_margin"]), 3), "r1000_margin": round(float(mrk.loc[gid, "final_margin"]), 3),
                                "v1_total": round(float(mv1.loc[gid, "final_total"]), 3), "r1000_total": round(float(mrk.loc[gid, "final_total"]), 3),
                                "other_model_signal": o_side == side, "lines_pulled_at": str(lines["pulled_at"].iloc[0]),
                                "logged_at": now.isoformat(timespec="seconds")})
                    have.add(bid)
        run["v1_check_max_diff"] = max(diffs) if diffs else None
        if new:
            pd.DataFrame(new).reindex(columns=COLS).to_csv(SIGNALS, mode="a", header=not os.path.exists(SIGNALS), index=False)
        if gl:
            old = pd.read_csv(GAMES) if os.path.exists(GAMES) else pd.DataFrame(columns=list(gl[0]))
            cur = pd.DataFrame(gl).drop_duplicates("game_id", keep="last")
            pd.concat([old[~old["game_id"].isin(cur["game_id"])], cur], ignore_index=True).sort_values(["date", "game_id"]).to_csv(GAMES, index=False)
        run["signals"] = len(new)
    except Exception as e:      # the shadow never stops anything; failures are logged
        run["error"] = str(e)[:300]
        print(f"shadow_r1000 failed: {e}")
    finally:
        pd.DataFrame([run]).to_csv(RUNS, mode="a", header=not os.path.exists(RUNS), index=False)
        print(run)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--now")
    a = ap.parse_args()
    main(pd.Timestamp(a.now) if a.now else None)
