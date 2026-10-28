"""Forward-test logging (FORWARD_TEST_PROTOCOL.md): what each line pull saw, when, and what each signal was built on.

Additive only: nothing here feeds the model, the card or the bet log, and every writer swallows its own errors so a
logging failure can never stop or change a card run.

  lines/polls.csv              one row per poll attempt per source (targeted polls: lines/polls_targeted.csv): observed_at, source, status (ok / error /
                               skipped), error text, events and quotes returned, cost (SGO entities = events; The Odds
                               API credits from its x-requests-last header), credits left, seconds since that source's
                               previous successful poll
  lines/obs/<ET date>.csv      (targeted polls: lines/obs_targeted/) every quote observation, both sides of each spread and total at every book in the frozen
                               book set, for games inside a watch window (watched_games: from a signal's actual alert
                               through SIGNAL_WATCH, and the last TIP_WATCH before its scheduled tip), plus every quote
                               of a new signal's game from the pull that generated it: observed_at (our clock), source,
                               event_id, game_key, book, market, side, line, price, source_updated_at (the feed's
                               lastUpdatedAt / last_update), quote_age_s, status (available / unavailable / stale /
                               absent: the book was in the poll but did not list this quote, or the game was missing
                               from the poll before its tip), poll_id. A quote is only ever "seen" at an observed_at;
                               nothing is inferred between polls. Finished days are gzipped (compact()).
  bets/signal_log.csv          one row per logged signal: generated_at (card run start), logged_at, the lines pull it
                               used, the quote it was logged at (source, book, line, price, source_updated_at, age),
                               input cutoffs (box scores through, KenPom source, Barttorvik file, crew posted),
                               opening-week shift, code version
  bets/alert_log.csv           one row per alert attempt: id, channel (ntfy / discord), kind, sent_at, ok, message id
"""
from __future__ import annotations

import os

import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
LINES = os.path.join(ROOT, "lines")
POLLS = os.path.join(LINES, "polls.csv")
OBS_DIR = os.path.join(LINES, "obs")
SIGNALS = os.path.join(ROOT, "bets", "signal_log.csv")
ALERTS = os.path.join(ROOT, "bets", "alert_log.csv")
SIGNAL_WATCH = pd.Timedelta(minutes=95)     # from the actual alert: the 60-80 minute delay window plus a buffer
TIP_WATCH = pd.Timedelta(minutes=20)        # games with an open signal: the last minutes before the scheduled tip
# Tip-time conflict (Chad, Oct 28, option 2): when ESPN's scheduled start differs from the feed's by at least this much,
# the TIP_WATCH before ESPN's start is polled as well. Logging only: the protocol's cutoff and close are unchanged.
TIP_CONFLICT = pd.Timedelta(minutes=30)     # = clv_primary.START_GAP_CONFLICT_MIN
                                            # (the strict close is the last valid observation within 15 minutes)
POLL_COLS = ["poll_id", "observed_at", "source", "status", "error", "events", "quotes", "cost", "remaining",
             "secs_since_prev_ok"]
OBS_COLS = ["poll_id", "observed_at", "source", "event_id", "game_key", "start", "book", "market", "side", "line",
            "price", "source_updated_at", "quote_age_s", "status"]
SIGNAL_COLS = ["bet_id", "generated_at", "logged_at", "lines_pulled_at", "market", "side", "book", "line", "odds",
               "quote_source", "quote_event_id", "quote_poll_id", "quote_source_updated_at", "quote_age_s", "quote_status",
               "box_scores_through", "kenpom_source", "barttorvik_file", "crew_posted", "opening_week_shift",
               "code_version"]
ALERT_COLS = ["id", "channel", "kind", "sent_at", "ok", "message_id"]

RUN_STARTED: pd.Timestamp | None = None    # set by run_day.main at the start of a card run
LOGGED: set = set()                        # (poll_id, game_key) already written by this process
SIDES = [("spread", "home"), ("spread", "away"), ("total", "over"), ("total", "under")]


def now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def _append(path: str, rows: list[dict], cols: list[str]) -> None:
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df = pd.DataFrame(rows).reindex(columns=cols)
    df.to_csv(path, mode="a", header=not os.path.exists(path), index=False)


