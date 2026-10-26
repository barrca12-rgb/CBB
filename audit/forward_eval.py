"""Forward-test evaluation, exactly as declared in FORWARD_TEST_PROTOCOL.md (v1.0). Written before any forward data
exists; run it unchanged at each read. Read-only.

    python -m audit.forward_eval [--through YYYY-MM-DD]

Cohort A (primary) = every signal in bets/bets.csv with logged_at on/after PROTOCOL_START, game date in the window,
status not void; voids are listed and excluded. Unit = the signal. Spreads and totals are separate; no combined
figure. Close = consensus close (closing_consensus). Line value = points our way from the logged number to that close.
ROI = flat 1 unit per signal at the logged price (-110 assumed and labelled where no price was logged); pushes return
the stake and are excluded from win %.
"""
from __future__ import annotations

import argparse
import math
import os

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
# Cohort v1 = signals logged at or after the freeze (dfb4bc7, committed 2026-10-26T19:20:50Z). Earlier signals came
# from an earlier model version (before the blended prior / opening-week rule settled) and are reported separately.
PROTOCOL_START = pd.Timestamp("2026-10-26T19:20:50Z")
FIRST_GAME, LAST_GAME = "2026-11-01", "2027-03-14"      # regular season through Selection Sunday
BOOKS = ["DraftKings", "FanDuel", "BetMGM", "Caesars", "Fanatics", "bet365", "theScore Bet"]   # odds.BOOKS, frozen
CLOSE_MAX_BEFORE_START = pd.Timedelta(minutes=60)       # a book's close counts only if observed this close to tip
DELAYS = [5, 15, 30, 60]                                # minutes after the alert
Z_INTERIM, Z_FINAL, MIN_INTERIM = 3.0, 2.50, 600        # see the protocol, section 7
RNG = np.random.default_rng(20261026)


def payout(odds) -> tuple[float, bool]:
    if odds is None or (isinstance(odds, float) and math.isnan(odds)):
        return 100 / 110, True
    o = float(odds)
    return (o / 100 if o > 0 else 100 / -o), False


def closing_consensus(closing: pd.DataFrame, bet: pd.Series) -> tuple[float, int, int]:
    """Median close of the frozen book set for the bet's game, from the bet's side. Returns (close, books used,
    books excluded as stale). Spread closes are home spreads converted to the bet's side."""
    c = closing[closing["date"] == bet["date"]]
    same = c[(c["home_id"] == bet["home_id"]) & (c["away_id"] == bet["away_id"])]
    flip = c[(c["home_id"] == bet["away_id"]) & (c["away_id"] == bet["home_id"])]
    flipped = not len(same) and len(flip) > 0
    c = (flip if flipped else same)
    c = c[c["book"].isin(BOOKS)]
    if not len(c):
        return np.nan, 0, 0
    start = pd.to_datetime(c["start"], utc=True, errors="coerce", format="ISO8601")
    seen = pd.to_datetime(c["pulled_at"], utc=True, errors="coerce", format="ISO8601")
    fresh = (start - seen) <= CLOSE_MAX_BEFORE_START
    stale = int((~fresh).sum())
    c = c[fresh]
    col = "total" if bet["market"] == "total" else "home_spread"
    v = c[col].dropna()
    if not len(v):
        return np.nan, 0, stale
    med = float(v.median())
    if bet["market"] == "spread":
        med = -med if flipped else med
        med = med if bet["side"] == "home" else -med
    return med, int(len(v)), stale


def line_value(bet: pd.Series, close: float) -> float:
    """Points the market moved our way from the logged number to the close (+ = toward our side)."""
    if np.isnan(close):
        return np.nan
    if bet["market"] == "spread":
        return float(bet["line"]) - close            # our spread got worse at the close = we got a better number
    return close - float(bet["line"]) if bet["side"] == "over" else float(bet["line"]) - close


def devig(p_ours: float, p_other: float) -> float:
    """Proportional (multiplicative) no-vig probability of our side from two American prices."""
    q = lambda o: (-o / (-o + 100)) if o < 0 else (100 / (o + 100))
    a, b = q(p_ours), q(p_other)
    return a / (a + b)


