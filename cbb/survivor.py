"""Survivor pool planner (Chad's CBB survivor pool): the Survivor tab, record/survivor.html.

Contest (rules from Chad, Oct 27): pick one Division I team to win outright each contest day (ET) for each surviving
entry; each team once per entry; a loss or a missed day ends that entry; up to 5 entries, picks independent per entry;
opening day Mon Nov 2, 2026 is required.

How the plan is made, per entry:
- Win chance: the card's full-model p_home_win for days that have a card; later games from the model's current team
  ratings (net per 100 possessions x tempo, plus home court), the same normal curve as the card (SD 11 points).
- Each remaining day gets one team the entry has not used, maximizing the product of win chances over the season
  (scipy's assignment solver on -log p). That spends teams whose only safe spots are now, and saves the teams that are
  still big favorites in January and February: the survivor "future value".
- Entries are solved in order and steered to different games on the same day, so one upset cannot end them all.

Picks are recorded with the page's Pick button (.github/workflows/survivor.yml), which refuses a team the entry has
already used, a second pick for the same entry and day, and a game that has tipped. Display and planning only: nothing
here touches the betting model, the card's picks, the bet log or the record.

    python -m cbb.survivor                                   # refresh schedule and results, plan, write the page
    python -m cbb.survivor --pick 1 2026-11-02 2633           # record entry 1's pick (ESPN team id) for a day
    python -m cbb.survivor --unpick 1 2026-11-02              # remove a pick before its game tips
"""
from __future__ import annotations

import argparse
import html
import json
import math
import os
import time
import urllib.request

import numpy as np
import pandas as pd

from . import report_html

ROOT = os.path.join(os.path.dirname(__file__), "..")
DIR = os.path.join(ROOT, "data", "survivor")
SCHED = os.path.join(DIR, "schedule.csv")
PICKS = os.path.join(DIR, "picks.csv")
OUT = os.path.join(ROOT, "site", "record", "survivor.html")
START = pd.Timestamp("2026-11-02")
END = pd.Timestamp("2027-04-06")
ENTRIES = 5
SD = 11.0                  # the card's win-chance curve (run_day: p = Phi(margin / 11))
HCA = 3.0                  # points of home court for projected games
SPREAD_PENALTY = 0.01      # log-points: steers entries off a game another entry already uses that day
P_CAP = 0.997              # no game is treated as more certain than this
URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates={}&groups=50&limit=500"
PICK_COLS = ["entry", "date", "team_id", "team", "game_id", "opponent", "recorded_at", "result"]


def now_et() -> pd.Timestamp:
    return pd.Timestamp.now(tz="America/New_York")


# ---------------------------------------------------------------------------------------------------------------
# schedule and results (ESPN's public scoreboard, every D-I game)
# ---------------------------------------------------------------------------------------------------------------
def _day(d: pd.Timestamp) -> list[dict]:
    for i in range(4):
        try:
            req = urllib.request.Request(URL.format(f"{d:%Y%m%d}"), headers={"User-Agent": "cbb-survivor"})
            with urllib.request.urlopen(req, timeout=40) as r:
                ev = json.load(r).get("events") or []
            break
        except Exception:
            time.sleep(2 ** (i + 1))
    else:
        raise RuntimeError(f"ESPN scoreboard unavailable for {d:%Y-%m-%d}")
    rows = []
    for e in ev:
        c = e["competitions"][0]
        side = {t.get("homeAway"): t for t in c.get("competitors", [])}
        h, a = side.get("home"), side.get("away")
        if not h or not a:
            continue
        st = (e.get("status") or {}).get("type") or {}
        win = next((int(t["team"]["id"]) for t in (h, a) if t.get("winner")), None)
        rows.append({"game_id": int(e["id"]), "start": e.get("date"), "home_id": int(h["team"]["id"]), "away_id": int(a["team"]["id"]),
                     "home": h["team"].get("location") or h["team"].get("displayName"), "away": a["team"].get("location") or a["team"].get("displayName"),
                     "neutral": bool(c.get("neutralSite")), "state": st.get("state"), "completed": bool(st.get("completed")),
                     "winner_id": win, "canceled": st.get("name") in ("STATUS_CANCELED", "STATUS_POSTPONED")})
    return rows


