"""Barttorvik and KenPom: a missing answer for a recent date is asked again, not cached as final (approved by Chad
Oct 30; MODEL_FREEZE.md). Old dates and files that exist behave exactly as before, so every backtest and replay is
byte-identical (checked on the 2025-11-15, 2026-01-17 and 2026-03-01 replays; here on the cached files).

    python -m pytest -q audit/test_source_retry.py
"""
import gzip
import io
import json
import os
import time

import pandas as pd
import pytest

from cbb import barttorvik, kenpom

TODAY = pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize()


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _rows():
    r = [0] * 45
    r[1], r[4], r[6], r[44] = "Duke", 120.0, 95.0, 70.0
    return [r]


@pytest.fixture
def bt(tmp_path, monkeypatch):
    monkeypatch.setattr(barttorvik, "CACHE", str(tmp_path))
    calls = []

    def fake(req, timeout=60):
        calls.append(req.full_url)
        return _Resp(gzip.compress(json.dumps(_rows()).encode()))
    monkeypatch.setattr(barttorvik.urllib.request, "urlopen", fake)
    return tmp_path, calls


def _empty(path, age_s):
    pd.DataFrame(columns=["team", "adj_oe", "adj_de", "adj_tempo", "espn_id"]).to_parquet(path)
    os.utime(path, (time.time() - age_s, time.time() - age_s))


def test_recent_missing_file_is_asked_again_hourly(bt):
    tmp, calls = bt
    day = TODAY - pd.Timedelta(days=1)
    p = tmp / f"{day:%Y%m%d}.parquet"
    _empty(p, 600)                                   # cached as missing 10 minutes ago: not asked yet
    assert barttorvik.snapshot(day) is None and calls == []
    _empty(p, 7200)                                  # two hours ago: asked again, and now it is posted
    t = barttorvik.snapshot(day)
    assert len(calls) == 1 and t is not None and list(t["team"]) == ["Duke"]
    assert len(pd.read_parquet(p)) == 1              # cached once posted


def test_old_missing_file_is_never_asked_again(bt):
    tmp, calls = bt
    day = TODAY - pd.Timedelta(days=barttorvik.RETRY_DAYS + 5)
    _empty(tmp / f"{day:%Y%m%d}.parquet", 10 ** 7)
    assert barttorvik.snapshot(day) is None and calls == []


