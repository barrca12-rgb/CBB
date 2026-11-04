"""Shared test setup: the complete-ratings rule (protocol v2.6, Appendix D) depends on the wall clock, so it is off
in every test except the ones that switch it on to test it (audit/test_ratings_rule.py)."""
import pytest


@pytest.fixture(autouse=True)
def _no_ratings_rule(monkeypatch):
    from cbb import run_day
    monkeypatch.setattr(run_day, "RATINGS_RULE", False)
