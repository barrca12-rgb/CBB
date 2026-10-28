"""Tests for cbb/clv_primary.py against the protocol's frozen close (audit/forward_eval.py). Synthetic observations
only; nothing here reads or writes the live logs.

    python -m pytest -q audit/test_clv_primary.py
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from audit import forward_eval as fe
from cbb import clv_primary

TIP = pd.Timestamp("2026-11-01T14:30:00Z")
NOW = TIP + pd.Timedelta(hours=4)
EMPTY_CLOSING = pd.DataFrame(columns=["date", "home_id", "away_id", "book", "home_spread", "total", "start", "pulled_at"])


def bet(market="total", side="under", line=149.5, odds=-110, home=222, away=87, status="settled", model=139.77):
    return {"bet_id": f"2026-11-01|1|{market}|{side}", "date": "2026-11-01", "game_id": 1, "market": market,
            "side": side, "home_id": home, "away_id": away, "line": line, "odds": odds, "book": "DraftKings",
            "model": model, "logged_at": "2026-10-25T22:32:02+00:00", "status": status, "result": "W"}


def ob(book, side, line, price, minutes_before, age_s, market="total", status="available", start=TIP, home=222, away=87):
    t = TIP - pd.Timedelta(minutes=minutes_before)
    lo, hi = sorted((home, away))
    return {"poll_id": "p", "observed_at": t.isoformat(), "source": "oddsapi", "event_id": "e",
            "game_key": f"2026-11-01|{lo}|{hi}", "start": start.isoformat(), "book": book, "market": market,
            "side": side, "line": line, "price": price,
            "source_updated_at": (t - pd.Timedelta(seconds=age_s)).isoformat(), "quote_age_s": age_s,
            "status": status, "log": "obs_targeted"}


def run(bets, obs):
    return clv_primary.primary(pd.DataFrame(bets), obs=pd.DataFrame(obs), closing=EMPTY_CLOSING, now=NOW)


def test_consensus_is_median_of_each_books_last_valid_quote_and_excludes_invalid_rows():
    obs = [ob("DraftKings", "under", 148.5, -110, 12, 30), ob("DraftKings", "under", 147.5, -112, 3, 40),
           ob("Caesars", "under", 147.5, -110, 5, 60), ob("Fanatics", "under", 148.5, -110, 4, 20),
           ob("FanDuel", "under", 140.0, -110, 4, 900),                    # stale: older than 300 s
           ob("BetMGM", "under", 140.0, -110, 2, 10, status="absent"),     # not available
           ob("bet365", "under", 140.0, -110, 30, 10),                     # outside the 15-minute window
           ob("theScore Bet", "under", 140.0, -110, -2, 10)]               # after the cutoff (in play)
    r = run([bet()], obs).iloc[0]
    assert r["books_primary"] == 3                                         # DraftKings (last), Caesars, Fanatics
    assert r["close_primary"] == 147.5                                     # median of 147.5, 147.5, 148.5
    assert r["clv_primary"] == pytest.approx(2.0)                          # under: logged 149.5 - close 147.5
    assert r["clv_status"] == "ok"
    assert sorted(json.loads(r["feed_age_s"])) == [20, 40, 60]


def test_matches_the_frozen_strict_close_exactly():
    obs = pd.DataFrame([ob("DraftKings", "over", 150.5, -105, 6, 50), ob("Caesars", "over", 151.0, -110, 9, 80)])
    o = fe.load_obs(obs)
    sc = fe.strict_close(o, "total", TIP)
    r = run([bet(side="over", line=149.5)], obs).iloc[0]
    assert r["close_primary"] == sc["close"] and r["books_primary"] == sc["books"]


@pytest.mark.parametrize("market,side,line,quotes,close,clv", [
    # favorite: Florida -5.5 at home; the market closes Florida -6.5 (home number -6.5) -> +1.0, a better entry
    ("spread", "home", -5.5, [("home", -6.5), ("away", 6.5)], -6.5, 1.0),
    # underdog: Purdue +4.5 (away here); closes +3.5 for the away team (home -3.5) -> +1.0
    ("spread", "away", 4.5, [("home", -3.5), ("away", 3.5)], 3.5, 1.0),
    # over 152.5, closes 154.5 -> +2.0 (the over got the lower number)
    ("total", "over", 152.5, [("over", 154.5), ("under", 154.5)], 154.5, 2.0),
    # under 149.5, closes 147.5 -> +2.0 (the under got the higher number)
    ("total", "under", 149.5, [("under", 147.5), ("over", 147.5)], 147.5, 2.0),
])
def test_positive_clv_means_a_better_entry(market, side, line, quotes, close, clv):
    obs = [ob(bk, s, ln, -110, 5, 30, market=market) for bk in ("DraftKings", "Caesars") for s, ln in quotes]
    r = run([bet(market=market, side=side, line=line)], obs).iloc[0]
    assert r["close_primary"] == pytest.approx(close)
    assert r["clv_primary"] == pytest.approx(clv)


def test_worse_entry_is_negative():
    obs = [ob("DraftKings", "under", 151.5, -110, 5, 30)]
    assert run([bet(line=149.5)], obs).iloc[0]["clv_primary"] == pytest.approx(-2.0)


def test_missing_close_is_unavailable_with_a_reason_never_zero_or_the_graders():
    obs = [ob("DraftKings", "under", 147.5, -110, 5, 900), ob("Caesars", "under", 147.5, -110, 6, 1200)]
    r = run([bet()], obs).iloc[0]
    assert np.isnan(r["close_primary"]) and np.isnan(r["clv_primary"]) and r["books_primary"] == 0
    assert r["clv_status"] == "unavailable" and "older than 300 s" in r["clv_reason"]
    r2 = run([bet()], [ob("DraftKings", "under", 147.5, -110, 40, 10)]).iloc[0]
    assert r2["clv_reason"] == "no quote observed in the 15 minutes before the tip cutoff"


def test_no_quotes_and_before_tip_are_reported_separately():
    assert run([bet()], [ob("X", "under", 1, -110, 5, 5, home=1, away=2)]).iloc[0]["clv_reason"] == \
        "tip time unknown (no pregame observation and no scheduled start in closing.csv)"
    early = clv_primary.primary(pd.DataFrame([bet()]), obs=pd.DataFrame([ob("DraftKings", "under", 148, -110, 60, 5)]),
                                closing=EMPTY_CLOSING, now=TIP - pd.Timedelta(hours=1)).iloc[0]
    assert early["clv_status"] == "pending"


def test_a_moved_start_moves_the_cutoff():
    later = TIP + pd.Timedelta(minutes=30)
    obs = [ob("DraftKings", "under", 148.5, -110, 20, 10, start=later),    # observed before the old tip, new start reported
           ob("DraftKings", "under", 146.5, -110, -20, 10, start=later)]   # 10 min before the new tip
    r = run([bet()], obs).iloc[0]
    assert pd.Timestamp(r["cutoff"]) == later and r["close_primary"] == 146.5


def test_same_number_different_price_is_not_called_equal():
    obs = [ob("DraftKings", "under", 149.5, -125, 5, 30)]
    r = run([bet(line=149.5, odds=-110)], obs).iloc[0]
    assert r["clv_primary"] == 0.0
    pv = json.loads(r["price_vs_close"])
    assert pv[0]["vs_entry"] == "no: same number, worse price"          # the close is worse for a new bettor:
    obs2 = [ob("DraftKings", "under", 149.5, -105, 5, 30)]              # the entry at -110 beat a -125 close
    assert json.loads(run([bet(line=149.5, odds=-110)], obs2).iloc[0]["price_vs_close"])[0]["vs_entry"] == \
        "yes: same number, price as good or better"


def test_attach_keeps_the_graders_value_as_diagnostic_and_never_substitutes_it(monkeypatch):
    b = pd.DataFrame([dict(bet(), close_line=147.0, clv_pts=2.5)])
    monkeypatch.setattr(clv_primary, "primary", lambda b: pd.DataFrame([{
        "bet_id": b["bet_id"].iloc[0], "cohort": "pre-freeze", "cutoff": None, "cutoff_source": "", "espn_start": None,
        "start_gap_min": None, "close_primary": np.nan,
        "clv_primary": np.nan, "books_primary": 0, "feed_age_s": "[]", "obs_before_cutoff_s": "[]",
        "clv_status": "unavailable", "clv_reason": "no quotes logged for this game", "price_vs_close": "[]"}]))
    a = clv_primary.attach(b).iloc[0]
    assert np.isnan(a["clv_pts"]) and a["clv_same_book"] == 2.5 and a["close_same_book"] == 147.0


def test_coverage_counts_missing_and_never_averages_them_as_zero():
    s = pd.DataFrame({"result": ["W", "L", "W", "P"], "clv_pts": [2.0, np.nan, 1.0, 5.0]})
    cv = clv_primary.coverage(s)
    assert cv == {"decided": 3, "with_close": 2, "missing": 1, "share": 2 / 3, "clv": 1.5, "beat": 1.0}


def test_every_surface_shows_the_same_primary_clv(monkeypatch, tmp_path):
    """One settled play (under 149.5, consensus close 147.5 -> +2.0; same-book close 148.5 -> +1.0) and one settled
    play with no closing observations. Discord, the card (tile, record table, recent table), the record page, the
    verification page, the weekly chart, the loss review and the tripwire must all show +2.0 for the first and no
    CLV for the second, with coverage 1 of 2."""
    from cbb import record, record_chart, record_page, report_html, review, tracker
    (tmp_path / "lines").mkdir()
    (tmp_path / "reports").mkdir()
    EMPTY_CLOSING.to_csv(tmp_path / "lines" / "closing.csv", index=False)
    b1 = dict(bet(), bet_id="2026-11-01|1|total|under", game_id=1, home="Villanova", away="Notre Dame", pick="Under 149.5",
              close_line=148.5, clv_pts=1.0, clv_prob=0.02, home_score=70, away_score=72, result="W", profit=0.91,
              stake=1.0, placed="yes", edge=9.7, alert_line=149.5, book="DraftKings")
    b2 = dict(b1, bet_id="2026-11-01|2|total|over", game_id=2, side="over", pick="Over 140", line=140.0, home_id=5,
              away_id=6, home="A", away="B", close_line=141.0, clv_pts=-1.0, result="L", profit=-1.0)
    bets = pd.DataFrame([b1, b2])
    obs = fe.load_obs(pd.DataFrame([ob("DraftKings", "under", 147.5, -110, 3, 40), ob("Caesars", "under", 147.5, -110, 5, 60),
                                    ob("Fanatics", "under", 148.5, -110, 4, 20)]))
    monkeypatch.setattr(fe, "ROOT", str(tmp_path))
    monkeypatch.setattr(clv_primary, "_load_obs", lambda o: obs)
    monkeypatch.setattr(tracker, "load", lambda: bets.copy())
    monkeypatch.setattr(review, "_three_luck", lambda s: pd.Series(0.0, index=s.index))
    monkeypatch.setattr(review, "_late_news", lambda s: pd.Series(False, index=s.index))
    a = clv_primary.attach(bets)
    r1, r2 = a.iloc[0], a.iloc[1]
    assert r1["clv_pts"] == pytest.approx(2.0) and r1["clv_same_book"] == 1.0 and np.isnan(r2["clv_pts"])
    # Discord
    f1 = {f["name"]: f["value"] for f in record._settled(r1)["embeds"][0]["fields"]}
    f2 = {f["name"]: f["value"] for f in record._settled(r2)["embeds"][0]["fields"]}
    assert f1["CLV"] == "+2.00 pts" and f1["Close (consensus)"] == "147.5 (3 books)" and f1["Same-book CLV (diagnostic)"] == "+1.00 pts"
    assert f2["CLV"] == "unavailable" and f2["Why no CLV"].startswith("tip time unknown")
    # card: tile, record table, recent table
    v = report_html._clv_view()
    assert v["all"]["clv"] == pytest.approx(2.0) and (v["all"]["with_close"], v["all"]["decided"]) == (1, 2)
    assert v["total"]["clv"] == pytest.approx(2.0)
    rec = {x["pick"]: x for x in v["recent"]}
    assert rec["Under 149.5"]["clv_pts"] == pytest.approx(2.0) and np.isnan(rec["Over 140"]["clv_pts"])
    # record page and verification page
    s = record_page.summary(a[a["status"] == "settled"])
    assert s["clv"] == pytest.approx(2.0) and s["cov"] == "1/2"
    html_, note = record_page.cohorts(a)
    assert "+2.00" in html_ and "1/2" in html_
    # weekly chart
    st = record_chart.stats(a, pd.Timestamp("2026-11-01"))
    assert st["tiles"]["total"]["mean"] == pytest.approx(2.0) and st["tiles"]["total"]["decided"] == 2
    # loss review and tripwire
    cl = review.classify().set_index("bet_id")["reason"]
    assert cl["2026-11-01|1|total|under"] == "Beat the close" and cl["2026-11-01|2|total|over"] == "No primary close"
    t = tracker.tripwires(bets)["model"]
    assert t["clv"] == pytest.approx(2.0) and t["with_close"] == 1 and t["missing"] == 1 and t["state"] == "collecting"
