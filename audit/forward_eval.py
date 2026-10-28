"""Forward-test evaluation, protocol 2.0 (FORWARD_TEST_PROTOCOL.md). Written before any forward data exists and run
unchanged at each read. Read-only: it writes nothing and changes no prediction, signal or log.

    python -m audit.forward_eval [--through YYYY-MM-DD]

Every definition below is the protocol's. Tests: python -m unittest audit.test_forward_eval
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import subprocess

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
PROTOCOL_VERSION = "2.0"

# --- model versions (protocol sections 1 and 8) ------------------------------------------------------------------
# Model v1 = the live card at the freeze commit (committed 2026-10-26T19:20:50Z). A switch to v2 at a checkpoint sets
# v1's "end" here in a dated protocol amendment; v1 then continues as a shadow strategy logging to its own file, and
# its signals after "end" come only from that file. Versions are never pooled.
FREEZE_COMMIT = "dfb4bc7196d4f72cdeb933abdfcbc87c951122b5"
PROTOCOL_START = pd.Timestamp("2026-10-26T19:20:50Z")
VERSIONS = {"v1": {"start": PROTOCOL_START, "end": None, "shadow_log": os.path.join("bets", "shadow_v1", "bets.csv")}}

# --- season and reads (section 9) --------------------------------------------------------------------------------
FIRST_GAME, LAST_GAME = "2026-11-01", "2027-03-14"      # regular season through Selection Sunday
FINAL_READ_ON = "2027-03-14"                            # the fixed evaluation date (v2.1): formal conclusions only here
DESCRIPTIVE_READS = ["2027-01-15"]                      # descriptive only: no verdict, no test

# --- frozen model v1 selection constants (run_day.py at the freeze). Delayed EV uses these with the signal's own
# logged prediction (bets.csv "model"), never later code, ratings or information.
BOOKS = ["DraftKings", "FanDuel", "BetMGM", "Caesars", "Fanatics", "bet365", "theScore Bet"]
WIN_PROB_V1 = {"spread": (0.0255, 0.58), "total": (0.014, 0.565)}
MIN_EV_V1 = 0.02
EDGE_V1 = {"spread": 2.5, "total": 3.0}

# --- quotes (sections 5 to 7) ------------------------------------------------------------------------------------
WINDOWS = [(5, 10), (15, 25), (30, 45), (60, 80)]      # minutes after the actual alert
FRESH_S = 600            # an "available" quote: feed timestamp no older than this when we observed it
CLOCK_SKEW_S = 60        # a feed timestamp up to this far ahead of our clock counts as fresh; further is invalid
STRICT_WINDOW = pd.Timedelta(minutes=15)               # primary close: last valid observation this close to the cutoff
STRICT_MAX_AGE_S = 300   # ... with the feed timestamp no older than this
BENCH_WINDOW = pd.Timedelta(minutes=60)                # secondary close (closing.csv): coverage and sensitivity only
LOG_RANK = {"obs": 0, "obs_targeted": 1}                # deterministic tie-break between the two logs
SOURCE_RANK = {"oddsapi": 0, "sgo": 1}                  # ... and between the two feeds

# --- inference (section 9) ---------------------------------------------------------------------------------------
N_BOOT, SEED = 5000, 20261026
Z_CRIT = 2.50            # one-sided alpha 0.025 over 4 tests (2 markets x 2 endpoints), Bonferroni: z = 2.498
MIN_PRICE_COVERAGE = 0.95
MIN_CLOSE_COVERAGE = 0.80
MIN_DECIDED_FINAL = 100  # fewer decided signals in a market at the final read: inconclusive


# ================================================================================================================
# prices and grading
# ================================================================================================================
def has_price(x) -> bool:
    try:
        return not math.isnan(float(x))
    except (TypeError, ValueError):
        return False


def payout(odds) -> float:
    """Winnings per unit risked at an American price."""
    o = float(odds)
    return o / 100 if o > 0 else 100 / -o


def win_prob_v1(market: str, edge: float) -> float:
    slope, cap = WIN_PROB_V1[market]
    return float(min(max(0.5 + slope * edge, 0.5), cap))


def edge_v1(market: str, side: str, model: float, line: float) -> float:
    """The signal's frozen edge at another number. model is bets.csv "model" (the home margin for spreads, the total
    for totals); line is from the signal's side."""
    if market == "spread":
        return model + line if side == "home" else line - model
    return model - line if side == "over" else line - model


def number_cmp(market: str, side: str, orig: float, new: float) -> int:
    """+1 if the new number is better for the bettor, 0 if the same, -1 if worse."""
    d = (new - orig) if (market == "spread" or side == "under") else (orig - new)
    return int(np.sign(round(d, 6)))