def refresh_schedule(days_back: int = 2) -> pd.DataFrame:
    """Re-fetch from a couple of days back to the end of the season (times, results and new games change); keep
    older days as stored."""
    old = pd.read_csv(SCHED) if os.path.exists(SCHED) else pd.DataFrame()
    first = max(START, now_et().tz_localize(None).normalize() - pd.Timedelta(days=days_back))
    rows = []
    for d in pd.date_range(first, END):
        rows += _day(d)
    new = pd.DataFrame(rows)
    if len(new):
        new["date"] = pd.to_datetime(new["start"], utc=True).dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
    keep = old[pd.to_datetime(old["date"]) < first] if len(old) else old
    s = pd.concat([keep, new], ignore_index=True).drop_duplicates("game_id", keep="last").sort_values(["date", "start"])
    os.makedirs(DIR, exist_ok=True)
    s.to_csv(SCHED, index=False)
    return s


# ---------------------------------------------------------------------------------------------------------------
# win chances
# ---------------------------------------------------------------------------------------------------------------
def _phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def ratings() -> pd.DataFrame:
    """The model's current team ratings (latest card), indexed by ESPN id."""
    from . import teams
    cur = json.load(open(os.path.join(ROOT, "reports", "days.json")))["current"]
    import re
    s = open(os.path.join(ROOT, "reports", f"cbb_{cur}.html")).read()
    d = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', s, re.S).group(1))
    r = pd.DataFrame(d["ratings"])
    ids = teams.load().drop_duplicates("espn_location").set_index("espn_location")["espn_id"]
    r["espn_id"] = r["team"].map(ids)
    return r.dropna(subset=["espn_id"]).assign(espn_id=lambda x: x["espn_id"].astype(int)).set_index("espn_id")


def card_probs() -> dict:
    """game_id -> the card's full-model home win chance, for every day that has a card."""
    out = {}
    for f in sorted(os.listdir(os.path.join(ROOT, "reports"))):
        if f.startswith("cbb_") and f.endswith(".csv"):
            try:
                c = pd.read_csv(os.path.join(ROOT, "reports", f), usecols=["game_id", "p_home_win"]).dropna()
                out.update(dict(zip(c["game_id"].astype(int), c["p_home_win"].astype(float))))
            except (ValueError, KeyError):
                continue
    return out


def win_probs(s: pd.DataFrame) -> pd.DataFrame:
    """Per game: p_home (card if it has the game, else ratings), and how it was made."""
    r, cp = ratings(), card_probs()
    tempo = float(r["adj_tempo"].mean())
    nh, na = s["home_id"].map(r["net"]), s["away_id"].map(r["net"])
    m = (nh - na) * tempo / 100 + np.where(s["neutral"].astype(bool), 0.0, HCA)
    p = m.map(lambda x: _phi(x / SD) if pd.notna(x) else np.nan)
    card = s["game_id"].map(cp)
    s = s.assign(p_home=card.fillna(p), p_src=np.where(card.notna(), "card", "ratings"))
    # rule 1: Division I vs Division I only (the model rates every D-I team); other games are never options
    s = s[nh.notna() & na.notna()].copy()
    # real upsets of 30-point favorites still happen about 0.3-0.5% of the time: cap the curve's tails
    s["p_home"] = s["p_home"].clip(1 - P_CAP, P_CAP)
    return s


# ---------------------------------------------------------------------------------------------------------------
# picks
# ---------------------------------------------------------------------------------------------------------------
def load_picks() -> pd.DataFrame:
    return pd.read_csv(PICKS) if os.path.exists(PICKS) else pd.DataFrame(columns=PICK_COLS)


