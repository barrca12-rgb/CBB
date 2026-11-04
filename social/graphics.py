"""X graphics for @OffTheGlassHQ: last night's recap and today's top plays (1600x900 PNG + a caption).

Every number comes from the official bet log (bets/bets.csv, main plays only, never band B) and the primary close
(cbb/clv_primary.py), the same figures as the site's record page. Display only: nothing here changes a pick, a number,
the bet log or the card.

    python -m social.graphics recap [--date YYYY-MM-DD]   # default: yesterday (ET)   -> out/social/recap_<date>.png/.txt
    python -m social.graphics top   [--date YYYY-MM-DD]   # default: today (ET)       -> out/social/top_<date>.png/.txt

Rendering uses headless Chromium through Node's Playwright (social/render.js).
"""
from __future__ import annotations

import argparse
import base64
import html
import os
import subprocess

import pandas as pd

from cbb import clv_primary, tracker

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "out", "social")
LOGO = os.path.join(ROOT, "site", "assets", "otg-logo-512.png")
HANDLE = "@OffTheGlassHQ"
MINUS = "−"

CSS = """
:root{--bg:#fbf6ea;--navy:#0a2c49;--muted:#56627a;--line:#ebe1cd;--pos:#0f7b4b;--neg:#c2352b;--brand:#fd6c0f;--accent:#b84a08}
*{box-sizing:border-box;margin:0;padding:0}
body{width:1600px;height:900px;background:var(--bg);font-family:Inter,sans-serif;color:var(--navy);overflow:hidden;position:relative}
.top{height:120px;background:var(--navy);display:flex;align-items:center;padding:0 56px;border-bottom:8px solid var(--brand)}
.top img{height:84px;width:84px;object-fit:contain;border-radius:14px;display:block}
.brand{font-family:Graduate,serif;color:#fbf6ea;font-size:44px;margin-left:24px;letter-spacing:.03em}
.date{margin-left:auto;text-align:right;color:#fbf6ea}
.date .k{font-size:20px;font-weight:700;letter-spacing:.14em;color:#b7c3d3}
.date .v{font-family:Graduate,serif;font-size:40px;margin-top:4px}
.pos{color:var(--pos)} .neg{color:var(--neg)}
.foot{position:absolute;left:56px;right:56px;bottom:26px;display:flex;align-items:center;font-size:21px;color:var(--muted);font-weight:600;border-top:2px solid var(--line);padding-top:16px}
.foot b{color:var(--navy)} .foot .r{margin-left:auto;color:var(--accent);font-weight:800}
/* recap */
.main{display:grid;grid-template-columns:560px 1fr;gap:40px;padding:62px 56px 0}
.hero .k{font-size:22px;font-weight:800;letter-spacing:.16em;color:var(--muted)}
.hero .rec{font-family:Graduate,serif;font-size:150px;line-height:1;margin-top:10px}
.hero .u{font-size:58px;font-weight:800;margin-top:8px}
.hero .u small{font-size:28px;color:var(--muted);font-weight:600;margin-left:10px}
.pills{display:flex;gap:20px;margin-top:40px}
.pill{flex:1;background:#fff;border:2px solid var(--line);border-radius:16px;padding:24px}
.pill .k{font-size:18px;font-weight:800;letter-spacing:.14em;color:var(--muted)}
.pill .v{font-size:46px;font-weight:800;margin-top:6px}
.pill .s{font-size:24px;font-weight:700;margin-top:2px}
.right .k{font-size:22px;font-weight:800;letter-spacing:.16em;color:var(--muted);margin-bottom:14px}
.right .k span{color:#8a93a3;font-weight:700;letter-spacing:.06em}
.right .row{display:flex;align-items:center;background:#fff;border:2px solid var(--line);border-radius:14px;padding:0 22px;height:86px;margin-bottom:15px}
.right .p{font-size:30px;font-weight:800;width:300px}
.right .g{flex:1;font-size:22px;font-weight:600;color:var(--muted)}
.right .b{font-size:26px;font-weight:800;color:var(--pos);background:#e6f4ed;border-radius:10px;padding:6px 14px}
.clv{display:flex;align-items:center;gap:24px;background:var(--navy);border-radius:16px;padding:22px 28px;margin-top:10px;color:#fbf6ea}
.clv .big{font-family:Graduate,serif;font-size:56px;color:var(--brand)}
.clv .t{font-size:24px;font-weight:700}
.clv small{display:block;font-size:17px;font-weight:500;color:#b7c3d3;margin-top:6px}
/* top plays */
.head{padding:34px 56px 16px;display:flex;align-items:baseline}
.head .t{font-size:24px;font-weight:800;letter-spacing:.16em;color:var(--muted)}
.head .s{margin-left:auto;font-size:20px;font-weight:600;color:#8a93a3}
.list{padding:0 56px}
.list .row{display:flex;align-items:center;background:#fff;border:2px solid var(--line);border-radius:16px;padding:16px 26px;margin-bottom:12px;height:104px}
.n{font-family:Graduate,serif;font-size:46px;color:var(--brand);width:64px}
.pk{flex:1} .pk .p{font-size:34px;font-weight:800} .pk .g{font-size:21px;font-weight:600;color:var(--muted);margin-top:4px}
.m{width:440px;font-size:22px;font-weight:700;text-align:right;padding-right:34px}
.bk{font-size:19px;font-weight:600;color:#8a93a3;margin-top:4px}
.e{width:150px;text-align:center;background:#e6f4ed;border-radius:12px;padding:10px 0}
.ev{font-size:38px;font-weight:800;color:var(--pos);line-height:1}
.el{font-size:15px;font-weight:800;letter-spacing:.1em;color:var(--pos);margin-top:4px;text-transform:uppercase}
"""