def grade(market: str, side: str, line: float, home_score, away_score) -> str | None:
    if not (has_price(home_score) and has_price(away_score)):
        return None
    hs, as_ = float(home_score), float(away_score)
    if market == "spread":
        m = (hs - as_ if side == "home" else as_ - hs) + line
    else:
        m = (hs + as_ - line) if side == "over" else (line - hs - as_)
    return "W" if m > 0 else "L" if m < 0 else "P"


# ================================================================================================================
# signals and versions (sections 2, 3 and 8)
# ================================================================================================================
def load_signals(version: str = "v1", through: str | None = None, bets: pd.DataFrame | None = None) -> tuple[pd.DataFrame, str]:
    """The version's signals: the live log from its start to its end, then its shadow log. Games dated in the
    season window (and through `through`). Returns (signals including voids, version status)."""
    v = VERSIONS[version]
    b = pd.read_csv(os.path.join(ROOT, "bets", "bets.csv")) if bets is None else bets
    t = pd.to_datetime(b["logged_at"], utc=True, format="ISO8601")
    keep = t >= v["start"]
    if v["end"] is not None:
        keep &= t < v["end"]
    parts, status = [b[keep].assign(log="live")], "running"
    if v["end"] is not None:
        sp = os.path.join(ROOT, v["shadow_log"])
        if os.path.exists(sp):
            s = pd.read_csv(sp)
            parts.append(s[pd.to_datetime(s["logged_at"], utc=True, format="ISO8601") >= v["end"]].assign(log="shadow"))
            status = f"shadow strategy after {v['end']}"
        else:
            status = f"interrupted at {v['end']} (no shadow log)"
    s = pd.concat(parts, ignore_index=True)
    s = s[(s["date"] >= FIRST_GAME) & (s["date"] <= LAST_GAME)]
    if through:
        s = s[s["date"] <= through]
    s = s.reset_index(drop=True)
    s["game_key"] = [f"{d}|{min(int(h), int(a))}|{max(int(h), int(a))}" for d, h, a in
                     zip(s["date"], s["home_id"], s["away_id"])]
    return s, status


SIGNAL_FIELDS = ["bet_id", "date", "game_id", "market", "side", "home_id", "away_id", "line", "odds", "book", "edge",
                 "model", "logged_at"]


def immutability(versions: list[pd.DataFrame] | None = None, since: pd.Timestamp = PROTOCOL_START) -> dict:
    """Across every committed version of bets/bets.csv (oldest first), no signal logged at or after `since` ever
    changed a defining field or disappeared. Pre-freeze rows are outside the check."""
    n = None
    if versions is None:
        try:
            revs = subprocess.run(["git", "-C", ROOT, "log", "--format=%H", "--", "bets/bets.csv"], capture_output=True,
                                  text=True, check=True).stdout.split()
        except Exception as e:
            return {"checked": False, "why": str(e)[:100]}
        n = len(revs)
        versions = []
        for rev in reversed(revs):
            try:
                versions.append(pd.read_csv(io.StringIO(subprocess.run(
                    ["git", "-C", ROOT, "show", f"{rev}:bets/bets.csv"], capture_output=True, text=True, check=True).stdout)))
            except Exception:
                continue
    first: dict = {}
    changed, vanished = set(), set()
    for d in versions:
        if "logged_at" not in d:
            continue
        d = d[pd.to_datetime(d["logged_at"], utc=True, errors="coerce", format="ISO8601") >= since]
        cur = {r["bet_id"]: tuple(str(r.get(c)) for c in SIGNAL_FIELDS) for _, r in d.iterrows()}
        for k, val in cur.items():
            if k in first and first[k] != val:
                changed.add(k)
            first.setdefault(k, val)
        vanished |= set(first) - set(cur)
    return {"checked": True, "versions": n if n is not None else len(versions), "signals": len(first),
            "changed": sorted(changed), "vanished": sorted(vanished)}


# ================================================================================================================
# alerts, observations, tip cutoffs (sections 5 to 7)
# ================================================================================================================
def alert_times(alerts: pd.DataFrame | None = None) -> pd.DataFrame:
    """bet_id -> actual alert time: the first successful ntfy send, else the first successful Discord post."""
    if alerts is None:
        p = os.path.join(ROOT, "bets", "alert_log.csv")
        if not os.path.exists(p):
            return pd.DataFrame(columns=["alert_at", "alert_source"])
        alerts = pd.read_csv(p)
    a = alerts[alerts["ok"].astype(str).eq("True") & alerts["channel"].isin(["ntfy", "discord"])].copy()
    a["alert_at"] = pd.to_datetime(a["sent_at"], utc=True, errors="coerce", format="ISO8601")
    a["alert_source"] = a["channel"]
    a["rank"] = a["channel"].map({"ntfy": 0, "discord": 1})
    return a.dropna(subset=["alert_at"]).sort_values(["rank", "alert_at"]).drop_duplicates("id").set_index("id")[
        ["alert_at", "alert_source"]]