def odds_aware(a: pd.DataFrame, closing: pd.DataFrame) -> pd.DataFrame:
    """No-vig probability of our side at the logged quote vs at the same book's close, only where both sides' prices
    exist at both times and the closing number equals the logged number (no conversion between numbers)."""
    frames = []
    p = os.path.join(ROOT, "lines", "obs")
    if os.path.isdir(p):
        frames = [pd.read_csv(os.path.join(p, f)) for f in os.listdir(p) if f.endswith(".csv")]
    if not frames or not len(a):
        return pd.DataFrame()
    o = pd.concat(frames, ignore_index=True)
    o["t"] = pd.to_datetime(o["observed_at"], utc=True, errors="coerce")
    other = {"home": "away", "away": "home", "over": "under", "under": "over"}
    rows = []
    for _, b in a.iterrows():
        lo, hi = sorted((int(b["home_id"]), int(b["away_id"])))
        q = o[(o["game_key"] == f"{b['date']}|{lo}|{hi}") & (o["book"] == b["book"]) & (o["market"] == b["market"])
              & (o["t"] <= pd.Timestamp(b["logged_at"])) & (o["status"] == "available")]
        if not len(q):
            continue
        last = q[q["poll_id"] == q.sort_values("t")["poll_id"].iloc[-1]].set_index("side")
        if b["side"] not in last.index or other[b["side"]] not in last.index:
            continue
        c = closing[(closing["date"] == b["date"]) & (closing["book"] == b["book"]) &
                    (((closing["home_id"] == b["home_id"]) & (closing["away_id"] == b["away_id"])))]
        if not len(c):
            continue
        c = c.iloc[-1]
        if b["market"] == "spread":
            num = c["home_spread"] if b["side"] == "home" else -c["home_spread"]
            po, pt = (c["home_spread_odds"], c["away_spread_odds"]) if b["side"] == "home" else (c["away_spread_odds"], c["home_spread_odds"])
        else:
            num = c["total"]
            po, pt = (c["over_odds"], c["under_odds"]) if b["side"] == "over" else (c["under_odds"], c["over_odds"])
        if pd.isna(num) or float(num) != float(b["line"]) or pd.isna(po) or pd.isna(pt):
            continue
        p_log = devig(float(last.loc[b["side"], "price"]), float(last.loc[other[b["side"]], "price"]))
        rows.append({"bet_id": b["bet_id"], "market": b["market"], "p_log": p_log, "p_close": devig(float(po), float(pt))})
    return pd.DataFrame(rows)


def clustered_z(values: pd.Series, dates: pd.Series, n_boot: int = 5000) -> tuple[float, float, float]:
    """Mean, date-clustered bootstrap SE, z = mean / SE."""
    d = pd.DataFrame({"v": values.to_numpy(float), "d": dates.to_numpy()}).dropna()
    if len(d) < 2:
        return (float(d["v"].mean()) if len(d) else np.nan), np.nan, np.nan
    g = d.groupby("d")["v"].agg(["sum", "count"]).to_numpy()
    idx = RNG.integers(0, len(g), size=(n_boot, len(g)))
    s = g[idx].sum(axis=1)
    se = float(np.std(s[:, 0] / s[:, 1]))
    m = float(d["v"].mean())
    return m, se, m / se if se > 0 else np.nan


