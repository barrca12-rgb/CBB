"""Daily CBB bet card as a self-contained HTML page: today's plays, the odds board, the record and the ratings.

Laid out like a sportsbook odds screen: one typeface with tabular figures, neutral surfaces, color only where it
means something (best number, edge, win/loss). Light and dark follow the viewer's system setting. The Update button
works like the NFL card's (GitHub Actions workflow dispatch with a token kept in the browser). No external
dependencies except the Inter font (with system fallbacks).
"""
from __future__ import annotations

import html
import json
import math
import os

import numpy as np
import pandas as pd

from cbb import autorefresh

REPO = "barrca12-rgb/CBB"
NFL_SITE = "https://barrca12-rgb.github.io/NFL/"
NBA_SITE = "https://barrca12-rgb.github.io/NBA/"
# NBA tab stays hidden until the NBA page answers (same origin, so a HEAD request works from the browser)
NBA_TAB = (f'<a id="nba-link" href="{NBA_SITE}" hidden>NBA</a>'
           f'<script>fetch("{NBA_SITE}", {{method: "HEAD", cache: "no-store"}}).then((r) => {{ if (r.ok) document.getElementById("nba-link").hidden = false; }}).catch(() => {{}});</script>')
SITE_URL = "https://barrca12-rgb.github.io/CBB/"
X_HANDLE = "OffTheGlassHQ"
# Off The Glass brand: shared <head> for the card and the record page (icons, link previews on X, fonts)
HEAD = f"""<meta name="description" content="Off The Glass: a college basketball betting model. Every play logged at the posted number, graded in public.">
<meta name="theme-color" content="#0A2C49">
<link rel="icon" type="image/png" sizes="32x32" href="assets/favicon-32.png">
<link rel="icon" type="image/png" sizes="64x64" href="assets/favicon-64.png">
<link rel="apple-touch-icon" href="assets/apple-touch-icon.png">
<meta property="og:site_name" content="Off The Glass">
<meta property="og:type" content="website">
<meta property="og:image" content="{SITE_URL}assets/otg-social.jpg">
<meta property="og:description" content="College basketball model: every play logged at the posted number, graded in public.">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@{X_HANDLE}">
<meta name="twitter:image" content="{SITE_URL}assets/otg-social.jpg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Graduate&family=Inter:wght@400;500;600;700;800&display=swap">"""
BRAND = ('<a class="brand" href="./" aria-label="Off The Glass home"><img src="assets/otg-logo-512.png" alt="" width="34" height="34">'
         '<span class="wordmark">Off The Glass</span></a>')


def _clean(v):
    if v is None:
        return None
    if isinstance(v, list):
        return [{k: _clean(x) for k, x in o.items()} for o in v]
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, (np.floating, float)):
        return None if math.isnan(v) else round(float(v), 3)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return v if isinstance(v, (int, str, bool)) else str(v)


REVISION = pd.Timestamp("2026-10-26T17:20:00Z")   # both Oct 26 model changes live (MODEL_FREEZE.md announcements)


def _logged_view(card: pd.DataFrame) -> pd.DataFrame:
    """Win chance and EV of each logged play as they were when it was logged: the frozen win-chance table applied to
    the logged edge, at the logged price (run_day's own functions, read-only). Display only."""
    from .run_day import ev, win_prob
    from . import tracker
    card = card.copy()
    try:
        b = tracker.load("v1_logged")   # every logged play (pre-rule line-move plays show in their own block)
        b = b[b["status"] != "void"]
    except Exception:
        b = None
    for mk in ("spread", "total"):
        e, o = f"{mk}_logged_edge", f"{mk}_logged_odds"
        if e not in card:
            continue
        p = [win_prob(mk, float(x)) if pd.notna(x) else np.nan for x in card[e]]
        card[f"{mk}_logged_p"] = p
        card[f"{mk}_logged_ev"] = [ev(pp, oo) if pd.notna(pp) and pd.notna(oo) else np.nan for pp, oo in zip(p, card[o])]
        # logged before the Oct 26 revision (preseason prior + opening-week totals rule): the card shows the edge
        # against today's model for these (Chad, Oct 27); the bet log keeps the logged edge
        if b is not None and len(b):
            m = b[b["market"] == mk].drop_duplicates("game_id", keep="last").set_index("game_id")
            t = pd.to_datetime(card["game_id"].map(m["logged_at"]), utc=True, errors="coerce", format="ISO8601")
            card[f"{mk}_logged_pre"] = (t < REVISION).fillna(False).to_numpy()
            card[f"{mk}_logged_at"] = [x.isoformat() if pd.notna(x) else None for x in t]   # for the Logged column / sort
    # tip-time review (cbb/clv_primary.py tip_check): shown on the logged play before tip, display only
    try:
        from . import clv_primary, tipcheck
        if b is not None and len(b):
            o = b[b["status"] == "open"]
            p = clv_primary.primary(o).merge(o[["bet_id", "game_id", "market", "pick", "home", "away"]], on="bet_id")
            p = p[p["tip_check"].isin(["review", "conflict"])]
            for mk in ("spread", "total"):
                m = p[p["market"] == mk].set_index("game_id")
                if len(m):
                    msg = card["game_id"].map(m.apply(tipcheck.message, axis=1))
                    old = card[f"{mk}_warn"] if f"{mk}_warn" in card else pd.Series(None, index=card.index)
                    card[f"{mk}_warn"] = [("; ".join(x for x in (a_, m_) if isinstance(x, str) and x)) or a_
                                          for a_, m_ in zip(old, msg)]
    except Exception as e:
        print(f"Tip-time warning failed ({e}); continuing.")
    return card


    return card


def _first_open_view(card: pd.DataFrame, day: pd.Timestamp) -> pd.DataFrame:
    """The first number posted on each game (lines/openers.csv: each book's first number and when it was seen), oriented
    to the card's home team: first_open = [{book, home_spread, total}] for the books that posted at the earliest time
    (spread and total separately, as first_open_spread / first_open_total). The card's Opened column shows the play's
    book when it is among them, else their median (Chad, Oct 31: a later book's opener must not move "Opened").
    Display only."""
    card = card.copy()
    card["first_open_spread"], card["first_open_total"] = None, None
    try:
        path = os.path.join(os.path.dirname(__file__), "..", "lines", "openers.csv")
        if not os.path.exists(path) or not len(card):
            return card
        o = pd.read_csv(path)
        o = o[o["game_key"].astype(str).str.startswith(f"{day:%Y-%m-%d}|")]
        o["t"] = pd.to_datetime(o["first_seen"], utc=True, format="ISO8601", errors="coerce")
        out_s, out_t = [], []
        for h, a in zip(card["home_id"], card["away_id"]):
            if pd.isna(h) or pd.isna(a):
                out_s.append(None); out_t.append(None); continue
            lo, hi = sorted((int(h), int(a)))
            g = o[o["game_key"] == f"{day:%Y-%m-%d}|{lo}|{hi}"]
            res = []
            for col in ("open_home_spread", "open_total"):
                x = g.dropna(subset=[col, "t"])
                if not len(x):
                    res.append(None); continue
                first = x[x["t"] <= x["t"].min() + pd.Timedelta(minutes=1)]      # the same pull
                val = [(v if int(oh) == int(h) else -v) if col == "open_home_spread" else v
                       for v, oh in zip(first[col], first["home_id"])]
                res.append([{"book": b, "value": float(v), "at": t.isoformat()} for b, v, t in zip(first["book"], val, first["t"])])
            out_s.append(res[0]); out_t.append(res[1])
        card["first_open_spread"], card["first_open_total"] = out_s, out_t
    except Exception as e:
        print(f"First openers failed ({e}); continuing.")
    return card


def _venue_view(card: pd.DataFrame, day: pd.Timestamp, fetch: bool) -> pd.DataFrame:
    """Venue check of each game's neutral flag (cbb/venue.py): confirmed / conflict / unknown with the venue.
    Display only; the flag the model used is unchanged. fetch=False reads the cache only (renders of past cards)."""
    from . import venue
    card = card.copy()
    try:
        path = venue.CACHE.format(f"{day:%Y-%m-%d}")
        t = venue.day_table(day, refresh=True) if fetch else (pd.read_csv(path) if os.path.exists(path) else None)
    except Exception as e:
        print(f"Venue check failed ({e}); continuing.")
        t = None
    if t is None or not len(t):
        card["venue_state"] = "unknown"
        return card
    t = t.drop_duplicates("game_id").set_index(t["game_id"].astype(str))
    gid = card["game_id"].astype(str)
    card["venue_state"] = gid.map(t["venue_state"]).fillna("unknown")
    for c in ("venue", "city", "reason", "edge", "event"):
        card[f"venue_{c}"] = gid.map(t[c])
    return card


def _clv_view() -> dict:
    """The card's CLV figures from the protocol's primary close (cbb/clv_primary.py), the same calculation as the
    record page, the charts, Discord and the tripwire: per market and overall, mean CLV over decided plays with a
    primary close plus coverage, and the recent settled plays with the same-book CLV as a labeled diagnostic.
    Display only; the stake multiplier and its cap come from tracker.status(), which uses the same primary close."""
    from . import clv_primary, tracker
    try:
        a = clv_primary.attach(tracker.load())
    except Exception as e:
        return {"status": clv_primary.VERIFICATION_STATUS, "error": str(e), "recent": None}
    a = a[a["status"] != "void"]
    s = a[a["status"] == "settled"]
    out = {mk: clv_primary.coverage(s[s["market"] == mk]) for mk in ("spread", "total")}
    out["all"] = clv_primary.coverage(s)
    out["all"]["text"] = clv_primary.coverage_text(out["all"])
    out["status"] = clv_primary.VERIFICATION_STATUS
    cols = ["date", "home", "away", "market", "pick", "book", "odds", "close_line", "clv_pts", "home_score",
            "away_score", "result", "profit", "books_primary", "clv_reason", "clv_same_book", "pregame_check"]
    out["recent"] = s.sort_values(["date", "logged_at"], ascending=False).head(30)[cols].to_dict("records")
    return out


def _band_b_view() -> dict | None:
    """Band B's own season record for the card's band B block (tracker.band_b_status, spreads only). Display only."""
    from . import tracker
    try:
        return {k: _clean(v) for k, v in tracker.band_b_status()["all"].items()}
    except Exception as e:
        print(f"Band B record failed ({e}); continuing.")
        return None


def _logged_sides(card: pd.DataFrame, day: pd.Timestamp) -> pd.DataFrame:
    """A logged spread whose game ESPN has since relisted the other way round (neutral sites; Nov 2: Purdue +4.5 was
    logged with Purdue at home, the card now has Gonzaga at home) is shown from the card's orientation: its side is
    swapped and the model's view now (edge, win chance, EV at the logged number and price) recomputed for the team
    actually bet. Display only; the bet log keeps the play as logged and grades it by team (tracker.settle)."""
    if "spread_logged_side" not in card or not card["spread_logged_side"].notna().any():
        return card
    from . import run_day, tracker
    try:
        b = tracker.load("all")
    except Exception:
        return card
    home = {str(k): v for k, v in zip(b["bet_id"], b["home_id"])}
    card = card.copy()
    for i, g in card.iterrows():
        side = g.get("spread_logged_side")
        if not isinstance(side, str) or side not in ("home", "away"):
            continue
        h = home.get(f"{day:%Y-%m-%d}|{g['game_id']}|spread|{side}")
        if h is None or pd.isna(h) or int(h) != int(g["away_id"]):
            continue
        card.loc[i, "spread_logged_bid_side"] = side          # the bet id keeps the side it was logged under
        side = "away" if side == "home" else "home"
        line = float(g["spread_logged_line"])
        e = g["model_margin"] + line if side == "home" else line - g["model_margin"]
        slope, cap = run_day.WIN_PROB["spread"]
        p = float(min(max(0.5 + slope * e, 1 - cap), cap))
        card.loc[i, ["spread_logged_side", "spread_now_edge", "spread_now_p", "spread_now_ev"]] = [
            side, e, p, run_day.ev(p, g["spread_logged_odds"])]
    return card


def _logged_models(card: pd.DataFrame, day: pd.Timestamp) -> pd.DataFrame:
    """{market}_logged_model: the model's number when each logged play was logged (bets.csv "model"), so the card's
    Model column matches the logged edge beside it (Nov 3). Display only."""
    from . import tracker
    try:
        b = tracker.load("all")
    except Exception:
        return card
    m = {str(k): v for k, v in zip(b["bet_id"], b["model"])}
    card = card.copy()
    for mk in ("spread", "total"):
        if f"{mk}_logged_side" not in card:
            continue
        bid_side = card.get(f"{mk}_logged_bid_side", pd.Series(index=card.index, dtype=object))
        side = bid_side.where(bid_side.notna(), card[f"{mk}_logged_side"]) if bid_side is not None else card[f"{mk}_logged_side"]
        card[f"{mk}_logged_model"] = [m.get(f"{day:%Y-%m-%d}|{g}|{mk}|{sd}") if isinstance(sd, str) else None
                                      for g, sd in zip(card["game_id"], side)]
    return card


