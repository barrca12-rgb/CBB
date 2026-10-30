"""Input freshness stamp on every play (Chad's Nov 1 brief, item 1). Reads and displays only: no pick, number, rule,
stake, log or grading changes. The card CSV gains trailing columns; bets/bets.csv is untouched (the stamp for each
logged play goes to the sidecar bets/inputs.csv, keyed by bet id).

Feeds fail quietly (the Oct 29 ESPN reset): a play built on a stale file looks identical to a good one. watch() wraps
the fetchers the projection uses so each records what it actually returned and when; the wrappers pass every result
through unchanged:

  kenpom       KenPom's DataThrough (ratings) or the FanMatch day; dated to the end of that day when KenPom is missing
               a completed game day, else to the fetch
  barttorvik   the time-machine snapshot date actually used (barttorvik.before looks back up to a week), end of that day;
               the fetch time when the live file was used
  injuries     the injury fetch this run; on a failed fetch, the last successful pull in injuries/sources/health.csv
  schedule     the download time of this season's hoopR schedule and box-score files (the older of the two; box
               scores count once the season has completed games)
  referees     the crew fetch this run (totals only; "not posted" is not missing)
  lines        this run's pull time of the play's book (lines/closing.csv pulled_at)

A play is stale when any input it used is older than its cadence (CADENCE, hours), unknown when one has no
timestamp, else fresh. No gate: Chad decides play by play. A feed stale for more than 24 hours sends one phone alert.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
INPUTS = os.path.join(ROOT, "bets", "inputs.csv")
ALERTED = os.path.join(ROOT, "bets", "freshness_alerted.json")
HEALTH = os.path.join(ROOT, "injuries", "sources", "health.csv")
CADENCE = {"kenpom": 36.0, "barttorvik": 36.0, "injuries": 12.0, "schedule": 6.0, "lines": 0.25, "referees": 24.0}
LABEL = {"kenpom": "KenPom", "barttorvik": "Barttorvik", "injuries": "injury report", "schedule": "ESPN schedule/box scores",
         "lines": "line", "referees": "referee crews"}
ALERT_HOURS = 24.0
INPUT_COLS = ["bet_id", "run_at", "state", "stale_inputs", "kenpom_at", "kenpom_data_through", "barttorvik_at",
              "barttorvik_snapshot", "injuries_at", "schedule_at", "referees_at", "line_at", "line_book"]
SEEN: dict = {}          # filled by the wrappers during one card run
LAST: dict = {}          # the latest stamp: {"run_at", "inputs": {...}, "games": DataFrame}


def _now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def _end_of_day_et(d) -> pd.Timestamp:
    return (pd.Timestamp(str(d)[:10]) + pd.Timedelta(hours=23, minutes=59)).tz_localize("America/New_York").tz_convert("UTC")


def watch() -> None:
    """Install the pass-through wrappers once per process."""
    if SEEN.get("_installed"):
        return
    from . import barttorvik, context, data, injuries, kenpom

    g0 = kenpom.get
    def get(endpoint, cache=True, **params):
        out = g0(endpoint, cache=cache, **params)
        try:
            if endpoint == "ratings":
                dt = max((r.get("DataThrough") for r in out if r.get("DataThrough")), default=None)
                SEEN["kenpom"] = {"at": _now(), "data_through": dt}
            elif endpoint == "fanmatch":
                SEEN["kenpom"] = {"at": _now(), "data_through": params.get("d"), "fanmatch": True}
        except Exception:
            pass
        return out
    kenpom.get = get

    s0 = barttorvik.snapshot
    def snapshot(day):
        t = s0(day)
        if t is not None:
            prev = SEEN.get("barttorvik", {}).get("snapshot")
            if prev is None or pd.Timestamp(day) > pd.Timestamp(prev):
                SEEN["barttorvik"] = {"snapshot": pd.Timestamp(day).strftime("%Y-%m-%d")}
        return t
    barttorvik.snapshot = snapshot
    c0 = barttorvik.current
    def current(season):
        t = c0(season)
        if t is not None:
            SEEN["barttorvik_live"] = {"at": _now()}
        return t
    barttorvik.current = current

    f0 = injuries.fetch
    def fetch():
        try:
            out = f0()
        except Exception:
            SEEN["injuries"] = {"ok": False}
            raise
        SEEN["injuries"] = {"ok": True, "at": _now()}
        return out
    injuries.fetch = fetch

    d0 = data.fetch
    def dfetch(kind, season, refresh=False):
        try:
            out = d0(kind, season, refresh)
        except Exception:
            SEEN.setdefault("hoopr", {})[(kind, season)] = {"ok": False}
            raise
        try:
            path = os.path.join(data.CACHE, os.path.basename(data.FILES[kind].format(season=season)))
            SEEN.setdefault("hoopr", {})[(kind, season)] = {"ok": True,
                                                            "at": pd.Timestamp(os.path.getmtime(path), unit="s", tz="UTC")}
        except Exception:
            pass
        return out
    data.fetch = dfetch

    o0 = context.live_officials
    def live_officials(game_ids):
        out = o0(game_ids)
        SEEN["referees"] = {"at": _now(), "games": set(out["game_id"]) if len(out) else set()}
        return out
    context.live_officials = live_officials
    SEEN["_installed"] = True


def _injuries_at():
    s = SEEN.get("injuries")
    if s and s.get("ok"):
        return s["at"]
    if os.path.exists(HEALTH):           # last successful ESPN pull on file
        h = pd.read_csv(HEALTH)
        h = h[(h["source"] == "espn") & h["ok"].astype(str).str.lower().eq("true")]
        if len(h):
            return pd.to_datetime(h["pulled_at"], utc=True).max()
    return None


def _kenpom_at(last_game_day):
    s = SEEN.get("kenpom")
    if not s:
        return None, None
    dt = s.get("data_through")
    if s.get("fanmatch") or last_game_day is None or dt is None:
        return s["at"], dt
    try:   # KenPom missing a completed game day: dated to the end of its own data
        if pd.Timestamp(str(dt)[:10]) < pd.Timestamp(last_game_day) - pd.Timedelta(days=1):
            return _end_of_day_et(dt), dt
    except Exception:
        pass
    return s["at"], dt


def _schedule_at(games_played: bool, season: int):
    h = SEEN.get("hoopr", {})
    sch = h.get(("schedule", season))
    if not sch or not sch.get("ok"):
        return None
    at = sch["at"]
    box = h.get(("team_box", season))
    if games_played:
        if not box or not box.get("ok"):
            return None
        at = min(at, box["at"])
    return at


def stamp(card: pd.DataFrame, day: pd.Timestamp, lines: pd.DataFrame | None, run_at: pd.Timestamp | None = None) -> pd.DataFrame:
    """One row per card game: each input's timestamp and the spread / total play's state. Stored in LAST."""
    run_at = run_at or _now()
    last_game_day, games_played = None, False
    from .run_day import season_of
    season = season_of(day)
    try:
        from . import data
        sch = data.fetch("schedule", season)
        fin = sch[sch["status_type_completed"].astype(bool)] if "status_type_completed" in sch else sch.iloc[0:0]
        if len(fin):
            games_played = True
            last_game_day = pd.to_datetime(fin["date"], utc=True).dt.tz_convert("America/New_York").max().strftime("%Y-%m-%d")
    except Exception:
        pass
    kp_at, kp_dt = _kenpom_at(last_game_day)
    bt = SEEN.get("barttorvik")
    bt_at = _end_of_day_et(bt["snapshot"]) if bt else (SEEN.get("barttorvik_live") or {}).get("at")
    inputs = {"kenpom": kp_at, "barttorvik": bt_at, "injuries": _injuries_at(), "schedule": _schedule_at(games_played, season)}
    refs = SEEN.get("referees")
    pulled = {}
    if lines is not None and len(lines):
        # rows from this run's pull carry no pulled_at (odds.pull stamps the saved copy); rows carried over from an
        # earlier pull keep theirs, so an old line shows its real age
        from . import odds
        this_pull = pd.to_datetime(getattr(odds.pull, "pulled_at", None), utc=True) if getattr(odds.pull, "pulled_at", None) else run_at
        p = pd.to_datetime(lines["pulled_at"], utc=True, errors="coerce") if "pulled_at" in lines else pd.Series(pd.NaT, index=lines.index)
        l = lines.assign(_p=p.fillna(this_pull))
        for (h, a, bk), t in l.groupby(["home_id", "away_id", "book"])["_p"].max().items():
            pulled[(int(h), int(a), bk)] = pulled[(int(a), int(h), bk)] = t
    rows = []
    for _, g in card.iterrows():
        r = {"game_id": g["game_id"], "run_at": run_at, "kenpom_data_through": kp_dt,
             "barttorvik_snapshot": bt["snapshot"] if bt else None, **{f"{k}_at": v for k, v in inputs.items()}}
        gid = g["game_id"]
        r["referees_at"] = refs["at"] if refs and gid in refs.get("games", set()) else None
        for mk in ("spread", "total"):
            bk = g.get(f"{mk}_logged_book") if isinstance(g.get(f"{mk}_logged_book"), str) else g.get(f"{mk}_book")
            la = pulled.get((int(g["home_id"]), int(g["away_id"]), bk)) if isinstance(bk, str) else None
            r[f"{mk}_line_book"], r[f"{mk}_line_at"] = bk if isinstance(bk, str) else None, la
            used = dict(inputs, lines=la)
            if mk == "total" and r["referees_at"] is not None:
                used["referees"] = r["referees_at"]
            st, stale = judge(used, run_at)
            r[f"{mk}_fresh"], r[f"{mk}_stale_inputs"] = st, stale
        rows.append(r)
    fr = pd.DataFrame(rows)
    LAST.clear()
    LAST.update(run_at=run_at, inputs=inputs, games=fr)
    return fr


MISSING = {"barttorvik": "Barttorvik: none this run (filled from KenPom)",
           "lines": "line: no pull time", "injuries": "injury report: no successful pull on file",
           "schedule": "ESPN schedule/box scores: download failed", "kenpom": "KenPom: not fetched"}


def judge(used: dict, run_at: pd.Timestamp) -> tuple[str, str]:
    """('fresh' | 'stale' | 'unknown', 'KenPom 40h; ...'). Stale wins over unknown."""
    stale, unknown = [], []
    for k, t in used.items():
        if t is None or (isinstance(t, float) and np.isnan(t)) or pd.isna(t):
            unknown.append(MISSING.get(k, LABEL[k]))
            continue
        age = (run_at - pd.Timestamp(t)).total_seconds() / 3600
        if age > CADENCE[k]:
            stale.append(f"{LABEL[k]} {age:.0f}h" if age >= 1 else f"{LABEL[k]} {age * 60:.0f}m")
    if stale:
        return "stale", "; ".join(stale)
    if unknown:
        return "unknown", "; ".join(unknown)
    return "fresh", ""


def trail(card: pd.DataFrame, fr: pd.DataFrame) -> pd.DataFrame:
    """The card with the stamp appended as trailing columns (every existing column unchanged, in place)."""
    cols = [c for c in fr.columns if c != "game_id"]
    m = fr.set_index("game_id")
    out = card.copy()
    for c in cols:
        v = out["game_id"].map(m[c])
        out["fresh_" + c if not c.startswith(("spread_", "total_")) else c] = v.map(
            lambda x: x.isoformat(timespec="seconds") if isinstance(x, pd.Timestamp) else x)
    return out


def log_inputs(new_bets: list[dict], fr: pd.DataFrame | None) -> None:
    """Append each newly logged play's stamp to bets/inputs.csv (keyed by bet id)."""
    if not new_bets or fr is None or not len(fr):
        return
    try:
        m = fr.set_index("game_id")
        iso = lambda x: x.isoformat(timespec="seconds") if isinstance(x, pd.Timestamp) else ("" if x is None or (isinstance(x, float) and np.isnan(x)) else x)
        rows = []
        for b in new_bets:
            if b["game_id"] not in m.index:
                continue
            r, mk = m.loc[b["game_id"]], b["market"]
            rows.append({"bet_id": b["bet_id"], "run_at": iso(r["run_at"]), "state": r[f"{mk}_fresh"],
                         "stale_inputs": r[f"{mk}_stale_inputs"], "kenpom_at": iso(r["kenpom_at"]),
                         "kenpom_data_through": iso(r["kenpom_data_through"]), "barttorvik_at": iso(r["barttorvik_at"]),
                         "barttorvik_snapshot": iso(r["barttorvik_snapshot"]), "injuries_at": iso(r["injuries_at"]),
                         "schedule_at": iso(r["schedule_at"]), "referees_at": iso(r["referees_at"]) if mk == "total" else "",
                         "line_at": iso(r[f"{mk}_line_at"]), "line_book": iso(r[f"{mk}_line_book"])})
        if rows:
            pd.DataFrame(rows).reindex(columns=INPUT_COLS).to_csv(INPUTS, mode="a", header=not os.path.exists(INPUTS), index=False)
    except Exception as e:
        print(f"Freshness log failed ({e}); continuing.")


