"""Weekly sequential CLV read, lineup v2 shadow vs live v1 spreads, 2026-27 (research/power/SEQUENTIAL_PLAN.md).

Read-only. Paired per game: closing-line value of v2's pick minus v1's (0 for a strategy with no pick), on games
where the picks differ. Entry = each log's own line; close = median across books of each book's last quote in the
60 minutes before the start, rebuilt from the git history of lines/closing.csv (closing_history.py), the same close
for both strategies. Interim looks use the Haybittle-Peto boundary |z| >= 3.29; the Mar 14 final read uses 1.96.

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


def picks() -> tuple[pd.DataFrame, pd.DataFrame]:
    v1 = pd.read_csv(os.path.join(ROOT, "bets", "bets.csv"))
    # same v1 set as research/v2_lineup/evaluate.py: spreads logged after the freeze, voids excluded
    v1 = v1[(pd.to_datetime(v1["logged_at"], utc=True, format="ISO8601") >= pd.Timestamp("2026-10-26T19:20:50Z"))
            & (v1["market"] == "spread") & (v1["status"] != "void")][["date", "game_id", "home_id", "away_id", "side", "line"]]
    v2 = pd.read_csv(os.path.join(ROOT, "bets", "shadow_v2", "signals.csv"))
    v2 = v2[["date", "game_id", "home_id", "away_id", "start", "side", "line"]]
    # one pick per strategy per game: the first logged
    return v1.drop_duplicates("game_id"), v2.drop_duplicates("game_id")


def clv(row, hist, start) -> float:
    if pd.isna(row["side"]):
        return 0.0
    h = close_line(hist, int(row["home_id"]), int(row["away_id"]), start, "spread")
    if np.isnan(h):
        return float("nan")
    side_close = h if row["side"] == "home" else -h
    return float(row["line"]) - side_close


def main(through: str | None = None) -> None:
    os.makedirs(OUT, exist_ok=True)
    hist = load()
    v1, v2 = picks()
    starts = hist.drop_duplicates(["home_id", "away_id", "start"])
    g = pd.merge(v1, v2, on="game_id", how="outer", suffixes=("_v1", "_v2"))
    rows = []
    for _, r in g.iterrows():
        home = r["home_id_v2"] if pd.notna(r.get("home_id_v2")) else r["home_id_v1"]
        away = r["away_id_v2"] if pd.notna(r.get("away_id_v2")) else r["away_id_v1"]
        date = r["date_v2"] if pd.notna(r.get("date_v2")) else r["date_v1"]
        if through and str(date) > through:
            continue
        st = r.get("start")
        if pd.isna(st):
            m = starts[((starts["home_id"] == home) & (starts["away_id"] == away)) | ((starts["home_id"] == away) & (starts["away_id"] == home))]
            st = m["start"].iloc[-1] if len(m) else np.nan
        if pd.isna(st) or pd.Timestamp(st) > pd.Timestamp.now(tz="UTC"):
            continue                                            # not started yet: no close
        s1, s2 = r.get("side_v1"), r.get("side_v2")
        if s1 == s2:
            continue                                            # same pick: no paired difference
        a = clv({"side": s1, "home_id": home, "away_id": away, "line": r.get("line_v1")}, hist, st) if pd.notna(s1) else 0.0
        b = clv({"side": s2, "home_id": home, "away_id": away, "line": r.get("line_v2")}, hist, st) if pd.notna(s2) else 0.0
        rows.append({"date": date, "game_id": r["game_id"], "v1": s1, "v2": s2, "clv_v1": a, "clv_v2": b, "diff": b - a})
    d = pd.DataFrame(rows)
    lines = [f"sequential CLV read through {through or 'today'} ({pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC)",
             f"closing history: {hist['commit'].nunique() if len(hist) else 0} pulls"]
    if not len(d):
        lines.append("no finished games where v1 and v2 picks differ yet")
    else:
        ok = d.dropna(subset=["diff"])
        lines.append(f"games where picks differ: {len(d)}; with a close for every pick: {len(ok)}; "
                     f"no close: {len(d) - len(ok)}")
        by = ok.groupby("date")["diff"].agg(["sum", "count"])
        n, tot = int(by["count"].sum()), float(by["sum"].sum())
        mean = tot / n if n else np.nan
        resid = by["sum"] - mean * by["count"]
        se = float(np.sqrt((resid ** 2).sum())) / n if n and len(by) > 1 else np.nan
        z = mean / se if se and se > 0 else np.nan
        final = (through or pd.Timestamp.now().strftime("%Y-%m-%d")) >= FINAL_DATE
        bound = FINAL_Z if final else INTERIM_Z
        lines += [f"v2 minus v1 CLV per differing game: {mean:+.3f} pts (date-clustered SE {se:.3f}); z = {z:+.2f}; "
                  f"{'final' if final else 'interim'} boundary |z| >= {bound}: {'CROSSED' if abs(z) >= bound else 'not crossed'}",
                  f"v2-only picks {int(ok['v1'].isna().sum())}, v1-only {int(ok['v2'].isna().sum())}, opposite sides {int((ok['v1'].notna() & ok['v2'].notna()).sum())}; "
                  f"dates {len(by)}",
                  "monitor only: any decision follows research/v2_lineup/PLAN.md unless Chad approves the drafted Amendment 3."]
    txt = "\n".join(lines)
    print(txt)
    open(os.path.join(OUT, f"sequential_{(through or pd.Timestamp.now().strftime('%Y-%m-%d'))}.txt"), "w").write(txt + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--through")
    main(ap.parse_args().through)