OBS_TYPED = ["t", "st", "upd", "age", "_lr", "_sr"]


def load_obs(obs: pd.DataFrame | None = None) -> pd.DataFrame:
    """All logged observations, typed, in one deterministic order: observed_at, then log, feed, feed timestamp,
    line, price. Duplicates (the same quote seen by two feeds or both logs) keep their own rows; every selection
    takes the first or last row in this order, so the same data always gives the same answer."""
    if obs is None:
        from cbb import quotelog
        obs = quotelog.read_obs()
    o = obs.copy()
    if "log" not in o:
        o["log"] = "obs"
    o["t"] = pd.to_datetime(o["observed_at"], utc=True, errors="coerce", format="ISO8601")
    o["st"] = pd.to_datetime(o["start"], utc=True, errors="coerce", format="ISO8601")
    o["upd"] = pd.to_datetime(o["source_updated_at"], utc=True, errors="coerce", format="ISO8601")
    o["age"] = (o["t"] - o["upd"]).dt.total_seconds()
    o["_lr"] = o["log"].map(LOG_RANK).fillna(9)
    o["_sr"] = o["source"].map(SOURCE_RANK).fillna(9)
    o["line"] = pd.to_numeric(o["line"], errors="coerce")
    o["price"] = pd.to_numeric(o["price"], errors="coerce")
    o = o.dropna(subset=["t"]).sort_values(["t", "_lr", "_sr", "upd", "line", "price"], na_position="first",
                                           kind="mergesort")
    return o.reset_index(drop=True)


def classify(r) -> str:
    """Status of one observation: unavailable (the feed said so, or the book did not list it), stale (marked stale,
    no feed timestamp, a timestamp too far ahead of our clock, or older than FRESH_S), else available."""
    if r["status"] in ("unavailable", "absent"):
        return "unavailable"
    if r["status"] == "stale" or pd.isna(r["age"]) or r["age"] < -CLOCK_SKEW_S or r["age"] > FRESH_S:
        return "stale"
    return "available"


def fallback_start(closing: pd.DataFrame, b) -> pd.Timestamp | None:
    if not len(closing):
        return None
    c = closing[(closing["date"] == b["date"]) &
                (((closing["home_id"] == b["home_id"]) & (closing["away_id"] == b["away_id"])) |
                 ((closing["home_id"] == b["away_id"]) & (closing["away_id"] == b["home_id"])))]
    st = pd.to_datetime(c["start"], utc=True, errors="coerce", format="ISO8601").max()
    return st if pd.notna(st) else None


def tip_cutoff(og: pd.DataFrame, fallback) -> tuple[pd.Timestamp | None, str]:
    """The scheduled start as last reported before it: the start carried by the latest observation made before its
    own reported start. Delays and reschedules move it; a game never observed pregame uses `fallback` (closing.csv's
    start). Actual tip times are not observed, and nothing at or after the cutoff is used."""
    pre = og[og["t"] < og["st"]] if len(og) else og
    if len(pre):
        return pre["st"].iloc[-1], "latest pregame report"
    return (fallback, "closing.csv start") if fallback is not None else (None, "unknown")


# ================================================================================================================
# closing lines (section 7)
# ================================================================================================================
def _home_number(rows: pd.DataFrame, market: str):
    """Each row's number on the reference side: the home spread (away rows negated), or the total."""
    if market == "spread":
        return np.where(rows["side"] == "home", rows["line"], -rows["line"])
    return rows["line"]


def strict_close(og: pd.DataFrame, market: str, cutoff: pd.Timestamp | None) -> dict:
    """Primary close: per eligible book, the last valid observation (available, feed timestamp at most
    STRICT_MAX_AGE_S old) made within STRICT_WINDOW before the cutoff; consensus = median across books."""
    if cutoff is None or not len(og):
        return {"close": np.nan, "books": 0}
    w = og[(og["market"] == market) & og["book"].isin(BOOKS) & (og["t"] >= cutoff - STRICT_WINDOW) &
           (og["t"] < cutoff) & ~(og["t"] >= og["st"])]
    w = w[(w["status"] == "available") & w["age"].between(-CLOCK_SKEW_S, STRICT_MAX_AGE_S) & w["line"].notna()]
    if not len(w):
        return {"close": np.nan, "books": 0}
    w = w.assign(num=_home_number(w, market))
    per = w.groupby("book", sort=True).tail(1)          # last in the deterministic order, per book
    return {"close": float(per["num"].median()), "books": int(len(per)),
            "obs_before_cutoff_s": sorted(int((cutoff - t).total_seconds()) for t in per["t"]),
            "feed_age_s": sorted(int(a) for a in per["age"])}


