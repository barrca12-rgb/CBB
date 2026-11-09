"""Daily bet card: today's slate, the model's numbers, live lines from SportsGameOdds, and the plays.

    python -m cbb.run_day                        # today (US Eastern), live lines
    python -m cbb.run_day --date 2026-11-14      # another day
    python -m cbb.run_day --date 2026-01-17 --replay   # a past day with ESPN's stored closing lines (to check the page)
    python -m cbb.run_day --auto                 # what the scheduled runs use: tomorrow's card after 8pm ET,
                                                 # plus a card for each later day (up to a week) with lines posted

Writes reports/cbb_<date>.html (the bet card), reports/cbb_<date>.csv (every number), and reports/days.json.

Calls, from the 2024-2026 backtest against opening lines (BACKTEST.md):

    spread  edge 2.5+ points  BET 1u   (about 57% at the opener)   edge 1.5-2.5  WATCH
    total   edge 3+ points    BET 1u   (about 56.5%)                edge 2-3      WATCH

and at least +2% expected value at the book's price, from the backtest's win rate for that edge (win_prob). The
book is the one with the best expected value (number and price together); an edge that's there but at a bad price
is a WATCH.

The edge held against the opener, not the close, so the card is meant to be acted on early: each play shows the
worst number it's still a play at ("good down to").
"""
from __future__ import annotations

import argparse
import json
import math
import os
import urllib.request

import numpy as np
import pandas as pd

from . import (backtest, context, data, injuries, injury_sources, injury_watch, kenpom, news, notify, odds, players,
               projection, quotelog, ratings, report_html, review, teams, tracker)
from . import record as public_record   # build() has its own local named record
from . import record_page

REPORTS = os.path.join(os.path.dirname(__file__), "..", "reports")
SCOREBOARD = ("https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
              "?dates={}&groups=50&limit=500")
# Thresholds from the CLV check (Oct 2026), opener plays 2014-2017 and 2024-2026: spreads at 2.5-3 points won 55.4%
# with the line moving 0.86 points our way by the close (1,571 home-site plays; neutral sites the same, +0.89);
# totals at 3-4 won about 55.5% with +0.95 (3,421). Against the close these bands are near break-even, so they rely
# on betting early. Approved by Chad; was 3 (2.5 at neutral sites) and 4.
SPREAD_CALLS = [(2.5, "BET", 1.0)]
TOTAL_CALLS = [(3.0, "BET", 1.0)]
WATCH_BELOW = 1.0      # within this many points of a BET: WATCH (becomes a play if the line moves)
# Win chance by edge against the opener, 2014-2017 and 2024-2026 backtest (capped: bigger edges didn't win more):
# spreads 54.7% at 2-3 pts, 58.0% at 3-4, flat after; totals 54.2% at 3-4, 56.8-57.3% at 4-6.
WIN_PROB = {"spread": (0.0255, 0.58), "total": (0.014, 0.565)}
PREFERRED_BOOK = "DraftKings"   # same number and price at several books: the play goes to this one
MIN_EV = 0.02          # a play also needs +2% expected value at the book's price (3-pt spread edge: fine to -125)
# Bad-quote guards (approved by Chad Oct 30, after a sign-flipped BetMGM row with no price was logged as Villanova +7.5):
# live quotes always carry a price, so one without a price on our side is a broken row, never a play (replays of past
# days keep the -110 assumption: ESPN's stored lines have no prices); a book 3+ points off the median of the other
# books, with 3+ books quoting, is skipped; an edge above MAX_EDGE is shown as REVIEW, never a BET or an alert
OFF_MARKET, OFF_MARKET_BOOKS = 3.0, 3
MAX_EDGE = {"spread": 8.0, "total": 10.0}
BAD_QUOTES = os.path.join(os.path.dirname(__file__), "..", "lines", "bad_quotes.csv")
BAD_COLS = ["first_seen", "date", "game_id", "market", "side", "book", "number", "price", "median_others", "books", "reason"]
BAD = []               # skips from the last plays() call, written by build() on live runs
# Opener rule (Chad, Nov 2; protocol v2.4): a live signal is a play only if it also qualifies against the game's
# opener with the current model. The opener is each book's FIRST quote for that market on our side: its earliest row
# in lines/moves.csv (odds.MOVES, the card's own pull log since Oct 26) with the number and our side's price. A book
# with no such row is skipped (never assumed); a book the card sees for the first time on this run is its own opener.
# The bad-quote guards apply to first quotes too (no price, 3+ points off the other books' first numbers, edge above
# MAX_EDGE). With no usable first quote at any book the test cannot be applied and the signal stands. The game's opener is the best first quote on our side: one that qualifies (threshold and +2% EV at that
# quote's price) if any, else the largest edge. A signal that clears the live rule but fails this test is not logged,
# alerted or posted: it goes to research/linemove/signals.csv only. The test gates; the number bet is unchanged.
OPENER_RULE = True     # the switch the replay check (research/linemove/replay.py) turns off to compare
# Complete-ratings rule (Chad, Nov 4; protocol v2.6 Appendix D): a play for a game on ET date D is logged and alerted
# only once the ratings include every game before D: from READY_HOUR ET on D with Barttorvik's file for D-1 in use, or
# from BT_GRACE_HOUR ET on D if Barttorvik has not posted it. Earlier, a qualifying signal shows as pending.
RATINGS_RULE = False   # built and tested; OFF pending Chad (Nov 4 evidence: see MODEL_FREEZE)
READY_HOUR, BT_GRACE_HOUR = 6, 10


def ratings_ready(day, now: pd.Timestamp | None = None, bt_snapshot: str | None = None, first_day=None) -> bool:
    """True when a play for ET date `day` may be logged (Appendix D). bt_snapshot: the newest Barttorvik file in use
    (freshness.SEEN); first_day: the season's first game date (no earlier games: always ready)."""
    d = pd.Timestamp(str(day)[:10])
    if first_day is not None and d <= pd.Timestamp(str(first_day)[:10]):
        return True
    now_et = (now or pd.Timestamp.now(tz="UTC")).tz_convert("America/New_York").tz_localize(None)
    if now_et < d + pd.Timedelta(hours=READY_HOUR):
        return False
    if bt_snapshot is not None and pd.Timestamp(str(bt_snapshot)[:10]) >= d - pd.Timedelta(days=1):
        return True
    return now_et >= d + pd.Timedelta(hours=BT_GRACE_HOUR)


def _season_first_day(day) -> pd.Timestamp | None:
    try:
        sch = data.fetch("schedule", season_of(pd.Timestamp(str(day)[:10])))
        sch = sch[~sch["status_type_name"].isin(["STATUS_POSTPONED", "STATUS_CANCELED"])]
        first = pd.to_datetime(sch["date"], utc=True).dt.tz_convert("America/New_York").min()
        return None if pd.isna(first) else first.tz_localize(None).normalize()
    except Exception:
        return None
READY = {}             # complete-ratings rule: ET date -> ready, per plays() call
# Input-failure hold (Chad, Nov 4): ET date -> reason, when a card day's box scores could not be loaded at all (no
# download and no valid earlier copy) after games have been played. Its plays are held: shown as a watch, not logged,
# alerted or posted, and one phone alert says why. A source that simply has not updated yet never holds anything.
INPUT_HOLD = {}
HOLD_ALERTED = os.path.join(os.path.dirname(__file__), "..", "bets", "input_hold_alerted.json")
GATED = []             # signals stopped by the opener rule in the last plays() call, written by build() on live runs
LINEMOVE_SIGNALS = os.path.join(os.path.dirname(__file__), "..", "research", "linemove", "signals.csv")
LINEMOVE_COLS = ["seen_at", "date", "game_id", "start", "home_id", "away_id", "home", "away", "market", "side",
                 "bet_type", "pick", "opener_line", "opener_price", "opener_book", "opener_first_seen", "line", "price",
                 "book", "move_pts", "minutes_since_open", "edge_vs_opener", "edge_vs_current", "model"]
