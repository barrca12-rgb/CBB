"""Weekly health line (helper doc, rule 2): one line of counts for the last 7 days, so a silent failure shows up
within a week. A zero, or a count far below the week before, means something broke.

    python -m audit.health [--end YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess

import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _in(ts: pd.Series, a: pd.Timestamp, b: pd.Timestamp) -> pd.Series:
    t = pd.to_datetime(ts, utc=True, errors="coerce", format="ISO8601")
    return (t >= a) & (t < b)


def counts(a: pd.Timestamp, b: pd.Timestamp) -> dict:
    out = {}
    log = subprocess.run(["git", "log", "--since", a.isoformat(), "--until", b.isoformat(), "--format=%s"],
                         cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    out["card runs"] = sum(s.startswith("Update CBB card (") for s in log)
    n = 0
    for f in glob.glob(os.path.join(ROOT, "lines", "obs", "*.csv*")) + glob.glob(os.path.join(ROOT, "lines", "obs_targeted", "*.csv*")):
        try:
            n += int(_in(pd.read_csv(f, usecols=["observed_at"])["observed_at"], a, b).sum())
        except Exception:
            pass
    out["quotes logged"] = n
    for tag, d in (("v2", "shadow_v2"), ("ridge", "shadow_r1000")):
        s, r = os.path.join(ROOT, "bets", d, "signals.csv"), os.path.join(ROOT, "bets", d, "runs.csv")
        out[f"{tag} signals"] = int(_in(pd.read_csv(s)["logged_at"], a, b).sum()) if os.path.exists(s) else 0
        if os.path.exists(r):
            rr = pd.read_csv(r)
            rr = rr[_in(rr["run_at"], a, b)]
            out[f"{tag} runs"] = len(rr)
            e = rr["error"].fillna("").astype(str) if "error" in rr else pd.Series("", index=rr.index)
            nobox = e.str.startswith("no adjustments")      # v2: no box scores yet, adjustments 0 (v2 = v1)
            out[f"{tag} run errors"] = int((e.str.len().gt(0) & ~nobox).sum())
            if nobox.any():
                out[f"{tag} runs without box scores"] = int(nobox.sum())
            if "v1_check_max_diff" in rr and rr["v1_check_max_diff"].notna().any():
                out["ridge input check (max diff)"] = float(rr["v1_check_max_diff"].max())
    bets = pd.read_csv(os.path.join(ROOT, "bets", "bets.csv"), dtype=str)
    new = bets[_in(bets["logged_at"], a, b)]
    posted = json.load(open(os.path.join(ROOT, "bets", "discord_posted.json"))).get("bets", {})
    out["new bets logged"] = len(new)
    out["Discord posts (of new bets)"] = int(new["bet_id"].isin(list(posted)).sum())
    out["marked placed (of new bets)"] = int(new["placed"].fillna("").str.lower().eq("yes").sum())
    return out


def flags(c: dict, prev: dict, end: pd.Timestamp) -> list[str]:
    f = []
    et = end.tz_convert("America/New_York")
    in_season = et.month in (12, 1, 2, 3, 4) or (et.month == 11 and et.day >= 5)   # games played, box scores due
    if in_season and c.get("v2 runs without box scores", 0):
        f.append(f"v2 had no box scores in {c['v2 runs without box scores']} run(s): lineup adjustments are 0")
    for k in ("card runs", "quotes logged", "v2 runs", "ridge runs"):
        if c.get(k, 0) == 0:
            f.append(f"{k} is 0")
        elif prev.get(k) and c[k] < 0.5 * prev[k]:
            f.append(f"{k} fell to {c[k]} from {prev[k]}")
    for k in ("v2 run errors", "ridge run errors"):
        if c.get(k, 0):
            f.append(f"{k}: {c[k]}")
    if c.get("ridge input check (max diff)", 0) > 1e-6:
        f.append(f"ridge input check off by {c['ridge input check (max diff)']:.3g} (card inputs no longer match)")
    if c.get("new bets logged", 0) and c["Discord posts (of new bets)"] < c["new bets logged"]:
        f.append(f"{c['new bets logged'] - c['Discord posts (of new bets)']} new bet(s) not posted to Discord")
    return f


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", help="YYYY-MM-DD (default: now)")
    x = ap.parse_args()
    b = pd.Timestamp(x.end, tz="America/New_York").tz_convert("UTC") if x.end else pd.Timestamp.now(tz="UTC")
    a = b - pd.Timedelta(days=7)
    c, prev = counts(a, b), counts(a - pd.Timedelta(days=7), a)
    line = " · ".join(f"{k} {v:g}" if isinstance(v, float) else f"{k} {v}" for k, v in c.items())
    print(f"Health, {a.tz_convert('America/New_York'):%b %d} to {b.tz_convert('America/New_York'):%b %d}: {line}")
    fl = flags(c, prev, b)
    print("Flags: " + ("; ".join(fl) if fl else "none"))


if __name__ == "__main__":
    main()
