"""Opening-record metadata for the opener orientation check (protocol item 7): for every ESPN odds record that has an
opening spread (2024-26), the opening record's own favourite flag and opening moneylines. These are stored at the
open, beside the opening spread, so they identify the opening favourite without reference to the close.
(2015-17 openers come from ESPN's "Opening" pseudo-book, whose row carries its own moneylines already.)

    python -m audit.b8_open_meta [--seasons 2024 2025 2026]

Writes audit/out/espn_open_meta_<season>.csv (resumable). Read-only with respect to the model and data/.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from cbb import lines_hist

OUT = os.path.join(os.path.dirname(__file__), "out")
COLS = ["game_id", "book", "open_home_spread", "open_home_fav", "open_away_fav", "open_home_ml", "open_away_ml"]


def _num(x):
    try:
        return float(str(x).replace("+", ""))
    except (TypeError, ValueError):
        return np.nan


def meta(game_id: int) -> list[dict]:
    for attempt in range(4):
        try:
            req = urllib.request.Request(lines_hist.URL.format(game_id), headers={"User-Agent": "cbb-model"})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
            break
        except Exception:
            if attempt == 3:
                return [{"game_id": game_id, "book": "fetch failed"}]
            time.sleep(2 ** attempt)
    rows = []
    for p in d.get("items") or []:
        book = (p.get("provider") or {}).get("name", "")
        if "live" in book.lower():
            continue
        ho, ao = (p.get("homeTeamOdds") or {}).get("open") or {}, (p.get("awayTeamOdds") or {}).get("open") or {}
        if not ho and not ao:
            continue
        rows.append({"game_id": game_id, "book": book,
                     "open_home_spread": _num((ho.get("pointSpread") or {}).get("american")),
                     "open_home_fav": ho.get("favorite"), "open_away_fav": ao.get("favorite"),
                     "open_home_ml": _num((ho.get("moneyLine") or {}).get("american")),
                     "open_away_ml": _num((ao.get("moneyLine") or {}).get("american"))})
    return rows or [{"game_id": game_id, "book": ""}]


def season(s: int, workers: int = 12) -> pd.DataFrame:
    path = os.path.join(OUT, f"espn_open_meta_{s}.csv")
    done = pd.read_csv(path) if os.path.exists(path) else pd.DataFrame(columns=COLS)
    done = done[done["book"] != "fetch failed"]
    l = pd.read_csv(os.path.join(lines_hist.OUT, f"espn_{s}.csv"))
    todo = sorted(set(l.loc[l["open_home_spread"].notna(), "game_id"]) - set(done["game_id"]))
    for i in range(0, len(todo), 500):
        with ThreadPoolExecutor(workers) as ex:
            new = [r for rows in ex.map(meta, todo[i:i + 500]) for r in rows]
        done = pd.concat([done, pd.DataFrame(new, columns=COLS)], ignore_index=True)
        done.sort_values(["game_id", "book"]).to_csv(path, index=False)
        print(f"{s}: {min(i + 500, len(todo))}/{len(todo)}", flush=True)
    return done


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", type=int, nargs="+", default=[2024, 2025, 2026])
    for s in ap.parse_args().seasons:
        season(s)
