"""The mean-vs-median piece alone: each season's v1 residuals with that season's level bias removed (in hindsight),
then the MAE change from lowering every forecast by 0.61. Diagnosis only; the level removal is not deployable.

    python -m research.quant3.skew     # -> research/quant3/out/skew.txt
"""
from __future__ import annotations

import os

import numpy as np

from research.quant.common import base_frames, fit_predict
from research.quant3.study import OUT, SHIFT, opening_week


def main() -> None:
    train, pred = base_frames()
    v1 = opening_week(fit_predict(train, pred))
    lines = ["season  mean-median  MAE gain from v1-0.61 on level-free residuals"]
    for s in range(2015, 2027):
        x = v1[v1["season"] == s]
        c = (x["points"] - x["final_total"]).to_numpy(float)
        c = c - c.mean()
        # lowering the forecast by 0.61 raises each residual by 0.61
        lines.append(f"{s}  {c.mean() - np.median(c):+.2f}  {np.abs(c).mean() - np.abs(c - SHIFT).mean():+.4f}")
    txt = "\n".join(lines) + "\n"
    open(os.path.join(OUT, "skew.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
