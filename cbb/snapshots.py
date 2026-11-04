"""What each alert was built on: the actual input tables, their hashes and times (Chad, Nov 4: "Save the actual input
snapshots, not just fingerprints"). Logging only: nothing the card computes, picks, logs, alerts or posts changes.

install() wraps the fetchers and steps the card already calls, the same way cbb/card_features.py wraps run_day.plays:
each wrapper passes its result through unchanged and keeps a copy for the day being built. When a play is logged
(freshness.log_inputs, called by run_day.build for main plays and band B), record() writes one manifest row per input
behind that play to bets/input_snapshots.csv and stores each table once, by content hash:

  input              what is kept                                                   where the table is stored
  kenpom_fanmatch    KenPom's FanMatch answer for the card day (when the card used it)    private runner cache *
  kenpom_ratings     KenPom's current ratings as fetched this run (when FanMatch was not out) private runner cache *
  barttorvik         the Barttorvik file the card used (time-machine date, or the live file)  bets/snapshots/
  stage1_ratings     our own stage-1 team ratings (run_day.project's ratings table)           bets/snapshots/
  box_scores         hoopR schedule/box-score files: hash, latest final game date, download time (not the files)
  injuries           the injury adjustment by team and the listed players behind it            bets/snapshots/
  referees           the referee crews posted for the day's games                               bets/snapshots/
  market_context     market ratings from our own closing lines (context.market)                 bets/snapshots/
  features           every game's stage-2 inputs and the model's margin and total               bets/snapshots/
  lines              this run's quotes, every book, for the play's game                         bets/snapshots/
  config:<file>      data/projection.json, referees.csv, teams.csv, ... : hash; the file is in git at code_version

* KenPom is licensed: its tables never go in this public repository. They are kept in cbb/cache/snapshots/kenpom/,
  the runner cache every card run restores and saves (private to the repository's workflows, but not permanent:
  GitHub drops cache entries not used for 7 days). The hash, request, DataThrough label and times are in the public
  manifest. A permanent private copy needs a place the workflow can write to (audit/TIMING_AUDIT.md, section 5).

Times, per input:
  retrieved_at         when our system downloaded the table (the cache file's time when it was served from cache)
  first_observed_at    the first card run that saw this exact table (bets/snapshots/seen.csv, written every run)
  provider_published_at  "unknown" unless the provider states it: first observed by us is not when they published
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re

import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
MANIFEST = os.path.join(ROOT, "bets", "input_snapshots.csv")
PUBLIC = os.path.join(ROOT, "bets", "snapshots")
SEEN = os.path.join(PUBLIC, "seen.csv")
PRIVATE = os.path.join(os.path.dirname(__file__), "cache", "snapshots")
LICENSED = ("kenpom_fanmatch", "kenpom_ratings")
CONFIG = ["data/projection.json", "data/referees.csv", "data/teams.csv", "data/team_aliases.csv",
          "data/barttorvik_preseason_2027.csv", "data/home_arenas.csv"]
COLS = ["bet_id", "run_at", "code_version", "model_version", "input", "source", "source_date", "sha256", "rows",
        "storage", "path", "retrieved_at", "first_observed_at", "provider_published_at"]
SEEN_COLS = ["input", "sha256", "source", "source_date", "first_observed_at", "run_id"]
SEEN_INPUTS = ("kenpom_fanmatch", "kenpom_ratings", "barttorvik", "box_scores", "injuries", "referees")

CAP: dict = {}           # card day (YYYY-MM-DD) -> {input: {...}}
STATE = {"day": None, "installed": False, "seen": None}


def _now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def _iso(t) -> str:
    if t is None or (not isinstance(t, str) and pd.isna(t)):
        return ""
    return pd.Timestamp(t).isoformat(timespec="seconds") if not isinstance(t, str) else t


def _mtime(path: str):
    try:
        return pd.Timestamp(os.path.getmtime(path), unit="s", tz="UTC")
    except OSError:
        return None


# ---- canonical bytes and hashes ------------------------------------------------------------------------------------

def table_bytes(df: pd.DataFrame) -> bytes:
    """A table as canonical CSV bytes (columns as given, no index; scalar cells only)."""
    d = df.copy()
    for c in d.columns:
        if d[c].dtype == object and d[c].map(lambda x: isinstance(x, (list, dict, set, tuple))).any():
            d[c] = d[c].map(lambda x: json.dumps(x, sort_keys=True, default=str) if isinstance(x, (list, dict, set, tuple)) else x)
    return d.to_csv(index=False).encode()


def json_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _store(kind: str, raw: bytes, digest: str, ext: str) -> tuple[str, str]:
    """Write the bytes once under their hash: (storage, path relative to the repo or the cache)."""
    if kind in LICENSED:
        base, storage = os.path.join(PRIVATE, "kenpom"), "private runner cache"
    else:
        base, storage = os.path.join(PUBLIC, kind), "repo"
    path = os.path.join(base, f"{digest[:20]}.{ext}.gz")
    if not os.path.exists(path):
        os.makedirs(base, exist_ok=True)
        with open(path + ".tmp", "wb") as fh:
            with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as z:
                z.write(raw)
        os.replace(path + ".tmp", path)
    return storage, os.path.relpath(path, ROOT).replace(os.sep, "/")


def load(path: str) -> bytes:
    """A stored table's bytes, from a manifest path (repo-relative; the private copy is under cbb/cache/)."""
    with gzip.open(os.path.join(ROOT, path), "rb") as fh:
        return fh.read()


