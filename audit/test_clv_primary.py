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
        "start_gap_min": None, "feed_latest_start": None, "feed_gap_min": None, "tip_check": "ok", "close_primary": np.nan,
        "clv_primary": np.nan, "books_primary": 0, "feed_age_s": "[]", "obs_before_cutoff_s": "[]",
        "clv_status": "unavailable", "clv_reason": "no quotes logged for this game", "price_vs_close": "[]"}]))
    a = clv_primary.attach(b).iloc[0]
    assert np.isnan(a["clv_pts"]) and a["clv_same_book"] == 2.5 and a["close_same_book"] == 147.0


def test_coverage_counts_missing_and_never_averages_them_as_zero():
    s = pd.DataFrame({"result": ["W", "L", "W", "P"], "clv_pts": [2.0, np.nan, 1.0, 5.0], "books_primary": [3, 0, 1, 2]})
    cv = clv_primary.coverage(s)
    assert cv == {"decided": 3, "with_close": 2, "missing": 1, "one_book": 1, "two_plus": 1, "clv_two_plus": 2.0, "pregame_verified": None,
                  "share": 2 / 3, "clv": 1.5, "beat": 1.0}
    assert clv_primary.coverage_text(cv) == ("primary close for 2 of 3 decided plays (67%); 2+ books: 1 (+2.00), "
                                             "1 book: 1")


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
    assert f1["Alert CLV (points)"] == "+2.00 pts" and f1["Close (consensus, computed)"] == "147.5 (3 books)"
    assert f1["Same-book CLV (diagnostic)"] == "+1.00 pts"
    assert sorted(f1["Prices at close"].split(", ")) == ["Caesars 147.5 -110", "DraftKings 147.5 -110", "Fanatics 148.5 -110"]
    assert f2["Alert CLV (points)"] == "unavailable" and f2["Why no alert CLV"].startswith("tip time unknown")
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


def _cap_world(monkeypatch, tmp_path, n, primary_close, same_book_clv, missing=0, result="W"):
    """n settled unders at 149.5; each game's books close at primary_close (so primary CLV = 149.5 - close);
    the grader's same-book CLV is same_book_clv. `missing` extra settled bets have no closing quotes."""
    from cbb import tracker
    (tmp_path / "lines").mkdir(exist_ok=True)
    (tmp_path / "reports").mkdir(exist_ok=True)
    EMPTY_CLOSING.to_csv(tmp_path / "lines" / "closing.csv", index=False)
    rows, obs = [], []
    for i in range(n + missing):
        home, away = 1000 + 2 * i, 1001 + 2 * i
        rows.append(dict(bet(home=home, away=away), bet_id=f"2026-11-01|{i}|total|under", game_id=i, result=result,
                         close_line=149.5 - same_book_clv, clv_pts=same_book_clv, clv_prob=0.0, stake=1.0,
                         profit=0.91 if result == "W" else -1.0, home="H", away="A", pick="Under 149.5"))
        if i < n:
            obs += [ob(bk, "under", primary_close, -110, 5, 30, home=home, away=away) for bk in ("DraftKings", "Caesars")]
    o = fe.load_obs(pd.DataFrame(obs))
    monkeypatch.setattr(fe, "ROOT", str(tmp_path))
    monkeypatch.setattr(clv_primary, "_load_obs", lambda x: o)
    monkeypatch.setattr(tracker, "STAKE_CAP_STATE", str(tmp_path / "stake_cap.json"))
    return tracker, pd.DataFrame(rows)


def test_stake_cap_fires_on_negative_primary_clv_despite_positive_same_book(monkeypatch, tmp_path):
    tracker, b = _cap_world(monkeypatch, tmp_path, 25, primary_close=150.5, same_book_clv=+1.0)   # primary -1.0
    st = tracker.status(b)["total"]
    assert st["cap"]["on"] and st["cap"]["clv"] == -1.0 and st["cap"]["n"] == 25
    assert st["multiplier"] <= tracker.CAP_MULT


def test_stake_cap_stays_off_on_positive_primary_clv_despite_negative_same_book(monkeypatch, tmp_path):
    tracker, b = _cap_world(monkeypatch, tmp_path, 25, primary_close=148.5, same_book_clv=-1.0)   # primary +1.0
    st = tracker.status(b)["total"]
    assert not st["cap"]["on"] and st["cap"]["clv"] == 1.0
    assert st["multiplier"] == 1.0                     # 25 wins: the record multiplier itself is 1.0