def grade(p: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    g = s.set_index("game_id")
    for i, r in p.iterrows():
        if pd.notna(r["result"]) and r["result"] in ("W", "L"):
            continue
        x = g.loc[int(r["game_id"])] if int(r["game_id"]) in g.index else None
        if x is None:
            continue
        if bool(x["canceled"]):
            p.at[i, "result"] = "void"
        elif bool(x["completed"]) and pd.notna(x["winner_id"]):
            p.at[i, "result"] = "W" if int(x["winner_id"]) == int(r["team_id"]) else "L"
    return p


def status(entry: int, p: pd.DataFrame, s: pd.DataFrame, today: pd.Timestamp) -> tuple[str, str]:
    """('alive' | 'out', why). A loss or a missed contest day (games played, no valid pick) ends an entry."""
    e = p[p["entry"] == entry]
    lost = e[e["result"] == "L"]
    if len(lost):
        r = lost.iloc[0]
        return "out", f"{r['team']} lost on {r['date']}"
    days = sorted(d for d in s["date"].unique() if START <= pd.Timestamp(d) < today)
    valid = set(e.loc[e["result"] != "void", "date"])
    missed = [d for d in days if d not in valid]
    if missed:
        return "out", f"no pick on {missed[0]}"
    return "alive", ""


def record_pick(entry: int, date: str, team_id: int) -> str:
    s = pd.read_csv(SCHED)
    p = load_picks()
    e = p[(p["entry"] == entry) & (p["result"] != "void")]
    if not 1 <= entry <= ENTRIES:
        raise SystemExit(f"entry must be 1-{ENTRIES}")
    if (e["team_id"] == team_id).any():
        raise SystemExit(f"entry {entry} already used team {team_id} ({e.loc[e['team_id'] == team_id, 'date'].iloc[0]}): each team once per entry")
    if (e["date"] == date).any():
        raise SystemExit(f"entry {entry} already has a pick on {date}")
    g = s[(s["date"] == date) & ((s["home_id"] == team_id) | (s["away_id"] == team_id))]
    if not len(g):
        raise SystemExit(f"team {team_id} has no game on {date}")
    g = g.iloc[0]
    if pd.Timestamp(g["start"]) <= pd.Timestamp.now(tz="UTC"):
        raise SystemExit("that game has tipped: picks lock at tipoff")
    home = int(g["home_id"]) == team_id
    row = {"entry": entry, "date": date, "team_id": team_id, "team": g["home"] if home else g["away"], "game_id": int(g["game_id"]),
           "opponent": g["away"] if home else g["home"], "recorded_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"), "result": ""}
    pd.concat([p, pd.DataFrame([row])], ignore_index=True)[PICK_COLS].to_csv(PICKS, index=False)
    return f"entry {entry}: {row['team']} over {row['opponent']} on {date}"


def unpick(entry: int, date: str) -> str:
    s = pd.read_csv(SCHED).set_index("game_id")
    p = load_picks()
    m = (p["entry"] == entry) & (p["date"] == date)
    if not m.any():
        raise SystemExit("no such pick")
    gid = int(p.loc[m, "game_id"].iloc[0])
    if gid in s.index and pd.Timestamp(s.loc[gid, "start"]) <= pd.Timestamp.now(tz="UTC"):
        raise SystemExit("that game has tipped: the pick is locked")
    p[~m].to_csv(PICKS, index=False)
    return f"entry {entry}: pick for {date} removed"


# ---------------------------------------------------------------------------------------------------------------
# the plan
# ---------------------------------------------------------------------------------------------------------------
def options(s: pd.DataFrame) -> pd.DataFrame:
    """One row per (date, team): the team's game that day and its win chance."""
    neu = s["neutral"].astype(bool)
    h = s.assign(team_id=s["home_id"], team=s["home"], opp=s["away"], opp_id=s["away_id"], p=s["p_home"], where=np.where(neu, "neutral", "home"))
    a = s.assign(team_id=s["away_id"], team=s["away"], opp=s["home"], opp_id=s["home_id"], p=1 - s["p_home"], where=np.where(neu, "neutral", "away"))
    o = pd.concat([h, a], ignore_index=True)
    return o[["date", "start", "game_id", "team_id", "team", "opp", "opp_id", "where", "p", "p_src"]]


