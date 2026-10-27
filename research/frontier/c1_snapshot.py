"""C1 data: a daily snapshot of two public rating systems, saved with the fetch time, from the first day this runs
(pre-registered in PLAN.md). Research only: reads public pages, writes under research/frontier/snapshots/.

  haslametrics  the full current ratings file (ratings.xml, time-dependent; every team's offense, defense, tempo and
                the rest), saved as fetched.
  evanmiya      the free team-ratings table (team, obpr, dbpr, bpr, tempo, opponent and pace adjustments). Game
                predictions there are subscriber-only and are not fetched.

    python -m research.frontier.c1_snapshot             # today's snapshot
    python -m research.frontier.c1_snapshot --archive   # once: Haslametrics' past season files (2015-2026)
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import urllib.request

import pandas as pd

HERE = os.path.dirname(__file__)
SNAP = os.path.join(HERE, "snapshots")
UA = {"User-Agent": "cbb-research (daily ratings snapshot)", "Accept-Encoding": "gzip, br"}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        b, enc = r.read(), r.headers.get("Content-Encoding")
    if enc == "gzip":
        return gzip.decompress(b)
    if enc == "br":                  # Haslametrics answers in brotli whatever the request asks for
        import brotli
        return brotli.decompress(b)
    return b


def evanmiya() -> pd.DataFrame:
    """The team-ratings table embedded in the public page (Next.js flight data)."""
    s = get("https://evanmiya.com/team-ratings").decode("utf-8", "replace").replace('\\"', '"')
    rows = []
    for m in re.finditer(r'\{[^{}]*"obpr":[^{}]*\}', s):
        try:
            o = json.loads(m.group(0))
        except ValueError:
            continue
        team = o.get("team") or o.get("name") or o.get("teamName")
        if team is None:
            t = re.search(r'"(?:team|name|teamName)":"([^"]+)"', m.group(0))
            team = t.group(1) if t else None
        rows.append({"team": team, **{k: v for k, v in o.items() if isinstance(v, (int, float, str)) and not k.endswith("Tip")}})
    return pd.DataFrame(rows).drop_duplicates()


def snapshot() -> dict:
    now = pd.Timestamp.now(tz="UTC")
    d = os.path.join(SNAP, f"{now:%Y-%m-%d}")
    os.makedirs(d, exist_ok=True)
    out = {"fetched_at": now.isoformat(timespec="seconds")}
    try:
        x = get("https://haslametrics.com/ratings.xml")
        with gzip.open(os.path.join(d, f"haslametrics_{now:%H%M}.xml.gz"), "wb") as fh:
            fh.write(x)
        out["haslametrics_teams"] = len(re.findall(rb"<mr ", x))
        out["haslametrics_as_of"] = (re.search(rb'<dt md="([^"]+)"', x) or [None, b""])[1].decode()
    except Exception as e:
        out["haslametrics_error"] = str(e)
    try:
        e = evanmiya()
        e.insert(0, "fetched_at", out["fetched_at"])
        e.to_csv(os.path.join(d, f"evanmiya_{now:%H%M}.csv.gz"), index=False)
        out["evanmiya_teams"] = int(e["team"].notna().sum())
    except Exception as ex:
        out["evanmiya_error"] = str(ex)
    with open(os.path.join(SNAP, "log.jsonl"), "a") as fh:
        fh.write(json.dumps(out) + "\n")
    return out


def archive() -> None:
    d = os.path.join(SNAP, "haslametrics_archive")
    os.makedirs(d, exist_ok=True)
    for y in range(15, 27):
        x = get(f"https://haslametrics.com/ratings{y}.xml")
        with gzip.open(os.path.join(d, f"ratings{y}.xml.gz"), "wb") as fh:
            fh.write(x)
        print(f"20{y}", len(re.findall(rb"<mr ", x)), "teams,", len(re.findall(rb"<tr ", x)), "daily rank rows")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", action="store_true")
    a = ap.parse_args()
    if a.archive:
        archive()
    print(snapshot())
