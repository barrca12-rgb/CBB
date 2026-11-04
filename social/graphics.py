"""X graphics for @OffTheGlassHQ: last night's recap and today's top plays (1600x900 PNG + a caption).

Dark box-score style (Chad, Nov 4: "look much less like AI"; picked the dark mock): condensed type, hard rules, every
play listed with its result, no rounded cards, badges or emoji. Every number comes from the official bet log
(bets/bets.csv, main plays only, never band B) and the primary close (cbb/clv_primary.py), the same figures as the
site's record page. Display only: nothing here changes a pick, a number, the bet log or the card.

    python -m social.graphics recap [--date YYYY-MM-DD]   # default: yesterday (ET)   -> out/social/recap_<date>.png/.txt
    python -m social.graphics top   [--date YYYY-MM-DD]   # default: today (ET)       -> out/social/top_<date>.png/.txt

Rendering uses headless Chromium through Node's Playwright (social/render.js).
"""
from __future__ import annotations

import argparse
import base64
import html
import math
import os
import subprocess

import pandas as pd

from cbb import clv_primary, tracker

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "out", "social")
LOGO = os.path.join(ROOT, "site", "assets", "otg-logo-512.png")
HANDLE = "@OffTheGlassHQ"
MINUS = "−"
DASH = "–"

FONTS = ("<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=Anton&family=Barlow+Condensed:wght@500;600;"
         "700;800&family=Barlow:wght@500;600;700&display=swap'>")
CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{width:1600px;height:900px;background:#101317;color:#eef0f2;font-family:Barlow,sans-serif;overflow:hidden;position:relative}
body:before{content:'';position:absolute;inset:0;background:repeating-linear-gradient(90deg,rgba(255,255,255,.018) 0 2px,transparent 2px 6px);pointer-events:none}
.l{position:absolute;left:64px;top:56px;width:500px}
.brand{display:flex;align-items:center;gap:14px;font-family:'Barlow Condensed';font-weight:800;font-size:26px;letter-spacing:.04em;color:#fd6c0f}
.brand img{width:46px;height:46px;display:block}
.day{font-family:'Barlow Condensed';font-weight:700;font-size:40px;margin-top:46px;color:#9aa3ad}
.big{font-family:Anton;font-size:210px;line-height:.92;margin-top:6px}
.big.sm{font-size:150px}
.u{font-family:Anton;font-size:84px;line-height:1;margin-top:14px}
.split{margin-top:40px;font-family:'Barlow Condensed';font-weight:600;font-size:30px;line-height:1.45;color:#c9ced4;border-top:3px solid #eef0f2;padding-top:16px}
.split b{color:#fff;font-weight:800}
.org{color:#fd6c0f} .W{color:#3ccf7e} .L{color:#ff5a4f} .P{color:#9aa3ad}
.rt{position:absolute;left:620px;right:64px;top:62px;display:grid;column-gap:36px}
.r{display:grid;align-items:baseline;column-gap:10px;border-bottom:1px solid #2a2f36}
.m{font-family:'Barlow Condensed';font-weight:800}
.p{font-family:'Barlow Condensed';font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.s{color:#8f98a2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.x{text-align:right;font-family:'Barlow Condensed';font-weight:700}
.more{font-family:'Barlow Condensed';font-weight:600;font-size:20px;color:#8f98a2;margin-top:10px}
.f{position:absolute;left:64px;right:64px;bottom:34px;display:flex;font-family:'Barlow Condensed';font-weight:600;font-size:22px;color:#8f98a2}
.f b{color:#eef0f2} .f .h{margin-left:auto;color:#fd6c0f;font-weight:800}
/* top plays */
.tp{position:absolute;left:620px;right:64px;top:62px}
.tr{display:grid;grid-template-columns:44px 1fr 150px;align-items:center;border-bottom:1px solid #2a2f36;padding:13px 0}
.tr .n{font-family:Anton;font-size:40px;color:#fd6c0f}
.tr .p{font-size:40px;line-height:1.05}
.tr .s{font-size:19px;margin-top:4px;white-space:normal}
.tr .s b{color:#c9ced4;font-weight:600}
.tr .e{text-align:right;font-family:Anton;font-size:44px;line-height:1}
.tr .e small{display:block;font-family:'Barlow Condensed';font-weight:700;font-size:17px;color:#8f98a2;letter-spacing:.06em;margin-top:4px}
"""


def _today_et() -> pd.Timestamp:
    return pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize()


def _num(x: float, d: int = 1) -> str:
    return f"{x:+.{d}f}".rstrip("0").rstrip(".").replace("-", MINUS)


def _units(x: float) -> str:
    return f"{x:+.2f}u".replace("-", MINUS)


def _rec(w: int, l: int, p: int = 0) -> str:
    return f"{w}{DASH}{l}" + (f"{DASH}{p}" if p else "")


def _pick(s: str) -> str:
    return html.escape(str(s)).replace(" -", f" {MINUS}")


def _day_label(day: pd.Timestamp) -> str:
    return f"{day:%A}, {day:%b}. {day.day}".upper().replace("MAY.", "MAY")


def _page(body: str) -> str:
    return f"<!doctype html><html><head><meta charset='utf-8'>{FONTS}<style>{CSS}</style></head><body>{body}</body></html>"


def _brand() -> str:
    logo = base64.b64encode(open(LOGO, "rb").read()).decode()
    return f"<div class='brand'><img src='data:image/png;base64,{logo}'>OFF THE GLASS</div>"


def _render(page: str, stem: str) -> str:
    os.makedirs(OUT, exist_ok=True)
    src, png = os.path.join(OUT, stem + ".html"), os.path.join(OUT, stem + ".png")
    open(src, "w").write(page)
    subprocess.run(["node", os.path.join(os.path.dirname(__file__), "render.js"), os.path.abspath(src), os.path.abspath(png)],
                   check=True, cwd=os.path.dirname(__file__))
    return png


def _season(through: str) -> dict:
    b = tracker.load("v1")
    s = b[(b["status"] == "settled") & (b["date"] <= through)]
    return {"w": int((s["result"] == "W").sum()), "l": int((s["result"] == "L").sum()), "p": int((s["result"] == "P").sum()),
            "u": float(s["profit"].sum())}


def _past(r) -> float:
    hs, as_ = float(r["home_score"]), float(r["away_score"])
    if r["market"] == "spread":
        return ((hs - as_) if r["side"] == "home" else (as_ - hs)) + float(r["line"])
    return (hs + as_ - float(r["line"])) * (1 if r["side"] == "over" else -1)


def _ledger(d: pd.DataFrame) -> str:
    """Every play, wins first then losses (each by margin), in columns sized to the slate: 2 columns with final scores
    up to 30 plays, 3 columns without scores up to 48, 4 up to 72; beyond that the last line says how many more."""
    n = len(d)
    cols, scores = (2, True) if n <= 30 else (3, False) if n <= 48 else (4, False)
    cap = 72
    shown = d.head(cap)
    per = math.ceil(len(shown) / cols)
    row_h = min(44 if scores else 40, int(700 / max(per, 1)))
    fs = 23 if cols <= 2 else 21 if cols == 3 else 17
    tmpl = "30px max-content minmax(0,1fr) 58px" if scores else ("26px minmax(0,1fr) 52px" if cols == 3 else "20px minmax(0,1fr) 42px")
    out = []
    for c in range(cols):
        part = shown.iloc[c * per:(c + 1) * per]
        rows = []
        for _, r in part.iterrows():
            res = r["result"]
            sc = (f"<span class='s' style='font-size:15px;text-align:right'>{html.escape(r['away'])} {int(r['away_score'])}, "
                  f"{html.escape(r['home'])} {int(r['home_score'])}</span>") if scores else ""
            body = (f"<span class='m {res}' style='font-size:{fs - 3}px'>{res}</span><span class='p' style='font-size:{fs}px'>"
                    f"{_pick(r['pick'])}</span>{sc}<span class='x {res}' style='font-size:{fs - 2}px'>{_num(r['past'])}</span>")
            rows.append(f"<div class='r' style='grid-template-columns:{tmpl};height:{row_h}px'>{body}</div>")
        out.append(f"<div>{''.join(rows)}</div>")
    more = f"<div class='more'>+{n - cap} more plays on the record page</div>" if n > cap else ""
    gap = 36 if cols <= 3 else 22
    return f"<div class='rt' style='grid-template-columns:repeat({cols},minmax(0,1fr));column-gap:{gap}px'>{''.join(out)}</div>{more}"


def recap(day: str) -> tuple[str, str]:
    """(png path, caption) for the main plays of ET date `day`; every one of the day's plays must be graded."""
    b = tracker.load("v1")
    d = b[(b["date"] == day) & (b["status"] != "void")].copy()
    if not len(d):
        raise SystemExit(f"No main plays on {day}.")
    if (d["status"] != "settled").any():
        raise SystemExit(f"{int((d['status'] != 'settled').sum())} play(s) on {day} are not graded yet.")
    w, l, p, u = int((d["result"] == "W").sum()), int((d["result"] == "L").sum()), int((d["result"] == "P").sum()), float(d["profit"].sum())
    d["past"] = d.apply(_past, axis=1)
    d["_o"] = d["result"].map({"W": 0, "P": 1, "L": 2})
    d = d.sort_values(["_o", "past"], ascending=[True, False])
    mk = {m: d[d["market"] == m] for m in ("total", "spread")}
    cl = clv_primary.primary(d).set_index("bet_id")["clv_primary"].dropna()
    sea = _season(day)
    dt = pd.Timestamp(day)
    parts = [f"{m.capitalize()}s <b>{_rec((x['result'] == 'W').sum(), (x['result'] == 'L').sum(), (x['result'] == 'P').sum())}</b> "
             f"({_units(x['profit'].sum())})" for m, x in mk.items() if len(x)]
    clv_line = (f"<br><b>{100 * (cl > 0).mean():.0f}%</b> beat the closing line (avg <b>{_num(cl.mean(), 2)}</b>)"
                if len(cl) else "")
    body = (f"<div class='l'>{_brand()}<div class='day'>{_day_label(dt)}</div><div class='big'>{_rec(w, l, p)}</div>"
            f"<div class='u {'org' if u >= 0 else 'L'}'>{_units(u).upper()}</div>"
            f"<div class='split'>{' &nbsp;·&nbsp; '.join(parts)}{clv_line}</div></div>{_ledger(d)}"
            f"<div class='f'><span>Season <b>{_rec(sea['w'], sea['l'], sea['p'])}, {_units(sea['u'])}</b>. Every play posted before tip. "
            f"Number at right = points past the line.</span><span class='h'>{HANDLE}</span></div>")
    png = _render(_page(body), f"recap_{day}")
    best = d[d["result"] == "W"].head(1)
    worst = d[d["result"] == "L"].tail(1)
    lines = [f"{dt:%A}: {_rec(w, l, p)}, {_units(u)}."]
    if len(best):
        lines.append(f"{str(best['pick'].iloc[0]).replace(' -', ' ' + MINUS)} cashed by {abs(best['past'].iloc[0]):g}.")
    if len(worst):
        lines.append(f"Worst miss: {str(worst['pick'].iloc[0]).replace(' -', ' ' + MINUS)} by {abs(worst['past'].iloc[0]):g}.")
    lines.append(", ".join(f"{m}s {_rec((x['result'] == 'W').sum(), (x['result'] == 'L').sum())}" for m, x in mk.items() if len(x)) + ".")
    if len(cl):
        lines.append(f"{100 * (cl > 0).mean():.0f}% beat the close.")
    lines[3] = lines[3][0].upper() + lines[3][1:]
    cap = " ".join(lines[:3]) + "\n\n" + " ".join(lines[3:]) + f"\n\nSeason {_rec(sea['w'], sea['l'], sea['p'])}, {_units(sea['u'])}."
    open(os.path.join(OUT, f"recap_{day}.txt"), "w").write(cap + "\n")
    return png, cap


def top_plays(day: str, n: int = 5) -> tuple[str, str]:
    """(png path, caption): the day's n main plays with the biggest logged edge, at the logged number and price."""
    b = tracker.load("v1")
    d = b[(b["date"] == day) & (b["status"] != "void")].sort_values("edge", ascending=False).head(n)
    if not len(d):
        raise SystemExit(f"No main plays logged for {day} yet.")
    card = os.path.join(ROOT, "reports", f"cbb_{day}.csv")
    start = pd.read_csv(card, usecols=["game_id", "start"]).set_index("game_id")["start"] if os.path.exists(card) else pd.Series(dtype=str)
    rows = []
    for i, (_, r) in enumerate(d.iterrows(), 1):
        st = pd.to_datetime(start.get(r["game_id"]), utc=True, errors="coerce")
        tip = f" · {st.tz_convert('America/New_York'):%-I:%M %p} ET" if pd.notna(st) else ""
        if r["market"] == "spread":
            team, tm = (r["home"], r["model"]) if r["side"] == "home" else (r["away"], -r["model"])
            model = f"model {html.escape(team)} {_num(-tm)}"
        else:
            model = f"model total {r['model']:.1f}"
        price = f"{int(r['odds']):+d}".replace("-", MINUS) if pd.notna(r["odds"]) else ""
        rows.append(f"<div class='tr'><div class='n'>{i}</div><div><div class='p'>{_pick(r['pick'])}</div>"
                    f"<div class='s'>{html.escape(r['away'])} at {html.escape(r['home'])}{tip} &nbsp;·&nbsp; "
                    f"<b>{html.escape(str(r['book']))} {price}</b> &nbsp;·&nbsp; {model}</div></div>"
                    f"<div class='e org'>{_num(r['edge'])}<small>POINT EDGE</small></div></div>")
    total = int(((b["date"] == day) & (b["status"] != "void")).sum())
    sea = _season((pd.Timestamp(day) - pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
    dt = pd.Timestamp(day)
    body = (f"<div class='l'>{_brand()}<div class='day'>{_day_label(dt)}</div><div class='big sm'>TOP {len(d)}</div>"
            f"<div class='u org' style='font-size:64px'>OF {total} PLAYS</div>"
            f"<div class='split'>Biggest edges between our number and the market, at the line and price when each play "
            f"was posted. Lines move.</div></div><div class='tp'>{''.join(rows)}</div>"
            f"<div class='f'><span>Season <b>{_rec(sea['w'], sea['l'], sea['p'])}, {_units(sea['u'])}</b>. Every play posted before tip "
            f"and graded in public.</span><span class='h'>{HANDLE}</span></div>")
    png = _render(_page(body), f"top_{day}")
    cap = (f"{dt:%A}'s top {len(d)} of {total}, by edge:\n\n"
           + "\n".join(f"{str(r['pick']).replace(' -', ' ' + MINUS)} ({r['book']} {f'{int(r.odds):+d}'.replace('-', MINUS)})"
                       for _, r in d.iterrows())
           + f"\n\nSeason {_rec(sea['w'], sea['l'], sea['p'])}, {_units(sea['u'])}.")
    open(os.path.join(OUT, f"top_{day}.txt"), "w").write(cap + "\n")
    return png, cap


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["recap", "top"])
    ap.add_argument("--date")
    a = ap.parse_args()
    day = a.date or f"{_today_et() - pd.Timedelta(days=1 if a.kind == 'recap' else 0):%Y-%m-%d}"
    png, cap = (recap if a.kind == "recap" else top_plays)(day)
    print(png)
    print(cap)