def plan_entry(o: pd.DataFrame, used: set, days: list[str], taken_today: dict) -> dict:
    """date -> option row: one unused team per day, maximizing the sum of log win chances (scipy assignment)."""
    from scipy.optimize import linear_sum_assignment
    o = o[o["date"].isin(days) & ~o["team_id"].isin(used) & o["p"].notna()]
    if not len(o):
        return {}
    o = o.sort_values("p", ascending=False).drop_duplicates(["date", "team_id"])
    dl, tl = sorted(o["date"].unique()), sorted(o["team_id"].unique())
    di, ti = {d: i for i, d in enumerate(dl)}, {t: j for j, t in enumerate(tl)}
    big = 50.0
    C = np.full((len(dl), len(tl)), big)
    cost = -np.log(np.clip(o["p"].to_numpy(float), 1e-6, 1.0))
    pen = np.array([SPREAD_PENALTY * taken_today.get((d, g), 0) for d, g in zip(o["date"], o["game_id"])])
    C[o["date"].map(di).to_numpy(), o["team_id"].map(ti).to_numpy()] = cost + pen
    rows, cols = linear_sum_assignment(C)
    pick = {}
    idx = o.set_index(["date", "team_id"], drop=False)
    for r_, c_ in zip(rows, cols):
        if C[r_, c_] < big:
            pick[dl[r_]] = idx.loc[(dl[r_], tl[c_])]
    return pick


def build(refresh: bool = True) -> str:
    s = refresh_schedule() if refresh or not os.path.exists(SCHED) else pd.read_csv(SCHED)
    s = win_probs(s[~s["canceled"].astype(bool)])
    p = grade(load_picks(), pd.read_csv(SCHED))
    p.to_csv(PICKS, index=False)
    now = now_et()
    today = now.tz_localize(None).normalize()
    o = options(s)
    o = o[pd.to_datetime(o["start"], utc=True) > pd.Timestamp.now(tz="UTC")]       # not tipped yet
    first = max(START, today)
    days_all = sorted(d for d in o["date"].unique() if pd.Timestamp(d) >= first)
    taken: dict = {}
    entries = []
    for e in range(1, ENTRIES + 1):
        st, why = status(e, p, s.assign(date=s["date"]), today)
        mine = p[(p["entry"] == e) & (p["result"] != "void")]
        used = set(mine["team_id"].astype(int))
        days = [d for d in days_all if d not in set(mine["date"])]
        plan = plan_entry(o, used, days, taken) if st == "alive" else {}
        nxt = next(iter(sorted(plan)), None)
        for dd, g in plan.items():                      # later entries are steered off these games on every day
            taken[(dd, g["game_id"])] = taken.get((dd, g["game_id"]), 0) + 1
        entries.append({"entry": e, "status": st, "why": why, "picks": mine.sort_values("date"), "plan": plan, "next": nxt})
    with open(OUT, "w") as fh:
        fh.write(page(entries, o, p))
    return OUT


# ---------------------------------------------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------------------------------------------
def _logo(tid, px=18) -> str:
    return (f"<img class='lg' src='https://a.espncdn.com/i/teamlogos/ncaa/500/{int(tid)}.png' alt='' width='{px}' height='{px}' "
            f"loading='lazy' onerror=\"this.remove()\">")


def _pct(x) -> str:
    return "–" if pd.isna(x) else f"{100 * x:.1f}%"


def _when(start) -> str:
    t = pd.Timestamp(start).tz_convert("America/New_York")
    return f"{t:%a %b} {t.day} · {t:%-I:%M %p}"


def by_date(p: pd.DataFrame) -> str:
    """Every recorded pick, one row per contest day, one column per entry, newest day first."""
    if not len(p):
        return "<div class='empty'>No picks recorded yet.</div>"
    res = {"W": " <span class='pos b'>W</span>", "L": " <span class='neg b'>L</span>", "void": " <span class='f'>void</span>"}
    head = "<thead><tr><th>Date</th>" + "".join(f"<th>Entry {e}</th>" for e in range(1, ENTRIES + 1)) + "</tr></thead>"
    rows = []
    for d in sorted(p["date"].unique(), reverse=True):
        x = p[p["date"] == d].set_index("entry")
        cells = "".join(
            (f"<td>{_logo(x.loc[e, 'team_id'], 16)}<b>{html.escape(str(x.loc[e, 'team']))}</b>{res.get(str(x.loc[e, 'result']), '')}"
             f"<div class='f' style='font-size:11px'>vs {html.escape(str(x.loc[e, 'opponent']))}</div></td>") if e in x.index else "<td class='f'>–</td>"
            for e in range(1, ENTRIES + 1))
        rows.append(f"<tr><td class='b'>{pd.Timestamp(d):%a %b} {pd.Timestamp(d).day}</td>{cells}</tr>")
    return f"<div class='scroll'><table>{head}<tbody>{''.join(rows)}</tbody></table></div>"