def poll(source: str, status: str, observed_at: pd.Timestamp, events=None, quotes=None, cost=None, remaining=None,
         error: str = "") -> str:
    """Record one poll attempt. Returns its poll_id."""
    pid = f"{source}-{observed_at:%Y%m%dT%H%M%S.%f}"
    try:
        prev = None
        if os.path.exists(POLLS):
            p = pd.read_csv(POLLS)
            p = p[(p["source"] == source) & (p["status"] == "ok")]
            if len(p):
                prev = pd.Timestamp(p["observed_at"].iloc[-1])
        gap = round((observed_at - prev).total_seconds()) if prev is not None and status == "ok" else None
        _append(POLLS, [{"poll_id": pid, "observed_at": observed_at.isoformat(timespec="seconds"), "source": source,
                         "status": status, "error": str(error)[:300], "events": events, "quotes": quotes, "cost": cost,
                         "remaining": remaining, "secs_since_prev_ok": gap}], POLL_COLS)
    except Exception as e:
        print(f"quotelog.poll failed ({e}); continuing.")
    return pid


def _game_key(start, home_id, away_id) -> str | None:
    try:
        d = pd.Timestamp(start).tz_convert("America/New_York").strftime("%Y-%m-%d")
        lo, hi = sorted((int(home_id), int(away_id)))
        return f"{d}|{lo}|{hi}"
    except Exception:
        return None


def observation(source, event_id, start, home_id, away_id, book, market, side, line, price, source_updated_at,
                observed_at, status) -> dict:
    upd = pd.to_datetime(source_updated_at, utc=True, errors="coerce")
    return {"observed_at": observed_at.isoformat(timespec="seconds"), "source": source, "event_id": event_id,
            "game_key": _game_key(start, home_id, away_id), "start": start, "book": book, "market": market,
            "side": side, "line": line, "price": price,
            "source_updated_at": upd.isoformat() if pd.notna(upd) else None,
            "quote_age_s": round((observed_at - upd).total_seconds()) if pd.notna(upd) else None, "status": status}


def alert_times() -> pd.DataFrame:
    """bet_id -> the actual alert time and its source, from bets/alert_log.csv: the first successful ntfy send, else
    the first successful Discord post. Bets with neither are absent; callers fall back to logged_at and label it."""
    if not os.path.exists(ALERTS):
        return pd.DataFrame(columns=["alert_at", "alert_source"])
    a = pd.read_csv(ALERTS)
    a = a[a["ok"].astype(str).eq("True") & a["channel"].isin(["ntfy", "discord"])].copy()
    a["alert_at"] = pd.to_datetime(a["sent_at"], utc=True, errors="coerce", format="ISO8601")
    a["alert_source"] = a["channel"]
    a["rank"] = a["channel"].map({"ntfy": 0, "discord": 1})
    a = a.dropna(subset=["alert_at"]).sort_values(["rank", "alert_at"]).drop_duplicates("id")
    return a.set_index("id")[["alert_at", "alert_source"]]


def watched_games(observed_at: pd.Timestamp) -> set:
    """game_keys inside a watch window: SIGNAL_WATCH after a signal's actual alert (its logged time when no alert
    was recorded), or TIP_WATCH before the scheduled tip of a game with an open signal. Both stop at the tip: the
    feeds drop started games, and the evaluation rejects anything observed at or after the scheduled start. When
    ESPN's start differs from the feed's by TIP_CONFLICT or more, the TIP_WATCH before ESPN's start is watched too
    (logging only; the protocol's cutoff stays the feed's start)."""
    keys: set = set()
    try:
        bets = os.path.join(ROOT, "bets", "bets.csv")
        if os.path.exists(bets):
            b = pd.read_csv(bets)
            b = b[b["status"] == "open"]
            t = pd.to_datetime(b["logged_at"], utc=True, errors="coerce", format="ISO8601")
            al = alert_times()["alert_at"]
            if len(al):
                t = b["bet_id"].map(al).fillna(t)
            starts = _signal_starts()
            espn = _espn_starts(b)
            for (_, r), ta in zip(b.iterrows(), t):
                lo, hi = sorted((int(r["home_id"]), int(r["away_id"])))
                gk = f"{r['date']}|{lo}|{hi}"
                st = starts.get(gk)
                es = espn.get(r["bet_id"])
                if es is not None and st is not None and abs(es - st) >= TIP_CONFLICT and \
                        es - TIP_WATCH <= observed_at < es:
                    keys.add(gk)
                if st is not None and observed_at >= st:
                    continue
                if (pd.notna(ta) and ta <= observed_at <= ta + SIGNAL_WATCH) or \
                        (st is not None and st - TIP_WATCH <= observed_at):
                    keys.add(gk)
    except Exception as e:
        print(f"quotelog.watched_games failed ({e}); continuing.")
    return keys


