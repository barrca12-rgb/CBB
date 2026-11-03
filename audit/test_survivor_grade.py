"""Survivor grading writes W / L / void into a picks file whose result column is still empty (Nov 3, 03:30 UTC run
failed: "Invalid value 'W' for dtype 'float64'").

    python -m pytest -q audit/test_survivor_grade.py
"""
import numpy as np
import pandas as pd

from cbb import survivor


def test_grades_into_an_empty_result_column(tmp_path, monkeypatch):
    f = tmp_path / "picks.csv"
    pd.DataFrame([{"entry": "a", "date": "2026-11-02", "team_id": 5, "team": "X", "game_id": 1, "opponent": "Y",
                   "recorded_at": "", "result": np.nan},
                  {"entry": "b", "date": "2026-11-02", "team_id": 6, "team": "Y", "game_id": 1, "opponent": "X",
                   "recorded_at": "", "result": np.nan}]).to_csv(f, index=False)
    monkeypatch.setattr(survivor, "PICKS", str(f))
    s = pd.DataFrame([{"game_id": 1, "canceled": False, "completed": True, "winner_id": 5}])
    assert survivor.grade(survivor.load_picks(), s)["result"].tolist() == ["W", "L"]
