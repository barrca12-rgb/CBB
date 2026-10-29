"""Opener speed: which feed sees a new opener first, and how fast the card alerts it (research only, read-only).

Reads the repository's own logs and git history; calls no API and writes only under research/speed/out/.

  lines/closing.csv git history   every committed version is one card-run pull (research/power/closing_history.py
                                  explains why). Rows of the current pull are those whose pulled_at equals the
                                  version's latest pulled_at. A row's source is The Odds API when sgo_event starts
                                  with "oa:", else SportsGameOdds (SGO). odds.pull keeps an Odds API row only where
                                  SGO has no line for that game and book, so an Odds API row is hidden on the runs
                                  where SGO was pulled and had the line; SGO-skipped runs (2 of 3) show its full set.
  lines/polls.csv                 every card-run poll attempt per feed (ok / skipped / error), cost, credits left
  lines/polls_targeted.csv        targeted 3-minute polls (2 credits each)
  lines/obs*/, bets/signal_log.csv  the feeds' own timestamps (Odds API last_update, SGO lastUpdatedAt), watched games only
  bets/bets.csv, bets/alert_log.csv  logged_at = alert time (alert_log's ntfy send time shown alongside)

An opener is the first card run at which a (game, book, market) has a number. "Bracket" = the time since that same
feed's previous successful poll, which did not have it: the book's posting time lies inside it, so it bounds the
unobserved part of the lag.

    python -m research.speed.measure                 # writes research/speed/out/*.csv and out/measure.txt
    python -m research.speed.measure --since 2026-11-01T00:00Z
"""
from __future__ import annotations

import argparse
import io
import os
import subprocess

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LINES = os.path.join(ROOT, "lines")
OUT = os.path.join(os.path.dirname(__file__), "out")
CACHE = os.path.join(OUT, "pulls.parquet")
ET = "America/New_York"
SINCE = "2026-10-26T00:00:00Z"
SGO_END = pd.Timestamp("2026-11-25T00:00:00Z")
RESEARCH_FLOOR = 50_000
SGO_MONTH = 100_000          # update.yml comment: Rookie plan, 100,000 entities a month, shared with the NFL model
ODDS_API_MONTH = 100_000     # audit/OPERATIONS.md: 100,000 credits a month, renews Nov 25
# Commits that change what the card logs (model, rules, line handling). A late alert with one of these between the
# line's first sighting and the alert was triggered by the change, not by polling.
MODEL_PATHS = ["cbb", "data/projection.json"]


def _git(*a) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def q(s: pd.Series, p: float) -> float:
    s = pd.Series(s).dropna()
    return float(np.percentile(s, p)) if len(s) else float("nan")


def dist(s: pd.Series) -> dict:
    s = pd.Series(s).dropna()
    return {"n": len(s), "median": q(s, 50), "p75": q(s, 75), "p90": q(s, 90), "max": float(s.max()) if len(s) else np.nan}


# ---------------------------------------------------------------- data
def pulls(refresh: bool = True) -> pd.DataFrame:
    """One row per (card-run pull, book, game) from every committed lines/closing.csv (cached incrementally)."""
    old = pd.read_parquet(CACHE) if os.path.exists(CACHE) else pd.DataFrame()
    done = set(old["commit"]) if len(old) else set()
    if refresh:
        parts = []
        for line in _git("log", "--format=%H %cI", "--", "lines/closing.csv").splitlines():
            c, t = line.split()
            if c in done:
                continue
            try:
                d = pd.read_csv(io.StringIO(_git("show", f"{c}:lines/closing.csv")))
            except Exception:
                continue
            if not len(d) or "pulled_at" not in d:
                continue
            d = d[d["pulled_at"] == d["pulled_at"].max()].assign(commit=c, committed=t)
            parts.append(d)
        if parts:
            old = pd.concat([old] + parts, ignore_index=True) if len(old) else pd.concat(parts, ignore_index=True)
            os.makedirs(OUT, exist_ok=True)
            old.to_parquet(CACHE, index=False)
    h = old.drop_duplicates(["pulled_at", "book", "home_id", "away_id"]).copy()
    h["t"] = pd.to_datetime(h["pulled_at"], utc=True, format="ISO8601")
    h["src"] = np.where(h["sgo_event"].astype(str).str.startswith("oa:"), "oddsapi", "sgo")
    day = pd.to_datetime(h["start"], utc=True, format="ISO8601").dt.tz_convert(ET).dt.strftime("%Y-%m-%d")
    lo = np.minimum(h["home_id"], h["away_id"]).astype(int).astype(str)
    hi = np.maximum(h["home_id"], h["away_id"]).astype(int).astype(str)
    h["game_key"] = day + "|" + lo + "|" + hi
    return h