def _espn_starts(b: pd.DataFrame) -> dict:
    """bet_id -> ESPN's scheduled start from the card files (reports/cbb_<date>.csv `start`)."""
    out = {}
    try:
        for d, g in b.groupby("date"):
            f = os.path.join(ROOT, "reports", f"cbb_{d}.csv")
            if os.path.exists(f):
                c = pd.read_csv(f, usecols=["game_id", "start"])
                m = dict(zip(c["game_id"].astype(int), pd.to_datetime(c["start"], utc=True, errors="coerce", format="ISO8601")))
                out.update({r["bet_id"]: m.get(int(r["game_id"])) for _, r in g.iterrows()
                            if pd.notna(m.get(int(r["game_id"])))})
    except Exception:
        pass
    return out


def _signal_starts() -> dict:
    """game_key -> scheduled start from lines/closing.csv (the latest start each feed reported)."""
    try:
        c = pd.read_csv(os.path.join(LINES, "closing.csv"))
        st = pd.to_datetime(c["start"], utc=True, errors="coerce", format="ISO8601")
        lo = c[["home_id", "away_id"]].min(axis=1).astype(int).astype(str)
        hi = c[["home_id", "away_id"]].max(axis=1).astype(int).astype(str)
        gk = st.dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d") + "|" + lo + "|" + hi
        return pd.Series(st.to_numpy(), index=gk).groupby(level=0).max().to_dict()
    except Exception:
        return {}


def _with_absent(rows: list[dict], games: set, observed_at: pd.Timestamp) -> list[dict]:
    """rows of `games`, plus an 'absent' row for each book in this poll that did not list one of a game's four quotes
    (and for every quote of a game missing from the poll before its scheduled tip)."""
    books = sorted({r["book"] for r in rows if r.get("book")})
    out = [r for r in rows if r.get("game_key") in games]
    have = {(r["game_key"], r["book"], r["market"], r["side"]) for r in out}
    seen = {r["game_key"]: r for r in out}
    starts = _signal_starts()
    for gk in sorted(games):
        ref = seen.get(gk)
        st = ref["start"] if ref else starts.get(gk)
        if ref is None and (st is None or observed_at >= pd.Timestamp(st)):
            continue   # not in the poll and not known to be pregame: nothing to record
        for bk in books:
            for mk, sd in SIDES:
                if (gk, bk, mk, sd) not in have:
                    out.append({"observed_at": observed_at.isoformat(timespec="seconds"),
                                "source": ref["source"] if ref else None, "event_id": ref["event_id"] if ref else None,
                                "game_key": gk, "start": str(st), "book": bk, "market": mk, "side": sd,
                                "status": "absent"})
    if out and out[0].get("source") is None:
        src = next((r["source"] for r in rows if r.get("source")), None)
        for r in out:
            r["source"] = r["source"] or src
    return out


def observations(rows: list[dict], poll_id: str, observed_at: pd.Timestamp, watched: set | None = None) -> int:
    """Append the observations of games inside a watch window to lines/obs/<ET date of observation>.csv."""
    try:
        watched = watched_games(observed_at) if watched is None else watched
        games = {g for g in watched if (poll_id, g) not in LOGGED}
        keep = [dict(r, poll_id=poll_id) for r in _with_absent(rows, games, observed_at)]
        day = observed_at.tz_convert("America/New_York").strftime("%Y-%m-%d")
        _append(os.path.join(OBS_DIR, f"{day}.csv"), keep, OBS_COLS)
        LOGGED.update((poll_id, g) for g in games)
        return len(keep)
    except Exception as e:
        print(f"quotelog.observations failed ({e}); continuing.")
        return 0


def compact(obs_dir: str | None = None) -> None:
    """Gzip finished days (ET dates before today) so the log stays small in the repository. Each finished day is
    written once and never changes again; readers take .csv and .csv.gz alike."""
    obs_dir = obs_dir or OBS_DIR
    try:
        today = now().tz_convert("America/New_York").strftime("%Y-%m-%d")
        for f in sorted(os.listdir(obs_dir)) if os.path.isdir(obs_dir) else []:
            if f.endswith(".csv") and f[:10] < today:
                src = os.path.join(obs_dir, f)
                pd.read_csv(src).to_csv(src + ".gz", index=False, compression={"method": "gzip", "mtime": 0})
                os.remove(src)
    except Exception as e:
        print(f"quotelog.compact failed ({e}); continuing.")


