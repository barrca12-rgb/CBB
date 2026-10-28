"""Closing-line value at the forward-test protocol's primary close (FORWARD_TEST_PROTOCOL.md section 7): the one CLV
calculation every surface uses (Discord results, the card's CLV tile and record table, the record page, the
verification page, the weekly charts and the model-check tripwire).

The close is computed by the protocol's own code (audit/forward_eval.py: load_obs, tip_cutoff, fallback_start,
strict_close, to_side, line_value, assess), imported read-only and never re-implemented: per eligible book, the last
valid observation (available, feed timestamp at most 300 seconds old, up to 60 seconds ahead accepted) made within
the 15 minutes before the tip cutoff and before the quote's own reported start; consensus = median across books. A
play with no valid observation in that window has no primary close: it is reported as unavailable with a reason and
counted, never filled with the grader's close or with zero.

The grader's same-book close (bets/bets.csv close_line / clv_pts, written by cbb/tracker.py) is kept as a diagnostic
column only (close_same_book / clv_same_book here) and is labeled as such wherever it is shown.

Price: the protocol compares a quote with the entry by number and payout, without converting points or prices into
probabilities (forward_eval.assess, measure A). The same comparison is reported for each closing book's quote on the
play's side; no new conversion is introduced.

Read only: bets/bets.csv is never changed here. write() saves a per-play table, bets/clv_primary.csv (derived; safe
to delete and rebuild).
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

# Shown next to every CLV figure until the first-game report (audit/CLV_VERIFICATION.md, section 7) confirms the
# pipeline on a real game. Changed only by that report.
VERIFICATION_STATUS = "built, not verified"
TABLE = os.path.join(os.path.dirname(__file__), "..", "bets", "clv_primary.csv")
COLS = ["bet_id", "cohort", "cutoff", "cutoff_source", "espn_start", "start_gap_min", "feed_latest_start",
        "feed_gap_min", "tip_check", "close_primary", "clv_primary", "books_primary", "feed_age_s",
        "obs_before_cutoff_s", "clv_status", "clv_reason", "price_vs_close", "close_espn_start", "clv_espn_start",
        "books_espn_start", "actual_tip", "pregame_check", "pregame_note", "q_pregame", "q_buffer", "q_near_tip",
        "secs_before_tip"]
# Tip-time diagnostics (never change the cutoff, which is the protocol's): the cutoff is compared with ESPN's scheduled
# start and with the feed's latest reported start (lines/closing.csv). Over START_GAP_FLAG_MIN: "review" (shown per
# play and sent for review before tip). At or over START_GAP_CONFLICT_MIN: "conflict" (escalated; a different rule
# would be a protocol change). 10 sits below the 15-minute closing window: a gap over 15 minutes means the window the
# protocol uses and the window around the other start do not overlap at all.
START_GAP_FLAG_MIN = 10
START_GAP_CONFLICT_MIN = 30
# For a "conflict" play the same strict-close rule is also applied at ESPN's start (close_espn_start / clv_espn_start /
# books_espn_start; Chad, Oct 28, option 2). Diagnostic only, always labeled: the protocol's CLV is clv_primary.
# Pregame validity (diagnostic; never changes the protocol's value; audit/CLV_VERIFICATION.md, section 2). Three
# separate questions against the actual tip (ESPN play-by-play, cbb/tipoff.py; measured in audit/tipoff_study.md):
#   pregame   every included quote observed (our clock) before the actual tip
#   buffer    every included quote at least TIP_MARGIN_S before it (ESPN's stamps lag the play by up to ~23 s at the
#             1st percentile; the opening stamp and the jump-ball stamp are a median 1 s apart)
#   near tip  the cutoff no more than EARLY_MIN before it (0.8% of usable 2021-26 games tipped more than 30 min after
#             the scheduled start; an hour-wrong feed start, as Memphis vs Iowa State, fails)
# "verified" only when all three hold; "unverified" when there is no usable actual tip.
TIP_MARGIN_S = 60
EARLY_MIN = 30
_CACHE: dict = {}


def pregame(close, cutoff, before_s, starts, tip) -> dict:
    """The three answers for one computed close. before_s: seconds each included quote was observed before the
    cutoff; starts: every known scheduled start (feed cutoff, ESPN, feed latest); tip: the usable actual tip or None.
    Returns check (verified / early / in-play risk / buffer / unverified / n/a), note, pregame, buffer, near_tip
    (yes / no / unknown) and secs_before_tip (each included quote, latest first; empty without a tip)."""
    out = {"check": "n/a", "note": "no computed close", "pregame": "n/a", "buffer": "n/a", "near_tip": "n/a",
           "secs_before_tip": []}
    if close is None or np.isnan(close) or cutoff is None or pd.isna(cutoff) or not before_s:
        return out
    last = cutoff - pd.Timedelta(seconds=min(before_s))         # the latest included quote, on our clock
    sched = min(s for s in starts if s is not None and pd.notna(s))
    if tip is None or pd.isna(tip):
        late = last >= sched
        out.update(check="in-play risk" if late else "unverified", pregame="no" if late else "unknown",
                   buffer="no" if late else "unknown", near_tip="unknown",
                   note=(f"no usable actual tip; latest included quote {last:%H:%M:%S} UTC is "
                         + (f"at or after the earliest scheduled start {sched:%H:%M} UTC" if late else
                            f"before every scheduled start (earliest {sched:%H:%M} UTC), which does not prove it was pregame")))
        return out
    gap = (tip - cutoff).total_seconds()
    secs = sorted(int(gap + x) for x in before_s)               # each included quote's seconds before the actual tip
    early = gap / 60
    out.update(secs_before_tip=secs, pregame="yes" if secs[0] > 0 else "no",
               buffer="yes" if secs[0] >= TIP_MARGIN_S else "no", near_tip="yes" if early <= EARLY_MIN else "no")
    if out["pregame"] == "no":
        out.update(check="in-play risk", note=f"latest included quote {last:%H:%M:%S} UTC is {-secs[0]} s after the actual tip {tip:%H:%M:%S} UTC")
    elif out["buffer"] == "no":
        out.update(check="buffer", note=f"latest included quote only {secs[0]} s before the actual tip {tip:%H:%M:%S} UTC (buffer {TIP_MARGIN_S} s)")
    elif out["near_tip"] == "no":
        out.update(check="early", note=f"every quote pregame, but the cutoff is {early:.0f} min before the actual tip {tip:%H:%M:%S} UTC: an early-market close")
    else:
        out.update(check="verified", note=f"quotes {secs[0]}-{secs[-1]} s before the actual tip {tip:%H:%M:%S} UTC; cutoff {early:+.0f} min from it")
    return out


def _obs_key() -> tuple:
    from cbb import quotelog
    out = []
    for d in ("obs", "obs_targeted"):
        p = os.path.join(quotelog.LINES, d)
        for f in sorted(os.listdir(p)) if os.path.isdir(p) else []:
            st = os.stat(os.path.join(p, f))
            out.append((d, f, st.st_size, st.st_mtime_ns))
    return tuple(out)


def _load_obs(obs):
    """The protocol's typed observations, cached per process while the log files are unchanged."""
    from audit import forward_eval as fe
    if obs is not None:
        return fe.load_obs(obs)
    k = _obs_key()
    if _CACHE.get("key") != k:
        _CACHE.update(key=k, obs=fe.load_obs(None))
    return _CACHE["obs"]