# Opening week (first 7 days of the season): totals are shifted so the day's average matches KenPom's, keeping our
# game-to-game differences. The model starts each season at last season's scoring level, and in 2026-27 that put every
# total about 3.6 below KenPom and the market: one league-wide bet that scoring falls back, not game-by-game edges.
# Approved by Chad (Oct 26 2026) as a stopgap while a preseason scoring-level fix is tested.
OPENING_WEEK = pd.Timedelta(days=7)


def win_prob(market: str, edge: float) -> float:
    slope, cap = WIN_PROB[market]
    return float(min(max(0.5 + slope * edge, 0.5), cap))


def ev(p: float, odds) -> float:
    o = -110.0 if odds is None or (isinstance(odds, float) and math.isnan(odds)) else float(odds)
    return p * (o / 100 if o > 0 else 100 / -o) - (1 - p)


def price_needed(market: str, thr: float, good_to: float, higher_better: bool) -> float:
    """Worst American price that still clears MIN_EV at the half-point line where a WATCH becomes a play (the card's
    "bet at" number). The number alone isn't enough: at 3 points a total needs about -113, not -115."""
    at = (math.ceil(good_to * 2 - 1e-9) if higher_better else math.floor(good_to * 2 + 1e-9)) / 2
    p = win_prob(market, thr + abs(at - good_to))
    pay = (MIN_EV + 1 - p) / p                # winnings per unit risked needed for +MIN_EV
    return float(math.ceil(100 * pay)) if pay >= 1 else -float(math.floor(100 / pay))


def season_of(day: pd.Timestamp) -> int:
    return day.year + 1 if day.month >= 8 else day.year


def today_et() -> pd.Timestamp:
    return pd.Timestamp.now(tz="America/New_York").normalize().tz_localize(None)


