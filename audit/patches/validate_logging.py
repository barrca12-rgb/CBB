"""Exercise the forward-test logging with mocked feeds and alert endpoints (no network). Run in the patched tree."""
import io, json, os, sys, urllib.error, urllib.request
sys.path.insert(0, os.getcwd())
import pandas as pd

NOW = pd.Timestamp.now(tz="UTC").floor("s")
START = (NOW + pd.Timedelta(days=3)).strftime("%Y-%m-%dT23:30:00Z")
U = lambda m: (NOW - pd.Timedelta(minutes=m)).isoformat()
SGO = {"data": [{"eventID": "EVT1", "status": {"startsAt": START}, "teams": {
    "home": {"names": {"long": "Purdue Boilermakers"}}, "away": {"names": {"long": "Gonzaga Bulldogs"}}},
    "odds": {
        "points-home-game-sp-home": {"byBookmaker": {"draftkings": {"spread": "-3.5", "odds": "-110", "lastUpdatedAt": U(4)},
                                                     "fanduel": {"spread": "-3", "odds": "-115", "lastUpdatedAt": U(2), "available": False}}},
        "points-away-game-sp-away": {"byBookmaker": {"draftkings": {"spread": "3.5", "odds": "-110", "lastUpdatedAt": U(4)},
                                                     "fanduel": {"spread": "3", "odds": "-105", "lastUpdatedAt": U(2), "available": False}}},
        "points-all-game-ou-over": {"byBookmaker": {"draftkings": {"overUnder": "151.5", "odds": "-110", "lastUpdatedAt": U(800)}}},
        "points-all-game-ou-under": {"byBookmaker": {"draftkings": {"overUnder": "151.5", "odds": "-110", "lastUpdatedAt": U(800)}}}}}],
    "nextCursor": None}
OA = [{"id": "oaev1", "commence_time": START, "home_team": "Purdue Boilermakers", "away_team": "Gonzaga Bulldogs",
       "bookmakers": [{"key": "betmgm", "last_update": U(1), "markets": [
           {"key": "spreads", "last_update": U(1), "outcomes": [{"name": "Purdue Boilermakers", "point": -3.5, "price": -108},
                                                                  {"name": "Gonzaga Bulldogs", "point": 3.5, "price": -112}]},
           {"key": "totals", "last_update": U(6), "outcomes": [{"name": "Over", "point": 152.0, "price": -110},
                                                                 {"name": "Under", "point": 152.0, "price": -110}]}]}]}]
FAIL_SGO = {"on": False}
POSTS = []


class R(io.BytesIO):
    def __init__(self, obj, headers=None):
        super().__init__(json.dumps(obj).encode())
        self.headers = headers or {}
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def fake(req, timeout=None):
    url = req.full_url if hasattr(req, "full_url") else req
    if "sportsgameodds.com/v2/account/usage" in url:
        return R({"data": {"rateLimits": {"per-month": {"current-entities": 4400, "max-entities": 100000}}}})
    if "sportsgameodds.com" in url:
        if FAIL_SGO["on"]:
            raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, io.BytesIO(b"down"))
        return R(SGO)
    if "the-odds-api.com" in url:
        cost = "2" if "markets=spreads%2Ctotals&" in url and "h2h" not in url else "3"
        return R(OA, {"x-requests-remaining": "95000", "x-requests-used": "5000", "x-requests-last": cost})
    if "ntfy.sh" in url:
        POSTS.append(("ntfy", url)); return R({})
    if "discord" in url:
        POSTS.append(("discord", url)); return R({"id": "9001"})
    raise RuntimeError("unexpected url " + url)


urllib.request.urlopen = fake
os.environ.update({"SGO_API_KEY": "test", "ODDS_API_KEY": "test", "ODDS_API_EVERY_RUN": "1", "NTFY_TOPIC": "test-topic",
                   "DISCORD_WEBHOOK": "https://discord.com/api/webhooks/1/" + "x" * 68})
from cbb import odds, poll_targets, quotelog, notify, record, record_page, tracker

for f in ("lines/sgo_last_pull.txt",):
    if os.path.exists(f):
        os.remove(f)
print("1) card-run pull: SGO + The Odds API")
l = odds.pull()
print("   returned rows:", len(l), "| books:", sorted(l["book"].unique()))
print("2) card-run pull 1 minute later: SGO throttled (skipped), The Odds API ok")
odds.pull()
print("3) SGO error path")
os.remove("lines/sgo_last_pull.txt"); FAIL_SGO["on"] = True
odds.pull()
p = pd.read_csv("lines/polls.csv")
print(p.tail(6).to_string(index=False))
day = pd.Timestamp(NOW.tz_convert("America/New_York").date()).strftime("%Y-%m-%d")
o = pd.read_csv(f"lines/obs/{day}.csv")
print(f"   obs rows {len(o)}; by source/status:", o.groupby(["source", "status"]).size().to_dict())
print(o[o.poll_id == o.poll_id.iloc[0]][["source", "event_id", "game_key", "book", "market", "side", "line", "price", "quote_age_s", "status"]].to_string(index=False))
print("4) targeted poll")
poll_targets.main()
print(pd.read_csv("lines/polls_targeted.csv").to_string(index=False))
ot = pd.read_csv(f"lines/obs_targeted/{day}.csv"); print(f"   targeted obs rows {len(ot)}:", ot[["book", "market", "side", "line", "price", "quote_age_s"]].values.tolist())
print("5) a signal on the synthetic game: signal_log, ntfy and Discord alert logs")
quotelog.RUN_STARTED = NOW
gk_date = pd.Timestamp(START).tz_convert("America/New_York").strftime("%Y-%m-%d")
bet = {"bet_id": f"{gk_date}|999|spread|home", "date": gk_date, "game_id": 999, "market": "spread", "side": "home",
       "home_id": 2509, "away_id": 2250, "home": "Purdue", "away": "Gonzaga", "pick": "Purdue -3.5", "line": -3.5,
       "odds": -110, "book": "DraftKings", "edge": 2.7, "logged_at": NOW.isoformat()}
card = pd.DataFrame([{"game_id": 999, "start": START, "crew": None, "total_shift": 3.4, "spread_link": None}])
quotelog.signals([bet], card, pd.Timestamp(gk_date), quotelog.inputs(pd.Timestamp(gk_date), None), getattr(odds.pull, "pulled_at", None))
print(pd.read_csv("bets/signal_log.csv").tail(1).T.to_string())
notify.send([dict(bet, edge=2.7)], card)
notify.message("CBB play cancelled: test", "body")
record.post({"embeds": [{"title": "BET: Purdue -3.5 -110", "footer": {"text": "bet id " + bet["bet_id"]}}]})
print(pd.read_csv("bets/alert_log.csv").to_string(index=False))
print("6) record page cohorts with one confirmed accepted bet")
b = tracker.load()
first = b[b["status"] != "void"].iloc[0]
pd.DataFrame([{"bet_id": first["bet_id"], "book": first["book"], "placed_at": (pd.Timestamp(first["logged_at"]) + pd.Timedelta(minutes=12)).isoformat(),
               "line": float(first["line"]) - 0.5, "odds": -115, "stake": 1.0, "source": "manual test"}]).to_csv("bets/accepted.csv", index=False)
h = record_page.build()
i = h.index("Signals, quotes and accepted bets")
import re
print(re.sub(r"<[^>]+>", " ", h[i:i + 2600]).split("By month")[0])