def _reason(fe, og: pd.DataFrame, market: str, cutoff, now: pd.Timestamp) -> tuple[str, str]:
    """Why a play has no primary close. Diagnostic only: the close itself always comes from fe.strict_close."""
    if cutoff is None or pd.isna(cutoff):
        return "unavailable", "tip time unknown (no pregame observation and no scheduled start in closing.csv)"
    if now < cutoff:
        return "pending", "game has not reached its tip cutoff"
    if not len(og):
        return "unavailable", "no quotes logged for this game"
    w = og[(og["market"] == market) & og["book"].isin(fe.BOOKS) & (og["t"] >= cutoff - fe.STRICT_WINDOW) &
           (og["t"] < cutoff) & ~(og["t"] >= og["st"])]
    if not len(w):
        return "unavailable", "no quote observed in the 15 minutes before the tip cutoff"
    unav = int((w["status"] != "available").sum())
    stale = int(((w["status"] == "available") & ~w["age"].between(-fe.CLOCK_SKEW_S, fe.STRICT_MAX_AGE_S)).sum())
    noline = int(((w["status"] == "available") & w["age"].between(-fe.CLOCK_SKEW_S, fe.STRICT_MAX_AGE_S) &
                  w["line"].isna()).sum())
    return "unavailable", (f"{len(w)} quote(s) in the 15-minute window, none valid: {unav} unavailable or absent, "
                           f"{stale} with a feed timestamp older than {fe.STRICT_MAX_AGE_S} s or missing, {noline} without a number")