def _today_et() -> pd.Timestamp:
    return pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize()


def _num(x: float, d: int = 1) -> str:
    s = f"{x:+.{d}f}".rstrip("0").rstrip(".") if d else f"{x:+.0f}"
    return s.replace("-", MINUS)


def _units(x: float) -> str:
    return f"{x:+.2f}u".replace("-", MINUS)


def _rec(w: int, l: int, p: int = 0) -> str:
    return f"{w}–{l}" + (f"–{p}" if p else "")


def _pick(s: str) -> str:
    return html.escape(str(s)).replace(" -", f" {MINUS}")


def _page(body: str, kicker: str, day: pd.Timestamp) -> str:
    logo = base64.b64encode(open(LOGO, "rb").read()).decode()
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=Graduate&family=Inter:wght@400;500;600;700;800&display=swap'>"
            f"<style>{CSS}</style></head><body><div class='top'><img src='data:image/png;base64,{logo}'>"
            f"<div class='brand'>OFF THE GLASS</div><div class='date'><div class='k'>COLLEGE BASKETBALL · {kicker}</div>"
            f"<div class='v'>{day.strftime('%a').upper()} · {day.strftime('%b').upper()} {day.day}</div></div></div>{body}</body></html>")


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


def recap(day: str) -> tuple[str, str]:
    """(png path, caption) for the main plays of ET date `day`; every one of the day's plays must be graded."""
    b = tracker.load("v1")
    d = b[(b["date"] == day) & (b["status"] != "void")].copy()
    if not len(d):
        raise SystemExit(f"No main plays on {day}.")
    if (d["status"] != "settled").any():
        raise SystemExit(f"{int((d['status'] != 'settled').sum())} play(s) on {day} are not graded yet.")
    w, l, p, u = int((d["result"] == "W").sum()), int((d["result"] == "L").sum()), int((d["result"] == "P").sum()), float(d["profit"].sum())
    mk = {m: d[d["market"] == m] for m in ("total", "spread")}
    d["past"] = d.apply(_past, axis=1)
    top = d[d["result"] == "W"].sort_values("past", ascending=False).head(4)
    cl = clv_primary.primary(d).set_index("bet_id")["clv_primary"].dropna()
    sea = _season(day)
    dt = pd.Timestamp(day)
    lab = f"{dt:%b} {dt.day}".upper()
    pills = "".join(
        f"<div class='pill'><div class='k'>{lab} {m.upper()}S</div><div class='v'>{_rec((x['result'] == 'W').sum(), (x['result'] == 'L').sum(), (x['result'] == 'P').sum())}</div>"
        f"<div class='s {'pos' if x['profit'].sum() >= 0 else 'neg'}'>{_units(x['profit'].sum())}</div></div>" for m, x in mk.items() if len(x))
    rows = "".join(f"<div class='row'><div class='p'>{_pick(r['pick'])}</div><div class='g'>{html.escape(r['away'])} {int(r['away_score'])}, "
                   f"{html.escape(r['home'])} {int(r['home_score'])}</div><div class='b'>{_num(r['past'])}</div></div>" for _, r in top.iterrows())
    clvbox = (f"<div class='clv'><div class='big'>{100 * (cl > 0).mean():.0f}%</div><div class='t'>of {dt:%b} {dt.day} plays beat the closing line, "
              f"{_num(cl.mean(), 2)} pts on average<small>vs. the consensus close of 6+ sportsbooks in the final 15 minutes before tip</small></div></div>"
              if len(cl) else "")
    body = (f"<div class='main'><div class='hero'><div class='k'>OFFICIAL RECORD · {lab}</div><div class='rec'>{_rec(w, l, p)}</div>"
            f"<div class='u {'pos' if u >= 0 else 'neg'}'>{_units(u)}<small>{100 * w / max(w + l, 1):.1f}% wins</small></div>"
            f"<div class='pills'>{pills}</div></div><div class='right'>"
            + (f"<div class='k'>BIGGEST CASHES <span>· POINTS PAST THE NUMBER</span></div>{rows}" if len(top) else "")
            + f"{clvbox}</div></div><div class='foot'><span>Season <b>{_rec(sea['w'], sea['l'], sea['p'])} · {_units(sea['u'])}</b> · "
            f"every play logged and timestamped before tip</span><span class='r'>{HANDLE}</span></div>")
    png = _render(_page(body, "DAY RECAP", dt), f"recap_{day}")
    parts = [f"{x.capitalize()}s {_rec((v['result'] == 'W').sum(), (v['result'] == 'L').sum())}" for x, v in mk.items() if len(v)]
    cap = (f"{dt:%A}: {_rec(w, l, p)}, {_units(u)} \U0001F3C0\n\n{', '.join(parts)}."
           + (f" {100 * (cl > 0).mean():.0f}% of plays beat the closing line." if len(cl) else "")
           + f"\n\nSeason: {_rec(sea['w'], sea['l'], sea['p'])}, {_units(sea['u'])}. Every play logged before tip.")
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
            model = f"Model: {html.escape(team)} {_num(-tm)}"
        else:
            model = f"Model: {r['model']:.1f} total"
        price = f"{int(r['odds']):+d}".replace("-", MINUS) if pd.notna(r["odds"]) else ""
        rows.append(f"<div class='row'><div class='n'>{i}</div><div class='pk'><div class='p'>{_pick(r['pick'])}</div>"
                    f"<div class='g'>{html.escape(r['away'])} at {html.escape(r['home'])}{tip}</div></div>"
                    f"<div class='m'>{model}<div class='bk'>{html.escape(str(r['book']))} {price}</div></div>"
                    f"<div class='e'><div class='ev'>{_num(r['edge'])}</div><div class='el'>pt edge</div></div></div>")
    sea = _season((pd.Timestamp(day) - pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
    body = (f"<div class='head'><div class='t'>TOP {len(d)} PLAYS · BIGGEST MODEL EDGE</div><div class='s'>Numbers and prices when the "
            f"play was logged · lines move</div></div><div class='list'>{''.join(rows)}</div><div class='foot'><span>Season <b>"
            f"{_rec(sea['w'], sea['l'], sea['p'])} · {_units(sea['u'])}</b> · every play logged and timestamped before tip</span>"
            f"<span class='r'>{HANDLE}</span></div>")
    dt = pd.Timestamp(day)
    png = _render(_page(body, "TODAY", dt), f"top_{day}")
    cap = (f"Tonight's top {len(d)} \U0001F3C0 biggest model edges:\n\n"
           + "\n".join(f"{i}. {str(r['pick']).replace(' -', ' ' + MINUS)}" for i, (_, r) in enumerate(d.iterrows(), 1))
           + f"\n\nSeason: {_rec(sea['w'], sea['l'], sea['p'])}, {_units(sea['u'])}. Logged before tip, graded in public.")
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
