"""Barttorvik's daily ratings file, fetched from Chad's own computer and committed to the repo (Chad's Oct 30 option 2).

Barttorvik refuses GitHub's servers (HTTP 403, Oct 30), so the card cannot download his time-machine file itself.
This script runs on Chad's machine, where the site serves normally, a few times a day. For each of the last DAYS
dates with no file in data/barttorvik_tm/ yet, it asks once for that date's file, waiting PAUSE seconds between
requests. It keeps only the four columns the model uses, the same as data/barttorvik_preseason_<season>.csv, then
commits and pushes. The card reads data/barttorvik_tm/<YYYYMMDD>.csv before trying the network (cbb/barttorvik.py).

Standard library only (no pandas needed). Setup steps: local/README.md.

    python3 local/fetch_barttorvik.py            # fetch, commit, push
    python3 local/fetch_barttorvik.py --no-push  # fetch only
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "data", "barttorvik_tm")
URL = "https://barttorvik.com/timemachine/team_results/{}_team_results.json.gz"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
DAYS, PAUSE = 3, 5
COLS = ["team", "adj_oe", "adj_de", "adj_tempo"]


def rows_for(day: dt.date) -> list[list] | None:
    """The four columns for every team on `day`, or None when Barttorvik has no file for it yet."""
    req = urllib.request.Request(URL.format(f"{day:%Y%m%d}"), headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    try:
        raw = gzip.decompress(raw)
    except OSError:
        pass
    data = json.loads(raw)
    return [[r[1], r[4], r[6], r[44]] for r in data] if data else None


def fetch(today: dt.date) -> list[str]:
    """Saves each missing file among the last DAYS dates (today included); returns the paths written."""
    os.makedirs(OUT, exist_ok=True)
    wrote = []
    for k in range(DAYS):
        day = today - dt.timedelta(days=k)
        path = os.path.join(OUT, f"{day:%Y%m%d}.csv")
        if os.path.exists(path):
            continue
        if wrote or k:
            time.sleep(PAUSE)
        rows = rows_for(day)
        if not rows:
            print(f"{day}: not posted yet")
            continue
        with open(path + ".tmp", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(COLS)
            w.writerows(rows)
        os.replace(path + ".tmp", path)
        wrote.append(path)
        print(f"{day}: saved {len(rows)} teams")
    return wrote


def push(paths: list[str]) -> None:
    git = lambda *a: subprocess.run(["git", "-C", ROOT, *a], check=True)
    git("add", *paths)
    git("commit", "-m", "Barttorvik daily file(s) from Chad's machine: " + ", ".join(os.path.basename(p)[:8] for p in paths))
    for i in range(5):            # the card pushes every 10 minutes; retry if one lands in between
        try:
            git("pull", "--rebase", "origin", "claude/college-basketball-model-nmztcl")
            git("push", "origin", "HEAD:claude/college-basketball-model-nmztcl")
            return
        except subprocess.CalledProcessError:
            time.sleep(5 * (i + 1))
    sys.exit("push failed five times; the files are committed locally and go up with the next run")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).date()     # US Eastern (standard time is close enough)
    written = fetch(today)
    if written and not a.no_push:
        push(written)
