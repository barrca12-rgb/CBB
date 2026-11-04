"""Morning shadow (research/morning_shadow/PLAN.md, pre-registered Nov 4, 2026). Collection only: nothing here logs a
play, alerts, posts, stakes or changes what the card shows. The live strategy is unchanged and the complete-ratings
rule stays off.

On game day D, the shadow takes ONE decision per game and market: what the unchanged live card decides at the first
card run in the morning window whose inputs include every game played before D. The card already re-prices every game
on every run; the shadow copies that run's verdict, number, book, price and the quote's source time into
bets/shadow_morning.csv, with the readiness of each input and the reason for every no-bet.

Readiness (all four, checked on the card run itself):
  barttorvik   the card used Barttorvik's file dated D-1 (a file dated X includes X's games; audit/TIMING_AUDIT.md)
  kenpom       KenPom's FanMatch for D is published and used (it is built on KenPom's ratings through D-1)
  box_scores   the hoopR schedule lists every D-1 game as final, postponed or cancelled, and every final one is in
               the box scores the stage-1 ratings were fit on
  injuries     this run's ESPN injury fetch succeeded

Window and decision, per game (times ET):
  - runs before 09:00 on D: nothing;
  - from 09:00 until the game's deadline, min(12:00, tip - 30 min): the first run with all four ready decides
    (decision_kind "ready");
  - no run ready by the deadline: the first run at or after it, if before tip, decides on what it has
    (decision_kind "fallback", the missing inputs listed): the timing case, never a silent skip;
  - no run decides before tip (tip earlier than the window, or no card run): "no decision" (counted as no bet);
  - a hard failure on the decision run (no model number for the game, or no named-book quote): no bet, with the
    reason (a hard failure is a failed or empty source, not a late update).
Stake: the live staking rule at the decision run (tracker.status multiplier for the market), as tracker.log uses.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
LOG = os.path.join(ROOT, "bets", "shadow_morning.csv")
OPEN_HOUR, CUTOFF_HOUR, BEFORE_TIP = 9, 12, pd.Timedelta(minutes=30)
COLS = ["date", "game_id", "market", "home_id", "away_id", "home", "away", "start", "decided_at", "decision_kind",
        "ready_barttorvik", "ready_kenpom", "ready_box_scores", "ready_injuries", "missing", "barttorvik_file",
        "kenpom_source", "box_scores_last_final", "verdict", "gate", "decision", "reason", "side", "pick", "line",
        "odds", "book", "edge", "ev", "model", "stake", "quote_source", "quote_source_updated_at", "quote_age_s",
        "lines_pulled_at", "code_version", "run_id"]
STATE = {"installed": False}


def _et(t) -> pd.Timestamp:
    t = pd.Timestamp(t)
    return (t.tz_localize("UTC") if t.tzinfo is None else t).tz_convert("America/New_York")


def window(day: str, start) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp | None]:
    """(window opens, decision deadline, tip) in UTC for a game on ET date `day`."""
    d = pd.Timestamp(day)
    op = (d + pd.Timedelta(hours=OPEN_HOUR)).tz_localize("America/New_York").tz_convert("UTC")
    cut = (d + pd.Timedelta(hours=CUTOFF_HOUR)).tz_localize("America/New_York").tz_convert("UTC")
    tip = pd.to_datetime(start, utc=True, errors="coerce")
    if pd.isna(tip):
        return op, cut, None
    return op, min(cut, tip - BEFORE_TIP), tip


def box_ready(day: str, schedule: pd.DataFrame | None, hist: pd.DataFrame | None) -> tuple[bool, str]:
    """Every D-1 Division I game final, postponed or cancelled in the hoopR schedule, and every final one in `hist`
    (data.season_games: the games whose box scores the stage-1 ratings are fit on). Returns (ready, last final date)."""
    last = ""
    have = set()
    if hist is not None and len(hist):
        h = hist.dropna(subset=["home_pts"]) if "home_pts" in hist else hist
        if len(h):
            last = str(pd.to_datetime(h["date"]).max().date())
            have = set(h["game_id"].astype(int))
    if schedule is None or not len(schedule):
        return False, last
    prev = (pd.Timestamp(day) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    s = schedule.assign(_d=pd.to_datetime(schedule["date"], utc=True).dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d"))
    s = s[s["_d"] == prev]
    if {"home_conference_id", "away_conference_id"} <= set(s.columns):   # Division I: both teams with a conference
        s = s[s["home_conference_id"].notna() & s["away_conference_id"].notna()]
    name = s["status_type_name"].astype(str) if "status_type_name" in s else pd.Series("", index=s.index)
    off = name.isin(["STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_FORFEIT"])
    fin = s["status_type_completed"].fillna(False).astype(bool) if "status_type_completed" in s else pd.Series(False, index=s.index)
    if not (fin | off).all():
        return False, last
    return bool(all(int(i) in have for i in s.loc[fin & ~off, "game_id"])), last


def readiness(day: str) -> dict:
    """The four readiness checks for card day `day`, read from what this run used."""
    from . import barttorvik, data, freshness, kenpom
    from .run_day import season_of
    prev = (pd.Timestamp(day) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    bt = barttorvik.LAST.get("file")
    fm = os.path.join(kenpom.CACHE, f"endpoint-fanmatch_d-{day}.json")
    kp = False
    try:
        kp = os.path.exists(fm) and os.path.getsize(fm) > 2
    except OSError:
        pass
    season = season_of(pd.Timestamp(day))
    try:
        sch = data.fetch("schedule", season)
        hist = data.season_games(season)[0]
    except Exception:
        sch, hist = None, None
    box, last = box_ready(day, sch, hist)
    inj = bool((freshness.SEEN.get("injuries") or {}).get("ok"))
    r = {"ready_barttorvik": bt == prev, "ready_kenpom": bool(kp), "ready_box_scores": box, "ready_injuries": inj,
         "barttorvik_file": bt or "none", "kenpom_source": "FanMatch " + day if kp else "current ratings (FanMatch not out)",
         "box_scores_last_final": last}
    r["missing"] = "; ".join(k[6:] for k in ("ready_barttorvik", "ready_kenpom", "ready_box_scores", "ready_injuries") if not r[k])
    return r


def _logged() -> set:
    if not os.path.exists(LOG):
        return set()
    t = pd.read_csv(LOG, usecols=["date", "game_id", "market"], dtype=str)
    return set(zip(t["date"], t["game_id"], t["market"]))


def _row(g, mk: str, day: str, now: pd.Timestamp, kind: str, ready: dict, stakes: dict, pulled, pulled_at) -> dict:
    from . import quotelog
    r = {"date": day, "game_id": int(g["game_id"]), "market": mk, "home_id": int(g["home_id"]), "away_id": int(g["away_id"]),
         "home": g.get("home"), "away": g.get("away"), "start": g.get("start"), "decided_at": now.isoformat(timespec="seconds"),
         "decision_kind": kind, **ready, "code_version": os.environ.get("GITHUB_SHA", ""), "run_id": os.environ.get("GITHUB_RUN_ID", "")}
    if kind == "no decision":
        return dict(r, decision="NO BET", reason="no card run decided before tip", missing=ready.get("missing", ""))
    v = g.get(f"{mk}_verdict")
    side = g.get("spread_side") if mk == "spread" else (str(g.get("total_pick")).lower() if isinstance(g.get("total_pick"), str) else None)
    model = g.get("model_margin") if mk == "spread" else g.get("model_total")
    book = g.get(f"{mk}_book") if isinstance(g.get(f"{mk}_book"), str) else None
    r.update(verdict=v, gate=g.get(f"{mk}_gate") if isinstance(g.get(f"{mk}_gate"), str) else "", side=side,
             pick=(f"{g.get(mk + '_pick')} {g.get(mk + '_line'):+g}" if mk == "spread" else f"{g.get('total_pick')} {g.get('total_line'):g}")
             if pd.notna(g.get(f"{mk}_line")) else "",
             line=g.get(f"{mk}_line"), odds=g.get(f"{mk}_odds"), book=book, edge=g.get(f"{mk}_edge"), ev=g.get(f"{mk}_ev"),
             model=model, lines_pulled_at=pulled_at or "")
    if model is None or pd.isna(model):
        return dict(r, decision="NO BET", reason="hard failure: no model number for the game")
    if book is None or pd.isna(g.get(f"{mk}_line")) or pd.isna(g.get(f"{mk}_odds")):
        return dict(r, decision="NO BET", reason="hard failure: no named-book quote with a price")
    if side is not None:
        lo, hi = sorted((int(g["home_id"]), int(g["away_id"])))
        q = quotelog.generating_quote(pulled, f"{day}|{lo}|{hi}", book, mk, side)
        r.update(quote_source=q.get("source", ""), quote_source_updated_at=q.get("source_updated_at", ""),
                 quote_age_s=q.get("quote_age_s", ""))
    if v == "BET":
        return dict(r, decision="BET", reason="", stake=stakes.get(mk, 1.0))
    return dict(r, decision="NO BET", reason=f"card verdict {v}" + (f" ({r['gate']})" if r["gate"] else ""))


def collect(card: pd.DataFrame, day: str, now: pd.Timestamp | None = None, ready: dict | None = None,
            stakes: dict | None = None, pulled=None, pulled_at=None) -> int:
    """Write this run's morning decisions for card day `day` (today, ET). Returns rows written."""
    now = now or pd.Timestamp.now(tz="UTC")
    if card is None or not len(card):
        return 0
    have = _logged()
    todo = [g for _, g in card.iterrows() if any((day, str(int(g["game_id"])), mk) not in have for mk in ("spread", "total"))]
    if not todo:
        return 0
    if ready is None:
        ready = readiness(day)
    if stakes is None:
        from . import tracker
        st = tracker.status()
        stakes = {mk: st[mk]["multiplier"] for mk in st}
    all_ready = not ready["missing"]
    rows = []
    for g in todo:
        op, dl, tip = window(day, g.get("start"))
        if tip is not None and now >= tip:
            kind = "no decision"
        elif now < op:
            continue
        elif all_ready:
            kind = "ready"
        elif now >= dl:
            kind = "fallback"
        else:
            continue
        for mk in ("spread", "total"):
            if (day, str(int(g["game_id"])), mk) in have:
                continue
            rows.append(_row(g, mk, day, now, kind, ready, stakes, pulled, pulled_at))
    if rows:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        pd.DataFrame(rows).reindex(columns=COLS).to_csv(LOG, mode="a", header=not os.path.exists(LOG), index=False)
    return len(rows)


def install() -> None:
    """Wrap run_day.plays (card run only) so each live build of today's card feeds collect(). Pass-through."""
    if STATE["installed"]:
        return
    from . import odds, run_day
    p0 = run_day.plays

    def plays(f, lines, live=True, *a, **k):
        card = p0(f, lines, live, *a, **k)
        if live:
            try:
                day = str(f["date"].iloc[0])[:10] if len(f) and "date" in f else ""
                if day == f"{run_day.today_et():%Y-%m-%d}":
                    n = collect(card, day, pulled=getattr(odds.pull, "observations", None),
                                pulled_at=getattr(odds.pull, "pulled_at", None))
                    if n:
                        print(f"Morning shadow: {n} decision row(s) for {day} (research only; nothing logged or alerted).")
            except Exception as e:   # never affects the card
                print(f"Morning shadow failed ({e}); continuing.")
        return card
    run_day.plays = plays
    STATE["installed"] = True
