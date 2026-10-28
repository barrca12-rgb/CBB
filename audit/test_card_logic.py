"""The live cards pass every display rule in audit/card_logic.py (rendered with the current template).

    python -m pytest -q audit/test_card_logic.py
"""
import shutil
import subprocess
import sys

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node + playwright")
def test_every_card_passes_the_display_rules():
    r = subprocess.run([sys.executable, "-m", "audit.card_logic"], capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stdout + r.stderr