def _price_vs_close(fe, b: pd.Series, og: pd.DataFrame, cutoff) -> list[dict]:
    """Per eligible book, its last valid quote on the play's own side in the closing window, compared with the
    entry by the protocol's measure A (number, then payout; no conversion)."""
    if cutoff is None or pd.isna(cutoff) or not len(og):
        return []
    w = og[(og["market"] == b["market"]) & og["book"].isin(fe.BOOKS) & (og["t"] >= cutoff - fe.STRICT_WINDOW) &
           (og["t"] < cutoff) & ~(og["t"] >= og["st"]) & (og["side"] == b["side"])]
    w = w[(w["status"] == "available") & w["age"].between(-fe.CLOCK_SKEW_S, fe.STRICT_MAX_AGE_S) & w["line"].notna()]
    out = []
    for _, r in w.groupby("book", sort=True).tail(1).iterrows():
        a = fe.assess(b, r)
        out.append({"book": r["book"], "line": float(r["line"]),
                    "price": float(r["price"]) if fe.has_price(r["price"]) else None, "age_s": int(r["age"]),
                    "observed_at": r["t"].isoformat(), "vs_entry": a["A"]})
    return out


def _espn_starts(dates) -> dict:
    """game_id -> ESPN's scheduled start from the card files (reports/cbb_<date>.csv `start`). Diagnostic only: the
    protocol's cutoff is the feed's reported start and is not changed by this."""
    from audit import forward_eval as fe
    out = {}
    for d in set(dates):
        f = os.path.join(fe.ROOT, "reports", f"cbb_{d}.csv")
        if os.path.exists(f):
            c = pd.read_csv(f, usecols=["game_id", "start"])
            out.update(dict(zip(c["game_id"].astype(int), pd.to_datetime(c["start"], utc=True, errors="coerce", format="ISO8601"))))
    return out


