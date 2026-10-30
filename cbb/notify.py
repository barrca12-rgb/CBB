"""Phone alerts for new BET plays, through ntfy (https://ntfy.sh, free app for iPhone and Android).

The scheduled runs send one alert per newly logged BET: the pick, the book and price, edge, win chance and the game
time; tapping it opens that book's betslip (or the day's card when the book gave no link). Needs NTFY_TOPIC (a
repository secret; the topic name works as the password, so keep it unguessable). Without it, nothing is sent.
"""
from __future__ import annotations

import os
import urllib.request

import pandas as pd

from . import quotelog

SITE = "https://barrca12-rgb.github.io/CBB"


def compare(market: str, side: str, number: float, price: float, line, odds) -> str:
    """How a show-only (Novig) quote compares with the alerted number and price, from the bet's side."""
    if line is None or pd.isna(line) or odds is None or pd.isna(odds):
        return ""
    pay = lambda o: o / 100 if o > 0 else 100 / -o
    k = number if market == "spread" or side == "under" else -number
    r = float(line) if market == "spread" or side == "under" else -float(line)
    if k > r + 1e-9:
        return "better number" + (", worse price" if pay(price) < pay(float(odds)) - 1e-9 else "")
    if abs(k - r) < 1e-9 and pay(price) > pay(float(odds)) + 1e-9:
        return "better price"
    return ""


def novig_line(bet: dict) -> str:
    """One line with Novig's price on the bet's side, if Novig has the game (show-only; Chad, Oct 30)."""
    try:
        from . import odds_api
        if bet.get("home_id") is None:
            return ""
        mk, side = bet["market"], str(bet.get("side", "")).lower()
        q = odds_api.display_side(odds_api.display_quote(int(bet["home_id"]), int(bet["away_id"])), mk, side)
        if not q:
            return ""
        n, p = q
        num = f"{n:+g}" if mk == "spread" else f"{side.title()} {n:g}"
        c = compare(mk, side, n, p, bet.get("line"), bet.get("odds"))
        return f"Novig: {num} {int(p):+d}" + (f" ({c})" if c else "")
    except Exception as e:
        print(f"Novig line failed ({e}); continuing.")
        return ""


def _message(bet: dict, row: pd.Series | None) -> tuple[str, str, str]:
    mk = bet["market"]
    odds = bet.get("odds")
    price = f"{int(odds):+d}" if pd.notna(odds) else ""
    tag = "CBB BAND B (0.5u):" if bet.get("bet_type") == "bandB" else "CBB BET:"   # band B: tracker.BAND_B
    title = f"{tag} {bet['pick']} {price} {bet.get('book') or ''}".strip()
    lines = [f"{bet['away']} at {bet['home']}"]
    if row is not None and pd.notna(row.get("start")):
        t = pd.Timestamp(row["start"]).tz_convert("America/New_York")
        lines[0] += f", {t:%a %b %-d %-I:%M %p} ET"
    detail = f"Edge {bet['edge']:.1f} pts"
    if row is not None and pd.notna(row.get(f"{mk}_p")):
        detail += f" · win {100 * row[f'{mk}_p']:.0f}% · EV {100 * row[f'{mk}_ev']:+.0f}%"
    lines.append(detail)
    if row is not None and pd.notna(row.get(f"{mk}_good_to")):
        lines.append(f"Good down to {row[f'{mk}_good_to']:+.1f}" if mk == "spread"
                     else f"Good to {row[f'{mk}_good_to']:.1f}")
    nv = novig_line(bet)
    if nv:
        lines.append(nv)
    try:   # venue check of the neutral flag (cbb/venue.py; display only)
        from . import venue
        lines.append(venue.word(venue.lookup(bet["date"], bet["game_id"])))
    except Exception as e:
        print(f"Venue line failed ({e}); continuing.")
    warn = row.get(f"{mk}_warn") if row is not None else None
    if isinstance(warn, str) and warn:
        lines.insert(0, "WARNING: " + warn)
    # injury report (every source) and team news for both teams at the moment of the alert
    try:
        from . import team_news
        if row is not None and pd.notna(row.get("home_id")):
            inj = team_news.injury_lines(int(row["home_id"]), int(row["away_id"]))
            lines.append("Injuries: " + ("; ".join(inj) if inj else "none listed"))
        flag = row.get("news_flag") if row is not None else None
        if isinstance(flag, str) and flag:
            lines.append(flag)
    except Exception as e:
        print(f"Alert news lines failed ({e}); continuing.")
    link = row.get(f"{mk}_link") if row is not None else None
    click = link if isinstance(link, str) and link else f"{SITE}/cbb_{bet['date']}.html"
    return title, "\n".join(lines), click


def message(title: str, body: str, topic: str | None = None, click: str | None = None) -> bool:
    """A one-off alert (not a bet). Returns whether it went out."""
    topic = topic or os.environ.get("NTFY_TOPIC", "")
    if not topic:
        return False
    req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode(), method="POST",
                                 headers={"Title": title.encode("ascii", "ignore").decode(), "Click": click or SITE,
                                          "Tags": "basketball"})
    try:
        urllib.request.urlopen(req, timeout=20).read()
        quotelog.alert(title, "ntfy", "message", True)
        return True
    except Exception as e:
        print(f"Alert failed: {e}")
        quotelog.alert(title, "ntfy", "message", False)
        return False


def send(new_bets: list[dict], card: pd.DataFrame, topic: str | None = None) -> int:
    """Send an alert for each new bet. Returns how many went out; a failed send is printed, never raised."""
    topic = topic or os.environ.get("NTFY_TOPIC", "")
    if not topic or not new_bets:
        return 0
    rows = card.set_index("game_id") if len(card) else None
    sent = 0
    for bet in new_bets:
        row = rows.loc[bet["game_id"]] if rows is not None and bet["game_id"] in rows.index else None
        title, body, click = _message(bet, row)
        headers = {"Title": title.encode("ascii", "ignore").decode(), "Click": click, "Priority": "high",
                   "Tags": "basketball"}
        news = row.get("news_url") if row is not None else None
        if isinstance(news, str) and news:   # buttons on the alert: injury news search, and the bet
            headers["Actions"] = f"view, News, {news}; view, Bet, {click}"
        req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode(), method="POST", headers=headers)
        try:
            urllib.request.urlopen(req, timeout=20).read()
            sent += 1
            quotelog.alert(bet["bet_id"], "ntfy", "bet", True)
        except Exception as e:
            print(f"Alert failed for {bet['bet_id']}: {e}")
            quotelog.alert(bet["bet_id"], "ntfy", "bet", False)
    return sent


if __name__ == "__main__":   # python -m cbb.notify: one test alert
    test = {"bet_id": "test", "market": "spread", "pick": "Test pick +3.5", "odds": -110, "book": "DraftKings",
            "away": "Away", "home": "Home", "edge": 3.5, "date": pd.Timestamp.now(tz="America/New_York").strftime("%Y-%m-%d")}
    print("Test alert sent." if send([test], pd.DataFrame()) else "No alert sent (is NTFY_TOPIC set?)")