def page(entries: list[dict], o: pd.DataFrame, p: pd.DataFrame) -> str:
    R = report_html
    style = R.TEMPLATE[R.TEMPLATE.index("<style>"):R.TEMPLATE.index("</style>") + 8]
    now = now_et()
    blocks, payload = [], {}
    for e in entries:
        n = e["entry"]
        used = e["picks"]
        hist = "".join(
            f"<tr><td class='m'>{html.escape(str(r['date']))}</td><td>{_logo(r['team_id'], 16)}<b>{html.escape(str(r['team']))}</b> "
            f"<span class='f'>vs {html.escape(str(r['opponent']))}</span></td><td class='r'>"
            f"{ {'W': '<span class=pos>Won</span>', 'L': '<span class=neg>Lost</span>', 'void': 'Void'}.get(str(r['result']), 'Pending')}</td></tr>"
            for _, r in used.iterrows()) or "<tr><td class='empty'>No picks yet.</td></tr>"
        head = (f"<span class='chip'>Alive</span>" if e["status"] == "alive" else f"<span class='chip zero'>Out: {html.escape(e['why'])}</span>")
        if e["status"] != "alive" or e["next"] is None:
            body = "<div class='empty'>Nothing to pick.</div>" if e["status"] == "alive" else ""
        else:
            d = e["next"]
            g = e["plan"][d]
            usedset = set(used["team_id"].astype(int))
            alts = o[(o["date"] == d) & ~o["team_id"].isin(usedset)].sort_values("p", ascending=False)
            alts = pd.concat([alts[alts["team_id"] == int(g["team_id"])], alts[alts["team_id"] != int(g["team_id"])]]).head(12)  # the plan's team first
            later = {t: max((x["p"] for dd, x in e["plan"].items() if dd != d and int(x["team_id"]) == int(t)), default=None) for t in alts["team_id"]}
            rows = "".join(
                f"<tr{' class=rec' if int(r['team_id']) == int(g['team_id']) else ''}><td>{_logo(r['team_id'])}<b>{html.escape(str(r['team']))}</b> "
                f"<span class='f'>{'vs' if r['where'] != 'away' else '@'} {html.escape(str(r['opp']))}</span>"
                f"{' <span class=tag>Plan</span>' if int(r['team_id']) == int(g['team_id']) else ''}</td>"
                f"<td class='m'>{_when(r['start'])}</td><td class='r b'>{_pct(r['p'])}</td>"
                f"<td class='r m hide-sm'>{'saved for ' + _pct(later[r['team_id']]) if later.get(r['team_id']) is not None else '–'}</td>"
                f"<td class='r'><button type='button' class='pk' data-e='{n}' data-d='{d}' data-t='{int(r['team_id'])}' "
                f"data-n='{html.escape(str(r['team']))}'>Pick</button></td></tr>"
                for _, r in alts.iterrows())
            ahead = " · ".join(f"{pd.Timestamp(dd):%b} {pd.Timestamp(dd).day}: {html.escape(str(x['team']))} {_pct(x['p'])}"
                               for dd, x in list(sorted(e['plan'].items()))[1:8])
            body = (f"<div class='nx'><div class='k'>PICK FOR {pd.Timestamp(d):%a %b} {pd.Timestamp(d).day}</div>"
                    f"<div class='big'>{_logo(g['team_id'], 26)}{html.escape(str(g['team']))} "
                    f"<span class='m' style='font-size:15px;font-weight:500'>{'vs' if g['where'] != 'away' else '@'} {html.escape(str(g['opp']))} · "
                    f"{_when(g['start'])}</span></div><div class='m'>Model win chance <b>{_pct(g['p'])}</b> · "
                    f"{'full model (card)' if g['p_src'] == 'card' else 'from current ratings'}</div>"
                    f"<button type='button' class='pk pk-main' data-e='{n}' data-d='{d}' data-t='{int(g['team_id'])}' "
                    f"data-n='{html.escape(str(g['team']))}'>Pick {html.escape(str(g['team']))} for entry {n}</button></div>"
                    f"<div class='scroll'><table class='opts'><thead><tr><th>Options {pd.Timestamp(d):%b} {pd.Timestamp(d).day} (unused teams)</th><th>Tip (ET)</th>"
                    f"<th class='r'>Win %</th><th class='r hide-sm'>Plan uses it later at</th><th></th></tr></thead><tbody>{rows}</tbody></table></div>"
                    f"<div class='f' style='padding:8px 16px 12px;font-size:12px'>Next in the plan: {ahead or '–'}</div>")
        pend = used[~used["result"].isin(["W", "L", "void"])]
        locked = "".join(f"<div class='lk'>&#10003; Picked {pd.Timestamp(r['date']):%a %b} {pd.Timestamp(r['date']).day}: {_logo(r['team_id'], 18)}"
                         f"<b>{html.escape(str(r['team']))}</b> <span class='m'>vs {html.escape(str(r['opponent']))}</span></div>"
                         for _, r in pend.iterrows())
        blocks.append(f"<section class='panel'><div class='panel-h'><h2>Entry {n}</h2><div class='ctrls'>{head}"
                      f"<span class='chip zero'>{len(used)} team{'' if len(used) == 1 else 's'} used</span></div></div>{locked}{body}"
                      f"<details class='usedd'><summary>Picks so far ({len(used)})</summary><div class='scroll'><table><tbody>{hist}</tbody></table></div></details></section>")
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<base href="../">
<meta name="robots" content="noindex">
<title>Off The Glass · College Basketball Survivor</title>
{R.HEAD}
{style}
<style>
.chip {{ display: inline-flex; align-items: center; padding: 5px 12px; border-radius: 6px; font-size: 13px; font-weight: 700; background: var(--brand); color: #fff; white-space: nowrap }}
.chip.zero {{ background: var(--sunken); color: var(--muted); border: 1px solid var(--line-strong); font-weight: 600 }}
.nx {{ padding: 14px 16px; border-bottom: 1px solid var(--line) }}
.nx .k {{ font-size: 11px; font-weight: 700; letter-spacing: .06em; color: var(--muted) }}
.nx .big {{ font-size: 22px; font-weight: 800; margin: 4px 0 2px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap }}
.lg {{ vertical-align: -4px; margin-right: 6px; object-fit: contain }}
.opts tr.rec td {{ background: var(--sunken) }}
.pk {{ font-size: 12px; padding: 4px 12px }}
.lk {{ padding: 10px 16px; border-bottom: 1px solid var(--line); background: var(--pos-bg); color: var(--text); font-size: 14px }}
.pk-main {{ margin-top: 10px; font-size: 14px; padding: 8px 16px; background: var(--brand); color: #fff; border-color: var(--brand) }}
.pk-main:hover {{ background: var(--brand); opacity: .9 }}
details.usedd > summary {{ cursor: pointer; padding: 10px 16px; font-size: 13px; color: var(--muted); border-top: 1px solid var(--line) }}
</style>
<header class="top"><div class="wrap">
  {R.BRAND}
  <nav class="tabs" aria-label="Sport"><a href="{R.NFL_SITE}">NFL</a>{R.NBA_TAB}<a href="./" aria-current="page"><span class="hide-sm">College Basketball</span><span class="show-sm">CBB</span></a></nav>
</div></header>
<main class="wrap">
  <div class="head"><div><h1>Survivor</h1>
    <div class="sub">Five entries · one team to win each day · each team once per entry. Updated {now:%b} {now.day}, {now:%-I:%M %p} ET.</div></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap"><a class="pagebtn" href="./">&larr; Card</a><a class="pagebtn" href="record.html">Record</a><a class="pagebtn" href="record/charts.html">Charts</a></div></div>
  <section class="panel"><div class="panel-h"><h2>My picks by date</h2><span class="note">Every pick recorded, all five entries. W / L once the game is final.</span></div>
    {by_date(p)}</section>
  <section class="panel"><div class="panel-h"><h2>How the plan works</h2></div><div style="padding:12px 16px;font-size:13px;color:var(--muted);line-height:1.55">
    Each entry gets one unused team per day for the rest of the season, chosen so the product of win chances is as high as
    possible. That spends teams whose only safe games are November and December buy games and saves the teams that are
    still big favorites in conference play. Entries are steered to different games on the same day. Win chances are the
    card's full model when the day has a card, otherwise the model's current ratings. Teams an entry has used never appear
    for it again. Pick records the choice (it refuses a used team or a game that has tipped); the page updates within
    about 10 minutes. Picks lock at tipoff, and a missed day ends an entry: pick every day.</div></section>
  {''.join(blocks)}
  <footer><div><a class="follow" href="https://x.com/{R.X_HANDLE}" target="_blank" rel="noopener"><img src="assets/otg-logo-512.png" alt="">Follow @{R.X_HANDLE} on X</a></div></footer>
</main>
<script>
(() => {{
  const REPO = "{R.REPO}";
  const store = {{ get: () => {{ try {{ return localStorage.getItem("gh_token_cbb") || ""; }} catch (e) {{ return ""; }} }},
                  set: (v) => {{ try {{ v ? localStorage.setItem("gh_token_cbb", v) : localStorage.removeItem("gh_token_cbb"); }} catch (e) {{}} }} }};
  const askKey = () => {{ const t = prompt("Paste a GitHub fine-grained token for " + REPO + " with Actions: Read and write.\\nIt is saved only in this browser.", store.get());
    if (t !== null) store.set(t.trim()); return store.get(); }};
  document.querySelectorAll(".pk").forEach((b) => b.onclick = async () => {{
    if (!confirm("Entry " + b.dataset.e + ": pick " + b.dataset.n + " for " + b.dataset.d + "?\\nEach team can be used once per entry.")) return;
    if (!store.get() && !askKey()) return;
    b.disabled = true; b.textContent = "Saving…";
    const branch = "claude/college-basketball-model-nmztcl";
    const r = await fetch("https://api.github.com/repos/" + REPO + "/actions/workflows/survivor.yml/dispatches", {{ method: "POST",
      headers: {{ Accept: "application/vnd.github+json", Authorization: "Bearer " + store.get(), "X-GitHub-Api-Version": "2022-11-28" }},
      body: JSON.stringify({{ ref: branch, inputs: {{ action: "pick", entry: b.dataset.e, date: b.dataset.d, team_id: b.dataset.t }} }}) }}).catch(() => null);
    if (r && r.status === 204) {{
      b.textContent = "Saved ✓";
      try {{ const k = "surv_saved"; const m = JSON.parse(localStorage.getItem(k) || "{{}}"); m[b.dataset.e + "|" + b.dataset.d] = b.dataset.n; localStorage.setItem(k, JSON.stringify(m)); }} catch (e) {{}}
      alert("Entry " + b.dataset.e + ": " + b.dataset.n + " sent. It shows on this page in about 10 minutes.");
    }}
    else if (r && [401, 403, 404].includes(r.status)) {{ store.set(""); b.disabled = false; b.textContent = "Pick"; alert("GitHub refused the token (" + r.status + "). Press Pick again and paste a new token. Nothing was saved."); }}
    else {{ b.disabled = false; b.textContent = "Pick"; alert("Couldn't reach GitHub" + (r ? " (" + r.status + ")" : "") + ". Nothing was saved: press Pick again."); }}
  }});
  document.querySelectorAll("main table").forEach((t) => {{
    const hs = [...t.querySelectorAll("thead th")].map((h) => h.textContent.trim());
    t.classList.add("stack");
    t.querySelectorAll("tbody tr").forEach((r) => [...r.children].forEach((c, k) => {{ if (hs[k]) c.dataset.l = hs[k]; }}));
  }});
}})();
</script>
</html>
"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick", nargs=3, metavar=("ENTRY", "DATE", "TEAM_ID"))
    ap.add_argument("--unpick", nargs=2, metavar=("ENTRY", "DATE"))
    ap.add_argument("--no-refresh", action="store_true")
    a = ap.parse_args()
    if a.pick:
        if not os.path.exists(SCHED):
            refresh_schedule()
        print(record_pick(int(a.pick[0]), a.pick[1], int(a.pick[2])))
    if a.unpick:
        print(unpick(int(a.unpick[0]), a.unpick[1]))
    print(build(refresh=not a.no_refresh and not (a.pick or a.unpick)))
