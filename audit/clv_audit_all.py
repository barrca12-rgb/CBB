"""Every play's CLV recomputed independently and compared with what the site shows (Chad, Nov 3: "did you verify ALL
CLV?").

Standard library only for the recomputation: no forward_eval, clv_primary, tracker or pandas function is used to
build a close, so a fault in the shared code cannot hide here. Rules as written in FORWARD_TEST_PROTOCOL.md section 7
(v2.5):
- **Cutoff:** the start carried by the latest observation made before its own start. A verified actual tip
  (lines/tipoffs.csv, quality "jump ball") earlier than that becomes the cutoff.
- **Window:** for each frozen book, the last available quote with a number, observed in the 15 minutes before the
  cutoff and before its own start, with a feed age of -60 to 300 s. The close is the median across books.
- **Spread sides:** read from the bet's home team. The feed's home team for each event is found from
  lines/moves.csv, where spreads are recorded by team id.

    python -m audit.clv_audit_all          # -> audit/out/clv_audit_all.txt
"""
from __future__ import annotations

import csv
import gzip
import os
import statistics
from datetime import datetime, timedelta

ROOT = os.path.join(os.path.dirname(__file__), "..")
LINES = os.path.join(ROOT, "lines")
BOOKS = {"DraftKings", "FanDuel", "BetMGM", "Caesars", "Fanatics", "bet365", "theScore Bet"}


def ts(x):
    return datetime.fromisoformat(x.replace("Z", "+00:00")) if x else None


def load_obs() -> dict:
    by = {}
    for d in ("obs", "obs_targeted"):
        p = os.path.join(LINES, d)
        for f in sorted(os.listdir(p)) if os.path.isdir(p) else []:
            if not f.endswith((".csv", ".csv.gz")):
                continue
            op = gzip.open if f.endswith(".gz") else open
            with op(os.path.join(p, f), "rt", newline="") as fh:
                for r in csv.DictReader(fh):
                    r["_t"], r["_st"], r["_upd"] = ts(r["observed_at"]), ts(r["start"]), ts(r.get("source_updated_at"))
                    by.setdefault(r["game_key"], []).append(r)
    return by


def load_moves() -> dict:
    """(game_key, book) -> [(time, lower-id team's spread, lo_id, hi_id)], time-ordered."""
    out = {}
    p = os.path.join(LINES, "moves.csv")
    with open(p, newline="") as fh:
        for r in csv.DictReader(fh):
            if not r.get("spread") or not r.get("pulled_at"):
                continue
            out.setdefault((r["game_key"], r["book"]), []).append((ts(r["pulled_at"]), float(r["spread"]),
                                                                   int(float(r["lo_id"])), int(float(r["hi_id"]))))
    for v in out.values():
        v.sort(key=lambda x: x[0])
    return out


def feed_home(rows: list, moves: dict) -> dict:
    """event_id -> team id of the feed's "home" side, by majority of quotes matched to the line log."""
    votes = {}
    for r in rows:
        if r["market"] != "spread" or r["side"] != "home" or not r["line"] or float(r["line"]) == 0:
            continue
        hist = [m for m in moves.get((r["game_key"], r["book"]), []) if m[0] <= r["_t"] and m[1] != 0]
        if not hist:
            continue
        _, lo_sp, lo, hi = hist[-1]
        v = 1 if float(r["line"]) == lo_sp else -1 if float(r["line"]) == -lo_sp else 0
        if v:
            votes.setdefault(r["event_id"], []).append(lo if v > 0 else hi)
    return {ev: max(set(ids), key=ids.count) for ev, ids in votes.items()
            if ids.count(max(set(ids), key=ids.count)) * 2 != len(ids) or len(set(ids)) == 1}


def actual_tips() -> dict:
    out = {}
    p = os.path.join(LINES, "tipoffs.csv")
    if os.path.exists(p):
        with open(p, newline="") as fh:
            for r in csv.DictReader(fh):
                if r.get("actual_tip") and r.get("quality") == "jump ball":
                    out[int(float(r["game_id"]))] = ts(r["actual_tip"])
    return out