def read_obs(dirs=("obs", "obs_targeted")) -> pd.DataFrame:
    """Every logged observation from the card runs' and targeted polls' logs (.csv and .csv.gz)."""
    frames = []
    for d in dirs:
        p = os.path.join(LINES, d)
        for f in sorted(os.listdir(p)) if os.path.isdir(p) else []:
            if f.endswith(".csv") or f.endswith(".csv.gz"):
                frames.append(pd.read_csv(os.path.join(p, f)).assign(log=d))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=OBS_COLS + ["log"])


def generating_quote(pulled: list | None, game_key: str, book: str, market: str, side: str) -> dict:
    """The signal's own quote in the pull that generated it (the card run's line pull), latest feed first."""
    best = {}
    for obs, pid, at in pulled or []:
        for r in obs:
            if (r.get("game_key"), r.get("book"), r.get("market"), r.get("side")) == (game_key, book, market, side):
                if not best or r["observed_at"] >= best["observed_at"]:
                    best = dict(r, poll_id=pid)
    return best


def inputs(day: pd.Timestamp, hist: pd.DataFrame | None) -> dict:
    """Input cutoffs for a card day, read from what the run had on disk (no model code is touched)."""
    from . import barttorvik, kenpom
    out = {}
    try:
        out["box_scores_through"] = str(pd.to_datetime(hist["date"]).max().date()) if hist is not None and len(hist) else ""
    except Exception:
        out["box_scores_through"] = ""
    fm = os.path.join(kenpom.CACHE, f"endpoint-fanmatch_d-{day:%Y-%m-%d}.json")
    out["kenpom_source"] = "fanmatch" if os.path.exists(fm) else "current ratings at run time"
    try:   # what barttorvik.before() would find: a non-empty cached file in the 7 days before; else the live file
        out["barttorvik_file"] = "live file (current ratings at run time)"
        for k in range(1, 8):
            f = os.path.join(barttorvik.CACHE, f"{day - pd.Timedelta(days=k):%Y%m%d}.parquet")
            if os.path.exists(f) and len(pd.read_parquet(f)):
                out["barttorvik_file"] = os.path.basename(f)[:8]
                break
    except Exception:
        out["barttorvik_file"] = ""
    return out


def signals(new_bets: list[dict], card: pd.DataFrame, day: pd.Timestamp, inp: dict, lines_pulled_at: str | None,
            pulled: list | None = None) -> None:
    """One signal_log row per newly logged bet, with its quote from the generating pull; that pull's quotes for the
    signal's game are added to the observation log (the game was not watched yet when the pull was logged)."""
    try:
        rows = []
        cg = card.set_index("game_id") if len(card) else None
        games = set()
        for b in new_bets:
            g = cg.loc[b["game_id"]] if cg is not None and b["game_id"] in cg.index else {}
            lo, hi = sorted((int(b["home_id"]), int(b["away_id"])))
            games.add(f"{b['date']}|{lo}|{hi}")
            q = generating_quote(pulled, f"{b['date']}|{lo}|{hi}", b.get("book"), b["market"], b["side"])
            crew = g.get("crew") if hasattr(g, "get") else None
            rows.append({"bet_id": b["bet_id"], "generated_at": RUN_STARTED.isoformat(timespec="seconds") if RUN_STARTED is not None else "",
                         "logged_at": b["logged_at"], "lines_pulled_at": lines_pulled_at or "", "market": b["market"],
                         "side": b["side"], "book": b.get("book"), "line": b.get("line"), "odds": b.get("odds"),
                         "quote_source": q.get("source", ""), "quote_event_id": q.get("event_id", ""),
                         "quote_poll_id": q.get("poll_id", ""),
                         "quote_source_updated_at": q.get("source_updated_at", ""), "quote_age_s": q.get("quote_age_s", ""),
                         "quote_status": q.get("status", ""), **inp,
                         "crew_posted": bool(isinstance(crew, str) and crew),
                         "opening_week_shift": g.get("total_shift", 0.0) if hasattr(g, "get") else 0.0,
                         "code_version": os.environ.get("GITHUB_SHA", "")})
        _append(SIGNALS, rows, SIGNAL_COLS)
        for obs, pid, at in pulled or []:
            observations(obs, pid, at, games)
    except Exception as e:
        print(f"quotelog.signals failed ({e}); continuing.")


def alert(id_: str, channel: str, kind: str, ok: bool, message_id: str | None = None) -> None:
    try:
        _append(ALERTS, [{"id": id_, "channel": channel, "kind": kind, "sent_at": now().isoformat(timespec="seconds"),
                          "ok": bool(ok), "message_id": message_id or ""}], ALERT_COLS)
    except Exception as e:
        print(f"quotelog.alert failed ({e}); continuing.")