def build(card: pd.DataFrame, rt: pd.DataFrame, day: pd.Timestamp, season: int, replay: bool = False,
          record: dict | None = None) -> str:
    if not replay:
        card = _logged_sides(card, day)
        card = _logged_models(card, day)
    card = _logged_view(card)
    card = _first_open_view(card, day)
    if not replay:
        card = _venue_view(card, day, fetch=record is not None)
    games = [{k: _clean(v) for k, v in r.items()} for r in card.to_dict("records")]
    if not replay and any(g.get("state") in ("in", "post") for g in games):
        # the game clock ("2nd half · 15:48 left") from ESPN's free scoreboard, so a card run keeps what the results
        # refresh (cbb/live_refresh.py) shows between runs; display only, never fails the build
        try:
            from .live_refresh import clocks
            clk = clocks(day)
            for g in games:
                if str(g.get("game_id")) in clk:
                    g["clock"] = clk[str(g.get("game_id"))]
        except Exception as e:
            print(f"Game clocks unavailable ({e}); scores only.")
    t = rt.reset_index(names="espn_id")
    t["rank"] = range(1, len(t) + 1)
    rat = [{k: _clean(v) for k, v in r.items()} for r in
           t[["rank", "team", "net", "adj_oe", "adj_de", "adj_tempo"]].to_dict("records")]
    built = autorefresh.stamp()
    try:   # line-move plays logged before the Nov 2 opener rule: their own block on the card
        from . import tracker
        prerule = sorted(i for i in tracker.prerule_ids() if i.startswith(f"{day:%Y-%m-%d}|"))
    except Exception:
        prerule = []
    data = {"date": f"{day:%Y-%m-%d}", "season": season, "replay": replay, "repo": REPO, "nfl": NFL_SITE,
            "prerule": prerule, "prerule_res": _prerule_results(f"{day:%Y-%m-%d}") if not replay else {},
            "generated_at": built, "games": games, "ratings": rat,
            "record": record_block(record) if record else None}
    payload = json.dumps(data).replace("</", "<\\/")
    title = f"Off The Glass · College Basketball · {day:%a %b} {day.day}"
    return (TEMPLATE.replace("__HEAD__", HEAD).replace("__BRAND__", BRAND).replace("__X__", X_HANDLE)
            .replace("__TITLE__", html.escape(title)).replace("__DATA__", payload)
            # auto refresh (cbb/autorefresh.py): live cards only; a replay never changes
            .replace("__BUILT__", "" if replay else autorefresh.meta(built))
            .replace("__AUTOREFRESH__", "" if replay else autorefresh.SCRIPT))



def record_block(record: dict) -> dict:
    """The card's record block (data["record"]) from run_day's record dict (status, recent, review, tripwire): the
    tiles, the record table, the recent results and band B's own line. Shared by the card build and the results-only
    refresh (cbb/live_refresh.py), so both show the same numbers."""
    clv = _clv_view()
    clv_recent = clv.pop("recent", None) if clv else None
    if clv_recent is None:   # primary close unreadable: show no CLV, never the grader's as CLV
        clv_recent = [dict(r, close_line=None, clv_pts=None, clv_same_book=r.get("clv_pts"),
                           clv_reason="primary close unavailable this run") for r in record["recent"]]
    return {"status": record["status"], "tripwire": record.get("tripwire"), "clv": clv,
            "recent": [{k: _clean(v) for k, v in r.items()} for r in clv_recent],
            "review": json.loads(json.dumps(record.get("review") or {}, default=_clean)),
            "band_b": _band_b_view()}


REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")


def _prerule_results(day: str) -> dict:
    """{bet_id: {"res", "profit"}} for the day's graded pre-rule line-move plays (their own block on the card)."""
    from . import tracker
    try:
        b = tracker.load(tracker.LINEMOVE)
    except Exception:
        return {}
    b = b[(b["date"] == day) & (b["status"] == "settled")]
    return {r["bet_id"]: {"res": r["result"], "profit": _clean(float(r["profit"]))} for _, r in b.iterrows()}
def put_scores(g: dict, r) -> None:
    """A scoreboard row's scores onto a card game by team, not by ESPN's home/away label: a game ESPN has since relisted
    with the other team at home (neutral sites; Nov 2, Florida State-Florida A&M) gets its scores the right way round."""
    hs, as_ = r.get("home_score"), r.get("away_score")
    try:
        if pd.notna(r.get("home_id")) and g.get("away_id") is not None and int(r.get("home_id")) == int(g["away_id"]):
            hs, as_ = as_, hs
    except (TypeError, ValueError):
        pass
    if pd.notna(hs):
        g["home_score"] = _clean(hs)
    if pd.notna(as_):
        g["away_score"] = _clean(as_)


PAST_DAYS = 3


def refresh_past(scores, reports: str | None = None, today_record: dict | None = None, days_back: int = PAST_DAYS) -> list[str]:
    """Bring the last few past days' cards up to date (Chad, Nov 2: "why isn't Nov 1 updating"). The card run
    rebuilds today and the coming week, never a past day, so a past page kept the scores and record from its last
    build. For each past day in days.json within days_back: final scores and game state from ESPN (scores(day), the
    card's own run_day.slate), the record block from today's freshly built card, the pre-rule line-move list, and
    today's layout. The day's picks and every logged number are kept as they were. Returns the dates rewritten."""
    import re as _re
    from . import tracker
    reports = reports or REPORTS_DIR
    path = os.path.join(reports, "days.json")
    if not os.path.exists(path):
        return []
    days = json.load(open(path))
    cur = days.get("current", "")
    past = sorted(d for d in days.get("days", []) if d < cur)[-days_back:]
    if today_record is None:
        f = os.path.join(reports, f"cbb_{cur}.html")
        m = _re.search(r'<script id="data" type="application/json">(.*?)</script>', open(f).read(), _re.S) if os.path.exists(f) else None
        today_record = json.loads(m.group(1)).get("record") if m else None
    done = []
    for d in past:
        f = os.path.join(reports, f"cbb_{d}.html")
        if not os.path.exists(f):
            continue
        src = open(f).read()
        m = _re.search(r'<script id="data" type="application/json">(.*?)</script>', src, _re.S)
        t = _re.search(r"<title>(.*?)</title>", src, _re.S)
        if not m or not t:
            continue
        data = json.loads(m.group(1))
        if data.get("replay"):
            continue
        try:
            sl = scores(pd.Timestamp(d))
            fin = {str(r["game_id"]): r for _, r in sl.iterrows()} if len(sl) else {}
        except Exception as e:
            print(f"Scores for {d} unavailable ({e}); page left as is.")
            continue
        for g in data.get("games", []):
            r = fin.get(str(g.get("game_id")))
            if r is None:
                continue
            g["state"] = r.get("state", g.get("state"))
            put_scores(g, r)
        try:   # a logged spread whose game was relisted with the other team at home: shown from the team bet
            from .live_refresh import _relisted
            _relisted(data, d)
        except Exception as e:
            print(f"Relisted-home check for {d} failed ({e}).")
        if today_record is not None:
            data["record"] = today_record
        data["prerule"] = sorted(i for i in tracker.prerule_ids() if i.startswith(f"{d}|"))
        data["prerule_res"] = _prerule_results(d)
        prev = json.loads(m.group(1))
        prev.pop("generated_at", None)
        cmp = dict(data)
        cmp.pop("generated_at", None)
        same_data = json.dumps(cmp, sort_keys=True) == json.dumps(prev, sort_keys=True)
        if not same_data:
            data["generated_at"] = autorefresh.stamp()
        payload = json.dumps(data).replace("</", "<\\/")
        page = (TEMPLATE.replace("__HEAD__", HEAD).replace("__BRAND__", BRAND).replace("__X__", X_HANDLE)
                .replace("__TITLE__", t.group(1)).replace("__DATA__", payload)
                .replace("__BUILT__", autorefresh.meta(data["generated_at"])).replace("__AUTOREFRESH__", autorefresh.SCRIPT))
        if page != src:
            open(f, "w").write(page)
            done.append(d)
    return done


TEMPLATE = r"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<meta property="og:title" content="__TITLE__">
__BUILT__
__HEAD__
<style>
:root {
  --bg: #fbf6ea; --surface: #ffffff; --sunken: #f7f0e1; --line: #ebe1cd; --line-strong: #d9cbb0;
  --text: #0a2c49; --muted: #56627a; --faint: #8a93a3;
  --accent: #b84a08; --pos: #0f7b4b; --pos-bg: #e6f4ed; --neg: #c2352b; --warn: #8a5a00; --warn-bg: #fbf0d9;
  --brand: #fd6c0f; --bar: #0a2c49; --bar-text: #fbf6ea; --bar-muted: #b7c3d3;
  --font: "Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --display: "Graduate", "Rockwell", Georgia, serif;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #08090b; --surface: #12151a; --sunken: #181c22; --line: #242a33; --line-strong: #333b46;
    --text: #f6eedd; --muted: #a8b0bc; --faint: #6f7886;
    --accent: #ff8a3d; --pos: #3ccf8e; --pos-bg: #12301f; --neg: #ff6b5e; --warn: #f0b44a; --warn-bg: #33270f;
    --brand: #fd6c0f; --bar: #000000; --bar-text: #f6eedd; --bar-muted: #9aa2ae;
    color-scheme: dark;
  }
}
* { box-sizing: border-box }
.show-sm { display: none }
body { margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 var(--font); font-feature-settings: "tnum" 1, "cv11" 1; -webkit-font-smoothing: antialiased }
a { color: var(--accent); text-decoration: none } a:hover { text-decoration: underline }
.wrap { max-width: 1320px; margin: 0 auto; padding: 0 16px }

/* Top bar */
.top { background: var(--bar); border-bottom: 3px solid var(--brand); position: sticky; top: 0; z-index: 5 }
.top .wrap { display: flex; align-items: center; gap: 22px; height: 58px }
.brand { display: flex; align-items: center; gap: 10px; white-space: nowrap; color: var(--bar-text); text-decoration: none }
.brand:hover { text-decoration: none }
.brand img { width: 34px; height: 34px; border-radius: 7px; display: block }
.wordmark { font-family: var(--display); font-size: 19px; letter-spacing: .02em; text-transform: uppercase; color: var(--bar-text); line-height: 1 }
.tabs { display: flex; gap: 2px; height: 100% }
.tabs a { display: flex; align-items: center; padding: 0 12px; color: var(--bar-muted); font-weight: 600; font-size: 13px; letter-spacing: .04em;
  text-transform: uppercase; border-bottom: 3px solid transparent; margin-bottom: -3px; text-decoration: none }
.tabs a[hidden] { display: none }
.tabs a:hover { color: var(--bar-text); text-decoration: none }
.tabs a[aria-current="page"] { color: var(--bar-text); border-bottom-color: var(--brand) }
.status { margin-left: auto; display: flex; align-items: center; gap: 12px; color: var(--bar-muted); font-size: 13px; min-width: 0 }
.status a { color: var(--bar-text) }
#upd-btn { background: transparent; color: var(--bar-text); border-color: rgba(251,246,234,.35) } #upd-btn:hover { background: rgba(251,246,234,.1) }
.status span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis }
button { font: inherit; font-weight: 600; font-size: 13px; color: var(--text); background: var(--surface); border: 1px solid var(--line-strong);
  border-radius: 6px; padding: 6px 12px; cursor: pointer } button:hover { background: var(--sunken) } button:disabled { opacity: .5; cursor: progress }

/* Page head */
.head { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 12px; padding: 24px 0 16px }
h1 { font-family: var(--display); font-weight: 400; font-size: 26px; letter-spacing: .01em; margin: 0; line-height: 1.15 }
.sub { color: var(--muted); margin-top: 2px }
.days { display: flex; gap: 4px; flex-wrap: wrap; margin: -4px 0 20px }
/* other pages: plain links beside the title, so they never read as days */
.pagelinks { display: flex; gap: 18px; align-items: center; flex-wrap: wrap; padding-bottom: 4px }
.pagelinks a { color: var(--muted); font-weight: 600; font-size: 13px; letter-spacing: .04em; text-transform: uppercase; text-decoration: none;
  border-bottom: 2px solid transparent; padding: 2px 0 }
.pagelinks a::after { content: " \2192"; opacity: .6 }
.pagelinks a:hover { color: var(--text); border-bottom-color: var(--brand); text-decoration: none }
.days a, .pagebtn { padding: 5px 12px; border-radius: 6px; color: var(--text); font-weight: 600; font-size: 13px; text-decoration: none;
  border: 1px solid var(--line-strong); background: var(--surface); white-space: nowrap }
