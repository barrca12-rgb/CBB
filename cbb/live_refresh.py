"""Results-only refresh of the published site (Chad, Nov 2: "make the site refresh more without using more odds
credits"). Display only.

Runs after every 3-minute quote poll (.github/workflows/live_refresh.yml). It reads ESPN's free scoreboard, grades
finished plays with the card's own grader (tracker.settle) and rebuilds what those results touch:
- today's card: live and final scores with the game clock, game states and the record block (tiles, record table,
  recent results);
- the coming week's cards: the record block;
- the last few past days' cards (report_html.refresh_past);
- the record page, when a play was graded.

It never pulls odds (no Odds API, SportsGameOdds, KenPom or Barttorvik call), never runs the model, never changes a
pick, line or price, and never commits: the bet log, Discord results and phone alerts stay with the 10-minute card
run, which grades the same games itself and remains the record of truth. The workflow gets no Discord or phone
secret, so nothing here can post or alert.

    python -m cbb.live_refresh        # writes publish=true|false to $GITHUB_OUTPUT when set
"""
from __future__ import annotations

import json
import os
import re

import pandas as pd

from . import autorefresh, report_html, run_day, tracker

DATA = re.compile(r'<script id="data" type="application/json">(.*?)</script>', re.S)
TITLE = re.compile(r"<title>(.*?)</title>", re.S)


def record(prev: dict | None) -> dict | None:
    """The card's record block, rebuilt from the bet log the same way run_day.build does. Any part that cannot be
    rebuilt here keeps the card run's value, so a failure never blanks a section."""
    prev = prev or {}
    parts = {"status": tracker.status, "recent": tracker.recent, "tripwire": tracker.check_tripwires}
    rec = {}
    for k, fn in parts.items():
        try:
            rec[k] = fn()
        except Exception as e:
            print(f"Record {k} unavailable ({e}); kept the card run's.")
            if k not in prev:
                return None
            rec[k] = prev[k]
    try:
        from . import review
        rec["review"] = review.summary()
    except Exception as e:
        print(f"Loss review unavailable ({e}); kept the card run's.")
        rec["review"] = prev.get("review") or {}
    try:
        return report_html.record_block(rec)
    except Exception as e:
        print(f"Record block failed ({e}); kept the card run's.")
        return None


def _page(src: str, data: dict) -> str:
    t = TITLE.search(src)
    payload = json.dumps(data).replace("</", "<\\/")
    return (report_html.TEMPLATE.replace("__HEAD__", report_html.HEAD).replace("__BRAND__", report_html.BRAND)
            .replace("__X__", report_html.X_HANDLE).replace("__TITLE__", t.group(1) if t else "")
            .replace("__DATA__", payload)
            # the page's build stamp moves so open pages reload; the card's own "Updated" time (generated_at, when
            # lines were last pulled) is left as it was
            .replace("__BUILT__", autorefresh.meta(autorefresh.stamp()))
            .replace("__AUTOREFRESH__", autorefresh.SCRIPT))


def clocks(day: pd.Timestamp) -> dict[str, str]:
    """game_id -> ESPN's short status for started games ("2nd 8:41", "Halftime", "Final", "Final/OT"): display only,
    from the same free scoreboard the card's slate reads."""
    import urllib.request
    req = urllib.request.Request(run_day.SCOREBOARD.format(day.strftime("%Y%m%d")), headers={"User-Agent": "cbb-model"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    out = {}
    for ev in d.get("events") or []:
        st = (ev.get("status") or {}).get("type") or {}
        if st.get("state") in ("in", "post") and st.get("shortDetail"):
            out[str(ev["id"])] = st["shortDetail"]
    return out


def refresh_cards(scores, reports: str | None = None, rec: dict | None = None) -> list[str]:
    """The cards from the day before the current one through the coming week. Yesterday's and today's get live
    scores, states and the game clock (after 8 pm ET the current card is tomorrow's while tonight's games still
    play); today's and later get the record block rec (None keeps each page's; past days take it in
    report_html.refresh_past). Picks, lines and logged numbers are untouched. Returns the dates rewritten."""
    reports = reports or report_html.REPORTS_DIR
    path = os.path.join(reports, "days.json")
    if not os.path.exists(path):
        return []
    days = json.load(open(path))
    cur = days.get("current", "")
    done = []
    prev_day = f"{pd.Timestamp(cur) - pd.Timedelta(days=1):%Y-%m-%d}" if cur else ""
    for d in sorted(x for x in days.get("days", []) if x >= prev_day):
        f = os.path.join(reports, f"cbb_{d}.html")
        if not os.path.exists(f):
            continue
        src = open(f).read()
        m = DATA.search(src)
        if not m:
            continue
        data = json.loads(m.group(1))
        if data.get("replay"):
            continue
        before = json.dumps(data, sort_keys=True)
        if d <= cur:
            try:
                sl = scores(pd.Timestamp(d))
                now = {str(r["game_id"]): r for _, r in sl.iterrows()} if len(sl) else {}
            except Exception as e:
                print(f"Scores for {d} unavailable ({e}); scores left as they were.")
                now = {}
            try:
                clk = clocks(pd.Timestamp(d))
            except Exception as e:
                print(f"Game clocks for {d} unavailable ({e}); scores only.")
                clk = {}
            for g in data.get("games", []):
                if str(g.get("game_id")) in clk:
                    g["clock"] = clk[str(g.get("game_id"))]
                r = now.get(str(g.get("game_id")))
                if r is None:
                    continue
                g["state"] = r.get("state", g.get("state"))
                for k in ("home_score", "away_score"):
                    if pd.notna(r.get(k)):
                        g[k] = report_html._clean(r.get(k))
            data["prerule_res"] = report_html._prerule_results(d)
        if d >= cur and rec is not None and data.get("record") is not None:
            data["record"] = rec
        if json.dumps(data, sort_keys=True) != before:
            open(f, "w").write(_page(src, data))
            done.append(d)
    return done


def main() -> bool:
    """Grade, rebuild and say whether anything changed (so the workflow publishes only then)."""
    try:
        n = tracker.settle()
    except Exception as e:
        print(f"Grading failed ({e}); scores only.")
        n = 0
    cur = json.load(open(os.path.join(report_html.REPORTS_DIR, "days.json"))).get("current", "")
    f = os.path.join(report_html.REPORTS_DIR, f"cbb_{cur}.html")
    m = DATA.search(open(f).read()) if os.path.exists(f) else None
    prev = json.loads(m.group(1)).get("record") if m else None
    rec = record(prev) if n else None   # nothing graded: the record block cannot have changed
    cards = refresh_cards(run_day.slate, rec=rec)
    past = report_html.refresh_past(run_day.slate)
    if n:
        try:
            from . import record_page
            record_page.write()
        except Exception as e:
            print(f"Record page failed ({e}); continuing.")
    print(f"Graded {n} play(s); cards rewritten: {cards or 'none'}; past days: {past or 'none'}.")
    return bool(n or cards or past)


if __name__ == "__main__":
    changed = main()
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as fh:
            fh.write(f"publish={'true' if changed else 'false'}\n")