def slate(day: pd.Timestamp) -> pd.DataFrame:
    """Every D-I game on `day` from ESPN's scoreboard."""
    req = urllib.request.Request(SCOREBOARD.format(day.strftime("%Y%m%d")), headers={"User-Agent": "cbb-model"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    rows = []
    for ev in d.get("events") or []:
        c = (ev.get("competitions") or [{}])[0]
        side = {t.get("homeAway"): t for t in c.get("competitors") or []}
        if "home" not in side or "away" not in side:
            continue
        st = (ev.get("status") or {}).get("type") or {}
        rows.append({
            "game_id": int(ev["id"]), "start": ev.get("date"), "home_id": int(side["home"]["team"]["id"]),
            "away_id": int(side["away"]["team"]["id"]), "home": side["home"]["team"].get("location"),
            "away": side["away"]["team"].get("location"), "neutral": bool(c.get("neutralSite")),
            "conf_game": bool(c.get("conferenceCompetition")), "state": st.get("state", "pre"),
            "home_score": pd.to_numeric(side["home"].get("score"), errors="coerce"),
            "away_score": pd.to_numeric(side["away"].get("score"), errors="coerce"),
            "note": "; ".join(n.get("headline", "") for n in c.get("notes") or [] if n.get("headline")),
        })
    return pd.DataFrame(rows)


def load_box_scores(season: int, day, schedule: pd.DataFrame | None, refresh: bool = False):
    """(games, team games) for the stage-1 ratings, or (None, None). Before the season's first game no box scores is
    expected. After it: a failed download falls back to the last downloaded copy (valid input, printed); with no valid
    copy at all the card day is held (INPUT_HOLD), never silently rated on the preseason prior alone."""
    try:
        return data.season_games(season, refresh=refresh)
    except Exception as e:
        if not games_played_before(schedule, day):
            return None, None
        try:
            out = data.season_games(season, refresh=False)
            print(f"Box-score download failed ({e}); using the last downloaded copy.")
            return out
        except Exception as e2:
            INPUT_HOLD[f"{pd.Timestamp(day):%Y-%m-%d}"] = f"box scores could not be loaded ({e2})"
            print(f"INPUT FAILURE: box scores for {season} could not be loaded ({e2}). Plays for {pd.Timestamp(day):%Y-%m-%d} "
                  f"are held: not logged, alerted or posted.")
            return None, None


def games_played_before(schedule: pd.DataFrame | None, day) -> bool:
    """True when the schedule has a completed game before ET date `day` (the stage-1 ratings need box scores)."""
    try:
        done = schedule[schedule["status_type_completed"].fillna(False).astype(bool)]
        d = pd.to_datetime(done["date"], utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None).dt.normalize()
        return bool((d < pd.Timestamp(str(day)[:10])).any())
    except Exception:
        return True            # cannot tell: treat as played, so a failure is never silent


def project(day: pd.Timestamp, games: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Final margin and total for each game, and the ratings table, using only games before `day`."""
    season = season_of(day)
    INPUT_HOLD.pop(f"{day:%Y-%m-%d}", None)
    sch_all = data.fetch("schedule", season, refresh=day >= today_et() - pd.Timedelta(days=1))
    hist, tg = load_box_scores(season, day, sch_all, refresh=day >= today_et() - pd.Timedelta(days=1))
    if hist is None:
        hist = pd.DataFrame({"home_pts": [], "away_pts": [], "date": pd.to_datetime([])})
        tg = pd.DataFrame({c: [] for c in ["team_id", "opp_id", "venue", "ppp", "pace"] + ratings.FACTORS}).assign(
            date=pd.to_datetime([]))
    ids = sorted(set(teams.load()["espn_id"]) | set(tg.get("team_id", [])))
    games = games[games["home_id"].isin(ids) & games["away_id"].isin(ids)].copy()
    last = data.season_games(season - 1)
    league = ratings.league_averages(last[1])
    r = ratings.fit(tg, day, ids, backtest.preseason_prior(season), league=league)
    p = ratings.predict(r, games["home_id"], games["away_id"], games["neutral"])
    p.index = games.index
    b = games.join(p.add_prefix("pred_")).assign(season=season, date=day, games_before=r["games"],
                                                 home_pts=np.nan, away_pts=np.nan)

    # KenPom: FanMatch once it's published for the day, else KenPom's current ratings with the same method.
    kp = None
    try:
        kp = kenpom.fanmatch(day.strftime("%Y-%m-%d")) if day <= today_et() else None
    except Exception:
        kp = None
    if kp is not None and len(kp):
        from .evaluate import fanmatch as fm
        kp = fm(b[["game_id", "date", "home_id", "away_id"]])
    else:
        kp = kenpom.predict_from_ratings(b, season)
    b = b.merge(kp, on="game_id", how="left")

    av = players.next_excess_missing(season) if day >= today_et() - pd.Timedelta(days=1) else None
    if av is not None:   # going-into-next-game availability, attached to today's game for each team
        sides = pd.concat([b[["game_id", c]].rename(columns={c: "team_id"}) for c in ("home_id", "away_id")])
        av = sides.merge(av, on="team_id", how="left").fillna({"excess_missing": 0.0})
        # injury report: expected missing minutes for listed players who played the last game (injuries.py)
        try:
            inj_team, inj_players = injuries.adjustment(season)
        except Exception as e:
            print(f"Injury report unavailable ({e}); using last game's lineups only.")
            inj_team, inj_players = pd.DataFrame(columns=["team_id", "injury_missing"]), pd.DataFrame()
        av = av.merge(inj_team, on="team_id", how="left").fillna({"injury_missing": 0.0})
        av["excess_missing"] = av["excess_missing"] + av["injury_missing"]
        im = inj_team.set_index("team_id")["injury_missing"] if len(inj_team) else pd.Series(dtype=float)
        with open(projection.SAVED) as fh:
            miss_w = json.load(fh)["margin"].get("miss_diff", 0.0)   # points per 1.0 of minutes missing (home side)
        nt = injuries.notes(inj_players, abs(miss_w)) if len(inj_players) else {}
        for sd in ("home", "away"):
            b[f"{sd}_injury_missing"] = b[f"{sd}_id"].map(im).fillna(0.0)
            b[f"{sd}_injuries"] = b[f"{sd}_id"].map(nt).fillna("")
    played = hist[(hist["date"] < day)].dropna(subset=["home_pts"]) if len(hist) else hist
    # scoring environment: this season's average total once it has 200 games, before that last season's
    last_avg = float((last[0]["home_pts"] + last[0]["away_pts"]).mean())
    live = {"team_hca": projection.saved_team_hca(), "season": season,
            "season_avg_total": float((played["home_pts"] + played["away_pts"]).mean()) if len(played) >= 200 else last_avg}
    if av is not None:
        live["availability"] = av[["game_id", "team_id", "excess_missing"]]
    # context: market ratings from this season's closing lines, referee crews if posted (context.py)
    keys = b[["game_id", "season", "date", "home_id", "away_id", "neutral"]]
    closes = context.live_closes(os.path.join(odds.LINES, "closing.csv"), hist) if len(hist) else pd.DataFrame()
    ctx = context.market(keys, closes) if len(closes) else keys[["game_id"]].assign(mkt_margin=0.0, mkt_total=0.0, mkt_n=0)
    refs = context.live_referees(b["game_id"], projection.REFEREES) if day >= today_et() - pd.Timedelta(days=1) else \
        pd.DataFrame(columns=["game_id", "ref_fouls", "ref_pts", "crew"])
    live["context"] = ctx.merge(refs[["game_id", "ref_fouls", "ref_pts"]], on="game_id", how="left")
    b = b.merge(refs[["game_id", "crew"]], on="game_id", how="left")
    f = projection.apply_saved(projection.add_features(b, live))
    f = roster_spreads(f, day, tg, ids, league, season)
    return f, ratings.table(r)


# Roster-based spreads (Chad, Nov 9: "yes do it, test it and push it"; research/roster_prior R3v4, the blend the
# rp4 shadow has run since Nov 5): the spread margin starts each team from the average of the current preseason prior
# and our roster-based prior (F2) and uses that blend's own stage-2 margin weights (data/shadow_rp4.json), then the
# blowout correction. Totals stay v1's (the blend did not pass on early totals). The roster prior is built once a day
# and cached. Any failure keeps v1's margin for the run and says so.
RP4_COEF = os.path.join(os.path.dirname(__file__), "..", "data", "shadow_rp4.json")
RP4_CACHE = os.path.join(os.path.dirname(__file__), "cache", "rp4")


def _roster_prior(season: int) -> pd.DataFrame:
    from . import shadow_rp4
    path = os.path.join(RP4_CACHE, f"f2_{season}_{today_et():%Y%m%d}.csv")
    if os.path.exists(path):
        return pd.read_csv(path, index_col=0)
    f2 = shadow_rp4.roster_prior(season)
    os.makedirs(RP4_CACHE, exist_ok=True)
    f2.to_csv(path)
    return f2


def roster_spreads(f: pd.DataFrame, day: pd.Timestamp, tg, ids, league, season: int) -> pd.DataFrame:
    f = f.assign(v1_final_margin=f["final_margin"])
    if not len(f) or not len(tg):
        return f
    try:
        from . import shadow_rp4
        cur = backtest.preseason_prior(season)
        bl = shadow_rp4.blended(cur, _roster_prior(season))
        fb = shadow_rp4.with_blend(f, day, tg, ids, league, cur, bl)
        with open(RP4_COEF) as fh:
            m = shadow_rp4.apply(fb, json.load(fh))["final_margin"]
        x = projection.BLOWOUT_K * np.maximum(0.0, m.abs() - projection.BLOWOUT_T)
        f["final_margin"] = (m + np.sign(m).replace(0, 1) * x).to_numpy()
    except Exception as e:
        print(f"Roster-based spreads unavailable for {day:%Y-%m-%d} ({e}); v1 margins used.")
    return f


def opening_week_totals(f: pd.DataFrame, day: pd.Timestamp) -> pd.DataFrame:
    """Through the season's first OPENING_WEEK (and any earlier games, which the schedule feed can miss), shift
    final_total by the day's average gap to KenPom (kp_total) and record the shift in total_shift. Unchanged
    otherwise, or when KenPom has none of the day's games."""
    sch = data.fetch("schedule", season_of(day))
    sch = sch[~sch["status_type_name"].isin(["STATUS_POSTPONED", "STATUS_CANCELED"])]
    first = pd.to_datetime(sch["date"], utc=True).dt.tz_convert("America/New_York").min()
    if pd.isna(first) or day >= first.tz_localize(None).normalize() + OPENING_WEEK or "kp_total" not in f:
        return f
    gap = (f["final_total"] - f["kp_total"]).mean()
    if pd.isna(gap):
        return f
    f = f.copy()
    f["final_total"] = f["final_total"] - gap
    f["total_shift"] = -gap
    print(f"Opening week: totals shifted {-gap:+.1f} to KenPom's scoring level.")
    return f


def _best(lines: pd.DataFrame, market: str, sides: dict, live: bool = False, skip=None):
    """Best (side, book row, edge, win prob, EV) across books and both sides. sides: side -> (line column, edge function
    of the line, odds column). Live, a quote with no price on the side is skipped (skip(row, side, number, reason)
    records it).

    A quote that qualifies wins over one that only prices better (approved by Chad Oct 31, after DraftKings' High
    Point -6.5 at -110, a full play, lost to theScore's -7.5 at +100 by 0.09% of EV and the game fell to WATCH):
    first the quotes that make a BET (cutoff edge and +2% EV), then those that make band B, then the rest; within a
    tier, the highest EV (then edge, then the preferred book). An edge above MAX_EDGE (REVIEW) ranks below all."""
    cut = (SPREAD_CALLS if market == "spread" else TOTAL_CALLS)[0][0]
    lo, hi = tracker.BAND_B_RANGE[market]

    def tier(e: float, v: float) -> int:
        if e > MAX_EDGE[market]:
            return -1
        if e >= cut and v >= MIN_EV:
            return 2
        if tracker.BAND_B_ON[market] and lo <= e < hi and v >= MIN_EV:
            return 1
        return 0
    best = None
    for side, (col, edge_fn, odds_col) in sides.items():
        for _, row in lines.dropna(subset=[col]).iterrows():
            e = float(edge_fn(row[col]))
            if e <= 0:
                continue
            if live and pd.isna(row.get(odds_col)):
                if skip:
                    skip(row, side, row[col], "no price")
                continue
            p = win_prob(market, e)
            v = ev(p, row.get(odds_col))
            key = (tier(e, v), round(v, 6), round(e, 6), row.get("book") == PREFERRED_BOOK)
            if best is None or key > best[5]:
                best = (side, row, e, p, v, key)
    return best[:5] if best else None


# Stake by edge (Chad, Nov 9: "improve the results now"; research/selection_cut test 3): 1u at the bar, 1.5u from
# bar + 1, 2u from bar + 2. Backtest 2015-17 and 2024-26, both markets: more units and higher ROI than flat 1u;
# the largest edges won 59.5-61.3%. The stake multiplier (tracker.status) still scales every stake.
EDGE_TIERS = ((2.0, 2.0), (1.0, 1.5))


def edge_tier(edge: float, thr: float) -> float:
    for over, mult in EDGE_TIERS:
        if edge >= thr + over:
            return mult
    return 1.0


def _call(edge: float, value: float, calls) -> tuple[str, float]:
    thr, name, units = calls[0]
    if edge >= thr and value >= MIN_EV:
        return name, units * edge_tier(edge, thr)
    if edge >= thr - WATCH_BELOW:   # close on the number, or there on the number but not the price
        return "WATCH", 0.0
    return "PASS", 0.0


def _band_b(market: str, edge: float, value: float, verdict: str) -> bool:
    """Band B (tracker.BAND_B, approved Oct 29): the same best play (book, side, EV) at an edge in the band below v1's
    cutoff that passes v1's +2% EV rule. Never a v1 BET, and it never changes v1's columns."""
    lo, hi = tracker.BAND_B_RANGE[market]
    return bool(tracker.BAND_B_ON[market] and verdict != "BET" and lo <= edge < hi and value >= MIN_EV)


def _off_market(l: pd.DataFrame, col: str) -> pd.DataFrame:
    """Rows whose number in col is OFF_MARKET+ points from the median of the other books, when OFF_MARKET_BOOKS+
    books quote it; adds median_others and books."""
    q = l.dropna(subset=[col])
    if q["book"].nunique() < OFF_MARKET_BOOKS:
        return q.iloc[0:0].assign(median_others=np.nan, books=0)
    med = [float(q.drop(index=i)[col].median()) for i in q.index]
    q = q.assign(median_others=med, books=q["book"].nunique())
    return q[(q[col] - q["median_others"]).abs() >= OFF_MARKET]


def first_quotes(path: str | None = None, openers: str | None = None) -> pd.DataFrame:
    """Each book's first quote per game, market and side from lines/moves.csv (its earliest row with that market's
    number), oriented by ESPN ids (lo/hi): columns lo_id, hi_id, date, book, market, side ("lo"/"hi" for spreads,
    "over"/"under"), number (spreads: the lo team's line), price (empty when that first row had no price on the side:
    the book is then skipped by the opener test, never given a later price), seen_at.

    lines/moves.csv starts Oct 26, 12:32 UTC. lines/openers.csv has each book's first number (no price) since Oct 25:
    where it saw a book more than 5 minutes before moves.csv did, that earlier number is the book's first quote, with
    no price, so the book is skipped for that game (6 games posted Oct 25-26, DraftKings and Caesars)."""
    path = path or odds.MOVES
    cols = ["lo_id", "hi_id", "date", "book", "market", "side", "number", "price", "seen_at"]
    if not os.path.exists(path):
        return pd.DataFrame(columns=cols)
    m = pd.read_csv(path).sort_values("pulled_at", kind="stable")
    rows = []
    for market, side, num, price in (("spread", "lo", "spread", "spread_odds_lo"), ("spread", "hi", "spread", "spread_odds_hi"),
                                     ("total", "over", "total", "over_odds"), ("total", "under", "total", "under_odds")):
        q = m.dropna(subset=[num]).drop_duplicates(["game_key", "book"], keep="first")
        rows.append(pd.DataFrame({"lo_id": q["lo_id"].astype(int), "hi_id": q["hi_id"].astype(int), "date": q["date"],
                                  "book": q["book"], "market": market, "side": side, "number": q[num],
                                  "price": q[price], "seen_at": q["pulled_at"]}))
    fq = pd.concat(rows, ignore_index=True)
    op_path = openers if openers is not None else (os.path.join(odds.LINES, "openers.csv") if path == odds.MOVES else None)
    if op_path and os.path.exists(op_path):
        o = pd.read_csv(op_path).dropna(subset=["home_id", "away_id", "first_seen"])
        if len(o):
            o_lo = np.minimum(o["home_id"], o["away_id"]).astype(int)
            o_hi = np.maximum(o["home_id"], o["away_id"]).astype(int)
            home_lo = o["home_id"].astype(int) == o_lo
            seen = pd.to_datetime(o["first_seen"], utc=True, format="ISO8601")
            earlier = []
            for market, sides in (("spread", ("lo", "hi")), ("total", ("over", "under"))):
                n = (np.where(home_lo, o["open_home_spread"], -o["open_home_spread"]) if market == "spread"
                     else o["open_total"])
                for sd in sides:
                    earlier.append(pd.DataFrame({"lo_id": o_lo, "hi_id": o_hi, "date": o["game_key"].astype(str).str[:10],
                                                 "book": o["book"], "market": market, "side": sd, "number": n,
                                                 "price": np.nan, "seen_at": seen.dt.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                                                 "_t": seen}))
            e = pd.concat(earlier, ignore_index=True).dropna(subset=["number"])
            k = ["lo_id", "hi_id", "date", "book", "market", "side"]
            mt = fq.assign(_m=pd.to_datetime(fq["seen_at"], utc=True, format="ISO8601"))[k + ["_m"]]
            e = e.merge(mt, on=k, how="left")
            e = e[e["_m"].isna() | (e["_t"] < e["_m"] - pd.Timedelta(minutes=5))].drop(columns=["_t", "_m"])
            if len(e):
                drop = set(map(tuple, e[k].astype(str).to_numpy()))
                fq = pd.concat([fq[[tuple(r) not in drop for r in fq[k].astype(str).to_numpy()]], e], ignore_index=True)
    return fq


def opener_test(fq: pd.DataFrame, g, market: str, side: str, model: float, thr: float, cur: pd.DataFrame,
                now: str | None = None) -> tuple[bool, dict | None]:
    """The opener rule for one signal: (passes, the opener used). fq: first_quotes(); g: the card's game (home_id,
    away_id, start); side: home/away/over/under; model: the margin (home) or total; thr: the edge the signal needs;
    cur: this run's quotes for the game (home/away oriented), the opener for any book with no earlier quote."""
    h, a = int(g["home_id"]), int(g["away_id"])
    lo, hi = min(h, a), max(h, a)
    st = pd.to_datetime(g.get("start"), utc=True, errors="coerce")
    day = pd.Timestamp(st.tz_convert("America/New_York").date()) if pd.notna(st) else None
    q = fq[(fq["lo_id"] == lo) & (fq["hi_id"] == hi) & (fq["market"] == market)] if len(fq) else fq
    if day is not None and len(q):   # the same pairing within a day either side (feeds can disagree on the start)
        q = q[(pd.to_datetime(q["date"]) - day).abs() <= pd.Timedelta(days=1)]
    if market == "spread":
        want = "lo" if (side == "home") == (h == lo) else "hi"
        q = q[q["side"] == want]
        num = q["number"] * (1 if want == "lo" else -1)           # our side's own line
        cols = ("home_spread", f"{side}_spread_odds")
        cn = cur[cols[0]] * (1 if side == "home" else -1) if len(cur) else pd.Series(dtype=float)
    else:
        q = q[q["side"] == side]
        num = q["number"]
        cols = ("total", f"{side}_odds")
        cn = cur[cols[0]] if len(cur) else pd.Series(dtype=float)
    c = pd.DataFrame({"book": q["book"], "number": num, "price": q["price"], "seen_at": q["seen_at"]})
    if len(cur):   # a book seen for the first time on this run is its own opener
        new = cur[~cur["book"].isin(set(c["book"]))]
        c = pd.concat([c, pd.DataFrame({"book": new["book"], "number": cn.reindex(new.index), "price": new[cols[1]],
                                        "seen_at": now or pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")})],
                      ignore_index=True)
    c = c.dropna(subset=["number", "price"])   # a first quote without a price: that book is skipped
    if len(c) and c["book"].nunique() >= OFF_MARKET_BOOKS:      # a first quote far off the others' is a broken row
        med = [float(c.drop(index=i)["number"].median()) for i in c.index]
        c = c[(c["number"] - pd.Series(med, index=c.index)).abs() < OFF_MARKET]
    if not len(c):   # no usable first quote at any book: the test cannot be applied, and missing data never fails it
        return True, None
    if market == "spread":
        c["edge"] = (model + c["number"]) if side == "home" else (c["number"] - model)
    else:
        c["edge"] = (model - c["number"]) if side == "over" else (c["number"] - model)
    c = c[c["edge"] <= MAX_EDGE[market]]
    if not len(c):
        return True, None
    c["ev"] = [ev(win_prob(market, e), p) for e, p in zip(c["edge"], c["price"])]
    c["ok"] = (c["edge"] >= thr) & (c["ev"] >= MIN_EV)
    c["pay"] = [(p / 100 if p > 0 else 100 / -p) for p in c["price"]]
    best = c.sort_values(["ok", "edge", "pay"], ascending=False).iloc[0]
    return bool(best["ok"]), {"book": best["book"], "line": float(best["number"]), "price": float(best["price"]),
                              "edge": float(best["edge"]), "seen_at": best["seen_at"]}


def plays(f: pd.DataFrame, lines: pd.DataFrame, live: bool = True, fq: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per game: the best spread and total play across books. live: apply the no-price and off-market
    guards and the opener rule (replays of past days have one priceless ESPN line per game). fq: first quotes for the
    opener rule (default: read from lines/moves.csv)."""
    global BAD, GATED, READY
    BAD = []
    GATED = []
    READY = {}
    if live and fq is None:
        try:
            fq = first_quotes()
        except Exception as e:   # unreadable first-quote log: this run's quotes are the openers (logged)
            print(f"First quotes unreadable ({e}); this run's quotes stand as the openers.")
            fq = None
    if fq is None:
        fq = first_quotes("/nonexistent")
    now = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    out = []
    for _, g in f.iterrows():
        l = lines[(lines["home_id"] == g["home_id"]) & (lines["away_id"] == g["away_id"])]
        flip = lines[(lines["home_id"] == g["away_id"]) & (lines["away_id"] == g["home_id"])]
        if not len(l) and len(flip):   # book lists the teams the other way round (neutral sites)
            l = flip.rename(columns={"home_spread_odds": "away_spread_odds", "away_spread_odds": "home_spread_odds",
                                     "home_spread_link": "away_spread_link", "away_spread_link": "home_spread_link",
                                     "home_ml": "away_ml", "away_ml": "home_ml"}).assign(
                home_spread=-flip["home_spread"], open_home_spread=-flip.get("open_home_spread", np.nan))
        m, t = g["final_margin"], g["final_total"]
        r = {k: g[k] for k in ["game_id", "start", "home", "away", "home_id", "away_id", "neutral", "state",
                               "home_score", "away_score", "note", "home_injuries", "away_injuries",
                               "home_injury_missing", "away_injury_missing", "crew"] if k in g}
        r.update(model_margin=m, model_total=t, model_home_spread=-m,
                 model_home_pts=(t + m) / 2, model_away_pts=(t - m) / 2, kp_margin=g.get("kp_margin"),
                 raw_margin=g.get("pred_margin"), home_missing=g.get("home_missing"), away_missing=g.get("away_missing"),
                 # each source alone, for the in-season check of our ratings against KenPom and Barttorvik
                 raw_total=g.get("pred_total"), kp_total=g.get("kp_total"), bt_margin=g.get("bt_margin"),
                 bt_total=g.get("bt_total"),
                 p_home_win=0.5 * (1 + math.erf(m / 11.0 / math.sqrt(2))), n_books=l["book"].nunique(),
                 total_shift=g.get("total_shift", 0.0))
        r["book_lines"] = l.drop(columns=[c for c in ("home_id", "away_id", "sgo_event", "start") if c in l]).to_dict("records")
        if len(l):
            r["line_home_spread"] = float(l["home_spread"].median()) if l["home_spread"].notna().any() else np.nan
            r["line_total"] = float(l["total"].median()) if l["total"].notna().any() else np.nan
            if "open_home_spread" in l:
                r["open_home_spread"] = float(l["open_home_spread"].median()) if l["open_home_spread"].notna().any() else np.nan
            if "open_total" in l:
                r["open_total"] = float(l["open_total"].median()) if l["open_total"].notna().any() else np.nan
            def skip(mk):
                def rec(row, side, number, reason, med=np.nan, books=np.nan):
                    BAD.append({"date": str(g.get("date", ""))[:10], "game_id": g["game_id"], "market": mk, "side": side,
                                "book": row.get("book"), "number": number, "price": row.get(f"{side}_spread_odds" if mk == "spread" else f"{side}_odds"),
                                "median_others": med, "books": books, "reason": reason})
                return rec
            ls, lt = l, l
            if live:   # a book far off every other book's number is a broken or stale quote, not a price to bet
                for mk, col in (("spread", "home_spread"), ("total", "total")):
                    off = _off_market(l, col)
                    for i, row in off.iterrows():
                        skip(mk)(row, "-", row[col], "off-market", row["median_others"], row["books"])
                    if len(off):
                        if mk == "spread":
                            ls = l.drop(index=off.index)
                        else:
                            lt = l.drop(index=off.index)
            def gate(mk, side, row, edge, value, v, units, bandb, cur):
                """The opener rule on a live BET, WATCH or band B signal: returns (verdict, units, bandb, gated)."""
                if not live or not OPENER_RULE or not (v in ("BET", "WATCH") or bandb):
                    return v, units, bandb, False
                model = m if mk == "spread" else t
                thr = (SPREAD_CALLS if mk == "spread" else TOTAL_CALLS)[0][0]
                ok, op = opener_test(fq, g, mk, side, model, thr, cur, now)
                ok_b, op_b = (opener_test(fq, g, mk, side, model, tracker.BAND_B_RANGE[mk][0], cur, now)
                              if bandb else (False, None))
                gated = False
                for kind, passed, o in (("v1", ok, op), ("bandB", ok_b, op_b)):
                    if (kind == "v1" and v != "BET") or (kind == "bandB" and not bandb) or passed:
                        continue
                    gated = True
                    line = (row["home_spread"] if side == "home" else -row["home_spread"]) if mk == "spread" else row["total"]
                    pick = (f"{g['home'] if side == 'home' else g['away']} {line:+g}" if mk == "spread"
                            else f"{side.title()} {line:g}")
                    e_op = o["edge"] if o else np.nan
                    st = pd.to_datetime(g.get("start"), utc=True, errors="coerce")
                    GATED.append({"seen_at": now, "date": str(g.get("date", ""))[:10] or (str(st.tz_convert("America/New_York").date()) if pd.notna(st) else ""),
                                  "game_id": g["game_id"], "start": g.get("start"), "home_id": g["home_id"], "away_id": g["away_id"],
                                  "home": g["home"], "away": g["away"], "market": mk, "side": side, "bet_type": kind,
                                  "pick": pick, "opener_line": o["line"] if o else np.nan, "opener_price": o["price"] if o else np.nan,
                                  "opener_book": o["book"] if o else None, "opener_first_seen": o["seen_at"] if o else None,
                                  "line": line, "price": row.get(f"{side}_spread_odds" if mk == "spread" else f"{side}_odds"),
                                  "book": row.get("book"), "move_pts": round(edge - e_op, 2) if o else np.nan,
                                  "minutes_since_open": round((pd.Timestamp(now) - pd.Timestamp(o["seen_at"])).total_seconds() / 60, 1) if o else np.nan,
                                  "edge_vs_opener": round(e_op, 2) if o else np.nan, "edge_vs_current": round(edge, 2),
                                  "model": round(float(model), 2)})
                if v in ("BET", "WATCH") and not ok:
                    v, units = "PASS", 0.0
                if bandb and not ok_b:
                    bandb = False
                return v, units, bandb, gated
            def ready_gate(mk, v2, u2, b2):
                """Appendix D: a qualifying play (BET or band B) before the ratings include the previous day's games
                is pending: shown as a watch, not logged, alerted or posted."""
                if not live or not RATINGS_RULE or not (v2 == "BET" or b2):
                    return None
                st_ = pd.to_datetime(g.get("start"), utc=True, errors="coerce")
                gday = str(g.get("date", ""))[:10] or (str(st_.tz_convert("America/New_York").date()) if pd.notna(st_) else "")
                if not gday:
                    return None
                if gday not in READY:
                    from . import freshness
                    READY[gday] = ratings_ready(gday, pd.Timestamp(now), (freshness.SEEN.get("barttorvik") or {}).get("snapshot"),
                                                _season_first_day(gday))
                if READY[gday]:
                    return None
                return ("WATCH" if v2 == "BET" else v2), 0.0, False
            def hold_gate(v2, b2):
                """Input-failure hold: a qualifying play on a day whose box scores could not be loaded is held."""
                if not live or not (v2 == "BET" or b2):
                    return None
                st_ = pd.to_datetime(g.get("start"), utc=True, errors="coerce")
                gday = str(g.get("date", ""))[:10] or (str(st_.tz_convert("America/New_York").date()) if pd.notna(st_) else "")
                if gday not in INPUT_HOLD:
                    return None
                return ("WATCH" if v2 == "BET" else v2), 0.0, False
            # spread: home edge at line s is m + s; away edge is -(m + s)
            sp = _best(ls, "spread", {"home": ("home_spread", lambda s_: m + s_, "home_spread_odds"),
                                      "away": ("home_spread", lambda s_: -(m + s_), "away_spread_odds")}, live, skip("spread"))
            if sp:
                side, row, edge, p, value = sp
                calls = SPREAD_CALLS
                v, units = _call(edge, value, calls)
                if edge > MAX_EDGE["spread"]:   # no real disagreement is this large: shown for review, never bet
                    BAD.append({"date": str(g.get("date", ""))[:10], "game_id": g["game_id"], "market": "spread", "side": side,
                                "book": row.get("book"), "number": row["home_spread"] if side == "home" else -row["home_spread"],
                                "price": row.get(f"{side}_spread_odds"), "median_others": np.nan, "books": np.nan,
                                "reason": f"review: edge {edge:.1f}"})
                    v, units = "REVIEW", 0.0
                line = row["home_spread"] if side == "home" else -row["home_spread"]
                thr = calls[0][0]
                r.update(spread_pick=g["home"] if side == "home" else g["away"], spread_side=side, spread_line=line,
                         spread_book=row["book"], spread_odds=row.get(f"{side}_spread_odds"), spread_edge=edge,
                         spread_p=p, spread_ev=value, spread_link=row.get(f"{side}_spread_link"), spread_verdict=v,
                         spread_units=units, spread_good_to=(thr - m) if side == "home" else (thr + m))
                r["spread_good_price"] = price_needed("spread", thr, r["spread_good_to"], True)
                r["spread_bandb"] = _band_b("spread", edge, value, v) and v != "REVIEW"
                v2, u2, b2, gated = gate("spread", side, row, edge, value, v, units, r["spread_bandb"], ls)
                if gated or (v2, u2, b2) != (v, units, r["spread_bandb"]):
                    r.update(spread_verdict=v2, spread_units=u2, spread_bandb=b2, spread_gate="opener rule")
                rg = ready_gate("spread", v2, u2, b2)
                if rg:
                    r.update(spread_verdict=rg[0], spread_units=rg[1], spread_bandb=rg[2], spread_gate="ratings update")
                hg = hold_gate(r["spread_verdict"], r["spread_bandb"])
                if hg:
                    r.update(spread_verdict=hg[0], spread_units=hg[1], spread_bandb=hg[2], spread_gate="input failure")
            to = _best(lt, "total", {"over": ("total", lambda x: t - x, "over_odds"),
                                     "under": ("total", lambda x: x - t, "under_odds")}, live, skip("total"))
            if to:
                side, row, edge, p, value = to
                v, units = _call(edge, value, TOTAL_CALLS)
                if edge > MAX_EDGE["total"]:
                    BAD.append({"date": str(g.get("date", ""))[:10], "game_id": g["game_id"], "market": "total", "side": side,
                                "book": row.get("book"), "number": row["total"], "price": row.get(f"{side}_odds"),
                                "median_others": np.nan, "books": np.nan, "reason": f"review: edge {edge:.1f}"})
                    v, units = "REVIEW", 0.0
                thr = TOTAL_CALLS[0][0]
                r.update(total_pick=side.title(), total_line=row["total"], total_book=row["book"],
                         total_odds=row.get(f"{side}_odds"), total_edge=edge, total_p=p, total_ev=value,
                         total_link=row.get(f"{side}_link"), total_verdict=v, total_units=units,
                         total_good_to=(t - thr) if side == "over" else (t + thr))
                r["total_good_price"] = price_needed("total", thr, r["total_good_to"], side == "under")
                r["total_bandb"] = _band_b("total", edge, value, v) and v != "REVIEW"
                v2, u2, b2, gated = gate("total", side, row, edge, value, v, units, r["total_bandb"], lt)
                if gated or (v2, u2, b2) != (v, units, r["total_bandb"]):
                    r.update(total_verdict=v2, total_units=u2, total_bandb=b2, total_gate="opener rule")
                rg = ready_gate("total", v2, u2, b2)
                if rg:
                    r.update(total_verdict=rg[0], total_units=rg[1], total_bandb=rg[2], total_gate="ratings update")
                hg = hold_gate(r["total_verdict"], r["total_bandb"])
                if hg:
                    r.update(total_verdict=hg[0], total_units=hg[1], total_bandb=hg[2], total_gate="input failure")
        out.append(r)
    return pd.DataFrame(out)


def log_linemove(gated: list[dict]) -> None:
    """Append each signal the opener rule stopped to research/linemove/signals.csv the first time it is seen (one row
    per game, market, side and bet type: the number and price it would have been bet at). Never stops the card."""
    try:
        if not gated:
            return
        new = pd.DataFrame(gated).reindex(columns=LINEMOVE_COLS)
        # a game and market the log already holds (any bet not void) could not have been logged anyway: the rule
        # stopped nothing there, so it is not a research signal
        b = tracker.load("all")
        held = set(zip(b.loc[b["status"] != "void", "game_id"].astype(str), b.loc[b["status"] != "void", "market"]))
        new = new[[(str(g), m) not in held for g, m in zip(new["game_id"], new["market"])]]
        key = ["date", "game_id", "market", "side", "bet_type"]
        if os.path.exists(LINEMOVE_SIGNALS):
            old = pd.read_csv(LINEMOVE_SIGNALS, dtype=str)
            seen = set(map(tuple, old[key].astype(str).to_numpy()))
            new = new[[tuple(map(str, r)) not in seen for r in new[key].astype(str).to_numpy()]]
        new = new.drop_duplicates(key)
        if len(new):
            os.makedirs(os.path.dirname(LINEMOVE_SIGNALS), exist_ok=True)
            new.to_csv(LINEMOVE_SIGNALS, mode="a", header=not os.path.exists(LINEMOVE_SIGNALS), index=False)
            for _, r in new.iterrows():
                print(f"Opener rule: {r['pick']} ({r['bet_type']}) not a play; opener {r['opener_line']} at "
                      f"{r['opener_book']}, edge there {r['edge_vs_opener']}")
    except Exception as e:
        print(f"Line-move research log failed ({e}); continuing.")


def log_bad_quotes(bad: list[dict]) -> None:
    """Append each guard skip to lines/bad_quotes.csv the first time it is seen (for the Nov 16 execution read:
    how often each guard fires, and at which book). Never stops the card."""
    try:
        if not bad:
            return
        new = pd.DataFrame(bad).assign(first_seen=pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"))
        key = ["date", "game_id", "market", "side", "book", "number", "reason"]
        if os.path.exists(BAD_QUOTES):
            old = pd.read_csv(BAD_QUOTES, dtype=str)
            seen = set(map(tuple, old[key].astype(str).to_numpy()))
            new = new[[tuple(map(str, r)) not in seen for r in new[key].astype(str).to_numpy()]]
        if len(new):
            new.reindex(columns=BAD_COLS).to_csv(BAD_QUOTES, mode="a", header=not os.path.exists(BAD_QUOTES), index=False)
            for _, r in new.iterrows():
                print(f"Bad quote skipped: {r['book']} {r['market']} {r['side']} {r['number']} ({r['reason']}) game {r['game_id']}")
    except Exception as e:
        print(f"Bad-quote log failed ({e}); continuing.")


def replay_lines(day: pd.Timestamp, f: pd.DataFrame) -> pd.DataFrame:
    """ESPN's stored lines for a past day, shaped like odds.pull() (no prices or links), to preview the page."""
    from . import lines_hist
    path = os.path.join(lines_hist.OUT, f"espn_{season_of(day)}.csv")
    l = pd.read_csv(path)
    l = l[l["game_id"].isin(f["game_id"]) & ~l["book"].fillna("").isin(lines_hist.NOT_BOOKS | {"", "Opening"})].copy()
    # ESPN's names for our books ("Caesars Sportsbook", "DraftKings Sportsbook (NJ)") -> the card's
    for ours in ("FanDuel", "DraftKings", "BetMGM", "Caesars"):
        l.loc[l["book"].str.startswith(ours), "book"] = ours
    l = l[l["book"].isin(odds.BOOKS.values())].drop_duplicates(["game_id", "book"])
    return l.merge(f[["game_id", "home_id", "away_id"]], on="game_id")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (default: today, US Eastern)")
    ap.add_argument("--replay", action="store_true", help="past day with ESPN's stored lines instead of live ones")
    ap.add_argument("--auto", action="store_true", help="after 8pm ET, build tomorrow's card (openers post overnight); "
                    "on a day without games, the next day that has them")
    a = ap.parse_args()
    quotelog.RUN_STARTED = quotelog.now()   # forward-test log: when this run's predictions were generated
    day = pd.Timestamp(a.date) if a.date else today_et()
    if a.auto and not a.date and pd.Timestamp.now(tz="America/New_York").hour >= 20:
        day += pd.Timedelta(days=1)
    if not (os.environ.get("KENPOM_API_KEY") or os.path.isdir(kenpom.CACHE)):
        raise SystemExit("KENPOM_API_KEY is not set (add it as a repository secret for the scheduled runs).")
    if not a.replay:   # every run, games or not: which outlet reports each injury first (injury_sources.py)
        try:
            injury_watch.check()
        except Exception as e:
            print(f"Injury source logger failed ({e}); continuing.")
    games = slate(day)
    if a.auto and not a.date:   # off day (or preseason): show the next day with games, up to two weeks out
        for _ in range(14):
            if len(games):
                break
            day += pd.Timedelta(days=1)
            games = slate(day)
    if not len(games):
        print(f"No games on {day:%Y-%m-%d}.")
        return
    if a.replay:
        build(day, games, None, replay=True)
        return
    try:
        lines = odds.pull()
    except Exception as e:   # no key or SportsGameOdds down: still publish the model's numbers
        print(f"Live lines unavailable ({e}); card has model numbers only.")
        lines = pd.DataFrame(columns=["book", "start", "home_id", "away_id", "home_spread", "total"])
    # grade earlier days first, so every card built below shows the current record
    try:
        tracker.settle()
    except Exception as e:
        print(f"Settling bets failed ({e}); continuing.")
    try:
        n = tracker.alert_voided()
        if n:
            print(f"Sent {n} cancellation alert(s).")
    except Exception as e:
        print(f"Cancellation alerts failed ({e}); continuing.")
    try:   # results, voids and announcements, even on runs that log no new bet
        public_record.sync()
    except Exception as e:
        print(f"Discord record failed ({e}); continuing.")
    build(day, games, lines)
    if a.auto and not a.date:
        # the whole coming week gets its own card every run, lines or not (Chad, Oct 31: "build out the week so we are
        # ready when lines drop"): the model's numbers are up before books post, and a day's first lines are priced
        # (and any play logged) on the first run that sees them
        for k in range(1, 8):
            d = day + pd.Timedelta(days=k)
            try:
                later = slate(d)
            except Exception as e:
                print(f"Schedule for {d:%Y-%m-%d} unavailable ({e}); skipped this run.")
                continue
            if len(later):
                build(d, later, lines, current=False)
    try:   # the public record page (record.html on the site)
        record_page.write()
    except Exception as e:
        print(f"Record page failed ({e}); continuing.")


def attach_logged(card: pd.DataFrame, day: pd.Timestamp) -> pd.DataFrame:
    """Add the day's logged bets (not void) to the card as {market}_logged_* columns, so a bet stays on the Plays list
    after the line or the model moves and the game is no longer a play at the current number."""
    b = tracker.load("v1_logged")   # pre-rule line-move plays included: the card shows them in their own block
    b = b[(b["date"] == f"{day:%Y-%m-%d}") & (b["status"] != "void")]
    card = card.copy()
    gid = card["game_id"].astype(str)
    for mk in ("spread", "total"):
        m = b[b["market"] == mk].drop_duplicates("game_id", keep="last")
        m = m.set_index(m["game_id"].astype(str))
        for c in ("pick", "side", "line", "book", "odds", "edge", "stake", "placed"):
            card[f"{mk}_logged_{c}"] = gid.map(m[c]) if len(m) else np.nan
        # the bet as the model sees it now: edge, win chance and EV at the logged number and price
        now = []
        for _, g in card.iterrows():
            side, line = str(g[f"{mk}_logged_side"]).lower(), g[f"{mk}_logged_line"]
            if pd.isna(line):
                now.append((np.nan, np.nan, np.nan))
                continue
            m_, t = g["model_margin"], g["model_total"]
            e = (m_ + line if side == "home" else line - m_) if mk == "spread" else (t - line if side == "over" else line - t)
            slope, cap = WIN_PROB[mk]
            p = float(min(max(0.5 + slope * e, 1 - cap), cap))
            now.append((e, p, ev(p, g[f"{mk}_logged_odds"])))
        card[[f"{mk}_now_edge", f"{mk}_now_p", f"{mk}_now_ev"]] = pd.DataFrame(now, index=card.index)
    return card


def alert_input_hold(day: pd.Timestamp, card: pd.DataFrame) -> bool:
    """One phone alert per held card day (INPUT_HOLD): what failed and which qualifying plays are held."""
    key = f"{day:%Y-%m-%d}"
    try:
        done = json.load(open(HOLD_ALERTED)) if os.path.exists(HOLD_ALERTED) else {}
        if key in done:
            return False
        held = [str(card.at[i, f"{mk}_pick"]) + " " + (f"{card.at[i, mk + '_line']:+g}" if mk == "spread" else f"{card.at[i, mk + '_line']:g}")
                for mk in ("spread", "total") if f"{mk}_gate" in card
                for i in card.index[card[f"{mk}_gate"] == "input failure"]]
        body = (f"{INPUT_HOLD[key]}. Plays for {key} are held: not logged, alerted or posted until the data loads. "
                + (f"Held: {', '.join(held)}." if held else "No play qualifies right now.") + " Don't bet the card for this day yet.")
        if notify.message(f"CBB: plays held for {key} (input failure)", body):
            done[key] = INPUT_HOLD[key]
            json.dump(done, open(HOLD_ALERTED, "w"))
            return True
    except Exception as e:
        print(f"Input-hold alert failed ({e}); continuing.")
    return False


def attach_band_b(card: pd.DataFrame, day: pd.Timestamp) -> pd.DataFrame:
    """The day's logged band B plays (not void) as {market}_bandb_* columns, for the card's band B block."""
    b = tracker.load("bandB_logged")
    b = b[(b["date"] == f"{day:%Y-%m-%d}") & (b["status"] != "void")]
    card = card.copy()
    gid = card["game_id"].astype(str)
    for mk in ("spread", "total"):
        m = b[b["market"] == mk].drop_duplicates("game_id", keep="last")
        m = m.set_index(m["game_id"].astype(str))
        for c in ("bet_id", "pick", "line", "book", "odds", "edge", "stake", "placed", "status", "result", "profit"):
            card[f"{mk}_bandb_{c}"] = gid.map(m[c]) if len(m) else np.nan
    return card


def build(day: pd.Timestamp, games: pd.DataFrame, lines: pd.DataFrame | None, replay: bool = False,
          current: bool = True):
    """Project one day's games, price them against the lines, log BETs and write the day's card. current=False adds
    the day to the site's day list without making it the day the site opens on."""
    from . import freshness   # input freshness stamp: pass-through wrappers that record each input's date
    if not replay:
        freshness.watch()
    f, rt = project(day, games)
    f = opening_week_totals(f, day)
    if replay:
        lines = replay_lines(day, f)
    card = plays(f, lines, live=not replay)
    if not replay and INPUT_HOLD.get(f"{day:%Y-%m-%d}"):
        alert_input_hold(day, card)
    if not replay:
        log_bad_quotes(BAD)
        log_linemove(GATED)
        try:
            card = news.annotate(card)
        except Exception as e:
            print(f"News checks failed ({e}); continuing.")
    record = None
    fr = None
    if not replay:   # freshness stamp (display only; never changes a pick or a number)
        try:
            fr = freshness.stamp(card, day, lines)
            freshness.alert_stale()
        except Exception as e:
            print(f"Freshness stamp failed ({e}); continuing.")
    if not replay:
        # scale stakes by each market's live record, then log the day's plays
        st = tracker.status()
        for mk in ("spread", "total"):
            if f"{mk}_units" in card:
                card[f"{mk}_units"] = card[f"{mk}_units"] * st[mk]["multiplier"]
        new = tracker.log(card, day, {mk: st[mk]["multiplier"] for mk in st})
        freshness.log_inputs(new, fr)
        if notify.send(new, card):
            print(f"Sent {len(new)} phone alert(s).")
        try:   # same run as the phone alert, so the public post carries the same time
            public_record.sync()
        except Exception as e:
            print(f"Discord record failed ({e}); continuing.")
        if new:   # alternate-line ladder, logged for research only (cbb/ladder.py; never shown, never changes a play)
            from . import ladder
            ladder.pull_for(new, lines)
        if new:   # forward-test log: what each new signal was built on (additive; never changes a play)
            try:
                hist = data.season_games(season_of(day))[0] if day <= today_et() + pd.Timedelta(days=14) else None
            except Exception:
                hist = None
            quotelog.signals(new, card, day, quotelog.inputs(day, hist), getattr(odds.pull, "pulled_at", None),
                             getattr(odds.pull, "observations", None))
        # band B (tracker.BAND_B): its own log rows, 0.5 u flat; after v1's, so it never changes a v1 bet, stake,
        # alert or post. No phone alert and no Discord post (Chad, Nov 2: "only main plays in the notifications")
        try:
            new_b = tracker.log_band_b(card, day)
            freshness.log_inputs(new_b, fr)
            if new_b:
                print(f"Logged {len(new_b)} band B play(s) (record page only; no alert or post).")
                from . import ladder
                ladder.pull_for(new_b, lines)
                try:
                    hb = data.season_games(season_of(day))[0] if day <= today_et() + pd.Timedelta(days=14) else None
                except Exception:
                    hb = None
                quotelog.signals(new_b, card, day, quotelog.inputs(day, hb), getattr(odds.pull, "pulled_at", None),
                                 getattr(odds.pull, "observations", None))
        except Exception as e:
            print(f"Band B failed ({e}); continuing.")
        card = attach_logged(card, day)
        card = attach_band_b(card, day)
        try:
            rv = review.summary()
        except Exception as e:
            print(f"Loss review failed ({e}); continuing.")
            rv = {}
        try:
            trip = tracker.check_tripwires()
        except Exception as e:
            print(f"Tripwire check failed ({e}); continuing.")
            trip = None
        record = {"status": tracker.status(), "recent": tracker.recent(), "review": rv, "tripwire": trip}
    os.makedirs(REPORTS, exist_ok=True)
    stem = os.path.join(REPORTS, f"cbb_{day:%Y-%m-%d}")
    if fr is not None:   # the stamp as trailing columns; every earlier column unchanged
        card = freshness.trail(card, fr)
    card.drop(columns=["book_lines"]).to_csv(stem + ".csv", index=False)
    names = teams.load().set_index("espn_id")["espn_location"]
    rt = rt.assign(team=names.reindex(rt.index).to_numpy())
    with open(stem + ".html", "w") as fh:
        fh.write(report_html.build(card, rt, day, season_of(day), replay=replay, record=record))
    days_path = os.path.join(REPORTS, "days.json")
    days = json.load(open(days_path)) if os.path.exists(days_path) else {"days": []}
    days["days"] = sorted(set(days["days"]) | {f"{day:%Y-%m-%d}"})
    if current or "current" not in days:
        days["current"] = f"{day:%Y-%m-%d}"
    with open(days_path, "w") as fh:
        json.dump(days, fh)
    n = lambda col, v: int((card.get(col) == v).sum()) if col in card else 0
    print(f"{day:%Y-%m-%d}: {len(card)} games, {int((card['n_books'] > 0).sum())} with lines; "
          f"{n('spread_verdict', 'BET')} spread and {n('total_verdict', 'BET')} total plays -> {stem}.html")


if __name__ == "__main__":
    main()
