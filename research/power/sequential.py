"""Weekly sequential CLV reads, 2026-27 (research/power/SEQUENTIAL_PLAN.md): lineup v2 shadow vs live v1 spreads,
and E2 shadow vs live v1 totals.

Read-only. Paired per game: closing-line value of the shadow's pick minus v1's (0 for a strategy with no pick), on
games where the picks differ. Entry = each log's own line; close = median across books of each book's last quote in
the 60 minutes before the start, rebuilt from the git history of lines/closing.csv (closing_history.py), the same
close for both strategies. Interim looks use the Haybittle-Peto boundary |z| >= 3.29; the Mar 14 final uses 1.96.

    python -m research.power.sequential [--through YYYY-MM-DD]     # -> research/power/out/sequential_<date>.txt
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

from research.power.closing_history import close_line, load

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(os.path.dirname(__file__), "out")
INTERIM_Z, FINAL_Z, FINAL_DATE = 3.29, 1.96, "2027-03-14"
FREEZE = pd.Timestamp("2026-10-26T19:20:50Z")
READS = {"spread": ("lineup v2", os.path.join("bets", "shadow_v2", "signals.csv")),
         "total": ("E2", os.path.join("bets", "shadow_e2", "signals.csv"))}


def _scores() -> pd.DataFrame:
    try:
        from cbb import data
        g = data.season_games(2027)[0]
        return g.drop_duplicates("game_id").set_index("game_id")[["home_pts", "away_pts"]].astype(float)
    except Exception:
        return pd.DataFrame(columns=["home_pts", "away_pts"])


SCORES = pd.DataFrame(columns=["home_pts", "away_pts"])


def picks(market: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    v1 = pd.read_csv(os.path.join(ROOT, "bets", "bets.csv"))
    # same v1 set as research/v2_lineup/evaluate.py: logged after the freeze, voids excluded
    v1 = v1[(pd.to_datetime(v1["logged_at"], utc=True, format="ISO8601") >= FREEZE) & (v1["market"] == market)
            & (v1["status"] != "void")][["date", "game_id", "home_id", "away_id", "side", "line"]]
    path = os.path.join(ROOT, READS[market][1])
    sh = pd.read_csv(path)[["date", "game_id", "home_id", "away_id", "start", "side", "line"]] if os.path.exists(path) else \
        pd.DataFrame(columns=["date", "game_id", "home_id", "away_id", "start", "side", "line"])
    return v1.drop_duplicates("game_id"), sh.drop_duplicates("game_id")     # first logged pick per game


def clv(side, line, home, away, hist, start, market) -> float:
    c = close_line(hist, int(home), int(away), start, market)
    if np.isnan(c):
        return float("nan")
    if market == "spread":
        return float(line) - (c if side == "home" else -c)
    return (c - float(line)) if side == "over" else (float(line) - c)


def read(market: str, hist: pd.DataFrame, through: str | None) -> list[str]:
    name = READS[market][0]
    v1, sh = picks(market)
    starts = hist.drop_duplicates(["home_id", "away_id", "start"])
    g = pd.merge(v1, sh, on="game_id", how="outer", suffixes=("_v1", "_sh"))
    rows = []
    for _, r in g.iterrows():
        home = r["home_id_sh"] if pd.notna(r.get("home_id_sh")) else r["home_id_v1"]
        away = r["away_id_sh"] if pd.notna(r.get("away_id_sh")) else r["away_id_v1"]
        date = r["date_sh"] if pd.notna(r.get("date_sh")) else r["date_v1"]
        if through and str(date) > through:
            continue
        st = r.get("start")
        if pd.isna(st):
            m = starts[((starts["home_id"] == home) & (starts["away_id"] == away)) | ((starts["home_id"] == away) & (starts["away_id"] == home))]
            st = m["start"].iloc[-1] if len(m) else np.nan
        if pd.isna(st) or pd.Timestamp(st) > pd.Timestamp.now(tz="UTC"):
            continue                                            # not started yet: no close
        s1, s2 = r.get("side_v1"), r.get("side_sh")
        if s1 == s2:
            continue                                            # same pick: no paired difference
        a = clv(s1, r["line_v1"], home, away, hist, st, market) if pd.notna(s1) else 0.0
        b = clv(s2, r["line_sh"], home, away, hist, st, market) if pd.notna(s2) else 0.0
        rc = np.nan                                             # result vs the same close (condition 1)
        if r["game_id"] in SCORES.index:
            hp, ap = SCORES.loc[r["game_id"]]
            c = close_line(hist, int(home), int(away), st, market)
            if not np.isnan(c):
                y = (hp - ap) + c if market == "spread" else (hp + ap) - c      # home/over side vs the close
                sgn = lambda s: 0.0 if pd.isna(s) else (1.0 if s in ("home", "over") else -1.0)
                rc = sgn(s2) * y - sgn(s1) * y
        rows.append({"date": date, "v1": s1, "sh": s2, "diff": b - a, "close_rec": rc})
    d = pd.DataFrame(rows)
    out = [f"\n{name} vs v1, {market}s"]
    if not len(d):
        return out + ["  no finished games where the picks differ yet"]
    ok = d.dropna(subset=["diff"])
    out.append(f"  games where picks differ: {len(d)}; with a close for every pick: {len(ok)}; no close: {len(d) - len(ok)}")
    if not len(ok):
        return out
    by = ok.groupby("date")["diff"].agg(["sum", "count"])
    n, tot = int(by["count"].sum()), float(by["sum"].sum())
    mean = tot / n
    resid = by["sum"] - mean * by["count"]
    se = float(np.sqrt((resid ** 2).sum())) / n if len(by) > 1 else np.nan
    z = mean / se if se and se > 0 else np.nan
    final = (through or pd.Timestamp.now().strftime("%Y-%m-%d")) >= FINAL_DATE
    bound = FINAL_Z if final else INTERIM_Z
    cr = ok.dropna(subset=["close_rec"])
    crs = (f"{cr['close_rec'].mean():+.2f} pts over {len(cr)} settled games (condition 1: must be >= 0 at a decision read)"
           if len(cr) else "no settled games yet")
    out.append(f"  result vs the close, {name} side minus v1 side per differing game: {crs}")
    return out + [f"  {name} minus v1 CLV per differing game: {mean:+.3f} pts (date-clustered SE {se:.3f}); z = {z:+.2f}; "
                  f"{'final' if final else 'interim'} boundary |z| >= {bound} (Haybittle-Peto, max 18 interim looks): {'CROSSED' if abs(z) >= bound else 'not crossed'}",
                  f"  {name}-only picks {int(ok['v1'].isna().sum())}, v1-only {int(ok['sh'].isna().sum())}, opposite sides "
                  f"{int((ok['v1'].notna() & ok['sh'].notna()).sum())}; dates {len(by)}"]


def main(through: str | None = None) -> None:
    os.makedirs(OUT, exist_ok=True)
    global SCORES
    hist = load()
    SCORES = _scores()
    lines = [f"sequential CLV reads through {through or 'today'} ({pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC); "
             f"closing history: {hist['commit'].nunique() if len(hist) else 0} pulls"]
    for market in ("spread", "total"):
        lines += read(market, hist, through)
    lines.append("\na crossing is a proposal only (Amendment 3 / research/e2_shadow/PLAN.md): Chad's approval, a MODEL_FREEZE "
                 "entry and a Discord note; nothing live changes by itself.")
    txt = "\n".join(lines)
    print(txt)
    open(os.path.join(OUT, f"sequential_{(through or pd.Timestamp.now().strftime('%Y-%m-%d'))}.txt"), "w").write(txt + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--through")
    main(ap.parse_args().through)
