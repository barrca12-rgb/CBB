"""Every date's card is built from the same template with the same sections and controls (Chad, Nov 1: "make sure
all dates have the same set up"), and Novig is no longer shown anywhere on the card.

    python -m pytest -q audit/test_same_layout.py
"""
import json
import os
import re

from cbb import report_html

REPORTS = os.path.join(os.path.dirname(__file__), "..", "reports")
DATA = re.compile(r'<script id="data" type="application/json">.*?</script>', re.S)


def _layout(path: str) -> str:
    """The page with its own data, title and build time taken out: what is left is the layout."""
    s = DATA.sub("", open(path).read())
    s = re.sub(r"<title>.*?</title>", "", s, flags=re.S)
    s = re.sub(r'<meta property="og:title" content="[^"]*">', "", s)
    return re.sub(r'<meta name="otg-built" content="[^"]*">', "", s)


def test_every_date_on_the_site_has_the_same_layout():
    days = json.load(open(os.path.join(REPORTS, "days.json")))["days"]
    pages = [os.path.join(REPORTS, f"cbb_{d}.html") for d in days if os.path.exists(os.path.join(REPORTS, f"cbb_{d}.html"))]
    layouts = {os.path.basename(p): _layout(p) for p in pages}
    first = next(iter(layouts.values()))
    assert all(v == first for v in layouts.values()), [k for k, v in layouts.items() if v != first]


def test_no_novig_on_the_card():
    assert "novig" not in report_html.TEMPLATE.lower()
    assert not hasattr(report_html, "_novig_view")