def polls() -> pd.DataFrame:
    p = pd.read_csv(os.path.join(LINES, "polls.csv"))
    p["t"] = pd.to_datetime(p["observed_at"], utc=True, format="ISO8601")
    return p


def feed_polls(h: pd.DataFrame, p: pd.DataFrame) -> dict:
    """Successful poll times per feed: polls.csv where it exists, else card runs whose pull had that feed's rows."""
    first_log = p["t"].min()
    out = {}
    for src in ("sgo", "oddsapi"):
        logged = p[(p["source"] == src) & (p["status"] == "ok")]["t"]
        early = h[(h["src"] == src) & (h["t"] < first_log)]["t"]
        out[src] = pd.Series(sorted(set(early) | set(logged))).reset_index(drop=True)
    return out


def card_runs(h: pd.DataFrame) -> pd.Series:
    return pd.Series(sorted(h["t"].unique()))


def model_commits() -> pd.Series:
    t = _git("log", "--format=%cI", "--", *MODEL_PATHS).split()
    return pd.Series(pd.to_datetime(t, utc=True, format="ISO8601")).sort_values().reset_index(drop=True)


# ---------------------------------------------------------------- 1. openers
def openers(h: pd.DataFrame, fp: dict) -> pd.DataFrame:
    """One row per (game, book, market): first card run with a number, which feed, each feed's first sighting, the
    bracket (that feed's previous ok poll), and the feed's own timestamp where the quote log has one."""
    rows = []
    long = []
    for mk, col in (("spread", "home_spread"), ("total", "total")):
        d = h.dropna(subset=[col])[["game_key", "book", "src", "t", "start"]].assign(market=mk)
        long.append(d)
    d = pd.concat(long, ignore_index=True)
    first_pull = {s: v.min() for s, v in fp.items()}
    for (gk, bk, mk), g in d.groupby(["game_key", "book", "market"]):
        g = g.sort_values("t")
        t0, src = g["t"].iloc[0], g["src"].iloc[0]
        by = g.groupby("src")["t"].min()
        prev = fp[src][fp[src] < t0]
        r = {"game_key": gk, "book": bk, "market": mk, "first_run": t0, "first_feed": src,
             "first_sgo": by.get("sgo", pd.NaT), "first_oddsapi": by.get("oddsapi", pd.NaT),
             "prev_poll_same_feed": prev.max() if len(prev) else pd.NaT,
             "start": pd.Timestamp(g["start"].iloc[0])}
        # left-censored: first sighting at the feed's first-ever poll (the line may have been up for days)
        r["censored"] = bool(t0 <= first_pull[src] + pd.Timedelta(seconds=1)) or pd.isna(r["prev_poll_same_feed"])
        r["bracket_min"] = (t0 - r["prev_poll_same_feed"]).total_seconds() / 60 if not r["censored"] else np.nan
        both = pd.notna(r["first_sgo"]) and pd.notna(r["first_oddsapi"])
        r["lead_min"] = abs((r["first_sgo"] - r["first_oddsapi"]).total_seconds()) / 60 if both else np.nan
        r["leader"] = ("sgo" if r["first_sgo"] < r["first_oddsapi"] else "oddsapi") if both else f"{src} only"
        rows.append(r)
    o = pd.DataFrame(rows)
    o["first_run_et"] = o["first_run"].dt.tz_convert(ET)
    o["hour_et"] = o["first_run_et"].dt.hour
    o["day_et"] = o["first_run_et"].dt.strftime("%Y-%m-%d")
    o["hours_before_tip"] = (pd.to_datetime(o["start"], utc=True) - o["first_run"]).dt.total_seconds() / 3600
    return o