.days a:hover, .pagebtn:hover { background: var(--sunken); text-decoration: none }
.days a[aria-current="page"] { color: var(--surface); border-color: var(--text); background: var(--text) }
.notice { border: 1px solid var(--line); background: var(--warn-bg); color: var(--warn); border-radius: 8px; padding: 10px 12px; margin-bottom: 16px; font-size: 13px }

/* KPI strip */
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); border: 1px solid var(--line); border-top: 3px solid var(--text); border-radius: 10px; background: var(--surface); margin-bottom: 24px; overflow: hidden; box-shadow: 0 1px 2px rgba(10,44,73,.06) }
.kpi { padding: 12px 16px; border-right: 1px solid var(--line) } .kpi:last-child { border-right: 0 }
.kpi .k { color: var(--muted); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em } .kpi .v { font-size: 21px; font-weight: 800; margin-top: 3px; letter-spacing: -.01em }
.kpi .v small { font-size: 12px; color: var(--muted); font-weight: 500; margin-left: 4px }
.kpi .v small.blk { display: block; margin: 2px 0 0; line-height: 1.3 }

/* Panels and tables */
.panel { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; margin-bottom: 24px; overflow: hidden; box-shadow: 0 1px 2px rgba(10,44,73,.06) }
.panel-h { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; padding: 12px 16px; border-bottom: 1px solid var(--line) }
.panel-h h2 { font-size: 13px; font-weight: 800; margin: 0; text-transform: uppercase; letter-spacing: .07em; display: flex; align-items: center; gap: 8px }
.panel-h h2::before { content: ""; width: 4px; height: 14px; background: var(--brand); border-radius: 2px } .panel-h .note { color: var(--muted); font-size: 12px }
.scroll { overflow-x: auto }
/* long notes wrap instead of widening the table (no sideways scrolling) */
#t-plays td:first-child { white-space: normal; min-width: 240px }
#t-rec td { white-space: normal }
table { width: 100%; border-collapse: collapse; font-size: 13px }
th { text-align: left; font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); padding: 8px 12px; border-bottom: 1px solid var(--line); background: var(--sunken); white-space: nowrap }
td { padding: 9px 12px; border-bottom: 1px solid var(--line); white-space: nowrap; vertical-align: middle }
tr.rephead th { border-top: 1px solid var(--line) }
tbody tr:last-child td { border-bottom: 0 }
.r { text-align: right } .c { text-align: center } .m { color: var(--muted) } .f { color: var(--faint) }
.pos { color: var(--pos) } .neg { color: var(--neg) } .b { font-weight: 600 }
.empty { padding: 28px 16px; color: var(--muted); text-align: center }
.betlink { font-weight: 600; font-size: 12px; border: 1px solid var(--line-strong); border-radius: 6px; padding: 4px 10px; color: var(--text); display: inline-block }
.betlink:hover { background: var(--sunken); text-decoration: none }
.tag { display: inline-block; font-size: 11px; font-weight: 600; padding: 1px 6px; border-radius: 4px; border: 1px solid var(--line-strong); color: var(--muted) }
.tag.bet { color: #fff; border-color: var(--brand); background: var(--brand) }
.tag.logged { color: var(--brand); border-color: var(--brand); background: transparent }

/* Segmented control */
.seg { display: inline-flex; border: 1px solid var(--line-strong); border-radius: 6px; overflow: hidden }
.seg button { border: 0; border-radius: 0; padding: 5px 12px; color: var(--muted); font-weight: 500; background: transparent }
.seg button + button { border-left: 1px solid var(--line-strong) }
.seg button[aria-pressed="true"] { background: var(--text); color: var(--surface) }
.ctrls { display: flex; flex-wrap: wrap; gap: 8px; align-items: center }
/* Plays header: a count chip and a Rules toggle, so it reads as a control bar like the odds board's */
.chip { display: inline-flex; align-items: center; padding: 5px 12px; border-radius: 6px; font-size: 13px; font-weight: 700;
  background: var(--brand); color: #fff; white-space: nowrap }
.chip.zero { background: var(--sunken); color: var(--muted); border: 1px solid var(--line-strong) }
.chipbtn { padding: 5px 12px; font-weight: 500; color: var(--muted) }
.chipbtn[aria-expanded="true"] { background: var(--text); color: var(--surface); border-color: var(--text) }
.rules { padding: 10px 16px; border-bottom: 1px solid var(--line); background: var(--sunken); color: var(--muted); font-size: 12px }
label.chk { display: inline-flex; gap: 6px; align-items: center; color: var(--muted); font-size: 13px; cursor: pointer }

/* Odds board: two rows per game (away, home) */
.board td { padding-top: 6px; padding-bottom: 6px }
.board tbody.g tr:first-child td { padding-top: 10px } .board tbody.g tr:last-child td { padding-bottom: 10px; border-bottom: 1px solid var(--line) }
.board tbody.g tr:first-child td { border-bottom: 0 }
.board tbody.g:last-child tr:last-child td { border-bottom: 0 }
.board .team { font-weight: 500 }
.score { font-size: 12px; font-weight: 600; margin-top: 2px } .score .dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #d64545; margin-right: 5px; vertical-align: 1px }
.score .res { display: inline-block; margin-left: 6px; padding: 0 6px; border-radius: 4px; font-weight: 800 } .score .res.W { background: #e3f3e8; color: #1d7a3e } .score .res.L { background: #fbe4e4; color: #b42318 } .score .res.P { background: var(--line) }
.inj { color: var(--warn); font-size: 11px; font-weight: 500; white-space: normal; max-width: 340px; margin-top: 1px } .board .tm { width: 72px; color: var(--muted); font-size: 12px }
.board .pts { color: var(--muted); width: 40px }
.odd { display: inline-flex; flex-direction: column; align-items: flex-end; min-width: 56px; padding: 3px 6px; border-radius: 6px; line-height: 1.25; color: var(--text); text-decoration: none }
.odd small { color: var(--faint); font-size: 11px }
a.odd:hover { background: var(--sunken); text-decoration: none }
.odd.best { background: var(--pos-bg); color: var(--pos) } .odd.best small { color: var(--pos) }
.na { color: var(--faint) }
.board th.bk, .board td.bk { text-align: right; width: 84px; padding-left: 6px; padding-right: 6px }
.board td.edge { white-space: normal; min-width: 110px; max-width: 170px } .tag { white-space: normal }
.bestc { display: none; text-align: right } .tm-sm { display: none; color: var(--faint); font-size: 11px }
@media (max-width: 1100px) { .bk-minor, .hide-md { display: none } .board .bestc { display: table-cell } }
.bestc small { display: block; color: var(--faint); font-size: 11px }
.board tbody.g.has-bet { background: linear-gradient(90deg, var(--brand) 0 3px, transparent 3px) }

details.panel > summary { list-style: none; cursor: pointer; padding: 12px 16px; font-weight: 600; font-size: 15px; display: flex; justify-content: space-between }
details.panel > summary::after { content: "Show"; color: var(--accent); font-size: 13px; font-weight: 500 }
details.panel[open] > summary::after { content: "Hide" }
details.panel[open] > summary { border-bottom: 1px solid var(--line) }
footer { color: var(--muted); font-size: 12px; padding: 8px 0 40px; max-width: 80ch }
.follow { display: inline-flex; align-items: center; gap: 8px; margin-top: 12px; font-weight: 700; color: var(--text) }
.follow img { width: 22px; height: 22px; border-radius: 5px }
.tl img { width: auto; vertical-align: -3px; margin-right: 5px; object-fit: contain }
.pick .tl img { vertical-align: -5px; margin-right: 6px }
.hero { display: block; height: 120px; width: auto; max-width: 100%; object-fit: contain; border-radius: 10px; margin-top: 18px; border: 1px solid var(--line) }
@media (max-width: 720px) { .hero { height: auto; width: 100% } }

@media (max-width: 380px) { #t-rat th:nth-child(6), #t-rat td:nth-child(6) { display: none } }
@media (max-width: 860px) {
  .top .wrap { gap: 10px } .status span { display: none }
  .wordmark { display: none } .tabs a { padding: 0 8px; font-size: 12px }
  h1 { font-size: 21px }
  .kpi { border-right: 0; border-bottom: 1px solid var(--line) } .kpi:last-child { border-bottom: 0 }
  .kpi.wide { grid-column: 1 / -1 }
  .hide-sm { display: none } .show-sm { display: inline }
  td, th { padding-left: 10px; padding-right: 10px }
  #t-plays td:first-child { white-space: normal; min-width: 150px }
  #t-rat td, #t-rat th { padding-left: 4px; padding-right: 4px; font-size: 12px } #t-rat th { letter-spacing: 0 } #t-rat td { white-space: normal }
  .board .bk, .board .pts { display: none } .bestc { display: table-cell }
  .board .tm { width: 52px; font-size: 11px } .board td.edge { min-width: 0; max-width: 104px }
  .board td, .board th { padding-left: 6px; padding-right: 6px } .board .team { white-space: normal; min-width: 0 }
  .board .tag { font-size: 10px; padding: 1px 4px } .board .tl img { width: 14px; height: 14px; margin-right: 4px }
  .board .tm { display: none } .tm-sm { display: block } .board td.edge { max-width: 104px }
  table.stack thead { display: none }
  table.stack tbody tr { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px 12px; padding: 12px; border-bottom: 1px solid var(--line) }
  table.stack tbody tr.rephead { display: none }
  table.stack tbody tr:last-child { border-bottom: 0 }
  table.stack td { display: block; border: 0; padding: 0; white-space: normal; text-align: left; min-width: 0 }
  table.stack td:first-child { grid-column: 1 / -1; min-width: 0 }
  table.stack td[data-l]::before { content: attr(data-l); display: block; font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: .05em; color: var(--faint); margin-bottom: 1px }
  table.stack td:first-child::before { display: none }
  table.stack td.hide-sm, table.stack td:empty { display: none }
  table.stack td.empty { grid-column: 1 / -1; text-align: center }
}
</style>

<header class="top"><div class="wrap">
  __BRAND__
  <nav class="tabs" aria-label="Sport"><a id="nfl-link" href="#">NFL</a>""" + NBA_TAB + r"""<a href="./" aria-current="page"><span class="hide-sm">College Basketball</span><span class="show-sm">CBB</span></a></nav>
  <div class="status"><span id="upd-status"></span><button id="upd-btn" type="button">Update</button></div>
</div></header>

<main class="wrap">
  <div class="head">
    <div><h1 id="h1"></h1><div class="sub" id="sub"></div></div>
    <nav class="pagelinks" aria-label="Pages"><a href="record.html">Record</a><a href="record/charts.html">Charts</a><a href="record/survivor.html">Survivor</a></nav>
  </div>
  <nav class="days" id="days" aria-label="Days"></nav>
  <div class="notice" id="replay" hidden>Replay of a past day using ESPN's stored closing lines. Prices and bet links appear on live cards only.</div>

  <div class="kpis" id="kpis"></div>

  <section class="panel" aria-labelledby="plays-h">
    <div class="panel-h"><h2 id="plays-h">Plays</h2>
      <div class="ctrls"><label class="chk" style="font-size:12px">Sort <select id="play-sort" style="font:inherit;font-size:12px;padding:2px 4px;border:1px solid var(--line-strong);border-radius:6px;background:var(--surface);color:var(--text)"><option value="bet">Tip time</option><option value="at">Newest play</option><option value="edge">Edge</option><option value="ev">EV</option><option value="book">Book</option></select></label><span class="chip" id="plays-count"></span><button type="button" class="chipbtn" id="rules-btn" aria-expanded="false" aria-controls="plays-rules">Rules</button></div>
    </div>
    <div class="rules" id="plays-rules" hidden>Spread edge 2.5+ pts · total edge 3+ pts · +2% EV at the price · 1 unit each. Win % = backtest rate for that edge. A logged play stays a play: its edge, win % and EV are as they were when it was logged (plays logged before the Oct 26 model update show them against today's model at your number); the line under it says where the line and the model are now.</div>
    <div class="scroll"><table id="t-plays"></table></div>
  </section>

  <section class="panel" aria-labelledby="bandb-h" id="bandb-sec" hidden>
    <div class="panel-h"><h2 id="bandb-h">Band B (spreads, edge 2-2.5, 0.5 u)</h2><span class="note" id="bandb-rec">A separate bet type on spreads only, never counted in the record above: v1's edge of 2-2.49 points with v1's +2% EV rule, 0.5 unit flat.</span></div>
    <div class="scroll"><table id="t-bandb"></table></div>
  </section>

  <section class="panel" aria-labelledby="watch-h" id="watch-sec">
    <div class="panel-h"><h2 id="watch-h">Watch list</h2><span class="note">Becomes a play if the line reaches the number shown. Follows the Spread / Total tab on the odds board.</span></div>
    <div class="scroll"><table class="board" id="t-watch"></table></div>
  </section>

  <section class="panel" aria-labelledby="lm-h" id="lm-sec" hidden>
    <div class="panel-h"><h2 id="lm-h">Line-move plays (before the opener rule)</h2><span class="note">Logged before Nov 2 under the old rule: they qualified only after the line moved, not at the opener. Kept as logged and graded, in their own record, never counted with the plays above.</span></div>
    <div class="scroll"><table id="t-lm"></table></div>
  </section>

  <section class="panel" aria-labelledby="board-h">
    <div class="panel-h"><h2 id="board-h">Odds board</h2>
      <div class="ctrls">
        <div class="seg" role="group" aria-label="Market"><button data-m="spread" aria-pressed="true">Spread</button><button data-m="total">Total</button><button data-m="ml">Moneyline</button></div>
        <label class="chk"><input type="checkbox" id="only-plays"> Plays only</label>
      </div>
    </div>
    <div class="scroll"><table class="board" id="t-board"></table></div>
  </section>

  <section class="panel" aria-labelledby="rec-h" id="rec-sec" hidden>
    <div class="panel-h"><h2 id="rec-h">Record</h2><span class="note">Every play graded at the number it first appeared. Alert CLV = points from the alert number to the consensus close; prices shown separately.</span></div>
    <div class="scroll"><table id="t-rec"></table></div>
  </section>

  <section class="panel" id="review-sec" hidden>
    <div class="panel-h"><h2>Loss review</h2><span class="note">Why bets lost. "Market disagreed" (the line moved against us with no news) are the real model misses; the rest is variance or late information.</span></div>
    <div class="scroll"><table id="t-review"></table></div>
    <div class="scroll"><table id="t-review2"></table></div>
    <div class="scroll"><table id="t-misses"></table></div>
  </section>

  <details class="panel" id="recent-sec" hidden><summary>Recent results</summary><div class="scroll"><table id="t-recent"></table></div></details>
  <details class="panel"><summary>Power ratings</summary><div class="scroll"><table id="t-rat"></table></div></details>

  <footer>
    <div><a class="follow" href="https://x.com/__X__" target="_blank" rel="noopener"><img src="assets/otg-logo-512.png" alt="">Follow @__X__ on X for every play</a></div>
  </footer>
</main>

<script id="data" type="application/json">__DATA__</script>
<script>
(() => {
  const D = JSON.parse(document.getElementById("data").textContent);
  const $ = (id) => document.getElementById(id);
  const loggedSide = (g, mk) => g[mk + "_logged_pick"] ? String(g[mk + "_logged_side"] || "").toLowerCase() : null;
  // a side already held (v1 or band B, not void): the other side of that market is never a new play or watch
  // (cbb/tracker.log, Chad Nov 1: "we didn't play both spots")
  const bbSide = (g, mk) => g[mk + "_bandb_bet_id"] ? String(g[mk + "_bandb_bet_id"]).split("|")[3] || null : null;
  const heldOther = (g, mk, sd) => { const a = loggedSide(g, mk), b = bbSide(g, mk); return !!((a && a !== sd) || (b && b !== sd)); };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const sgn = (x, d = 1) => x == null ? "–" : (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x).toFixed(d).replace(/\.0+$/, "");
  // stake cap (cbb/tracker.py): held at 50% when primary-close CLV averages below 0 after 25 bets with a close
  const capText = (c) => !c ? "" : "<small>" + (c.state === "held" ? "cap held (closes unreadable)"
    : "cap " + c.state + " (primary CLV " + clvf(c.clv) + " on " + c.n + " of " + c.settled + " plays)") +
    (c.refreshed_at ? " · refreshed " + new Date(c.refreshed_at).toLocaleString("en-US", {timeZone: "America/New_York", month: "short", day: "numeric", hour: "numeric", minute: "2-digit"}) + " ET" : "") + "</small>";
  // CLV: always 2 decimals, the same figure Discord, the record page and the charts show (cbb/clv_primary.py)
  const clvf = (x) => x == null ? "–" : (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x).toFixed(2);
  const ln = (x) => x == null ? "–" : Math.abs(x) < 0.05 ? "PK" : sgn(x);
  const num = (x, d = 1) => x == null ? "–" : Number(x).toFixed(d).replace(/\.0$/, "");
  // The half-point line a WATCH becomes a BET at (good_to is the exact number; books post halves).
  const gp = (o) => o == null ? "" : ", " + odds(o) + " or better";   // price a WATCH needs at that number
  // complete-ratings rule (protocol v2.6, Appendix D): qualifies now, but not a play until the overnight ratings
  // update has the previous day's games (from 6 am ET on game day); never alerted or logged before that
  const heldTag = (e) => "<span class='tag' title='Qualifies, but held: an input failed to load (box scores), so it is not logged or alerted. Do not bet it until the hold clears.'>HELD " + sgn(e) + "</span>";
  const pendTag = (e) => "<span class='tag' title='Qualifies now. It becomes a play only if it still qualifies after the overnight ratings update (from 6 am ET on game day); nothing is alerted or logged before then.'>PENDING " + sgn(e) + "</span>";
  const playAt = (v, higherBetter) => v == null ? null : (higherBetter ? Math.ceil(v * 2 - 1e-9) : Math.floor(v * 2 + 1e-9)) / 2;
  const watchTag = (text) => "<span class='tag'>Watch · " + text + "</span>";
  const odds = (x) => x == null ? "" : (x > 0 ? "+" : "−") + Math.abs(Math.round(x));
  const pct = (x) => x == null ? "–" : (100 * x).toFixed(1) + "%";
  const day = new Date(D.date + "T12:00:00");
  const tip = (g) => g.start ? new Date(g.start).toLocaleTimeString("en-US", {hour: "numeric", minute: "2-digit", timeZone: "America/New_York"}) : "";
  // live and final scores (Chad, Nov 2: "can you add live scores"); the clock comes from the results refresh
  // (cbb/live_refresh.py, every ~3 minutes during games)
  const started = (g) => (g.state === "in" || g.state === "post") && g.home_score != null && g.away_score != null;
  // ESPN's short status ("15:48 - 2nd", "0:42 - OT", "Halftime") read as "2nd half · 15:48 left" (Chad, Nov 2)
  const clock = (g) => {
    if (g.state === "post") return /final/i.test(g.clock || "") ? g.clock : "Final";
    const c = String(g.clock || ""), m = /^(\d{1,2}:\d{2}(?:\.\d)?) - (1st|2nd|\d*OT)$/i.exec(c);
    if (m) return (/OT/i.test(m[2]) ? m[2] : m[2] + " half") + " · " + m[1] + " left";
    if (/^half/i.test(c)) return "Halftime";
    const e = /^end of (1st|2nd)/i.exec(c);
    if (e) return "End of " + e[1] + " half";
    return c || "Live"; };
  // a play's result at its own number from the final score, graded the way the bet log grades it (tracker.settle)
  const cover = (g, kind, side, line) => {
    if (g.state !== "post" || !started(g) || line == null || !side) return null;
    const hs = Number(g.home_score), as = Number(g.away_score), l = Number(line);
    const r = kind === "Spread" ? (side === "home" ? hs - as : as - hs) + l : (hs + as - l) * (side === "over" ? 1 : -1);
    return r > 0 ? "W" : r < 0 ? "L" : "P"; };
  const scoreInner = (g, res) => started(g) ? (g.state === "in" ? "<span class='dot'></span>" : "") +
    esc(clock(g)) + " · " + esc(g.away) + " " + esc(g.away_score) + ", " + esc(g.home) + " " + esc(g.home_score) +
    (res ? "<span class='res " + res + "'>" + res + "</span>" : "") : "";
  // every score line carries its game and play, so the in-page live updater (bottom of this script) can repaint it
  const scoreTag = (g, kind, side, line, grade) => "<div class='score' data-g='" + esc(g.game_id) + "' data-k='" + esc(kind || "") +
    "' data-s='" + esc(side || "") + "' data-l='" + esc(line ?? "") + "' data-r='" + (grade ? 1 : 0) + "'" + (started(g) ? "" : " hidden") + ">" +
    scoreInner(g, grade ? cover(g, kind, side, line) : null) + "</div>";
  const matchup = (g) => g.away + (g.neutral ? " vs " : " @ ") + g.home;
  // phones: each row of these tables becomes a small card; each cell is labeled with its column header
  const stack = (id) => { const t = $(id); if (!t) return; const hs = [...t.querySelectorAll("thead th")].map((h) => h.textContent.trim());
    t.classList.add("stack"); t.querySelectorAll("tbody tr").forEach((r) => [...r.children].forEach((c, k) => { if (hs[k]) c.dataset.l = hs[k]; })); };
  const logo = (id, px) => id == null ? "" : "<picture class='tl'><source media='(prefers-color-scheme: dark)' srcset='https://a.espncdn.com/i/teamlogos/ncaa/500-dark/" + Number(id) +
    ".png'><img src='https://a.espncdn.com/i/teamlogos/ncaa/500/" + Number(id) + ".png' alt='' loading='lazy' width='" + px + "' height='" + px +
    "' onerror=\"this.closest('picture').remove()\"></picture>";
  const matchupL = (g) => logo(g.away_id, 14) + esc(g.away) + (g.neutral ? " vs " : " @ ") + logo(g.home_id, 14) + esc(g.home);
  const pickId = (g, kind, side) => kind === "Spread" ? (side === "home" ? g.home_id : side === "away" ? g.away_id : null) : null;
  const BOOKS = ["FanDuel", "DraftKings", "BetMGM", "Caesars", "Fanatics", "bet365", "theScore Bet"];
  const bl = (g, bk) => (g.book_lines || []).find((x) => x.book === bk);

  $("nfl-link").href = D.nfl;
  $("h1").textContent = day.toLocaleDateString("en-US", {weekday: "long", month: "long", day: "numeric"});
  const withLines = D.games.filter((g) => g.n_books > 0).length;
  $("sub").textContent = D.games.length + " games · " + withLines + " with lines · " + (D.season - 1) + "–" + String(D.season).slice(2) + " season";
  $("replay").hidden = !D.replay;

  const navDays = (list, cur) => {
    // yesterday and today, then the coming week (the card builds the next 7 days every run)
    const i = list.indexOf(cur || D.date), shown = i < 0 ? list.slice(-9) : list.slice(Math.max(0, i - 1), i + 8);
    $("days").innerHTML = shown.map((d) => '<a href="cbb_' + d + '.html"' + (d === D.date ? ' aria-current="page"' : "") + ">" +
      new Date(d + "T12:00:00").toLocaleDateString("en-US", {weekday: "short", month: "short", day: "numeric"}) + "</a>").join("");
  };
  navDays([D.date]);
  fetch("days.json", {cache: "no-store"}).then((r) => r.json()).then((j) => navDays(j.days, j.current)).catch(() => {});

  // Plays
  const P = [];
  // the current market number on a play's side: the median across books (line_home_spread / line_total), like Opened
  const firstOpen = (g, mk, side, book) => {
    const f = g["first_open_" + mk];
    if (!f || !f.length) return mk === "spread" ? (g.open_home_spread == null ? null : ln(side === "home" ? g.open_home_spread : -g.open_home_spread))
      : (g.open_total == null ? null : num(g.open_total));
    const own = f.find((x) => x.book === book);
    const vs = f.map((x) => x.value).sort((p, q) => p - q), mid = vs.length % 2 ? vs[(vs.length - 1) / 2] : (vs[vs.length / 2 - 1] + vs[vs.length / 2]) / 2;
    const v = own ? own.value : mid;
    return mk === "spread" ? ln(side === "home" ? v : -v) : num(v);
  };
  const nowLine = (g, mk, side) => mk === "spread" ? (g.line_home_spread == null ? null : ln(side === "home" ? g.line_home_spread : -g.line_home_spread))
    : (g.line_total == null ? null : num(g.line_total));
  // A logged bet stays listed at the number it was logged at, with where the game stands now underneath.
  const logged = (g, mk) => {
    const pick = g[mk + "_logged_pick"];
    if (!pick) return false;
    const side = String(g[mk + "_logged_side"] || "").toLowerCase();
    const curSide = mk === "spread" ? g.spread_side : String(g.total_pick || "").toLowerCase();
    const still = g[mk + "_verdict"] === "BET" && curSide === side;
    // best current number on the bet's own side across books (the card's pick may now be the other side)
    const sideBest = (g.book_lines || []).map((x) => mk === "spread"
      ? (x.home_spread == null ? null : {book: x.book, key: side === "home" ? x.home_spread : -x.home_spread})
      : (x.total == null ? null : {book: x.book, key: side === "over" ? -x.total : x.total}))
      .filter(Boolean).sort((p, q) => q.key - p.key)[0];
    const cur = still ? (mk === "spread" ? ln(g.spread_line) : num(g.total_line))
      : sideBest ? (mk === "spread" ? ln(sideBest.key) : (side === "over" ? "o" : "u") + num(Math.abs(sideBest.key))) + " (" + sideBest.book + ")" : null;
    const pre = !!g[mk + "_logged_pre"];
    // a logged play stays a play at its logged number; this only says where the market is now
    // today's model number from the bet's side, in the same form as the bet (spread: the team's line; total: points)
    const mnow = mk === "spread" ? (g.model_margin == null ? null : "model now " + (side === "home" ? g.home : g.away) + " " + ln(-(side === "home" ? g.model_margin : -g.model_margin)))
      : (g.model_total == null ? null : "model now " + num(g.model_total));
    // the model's number when the play was logged (bets.csv "model": a total, or the bet side's margin for a favorite /
    // its line for an underdog), shown in the Model column beside the logged edge (Chad, Nov 3: the column showed
    // today's model next to the logged edge, so an Over at +3 sat beside a model total below the line)
    const lm = g[mk + "_logged_model"], ll = Number(g[mk + "_logged_line"]);
    const modelAt = lm == null ? null : mk === "spread" ? ln(ll > 0 ? lm : -lm) : num(lm);
    const edgeNow = !pre && modelAt != null && g[mk + "_now_edge"] != null ? " (edge now " + sgn(g[mk + "_now_edge"]) + ")" : "";
    const now = (still ? "still available at " + cur + " (" + g[mk + "_book"] + ")" : "line now " + (cur ?? "–")) + (mnow ? " · " + mnow + edgeNow : "");
    P.push({g, kind: mk === "spread" ? "Spread" : "Total", side, bet: pick, price: g[mk + "_logged_odds"], book: g[mk + "_logged_book"],
      link: still ? g[mk + "_link"] : null, warn: g[mk + "_warn"],
      // plays logged before the Oct 26 revision show the edge vs today's model at the placed number; others as logged
      edge: pre ? g[mk + "_now_edge"] : g[mk + "_logged_edge"] ?? g[mk + "_now_edge"],
      p: pre ? g[mk + "_now_p"] : g[mk + "_logged_p"] ?? g[mk + "_now_p"], ev: pre ? g[mk + "_now_ev"] : g[mk + "_logged_ev"] ?? g[mk + "_now_ev"],
      model: !pre && modelAt != null ? modelAt : mk === "spread" ? (side === "home" ? ln(-g.model_margin) : ln(g.model_margin)) : num(g.model_total),
      to: still ? (mk === "spread" ? ln(g.spread_good_to) : num(g.total_good_to)) : "–",
      now: nowLine(g, mk, side), at: g[mk + "_logged_at"] || null,
      open: firstOpen(g, mk, side, g[mk + "_logged_book"]),
      units: g[mk + "_logged_stake"], line: g[mk + "_logged_line"],
      bid: D.date + "|" + g.game_id + "|" + mk + "|" + (g[mk + "_logged_bid_side"] || side),
      fill: {book: g[mk + "_logged_book"], line: g[mk + "_logged_line"], odds: g[mk + "_logged_odds"], stake: g[mk + "_logged_stake"]},
      status: (pre ? "Logged at edge " + sgn(g[mk + "_logged_edge"]) + " (before the Oct 26 update) · edge now vs today's model"
        : "Logged at edge " + sgn(g[mk + "_logged_edge"])) + " · " + now});
    return true;
  };
  // Line shopping: every other book on the play's side, best number first, then best price.
  const others = (g, mk, side, used) => {
    const pay = (o) => o == null ? -1 : (o > 0 ? o / 100 : 100 / -o);
    const L = (g.book_lines || []).filter((x) => x.book !== used).map((x) => {
      if (mk === "spread") {
        if (x.home_spread == null) return null;
        const v = side === "home" ? x.home_spread : -x.home_spread;
        return {book: x.book, key: v, price: x[side + "_spread_odds"], txt: ln(v)};
      }
      if (x.total == null) return null;
      return {book: x.book, key: side === "over" ? -x.total : x.total, price: x[side + "_odds"], txt: (side === "over" ? "o" : "u") + num(x.total)};
    }).filter(Boolean).sort((p, q) => q.key - p.key || pay(q.price) - pay(p.price));
    return L.length ? "Also: " + L.map((x) => x.book + " " + x.txt + (x.price != null ? " (" + odds(x.price) + ")" : "")).join(" · ") : "";
  };
  // Venue check of the neutral flag (cbb/venue.py): shown only when the listed arena contradicts the flag; display only
  const venueTag = (g) => {
    if ((g.venue_state || "unknown") !== "conflict") return "";
    const where = [g.venue_venue, g.venue_city].filter(Boolean).join(", ");
    return "<div class='inj'>&#9888; Venue conflict: " + esc(g.venue_reason || "") + (where ? " (" + esc(where) + ")" : "") + ". The model used the " + (g.neutral ? "neutral" : "home") + " flag.</div>";
  };
  // Input freshness (cbb/freshness.py): nothing when every input is current; otherwise one line naming the input, with
  // every input's time on hover; display only
  const freshTag = (g, kind) => {
    const mk = kind === "Spread" ? "spread" : "total", s = g[mk + "_fresh"];
    if (!s || s === "fresh") return "";
    // books take lines down at tip: once a game starts there is no current line to time, and a logged play keeps
    // its own logged number and time (Chad, Nov 2: "why are they all saying line time not recorded")
    if (g.state === "in" || g.state === "post") return "";
    const ts = (k, lab) => g["fresh_" + k] ? lab + " " + new Date(g["fresh_" + k]).toLocaleString("en-US", {timeZone: "America/New_York", month: "short", day: "numeric", hour: "numeric", minute: "2-digit"}) : lab + " –";
    const ttl = "Inputs used: " + [ts("kenpom_at", "KenPom"), ts("barttorvik_at", "Barttorvik"), ts("injuries_at", "injuries"), ts("schedule_at", "schedule"),
      g[mk + "_line_at"] ? "line (" + (g[mk + "_line_book"] || "") + ") " + new Date(g[mk + "_line_at"]).toLocaleTimeString("en-US", {timeZone: "America/New_York", hour: "numeric", minute: "2-digit"}) : "line –"].join(" · ");
    const bk = g[mk + "_line_book"] || g[mk + "_logged_book"] || g[mk + "_book"];
    const why = String(g[mk + "_stale_inputs"] || "an input has no timestamp").replace("line time not recorded",
      !g.n_books ? "no book has a line up right now" : "no current line at " + (bk || "the play's book"));
    return s === "stale" ? "<div class='inj' title='" + esc(ttl) + "'>&#9888; Old input: " + esc(why) + "</div>"
      : "<div class='f' style='font-size:12px' title='" + esc(ttl) + "'>" + esc(why.charAt(0).toUpperCase() + why.slice(1)) + "</div>";
  };
  D.games.forEach((g) => {
    const ls = logged(g, "spread"), lt = logged(g, "total");
    if (!ls && g.spread_verdict === "BET" && !heldOther(g, "spread", g.spread_side)) P.push({g, kind: "Spread", side: g.spread_side, bet: g.spread_pick + " " + ln(g.spread_line), price: g.spread_odds, book: g.spread_book,
      link: g.spread_link, warn: g.spread_warn, edge: g.spread_edge, p: g.spread_p, ev: g.spread_ev, model: g.spread_side === "home" ? ln(-g.model_margin) : ln(g.model_margin), to: ln(g.spread_good_to),
      open: firstOpen(g, "spread", g.spread_side, g.spread_book), units: g.spread_units,
      now: nowLine(g, "spread", g.spread_side),
      also: others(g, "spread", g.spread_side, g.spread_book), line: g.spread_line});
    if (!lt && g.total_verdict === "BET" && !heldOther(g, "total", String(g.total_pick || "").toLowerCase())) P.push({g, kind: "Total", bet: g.total_pick + " " + num(g.total_line), price: g.total_odds, book: g.total_book,
      link: g.total_link, warn: g.total_warn, edge: g.total_edge, p: g.total_p, ev: g.total_ev, model: num(g.model_total), to: num(g.total_good_to), open: firstOpen(g, "total", null, g.total_book), now: nowLine(g, "total"), units: g.total_units,
      also: others(g, "total", String(g.total_pick || "").toLowerCase(), g.total_book), side: String(g.total_pick || "").toLowerCase(), line: g.total_line});
  });
  // line-move plays logged before the Nov 2 opener rule: their own block, never listed or counted with v1's plays
  const PRE = new Set(D.prerule || []);
  const LM = P.filter((p) => PRE.has(p.bid)).map((p) => Object.assign({type: "v1"}, p));
  for (let i = P.length - 1; i >= 0; i--) if (PRE.has(P[i].bid)) P.splice(i, 1);
  // sortable columns: click a header to sort by it, again to reverse; the default is tip time, then edge
  const byTime = (a, b) => String(a.g.start).localeCompare(String(b.g.start)) || b.edge - a.edge;
  const numOf = (v) => { if (v == null) return null; const m = String(v).replace(/\u2212/g, "-").match(/[-+]?\d+(\.\d+)?/); return m ? Number(m[0]) : null; };
  const SORT = {bet: (p) => String(p.g.start || ""), book: (p) => String(p.book || "").toLowerCase(), model: (p) => numOf(p.model),
    edge: (p) => p.edge, p: (p) => p.p, ev: (p) => p.ev, to: (p) => numOf(p.to), open: (p) => numOf(p.open), now: (p) => numOf(p.now), units: (p) => p.units,
    at: (p) => p.at ? Date.parse(p.at) : null};
  let playSort = {key: "bet", dir: 1};
  try { const v = JSON.parse(localStorage.getItem("cbb-play-sort") || "null"); if (v && SORT[v.key]) playSort = v; } catch (e) {}
  const sortPlays = () => P.sort((a, b) => {
    if (playSort.key === "bet") return playSort.dir * byTime(a, b) || 0;
    const x = SORT[playSort.key](a), y = SORT[playSort.key](b);
    if (x == null || x === "") return (y == null || y === "") ? byTime(a, b) : 1;   // blanks last, either direction
    if (y == null || y === "") return -1;
    return (x < y ? -1 : x > y ? 1 : 0) * playSort.dir || byTime(a, b);
  });
  sortPlays();
  const pc = $("plays-count"), pUnits = P.reduce((s, p) => s + (p.units || 0), 0);
  pc.textContent = P.length ? P.length + (P.length === 1 ? " play" : " plays") + " · " + pUnits.toFixed(1).replace(/\.0$/, "") + "u" : "No plays";
  pc.classList.toggle("zero", !P.length);
  $("rules-btn").onclick = () => { const r = $("plays-rules"), open = r.hidden; r.hidden = !open; $("rules-btn").setAttribute("aria-expanded", open); };
  const renderPlays = () => {
  const th = (k, label, cls) => "<th" + (cls ? " class='" + cls + "'" : "") + " data-sort='" + k + "' style='cursor:pointer;user-select:none' title='Sort'>" +
    label + (playSort.key === k ? (playSort.dir > 0 ? " &#9650;" : " &#9660;") : "") + "</th>";
  // the column bar, repeated above every play after the first (Chad, Nov 1: "easier to follow"); hidden on phones,
  // where each play is a card with its own labels
  const bar = th("bet", "Bet") + th("book", "Book") + th("model", "Model", "r hide-sm hide-md") + th("edge", "Edge", "r") +
    th("p", "Win %", "r hide-sm") + th("ev", "EV", "r") + th("to", "Bet to", "r") + th("open", "Opened", "r hide-sm hide-md") + th("now", "Now", "r") + th("units", "Units", "r hide-sm hide-md") + th("at", "Logged", "r hide-sm") +
    "<th></th>";
  $("t-plays").innerHTML = P.length ? "<thead><tr>" + bar + "</tr></thead><tbody>" +
    P.map((p, i) => (i ? "<tr class='rephead'>" + bar + "</tr>" : "") + "<tr data-gid='" + p.g.game_id + "' data-mk='" + p.kind.toLowerCase() + "'><td><div class='b pick'>" + logo(pickId(p.g, p.kind, p.side), 20) + esc(p.bet) + "</div><div class='f' style='font-size:12px'>" + matchupL(p.g) + " · " + esc(tip(p.g)) + " · " + p.kind + "</div>" +
      scoreTag(p.g, p.kind, p.side, p.line, true) +
      (p.kind === "Total" && p.g.crew ? "<div class='f' style='font-size:11px'>Refs: " + esc(p.g.crew) + "</div>" : "") +
      (D.replay ? "" : venueTag(p.g) + freshTag(p.g, p.kind)) +
      (p.status ? "<div class='f' style='font-size:12px'>" + esc(p.status) + "</div>" : "") +
      (p.also ? "<div class='f' style='font-size:12px'>" + esc(p.also) + "</div>" : "") +
      (p.g.news_flag ? "<div class='inj'>&#9888; " + esc(p.g.news_flag) + "</div>" : "") +
      (p.warn ? "<div class='inj'>&#9888; " + esc(p.warn) + "</div>" : "") +
      [["away", p.g.away], ["home", p.g.home]].filter(([sd]) => p.g[sd + "_injuries"]).map(([sd, nm]) => "<div class='inj'>" + esc(nm) + ": " + esc(p.g[sd + "_injuries"]) + "</div>").join("") + "</td><td>" +
      esc(p.book || "–") + (p.price != null ? " <span class='m'>" + esc(odds(p.price)) + "</span>" : "") + "</td><td class='r m hide-sm hide-md'>" + esc(p.model) + "</td><td class='r " + (p.edge >= (p.kind === "Spread" ? 2.5 : 3) ? "pos b" : p.edge < 0 ? "neg" : "m") + "'>" + sgn(p.edge) +
      "</td><td class='r m hide-sm'>" + pct(p.p) + "</td><td class='r'>" + (p.ev == null ? "–" : sgn(100 * p.ev) + "%") +
      "</td><td class='r'>" + esc(p.to) + "</td><td class='r m hide-sm hide-md' title='First number posted (the play&#39;s book if it was among the first)'>" + esc(p.open ?? "–") + "</td><td class='r m' title='Median across books now'>" + esc(p.now ?? "–") + "</td><td class='r hide-sm hide-md'>" + num(p.units, 2) + "</td><td class='r m hide-sm' style='white-space:nowrap'>" +
      (p.at ? esc(new Date(p.at).toLocaleString("en-US", {timeZone: "America/New_York", month: "short", day: "numeric", hour: "numeric", minute: "2-digit"})) : "–") + "</td><td class='r'>" +
      (p.g.news_url ? "<a class='f' style='font-size:12px;margin-right:8px' href='" + esc(p.g.news_url) + "' target='_blank' rel='noopener'>News</a>" : "") +
      "</td></tr>").join("") + "</tbody>"
    : "<tbody><tr><td class='empty'>" + (withLines ? "No plays. No line is far enough from the model." : "No lines posted yet. Openers usually post the night before.") + "</td></tr></tbody>";
  stack("t-plays");
  };
  renderPlays();
  const sel = $("play-sort");
  const syncSel = () => { if ([...sel.options].some((o) => o.value === playSort.key)) sel.value = playSort.key; };
  syncSel();
  sel.onchange = () => {
    const k = sel.value;
    playSort = {key: k, dir: ["edge", "p", "ev", "units", "at"].includes(k) ? -1 : 1};
    try { localStorage.setItem("cbb-play-sort", JSON.stringify(playSort)); } catch (e) {}
    sortPlays();
    renderPlays();
  };
  $("t-plays").addEventListener("click", (ev) => {
    const h = ev.target.closest("th[data-sort]");
    if (!h) return;
    const k = h.dataset.sort;
    playSort = playSort.key === k ? {key: k, dir: -playSort.dir} : {key: k, dir: ["edge", "p", "ev", "units", "at"].includes(k) ? -1 : 1};
    try { localStorage.setItem("cbb-play-sort", JSON.stringify(playSort)); } catch (e) {}
    sortPlays();
    renderPlays();
    syncSel();
  });

  // Band B (cbb/tracker.py BAND_B): logged band B plays, in their own block; never in P, the KPIs or the record
  const BB = [];
  D.games.forEach((g) => ["spread", "total"].forEach((mk) => {
    if (!g[mk + "_bandb_pick"]) return;
    BB.push({g, kind: mk === "spread" ? "Spread" : "Total", bet: g[mk + "_bandb_pick"], book: g[mk + "_bandb_book"], price: g[mk + "_bandb_odds"],
      edge: g[mk + "_bandb_edge"], units: g[mk + "_bandb_stake"], res: g[mk + "_bandb_result"], profit: g[mk + "_bandb_profit"],
      bid: g[mk + "_bandb_bet_id"],
      side: String(g[mk + "_bandb_bet_id"] || "").split("|")[3], line: g[mk + "_bandb_line"],
      fill: {book: g[mk + "_bandb_book"], line: g[mk + "_bandb_line"], odds: g[mk + "_bandb_odds"], stake: g[mk + "_bandb_stake"]}});
  }));
  for (let i = BB.length - 1; i >= 0; i--) if (PRE.has(BB[i].bid)) LM.push(Object.assign({type: "Band B"}, BB.splice(i, 1)[0]));
  BB.sort((a, b) => String(a.g.start).localeCompare(String(b.g.start)) || b.edge - a.edge);
  $("lm-sec").hidden = D.replay || !LM.length;
  const LMR = D.prerule_res || {};
  // sortable like the Plays table: click a header to sort by it, again to reverse (kept in this browser)
  const lmRes = (p) => LMR[p.bid] ? {W: 0, L: 1, P: 2}[LMR[p.bid].res] ?? 3 : 4;
  const LMSORT = {bet: (p) => String(p.g.start || ""), book: (p) => String(p.book || "").toLowerCase(), edge: (p) => p.edge,
    units: (p) => p.units, now: (p) => numOf(p.now), res: lmRes};
  let lmSort = {key: "bet", dir: 1};
  try { const v = JSON.parse(localStorage.getItem("cbb-lm-sort") || "null"); if (v && LMSORT[v.key]) lmSort = v; } catch (e) {}
  const renderLM = () => {
    LM.sort((a, b) => {
      const x = LMSORT[lmSort.key](a), y = LMSORT[lmSort.key](b);
      if (x == null || x === "") return (y == null || y === "") ? 0 : 1;   // blanks last, either direction
      if (y == null || y === "") return -1;
      return (x < y ? -1 : x > y ? 1 : 0) * lmSort.dir || String(a.g.start).localeCompare(String(b.g.start));
    });
    const th = (k, label, cls) => "<th" + (cls ? " class='" + cls + "'" : "") + " data-lmsort='" + k + "' style='cursor:pointer;user-select:none' title='Sort'>" +
      label + (lmSort.key === k ? (lmSort.dir > 0 ? " &#9650;" : " &#9660;") : "") + "</th>";
    $("t-lm").innerHTML = LM.length ? "<thead><tr>" + th("bet", "Bet") + th("book", "Book") + th("edge", "Edge", "r") + th("units", "Units", "r") +
      th("now", "Now", "r") + th("res", "Result", "r") + "</tr></thead><tbody>" +
      LM.map((p) => "<tr data-lm='" + esc(p.bid) + "'><td><div class='b pick'><span class='tag'>Line move</span> " + esc(p.bet) + (p.type === "Band B" ? " <span class='m'>(band B)</span>" : "") +
        "</div><div class='f' style='font-size:12px'>" + matchupL(p.g) + " · " + esc(tip(p.g)) + " · " + p.kind + "</div></td><td>" +
        esc(p.book || "–") + (p.price != null ? " <span class='m'>" + esc(odds(p.price)) + "</span>" : "") + "</td><td class='r'>" + sgn(p.edge) + "</td><td class='r'>" + num(p.units, 2) +
        "</td><td class='r m' title='Median across books now'>" + esc(p.now ?? "–") + "</td><td class='r'>" + (LMR[p.bid] ? esc(LMR[p.bid].res === "W" ? "Win" : LMR[p.bid].res === "L" ? "Loss" : "Push") +
          " <span class='" + (LMR[p.bid].profit > 0 ? "pos" : LMR[p.bid].profit < 0 ? "neg" : "m") + "'>" + sgn(LMR[p.bid].profit, 2) + "</span>"
          : "<span class='m'>Open</span>") + "</td></tr>").join("") + "</tbody>" : "";
    stack("t-lm");
  };
  renderLM();
  $("t-lm").addEventListener("click", (ev) => {
    const h = ev.target.closest("th[data-lmsort]");
    if (!h) return;
    const k = h.dataset.lmsort;
    lmSort = lmSort.key === k ? {key: k, dir: -lmSort.dir} : {key: k, dir: ["edge", "units"].includes(k) ? -1 : 1};
    try { localStorage.setItem("cbb-lm-sort", JSON.stringify(lmSort)); } catch (e) {}
    renderLM();
  });
  $("bandb-sec").hidden = D.replay;
  const bbr = D.record && D.record.band_b;   // band B's own season record (tracker.band_b_status), never pooled
  if (bbr) $("bandb-rec").textContent = "Season: " + bbr.w + "–" + bbr.l + (bbr.p ? "–" + bbr.p : "") + " · " + sgn(bbr.units, 2) + "u" +
    (bbr.clv != null ? " · Alert CLV " + clvf(bbr.clv) + " on " + bbr.clv_n : "") + (bbr.open ? " · " + bbr.open + " open" : "") +
    ". A separate bet type on spreads only, never counted in the record above: v1's edge of 2-2.49 points with v1's +2% EV rule, 0.5 unit flat.";
  $("t-bandb").innerHTML = BB.length ? "<thead><tr><th>Bet</th><th>Book</th><th class='r'>Edge</th><th class='r'>Units</th><th class='r'>Result</th><th></th></tr></thead><tbody>" +
    BB.map((p) => "<tr><td><div class='b pick'><span class='tag'>Band B</span> " + esc(p.bet) + "</div><div class='f' style='font-size:12px'>" + matchupL(p.g) + " · " + esc(tip(p.g)) + " · " + p.kind + "</div>" + scoreTag(p.g, p.kind, p.side, p.line, false) +
      venueTag(p.g) + freshTag(p.g, p.kind) +
      "</td><td>" +
      esc(p.book || "–") + (p.price != null ? " <span class='m'>" + esc(odds(p.price)) + "</span>" : "") + "</td><td class='r'>" + sgn(p.edge) + "</td><td class='r'>" + num(p.units, 2) +
      "</td><td class='r'>" + (p.res ? esc(p.res) + (p.profit != null ? " <span class='" + (p.profit > 0 ? "pos" : p.profit < 0 ? "neg" : "m") + "'>" + sgn(p.profit, 2) + "</span>" : "") : "–") + "</td><td class='r'>" +
      "</td></tr>").join("") + "</tbody>"
    : "<tbody><tr><td class='empty'>No band B plays.</td></tr></tbody>";

  // KPIs
  const st = D.record ? D.record.status : null;
  const rec = (s) => s && s.bets ? s.w + "–" + s.l + (s.p ? "–" + s.p : "") : "0–0";
  const units = st ? (st.spread.units || 0) + (st.total.units || 0) : 0;
  // the official record, both markets together (Chad, Nov 2: "show the total record up top")
  const all = st ? ["w", "l", "p"].reduce((o, k) => (o[k] = (st.spread[k] || 0) + (st.total[k] || 0), o), {}) : null;
  const allRec = all && all.w + all.l + all.p ? all.w + "–" + all.l + (all.p ? "–" + all.p : "") : "0–0";
  const kp = [["Season record", allRec + "<small>" + (all && all.w + all.l ? pct(all.w / (all.w + all.l)) : "") + "</small>", "wide"],
    ["Plays today", P.length + "<small>" + P.reduce((s, p) => s + (p.units || 0), 0).toFixed(1).replace(/\.0$/, "") + "u</small>"],
    ["Spreads", rec(st && st.spread) + "<small>" + (st && st.spread.win != null ? pct(st.spread.win) : "") + "</small>"],
    ["Totals", rec(st && st.total) + "<small>" + (st && st.total.win != null ? pct(st.total.win) : "") + "</small>"],
    ["Units", "<span class='" + (units > 0 ? "pos" : units < 0 ? "neg" : "") + "'>" + sgn(units, 2) + "</span>"],
    ["Model check", (() => { const t = D.record && D.record.tripwire; if (!t) return "–";
      const m = t.model, e = t.execution;
      // primary-close CLV; bets without a close are excluded and counted (cbb/tracker.py, Oct 28)
      const miss = m.missing ? " · " + m.missing + " without a close" : "";
      const lab = m.state === "unavailable" ? "Unavailable<small>closes could not be read</small>"
        : m.state === "collecting" ? "Collecting<small class='blk'>" + (m.with_close != null ? m.with_close : m.n) + "/" + (m.min || 150) + " closes" + miss + "</small>"
        : "<span class='" + (m.state === "ok" ? "pos" : "neg") + "'>" + {ok: "OK", review: "Review", pause: "Pause"}[m.state] + "</span><small>CLV " + clvf(m.clv) + " · last " + m.n + miss + "</small>";
      return lab + (e.state === "review" ? "<small class='neg'> · slippage " + sgn(e.slip, 2) + "</small>" : ""); })()],
    ["Alert CLV", (() => { const c = D.record && D.record.clv; if (!c || c.error || !c.all) return "–<small>CLV unavailable</small>";
      // primary (consensus) close, decided plays with a close; coverage and status on one short line, the full
      // breakdown (books, pregame check) on hover (Chad, Nov 2: the tile was dragging the row down)
      const short = c.all.decided ? c.all.with_close + "/" + c.all.decided + " closed" : "no graded plays yet";
      return "<span title='" + esc(c.all.text + " · " + c.status) + "'>" + (c.all.clv != null ? clvf(c.all.clv) + "<small>pts</small>" : "–") +
        "<small class='blk'>" + esc(short) + (/not verified/.test(String(c.status)) ? " · " + esc(String(c.status).replace("built, ", "")) : "") + "</small></span>"; })()]];
  $("kpis").innerHTML = kp.map(([k, v, c]) => "<div class='kpi" + (c ? " " + c : "") + "'><div class='k'>" + k + "</div><div class='v'>" + v + "</div></div>").join("");

  // Odds board
  let market = "spread";
  const cell = (val, price, link, best) => val == null ? "<span class='na'>–</span>" :
    "<" + (link ? "a href='" + esc(link) + "' target='_blank' rel='noopener'" : "span") + " class='odd" + (best ? " best" : "") + "'>" + esc(val) +
    (price != null ? "<small>" + esc(odds(price)) + "</small>" : "") + "</" + (link ? "a" : "span") + ">";
  // best number (then price) across books for one side, for the phone layout's single column
  const best = (g, sd, i) => {
    const pay = (o) => o == null ? -1 : (o > 0 ? o / 100 : 100 / -o);
    let top = null;
    for (const x of (g.book_lines || [])) {
      let v, pr, txt;
      if (market === "spread") { if (x.home_spread == null) continue; v = sd === "home" ? x.home_spread : -x.home_spread; pr = x[sd + "_spread_odds"]; txt = ln(v); }
      else if (market === "total") { if (x.total == null) continue; const ou = i === 0 ? "over" : "under"; v = ou === "over" ? -x.total : x.total; pr = x[ou + "_odds"]; txt = ou[0] + num(x.total); }
      else { pr = x[sd + "_ml"]; if (pr == null) continue; v = pay(pr); txt = odds(pr); }
      const key = [v, pay(pr)];
      if (!top || key[0] > top.key[0] || (key[0] === top.key[0] && key[1] > top.key[1])) top = {key, txt, pr, book: x.book};
    }
    return top ? esc(top.txt) + (market !== "ml" && top.pr != null ? " <span class='m'>" + esc(odds(top.pr)) + "</span>" : "") + "<small>" + esc(top.book) + "</small>" : "<span class='na'>–</span>";
  };
  // the side of a market already logged as a play ("home"/"away"/"over"/"under"), or null; a logged side is shown
  // as logged everywhere (Plays, board), never again as a new BET or a WATCH
  const loggedTag = (g, mk) => "<span class='tag logged'>Logged " + esc(g[mk + "_logged_pick"]) + "</span>";
  const board = () => {
    const only = $("only-plays").checked;
    boardInto($("t-board"), D.games.filter((g) => !only || g.spread_verdict === "BET" || g.total_verdict === "BET" ||
      loggedSide(g, "spread") || loggedSide(g, "total")), "No games.");
  };
  // one odds-board tile per game (logos, every book, best, edge), into any table: the board and the watch list
  const boardInto = (table, games, empty) => {
    const G = games.slice().sort((a, b) => String(a.start).localeCompare(String(b.start)) || a.home.localeCompare(b.home));
    const mh = {spread: "Model", total: "Model", ml: "Win %"}[market];
    let h = "<thead><tr><th class='tm'>Time</th><th>Team</th><th class='r pts'>Proj</th><th class='r'>" + mh + "</th>" +
      BOOKS.map((b, j) => "<th class='bk" + (j >= 4 ? " bk-minor" : "") + "'>" + b + "</th>").join("") +
      "<th class='bestc'>Best</th><th class='r edge'>Edge</th></tr></thead>";
    if (!G.length) { table.innerHTML = h + "<tbody><tr><td class='empty' colspan='" + (BOOKS.length + 5) + "'>" + esc(empty) + "</td></tr></tbody>"; return; }
    h += G.map((g) => {
      const sides = ["away", "home"];
      const hasBet = (market === "spread" && (g.spread_verdict === "BET" || loggedSide(g, "spread"))) ||
        (market === "total" && (g.total_verdict === "BET" || loggedSide(g, "total")));
      const rows = sides.map((sd, i) => {
        const team = g[sd], pts = Math.round(g["model_" + sd + "_pts"]);
        let model, bookCells, edge = "";
        if (market === "spread") {
          model = ln(sd === "home" ? g.model_home_spread : -g.model_home_spread);
          const pick = g.spread_side === sd && ["BET", "WATCH", "REVIEW"].includes(g.spread_verdict) && loggedSide(g, "spread") !== sd && !heldOther(g, "spread", sd);
          bookCells = BOOKS.map((bk) => { const x = bl(g, bk); if (!x || x.home_spread == null) return cell(null);
            const v = sd === "home" ? x.home_spread : -x.home_spread;
            return cell(ln(v), x[sd + "_spread_odds"], x[sd + "_spread_link"], pick && g.spread_book === bk && v === g.spread_line); });
          if (loggedSide(g, "spread") === sd) edge = loggedTag(g, "spread");
          else if (pick && g.spread_verdict === "BET") edge = "<span class='tag bet'>BET " + sgn(g.spread_edge) + "</span>";
          else if (pick && g.spread_gate === "ratings update") edge = pendTag(g.spread_edge);
          else if (pick && g.spread_gate === "input failure") edge = heldTag(g.spread_edge);
          else if (pick && g.spread_verdict === "REVIEW") edge = "<span class='tag' title='Edge above the maximum: likely a bad quote. Never a play.'>REVIEW " + sgn(g.spread_edge) + "</span>";
          else if (pick) { const at = playAt(g.spread_good_to, true);
            edge = watchTag(g.spread_line >= at ? "better price" : "bet at " + ln(at) + gp(g.spread_good_price)); }
        } else if (market === "total") {
          const ou = i === 0 ? "over" : "under";
          model = i === 0 ? num(g.model_total) : "";
          const pick = (g.total_pick || "").toLowerCase() === ou && ["BET", "WATCH", "REVIEW"].includes(g.total_verdict) && loggedSide(g, "total") !== ou && !heldOther(g, "total", ou);
          bookCells = BOOKS.map((bk) => { const x = bl(g, bk); if (!x || x.total == null) return cell(null);
            return cell((i === 0 ? "o" : "u") + num(x.total), x[ou + "_odds"], x[ou + "_link"], pick && g.total_book === bk && x.total === g.total_line); });
          if (loggedSide(g, "total") === ou) edge = loggedTag(g, "total");
          else if (pick && g.total_verdict === "BET") edge = "<span class='tag bet'>BET " + sgn(g.total_edge) + "</span>";
          else if (pick && g.total_gate === "ratings update") edge = pendTag(g.total_edge);
          else if (pick && g.total_gate === "input failure") edge = heldTag(g.total_edge);
          else if (pick && g.total_verdict === "REVIEW") edge = "<span class='tag' title='Edge above the maximum: likely a bad quote. Never a play.'>REVIEW " + sgn(g.total_edge) + "</span>";
          else if (pick) { const at = playAt(g.total_good_to, ou === "under");
            edge = watchTag((ou === "under" ? g.total_line >= at : g.total_line <= at) ? "better price" : "bet at " + ou[0] + num(at) + gp(g.total_good_price)); }
        } else {
          const p = sd === "home" ? g.p_home_win : 1 - g.p_home_win;
          model = Math.round(100 * p) + "%";
          const prices = BOOKS.map((bk) => (bl(g, bk) || {})[sd + "_ml"]);
          const top = Math.max(...prices.filter((v) => v != null));
          bookCells = BOOKS.map((bk, j) => { const x = bl(g, bk); return x && x[sd + "_ml"] != null ? cell(odds(x[sd + "_ml"]), null, x[sd + "_ml_link"], prices[j] === top && prices.filter((v) => v != null).length > 1) : cell(null); });
        }
        return "<tr>" + (i === 0 ? "<td class='tm' rowspan='2'>" + esc(tip(g)) + "<div class='f clk' data-g='" + esc(g.game_id) + "'>" + (started(g) ? esc(clock(g)) : "") + "</div></td>" : "") +
          "<td class='team'>" + (i === 0 ? "<div class='tm-sm'>" + esc(tip(g)) + "<span class='clk2' data-g='" + esc(g.game_id) + "'>" + (started(g) ? " · " + esc(clock(g)) : "") + "</span></div>" : "") +
          (i === 1 && !g.neutral ? "<span class='f'>@ </span>" : "") + logo(g[sd + "_id"], 18) + esc(team) +
          " <span class='sc " + (g.state === "in" ? "b" : "m") + "' data-g='" + esc(g.game_id) + "' data-sd='" + sd + "'>" + (started(g) ? esc(g[sd + "_score"]) : "") + "</span>" +
          (g[sd + "_injuries"] ? "<div class='inj'>" + esc(g[sd + "_injuries"]) + "</div>" : "") + "</td><td class='r pts'>" + pts + "</td><td class='r b'>" + model + "</td>" +
          bookCells.map((c, j) => "<td class='bk" + (j >= 4 ? " bk-minor" : "") + "'>" + c + "</td>").join("") +
          "<td class='bestc'>" + best(g, sd, i) + "</td><td class='r edge'>" + edge + "</td></tr>";
      }).join("");
      return "<tbody class='g" + (hasBet ? " has-bet" : "") + "' data-gid='" + g.game_id + "'>" + rows + "</tbody>";
    }).join("");
    table.innerHTML = h;
  };
  document.querySelectorAll(".seg button").forEach((b) => b.onclick = () => {
    market = b.dataset.m; document.querySelectorAll(".seg button").forEach((x) => x.setAttribute("aria-pressed", x === b)); board(); watch(); });
  $("only-plays").onchange = board;
  board();
  // auto refresh hooks (cbb/autorefresh.py): keep the odds-board tab and "Plays only" across a reload
  window.otgState = () => ({market, only: $("only-plays").checked});
  window.otgRestore = (s) => {
    if (s.only) $("only-plays").checked = true;
    const b = document.querySelector(".seg button[data-m='" + s.market + "']");
    if (b && s.market !== market) b.onclick(); else board();
  };

  // Watch list: the odds-board tile of every game whose pick on the current tab is WATCH (becomes a play if the line
  // reaches the number shown) or REVIEW (edge above run_day.MAX_EDGE: never a play); a side already logged is under Plays
  const onWatch = (g, mk) => {
    const sd = mk === "spread" ? g.spread_side : String(g.total_pick || "").toLowerCase();
    return ["WATCH", "REVIEW"].includes(g[mk + "_verdict"]) && loggedSide(g, mk) !== sd && !heldOther(g, mk, sd);
  };
  const watch = () => {
    const mk = market === "total" ? "total" : "spread";
    $("watch-sec").hidden = market === "ml" || !D.games.some((g) => onWatch(g, "spread") || onWatch(g, "total"));
    boardInto($("t-watch"), D.games.filter((g) => onWatch(g, mk)), "No " + (mk === "total" ? "totals" : "spreads") + " on the watch list.");
  };
  watch();

  // Record
  if (st) {
    $("rec-sec").hidden = false;
    $("t-rec").innerHTML = "<thead><tr><th>Market</th><th class='r'>Record</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>ROI</th><th class='r'>Avg CLV</th><th class='r'>Beat close</th><th class='r'>Close coverage</th><th class='r'>Stake</th><th class='r'>Open</th></tr></thead><tbody>" +
      Object.entries(st).map(([mk, s]) => { const c = (D.record.clv && D.record.clv[mk]) || {};
        return "<tr><td>" + mk[0].toUpperCase() + mk.slice(1) + "</td><td class='r'>" + rec(s) + "</td><td class='r'>" + pct(s.win) + "</td><td class='r " +
        (s.units > 0 ? "pos" : s.units < 0 ? "neg" : "") + "'>" + sgn(s.units, 2) + "</td><td class='r'>" + pct(s.roi) + "</td><td class='r'>" + clvf(c.clv) +
        "</td><td class='r'>" + pct(c.beat) + "</td><td class='r'>" + (c.decided ? c.with_close + "/" + c.decided : "–") +
        "</td><td class='r'>" + Math.round(100 * s.multiplier) + "%" + capText(s.cap) + "</td><td class='r m'>" + s.open + "</td></tr>"; }).join("") + "</tbody>" +
      "<caption class='f' style='caption-side:bottom;text-align:left;padding:8px 12px;font-size:12px'>Alert CLV (points): the alert number against the consensus close (median of each book's last fresh quote in the 15 minutes before tip), decided plays with a close; close coverage = decided plays with one. CLV tracking: " + esc((D.record.clv && D.record.clv.status) || "") + ".</caption>";
    const R = D.record.recent || [];
    if (R.length) {
      $("recent-sec").hidden = false;
      $("t-recent").innerHTML = "<thead><tr><th>Date</th><th>Game</th><th>Bet</th><th>Book</th><th class='r'>Close</th><th class='r'>Alert CLV (pts)</th><th class='r hide-sm'>Same-book CLV (diagnostic)</th><th class='r'>Final</th><th class='r'>Result</th><th class='r'>Units</th></tr></thead><tbody>" +
        R.map((x) => "<tr><td class='m'>" + esc(x.date) + "</td><td>" + esc(x.away + " @ " + x.home) + "</td><td class='b'>" + esc(x.pick) + "</td><td>" + esc(x.book || "–") +
          "</td><td class='r'>" + (x.close_line == null ? "<span title='" + esc(x.clv_reason || "") + "'>n/a</span>" : num(x.close_line) + "<small> (" + x.books_primary + (x.books_primary === 1 ? " book: one-book close" : "") + "; pregame " + esc(x.pregame_check || "not checked") + ")</small>") +
          "</td><td class='r'>" + (x.clv_pts == null ? "<span title='" + esc(x.clv_reason || "") + "'>n/a</span>" : clvf(x.clv_pts)) +
          "</td><td class='r m hide-sm'>" + clvf(x.clv_same_book) + "</td><td class='r m'>" + esc(x.away_score) + "–" + esc(x.home_score) +
          "</td><td class='r b " + (x.result === "W" ? "pos" : x.result === "L" ? "neg" : "") + "'>" + esc(x.result) + "</td><td class='r'>" + sgn(x.profit, 2) + "</td></tr>").join("") + "</tbody>";
    }
  }

  // Loss review (review.py)
  const RV = D.record && D.record.review;
  if (RV && RV.by_reason) {
    $("review-sec").hidden = false;
    const rows = (obj, label) => Object.entries(obj || {}).map(([k, a]) => "<tr><td>" + esc(k) + "</td><td class='r'>" + a.bets + "</td><td class='r'>" + a.w + "–" + a.l +
      "</td><td class='r'>" + pct(a.win) + "</td><td class='r " + (a.units > 0 ? "pos" : a.units < 0 ? "neg" : "") + "'>" + sgn(a.units, 2) + "</td><td class='r'>" + (a.clv == null ? "–" : sgn(a.clv, 2)) +
      "</td>" + (label ? "<td class='r m'>" + ((RV.losses_by_reason || {})[k] || 0) + "</td>" : "") + "</tr>").join("");
    const head = (first, extra) => "<thead><tr><th>" + first + "</th><th class='r'>Bets</th><th class='r'>Record</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Avg CLV</th>" + (extra ? "<th class='r'>Losses</th>" : "") + "</tr></thead>";
    $("t-review").innerHTML = head("Reason", true) + "<tbody>" + rows(RV.by_reason, true) + "</tbody>";
    $("t-review2").innerHTML = head("Split", false) + "<tbody>" + rows(Object.fromEntries([
      ...Object.entries(RV.by_market || {}).map(([k, v]) => [k[0].toUpperCase() + k.slice(1), v]),
      ...Object.entries(RV.by_edge || {}).map(([k, v]) => ["Edge " + k, v]),
      ...Object.entries(RV.by_month || {}),
      ...Object.entries(RV.by_venue || {}).filter(([k]) => !k.startsWith("Total"))]), false) + "</tbody>";
    const HC = RV.home_court || {};
    if (HC.home) {
      const h = HC.home, nn = HC.neutral || {};
      const verdict = h.resid_se && Math.abs(h.resid) > 2 * h.resid_se ? (h.resid > 0 ? "home edge looks too low" : "home edge looks too high") : "no evidence our home edge is off";
      $("t-review2").insertAdjacentHTML("afterend", "<div class='scroll'><table><thead><tr><th>Home court check</th><th class='r'>Games</th><th class='r'>Result vs model</th><th class='r'>Close vs model</th></tr></thead><tbody>" +
        "<tr><td>Home games <span class='m'>(" + verdict + ")</span></td><td class='r'>" + h.games + "</td><td class='r'>" + sgn(h.resid, 2) + (h.resid_se ? " <span class='f'>± " + num(2 * h.resid_se, 2) + "</span>" : "") +
        "</td><td class='r'>" + (h.vs_close == null ? "–" : sgn(h.vs_close, 2)) + "</td></tr>" +
        (nn.games ? "<tr><td>Neutral sites</td><td class='r'>" + nn.games + "</td><td class='r'>" + sgn(nn.resid, 2) + "</td><td class='r'>" + (nn.vs_close == null ? "–" : sgn(nn.vs_close, 2)) + "</td></tr>" : "") +
        "</tbody></table></div><p class='note' style='padding:8px 16px 12px'>+ = home teams did better than our projection (or the closing line gave them more than we did). Biggest team misses at home: " +
        esc((HC.teams_high || []).map((t) => t[0] + " " + sgn(t[1])).join(", ")) + " · " + esc((HC.teams_low || []).map((t) => t[0] + " " + sgn(t[1])).join(", ")) + "</p>");
    }
    const MM = RV.model_misses || [];
    if (MM.length) $("t-misses").innerHTML = "<thead><tr><th>Market disagreed: biggest misses</th><th class='r'>Bet</th><th class='r'>Close</th><th class='r'>CLV</th><th class='r'>Model (home margin)</th><th class='r'>Final</th></tr></thead><tbody>" +
      MM.map((x) => "<tr><td>" + esc(x.date + " · " + x.away + " @ " + x.home) + "</td><td class='r b'>" + esc(x.pick) + "</td><td class='r'>" + num(x.close_line) + "</td><td class='r neg'>" + clvf(x.clv_pts) +
        "</td><td class='r m'>" + num(x.model) + "</td><td class='r m'>" + esc(x.away_score) + "–" + esc(x.home_score) + "</td></tr>").join("") + "</tbody>";
  }

  ["t-bandb", "t-rec", "t-recent", "t-review", "t-review2", "t-misses"].forEach(stack);   // t-plays, t-lm: their renders stack themselves   // t-plays: renderPlays() stacks itself

  // Ratings
  $("t-rat").innerHTML = "<thead><tr><th class='r'>#</th><th>Team</th><th class='r'>Net</th><th class='r'>Offense</th><th class='r'>Defense</th><th class='r'>Tempo</th></tr></thead><tbody>" +
    D.ratings.map((r) => "<tr><td class='r m'>" + r.rank + "</td><td>" + esc(r.team) + "</td><td class='r b'>" + sgn(r.net) + "</td><td class='r'>" + num(r.adj_oe) +
      "</td><td class='r'>" + num(r.adj_de) + "</td><td class='r'>" + num(r.adj_tempo) + "</td></tr>").join("") + "</tbody>";

  // Update: starts the "Update CBB card" workflow (token for this repo kept only in this browser)
  const REPO = D.repo, WF = "update.yml", API = "https://api.github.com/repos/" + REPO + "/actions";
  const RUNS_URL = "https://github.com/" + REPO + "/actions/workflows/" + WF;
  const store = { get: () => { try { return localStorage.getItem("gh_token_cbb") || ""; } catch (e) { return ""; } },
                  set: (v) => { try { v ? localStorage.setItem("gh_token_cbb", v) : localStorage.removeItem("gh_token_cbb"); } catch (e) {} } };
  const gen = new Date(D.generated_at);
  const ago = (d) => { const m = Math.round((Date.now() - d) / 60000);
    return m < 1 ? "just now" : m < 60 ? m + " min ago" : m < 1440 ? Math.round(m / 60) + " hr ago" : Math.round(m / 1440) + " days ago"; };
  const say = (t) => { $("upd-status").innerHTML = t; };
  const stamp = () => say("Updated " + gen.toLocaleString("en-US", {weekday: "short", hour: "numeric", minute: "2-digit"}) + " · " + ago(gen));
  stamp();
  setInterval(() => { if (!$("upd-btn").disabled && /^Updated /.test($("upd-status").textContent)) stamp(); }, 60000);
  const askKey = () => { const t = prompt("Paste a GitHub fine-grained token for " + REPO + " with Actions: Read and write.\nIt is saved only in this browser. Leave blank to remove it.", store.get());
    if (t !== null) store.set(t.trim()); return store.get(); };
  const gh = (path, opts) => fetch(API + path, Object.assign({ headers: { Accept: "application/vnd.github+json",
    Authorization: "Bearer " + store.get(), "X-GitHub-Api-Version": "2022-11-28" } }, opts || {}));
  const followRun = (since) => {
    const btn = $("upd-btn"); btn.disabled = true; const t0 = Date.now();
    const tick = async () => {
      try {
        const run = (await (await gh("/workflows/" + WF + "/runs?per_page=1")).json()).workflow_runs?.[0];
        const mins = Math.floor((Date.now() - t0) / 60000);
        if (!run || new Date(run.created_at) < since) say("Starting…");
        else if (run.status !== "completed") say("Updating… " + mins + " min · <a href='" + run.html_url + "' target='_blank' rel='noopener'>details</a>");
        else if (run.conclusion === "success") { say("Done. Reloading…"); setTimeout(() => location.replace(location.pathname + "?t=" + Date.now()), 4000); return; }
        else { say("Update failed · <a href='" + run.html_url + "' target='_blank' rel='noopener'>details</a>"); btn.disabled = false; return; }
      } catch (e) { say("Reconnecting…"); }
      setTimeout(tick, 10000);
    };
    tick();
  };
  $("upd-btn").onclick = async () => {
    if (!store.get() && !askKey()) { window.open(RUNS_URL, "_blank", "noopener"); say("No token: use Run workflow on GitHub"); return; }
    const since = new Date(Date.now() - 5000);
    say("Starting…");
    const branch = (await (await fetch("https://api.github.com/repos/" + REPO)).json().catch(() => ({}))).default_branch || "main";
    const r = await gh("/workflows/" + WF + "/dispatches", { method: "POST", body: JSON.stringify({ ref: branch }) }).catch(() => null);
    if (r && r.status === 204) followRun(since);
    else if (r && [401, 403, 404].includes(r.status)) { store.set(""); say("Token refused (" + r.status + "). Click Update to enter a new one."); }
    else say("Couldn't reach GitHub");
  };
  if (store.get()) gh("/workflows/" + WF + "/runs?per_page=1").then((r) => r.json()).then((j) => {
    const run = j.workflow_runs?.[0]; if (run && run.status !== "completed") followRun(new Date(run.created_at)); }).catch(() => {});

  // Live scores in the page itself (Chad, Nov 2: "time not updating"): while a game on this card is on, read ESPN's
  // free scoreboard every 30 seconds and repaint scores, clocks and final W/L in place. Display only; the published
  // card, the record and the bet log are unchanged (they update through the card run and cbb/live_refresh.py).
  if (!D.replay) {
    const SB = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?groups=50&limit=500&dates=";
    const GI = {};
    D.games.forEach((g) => { GI[String(g.game_id)] = g; });
    const paint = () => {
      document.querySelectorAll(".score[data-g]").forEach((el) => {
        const g = GI[el.dataset.g]; if (!g) return;
        el.hidden = !started(g);
        el.innerHTML = scoreInner(g, el.dataset.r === "1" ? cover(g, el.dataset.k, el.dataset.s, el.dataset.l === "" ? null : el.dataset.l) : null);
      });
      document.querySelectorAll(".clk[data-g], .clk2[data-g]").forEach((el) => {
        const g = GI[el.dataset.g]; if (!g) return;
        el.textContent = started(g) ? (el.classList.contains("clk2") ? " · " : "") + clock(g) : "";
      });
      document.querySelectorAll(".sc[data-g]").forEach((el) => {
        const g = GI[el.dataset.g]; if (!g) return;
        el.textContent = started(g) ? String(g[el.dataset.sd + "_score"] ?? "") : "";
        el.className = "sc " + (g.state === "in" ? "b" : "m");
      });
    };
    const active = () => { const now = Date.now();
      return D.games.some((g) => g.state === "in" || (g.state !== "post" && g.start && Date.parse(g.start) <= now + 300000 && Date.parse(g.start) > now - 14400000)); };
    const liveTick = async () => {
      if (document.hidden || !active()) return;
      try {
        const d = await (await fetch(SB + String(D.date).replace(/-/g, ""), {cache: "no-store"})).json();
        (d.events || []).forEach((ev) => {
          const g = GI[String(ev.id)]; if (!g) return;
          const st = ((ev.status || {}).type) || {}, c = (ev.competitions || [{}])[0] || {}, side = {};
          // by team, not by ESPN's home/away label (a game relisted with the other team at home; Nov 2)
          (c.competitors || []).forEach((t) => { const id = Number((t.team || {}).id);
            side[id === Number(g.home_id) ? "home" : id === Number(g.away_id) ? "away" : t.homeAway] = t; });
          if (st.state) g.state = st.state;
          ["home", "away"].forEach((sd) => { const v = side[sd] && side[sd].score; if (v != null && v !== "") g[sd + "_score"] = Number(v); });
          if (st.shortDetail) g.clock = st.shortDetail;
        });
        paint();
      } catch (e) {}
    };
    window.otgLiveTick = liveTick;
    setTimeout(liveTick, 1500);
    setInterval(liveTick, 30000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) liveTick(); });
  }

})();
</script>
__AUTOREFRESH__"""
