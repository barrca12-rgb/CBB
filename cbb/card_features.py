"""Runs the card exactly as `python -m cbb.run_day` does, and also saves each built day's stage-2 inputs to
reports/features_<date>.csv for the ridge-1,000 shadow (cbb/shadow_r1000.py), and every book's moneyline as the card
pulled it to lines/ml/ (research/moneyline/PLAN.md: how long a mispriced moneyline stays up; no extra credits, the
card's pull already carries them). Nothing the card computes, picks, logs or posts changes: projection.apply_saved
and run_day.plays are wrapped only to copy what they see, and a failure to save is printed and ignored. Used by
.github/workflows/update.yml in place of `python -m cbb.run_day` (same arguments).

    python -m cbb.card_features --auto | --date YYYY-MM-DD
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from . import projection, run_day

KEYS = ["game_id", "date", "start", "home", "away", "home_id", "away_id", "neutral", "state", "home_score", "away_score"]
_apply = projection.apply_saved


def _apply_and_save(b: pd.DataFrame) -> pd.DataFrame:
    f = _apply(b)
    try:
        cols = [c for c in KEYS if c in f] + [c for c in dict.fromkeys(projection.MARGIN_FEATURES + projection.TOTAL_FEATURES) if c in f] \
            + ["final_margin", "final_total"]
        day = pd.Timestamp(f["date"].iloc[0])
        os.makedirs(run_day.REPORTS, exist_ok=True)
        f[cols].to_csv(os.path.join(run_day.REPORTS, f"features_{day:%Y-%m-%d}.csv"), index=False)
    except Exception as e:   # never affects the card
        print(f"Saving stage-2 inputs failed ({e}); continuing.")
    return f


projection.apply_saved = _apply_and_save

ML_DIR = os.path.join(os.path.dirname(__file__), "..", "lines", "ml")
ML_COLS = ["observed_at", "pulled_at", "date", "start", "home_id", "away_id", "book", "home_ml", "away_ml", "status"]
_plays = run_day.plays


def log_moneylines(lines: pd.DataFrame, now: pd.Timestamp | None = None) -> int:
    """Append each (game, book) moneyline that is new or changed since its last logged row to
    lines/ml/<UTC date>.csv (change-only, like lines/moves.csv). A book quoting the game with no moneyline, or with
    one side only, is logged with status "missing" (never a price); status "ok" otherwise. Returns rows written."""
    if lines is None or not len(lines):
        return 0
    now = now or pd.Timestamp.now(tz="UTC")
    cur = lines.copy()
    for c in ML_COLS:
        if c not in cur:
            cur[c] = np.nan
    # this run's pull carries no pulled_at (odds.pull stamps the saved copy); carried rows keep their own
    from . import odds
    this_pull = getattr(odds.pull, "pulled_at", None) or now.isoformat(timespec="seconds")
    cur["pulled_at"] = cur["pulled_at"].where(cur["pulled_at"].notna(), this_pull)
    cur["date"] = cur["date"].where(cur["date"].notna(), pd.to_datetime(cur["start"], utc=True, errors="coerce")
                                    .dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d"))
    ok = cur["home_ml"].notna() & cur["away_ml"].notna() & (cur["home_ml"].abs() >= 100) & (cur["away_ml"].abs() >= 100)
    cur["status"] = np.where(ok, "ok", "missing")
    cur.loc[~ok, ["home_ml", "away_ml"]] = np.nan
    cur["observed_at"] = now.isoformat(timespec="seconds")
    cur = cur[ML_COLS]
    os.makedirs(ML_DIR, exist_ok=True)
    last_path = os.path.join(ML_DIR, "latest.csv")
    key = ["home_id", "away_id", "book"]
    if os.path.exists(last_path):
        old = pd.read_csv(last_path).reindex(columns=ML_COLS)
        old["status"] = old["status"].fillna("ok")
        last = old.drop_duplicates(key, keep="last").set_index(key)[["home_ml", "away_ml", "status"]]
        prev = last.reindex(pd.MultiIndex.from_frame(cur[key]))
        same = ((prev["home_ml"].fillna(0).to_numpy() == cur["home_ml"].fillna(0).to_numpy())
                & (prev["away_ml"].fillna(0).to_numpy() == cur["away_ml"].fillna(0).to_numpy())
                & (prev["status"].to_numpy() == cur["status"].to_numpy()))
        new = cur[~same]
        keep = pd.concat([old, cur]).drop_duplicates(key, keep="last")
    else:
        new, keep = cur, cur
    if len(new):
        day = os.path.join(ML_DIR, f"{now:%Y-%m-%d}.csv")
        if os.path.exists(day):
            old_cols = list(pd.read_csv(day, nrows=0).columns)
            if old_cols != ML_COLS:      # the first day's file predates the status column: rewrite it with one
                pd.read_csv(day).reindex(columns=ML_COLS).fillna({"status": "ok"}).to_csv(day, index=False)
        new.to_csv(day, mode="a", header=not os.path.exists(day), index=False)
    keep.to_csv(last_path, index=False)
    return len(new)


OPENER_FAV = os.path.join(ML_DIR, "opener_fav.csv")
OPENER_COLS = ["run_at", "date", "game_id", "start", "book", "team_id", "opp_id", "price", "opp_price", "p_model", "ev",
               "model_margin"]
OPENER_EV, OPENER_SIGMA = 0.05, 11.0     # research/moneyline/opener_fav/PLAN.md: the Oct 26 rule, favorites only


def _priced_keys() -> set:
    """(home_id, away_id, book) already holding a priced moneyline in the log (before this run)."""
    path = os.path.join(ML_DIR, "latest.csv")
    if not os.path.exists(path):
        return set()
    old = pd.read_csv(path)
    if "status" in old:
        old = old[old["status"].fillna("ok") == "ok"]
    return set(zip(old["home_id"].astype(int), old["away_id"].astype(int), old["book"]))


def log_opener_favs(f: pd.DataFrame, lines: pd.DataFrame, before: set, now: pd.Timestamp | None = None) -> int:
    """Each book's FIRST priced moneyline on a game this run: if the favorite's EV against the model's win
    probability Phi(margin / 11) is +5% or more, append it to lines/ml/opener_fav.csv. Returns rows written."""
    from scipy.stats import norm
    if lines is None or not len(lines) or "home_ml" not in lines or not before:
        return 0       # no log yet: everything would look new, and nothing is a true opener
    now = now or pd.Timestamp.now(tz="UTC")
    rows = []
    proj = {(int(r.home_id), int(r.away_id)): r for r in f.itertuples()}
    for r in lines.itertuples():
        h, a = int(r.home_id), int(r.away_id)
        if (h, a, r.book) in before or pd.isna(r.home_ml) or pd.isna(r.away_ml) or abs(r.home_ml) < 100 or abs(r.away_ml) < 100:
            continue
        g, sign = (proj[(h, a)], 1) if (h, a) in proj else (proj.get((a, h)), -1)
        if g is None or pd.isna(g.final_margin):
            continue
        m_home = sign * float(g.final_margin)          # the model's margin for the feed's home team
        for team, opp, price, opp_price, m in ((h, a, r.home_ml, r.away_ml, m_home), (a, h, r.away_ml, r.home_ml, -m_home)):
            if price >= 0:
                continue                                 # favorites only
            p = float(norm.cdf(m / OPENER_SIGMA))
            ev = p * (100 / -price) - (1 - p)
            if ev >= OPENER_EV:
                rows.append({"run_at": now.isoformat(timespec="seconds"), "date": str(g.date)[:10], "game_id": g.game_id,
                             "start": getattr(r, "start", None), "book": r.book, "team_id": team, "opp_id": opp, "price": price,
                             "opp_price": opp_price, "p_model": round(p, 4), "ev": round(ev, 4), "model_margin": round(m, 2)})
    if rows:
        os.makedirs(ML_DIR, exist_ok=True)
        pd.DataFrame(rows)[OPENER_COLS].to_csv(OPENER_FAV, mode="a", header=not os.path.exists(OPENER_FAV), index=False)
    return len(rows)


MISSED = os.path.join(os.path.dirname(__file__), "..", "lines", "missed_plays.csv")
MISSED_ALERTED = os.path.join(os.path.dirname(__file__), "..", "lines", "missed_alerted.json")
MISSED_COLS = ["seen_at", "date", "game_id", "game", "market", "side", "book", "line", "price", "edge", "ev", "card_verdict",
               "card_book", "card_line", "card_edge"]


def missed_plays(card: pd.DataFrame, lines: pd.DataFrame) -> pd.DataFrame:
    """Safety net, independent of run_day's own selection (Chad, Oct 31: "make sure watch list plays don't get missed
    ever again"). Every book's quote is re-checked against the live rule: an edge at the cutoff or more (and at most
    MAX_EDGE), +2% EV at that book's price, a real price, and not off-market. A qualifying quote on a game and
    market the card neither plays (BET) nor already has logged is a miss."""
    out = []
    if card is None or not len(card) or lines is None or not len(lines):
        return pd.DataFrame(columns=MISSED_COLS)
    for _, g in card.iterrows():
        h, a = int(g["home_id"]), int(g["away_id"])
        l = lines[(lines["home_id"] == h) & (lines["away_id"] == a)]
        flip = lines[(lines["home_id"] == a) & (lines["away_id"] == h)]
        if not len(l) and len(flip):                    # the feed lists the teams the other way round
            l = flip.rename(columns={"home_spread_odds": "away_spread_odds", "away_spread_odds": "home_spread_odds"}).assign(
                home_spread=-flip["home_spread"])
        if not len(l):
            continue
        for mk, col, thr in (("spread", "home_spread", run_day.SPREAD_CALLS[0][0]), ("total", "total", run_day.TOTAL_CALLS[0][0])):
            if g.get(f"{mk}_verdict") == "BET" or (isinstance(g.get(f"{mk}_logged_pick"), str) and g.get(f"{mk}_logged_pick")):
                continue
            off = set(run_day._off_market(l, col).index)
            m = g["model_margin"] if mk == "spread" else g["model_total"]
            for i, x in l.iterrows():
                if i in off or pd.isna(x.get(col)) or pd.isna(m):
                    continue
                sides = (("home", m + x[col], "home_spread_odds"), ("away", -(m + x[col]), "away_spread_odds")) if mk == "spread" \
                    else (("over", m - x[col], "over_odds"), ("under", x[col] - m, "under_odds"))
                for side, e, oc in sides:
                    price = x.get(oc)
                    if pd.isna(price) or e < thr or e > run_day.MAX_EDGE[mk]:
                        continue
                    v = run_day.ev(run_day.win_prob(mk, e), price)
                    if v >= run_day.MIN_EV:
                        line = (x[col] if side == "home" else -x[col]) if mk == "spread" else x[col]
                        out.append({"date": str(g.get("date", ""))[:10] if "date" in g else "", "game_id": g["game_id"],
                                    "game": f"{g['away']} at {g['home']}", "market": mk, "side": side, "book": x.get("book"),
                                    "line": line, "price": price, "edge": round(e, 2), "ev": round(v, 4),
                                    "card_verdict": g.get(f"{mk}_verdict"), "card_book": g.get(f"{mk}_book"),
                                    "card_line": g.get(f"{mk}_line"), "card_edge": round(float(g.get(f"{mk}_edge") or 0), 2)})
    return pd.DataFrame(out, columns=[c for c in MISSED_COLS if c != "seen_at"])


def report_missed(miss: pd.DataFrame, day: str, now: pd.Timestamp | None = None) -> int:
    """Append misses to lines/missed_plays.csv and send one phone alert per game, market, book and number."""
    import json
    from . import notify
    if miss is None or not len(miss):
        return 0
    now = now or pd.Timestamp.now(tz="UTC")
    miss = miss.assign(seen_at=now.isoformat(timespec="seconds"), date=miss["date"].replace("", day))[MISSED_COLS]
    miss.to_csv(MISSED, mode="a", header=not os.path.exists(MISSED), index=False)
    done = set(json.load(open(MISSED_ALERTED))) if os.path.exists(MISSED_ALERTED) else set()
    sent = 0
    for _, r in miss.iterrows():
        k = f"{r['date']}|{r['game_id']}|{r['market']}|{r['book']}|{r['line']}"
        print(f"MISSED PLAY: {r['game']} {r['market']} {r['side']} {r['line']} at {r['book']} ({r['price']}), edge {r['edge']}, "
              f"EV {100 * r['ev']:+.1f}%; card had {r['card_verdict']} at {r['card_book']} {r['card_line']}")
        if k in done:
            continue
        if notify.message(f"CBB: a qualifying quote was not played ({r['game']})",
                          f"{r['side']} {r['line']} at {r['book']} ({int(r['price']):+d}): edge {r['edge']}, EV {100 * r['ev']:+.1f}%. "
                          f"The card shows {r['card_verdict']} at {r['card_book']}. This is a selection bug; check before betting."):
            done.add(k)
            sent += 1
    json.dump(sorted(done), open(MISSED_ALERTED, "w"))
    return sent


def _plays_and_log(f: pd.DataFrame, lines: pd.DataFrame, live: bool = True) -> pd.DataFrame:
    if live:
        try:
            before = _priced_keys()
            log_moneylines(lines)
            log_opener_favs(f, lines, before)
        except Exception as e:   # never affects the card
            print(f"Moneyline log failed ({e}); continuing.")
    card = _plays(f, lines, live)
    if live:
        try:
            day = str(f["date"].iloc[0])[:10] if len(f) and "date" in f else ""
            report_missed(missed_plays(card.assign(date=day), lines), day)
        except Exception as e:   # never affects the card
            print(f"Missed-play check failed ({e}); continuing.")
    return card


if __name__ == "__main__":
    run_day.plays = _plays_and_log      # only the card run logs moneylines (not tests or other importers)
    run_day.main()
