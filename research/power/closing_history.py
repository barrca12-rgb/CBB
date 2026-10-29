"""Every pull of lines/closing.csv, rebuilt from git history (research only).

The card job overwrites lines/closing.csv on each pull and commits it, so the file on disk holds only the latest
pull; earlier pulls survive only as git versions. The quote logger (lines/obs*) watches v1's signal games only, so
plays that only a shadow makes (e.g. lineup v2) have no other close-time quotes. This reads every committed
version, keeps one row per (pull, book, game), and caches the result (research/power/out/closing_history.parquet,
rebuilt incrementally; safe to delete).

    python -m research.power.closing_history
"""
from __future__ import annotations

import io
import os
import subprocess

import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
CACHE = os.path.join(os.path.dirname(__file__), "out", "closing_history.parquet")


def _git(*a) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def load(refresh: bool = True) -> pd.DataFrame:
    old = pd.read_parquet(CACHE) if os.path.exists(CACHE) else pd.DataFrame()
    done = set(old["commit"]) if len(old) else set()
    if refresh:
        commits = [c for c in _git("log", "--format=%H", "--", "lines/closing.csv").split() if c not in done]
        parts = []
        for c in commits:
            try:
                txt = _git("show", f"{c}:lines/closing.csv")
            except subprocess.CalledProcessError:
                continue
            if not txt.strip():
                continue
            d = pd.read_csv(io.StringIO(txt))
            d["commit"] = c
            parts.append(d)
        if parts:
            old = pd.concat([old] + parts, ignore_index=True) if len(old) else pd.concat(parts, ignore_index=True)
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            old.to_parquet(CACHE, index=False)
    if not len(old):
        return old
    keys = [c for c in ("pulled_at", "book", "home_id", "away_id", "start") if c in old]
    return old.drop_duplicates(keys).reset_index(drop=True)


def close_line(hist: pd.DataFrame, home_id: int, away_id: int, start, market: str, window_min: int = 60):
    """Median home spread (or total) across books, using each book's last quote observed within window_min minutes
    before the start (and before it). Matches the game in either orientation. NaN if none."""
    st = pd.Timestamp(start)
    st = st.tz_localize("UTC") if st.tzinfo is None else st.tz_convert("UTC")
    same = hist[(hist["home_id"] == home_id) & (hist["away_id"] == away_id)]
    flip = hist[(hist["home_id"] == away_id) & (hist["away_id"] == home_id)]
    h, sgn = (same, 1.0) if len(same) else (flip, -1.0)
    if not len(h):
        return float("nan")
    seen = pd.to_datetime(h["pulled_at"], utc=True, errors="coerce", format="ISO8601")
    h = h[(seen < st) & (st - seen <= pd.Timedelta(minutes=window_min))].assign(seen=seen)
    col = "home_spread" if market == "spread" else "total"
    h = h.dropna(subset=[col]).sort_values("seen").groupby("book").tail(1)
    if not len(h):
        return float("nan")
    v = float(h[col].median())
    return sgn * v if market == "spread" else v


if __name__ == "__main__":
    d = load()
    print(f"{len(d)} rows from {d['commit'].nunique() if len(d) else 0} committed pulls; "
          f"pulled_at {d['pulled_at'].min() if len(d) else '-'} to {d['pulled_at'].max() if len(d) else '-'}")