def delay_test(a: pd.DataFrame) -> pd.DataFrame:
    """Reprice each signal at the first observed quote at its book at least k minutes after its alert (ntfy send
    time, else logged_at), from lines/obs*/ (card pulls and targeted polls). A quote counts only if observed
    'available' at that poll; nothing is carried across polls. Reports fills, unavailable/stale, and no observation."""
    frames = []
    for d in ("obs", "obs_targeted"):
        p = os.path.join(ROOT, "lines", d)
        if os.path.isdir(p):
            frames += [pd.read_csv(os.path.join(p, f)) for f in os.listdir(p) if f.endswith(".csv")]
    if not frames:
        return pd.DataFrame()
    o = pd.concat(frames, ignore_index=True)
    o["t"] = pd.to_datetime(o["observed_at"], utc=True, errors="coerce")
    al = os.path.join(ROOT, "bets", "alert_log.csv")
    alerts = pd.read_csv(al) if os.path.exists(al) else pd.DataFrame(columns=["id", "channel", "sent_at", "ok"])
    sent = alerts[(alerts["channel"] == "ntfy") & alerts["ok"].astype(str).eq("True")].drop_duplicates("id").set_index("id")["sent_at"]
    rows = []
    for _, b in a.iterrows():
        t0 = pd.Timestamp(sent.get(b["bet_id"], b["logged_at"]))
        t0 = t0.tz_localize("UTC") if t0.tzinfo is None else t0
        lo, hi = sorted((int(b["home_id"]), int(b["away_id"])))
        q = o[(o["game_key"] == f"{b['date']}|{lo}|{hi}") & (o["book"] == b["book"]) & (o["market"] == b["market"])
              & (o["side"] == b["side"])].sort_values("t")
        for k in DELAYS:
            nxt = q[q["t"] >= t0 + pd.Timedelta(minutes=k)].head(1)
            if not len(nxt):
                rows.append({"bet_id": b["bet_id"], "delay": k, "outcome": "no observation"})
                continue
            r = nxt.iloc[0]
            if r["status"] != "available":
                rows.append({"bet_id": b["bet_id"], "delay": k, "outcome": f"{r['status']} at observation",
                             "elapsed_min": (r["t"] - t0).total_seconds() / 60})
                continue
            rows.append({"bet_id": b["bet_id"], "delay": k, "outcome": "filled", "elapsed_min": (r["t"] - t0).total_seconds() / 60,
                         "line": r["line"], "price": r["price"]})
        # v1.1 secondary: did ANY book in the frozen set show the logged number or better, available, at the first poll
        # at least k minutes after the alert (each book's own first observation after t0 + k)
        anyq = o[(o["game_key"] == f"{b['date']}|{lo}|{hi}") & (o["market"] == b["market"]) & (o["side"] == b["side"])]
        for k in DELAYS:
            first = anyq[anyq["t"] >= t0 + pd.Timedelta(minutes=k)].sort_values("t").drop_duplicates("book")
            ok = first[first["status"] == "available"]
            better = (ok["line"] >= float(b["line"])) if b["market"] == "spread" or b["side"] == "under" else (ok["line"] <= float(b["line"]))
            rows.append({"bet_id": b["bet_id"], "delay": k, "outcome": "any book at logged number or better" if better.any()
                         else ("no book at logged number" if len(first) else "any book: no observation")})
    return pd.DataFrame(rows)