def bench_close(closing: pd.DataFrame, b) -> tuple[float, int]:
    """Secondary close: lines/closing.csv, books observed within BENCH_WINDOW before the scheduled start; the median
    home spread or total. Reported beside the primary close, never substituted for it."""
    if not len(closing):
        return np.nan, 0
    c = closing[(closing["date"] == b["date"]) & closing["book"].isin(BOOKS)]
    same = c[(c["home_id"] == b["home_id"]) & (c["away_id"] == b["away_id"])]
    flip = c[(c["home_id"] == b["away_id"]) & (c["away_id"] == b["home_id"])]
    flipped = not len(same) and len(flip) > 0
    c = flip if flipped else same
    st = pd.to_datetime(c["start"], utc=True, errors="coerce", format="ISO8601")
    seen = pd.to_datetime(c["pulled_at"], utc=True, errors="coerce", format="ISO8601")
    v = c.loc[((st - seen) <= BENCH_WINDOW) & (seen < st), "total" if b["market"] == "total" else "home_spread"].dropna()
    if not len(v):
        return np.nan, 0
    med = float(v.median())
    return (-med if flipped and b["market"] == "spread" else med), int(len(v))


def to_side(b, home_number: float) -> float:
    """A reference-side close converted to the signal's side (spreads: the bettor's spread)."""
    if np.isnan(home_number) or b["market"] == "total":
        return home_number
    return home_number if b["side"] == "home" else -home_number


def line_value(b, close: float) -> float:
    """Points the close moved toward the signal from its logged number (+ = the signal beat the close)."""
    if np.isnan(close):
        return np.nan
    if b["market"] == "spread":
        return float(b["line"]) - close
    return close - float(b["line"]) if b["side"] == "over" else float(b["line"]) - close


# ================================================================================================================
# delay windows (sections 5 and 6)
# ================================================================================================================
def assess(b, r) -> dict:
    """For one available observation: A, the original number or better at an acceptable price (a payout at least
    as good as the original; a better number with a worse price is reported as ambiguous, never converted), and B,
    whether the quote passes the frozen +2% EV rule with the signal's own frozen prediction."""
    mk, sd = b["market"], b["side"]
    cmp = number_cmp(mk, sd, float(b["line"]), float(r["line"]))
    if not has_price(r["price"]):
        a = "unknown: no observed price"
    elif not has_price(b["odds"]):
        a = "unknown: no recorded original price"
    else:
        ok = payout(r["price"]) >= payout(b["odds"]) - 1e-9
        a = {(0, True): "yes: same number, price as good or better",
             (1, True): "yes: better number, price as good or better",
             (1, False): "ambiguous: better number, worse price",
             (0, False): "no: same number, worse price"}.get((cmp, ok), "no: worse number")
    out = {"A": a, "number_or_better": cmp >= 0}
    if has_price(r["price"]) and has_price(b.get("model")):
        e = edge_v1(mk, sd, float(b["model"]), float(r["line"]))
        p = win_prob_v1(mk, e)
        ev = p * payout(r["price"]) - (1 - p)
        out.update(edge_v1=round(e, 3), ev_v1=round(ev, 4), B_ev=bool(ev >= MIN_EV_V1),
                   B_rule=bool(ev >= MIN_EV_V1 and e >= EDGE_V1[mk]))
    return out


