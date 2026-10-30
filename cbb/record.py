"""The public, timestamped record: every logged BET posted to a read-only Discord channel through a webhook.

One message when a bet is logged (same run as the phone alert, so both carry the same time), one when it settles
(close, CLV, result), and a correction when a bet is voided or reinstated; posts are never edited, so a wrong log is
fixed by a new message, not by changing an old one. Bets logged before the channel existed are posted on the first
run with their original logged time. Announcements of model and rule changes (bets/announcements.json, added by hand
with the date they went live) are posted once each.

Needs DISCORD_WEBHOOK (repository secret). Without it nothing is posted and nothing is marked posted, so the first
run with the secret catches up. What has been posted is kept in bets/discord_posted.json.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

import pandas as pd

from . import quotelog, tracker

STATE = os.path.join(tracker.ROOT, "bets", "discord_posted.json")
ANNOUNCEMENTS = os.path.join(tracker.ROOT, "bets", "announcements.json")
GREEN, RED, GRAY, BLUE = 0x2E7D32, 0xC62828, 0x757575, 0x1565C0


class Refused(Exception):
    """Discord refused the webhook itself (bad or deleted URL): stop this run's posting."""


def _close_prices(b) -> str:
    """Each closing book's number and price on the play's side ('DraftKings 154 -110, Caesars 154 -115'): shown
    beside the points CLV, never converted into it."""
    try:
        q = json.loads(b.get("price_vs_close") or "[]")
    except (TypeError, ValueError):
        return ""
    return ", ".join(f"{x['book']} {x['line']:g} {_price(x['price']) if x.get('price') is not None else '(no price)'}"
                     for x in q)[:1000]


def _label(payload: dict) -> str:
    """What a post was about, for the alert log: the bet id in its footer, or its title or first words."""
    e = (payload.get("embeds") or [{}])[0]
    foot = (e.get("footer") or {}).get("text", "")
    return foot.replace("bet id ", "").split(" · ")[0] if foot.startswith("bet id ") else (e.get("title") or payload.get("content", ""))[:120]


def url_shape(url: str) -> str:
    """What the webhook URL looks like, without the secret parts: prefix ok, id digits, token length (68 expected)."""
    m = re.match(r"^https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/(?:v\d+/)?webhooks/(\d+)/([\w-]+)$", url)
    if not m:
        return (f"not a Discord webhook URL (length {len(url)}, starts {url[:8]!r}, "
                f"whitespace {'yes' if url != url.strip() else 'no'})")
    return f"prefix ok, id {len(m.group(1))} digits, token {len(m.group(2))} chars"