def test_cached_files_read_without_network(monkeypatch):
    """Every cached file with data is returned from the cache, unchanged, with no request (sample of the real cache)."""
    files = sorted(f for f in os.listdir(barttorvik.CACHE) if f.endswith(".parquet")) if os.path.isdir(barttorvik.CACHE) else []
    if not files:
        pytest.skip("no Barttorvik cache in this checkout")
    monkeypatch.setattr(barttorvik.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    for f in files[::25]:
        raw = pd.read_parquet(os.path.join(barttorvik.CACHE, f))
        day = pd.Timestamp(f[:8])
        if len(raw) == 0 and barttorvik._recent(day):
            continue                                 # recent and missing: the one case that changed
        t = barttorvik.snapshot(day)
        assert (t is None and len(raw) == 0) or t.equals(raw)


def test_kenpom_empty_answer_for_today_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(kenpom, "CACHE", str(tmp_path))
    answers = [[], [{"Home": "Duke", "Visitor": "UNC"}]]
    monkeypatch.setattr(kenpom.urllib.request, "urlopen", lambda req, timeout=60: _Resp(json.dumps(answers.pop(0)).encode()))
    d = f"{TODAY:%Y-%m-%d}"
    assert kenpom.get("fanmatch", d=d) == []                       # 7:37 am: not published yet
    assert not os.listdir(tmp_path)                                 # ... and not cached
    assert kenpom.get("fanmatch", d=d) == [{"Home": "Duke", "Visitor": "UNC"}]   # later run: published, cached
    assert os.listdir(tmp_path) == [f"endpoint-fanmatch_d-{d}.json"]


def test_kenpom_old_and_undated_answers_cache_as_before(tmp_path, monkeypatch):
    monkeypatch.setattr(kenpom, "CACHE", str(tmp_path))
    monkeypatch.setattr(kenpom.urllib.request, "urlopen", lambda req, timeout=60: _Resp(b"[]"))
    kenpom.get("fanmatch", d="2025-07-04")                          # an old empty date stays cached as empty
    kenpom.get("archive", preseason="true", y=2027)
    assert sorted(os.listdir(tmp_path)) == ["endpoint-archive_preseason-true_y-2027.json", "endpoint-fanmatch_d-2025-07-04.json"]


def _fetcher():
    import importlib.util
    spec = importlib.util.spec_from_file_location("fetch_barttorvik", os.path.join(os.path.dirname(barttorvik.__file__), "..", "local", "fetch_barttorvik.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _rows_many():
    out = []
    for k, (team, oe, de, tempo) in enumerate([("Duke", 120.63523723471697, 91.26906206401344, 70.13581845268743),
                                                ("Florida", 120.431960949121, 93.50930117438779, 74.11147845268742)]):
        r = [0] * 45
        r[1], r[4], r[6], r[44] = team, oe, de, tempo
        out.append(r)
    return out


def test_repo_copy_from_chads_machine_matches_a_direct_download(tmp_path, monkeypatch):
    """The fetcher's CSV, read by the card, gives exactly the frame a direct download would; no request is made."""
    import datetime as dt
    f = _fetcher()
    monkeypatch.setattr(f, "OUT", str(tmp_path / "repo"))
    monkeypatch.setattr(f, "PAUSE", 0)
    day = dt.date(2026, 11, 2)
    served = {"20261102": _rows_many()}                                  # Nov 1 and Oct 31: not posted (404)

    def fake(req, timeout=60):
        d = req.full_url.split("/")[-1][:8]
        if d not in served:
            raise f.urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)
        return _Resp(gzip.compress(json.dumps(served[d]).encode()))
    monkeypatch.setattr(f.urllib.request, "urlopen", fake)
    assert [os.path.basename(p) for p in f.fetch(day)] == ["20261102.csv"]
    assert f.fetch(day) == []                                             # already there: not asked again

    # direct download of the same rows through the card's own path, into an empty cache
    monkeypatch.setattr(barttorvik, "CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(barttorvik, "REPO", str(tmp_path / "none"))
    monkeypatch.setattr(barttorvik.urllib.request, "urlopen", lambda req, timeout=60: _Resp(gzip.compress(json.dumps(_rows_many()).encode())))
    direct = barttorvik.snapshot(pd.Timestamp("2026-11-02"))

    # the card reading the repo copy, with a stale "missing" cache entry and no network at all
    monkeypatch.setattr(barttorvik, "CACHE", str(tmp_path / "cache2"))
    os.makedirs(tmp_path / "cache2")
    _empty(tmp_path / "cache2" / "20261102.parquet", 60)
    monkeypatch.setattr(barttorvik, "REPO", str(tmp_path / "repo"))
    monkeypatch.setattr(barttorvik.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    from_repo = barttorvik.snapshot(pd.Timestamp("2026-11-02"))
    pd.testing.assert_frame_equal(from_repo.reset_index(drop=True), direct.reset_index(drop=True))


def test_a_non_ratings_answer_never_stops_the_card(bt, monkeypatch):
    """Oct 30 18:20 UTC: Barttorvik answered a recent date with a page that was not JSON (200), and the card crashed."""
    tmp, calls = bt
    monkeypatch.setattr(barttorvik, "REPO", str(tmp / "none"))
    monkeypatch.setattr(barttorvik.urllib.request, "urlopen", lambda req, timeout=60: _Resp(b"\n<!doctype html><title>Just a moment...</title>"))
    day = TODAY - pd.Timedelta(days=1)
    assert barttorvik.snapshot(day) is None                         # treated as missing
    assert len(pd.read_parquet(tmp / f"{day:%Y%m%d}.parquet")) == 0  # marked missing: asked again at most hourly
    old = TODAY - pd.Timedelta(days=barttorvik.RETRY_DAYS + 30)
    assert barttorvik.snapshot(old) is None and not (tmp / f"{old:%Y%m%d}.parquet").exists()   # old date: not cached
    monkeypatch.setattr(barttorvik, "before", lambda day: (_ for _ in ()).throw(RuntimeError("boom")))
    g = pd.DataFrame([{"game_id": 1, "date": TODAY, "home_id": 150, "away_id": 57, "neutral": False}])
    assert barttorvik.predict(g).empty                               # any other failure: KenPom fills, no crash