def delay_windows(sig: pd.DataFrame, obs: pd.DataFrame, closing: pd.DataFrame,
                  alerts: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per signal x window x scope (the original book, then each tracked book): the FIRST observation in
    [alert + lo, alert + hi] before the tip cutoff, its status, the elapsed minutes, A and B. A later observation
    never replaces an unavailable or stale first one; no observation in the window is "missing"."""
    al = alert_times(alerts)
    by_game = dict(tuple(obs.groupby("game_key", sort=False))) if len(obs) else {}
    rows = []
    for _, b in sig.iterrows():
        og = by_game.get(b["game_key"], obs.iloc[0:0])
        cutoff, _ = tip_cutoff(og, fallback_start(closing, b))
        if b["bet_id"] in al.index:
            t0, src = al.loc[b["bet_id"], "alert_at"], al.loc[b["bet_id"], "alert_source"]
        else:
            t0, src = pd.Timestamp(b["logged_at"]), "fallback: logged_at (no alert recorded)"
        q = og[(og["market"] == b["market"]) & (og["side"] == b["side"]) & ~(og["t"] >= og["st"])]
        if cutoff is not None:
            q = q[q["t"] < cutoff]
        by_book = dict(tuple(q.groupby("book", sort=False)))
        for lo, hi in WINDOWS:
            ws, we = t0 + pd.Timedelta(minutes=lo), t0 + pd.Timedelta(minutes=hi)
            base = {"bet_id": b["bet_id"], "market": b["market"], "date": b["date"], "window": f"{lo}-{hi} min",
                    "alert_source": src}
            for scope, book in [("original book", b["book"])] + [("tracked book", bk) for bk in BOOKS]:
                rec = dict(base, scope=scope, book=book, truncated_by_tip=bool(cutoff is not None and we >= cutoff))
                if cutoff is not None and ws >= cutoff:
                    rows.append(dict(rec, outcome="window after tip"))
                    continue
                qb = by_book.get(book)
                w = qb[(qb["t"] >= ws) & (qb["t"] <= we)] if qb is not None else q.iloc[0:0]
                if not len(w):
                    rows.append(dict(rec, outcome="missing"))
                    continue
                r = w.iloc[0]
                rec.update(outcome=classify(r), elapsed_min=round((r["t"] - t0).total_seconds() / 60, 2),
                           line=r["line"], price=r["price"])
                if rec["outcome"] == "available":
                    rec.update(assess(b, r))
                    g = grade(b["market"], b["side"], float(r["line"]), b.get("home_score"), b.get("away_score"))
                    if g and has_price(r["price"]):
                        rec["u_observed"] = payout(r["price"]) if g == "W" else (-1.0 if g == "L" else 0.0)
                rows.append(rec)
    return pd.DataFrame(rows)


def summarize_delays(d: pd.DataFrame) -> dict:
    if not len(d):
        return {"note": "no signals"}
    out = {}
    for mk in ("spread", "total"):
        for lo, hi in WINDOWS:
            w = d[(d["market"] == mk) & (d["window"] == f"{lo}-{hi} min")]
            if not len(w):
                continue
            ob = w[w["scope"] == "original book"]
            av = ob[ob["outcome"] == "available"]
            tb = w[w["scope"] == "tracked book"]
            get = lambda f, c: f[c] if c in f else pd.Series(index=f.index, dtype=object)
            yes = get(tb, "A").astype(str).str.startswith("yes")
            seen = tb["outcome"].isin(["available", "stale", "unavailable"])
            out[f"{mk} {lo}-{hi} min"] = {
                "original book": {
                    "signals": int(len(ob)),
                    "outcome": {k: int(v) for k, v in ob["outcome"].value_counts().sort_index().items()},
                    "window cut short by the tip": int(ob["truncated_by_tip"].sum()),
                    "elapsed min, median (observed)": float(get(ob, "elapsed_min").astype(float).median()) if get(ob, "elapsed_min").notna().any() else None,
                    "A among observed available": {k: int(v) for k, v in get(av, "A").value_counts().sort_index().items()},
                    "number or better at any price (descriptive)": int(get(av, "number_or_better").fillna(False).astype(bool).sum()),
                    "B: passes frozen +2% EV": int(get(av, "B_ev").fillna(False).astype(bool).sum()),
                    "B: passes frozen edge threshold and +2% EV": int(get(av, "B_rule").fillna(False).astype(bool).sum()),
                    "ROI% at the observed quote (hypothetical, observed available only)":
                        100 * float(get(av, "u_observed").astype(float).mean()) if get(av, "u_observed").notna().any() else None,
                    "alert time from fallback (logged_at)": int(ob["alert_source"].str.startswith("fallback").sum()),
                },
                "any tracked book (each book's first observation in the window)": {
                    "signals with A at one or more books": int(yes.groupby(tb["bet_id"]).any().sum()),
                    "signals with one or more books observed": int(seen.groupby(tb["bet_id"]).any().sum()),
                    "signals with no book observed": int((~seen.groupby(tb["bet_id"]).any()).sum()),
                },
            }
    out["note"] = ("'available' means observed available, not filled: only accepted bets (cohort C) show a bet was "
                   "taken. A missing or unavailable observation is not proof that no bet was possible.")
    return out


# ================================================================================================================
# inference (section 9)
# ================================================================================================================
def boot(values, dates, n_boot: int = N_BOOT) -> dict:
    """Date-clustered bootstrap of a mean: resample game dates with replacement; each draw's statistic is the mean
    of every value on the drawn dates. z = the mean of the draws / their standard deviation (the bootstrap SE)."""
    d = pd.DataFrame({"v": np.asarray(values, float), "d": np.asarray(dates)}).dropna()
    est = float(d["v"].mean()) if len(d) else np.nan
    if d["d"].nunique() < 2:
        return {"n": int(len(d)), "dates": int(d["d"].nunique()), "estimate": est}
    g = d.groupby("d")["v"].agg(["sum", "count"]).to_numpy()
    idx = np.random.default_rng(SEED).integers(0, len(g), size=(n_boot, len(g)))
    s = g[idx].sum(axis=1)
    draws = s[:, 0] / s[:, 1]
    bm, se = float(draws.mean()), float(draws.std(ddof=1))
    return {"n": int(len(d)), "dates": int(len(g)), "estimate": est, "boot_mean": bm, "se": se,
            "z": bm / se if se > 0 else (np.sign(bm) * np.inf if bm != 0 else np.nan),
            "interval95 (descriptive)": [float(np.quantile(draws, .025)), float(np.quantile(draws, .975))]}


def _r(x, k=4):
    if isinstance(x, dict):
        return {a: _r(b, k) for a, b in x.items()}
    if isinstance(x, (list, tuple)):
        return [_r(b, k) for b in x]
    if isinstance(x, (float, np.floating)):
        return None if math.isnan(x) else round(float(x), k)
    if isinstance(x, np.integer):
        return int(x)
    return x


def endpoint_verdict(z: float, gate_ok: bool, gate_why: str, n_ok: bool, z_sens=(), z_sens_contra=()) -> str:
    """supported: z >= Z_CRIT (and in every listed sensitivity); contradicted: z <= -Z_CRIT (and in every listed
    contradiction sensitivity); else inconclusive. A failed gate or too few decided signals: inconclusive."""
    if not n_ok:
        return f"inconclusive (fewer than {MIN_DECIDED_FINAL} decided signals)"
    if not gate_ok:
        return f"inconclusive ({gate_why})"
    if z is None or np.isnan(z):
        return "inconclusive (no estimate)"
    if z >= Z_CRIT and all(s >= Z_CRIT for s in z_sens):
        return "supported"
    if z <= -Z_CRIT and all(s <= -Z_CRIT for s in z_sens_contra):
        return "contradicted"
    return "inconclusive"


def market_verdict(e1: str, e2: str) -> str:
    """supported only if both endpoints are; contradicted if one is and neither is supported; else inconclusive."""
    if e1 == "supported" and e2 == "supported":
        return "supported"
    if "contradicted" in (e1, e2) and "supported" not in (e1, e2):
        return "contradicted"
    return "inconclusive"


def missing_price_clusters(dec: pd.DataFrame) -> dict:
    """Share of decided signals without a recorded price by book, week, edge band, feed and market. Groups with 10+
    decided signals and a share of at least max(10%, twice the overall share) are flagged."""
    if not len(dec):
        return {}
    d = dec.assign(missing=~dec["odds"].map(has_price))
    overall = float(d["missing"].mean())
    bands = {"spread": [2.5, 3.5, 5, np.inf], "total": [3, 4, 6, np.inf]}
    d["edge_band"] = [next((f"{lo}-{hi}" for lo, hi in zip(bands[m][:-1], bands[m][1:]) if lo <= e < hi), "below threshold")
                      for m, e in zip(d["market"], pd.to_numeric(d["edge"], errors="coerce").fillna(-1))]
    d["week"] = pd.to_datetime(d["date"]).dt.strftime("%G-W%V")
    d["feed"] = d["quote_source"].fillna("no quote record") if "quote_source" in d else "no quote record"
    out, flagged = {"overall missing share": overall}, []
    for col in ("book", "week", "edge_band", "feed", "market"):
        g = d.groupby(col)["missing"].agg(["mean", "size"])
        out[col] = {str(k): [float(r["mean"]), int(r["size"])] for k, r in g.iterrows()}
        flagged += [f"{col}={k}" for k, r in g.iterrows() if r["size"] >= 10 and r["mean"] >= max(0.10, 2 * overall)]
    out["flagged groups"] = flagged
    return out


def units(result, odds) -> float:
    """Flat 1 unit at a recorded price; NaN without one (never an assumed price)."""
    if result not in ("W", "L", "P") or not has_price(odds):
        return np.nan
    return payout(odds) if result == "W" else (-1.0 if result == "L" else 0.0)


# ================================================================================================================
# the read
# ================================================================================================================
def evaluate(through: str | None = None, today: str | None = None, bets: pd.DataFrame | None = None,
             obs: pd.DataFrame | None = None, closing: pd.DataFrame | None = None, alerts: pd.DataFrame | None = None,
             signal_log: pd.DataFrame | None = None, accepted: pd.DataFrame | None = None,
             history: list | None = None, version: str = "v1") -> dict:
    today = today or pd.Timestamp.now(tz="America/New_York").strftime("%Y-%m-%d")
    through = through or min(today, LAST_GAME)
    final = through >= LAST_GAME and today >= FINAL_READ_ON
    sig, vstatus = load_signals(version, through, bets)
    voids = sig[sig["status"] == "void"]
    a = sig[sig["status"] != "void"].copy()

    def _csv(df, *path):
        p = os.path.join(ROOT, *path)
        return df if df is not None else (pd.read_csv(p) if os.path.exists(p) else None)
    slog = _csv(signal_log, "bets", "signal_log.csv")
    slog = slog.drop_duplicates("bet_id").set_index("bet_id") if slog is not None and len(slog) else pd.DataFrame()
    for c in ("quote_source", "quote_status", "quote_age_s", "line", "book"):
        a[f"sl_{c}"] = a["bet_id"].map(slog[c]) if c in slog else np.nan
    a["quote_source"] = a["sl_quote_source"]
    closing = _csv(closing, "lines", "closing.csv")
    if closing is None:
        closing = pd.DataFrame(columns=["date", "home_id", "away_id", "book", "home_spread", "total", "start", "pulled_at"])
    o = load_obs(obs)

    strict, bench, books_used = [], [], []
    by_game = dict(tuple(o.groupby("game_key", sort=False))) if len(o) else {}
    for _, b in a.iterrows():
        og = by_game.get(b["game_key"], o.iloc[0:0])
        cutoff, _ = tip_cutoff(og, fallback_start(closing, b))
        sc = strict_close(og, b["market"], cutoff)
        strict.append(to_side(b, sc["close"]))
        bench.append(to_side(b, bench_close(closing, b)[0]))
        books_used.append(sc["books"])
    a["close_strict"], a["close_bench"], a["close_books"] = strict, bench, books_used
    a["lv"] = [line_value(r, c) for (_, r), c in zip(a.iterrows(), a["close_strict"])]
    a["lv_bench"] = [line_value(r, c) for (_, r), c in zip(a.iterrows(), a["close_bench"])]
    a["priced"] = a["odds"].map(has_price).astype(bool)
    a["u"] = [units(r, o_) if s == "settled" else np.nan for r, o_, s in zip(a["result"], a["odds"], a["status"])]
    a["gm"] = a["date"].astype(str) + "|" + a["game_id"].astype(str) + "|" + a["market"]
    later = set(a.sort_values("logged_at", kind="mergesort").loc[lambda x: x["gm"].duplicated(), "bet_id"])

    out = {"protocol": PROTOCOL_VERSION, "model version": version, "version status": vstatus,
           "read": "final: formal verdicts" if final else "descriptive: no verdict, no test",
           "through": through, "run on": today, "signals (cohort A, non-void)": int(len(a)),
           "voids (listed, excluded from every metric)": voids["bet_id"].tolist()}
    for mk in ("spread", "total"):
        m = a[a["market"] == mk]
        st = m[m["status"] == "settled"]
        dec = st[st["result"].isin(["W", "L"])]
        roi = st.loc[st["priced"].astype(bool)]
        w, l, p = (int((st["result"] == x).sum()) for x in "WLP")
        coverage = float(dec["priced"].mean()) if len(dec) else np.nan
        close_cov = float(m["lv"].notna().mean()) if len(m) else np.nan
        rec_pay = dec.loc[dec["priced"], "odds"].map(payout)
        sens = {}
        for name, pay in (("missing at -110 (hypothetical)", 100 / 110),
                          ("missing at the worst recorded price", rec_pay.min() if len(rec_pay) else np.nan),
                          ("missing at the best recorded price", rec_pay.max() if len(rec_pay) else np.nan)):
            u = [x if not np.isnan(x) else (pay if r == "W" else -1.0 if r == "L" else 0.0)
                 for x, r in zip(st["u"], st["result"])]
            sens[name] = boot(u, st["date"])
        e1, e2 = boot(m["lv"], m["date"]), boot(roi["u"], roi["date"])
        res = {
            "counts": {"signals": len(m), "settled": len(st), "W": w, "L": l, "P (pushes, 0 units, in ROI)": p,
                       "decided (W+L)": len(dec), "unsettled (excluded until settled)": int((m["status"] == "open").sum()),
                       "decided with recorded price": int(dec["priced"].sum()),
                       "recorded-price coverage among decided": coverage,
                       "settled signals in confirmatory ROI": len(roi),
                       "strict close present": int(m["lv"].notna().sum()), "strict close missing": int(m["lv"].isna().sum()),
                       "strict-close coverage": close_cov,
                       "books per strict close (median)": float(m.loc[m["close_books"] > 0, "close_books"].median()) if (m["close_books"] > 0).any() else None,
                       "benchmark close present": int(m["lv_bench"].notna().sum())},
            "win% (decided)": 100 * w / (w + l) if w + l else None,
            "E1: line value vs strict close (points)": e1,
            "E2: ROI at recorded prices (units per signal)": e2,
            "line value vs 60-minute benchmark (secondary)": boot(m["lv_bench"], m["date"]),
            "line value p10/p50/p90": m["lv"].quantile([.1, .5, .9]).tolist() if m["lv"].notna().any() else None,
            "ROI sensitivities for missing prices (never confirmatory)": sens,
            "missing-price clustering": missing_price_clusters(dec),
            "ROI without later opposite-side signals": boot(roi.loc[~roi["bet_id"].isin(later), "u"],
                                                            roi.loc[~roi["bet_id"].isin(later), "date"]),
        }
        if final:
            n_ok = len(dec) >= MIN_DECIDED_FINAL
            v1 = endpoint_verdict(e1.get("z", np.nan), close_cov >= MIN_CLOSE_COVERAGE,
                                  f"strict-close coverage {close_cov:.0%} below {MIN_CLOSE_COVERAGE:.0%}", n_ok)
            v2 = endpoint_verdict(e2.get("z", np.nan), coverage >= MIN_PRICE_COVERAGE,
                                  f"recorded-price coverage {coverage:.1%} below {MIN_PRICE_COVERAGE:.0%}", n_ok,
                                  [sens["missing at the worst recorded price"].get("z", np.nan)],
                                  [sens["missing at the best recorded price"].get("z", np.nan)])
            res.update({"E1 verdict": v1, "E2 verdict": v2, "verdict": market_verdict(v1, v2)})
        else:
            for k, v in res.items():
                if isinstance(v, dict) and "z" in v:
                    res[k] = {kk: vv for kk, vv in v.items() if kk != "z"}
            for v in sens.values():
                v.pop("z", None)
            res["verdict"] = f"none: descriptive read (formal conclusions only at the final read, {FINAL_READ_ON})"
        out[mk] = _r(res)

    acc = _csv(accepted, "bets", "accepted.csv")
    acc = acc if acc is not None else pd.DataFrame(columns=["bet_id", "line", "odds"])
    age = pd.to_numeric(a["sl_quote_age_s"], errors="coerce")
    in_b = (a["sl_quote_status"] == "available") & age.between(-CLOCK_SKEW_S, FRESH_S) & (a["sl_book"] == a["book"]) & \
           (pd.to_numeric(a["sl_line"], errors="coerce") == pd.to_numeric(a["line"], errors="coerce"))
    c = a.merge(acc, on="bet_id", how="inner", suffixes=("", "_acc"))
    c["u_acc"] = [units(grade(r["market"], r["side"], float(r["line_acc"]), r.get("home_score"), r.get("away_score"))
                        if has_price(r["line_acc"]) else None, r["odds_acc"]) for _, r in c.iterrows()]
    cohorts = {}
    for name, sub, ucol in (("A: every signal", a, "u"), ("A with a recorded price", a.loc[a["priced"].astype(bool)], "u"),
                            ("B: fresh observed quote at the named book and number", a.loc[in_b.astype(bool)], "u"),
                            ("C: accepted bets, at the accepted line and price", c, "u_acc")):
        cohorts[name] = {mk: _r({"signals": int((sub["market"] == mk).sum()),
                                 "settled with price": int(sub.loc[sub["market"] == mk, ucol].notna().sum()),
                                 "ROI%": 100 * float(sub.loc[sub["market"] == mk, ucol].mean()) if sub.loc[sub["market"] == mk, ucol].notna().any() else None,
                                 "line value, strict (pts)": float(sub.loc[sub["market"] == mk, "lv"].mean()) if sub.loc[sub["market"] == mk, "lv"].notna().any() else None})
                         for mk in ("spread", "total")}
    out["cohorts"] = cohorts
    out["cohort B exclusions"] = {"no quote record": int(a["sl_quote_status"].isna().sum()),
                                  "quote stale, unavailable, or not at the logged book and number":
                                      int((a["sl_quote_status"].notna() & ~in_b).sum())}
    out["delay windows"] = _r(summarize_delays(delay_windows(a, o, closing, alerts) if len(a) else pd.DataFrame()))
    out["opposite-side later signals (flagged)"] = len(later)
    out["signal immutability since the freeze"] = immutability(history)
    if bets is None:
        pre = pd.read_csv(os.path.join(ROOT, "bets", "bets.csv"))
        pre = pre[pd.to_datetime(pre["logged_at"], utc=True, format="ISO8601") < PROTOCOL_START]
        out["pre-freeze signals (separate, never pooled)"] = {"signals": len(pre), "voids": int((pre["status"] == "void").sum())}
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--through")
    print(json.dumps(evaluate(ap.parse_args().through), indent=1, default=str))