def feed_timestamps(o: pd.DataFrame) -> pd.DataFrame:
    """The feed's own timestamp of an opener's quote, where the quote log captured that pull (watched games only)."""
    frames = []
    for sub in ("obs", "obs_targeted"):
        p = os.path.join(LINES, sub)
        for f in sorted(os.listdir(p)) if os.path.isdir(p) else []:
            if f.endswith((".csv", ".csv.gz")):
                frames.append(pd.read_csv(os.path.join(p, f)))
    if not frames:
        return o.assign(feed_ts=pd.NaT, feed_observed=pd.NaT)
    ob = pd.concat(frames, ignore_index=True)
    ob = ob[ob["status"] == "available"].copy()
    ob["obs_t"] = pd.to_datetime(ob["observed_at"], utc=True, format="ISO8601")
    ob["upd"] = pd.to_datetime(ob["source_updated_at"], utc=True, errors="coerce", format="ISO8601")
    ob = ob.sort_values("obs_t").drop_duplicates(["game_key", "book", "market"])   # earliest logged quote
    m = o.merge(ob[["game_key", "book", "market", "obs_t", "upd", "source"]], on=["game_key", "book", "market"], how="left")
    same_pull = (m["obs_t"] <= m["first_run"]) & (m["first_run"] - m["obs_t"] <= pd.Timedelta(minutes=3))
    m["feed_ts"] = m["upd"].where(same_pull)
    m["feed_observed"] = m["obs_t"].where(same_pull)
    return m.drop(columns=["obs_t", "upd", "source"])


