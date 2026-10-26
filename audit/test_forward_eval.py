"""Tests for the forward-test evaluation (protocol 2.0) and the quote logger, on synthetic data.

    python -m unittest audit.test_forward_eval -v
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest

import numpy as np
import pandas as pd

from audit import forward_eval as fe
from cbb import quotelog

T0 = pd.Timestamp("2026-11-10T20:00:00Z")      # the alert
TIP = pd.Timestamp("2026-11-11T00:00:00Z")     # scheduled start
GK = "2026-11-10|10|20"


def bet(**kw) -> dict:
    b = {"bet_id": "2026-11-10|1|spread|home", "date": "2026-11-10", "game_id": 1, "market": "spread", "pick": "X",
         "side": "home", "home_id": 10, "away_id": 20, "home": "H", "away": "A", "line": -3.0, "alert_line": -3.0,
         "odds": -110.0, "book": "DraftKings", "edge": 3.0, "model": 6.0, "stake": 1.0, "placed": "",
         "logged_at": "2026-11-10T19:59:00+00:00", "close_line": np.nan, "clv_pts": np.nan, "clv_prob": np.nan,
         "home_score": np.nan, "away_score": np.nan, "result": np.nan, "profit": np.nan, "status": "open"}
    b.update(kw)
    return b


def ob(minutes: float, line=-3.0, price=-110, book="DraftKings", side="home", market="spread", status="available",
       age_s=30, source="oddsapi", log="obs_targeted", start=TIP) -> dict:
    t = T0 + pd.Timedelta(minutes=minutes)
    return {"poll_id": f"p{minutes}", "observed_at": t.isoformat(), "source": source, "event_id": "e", "game_key": GK,
            "start": start.isoformat(), "book": book, "market": market, "side": side, "line": line, "price": price,
            "source_updated_at": (t - pd.Timedelta(seconds=age_s)).isoformat() if age_s is not None else None,
            "quote_age_s": age_s, "status": status, "log": log}


ALERTS = pd.DataFrame([{"id": "2026-11-10|1|spread|home", "channel": "ntfy", "kind": "bet", "sent_at": T0.isoformat(),
                        "ok": True, "message_id": ""}])
EMPTY_CLOSING = pd.DataFrame(columns=["date", "home_id", "away_id", "book", "home_spread", "total", "start", "pulled_at"])


def windows(obs_rows, b=None, alerts=ALERTS, closing=EMPTY_CLOSING) -> pd.DataFrame:
    sig, _ = fe.load_signals("v1", None, pd.DataFrame([b or bet()]))
    d = fe.delay_windows(sig, fe.load_obs(pd.DataFrame(obs_rows)), closing, alerts)
    return d[d["scope"] == "original book"].set_index("window")


class DelayWindows(unittest.TestCase):
    def test_first_observation_in_each_bounded_window(self):
        d = windows([ob(3), ob(7, line=-2.5), ob(8, line=-4), ob(12), ob(20, line=-3.5), ob(31), ob(70)])
        self.assertEqual(d.loc["5-10 min", "elapsed_min"], 7.0)          # not the 3-minute one, not the later 8
        self.assertEqual(d.loc["5-10 min", "line"], -2.5)
        self.assertEqual(d.loc["15-25 min", "elapsed_min"], 20.0)        # the 12-minute observation is in no window
        self.assertEqual(d.loc["30-45 min", "elapsed_min"], 31.0)
        self.assertEqual(d.loc["60-80 min", "elapsed_min"], 70.0)

    def test_no_observation_is_missing(self):
        d = windows([ob(7)])
        self.assertEqual(d.loc["15-25 min", "outcome"], "missing")

    def test_unavailable_or_stale_first_observation_is_not_skipped(self):
        d = windows([ob(6, status="absent"), ob(8), ob(16, age_s=900), ob(18)])
        self.assertEqual(d.loc["5-10 min", "outcome"], "unavailable")
        self.assertEqual(d.loc["15-25 min", "outcome"], "stale")
        d = windows([ob(6, age_s=None)])
        self.assertEqual(d.loc["5-10 min", "outcome"], "stale")          # no feed timestamp: never available

    def test_late_alert_windows_stop_at_the_tip(self):
        tip = T0 + pd.Timedelta(minutes=40)
        d = windows([ob(7, start=tip), ob(33, start=tip), ob(41, start=tip), ob(65, start=tip)])
        self.assertEqual(d.loc["30-45 min", "outcome"], "available")
        self.assertTrue(d.loc["30-45 min", "truncated_by_tip"])
        self.assertEqual(d.loc["60-80 min", "outcome"], "window after tip")
        d = windows([ob(38, start=tip), ob(42, start=tip)])               # post-tip quote never used
        self.assertEqual(d.loc["30-45 min", "elapsed_min"], 38.0)
        d = windows([ob(42, start=tip)])
        self.assertEqual(d.loc["30-45 min", "outcome"], "missing")

    def test_alert_fallback_is_labelled(self):
        d = windows([ob(7)], alerts=ALERTS.iloc[0:0])
        self.assertTrue(d["alert_source"].str.startswith("fallback").all())

    def test_A_acceptable_price_and_B_frozen_ev(self):
        d = windows([ob(7, price=-105), ob(16, line=-2.5, price=-120), ob(31, price=-115), ob(61, line=-3.5, price=100)])
        self.assertEqual(d.loc["5-10 min", "A"], "yes: same number, price as good or better")
        self.assertEqual(d.loc["15-25 min", "A"], "ambiguous: better number, worse price")
        self.assertEqual(d.loc["30-45 min", "A"], "no: same number, worse price")
        self.assertEqual(d.loc["60-80 min", "A"], "no: worse number")
        # model home margin 6 at home -3: edge 3, p = 0.5 + 0.0255 * 3 = 0.5765; EV at -105 = +12.6%
        self.assertAlmostEqual(d.loc["5-10 min", "ev_v1"], 0.5765 * 100 / 105 - 0.4235, places=4)
        self.assertTrue(d.loc["5-10 min", "B_rule"])
        # at -3.5 (edge 2.5, p 0.56375) and +100, EV = +12.75%: passes EV and the 2.5 threshold
        self.assertTrue(d.loc["60-80 min", "B_ev"])

    def test_duplicate_feeds_resolve_deterministically(self):
        rows = [ob(7, line=-2.5, source="sgo", log="obs"), ob(7, line=-3.5, source="oddsapi", log="obs"),
                ob(7, line=-3.0, source="oddsapi", log="obs_targeted")]
        first = windows(rows).loc["5-10 min", "line"]
        for perm in ([2, 0, 1], [1, 2, 0], [2, 1, 0]):
            self.assertEqual(windows([rows[i] for i in perm]).loc["5-10 min", "line"], first)
        self.assertEqual(first, -3.5)     # card log before targeted log, The Odds API before SGO


class Closes(unittest.TestCase):
    def close(self, rows, market="spread"):
        o = fe.load_obs(pd.DataFrame(rows))
        cutoff, how = fe.tip_cutoff(o, None)
        return fe.strict_close(o, market, cutoff), cutoff, how

    def test_strict_close_rejects_stale_post_tip_and_old(self):
        m = (TIP - T0).total_seconds() / 60
        rows = [ob(m - 10, line=-4, age_s=400),          # inside 15 minutes, but the feed timestamp is too old
                ob(m - 20, line=-5),                      # valid but older than 15 minutes before the cutoff
                ob(m - 8, line=-3.5),                     # the close
                ob(m + 1, line=-9)]                       # after the tip
        c, cutoff, how = self.close(rows)
        self.assertEqual(cutoff, TIP)
        self.assertEqual(c["close"], -3.5)
        self.assertEqual(c["books"], 1)
        self.assertTrue(np.isnan(self.close([ob(m - 10, age_s=400)])[0]["close"]))

    def test_consensus_median_and_away_rows(self):
        m = (TIP - T0).total_seconds() / 60
        rows = [ob(m - 5, line=-3, book="DraftKings"), ob(m - 5, line=4, side="away", book="FanDuel"),
                ob(m - 4, line=-3.5, book="BetMGM"), ob(m - 4, line=-1, book="NotABook")]
        c, _, _ = self.close(rows)
        self.assertEqual(c["books"], 3)
        self.assertEqual(c["close"], -3.5)                # median of -3, -4, -3.5

    def test_delayed_start_moves_the_cutoff(self):
        later = TIP + pd.Timedelta(hours=1)
        m = (TIP - T0).total_seconds() / 60
        rows = [ob(m - 30, line=-3), ob(m + 55, line=-6, start=later)]   # rescheduled: observed after the old tip
        c, cutoff, _ = self.close(rows)
        self.assertEqual(cutoff, later)
        self.assertEqual(c["close"], -6)

    def test_line_value_signs(self):
        self.assertEqual(fe.line_value(pd.Series(bet()), -4.0), 1.0)
        self.assertEqual(fe.line_value(pd.Series(bet(market="total", side="over", line=150)), 152.0), 2.0)
        self.assertEqual(fe.line_value(pd.Series(bet(market="total", side="under", line=150)), 152.0), -2.0)


class Inference(unittest.TestCase):
    def season(self, n_days=120, per_day=6, win=0.62, price=-110, missing_every=0, lv=1.0):
        rows, k = [], 0
        rng = np.random.default_rng(1)
        for d in pd.date_range("2026-11-02", periods=n_days):
            for j in range(per_day):
                k += 1
                r = "W" if rng.random() < win else "L"
                odds = np.nan if missing_every and k % missing_every == 0 else price
                rows.append(bet(bet_id=f"{d:%Y-%m-%d}|{k}|spread|home", date=f"{d:%Y-%m-%d}", game_id=k, home_id=k,
                                away_id=100000 + k, logged_at=f"{d - pd.Timedelta(hours=6):%Y-%m-%dT%H:%M:%S}+00:00",
                                odds=odds, result=r, status="settled"))
        b = pd.DataFrame(rows)
        # strict closes for every signal: lv points of line value
        obs = []
        for _, r in b.iterrows():
            tip = pd.Timestamp(r["date"] + "T23:00:00Z")
            t = tip - pd.Timedelta(minutes=5)
            gk = f"{r['date']}|{r['home_id']}|{r['away_id']}"
            obs.append({"poll_id": "p", "observed_at": t.isoformat(), "source": "oddsapi", "event_id": "e",
                        "game_key": gk, "start": tip.isoformat(), "book": "DraftKings", "market": "spread",
                        "side": "home", "line": r["line"] - lv + rng.choice([-1.0, 0.0, 1.0]), "price": -110,
                        "source_updated_at": (t - pd.Timedelta(seconds=20)).isoformat(), "status": "available"})
        return b, pd.DataFrame(obs)

    def run_eval(self, b, obs, today="2027-03-20", through="2027-03-14"):
        return fe.evaluate(through=through, today=today, bets=b, obs=obs, closing=EMPTY_CLOSING, alerts=ALERTS.iloc[0:0],
                           signal_log=pd.DataFrame(columns=["bet_id"]), accepted=pd.DataFrame(columns=["bet_id", "line", "odds"]),
                           history=[])

    def test_missing_prices_never_enter_confirmatory_roi(self):
        b = pd.DataFrame([bet(bet_id="x1", odds=np.nan, result="W", status="settled"),
                          bet(bet_id="x2", game_id=2, odds=-110.0, result="L", status="settled", logged_at="2026-11-10T19:00:00+00:00")])
        out = self.run_eval(b, pd.DataFrame(columns=list(ob(0))), today="2026-11-20", through="2026-11-19")
        self.assertEqual(out["spread"]["E2: ROI at recorded prices (units per signal)"]["estimate"], -1.0)
        self.assertEqual(out["spread"]["counts"]["recorded-price coverage among decided"], 0.5)
        self.assertEqual(out["spread"]["ROI sensitivities for missing prices (never confirmatory)"]["missing at -110 (hypothetical)"]["estimate"],
                         round((100 / 110 - 1) / 2, 4))

    def test_interim_read_is_descriptive_only(self):
        b, obs = self.season()
        out = self.run_eval(b, obs, today="2027-01-15", through="2027-01-14")
        self.assertTrue(out["read"].startswith("descriptive"))
        self.assertTrue(out["spread"]["verdict"].startswith("none"))
        self.assertNotIn("z", out["spread"]["E2: ROI at recorded prices (units per signal)"])
        self.assertNotIn("E1 verdict", out["spread"])

    def test_final_read_supported_and_coverage_gate(self):
        b, obs = self.season()
        out = self.run_eval(b, obs)
        self.assertEqual(out["spread"]["verdict"], "supported", out["spread"])
        b2, obs2 = self.season(missing_every=10)      # 90% recorded-price coverage
        out2 = self.run_eval(b2, obs2)
        self.assertTrue(out2["spread"]["E2 verdict"].startswith("inconclusive (recorded-price coverage"))
        self.assertEqual(out2["spread"]["verdict"], "inconclusive")

    def test_final_read_contradicted(self):
        b, obs = self.season(win=0.40, lv=-1.0)
        out = self.run_eval(b, obs)
        self.assertEqual(out["spread"]["verdict"], "contradicted")

    def test_final_read_not_before_the_fixed_date(self):
        b, obs = self.season()
        out = self.run_eval(b, obs, today="2027-03-15")
        self.assertTrue(out["read"].startswith("descriptive"))

    def test_z_is_bootstrap_mean_over_bootstrap_se(self):
        r = fe.boot([1.0, 2.0, 3.0, 4.0], ["a", "b", "c", "d"])
        self.assertAlmostEqual(r["z"], r["boot_mean"] / r["se"])


class Versions(unittest.TestCase):
    def test_immutability_flags_a_changed_or_deleted_signal(self):
        v1 = pd.DataFrame([bet(bet_id="s1", logged_at="2026-11-01T12:00:00+00:00"),
                           bet(bet_id="s2", logged_at="2026-11-01T12:00:00+00:00")])
        v2 = v1.copy()
        v2.loc[0, "line"] = -2.5                 # a signal field rewritten
        v2.loc[1, "status"] = "settled"          # settling is allowed
        v3 = v2.iloc[[1]]                        # s1 deleted
        r = fe.immutability([v1, v2, v3])
        self.assertEqual(r["changed"], ["s1"])
        self.assertEqual(r["vanished"], ["s1"])
        self.assertEqual(fe.immutability([v1, v1.assign(status="settled")])["changed"], [])

    def test_versions_are_separated(self):
        old = fe.VERSIONS["v1"]["end"]
        try:
            fe.VERSIONS["v1"]["end"] = pd.Timestamp("2027-01-16T00:00:00Z")
            b = pd.DataFrame([bet(bet_id="early", date="2027-01-10", logged_at="2027-01-10T12:00:00+00:00"),
                              bet(bet_id="late", date="2027-01-20", logged_at="2027-01-20T12:00:00+00:00")])
            s, status = fe.load_signals("v1", None, b)
            self.assertEqual(s["bet_id"].tolist(), ["early"])      # a v2 signal in the live log is never v1
            self.assertTrue(status.startswith("interrupted"))
        finally:
            fe.VERSIONS["v1"]["end"] = old
        b = pd.DataFrame([bet(bet_id="pre", logged_at="2026-10-26T19:00:00+00:00")])
        self.assertEqual(len(fe.load_signals("v1", None, b)[0]), 0)  # pre-freeze signals are not v1

    def test_frozen_constants_match_the_frozen_card(self):
        import subprocess
        src = subprocess.run(["git", "-C", fe.ROOT, "show", f"{fe.FREEZE_COMMIT}:cbb/run_day.py"], capture_output=True,
                             text=True).stdout
        if not src:
            self.skipTest("git history unavailable")
        self.assertIn('WIN_PROB = {"spread": (0.0255, 0.58), "total": (0.014, 0.565)}', src)
        self.assertIn("MIN_EV = 0.02 ", src)
        self.assertIn('SPREAD_CALLS = [(2.5, "BET", 1.0)]', src)
        self.assertIn('TOTAL_CALLS = [(3.0, "BET", 1.0)]', src)
        self.assertEqual(fe.WIN_PROB_V1, {"spread": (0.0255, 0.58), "total": (0.014, 0.565)})
        self.assertEqual((fe.MIN_EV_V1, fe.EDGE_V1), (0.02, {"spread": 2.5, "total": 3.0}))


class QuoteLogger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved = {k: getattr(quotelog, k) for k in ("ROOT", "LINES", "POLLS", "OBS_DIR", "SIGNALS", "ALERTS")}
        quotelog.ROOT = self.tmp
        quotelog.LINES = os.path.join(self.tmp, "lines")
        quotelog.POLLS = os.path.join(quotelog.LINES, "polls.csv")
        quotelog.OBS_DIR = os.path.join(quotelog.LINES, "obs")
        quotelog.SIGNALS = os.path.join(self.tmp, "bets", "signal_log.csv")
        quotelog.ALERTS = os.path.join(self.tmp, "bets", "alert_log.csv")
        quotelog.LOGGED.clear()
        os.makedirs(os.path.join(self.tmp, "bets"))
        os.makedirs(quotelog.LINES)
        pd.DataFrame([bet(date="2026-11-10", logged_at=(T0 - pd.Timedelta(minutes=1)).isoformat())]).to_csv(
            os.path.join(self.tmp, "bets", "bets.csv"), index=False)
        pd.DataFrame([{"sgo_event": "e", "book": "DraftKings", "start": TIP.isoformat(), "home_id": 10, "away_id": 20,
                       "date": "2026-11-10", "pulled_at": T0.isoformat()}]).to_csv(os.path.join(quotelog.LINES, "closing.csv"), index=False)
        ALERTS.to_csv(quotelog.ALERTS, index=False)

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(quotelog, k, v)
        quotelog.LOGGED.clear()
        shutil.rmtree(self.tmp)

    def test_watch_window_from_alert_and_before_tip(self):
        at = lambda m: GK in quotelog.watched_games(T0 + pd.Timedelta(minutes=m))
        self.assertTrue(at(1) and at(80) and at(95))
        self.assertFalse(at(96) or at(200))                       # between the alert window and the tip window
        self.assertTrue(at((TIP - T0).total_seconds() / 60 - 20) and at((TIP - T0).total_seconds() / 60 - 1))
        self.assertFalse(at((TIP - T0).total_seconds() / 60))     # stops at the tip

    def test_absent_rows_and_generating_quote(self):
        t = T0 + pd.Timedelta(minutes=5)
        rows = [quotelog.observation("oddsapi", "e", TIP.isoformat(), 10, 20, bk, "spread", sd, -3 if sd == "home" else 3,
                                     -110, t.isoformat(), t, "available") for bk in ("DraftKings", "Caesars") for sd in ("home", "away")]
        rows = rows[:-1]                                            # Caesars away missing
        n = quotelog.observations(rows, "p1", t)
        self.assertEqual(n, 8)                                      # 3 seen + 5 absent (Caesars away, both totals x2)
        o = quotelog.read_obs()
        self.assertEqual(set(o.loc[o["status"] == "absent", "book"] + o.loc[o["status"] == "absent", "side"]),
                         {"Caesarsaway", "DraftKingsover", "DraftKingsunder", "Caesarsover", "Caesarsunder"})
        self.assertEqual(quotelog.observations(rows, "p1", t), 0)   # the same poll is never logged twice
        q = quotelog.generating_quote([(rows, "p1", t)], GK, "DraftKings", "spread", "home")
        self.assertEqual((q["line"], q["poll_id"]), (-3, "p1"))

    def test_compact_keeps_every_row(self):
        os.makedirs(quotelog.OBS_DIR)
        p = os.path.join(quotelog.OBS_DIR, "2026-10-01.csv")
        pd.DataFrame([ob(1), ob(2)]).drop(columns="log").to_csv(p, index=False)
        quotelog.compact()
        self.assertFalse(os.path.exists(p))
        self.assertEqual(len(quotelog.read_obs()), 2)


if __name__ == "__main__":
    unittest.main()