def for_bet(bet_id: str, market: str | None = None, game_id=None) -> dict | None:
    """The stamp of a logged play: this run's if present, else bets/inputs.csv."""
    try:
        if os.path.exists(INPUTS):
            t = pd.read_csv(INPUTS, dtype=str)
            m = t[t["bet_id"] == str(bet_id)]
            if len(m):
                r = m.iloc[0]
                return {"state": r["state"], "stale_inputs": r["stale_inputs"] if isinstance(r["stale_inputs"], str) else ""}
        g = LAST.get("games")
        if g is not None and market and game_id is not None:
            r = g[g["game_id"] == game_id]
            if len(r):
                return {"state": r.iloc[0][f"{market}_fresh"], "stale_inputs": r.iloc[0][f"{market}_stale_inputs"]}
    except Exception as e:
        print(f"Freshness lookup failed ({e}); continuing.")
    return None


def word(f: dict | None) -> str:
    if not f:
        return "Inputs: unknown"
    return f"Inputs: {f['state']}" + (f" ({f['stale_inputs']})" if f.get("stale_inputs") else "")


def alert_stale(run_at: pd.Timestamp | None = None) -> int:
    """One phone alert per feed the first time it is more than ALERT_HOURS stale; re-armed when it is fresh again."""
    run_at = run_at or LAST.get("run_at") or _now()
    inputs = LAST.get("inputs") or {}
    st = json.load(open(ALERTED)) if os.path.exists(ALERTED) else {}
    sent = 0
    for k, t in inputs.items():
        if t is None or pd.isna(t):   # missing this run: age counted from the last run it was there (or first missed)
            last = st.get(f"{k}_last_seen") or st.setdefault(f"{k}_missing_since", run_at.isoformat(timespec="seconds"))
            t = pd.Timestamp(last)
        else:
            st[f"{k}_last_seen"] = pd.Timestamp(t).isoformat(timespec="seconds")
            st.pop(f"{k}_missing_since", None)
        age = (run_at - pd.Timestamp(t)).total_seconds() / 3600
        if age <= ALERT_HOURS:
            st.pop(k, None)
            continue
        if st.get(k):
            continue
        try:
            from . import notify
            if notify.message(f"CBB: {LABEL[k]} stale", f"{LABEL[k]} is {age:.0f} hours old (normal: under {CADENCE[k]:g} h). "
                              f"Plays built on it are marked stale on the card. Nothing is blocked."):
                st[k] = run_at.isoformat(timespec="seconds")
                sent += 1
        except Exception as e:
            print(f"Stale-feed alert failed ({e}); continuing.")
    try:
        json.dump(st, open(ALERTED, "w"))
    except OSError:
        pass
    return sent
