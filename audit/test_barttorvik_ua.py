"""Bart Torvik's whitelist (Nov 2): every barttorvik.com request carries the string from the BARTTORVIK_UA_TOKEN
secret in its User-Agent; with no secret set, the request is exactly as before. No network: urlopen is replaced.

    python -m pytest -q audit/test_barttorvik_ua.py
"""
import urllib.error
import urllib.request

import pandas as pd
import pytest

from cbb import barttorvik

PLAIN = barttorvik.UA["User-Agent"]


@pytest.fixture
def seen(monkeypatch, tmp_path):
    monkeypatch.setattr(barttorvik, "CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(barttorvik, "REPO", str(tmp_path / "repo"))
    got = []

    def fake(req, timeout=None):
        got.append(req.get_header("User-agent"))
        raise urllib.error.HTTPError(req.full_url, 403, "refused", {}, None)
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return got


def test_requests_carry_the_whitelist_string_when_the_secret_is_set(seen, monkeypatch):
    monkeypatch.setenv(barttorvik.UA_TOKEN_ENV, "test-token-123")
    barttorvik.snapshot(pd.Timestamp.now().normalize())      # a time-machine file
    barttorvik.current(2027)                                  # the live ratings file
    assert seen == [PLAIN + " test-token-123"] * 2


def test_without_the_secret_requests_are_unchanged(seen, monkeypatch):
    monkeypatch.delenv(barttorvik.UA_TOKEN_ENV, raising=False)
    barttorvik.snapshot(pd.Timestamp.now().normalize())
    barttorvik.current(2027)
    assert seen == [PLAIN] * 2


def test_the_string_is_not_in_the_repo():
    """The whitelist string lives only in the GitHub secret: nothing in cbb/ spells a token."""
    src = open(barttorvik.__file__).read()
    assert "offtheglass" not in src.lower()
