"""Dated snapshot of CJH Analytics' preseason files (cjhanalytics.com), for the two pre-registered reads in PLAN.md.

The raw files are third-party content, so they are stored in the private data repo (../cbb-data/research/cjh/
snapshots/<UTC time>/), never in this public repo. Only their hashes, sizes and fetch times are recorded here
(research/cjh/snapshots.csv), so a later read can prove which pre-opening file it used.

    python -m research.cjh.snapshot [dest_root]
"""
from __future__ import annotations

import csv
import hashlib
import os
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(__file__)
BASE = "https://cjhanalytics.com/"
FILES = ["preseason_projections.json", "manual_overrides/player_injuries_2026.json", "player_projections.json",
         "players_current.json", "changelog.json"]
LEDGER = os.path.join(HERE, "snapshots.csv")


def main() -> None:
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "..", "cbb-data", "research", "cjh", "snapshots")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%MZ")
    dest = os.path.join(root, stamp)
    os.makedirs(dest, exist_ok=True)
    rows = []
    for f in FILES:
        req = urllib.request.Request(BASE + f, headers={"User-Agent": "cbb-model research snapshot"})
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read()
            lm, etag = r.headers.get("Last-Modified", ""), r.headers.get("ETag", "")
        out = os.path.join(dest, f.replace("/", "__"))
        open(out, "wb").write(body)
        rows.append({"snapshot": stamp, "file": f, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                     "last_modified": lm, "etag": etag})
        print(f, len(body), rows[-1]["sha256"][:16], lm)
    new = not os.path.exists(LEDGER)
    with open(LEDGER, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        if new:
            w.writeheader()
        w.writerows(rows)
    print("saved to", dest)


if __name__ == "__main__":
    main()