def test_stake_cap_minimum_counts_only_bets_with_a_primary_close(monkeypatch, tmp_path):
    tracker, b = _cap_world(monkeypatch, tmp_path, 24, primary_close=150.5, same_book_clv=-1.0, missing=3)
    c = tracker.status(b)["total"]["cap"]
    assert not c["on"] and c["n"] == 24 and c["missing"] == 3 and c["settled"] == 27


def test_stake_cap_keeps_its_last_state_when_closes_cannot_be_read(monkeypatch, tmp_path):
    tracker, b = _cap_world(monkeypatch, tmp_path, 25, primary_close=150.5, same_book_clv=+1.0)
    assert tracker.status(b)["total"]["cap"]["on"]
    def boom(x):
        raise OSError("obs unreadable")
    monkeypatch.setattr(clv_primary, "_load_obs", boom)
    c = tracker.status(b)["total"]["cap"]
    assert c["state"] == "held" and c["on"]           # kept on, not reset by missing data


def test_stake_cap_records_its_last_successful_refresh_and_keeps_it_while_held(monkeypatch, tmp_path):
    tracker, b = _cap_world(monkeypatch, tmp_path, 25, primary_close=150.5, same_book_clv=+1.0)
    first = tracker.status(b)["total"]["cap"]["refreshed_at"]
    assert first is not None
    def boom(x):
        raise OSError("obs unreadable")
    monkeypatch.setattr(clv_primary, "_load_obs", boom)
    c = tracker.status(b)["total"]["cap"]
    assert c["state"] == "held" and c["refreshed_at"] == first      # the stale time stays visible while held


@pytest.mark.parametrize("market,side,entry,home_close,clv", [
    ("spread", "home", -12.0, -12.5, 0.5),     # favorite: entry -12, close -12.5
    ("spread", "away", 12.0, -11.5, 0.5),      # underdog: entry +12, close +11.5 (home -11.5)
    ("total", "over", 152.5, 154.0, 1.5),
    ("total", "under", 149.5, 148.0, 1.5),
])
def test_points_clv_is_measured_on_the_selected_side(market, side, entry, home_close, clv):
    """Chad's table (Oct 28): both spread numbers refer to the selected team; + = the alert beat the close."""
    b = pd.DataFrame([dict(bet(market=market, side=side, line=entry))])
    if market == "spread":
        obs = [ob(bk, sd, home_close if sd == "home" else -home_close, -110, m, 30, market="spread")
               for bk, m in (("DraftKings", 3), ("Caesars", 5)) for sd in ("home", "away")]
    else:
        obs = [ob(bk, sd, home_close, -110, m, 30) for bk, m in (("DraftKings", 3), ("Caesars", 5)) for sd in ("over", "under")]
    r = clv_primary.primary(b, obs=pd.DataFrame(obs), closing=EMPTY_CLOSING).iloc[0]
    assert r["books_primary"] == 2 and r["clv_primary"] == pytest.approx(clv)
    sel = home_close if market == "total" or side == "home" else -home_close
    assert r["close_primary"] == pytest.approx(sel)


def test_independent_recomputation_from_raw_files_matches_the_protocol(tmp_path):
    """audit/clv_example.recompute reads the raw CSVs with the standard library only; on the same quotes it must give
    the protocol's cutoff, book count, close and alert CLV (stale, out-of-window and in-play quotes included)."""
    from audit import clv_example
    obs = pd.DataFrame([ob("DraftKings", "under", 147.5, -110, 3, 40), ob("Caesars", "under", 147.0, -110, 5, 60),
                        ob("Fanatics", "under", 148.5, -110, 4, 20), ob("Fanatics", "under", 151.0, -110, 2, 900),
                        ob("FanDuel", "under", 146.0, -110, 20, 20), ob("BetMGM", "under", 140.0, -110, -2, 20)])
    (tmp_path / "obs").mkdir()
    obs.to_csv(tmp_path / "obs" / "2026-11-01.csv", index=False)
    b = bet()
    r = clv_primary.primary(pd.DataFrame([b]), obs=obs, closing=EMPTY_CLOSING).iloc[0]
    rc = clv_example.recompute(b, obs["game_key"].iloc[0], lines_dir=str(tmp_path))
    assert rc["books"] == r["books_primary"] == 3 and rc["close"] == r["close_primary"] == 147.5
    assert rc["clv"] == pytest.approx(r["clv_primary"]) and pd.Timestamp(rc["cutoff"]) == pd.Timestamp(r["cutoff"])