def primary(b: pd.DataFrame, obs: pd.DataFrame | None = None, closing: pd.DataFrame | None = None,
            now: pd.Timestamp | None = None) -> pd.DataFrame:
    """One row per bet: the primary close and CLV (points, + = beat the close) from the signal's side, the books and
    their quote ages, the status (ok / pending / unavailable / void) with a reason, and the price comparison."""
    from audit import forward_eval as fe
    if closing is None:
        p = os.path.join(fe.ROOT, "lines", "closing.csv")
        closing = pd.read_csv(p) if os.path.exists(p) else pd.DataFrame(
            columns=["date", "home_id", "away_id", "book", "home_spread", "total", "start", "pulled_at"])
    now = now or pd.Timestamp.now(tz="UTC")
    o = _load_obs(obs)
    by_game = dict(tuple(o.groupby("game_key", sort=False))) if len(o) and "game_key" in o else {}
    espn = _espn_starts(b["date"]) if len(b) else {}
    from . import tipoff
    tips = tipoff.load()
    cl = closing.assign(_st=pd.to_datetime(closing["start"], utc=True, errors="coerce", format="ISO8601")) if len(closing) else closing
    rows = []
    for _, r in b.iterrows():
        key = f"{r['date']}|{min(int(r['home_id']), int(r['away_id']))}|{max(int(r['home_id']), int(r['away_id']))}"
        og = by_game.get(key, o.iloc[0:0])
        cutoff, src = fe.tip_cutoff(og, fe.fallback_start(closing, r))
        sc = fe.strict_close(og, r["market"], cutoff)
        close = fe.to_side(r, sc["close"])
        clv = fe.line_value(r, close)
        cohort = "v1" if pd.Timestamp(r["logged_at"]) >= fe.PROTOCOL_START else "pre-freeze"
        es = espn.get(int(r["game_id"]))
        gap = round((cutoff - es).total_seconds() / 60) if es is not None and pd.notna(es) and cutoff is not None \
            and pd.notna(cutoff) else None
        fl = None
        if len(cl):
            m = cl[(cl["date"] == r["date"]) & (((cl["home_id"] == r["home_id"]) & (cl["away_id"] == r["away_id"])) |
                                                ((cl["home_id"] == r["away_id"]) & (cl["away_id"] == r["home_id"])))]
            fl = m["_st"].max() if len(m) and m["_st"].notna().any() else None
        fgap = round((cutoff - fl).total_seconds() / 60) if fl is not None and cutoff is not None and pd.notna(cutoff) else None
        worst = max([abs(x) for x in (gap, fgap) if x is not None] or [0])
        tip = "conflict" if worst >= START_GAP_CONFLICT_MIN else "review" if worst > START_GAP_FLAG_MIN else "ok"
        dg = {"close": np.nan, "books": 0}
        if tip == "conflict" and es is not None and pd.notna(es):
            dg = fe.strict_close(og.assign(st=es), r["market"], es)     # same rule, cutoff = ESPN's start
        dclose = fe.to_side(r, dg["close"])
        at = tips.get(int(r["game_id"]))
        pg = pregame(close, cutoff, sc.get("obs_before_cutoff_s", []), [cutoff, es, fl], at)
        if str(r.get("status")) == "void":
            st, why = "void", "void: excluded from every metric"
        elif np.isnan(close):
            st, why = _reason(fe, og, r["market"], cutoff, now)
        else:
            st, why = "ok", f"{sc['books']} book(s)"
        if gap is not None and abs(gap) > START_GAP_FLAG_MIN:
            why += (f"; tip time {tip}: the cutoff (the feed's reported start) is {abs(gap)} min "
                    f"{'before' if gap < 0 else 'after'} ESPN's scheduled start")
        if fgap is not None and abs(fgap) > START_GAP_FLAG_MIN:
            why += (f"; tip time {tip}: the cutoff is {abs(fgap)} min {'before' if fgap < 0 else 'after'} the feed's "
                    f"latest reported start (no observation carries the newer start)")
        if tip == "conflict" and not np.isnan(dclose):
            why += (f"; diagnostic close at ESPN's start: {dclose:g} ({dg['books']} book(s)), "
                    f"CLV {fe.line_value(r, dclose):+.2f} (not the protocol's CLV)")
        rows.append({"bet_id": r["bet_id"], "cohort": cohort,
                     "cutoff": cutoff.isoformat() if cutoff is not None and pd.notna(cutoff) else None,
                     "cutoff_source": src, "espn_start": es.isoformat() if es is not None and pd.notna(es) else None,
                     "start_gap_min": gap, "feed_latest_start": fl.isoformat() if fl is not None else None,
                     "feed_gap_min": fgap, "tip_check": tip, "close_primary": close, "clv_primary": clv,
                     "books_primary": sc["books"], "feed_age_s": json.dumps(sc.get("feed_age_s", [])),
                     "obs_before_cutoff_s": json.dumps(sc.get("obs_before_cutoff_s", [])),
                     "clv_status": st, "clv_reason": why,
                     "price_vs_close": json.dumps(_price_vs_close(fe, r, og, cutoff)),
                     "close_espn_start": dclose, "clv_espn_start": fe.line_value(r, dclose),
                     "books_espn_start": dg["books"], "actual_tip": at.isoformat() if at is not None else None,
                     "pregame_check": pg["check"], "pregame_note": pg["note"], "q_pregame": pg["pregame"],
                     "q_buffer": pg["buffer"], "q_near_tip": pg["near_tip"],
                     "secs_before_tip": json.dumps(pg["secs_before_tip"])})
    return pd.DataFrame(rows, columns=COLS)