def post(payload: dict, url: str | None = None) -> str | None:
    """Post one message; returns Discord's message id, or None if it didn't go out (printed, never raised). Raises
    Refused when Discord rejects the webhook itself (401, 403, 404)."""
    url = (url or os.environ.get("DISCORD_WEBHOOK", "")).strip()
    if not url:
        return None
    req = urllib.request.Request(url + ("&" if "?" in url else "?") + "wait=true", data=json.dumps(payload).encode(),
                                 method="POST", headers={"Content-Type": "application/json", "User-Agent": "cbb-model"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            mid = str(json.load(r).get("id") or "posted")
        quotelog.alert(_label(payload), "discord", "post", True, mid)
        return mid
    except urllib.error.HTTPError as e:
        quotelog.alert(_label(payload), "discord", "post", False)
        detail = e.read()[:200].decode(errors="ignore")
        print(f"Discord post failed: HTTP {e.code} {detail}")
        if e.code in (401, 403, 404):
            print(f"Discord refused the webhook; check the DISCORD_WEBHOOK secret ({url_shape(url)}).")
            raise Refused from e
        return None
    except Exception as e:
        quotelog.alert(_label(payload), "discord", "post", False)
        print(f"Discord post failed: {e}")
        return None
    finally:
        time.sleep(0.5)   # webhook rate limit: 5 posts per 2 seconds


def _price(odds) -> str:
    return f"{int(odds):+d}" if pd.notna(odds) else ""


def _tag(b: pd.Series) -> str:
    """Title prefix for a band B play (tracker.BAND_B); v1 titles are unchanged."""
    return "BAND B (0.5u) " if str(b.get("bet_type", "")) == tracker.BAND_B else ""


def _logged(b: pd.Series) -> dict:
    t = pd.Timestamp(b["logged_at"]).tz_convert("America/New_York")
    fields = [("Game", f"{b['away']} at {b['home']} · {b['date']}"), ("Market", b["market"].title()),
              ("Book", f"{b['book']} {_price(b['odds'])}"), ("Edge", f"{float(b['edge']):.1f} pts"),
              ("Stake", f"{float(b['stake']):g} u"), ("Logged", f"{t:%Y-%m-%d %-I:%M %p} ET")]
    try:   # venue check of the neutral flag (cbb/venue.py; display only)
        from . import venue
        fields.append(("Venue", venue.word(venue.lookup(b["date"], b["game_id"]))[len("Venue: "):]))
    except Exception as e:
        print(f"Venue field failed ({e}); continuing.")
    try:   # input freshness stamp (cbb/freshness.py; display only)
        from . import freshness
        fields.append(("Inputs", freshness.word(freshness.for_bet(b["bet_id"], b.get("market"), b.get("game_id")))[len("Inputs: "):]))
    except Exception as e:
        print(f"Freshness field failed ({e}); continuing.")
    return {"embeds": [{"title": f"{_tag(b)}BET: {b['pick']} {_price(b['odds'])}", "color": BLUE,
                        "fields": [{"name": k, "value": v, "inline": True} for k, v in fields],
                        "footer": {"text": f"bet id {b['bet_id']}"}}]}


def _settled(b: pd.Series) -> dict:
    res = {"W": "WIN", "L": "LOSS", "P": "PUSH"}.get(str(b["result"]), str(b["result"]))
    color = GREEN if res == "WIN" else RED if res == "LOSS" else GRAY
    placed = "not placed" if str(b.get("placed", "")).lower() == "no" else "placed"
    # b is clv_primary.attach()ed: close_line / clv_pts are the protocol's primary (consensus) close; the grader's
    # same-book values are clv_same_book / close_same_book, shown as a diagnostic only
    ok = pd.notna(b["clv_pts"])
    nb = int(b["books_primary"]) if pd.notna(b.get("books_primary")) else 0
    fields = [("Final", f"{b['away']} {b['away_score']:.0f}, {b['home']} {b['home_score']:.0f}"),
              ("Close (consensus, computed)", (f"{b['close_line']:g} ({nb} book{'s' if nb != 1 else ''}"
                                               f"{': one-book close' if nb == 1 else ''})") if ok else "unavailable"),
              ("Alert CLV (points)", f"{b['clv_pts']:+.2f} pts" if ok else "unavailable"),
              ("Pregame check", (str(b.get("pregame_check") or "not checked") if ok else "n/a")),
              ("Prices at close", _close_prices(b) or "none recorded"),
              ("Units", f"{b['profit']:+.2f}" if pd.notna(b["profit"]) else "–"), ("Bet", placed)]
    if not ok:
        fields.append(("Why no alert CLV", str(b.get("clv_reason") or "no primary close")[:1000]))
    if pd.notna(b.get("clv_same_book")):
        fields.append(("Same-book CLV (diagnostic)", f"{b['clv_same_book']:+.2f} pts"))
    from .clv_primary import VERIFICATION_STATUS
    return {"embeds": [{"title": f"{_tag(b)}{res}: {b['pick']} {_price(b['odds'])}", "color": color,
                        "fields": [{"name": k, "value": v, "inline": True} for k, v in fields],
                        "footer": {"text": f"bet id {b['bet_id']} · Alert CLV = points from the alert number to the "
                                           f"consensus close of fresh quotes in the last 15 min before tip; prices are "
                                           f"shown separately, not converted · CLV tracking: {VERIFICATION_STATUS}"}}]}


def sync(url: str | None = None) -> int:
    """Post everything not posted yet: new bets, results, voids and reinstatements, announcements. Returns posts."""
    url = (url or os.environ.get("DISCORD_WEBHOOK", "")).strip()
    if not url:
        return 0
    try:
        return _sync(url)
    except Refused:
        return 0


def _sync(url: str) -> int:
    st = json.load(open(STATE)) if os.path.exists(STATE) else {}
    for k in ("bets", "settled", "voided", "reinstated", "notes"):
        st.setdefault(k, {} if k == "bets" else [])
    n = 0

    def done(key, item, mid=None):   # saved after every post, so a failed run never posts twice
        nonlocal n
        n += 1
        if key == "bets":
            st["bets"][item] = mid
        else:
            st[key].append(item)
        with open(STATE, "w") as fh:
            json.dump(st, fh, indent=1)

    ann = json.load(open(ANNOUNCEMENTS)) if os.path.exists(ANNOUNCEMENTS) else []
    for a in ann:   # announcements first, so the record opens with the model that is running
        if a["id"] not in st["notes"] and post({"embeds": [{"title": f"Model note · {a['date']}",
                                                            "description": a["text"], "color": GRAY}]}, url):
            done("notes", a["id"])
    from . import clv_primary
    from . import tipoff
    tipoff.refresh(tracker.load("all"))                                # actual tips for the pregame check (cached)
    b = clv_primary.attach(tracker.load("all")).sort_values("logged_at")   # results post the primary-close CLV; band B tagged
    for _, r in b.iterrows():
        i = r["bet_id"]
        if i not in st["bets"]:
            mid = post(_logged(r), url)
            if mid:
                done("bets", i, mid)
        if i not in st["bets"]:
            continue
        if r["status"] == "void" and i not in st["voided"]:
            if post({"content": f"CORRECTION: {r['pick']} ({r['away']} at {r['home']}, {r['date']}) is void: not a "
                                f"play and not graded. bet id {i}"}, url):
                done("voided", i)
        elif r["status"] != "void" and i in st["voided"] and i not in st["reinstated"]:
            if post({"content": f"CORRECTION: {r['pick']} ({r['away']} at {r['home']}, {r['date']}) is reinstated "
                                f"and graded. bet id {i}"}, url):
                done("reinstated", i)
        # posts are never edited: a result waits for the next run if the closing observations could not be read
        if r["status"] == "settled" and str(r.get("clv_reason", "")).startswith("observations could not be read"):
            continue
        if r["status"] == "settled" and i not in st["settled"] and post(_settled(r), url):
            done("settled", i)
    return n


if __name__ == "__main__":
    print(f"Posted {sync()} message(s) to Discord.")