def recompute(bet: dict, rows: list, fh_map: dict, tip) -> dict:
    pre = sorted((r for r in rows if r["_t"] and r["_st"] and r["_t"] < r["_st"]), key=lambda r: r["_t"])
    cutoff = pre[-1]["_st"] if pre else None
    if tip is not None and (cutoff is None or tip < cutoff):
        cutoff = tip
    if cutoff is None:
        return {"close": None, "clv": None, "books": 0}
    home_id, away_id = int(float(bet["home_id"])), int(float(bet["away_id"]))
    per = {}
    for r in rows:
        if r["market"] != bet["market"] or r["book"] not in BOOKS or r["status"] != "available" or not r["line"]:
            continue
        if not (cutoff - timedelta(minutes=15) <= r["_t"] < cutoff) or r["_t"] >= r["_st"] or r["_upd"] is None:
            continue
        if not -60 <= (r["_t"] - r["_upd"]).total_seconds() <= 300:
            continue
        num = float(r["line"])
        side = r["side"]
        if bet["market"] == "spread" and fh_map.get(r["event_id"]) == away_id:
            side = {"home": "away", "away": "home"}[side]           # the feed lists the bet's away team as home
        home = -num if (bet["market"] == "spread" and side == "away") else num
        k = (r["_t"], r["_upd"])
        if r["book"] not in per or k > per[r["book"]][0]:
            per[r["book"]] = (k, home)
    if not per:
        return {"close": None, "clv": None, "books": 0}
    hc = statistics.median(v for _, v in per.values())
    close = -hc if (bet["market"] == "spread" and bet["side"] == "away") else hc
    line = float(bet["line"])
    clv = (line - close) if bet["market"] == "spread" or bet["side"] == "under" else (close - line)
    return {"close": close, "clv": clv, "books": len(per)}


def main() -> None:
    import pandas as pd                                    # only to read the bet log and the site's own numbers
    from cbb import clv_primary, tracker
    bets = tracker.load("all")
    bets = bets[bets["status"] != "void"]
    shown = clv_primary.primary(bets).set_index("bet_id")
    obs, moves, tips = load_obs(), load_moves(), actual_tips()
    fh_cache = {}
    rows_out, L = [], []
    for _, b in bets.iterrows():
        key = f"{b['date']}|{min(int(b['home_id']), int(b['away_id']))}|{max(int(b['home_id']), int(b['away_id']))}"
        rows = obs.get(key, [])
        if key not in fh_cache:
            fh_cache[key] = feed_home(rows, moves)
        mine = recompute(b.to_dict(), rows, fh_cache[key], tips.get(int(b["game_id"])))
        s = shown.loc[b["bet_id"]]
        sc, sv = s["close_primary"], s["clv_primary"]
        both_none = mine["close"] is None and pd.isna(sc)
        same = both_none or (mine["close"] is not None and pd.notna(sc) and abs(mine["close"] - sc) < 1e-9
                             and abs(mine["clv"] - sv) < 1e-9)
        rows_out.append({"bet_id": b["bet_id"], "pick": b["pick"], "status": b["status"], "type": b.get("bet_type") or "v1",
                         "site_close": sc, "site_clv": sv, "audit_close": mine["close"], "audit_clv": mine["clv"],
                         "books": mine["books"], "match": same})
    r = pd.DataFrame(rows_out)
    have = r[r["audit_close"].notna() | r["site_close"].notna()]
    L.append(f"Every play's CLV recomputed independently (standard library, protocol v2.5) vs the site, "
             f"{pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC")
    L.append(f"  plays (not void): {len(r)}; with a close: {len(have)}; matching to the decimal: {int(have['match'].sum())}; "
             f"mismatches: {int((~have['match']).sum())}; no close yet (games not played or no fresh quotes): "
             f"{len(r) - len(have)}")
    g = r[r["status"] == "settled"]
    gh = g[g["audit_close"].notna() | g["site_close"].notna()]
    L.append(f"  graded plays: {len(g)}; with a close: {len(gh)}; matching: {int(gh['match'].sum())}; "
             f"graded without a close: {len(g) - len(gh)}")
    bad = have[~have["match"]]
    if len(bad):
        L.append("\nMismatches:")
        L.append(bad.to_string(index=False))
    nc = g[g["audit_close"].isna() & g["site_close"].isna()]
    if len(nc):
        L.append("\nGraded plays without a close (shown as 'no close' on the site, excluded from CLV averages):")
        L.append(nc[["bet_id", "pick", "type"]].to_string(index=False))
    os.makedirs(os.path.join(os.path.dirname(__file__), "out"), exist_ok=True)
    txt = "\n".join(L)
    open(os.path.join(os.path.dirname(__file__), "out", "clv_audit_all.txt"), "w").write(txt + "\n")
    r.to_csv(os.path.join(os.path.dirname(__file__), "out", "clv_audit_all.csv"), index=False)
    print(txt)


if __name__ == "__main__":
    main()
