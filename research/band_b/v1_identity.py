"""Band B go-live check: v1's output is byte-identical with and without band B (research/band_b; run before go-live).

Runs one code tree (`--root`, the repository before band B or after) on a bet log (`--bets`) and writes the hash of
every v1 output to a JSON file; compare.py-style diffing is done by `--compare`.

  card      run_day.plays() on every committed pull of lines/closing.csv (git history) against the saved model
            numbers of each card date (reports/cbb_<date>.csv): v1's columns only (band B adds *_bandb columns)
  log       tracker.load() (the v1 view, without the new bet_type column), status() without its refresh time, tripwires(), recent()
  record    record_page.build() and build_verify() with the "Updated" time removed and band B's own section cut
  discord   record._logged / record._settled payloads for every v1 row
  chart     record_chart.stats() of v1, the X caption, and the two PNGs' sha256

Nothing in the repository is written: every state file is redirected to a temporary folder and tipoff.refresh is
a no-op (both trees read the same cached tip times).

    python research/band_b/v1_identity.py --root <tree> --bets <csv> --out <json>
    python research/band_b/v1_identity.py --compare a.json b.json
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile

H = lambda s: hashlib.sha256(s if isinstance(s, bytes) else str(s).encode()).hexdigest()


def pulls(root: str):
    """(date, pull time, rows) for every committed pull of lines/closing.csv, newest commit first."""
    import pandas as pd
    revs = subprocess.run(["git", "-C", root, "log", "--format=%H", "--", "lines/closing.csv"], capture_output=True,
                          text=True, check=True).stdout.split()
    for c in revs:
        try:
            txt = subprocess.run(["git", "-C", root, "show", f"{c}:lines/closing.csv"], capture_output=True, text=True,
                                 check=True).stdout
        except subprocess.CalledProcessError:
            continue
        if not txt.strip():
            continue
        d = pd.read_csv(io.StringIO(txt))
        if "date" not in d or "home_id" not in d:
            continue
        yield c, d


def emit(root: str, bets: str, out: str) -> None:
    sys.path.insert(0, os.path.abspath(root))
    import numpy as np
    import pandas as pd
    from cbb import clv_primary, record, record_chart, record_page, run_day, tipoff, tracker
    assert os.path.abspath(tracker.ROOT).startswith(os.path.abspath(root)), tracker.ROOT
    tmp = tempfile.mkdtemp()
    tracker.BETS = bets
    for k in ("STAKE_CAP_STATE", "TRIP_STATE", "VOID_ALERTED"):
        setattr(tracker, k, os.path.join(tmp, k))
    clv_primary.TABLE = os.path.join(tmp, "clv_primary.csv")
    tipoff.refresh = lambda *a, **k: None
    res: dict = {}

    # card: every committed pull x the saved model numbers of that pull's dates
    cards = {}
    for f in sorted(os.listdir(os.path.join(root, "reports"))):
        m = re.fullmatch(r"cbb_(\d{4}-\d{2}-\d{2})\.csv", f)
        if m:
            c = pd.read_csv(os.path.join(root, "reports", f))
            if len(c) and "model_margin" in c:
                cards[m.group(1)] = c
    hashes, n_rows, n_bandb = [], 0, {"spread": 0, "total": 0}
    seen = set()
    for commit, d in pulls(root):
        key = H(d.to_csv(index=False))
        if key in seen:
            continue
        seen.add(key)
        for day, c in cards.items():
            l = d[d["date"] == day]
            if not len(l):
                continue
            f = c.assign(final_margin=c["model_margin"], final_total=c["model_total"])
            p = run_day.plays(f, l.drop(columns=["date"]))
            v1 = p[[x for x in p.columns if "_bandb" not in x]]
            hashes.append(H(v1.drop(columns=["book_lines"]).to_csv(index=False)) + H(json.dumps(
                v1["book_lines"].tolist(), default=str, sort_keys=True)))
            n_rows += len(p)
            for mk in n_bandb:
                if f"{mk}_bandb" in p:
                    n_bandb[mk] += int(p[f"{mk}_bandb"].fillna(False).astype(bool).sum())
    res["card"] = {"pulls x dates": len(hashes), "rows": n_rows, "hash": H("".join(hashes)),
                   "band B flags (not part of the hash)": n_bandb}

    # log
    st = tracker.status()
    for mk in st:
        st[mk]["cap"].pop("refreshed_at", None)
    v1log = tracker.load().drop(columns=["bet_type"], errors="ignore")    # the new empty tag column is not v1 output
    res["log"] = {"load (without bet_type)": H(v1log.to_csv(index=False)), "rows": len(v1log),
                  "status": H(json.dumps(st, sort_keys=True, default=str)), "tripwires": H(json.dumps(tracker.tripwires(), sort_keys=True, default=str)),
                  "recent": H(json.dumps(tracker.recent(), sort_keys=True, default=str))}

    # record pages
    strip = lambda h: re.sub(r"Updated [^<]*ET", "Updated", re.sub(r"<section class='panel'><div class='panel-h'><h2>Band B.*?</section>", "", h, flags=re.S))
    rp, rv = record_page.build(), record_page.build_verify()
    res["record"] = {"record.html": H(strip(rp)), "verify.html": H(re.sub(r"\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}[^<]*", "", strip(rv))),
                     "band B section shown": "<h2>Band B" in rp}

    # discord payloads for v1 rows
    a = clv_primary.attach(tracker.load())
    res["discord"] = {"logged": H(json.dumps([record._logged(r) for _, r in a.iterrows()], sort_keys=True, default=str)),
                      "settled": H(json.dumps([record._settled(r) for _, r in a[a["status"] == "settled"].iterrows()], sort_keys=True, default=str)),
                      "rows": len(a)}
    if hasattr(tracker, "BAND_B"):
        bb = tracker.load(tracker.BAND_B)
        if len(bb):
            bb = clv_primary.attach(bb)
            res["discord"]["band B titles"] = [record._logged(r)["embeds"][0]["title"] for _, r in bb.iterrows()] + \
                [record._settled(r)["embeds"][0]["title"] for _, r in bb[bb["status"] == "settled"].iterrows()]

    # weekly chart
    through = pd.Timestamp("2026-11-08")
    od = os.path.join(tmp, "weekly")
    st = record_chart.write(through, out=od)
    v1s = {k: v for k, v in st.items() if k not in ("series", "weekly", "bandb", "through")}
    res["chart"] = {"v1 stats": H(json.dumps(v1s, sort_keys=True, default=str)),
                    "v1 series": H(json.dumps({k: list(map(float, v)) for k, v in st["series"].items()})),
                    "caption": H(open(os.path.join(od, "2026-11-08-caption.txt")).read()),
                    "clv.png": H(open(os.path.join(od, "2026-11-08-clv.png"), "rb").read()),
                    "units.png": H(open(os.path.join(od, "2026-11-08-units.png"), "rb").read()),
                    "band B tile": bool(st.get("bandb"))}
    json.dump(res, open(out, "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


def compare(a: str, b: str) -> None:
    A, B = json.load(open(a)), json.load(open(b))
    for sec in A:
        for k, v in A[sec].items():
            w = B.get(sec, {}).get(k)
            print(f"{sec:8s} {k:40s} {'same' if v == w else 'DIFFERENT'}" + ("" if v == w else f"   {v!s:.40} | {w!s:.40}"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root")
    ap.add_argument("--bets")
    ap.add_argument("--out")
    ap.add_argument("--compare", nargs=2)
    x = ap.parse_args()
    compare(*x.compare) if x.compare else emit(x.root, x.bets, x.out)