# ---- capture -------------------------------------------------------------------------------------------------------

def _put(kind: str, raw: bytes, ext: str, source: str, source_date, retrieved_at, rows: int, day: str | None = None) -> None:
    day = day or STATE["day"]
    if not day:
        return
    CAP.setdefault(day, {})[kind] = {"raw": raw, "sha": sha(raw), "ext": ext, "source": source,
                                     "source_date": "" if source_date is None else str(source_date),
                                     "retrieved_at": retrieved_at, "rows": rows}


def _kenpom_path(endpoint: str, params: dict) -> str:
    from . import kenpom
    q = {"endpoint": endpoint, **params}
    return os.path.join(kenpom.CACHE, "_".join(f"{k}-{v}" for k, v in q.items()) + ".json")


def install() -> None:
    """Install the pass-through wrappers once per process (the card run only: cbb/card_features.py)."""
    if STATE["installed"]:
        return
    from . import barttorvik, context, data, freshness, injuries, kenpom, run_day

    p0 = run_day.project
    def project(day, games):
        STATE["day"] = f"{pd.Timestamp(day):%Y-%m-%d}"
        CAP.pop(STATE["day"], None)
        f, rt = p0(day, games)
        try:
            _put("stage1_ratings", table_bytes(rt.reset_index()), "csv", "run_day.project ratings table", STATE["day"],
                 _now(), len(rt))
        except Exception as e:
            print(f"Snapshot (stage-1) failed ({e}); continuing.")
        return f, rt
    run_day.project = project

    g0 = kenpom.get
    def get(endpoint, cache=True, **params):
        path = _kenpom_path(endpoint, params)
        had = cache and os.path.exists(path)
        out = g0(endpoint, cache=cache, **params)
        try:
            if endpoint in ("ratings", "fanmatch") and out:
                dt = max((r.get("DataThrough") for r in out if isinstance(r, dict) and r.get("DataThrough")), default=None) \
                    if endpoint == "ratings" else params.get("d")
                src = f"KenPom {endpoint} " + " ".join(f"{k}={v}" for k, v in params.items())
                _put(f"kenpom_{endpoint}", json_bytes(out), "json", src, dt, _mtime(path) if had else _now(), len(out))
        except Exception as e:
            print(f"Snapshot (KenPom) failed ({e}); continuing.")
        return out
    kenpom.get = get

    b0 = barttorvik.before
    def before(day):
        t = b0(day)
        try:
            f = barttorvik.LAST.get("file")
            if t is not None and f:
                d = f.replace("-", "")
                cand = [os.path.join(barttorvik.CACHE, d + ".parquet"), os.path.join(barttorvik.REPO, d + ".csv")]
                got = next((_mtime(p) for p in cand if os.path.exists(p)), None) or _now()
                _put("barttorvik", table_bytes(t), "csv", f"Barttorvik time-machine file {f}", f, got, len(t),
                     day=f"{pd.Timestamp(day):%Y-%m-%d}")
        except Exception as e:
            print(f"Snapshot (Barttorvik) failed ({e}); continuing.")
        return t
    barttorvik.before = before

    c0 = barttorvik.current
    def current(season):
        t = c0(season)
        try:
            if t is not None:
                _put("barttorvik", table_bytes(t), "csv", f"Barttorvik live ratings file {season}", "live", _now(), len(t))
        except Exception as e:
            print(f"Snapshot (Barttorvik live) failed ({e}); continuing.")
        return t
    barttorvik.current = current

    s0 = data.season_games
    def season_games(season, refresh=False):
        out = s0(season, refresh=refresh)
        try:
            hist = out[0]
            fin = hist.dropna(subset=["home_pts"]) if "home_pts" in hist else hist
            last = str(pd.to_datetime(fin["date"]).max().date()) if len(fin) else ""
            files = [os.path.join(data.CACHE, os.path.basename(data.FILES[k].format(season=season))) for k in ("schedule", "team_box")]
            h = hashlib.sha256()
            for p in files:
                if os.path.exists(p):
                    with open(p, "rb") as fh:
                        h.update(fh.read())
            got = min([t for t in (_mtime(p) for p in files) if t is not None], default=None)
            if STATE["day"] and season == run_day.season_of(pd.Timestamp(STATE["day"])):
                d = CAP.setdefault(STATE["day"], {})
                d["box_scores"] = {"raw": None, "sha": h.hexdigest(), "ext": "", "rows": len(fin),
                                   "source": f"hoopR schedule + team box {season} (files not kept: public, re-downloadable)",
                                   "source_date": last, "retrieved_at": got}
        except Exception as e:
            print(f"Snapshot (box scores) failed ({e}); continuing.")
        return out
    data.season_games = season_games

    a0 = injuries.adjustment
    def adjustment(season):
        team, players = a0(season)
        try:
            raw = table_bytes(team) + b"\n--- players ---\n" + (table_bytes(players) if len(players) else b"")
            got = (freshness.SEEN.get("injuries") or {}).get("at") or _now()
            _put("injuries", raw, "csv", "ESPN injury report via injuries.adjustment", "", got, len(team))
        except Exception as e:
            print(f"Snapshot (injuries) failed ({e}); continuing.")
        return team, players
    injuries.adjustment = adjustment

    r0 = context.live_referees
    def live_referees(game_ids, *a, **k):
        out = r0(game_ids, *a, **k)
        try:
            _put("referees", table_bytes(out), "csv", "ESPN officials via context.live_referees", "", _now(), len(out))
        except Exception as e:
            print(f"Snapshot (referees) failed ({e}); continuing.")
        return out
    context.live_referees = live_referees

    m0 = context.market
    def market(keys, closes, *a, **k):
        out = m0(keys, closes, *a, **k)
        try:
            _put("market_context", table_bytes(out), "csv", "context.market from lines/closing.csv", "", _now(), len(out))
        except Exception as e:
            print(f"Snapshot (market context) failed ({e}); continuing.")
        return out
    context.market = market

    pl0 = run_day.plays
    def plays(f, lines, live=True, *a, **k):
        card = pl0(f, lines, live, *a, **k)
        if live:
            try:
                day = str(f["date"].iloc[0])[:10] if len(f) and "date" in f else STATE["day"]
                _put("features", table_bytes(f), "csv", "projection.apply_saved output (stage-2 inputs and model)", day,
                     _now(), len(f), day=day)
                if lines is not None:
                    CAP.setdefault(day, {})["_lines"] = lines
                note_seen(day)
            except Exception as e:
                print(f"Snapshot (features) failed ({e}); continuing.")
        return card
    run_day.plays = plays

    l0 = freshness.log_inputs
    def log_inputs(new_bets, fr):
        l0(new_bets, fr)
        record(new_bets)
    freshness.log_inputs = log_inputs
    STATE["installed"] = True