# ---------------------------------------------------------------- alerts
def alerts(h: pd.DataFrame, fp: dict, o: pd.DataFrame, mc: pd.Series) -> pd.DataFrame:
    b = pd.read_csv(os.path.join(ROOT, "bets", "bets.csv"))
    b["logged"] = pd.to_datetime(b["logged_at"], utc=True, format="ISO8601")
    al = pd.read_csv(os.path.join(ROOT, "bets", "alert_log.csv")) if os.path.exists(
        os.path.join(ROOT, "bets", "alert_log.csv")) else pd.DataFrame(columns=["id", "channel", "sent_at", "ok"])
    al = al[(al["channel"] == "ntfy") & al["ok"].astype(str).eq("True")]
    sent = dict(zip(al["id"], pd.to_datetime(al["sent_at"], utc=True, format="ISO8601")))
    sl = os.path.join(ROOT, "bets", "signal_log.csv")
    sig = pd.read_csv(sl).set_index("bet_id") if os.path.exists(sl) else pd.DataFrame()
    rows = []
    for _, r in b.iterrows():
        lo, hi = sorted((int(r["home_id"]), int(r["away_id"])))
        # the feed's start can fall on the next ET date (late tips): match the teams within a day of the bet's date
        near = {f"{(pd.Timestamp(r['date']) + pd.Timedelta(days=k)):%Y-%m-%d}|{lo}|{hi}" for k in (-1, 0, 1)}
        g = h[h["game_key"].isin(near) & (h["book"] == r["book"])].sort_values("t")
        gk = g["game_key"].iloc[0] if len(g) else f"{r['date']}|{lo}|{hi}"
        same = g["home_id"].astype(int) == int(r["home_id"])
        if r["market"] == "spread":
            home_line = np.where(same, g["home_spread"], -g["home_spread"])
            line = home_line if r["side"] == "home" else -home_line
        else:
            line = g["total"].to_numpy()
        g = g.assign(bet_side_line=line)
        hit = g[np.isclose(g["bet_side_line"].astype(float), float(r["line"]), equal_nan=False)]
        hit = hit[hit["t"] <= r["logged"] + pd.Timedelta(seconds=5)]
        op = o[(o["game_key"] == gk) & (o["book"] == r["book"]) & (o["market"] == r["market"])]
        first_line = hit["t"].min() if len(hit) else pd.NaT
        src = hit["src"].iloc[0] if len(hit) else None
        prev = fp[src][fp[src] < first_line] if src else pd.Series(dtype="datetime64[ns, UTC]")
        opening = g.dropna(subset=["bet_side_line"])
        is_opener = bool(len(opening)) and np.isclose(float(opening["bet_side_line"].iloc[0]), float(r["line"]))
        changes = mc[(mc > first_line) & (mc < r["logged"])] if pd.notna(first_line) else mc.iloc[:0]
        q_upd = pd.to_datetime(sig["quote_source_updated_at"].get(r["bet_id"]), utc=True, errors="coerce") \
            if len(sig) and r["bet_id"] in sig.index else pd.NaT
        rows.append({
            "bet_id": r["bet_id"], "status": r["status"], "book": r["book"], "market": r["market"], "pick": r["pick"],
            "line": r["line"], "logged_at": r["logged"], "ntfy_sent": sent.get(r["bet_id"], pd.NaT),
            "first_quote_of_line": first_line, "feed": src, "opener_line": is_opener,
            "book_first_run": op["first_run"].min() if len(op) else pd.NaT,
            "censored": bool(op["censored"].any()) if len(op) else True,
            "lag_min": (r["logged"] - first_line).total_seconds() / 60 if pd.notna(first_line) else np.nan,
            "lag_upper_min": (r["logged"] - prev.max()).total_seconds() / 60 if len(prev) else np.nan,
            "feed_ts_to_alert_min": (r["logged"] - q_upd).total_seconds() / 60 if pd.notna(q_upd) else np.nan,
            "model_changes_between": len(changes),
        })
    a = pd.DataFrame(rows)
    a["hour_et"] = a["first_quote_of_line"].dt.tz_convert(ET).dt.hour
    a["cause"] = np.where(a["model_changes_between"] > 0, "rule/model change", "polling")
    return a


