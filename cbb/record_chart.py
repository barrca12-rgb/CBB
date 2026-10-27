"""Weekly record chart for @OffTheGlassHQ: two 1600x900 PNGs a week, drawn only from bets/bets.csv (whose CLV the
grader computes from lines/closing.csv), the same file the record page and the forward test read, so the chart and
the page can never disagree. Reads and displays only: no pick, number, rule, stake, log or grading change.

  <date>-clv.png    cumulative closing-line value by play, season to date, spreads and totals as separate lines,
                    under a row of six stat tiles
  <date>-units.png  units by week (bars, every week the same color) with cumulative units (line)

<date> is the Sunday the chart runs through. Every non-void play counts (cohort A, bet or not); voids are counted
in the footer and left out of the series. Always season to date from the freeze; never a chosen window. Posting to
X is manual.

    python -m cbb.record_chart [--through YYYY-MM-DD] [--bets PATH] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess

import numpy as np
import pandas as pd

from . import tracker

ROOT = tracker.ROOT
OUT = os.path.join(ROOT, "site", "record", "weekly")
FONTS = os.path.join(os.path.dirname(__file__), "fonts")
FREEZE = os.path.join(ROOT, "MODEL_FREEZE.md")
ANN = os.path.join(ROOT, "bets", "announcements.json")
SITE = "barrca12-rgb.github.io/CBB/record.html"
# brand palette (site/BRAND.md)
CREAM, SURFACE, LINE, NAVY, MUTED, FAINT, ORANGE, GREY = ("#fbf6ea", "#ffffff", "#ebe1cd", "#0a2c49", "#56627a",
                                                          "#8a93a3", "#fd6c0f", "#9aa2ae")
SMALL_N = 50


def _fonts():
    from matplotlib import font_manager
    for f in os.listdir(FONTS):
        if f.endswith(".ttf"):
            font_manager.fontManager.addfont(os.path.join(FONTS, f))


def last_sunday(today: pd.Timestamp | None = None) -> pd.Timestamp:
    """The most recent Sunday on or before today (ET): a Monday run charts through the day before."""
    t = pd.Timestamp(today) if today is not None else pd.Timestamp.now(tz="America/New_York").tz_localize(None)
    t = t.normalize()
    return t - pd.Timedelta(days=(t.weekday() + 1) % 7)


def clustered_mean(x: pd.Series, dates: pd.Series) -> tuple[float, float]:
    """Mean and its date-clustered standard error."""
    x = x.astype(float)
    n = len(x)
    if not n:
        return np.nan, np.nan
    m = float(x.mean())
    if n < 2:
        return m, np.nan
    g = (x - m).groupby(dates.to_numpy()).sum()
    return m, float(np.sqrt((g ** 2).sum()) / n)


def stats(b: pd.DataFrame, through: pd.Timestamp) -> dict:
    """Everything on the chart, from the bet log as of `through` (plays dated on or before it)."""
    b = b[pd.to_datetime(b["date"]) <= through]
    voids = int((b["status"] == "void").sum())
    a = b[b["status"] != "void"].copy()                     # cohort A: every signal, bet or not
    a = a.sort_values(["date", "logged_at"])
    s = a[a["status"] == "settled"]
    w, l, p = int((s["result"] == "W").sum()), int((s["result"] == "L").sum()), int((s["result"] == "P").sum())
    flat = (s["profit"].astype(float) / s["stake"].astype(float).replace(0, np.nan).fillna(1.0)).fillna(0.0)
    out = {"through": through, "logged": len(a), "voids": voids, "settled": len(s), "w": w, "l": l, "p": p,
           "units": float(flat.sum()), "series": {}, "tiles": {}}
    c = s.dropna(subset=["clv_pts"])
    for mk in ("spread", "total"):
        x = c[c["market"] == mk]
        m, se = clustered_mean(x["clv_pts"], x["date"])
        out["tiles"][mk] = {"mean": m, "se": se, "n": len(x)}
        out["series"][mk] = np.r_[0.0, x["clv_pts"].astype(float).cumsum().to_numpy()]
    v = c["clv_pts"].astype(float)
    out["moved"] = {"for": int((v > 0).sum()), "flat": int((v == 0).sum()), "against": int((v < 0).sum()), "n": len(v)}
    wk = s.assign(week=pd.to_datetime(s["date"]).dt.to_period("W-SUN").dt.end_time.dt.normalize(), u=flat)
    weeks = pd.period_range(pd.to_datetime(a["date"]).min() if len(a) else through, through, freq="W-SUN")
    out["weekly"] = wk.groupby("week")["u"].sum().reindex([w_.end_time.normalize() for w_ in weeks], fill_value=0.0)
    return out


def version() -> tuple[str, str]:
    """('v1, frozen <commit>', 'Model unchanged since <date>')."""
    commit = "?"
    if os.path.exists(FREEZE):
        for line in open(FREEZE):
            if line.startswith("Frozen at commit:"):
                commit = line.split(":", 1)[1].strip()[:7]
    changes = []
    if os.path.exists(ANN):
        changes = [x["date"] for x in json.load(open(ANN)) if str(x.get("text", "")).startswith(("Model change", "Rule change"))]
    since = pd.Timestamp(max(changes)) if changes else pd.Timestamp("2026-10-26")
    return f"Model v1, frozen {commit}", f"Model unchanged since {since:%b} {since.day}, {since:%Y}"


def _footer(fig, st: dict) -> None:
    t = st["through"]
    fig.text(0.04, 0.035, f"Through {t:%a %b} {t.day}, {t:%Y}  ·  every play alerted and timestamped before tip  ·  "
             f"bets/bets.csv, OpenTimestamps-stamped", fontsize=13, color=MUTED, family="Inter")


def _title(fig, text: str, y: float) -> None:
    fig.text(0.04, 0.93, "OFF THE GLASS", fontsize=30, color=NAVY, family="Graduate", va="center")
    fig.text(0.96, 0.93, "@OffTheGlassHQ", fontsize=19, color=NAVY, family="Inter", weight="bold", ha="right", va="center")
    fig.text(0.04, y, text.upper(), fontsize=14, color=NAVY, family="Inter", weight="heavy")
    fig.add_artist(__import__("matplotlib").lines.Line2D([0.04, 0.96], [0.885, 0.885], color=ORANGE, lw=3))


def _fmt(x: float, d: int = 2, plus: bool = True) -> str:
    return "–" if x is None or not np.isfinite(x) else (f"{x:+.{d}f}" if plus else f"{x:.{d}f}")


def tiles(st: dict) -> list[tuple[str, str, str]]:
    """(label, big number, small line) for the six tiles."""
    rec = f"{st['w']}-{st['l']}-{st['p']}"
    wl = st["w"] + st["l"]
    winline = f"n {st['settled']} settled · n too small" if st["settled"] < SMALL_N else f"n {st['settled']} · {st['w'] / wl:.1%}"
    sp, to, mv = st["tiles"]["spread"], st["tiles"]["total"], st["moved"]
    se = lambda t: f"± {t['se']:.2f} · n {t['n']}" if np.isfinite(t["se"]) else f"n {t['n']}"
    share = f"{mv['for'] / mv['n']:.0%}" if mv["n"] else "–"
    return [("PLAYS LOGGED", str(st["logged"]), "every signal, bet or not"),
            ("RECORD", rec, winline),
            ("UNITS", _fmt(st["units"]), f"flat 1u · n {st['settled']}"),
            ("CLV SPREADS", _fmt(sp["mean"]), se(sp)),
            ("CLV TOTALS", _fmt(to["mean"]), se(to)),
            ("CLOSE MOVED FOR", share, f"{mv['for']} / {mv['flat']} / {mv['against']} · n {mv['n']}")]


def draw_clv(st: dict, path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    _fonts()
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=CREAM)
    _title(fig, "Cumulative closing-line value by play, season to date", 0.655)
    # tiles
    x0, y0, w, h, gap = 0.04, 0.70, (0.92 - 5 * 0.012) / 6, 0.15, 0.012
    for i, (lab, big, small) in enumerate(tiles(st)):
        x = x0 + i * (w + gap)
        fig.add_artist(FancyBboxPatch((x, y0), w, h, boxstyle="round,pad=0,rounding_size=0.008", transform=fig.transFigure,
                                      facecolor=SURFACE, edgecolor=LINE, lw=1.2))
        fig.add_artist(matplotlib.lines.Line2D([x + 0.004, x + w - 0.004], [y0 + h, y0 + h], color=NAVY, lw=3))
        fig.text(x + 0.012, y0 + h - 0.03, lab, fontsize=11.5, color=MUTED, family="Inter", weight="bold")
        fig.text(x + 0.012, y0 + 0.058, big, fontsize=30 if len(big) < 8 else 24, color=NAVY, family="Inter", weight="heavy")
        fig.text(x + 0.012, y0 + 0.018, small, fontsize=11.5, color=FAINT, family="Inter")
    # chart
    ax = fig.add_axes([0.07, 0.15, 0.89, 0.47], facecolor=CREAM)
    for mk, color, lab in (("spread", ORANGE, "Spreads"), ("total", NAVY, "Totals")):
        y = st["series"][mk]
        ax.plot(np.arange(len(y)), y, color=color, lw=3, label=f"{lab}  {_fmt(y[-1])} pts after {len(y) - 1} plays",
                solid_capstyle="round", zorder=3)
    ax.axhline(0, color=GREY, lw=1.5, zorder=2)
    n = max(len(st["series"]["spread"]), len(st["series"]["total"]))
    ax.set_xlim(0, max(n - 1, 10))
    lo = min(0, *(s.min() for s in st["series"].values()))
    hi = max(0, *(s.max() for s in st["series"].values()))
    pad = max((hi - lo) * 0.12, 1.0)
    ax.set_ylim(lo - pad, hi + pad)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(LINE)
    ax.tick_params(colors=MUTED, labelsize=12)
    for t in ax.get_xticklabels() + ax.get_yticklabels():
        t.set_family("Inter")
    ax.set_xlabel("Play number (graded plays with a closing line)", fontsize=13, color=MUTED, family="Inter")
    ax.set_ylabel("Cumulative points vs the close", fontsize=13, color=MUTED, family="Inter")
    ax.grid(axis="y", color=LINE, lw=0.8, zorder=1)
    leg = ax.legend(loc="upper left", frameon=False, prop={"family": "Inter", "size": 13})
    for t in leg.get_texts():
        t.set_color(NAVY)
    if n <= 1:
        ax.text(0.5, 0.75, "No graded plays yet", transform=ax.transAxes, ha="center", va="center", fontsize=16,
                color=FAINT, family="Inter")
    _footer(fig, st)
    fig.savefig(path, dpi=100, facecolor=CREAM)
    plt.close(fig)


def draw_units(st: dict, path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _fonts()
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=CREAM)
    _title(fig, "Units by week, season to date (flat 1 unit)", 0.84)
    wk = st["weekly"]
    ax = fig.add_axes([0.07, 0.17, 0.89, 0.6], facecolor=CREAM)
    x = np.arange(len(wk))
    ax.bar(x, wk.to_numpy(), color=NAVY, width=0.6, zorder=3, label="Units that week")
    ax.plot(x, wk.cumsum().to_numpy(), color=ORANGE, lw=3, marker="o", ms=7, zorder=4, label=f"Cumulative  {_fmt(st['units'])} u")
    ax.axhline(0, color=GREY, lw=1.5, zorder=2)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{d:%b} {d.day}" for d in wk.index], fontsize=12, color=MUTED, family="Inter")
    lo, hi = min(0, wk.min(), wk.cumsum().min()), max(0, wk.max(), wk.cumsum().max())
    pad = max((hi - lo) * 0.15, 1.0)
    ax.set_ylim(lo - pad, hi + pad)
    ax.set_xlim(-0.6, max(len(wk), 6) - 0.4)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(LINE)
    ax.tick_params(colors=MUTED, labelsize=12)
    for t in ax.get_yticklabels():
        t.set_family("Inter")
    ax.set_xlabel("Week ending (Sunday)", fontsize=13, color=MUTED, family="Inter")
    ax.set_ylabel("Units", fontsize=13, color=MUTED, family="Inter")
    ax.grid(axis="y", color=LINE, lw=0.8, zorder=1)
    leg = ax.legend(loc="upper left", frameon=False, prop={"family": "Inter", "size": 13})
    for t in leg.get_texts():
        t.set_color(NAVY)
    fig.text(0.96, 0.84, f"Record {st['w']}-{st['l']}-{st['p']} · {st['settled']} graded of {st['logged']} logged",
             fontsize=14, color=NAVY, family="Inter", weight="semibold", ha="right")
    _footer(fig, st)
    fig.savefig(path, dpi=100, facecolor=CREAM)
    plt.close(fig)


def index(out: str) -> list[str]:
    """Weeks with charts, newest first (the record page reads this)."""
    return sorted({f[:10] for f in os.listdir(out) if f.endswith("-clv.png")}, reverse=True) if os.path.isdir(out) else []


def write(through: pd.Timestamp | None = None, bets: str | None = None, out: str = OUT) -> dict:
    through = pd.Timestamp(through) if through is not None else last_sunday()
    b = pd.read_csv(bets) if bets else tracker.load()
    st = stats(b, through)
    os.makedirs(out, exist_ok=True)
    tag = f"{through:%Y-%m-%d}"
    draw_clv(st, os.path.join(out, f"{tag}-clv.png"))
    draw_units(st, os.path.join(out, f"{tag}-units.png"))
    with open(os.path.join(out, "index.json"), "w") as fh:
        json.dump({"weeks": index(out)}, fh)
    return st


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--through")
    ap.add_argument("--bets")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    st = write(a.through, a.bets, a.out)
    print({k: v for k, v in st.items() if k not in ("series", "weekly")})