# ---- first observed ------------------------------------------------------------------------------------------------

def _seen() -> dict:
    if STATE["seen"] is None:
        STATE["seen"] = {}
        if os.path.exists(SEEN):
            try:
                s = pd.read_csv(SEEN, dtype=str)
                STATE["seen"] = {(r.input, r.sha256): r.first_observed_at for r in s.itertuples()}
            except Exception as e:
                print(f"Snapshot index unreadable ({e}); continuing.")
    return STATE["seen"]


def note_seen(day: str, now: pd.Timestamp | None = None) -> int:
    """Add each source table this run saw for `day` and never saw before to bets/snapshots/seen.csv."""
    now = now or _now()
    seen, rows = _seen(), []
    for kind, v in CAP.get(day, {}).items():
        if kind not in SEEN_INPUTS or (kind, v["sha"]) in seen:
            continue
        seen[(kind, v["sha"])] = _iso(now)
        rows.append({"input": kind, "sha256": v["sha"], "source": v["source"], "source_date": v["source_date"],
                     "first_observed_at": _iso(now), "run_id": os.environ.get("GITHUB_RUN_ID", "")})
    if rows:
        os.makedirs(PUBLIC, exist_ok=True)
        pd.DataFrame(rows, columns=SEEN_COLS).to_csv(SEEN, mode="a", header=not os.path.exists(SEEN), index=False)
    return len(rows)


