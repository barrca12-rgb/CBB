"""SGO ends after Nov 25, 2026: an SGO error (expired key, HTTP 401/403, timeout) must not block the card's line pull
when The Odds API is due (it is on every run: ODDS_API_EVERY_RUN in update.yml). The pull falls back to The Odds API
alone, still writes closing.csv and openers.csv, and logs the SGO poll as an error."""
import os
import shutil

import pandas as pd
import pytest

from cbb import odds, odds_api, quotelog

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _oa_frame() -> pd.DataFrame:
    c = pd.read_csv(os.path.join(ROOT, "lines", "closing.csv"))
    c = c[c["sgo_event"].astype(str).str.startswith("oa:")].tail(20)
    return c.drop(columns=["date", "pulled_at"]).reset_index(drop=True)


def test_card_pull_survives_sgo_failure(tmp_path, monkeypatch):
    lines = tmp_path / "lines"
    lines.mkdir()
    for f in ("closing.csv", "openers.csv"):
        shutil.copy(os.path.join(ROOT, "lines", f), lines / f)
    for mod in (odds, quotelog):
        monkeypatch.setattr(mod, "LINES", str(lines))
    monkeypatch.setattr(odds, "SGO_LAST", str(lines / "sgo_last_pull.txt"))
    monkeypatch.setattr(quotelog, "POLLS", str(lines / "polls.csv"))
    monkeypatch.setattr(quotelog, "OBS_DIR", str(lines / "obs"))

    def sgo_dead(*a, **k):
        raise RuntimeError("HTTP Error 401: Unauthorized (subscription ended)")
    monkeypatch.setattr(odds, "fetch", sgo_dead)
    frame = _oa_frame()

    def oa_fetch(*a, **k):
        oa_fetch.observed_at, oa_fetch.events, oa_fetch.observations = pd.Timestamp.now(tz="UTC"), len(frame), []
        oa_fetch.last_cost, oa_fetch.usage, oa_fetch.unmatched = 3, {"remaining": 70000}, []
        return frame.copy()
    monkeypatch.setattr(odds_api, "fetch", oa_fetch)
    monkeypatch.setattr(odds_api, "due", lambda: True)

    out = odds.pull()
    assert len(out) == len(frame)                                  # The Odds API lines come through alone
    polls = pd.read_csv(lines / "polls.csv")
    assert (polls["source"] == "sgo").any() and (polls.loc[polls["source"] == "sgo", "status"] == "error").all()
    assert (polls["source"] == "oddsapi").any()
    assert "0 SGO" in (lines / "last_pull.txt").read_text()
