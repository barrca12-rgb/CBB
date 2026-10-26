"""Build the Nov 2 card from the stored lines in whichever tree this runs in (cwd), with alerts and external posts
disabled and the clock fixed, so two trees can be compared byte for byte (card CSV and bets.csv)."""
import os, sys
for k in ("NTFY_TOPIC", "DISCORD_WEBHOOK", "ODDS_API_KEY", "SGO_API_KEY"):
    os.environ.pop(k, None)
sys.path.insert(0, os.getcwd())
import pandas as pd
FIXED = pd.Timestamp("2026-10-26T21:00:00Z")
pd.Timestamp.now = classmethod(lambda cls, tz=None: FIXED.tz_localize(None) if tz is None else FIXED.tz_convert(tz))
from cbb import run_day
day = pd.Timestamp("2026-11-02")
lines = pd.read_csv("lines/closing.csv")
op = pd.read_csv("lines/openers.csv")
lines = lines.merge(op[["book", "home_id", "away_id", "open_home_spread", "open_total"]], on=["book", "home_id", "away_id"], how="left")
run_day.build(day, run_day.slate(day), lines, current=True)
print("built")