# ---- per alert -----------------------------------------------------------------------------------------------------

def model_version() -> str:
    try:
        head = open(os.path.join(ROOT, "FORWARD_TEST_PROTOCOL.md")).read(400)
        m = re.search(r"v(\d+\.\d+)", head)
        return f"v1 (protocol v{m.group(1)})" if m else "v1"
    except OSError:
        return "v1"


def _file_sha(rel: str) -> str:
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return ""
    with open(p, "rb") as fh:
        return sha(fh.read())


def record(new_bets: list[dict], now: pd.Timestamp | None = None) -> int:
    """One manifest row per input behind each newly logged play; each table stored once by hash. Returns rows."""
    if not new_bets:
        return 0
    try:
        from . import odds
        now = now or _now()
        seen = _seen()
        code, mv = os.environ.get("GITHUB_SHA", ""), model_version()
        cfg = [(rel, _file_sha(rel)) for rel in CONFIG]
        rows = []
        for b in new_bets:
            day = str(b["date"])[:10]
            cap = dict(CAP.get(day, {}))
            lines = cap.pop("_lines", None)
            if lines is not None and len(lines):
                h, a = int(b["home_id"]), int(b["away_id"])
                g = lines[((lines["home_id"] == h) & (lines["away_id"] == a)) | ((lines["home_id"] == a) & (lines["away_id"] == h))]
                cap["lines"] = {"raw": table_bytes(g), "ext": "csv", "source": "this run's pulled quotes (all books)",
                                "source_date": "", "retrieved_at": getattr(odds.pull, "pulled_at", None) or now, "rows": len(g)}
                cap["lines"]["sha"] = sha(cap["lines"]["raw"])
            base = {"bet_id": b["bet_id"], "run_at": _iso(now), "code_version": code, "model_version": mv,
                    "provider_published_at": "unknown"}
            if not cap:
                rows.append({**base, "input": "none", "source": "no inputs captured for this day (snapshot hooks not active)"})
            for kind, v in cap.items():
                storage, path = ("not kept", "")
                if v.get("raw") is not None:
                    storage, path = _store(kind, v["raw"], v["sha"], v["ext"])
                rows.append({**base, "input": kind, "source": v["source"], "source_date": v["source_date"],
                             "sha256": v["sha"], "rows": v["rows"], "storage": storage, "path": path,
                             "retrieved_at": _iso(v["retrieved_at"]),
                             "first_observed_at": seen.get((kind, v["sha"]), "")})
            for rel, h in cfg:
                rows.append({**base, "input": f"config:{rel}", "source": "git", "sha256": h,
                             "storage": "repo at code_version", "path": rel})
        if rows:
            os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
            pd.DataFrame(rows).reindex(columns=COLS).to_csv(MANIFEST, mode="a", header=not os.path.exists(MANIFEST), index=False)
        return len(rows)
    except Exception as e:
        print(f"Input snapshot log failed ({e}); continuing.")
        return 0


def for_bet(bet_id: str) -> pd.DataFrame:
    """The manifest rows of one logged play."""
    if not os.path.exists(MANIFEST):
        return pd.DataFrame(columns=COLS)
    m = pd.read_csv(MANIFEST, dtype=str)
    return m[m["bet_id"] == str(bet_id)]