def attach(b: pd.DataFrame) -> pd.DataFrame:
    """The bet log with close_line and clv_pts replaced by the primary-close values (display copy only); the
    grader's same-book values move to close_same_book / clv_same_book (diagnostic). Plays without a primary close
    show none, with clv_status and clv_reason saying why. If the observations cannot be read, every CLV shows as
    unavailable with that reason (never the grader's close)."""
    b = b.copy()
    b["close_same_book"], b["clv_same_book"] = b.get("close_line"), b.get("clv_pts")
    try:
        p = primary(b).set_index("bet_id").reindex(columns=COLS[1:])
    except Exception as e:                       # never stop a page; say so, and show no CLV
        print(f"Primary close unavailable ({e}).")
        b["close_line"], b["clv_pts"] = np.nan, np.nan
        b["clv_status"], b["clv_reason"], b["books_primary"] = "unavailable", f"observations could not be read: {e}", 0
        b.attrs["clv_source"] = "unavailable"
        return b
    for c in COLS[1:]:
        b[c] = b["bet_id"].map(p[c])
    b["close_line"], b["clv_pts"] = b["close_primary"], b["clv_primary"]
    b.loc[b["status"] != "settled", ["close_line", "clv_pts"]] = np.nan
    b.attrs["clv_source"] = "primary"
    return b


def coverage(s: pd.DataFrame) -> dict:
    """For settled plays s (attach()ed): decided plays (W or L), how many have a primary close, mean CLV over those,
    and the share. Missing closes are excluded from the mean and counted, never treated as zero."""
    d = s[s["result"].isin(["W", "L"])] if "result" in s else s.iloc[0:0]
    c = pd.to_numeric(d["clv_pts"], errors="coerce").dropna() if len(d) else pd.Series(dtype=float)
    n = int(len(d))
    known = "books_primary" in d     # book counts are on attach()ed tables; without them the split is unknown
    c2 = c[pd.to_numeric(d.loc[c.index, "books_primary"], errors="coerce") >= 2] if known else c.iloc[0:0]
    return {"decided": n, "with_close": int(len(c)), "missing": n - int(len(c)),
            "one_book": int(len(c) - len(c2)) if known else None, "two_plus": int(len(c2)) if known else None,
            "clv_two_plus": float(c2.mean()) if len(c2) else None,
            "pregame_verified": int((d.loc[c.index, "pregame_check"] == "verified").sum()) if "pregame_check" in d else None,
            "share": (len(c) / n) if n else None, "clv": float(c.mean()) if len(c) else None,
            "beat": float((c > 0).mean()) if len(c) else None}


def coverage_text(cv: dict) -> str:
    """'primary close for 7 of 8 decided plays (88%); 2+ books: 6 (+0.41), 1 book: 1', or 'no decided plays yet'.
    A one-book close is a valid primary close (the frozen rule) and is flagged, never dropped."""
    if not cv["decided"]:
        return "no decided plays yet"
    t = f"primary close for {cv['with_close']} of {cv['decided']} decided plays ({cv['share']:.0%})"
    if cv["with_close"] and cv.get("two_plus") is not None:
        two = f"{cv['clv_two_plus']:+.2f}" if cv.get("clv_two_plus") is not None else "n/a"
        t += f"; 2+ books: {cv['two_plus']} ({two}), 1 book: {cv['one_book']}"
    if cv["with_close"] and cv.get("pregame_verified") is not None:
        t += f"; pregame verified: {cv['pregame_verified']} of {cv['with_close']}"
    return t


def accepted_clv(b: pd.DataFrame, acc: pd.DataFrame) -> pd.Series:
    """Cohort C: CLV of the accepted bet's own number against the same primary close (b attach()ed). Indexed like
    acc. A play without a primary close has none."""
    from audit import forward_eval as fe
    m = acc.merge(b[["bet_id", "market", "side", "close_primary", "status"]], on="bet_id", how="left")
    out = [fe.line_value(pd.Series({"market": r["market"], "side": r["side"], "line": r["line"]}), float(r["close_primary"]))
           if r["status"] == "settled" and pd.notna(r["close_primary"]) and pd.notna(r["line"]) else np.nan
           for _, r in m.iterrows()]
    return pd.Series(out, index=acc.index, dtype=float)


def write(b: pd.DataFrame | None = None) -> pd.DataFrame:
    """Save the per-play table (bets/clv_primary.csv): every play's primary close, books, quote ages, status and
    reason, and the price comparison. Derived from the logs; rebuilt on every card run."""
    if b is None:
        from cbb import tracker
        b = tracker.load()
    from . import tipoff
    tipoff.refresh(b)
    p = primary(b)
    p.to_csv(TABLE, index=False)
    return p