def evaluate(through: str | None = None) -> dict:
    b = pd.read_csv(os.path.join(ROOT, "bets", "bets.csv"))
    b = b[(pd.to_datetime(b["logged_at"], utc=True) >= PROTOCOL_START) & (b["date"] >= FIRST_GAME) & (b["date"] <= LAST_GAME)]
    if through:
        b = b[b["date"] <= through]
    voids = b[b["status"] == "void"]
    a = b[b["status"] != "void"].copy()
    cl_path = os.path.join(ROOT, "lines", "closing.csv")
    closing = pd.read_csv(cl_path) if os.path.exists(cl_path) else pd.DataFrame(
        columns=["date", "home_id", "away_id", "book", "home_spread", "total", "start", "pulled_at"])
    cons = a.apply(lambda r: closing_consensus(closing, r), axis=1, result_type="expand")
    a[["close_cons", "close_books", "close_stale_books"]] = cons if len(a) else np.nan
    a["lv"] = [line_value(r, c) for (_, r), c in zip(a.iterrows(), a["close_cons"])]
    pay = a["odds"].map(lambda o: payout(o)[0])
    a["price_assumed"] = a["odds"].map(lambda o: payout(o)[1])
    a["u"] = np.where(a["result"] == "W", pay, np.where(a["result"] == "L", -1.0, 0.0))
    out = {"signals": len(a), "voids listed and excluded": len(voids)}
    for mk in ("spread", "total"):
        m = a[a["market"] == mk]
        st = m[m["status"] == "settled"]
        w, l, p = int((st["result"] == "W").sum()), int((st["result"] == "L").sum()), int((st["result"] == "P").sum())
        lv_m, lv_se, lv_z = clustered_z(m["lv"], m["date"])
        roi_m, roi_se, roi_z = clustered_z(st["u"], st["date"])
        dec = w + l
        read_through = through or pd.Timestamp.now(tz="America/New_York").strftime("%Y-%m-%d")
        phase = "final" if read_through > LAST_GAME else ("interim" if dec >= MIN_INTERIM else "descriptive only")
        zcut = Z_FINAL if phase == "final" else Z_INTERIM
        if phase == "descriptive only":
            verdict = "no inference (fewer than 600 decided signals)"
        elif lv_z >= zcut and roi_z >= zcut:
            verdict = "supported"
        elif phase == "final" and (lv_m + 1.96 * lv_se < 0 or roi_m + 1.96 * roi_se < 0):
            verdict = "contradicted"
        else:
            verdict = "inconclusive" if phase == "final" else "continue"
        out[mk] = {"selections": len(m), "settled": len(st), "W": w, "L": l, "P": p, "unsettled": int((m["status"] == "open").sum()),
                   "win%": round(100 * w / dec, 2) if dec else None,
                   "ROI% (flat 1u, logged price)": round(100 * roi_m, 2) if not np.isnan(roi_m) else None, "ROI z": round(roi_z, 2) if roi_z == roi_z else None,
                   "price assumed -110 (count)": int(st["price_assumed"].sum()),
                   "line value pts": round(lv_m, 3) if lv_m == lv_m else None, "line value z": round(lv_z, 2) if lv_z == lv_z else None,
                   "missing close (excluded)": int(m["lv"].isna().sum()),
                   "line value distribution p10/50/90": m["lv"].quantile([.1, .5, .9]).round(2).tolist() if m["lv"].notna().any() else None,
                   "phase": phase, "verdict": verdict}
    dt = delay_test(a) if len(a) else pd.DataFrame()
    out["delay test"] = dt.groupby(["delay", "outcome"]).size().to_dict() if len(dt) else \
        {"no quote log yet (all signals unobserved after the alert)": len(a)}
    oa = odds_aware(a, closing)
    out["odds-aware (same book, same number)"] = {mk: {"eligible": int((oa["market"] == mk).sum()),
                                                       "mean no-vig prob change": round(float((oa.loc[oa["market"] == mk, "p_close"] - oa.loc[oa["market"] == mk, "p_log"]).mean()), 4)}
                                                  for mk in ("spread", "total")} if len(oa) else {}
    # protocol section 3.2: a later opposite-side signal on the same game and market is flagged; sensitivity without it
    a["gm"] = a["date"].astype(str) + "|" + a["game_id"].astype(str) + "|" + a["market"]
    first = a.sort_values("logged_at").drop_duplicates("gm", keep="first")
    later = a[~a["bet_id"].isin(first["bet_id"])]
    out["opposite-side later signals (flagged)"] = len(later)
    if len(later):
        for mk in ("spread", "total"):
            f = first[(first["market"] == mk) & (first["status"] == "settled")]
            out[f"{mk} ROI% without later opposite-side signals"] = round(100 * f["u"].mean(), 2) if len(f) else None
    # cohorts B and C (protocol section 2)
    sl = os.path.join(ROOT, "bets", "signal_log.csv")
    sig = pd.read_csv(sl).drop_duplicates("bet_id").set_index("bet_id") if os.path.exists(sl) else pd.DataFrame()
    if len(sig):
        age = pd.to_numeric(a["bet_id"].map(sig["quote_age_s"]), errors="coerce")
        in_b = (a["bet_id"].map(sig["quote_status"]) == "available") & (age <= 600)
    else:
        in_b = pd.Series(False, index=a.index)
    acc_p = os.path.join(ROOT, "bets", "accepted.csv")
    acc = pd.read_csv(acc_p) if os.path.exists(acc_p) else pd.DataFrame(columns=["bet_id"])
    for name, sub in (("B", a[in_b]), ("C", a[a["bet_id"].isin(acc["bet_id"])])):
        st = sub[sub["status"] == "settled"]
        out[f"cohort {name}"] = {"signals": len(sub), "settled": len(st), "W-L-P": f"{(st['result'] == 'W').sum()}-{(st['result'] == 'L').sum()}-{(st['result'] == 'P').sum()}",
                                 "ROI% (logged price)": round(100 * st["u"].mean(), 2) if len(st) else None,
                                 "line value pts": round(float(sub["lv"].mean()), 3) if sub["lv"].notna().any() else None}
    out["cohort B excluded: no quote record"] = int((~a["bet_id"].isin(sig.index)).sum()) if len(sig) else len(a)
    pre = pd.read_csv(os.path.join(ROOT, "bets", "bets.csv"))
    pre = pre[pd.to_datetime(pre["logged_at"], utc=True) < PROTOCOL_START]
    out["pre-freeze signals (reported separately, not in v1)"] = {"signals": len(pre), "voids": int((pre["status"] == "void").sum())}
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--through")
    import json
    print(json.dumps(evaluate(ap.parse_args().through), indent=1, default=str))
