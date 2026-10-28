"""C2/A1 prospective test (LOG.md): v1's totals minus a frozen 0.61 points (the median correction; the 2026 fit's
training-residual median), scored after the fact on 2026-27 from the files the card already writes. Reuses the E2
scorer's reconstruction of the card's v1 totals read-only (research/quant/e2_shadow.build); E2 itself is untouched.

    python -m research.quant2.c2_shadow       # -> out/c2_shadow.txt
"""
from __future__ import annotations

import os

import numpy as np

from research.quant.common import boot
from research.quant.e2_shadow import _days, build
from research.quant2.common import OUT

SHIFT = -0.61          # frozen Oct 28, 2026; never refit during the test


def main() -> None:
    if not _days():
        print("no 2026-27 feature files yet")
        return
    d = build().dropna(subset=["points"])
    L = [f"2026-27 final games: {len(d)}"]
    if len(d) >= 2:
        d = d.assign(c2_total=d["v1_total"] + SHIFT)
        g, lo, hi = boot((d["points"] - d["v1_total"]).abs() - (d["points"] - d["c2_total"]).abs(), d["day"])
        r = d["points"] - d["v1_total"]
        L.append(f"totals MAE v1 {(r).abs().mean():.3f}, C2 {(d['points'] - d['c2_total']).abs().mean():.3f}, gain {g:+.4f} "
                 f"[{lo:+.4f}, {hi:+.4f}]; v1 residual mean {r.mean():+.2f}, median {r.median():+.2f}; "
                 f"games over the v1 forecast {100 * (r > 0).mean():.1f}%")
        for tag, col in (("v1", "v1_total"), ("C2", "c2_total")):
            x = d.dropna(subset=["open_total"])
            e = x[col] - x["open_total"]
            p = x[e.abs() >= 3]
            cov = np.sign(e[e.abs() >= 3]) * (p["points"] - p["open_total"])
            w = cov[cov != 0] > 0
            L.append(f"opener totals, edge 3+, {tag}: {len(w)} plays, win% {100 * w.mean():.1f}, overs {100 * (e[e.abs() >= 3] > 0).mean():.0f}%"
                     if len(w) else f"{tag}: no plays")
    txt = "\n".join(L) + "\n"
    open(os.path.join(OUT, "c2_shadow.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
