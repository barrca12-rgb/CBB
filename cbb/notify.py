"""Phone alerts for new BET plays, through ntfy (https://ntfy.sh, free app for iPhone and Android).

The scheduled runs send one alert per newly logged BET: the pick, the book and price, edge, win chance and the game
time; tapping it opens that book's betslip (or the day's card when the book gave no link). Needs NTFY_TOPIC (a
repository secret; the topic name works as the password, so keep it unguessable). Without it, nothing is sent.
"""
from __future__ import annotations

import os
import urllib.request

import pandas as pd

SITE = "https://barrca12-rgb.github.io/CBB"


def _message(bet: dict, row: pd.Series | None) -> tuple[str, str, str]:
    mk = bet["market"]
    odds = bet.get("odds")
    price = f"{int(odds):+d}" if pd.notna(odds) else ""
    title = f"CBB BET: {bet['pick']} {price} {bet.get('book') or ''}".strip()
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
        return True
    except Exception as e:
        print(f"Alert failed: {e}")
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
        req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode(), method="POST",
                                     headers={"Title": title.encode("ascii", "ignore").decode(), "Click": click,
                                              "Priority": "high", "Tags": "basketball"})
        try:
            urllib.request.urlopen(req, timeout=20).read()
            sent += 1
        except Exception as e:
            print(f"Alert failed for {bet['bet_id']}: {e}")
    return sent


if __name__ == "__main__":   # python -m cbb.notify: one test alert
    test = {"bet_id": "test", "market": "spread", "pick": "Test pick +3.5", "odds": -110, "book": "DraftKings",
            "away": "Away", "home": "Home", "edge": 3.5, "date": pd.Timestamp.now(tz="America/New_York").strftime("%Y-%m-%d")}
    print("Test alert sent." if send([test], pd.DataFrame()) else "No alert sent (is NTFY_TOPIC set?)")