# ---------------------------------------------------------------- 3. latency from the achieved cadence
def _secs(times: pd.Series) -> np.ndarray:
    return ((pd.to_datetime(times, utc=True) - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()).to_numpy()


def residual_delay(times: pd.Series, start: pd.Timestamp, end: pd.Timestamp, step_s: int = 10) -> np.ndarray:
    """Minutes from a uniformly random posting instant in [start, end) to the feed's next successful poll."""
    t = np.sort(_secs(times[(times >= start) & (times <= end)]))
    if len(t) < 2:
        return np.array([])
    grid = np.arange(t[0], t[-1], step_s)
    nxt = t[np.searchsorted(t, grid, side="left")]
    return (nxt - grid) / 60


def latency_table(fp: dict, start: pd.Timestamp, end: pd.Timestamp, hours: list[int] | None) -> pd.DataFrame:
    rows = []
    sgo, oa = fp["sgo"], fp["oddsapi"]
    both = pd.Series(sorted(set(sgo) | set(oa)))
    for name, times in (("SGO alone, as polled (every ~30 min)", sgo),
                        ("The Odds API alone, as polled (every ~10 min)", oa),
                        ("Either feed, as polled now", both)):
        d = residual_delay(times, start, end)
        if hours is not None and len(d):
            t = np.sort(_secs(times[(times >= start) & (times <= end)]))
            grid = np.arange(t[0], t[-1], 10)
            hr = pd.to_datetime(grid, unit="s", utc=True).tz_convert(ET).hour
            d = d[np.isin(hr, hours)]
        rows.append({"scenario": name, **dist(d)})
    for name, every in (("The Odds API every 3 min (proposal)", 3.0),):
        d = np.arange(0, every * 60, 10) / 60
        rows.append({"scenario": name, **dist(d)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 4. credits
def credits(p: pd.DataFrame, busiest: list[int]) -> dict:
    ok = p[p["status"] == "ok"]
    oa = ok[ok["source"] == "oddsapi"]
    sg = ok[ok["source"] == "sgo"]
    tp = pd.read_csv(os.path.join(LINES, "polls_targeted.csv"))
    oa_cost = float(oa["cost"].median())
    tgt_cost = float(tp["cost"].median()) if len(tp) else 2.0
    sgo_cost = sg["cost"].astype(float)
    # achieved calls per hour in the busiest window now
    oa_t = oa["t"].dt.tz_convert(ET)
    days = max(oa_t.dt.normalize().nunique(), 1)
    sg_t = sg["t"].dt.tz_convert(ET)
    in_w = lambda s: s.dt.hour.isin(busiest)
    oa_now = in_w(oa_t).sum() / max((oa_t.dt.normalize()[in_w(oa_t)]).nunique(), 1)
    sg_now = in_w(sg_t).sum() / max((sg_t.dt.normalize()[in_w(sg_t)]).nunique(), 1)
    w = len(busiest)
    calls3 = w * 60 / 3
    usage = os_json(os.path.join(LINES, "odds_api_usage.json"))
    # SGO entities used per day by everyone (our pulls plus the NFL model), from the logged balance
    sgr = sg.dropna(subset=["remaining"])
    sgo_rate = ((sgr["remaining"].iloc[0] - sgr["remaining"].iloc[-1]) /
                ((sgr["t"].iloc[-1] - sgr["t"].iloc[0]).total_seconds() / 86400)) if len(sgr) > 1 else np.nan
    our_sgo_rate = sg["cost"].sum() / ((sg["t"].iloc[-1] - sg["t"].iloc[0]).total_seconds() / 86400) if len(sg) > 1 else np.nan
    return {"oa_cost": oa_cost, "tgt_cost": tgt_cost, "sgo_cost_median": float(sgo_cost.median()),
            "sgo_cost_max": float(sgo_cost.max()), "oa_calls_now_window": oa_now, "sgo_calls_now_window": sg_now,
            "window_hours": w, "calls_3min": calls3, "oa_remaining": usage.get("remaining"),
            "oa_remaining_at": usage.get("at"), "sgo_remaining": float(sgr["remaining"].iloc[-1]) if len(sgr) else np.nan,
            "sgo_rate_all": sgo_rate, "sgo_rate_ours": our_sgo_rate, "oa_calls_per_day_all": len(oa) / days}


def os_json(path: str) -> dict:
    import json
    try:
        return json.load(open(path))
    except Exception:
        return {}


# ---------------------------------------------------------------- report
def fmt(x, d=1):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:,.{d}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=SINCE)
    ap.add_argument("--no-refresh", action="store_true")
    a = ap.parse_args()
    since = pd.Timestamp(a.since)
    h = pulls(refresh=not a.no_refresh)
    p = polls()
    fp = feed_polls(h, p)
    mc = model_commits()
    o_all = feed_timestamps(openers(h, fp))
    o = o_all[o_all["first_run"] >= since].copy()
    al = alerts(h, fp, o_all, mc)
    al = al[al["logged_at"] >= since].copy()
    os.makedirs(OUT, exist_ok=True)
    o.to_csv(os.path.join(OUT, "openers.csv"), index=False)
    al.to_csv(os.path.join(OUT, "alerts.csv"), index=False)
    L = []
    w = L.append
    runs = card_runs(h)
    w(f"Data: {len(runs)} committed card-run pulls {runs.min():%Y-%m-%d %H:%M} to {runs.max():%Y-%m-%d %H:%M} UTC; "
      f"window from {since:%Y-%m-%d %H:%M} UTC. Feed polls ok: SGO {len(fp['sgo'])}, The Odds API {len(fp['oddsapi'])}.")
    gaps = runs.diff().dt.total_seconds().div(60)
    w(f"Card-run gaps (min): median {fmt(gaps.median())}, p90 {fmt(q(gaps, 90))}, max {fmt(gaps.max())}.")
    for s in ("sgo", "oddsapi"):
        gg = fp[s].diff().dt.total_seconds().div(60)
        gg = gg[fp[s] >= since]
        w(f"{s} poll gaps (min): median {fmt(gg.median())}, p90 {fmt(q(gg, 90))}, max {fmt(gg.max())}")

    w("\n## 1a. Openers (game, book, market): first card run and feed")
    cols = ["game_key", "book", "market", "first_run_et", "first_feed", "first_sgo", "first_oddsapi", "leader",
            "lead_min", "bracket_min", "censored", "feed_ts", "hours_before_tip"]
    t = o[cols].copy()
    for c in ("first_sgo", "first_oddsapi", "feed_ts"):
        t[c] = pd.to_datetime(t[c], utc=True).dt.tz_convert(ET).dt.strftime("%m-%d %H:%M").fillna("-")
    t["first_run_et"] = t["first_run_et"].dt.strftime("%m-%d %H:%M")
    w(t.sort_values(["first_run_et", "book", "game_key", "market"]).to_string(index=False, float_format=lambda x: f"{x:.1f}"))
    w(f"\nOpeners in window: {len(o)} (game-book-market) = {o.groupby(['game_key', 'book']).ngroups} game-books, "
      f"{o['game_key'].nunique()} games, {o.groupby(['book', 'first_run']).ngroups} posting batches (book x run). "
      f"Left-censored (first sighting at the feed's first poll): {int(o['censored'].sum())}.")
    gb = o.sort_values("first_run").drop_duplicates(["game_key", "book"])
    bt = gb.groupby(["first_run", "book", "first_feed"]).agg(
        games=("game_key", "nunique"), bracket_min=("bracket_min", "max"), censored=("censored", "all"),
        feed_ts=("feed_ts", "min"), tip_h=("hours_before_tip", "median")).reset_index()
    bt["card_run_et"] = bt["first_run"].dt.tz_convert(ET).dt.strftime("%a %m-%d %H:%M:%S")
    bt["feed_ts_et"] = pd.to_datetime(bt["feed_ts"], utc=True).dt.tz_convert(ET).dt.strftime("%H:%M:%S").fillna("-")
    w("\nPosting batches (book x first card run), game-books:")
    w(bt[["card_run_et", "book", "first_feed", "games", "feed_ts_et", "bracket_min", "censored", "tip_h"]]
      .to_string(index=False, float_format=lambda x: f"{x:.1f}"))
    w("First feed per game-book: " + ", ".join(f"{k} {v}" for k, v in gb["first_feed"].value_counts().items()))
    bothf = gb[gb["leader"].isin(["sgo", "oddsapi"])]
    w(f"Game-books seen on both feeds: {len(bothf)}; leader: " +
      ", ".join(f"{k} {v}" for k, v in bothf["leader"].value_counts().items()) +
      "; lead minutes: " + ", ".join(f"{r.book} {r.game_key} {r.leader} by {r.lead_min:.0f}" for r in bothf.itertuples()))
    unc = o[~o["censored"]].sort_values("first_run").drop_duplicates(["game_key", "book"])   # game-books
    w(f"Bracket (minutes since that feed's previous poll without the line), uncensored game-books n={len(unc)}: " +
      ", ".join(f"{k} {fmt(v)}" for k, v in dist(unc["bracket_min"]).items() if k != "n"))
    ft = o.dropna(subset=["feed_ts"])
    w(f"Openers with the feed's own timestamp in the quote log: {len(ft)}" +
      ("".join(f"; {r.book} {r.game_key} {r.market}: feed {r.feed_ts:%H:%M:%S} UTC, card run {r.first_run:%H:%M:%S}"
               for r in ft.itertuples())))

    w("\n## 1b. Alerts in bets/bets.csv: first quote of the alerted line -> logged_at")
    ac = ["bet_id", "status", "book", "pick", "opener_line", "first_quote_of_line", "logged_at", "lag_min",
          "lag_upper_min", "feed_ts_to_alert_min", "model_changes_between", "cause", "censored"]
    t = al[ac].copy()
    for c in ("first_quote_of_line", "logged_at"):
        t[c] = t[c].dt.tz_convert(ET).dt.strftime("%m-%d %H:%M:%S")
    w(t.to_string(index=False, float_format=lambda x: f"{x:.1f}"))
    live = al[al["status"] != "void"]
    op = live[live["opener_line"]]
    w("\nLag distribution (minutes), alerts at the book's opening number, voids excluded:")
    rows = [("all opener alerts", op), ("cause = polling (no model/rule change between)", op[op["cause"] == "polling"]),
            ("cause = rule/model change", op[op["cause"] != "polling"])]
    tab = pd.DataFrame([{"group": g, **dist(d["lag_min"]), "upper_median": q(d["lag_upper_min"], 50),
                         "upper_p90": q(d["lag_upper_min"], 90)} for g, d in rows])
    w(tab.to_string(index=False, float_format=lambda x: f"{x:.1f}"))
    w("\nNov 12 rule check (median > 5 or p90 > 20 minutes, first quote of the line -> logged_at, opener alerts, no voids):")
    for lab, d in (("window", op), ("in-season (logged from Nov 1 ET)", op[op["logged_at"] >= pd.Timestamp("2026-11-01T04:00Z")])):
        dd = dist(d["lag_min"])
        fire = dd["n"] > 0 and (dd["median"] > 5 or dd["p90"] > 20)
        w(f"  {lab}: n={dd['n']}, median {fmt(dd['median'])}, p90 {fmt(dd['p90'])} -> "
          f"{'TRIGGER' if fire else ('no trigger' if dd['n'] else 'no data')}")
    w("\nBy ET hour of the first quote (opener alerts):")
    w(op.groupby("hour_et")["lag_min"].agg(["count", "median", lambda s: q(s, 75), lambda s: q(s, 90)])
      .set_axis(["n", "median", "p75", "p90"], axis=1).to_string(float_format=lambda x: f"{x:.1f}"))
    w("\nBy book (opener alerts):")
    w(op.groupby("book")["lag_min"].agg(["count", "median", lambda s: q(s, 75), lambda s: q(s, 90)])
      .set_axis(["n", "median", "p75", "p90"], axis=1).to_string(float_format=lambda x: f"{x:.1f}"))
    w("\nOpener detection bracket (unobserved part, minutes) by ET hour and by book, uncensored openers:")
    for k in ("hour_et", "book"):
        w(unc.groupby(k)["bracket_min"].agg(["count", "median", lambda s: q(s, 75), lambda s: q(s, 90)])
          .set_axis(["n", "median", "p75", "p90"], axis=1).to_string(float_format=lambda x: f"{x:.1f}"))

    w("\n## 2. When openers post (first card run, ET hour); uncensored game-books (spread and total post together)")
    hist = unc.groupby("hour_et").size().reindex(range(24), fill_value=0)
    batches = unc.drop_duplicates(["book", "first_run"]).groupby("hour_et").size().reindex(range(24), fill_value=0)
    w(pd.DataFrame({"openers": hist, "batches": batches}).T.to_string())
    top3 = hist.sort_values(ascending=False, kind="stable").index[:3].tolist()
    share = hist[top3].sum() / max(hist.sum(), 1)
    roll = pd.Series([hist[[(h0 + i) % 24 for i in range(3)]].sum() for h0 in range(24)])
    h0 = int(roll.idxmax())
    w(f"Busiest three hours (any): {sorted(top3)} ET = {share:.0%} of {int(hist.sum())} openers. "
      f"Busiest contiguous 3 hours: {h0}:00-{(h0 + 3) % 24}:00 ET = {roll.max() / max(hist.sum(), 1):.0%}.")
    per_day = []
    for d, g in unc.groupby("day_et"):
        hh = g.groupby("hour_et").size()
        per_day.append({"day_et": d, "openers": len(g), "top3_share": hh.sort_values(ascending=False).iloc[:3].sum() / len(g),
                        "busiest_hours": ",".join(str(x) for x in hh.sort_values(ascending=False).index[:3])})
    w(pd.DataFrame(per_day).to_string(index=False, float_format=lambda x: f"{x:.0%}"))
    w(f"Hours before tip at first sighting: median {fmt(unc['hours_before_tip'].median())}, "
      f"min {fmt(unc['hours_before_tip'].min())}.")

    w("\n## 3. Effective opener latency from the achieved cadence (minutes from posting to the next poll that has it)")
    start, end = max(since, fp["sgo"].min()), min(fp["sgo"].max(), fp["oddsapi"].max())
    w("All hours:")
    w(latency_table(fp, start, end, None).to_string(index=False, float_format=lambda x: f"{x:.1f}"))
    win = sorted({(h0 + i) % 24 for i in range(3)})
    w(f"Busiest contiguous window {win} ET:")
    w(latency_table(fp, start, end, win).to_string(index=False, float_format=lambda x: f"{x:.1f}"))
    led = gb[gb["leader"] == "sgo"]
    w(f"Lines SGO had first ({len(led)} game-books): The Odds API showed them {', '.join(f'{x:.0f}' for x in led['lead_min'])} "
      "minutes later. After Nov 25 (The Odds API alone) such a line is first seen that much later, plus the poll delay.")
    gen = pd.read_csv(os.path.join(ROOT, "bets", "signal_log.csv")) if os.path.exists(
        os.path.join(ROOT, "bets", "signal_log.csv")) else pd.DataFrame()
    if len(gen):
        s = (pd.to_datetime(gen["logged_at"], utc=True) - pd.to_datetime(gen["lines_pulled_at"], utc=True)).dt.total_seconds()
        w(f"Card processing (lines pulled -> logged_at), n={len(s)}: median {s.median():.0f} s.")
    oaobs = []
    for sub in ("obs", "obs_targeted"):
        pth = os.path.join(LINES, sub)
        for f in sorted(os.listdir(pth)) if os.path.isdir(pth) else []:
            if f.endswith((".csv", ".csv.gz")):
                oaobs.append(pd.read_csv(os.path.join(pth, f)))
    if oaobs:
        ob = pd.concat(oaobs)
        ob = ob[(ob["status"] == "available")]
        for s_, g in ob.groupby("source"):
            w(f"Feed timestamp age at our poll ({s_}, quote_age_s, n={len(g)}): median {g['quote_age_s'].median():.0f} s, "
              f"p90 {q(g['quote_age_s'], 90):.0f} s.")

    w("\n## 4. Credits for a 3-minute cadence in the busiest window")
    c = credits(p, win)
    for k, v in c.items():
        w(f"  {k}: {v}")
    extra_calls = c["calls_3min"] - c["oa_calls_now_window"]
    w(f"The Odds API: {c['calls_3min']:.0f} calls/day in the window at 3 min vs {c['oa_calls_now_window']:.1f} now: "
      f"+{extra_calls:.0f} calls = +{extra_calls * c['oa_cost']:.0f} credits/day at {c['oa_cost']:.0f} per card call "
      f"(+{extra_calls * c['tgt_cost']:.0f} with the {c['tgt_cost']:.0f}-credit spreads+totals call); "
      f"30 days: +{30 * extra_calls * c['oa_cost']:,.0f} of {ODDS_API_MONTH:,}.")
    sg_extra = c["calls_3min"] - c["sgo_calls_now_window"]
    w(f"SGO: +{sg_extra:.0f} calls/day x entities per call ({c['sgo_cost_median']:.0f} now, about 200 in season per "
      f"update.yml) = +{sg_extra * c['sgo_cost_median']:,.0f} to +{sg_extra * 200:,.0f} entities/day vs a "
      f"{SGO_MONTH:,}/month plan shared with the NFL model (current use, all consumers: {c['sgo_rate_all']:,.0f}/day).")
    txt = "\n".join(L)
    with open(os.path.join(OUT, "measure.txt"), "w") as f:
        f.write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
