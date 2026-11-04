"""X graphics for @OffTheGlassHQ: last night's recap and today's top plays (1600x900 PNG + a caption).

Dark box-score style (Chad, Nov 4: "look much less like AI"; picked the dark mock): condensed type, hard rules, every
play listed with its result, no rounded cards, badges or emoji. Every number comes from the official bet log
(bets/bets.csv, main plays only, never band B) and the primary close (cbb/clv_primary.py), the same figures as the
site's record page. Display only: nothing here changes a pick, a number, the bet log or the card.

    python -m social.graphics recap [--date YYYY-MM-DD]   # default: yesterday (ET)   -> out/social/recap_<date>.png/.txt
    python -m social.graphics top   [--date YYYY-MM-DD]   # default: today (ET)       -> out/social/top_<date>.png/.txt
    python -m social.graphics marquee  [--date]   # today's biggest game: our number vs the market (play or not)
    python -m social.graphics ratings  [--date]   # our power ratings top 25 next to the AP poll (Mondays)
    python -m social.graphics receipts [--date]   # today's plays whose closing line moved 2+ points our way

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
.mq{position:absolute;left:620px;right:64px;top:70px}
.mq .match{font-family:Anton;font-size:76px;line-height:1.02}
.mq .meta{font-family:'Barlow Condensed';font-weight:600;font-size:28px;color:#9aa3ad;margin-top:10px}
.mq table{width:100%;border-collapse:collapse;margin-top:34px}
.mq td{font-family:'Barlow Condensed';font-weight:700;font-size:40px;padding:14px 0;border-bottom:1px solid #2a2f36}
.mq td.k{color:#8f98a2;font-size:26px;font-weight:600;width:240px}
.mq .verdict{margin-top:30px;font-family:'Barlow Condensed';font-weight:700;font-size:34px;line-height:1.3}
.pr{position:absolute;left:620px;right:64px;top:58px;display:grid;grid-template-columns:1fr 1fr;column-gap:36px}
.pr .r{grid-template-columns:44px minmax(0,1fr) 70px 60px;height:56px}
.pr .rk{font-family:Anton;font-size:26px;color:#fd6c0f}
.pr .t{font-family:'Barlow Condensed';font-weight:700;font-size:25px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pr .nt{text-align:right;font-family:'Barlow Condensed';font-weight:700;font-size:22px;color:#c9ced4}
.pr .ap{text-align:right;font-family:'Barlow Condensed';font-weight:700;font-size:20px;color:#8f98a2}
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


ESPN = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/"
NATIONAL = {"ESPN", "ESPN2", "ABC", "CBS", "FOX", "FS1", "TNT", "TBS", "truTV", "NBC", "Peacock", "BTN", "SEC Network", "SECN",
            "ACC Network", "ACCN", "CBSSN", "ESPNU", "Big Ten Network", "USA Net"}


def _espn(path: str) -> dict:
    import json
    import urllib.request
    req = urllib.request.Request(ESPN + path, headers={"User-Agent": "cbb-model"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _card(day: str) -> pd.DataFrame:
    return pd.read_csv(os.path.join(ROOT, "reports", f"cbb_{day}.csv"))


def _card_data(day: str) -> dict:
    import json
    import re
    src = open(os.path.join(ROOT, "reports", f"cbb_{day}.html")).read()
    return json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', src, re.S).group(1))


def _market(day: str, h: int, a: int) -> tuple[float | None, float | None, int]:
    """Median home spread and total across books from each book's latest pull for the game (our own line log)."""
    c = pd.read_csv(os.path.join(ROOT, "lines", "closing.csv"))
    c = c[c["date"] == day]
    same = c[(c["home_id"] == h) & (c["away_id"] == a)]
    flip = c[(c["home_id"] == a) & (c["away_id"] == h)].assign(home_spread=lambda x: -x["home_spread"])
    g = pd.concat([same, flip]).sort_values("pulled_at").drop_duplicates("book", keep="last")
    if not len(g):
        return None, None, 0
    def consensus(x):      # the most common number across books; a tie goes to the one nearest the median
        if not len(x):
            return None
        m = x.mode()
        return float(min(m, key=lambda v: abs(v - x.median())))
    return consensus(g["home_spread"].dropna()), consensus(g["total"].dropna()), len(g)


def _line(team: str, x: float) -> str:
    return f"{team} {_num(x)}" if x else f"{team} PK"


def marquee(day: str) -> tuple[str, str]:
    """Today's biggest game: AP-ranked teams first, then national TV, then the best matchup in our own ratings.
    Our number vs the market, and whether it is an official play (never presented as one when it is not)."""
    card = _card(day)
    card = card[card["state"].astype(str) == "pre"] if "state" in card else card
    if not len(card):
        raise SystemExit(f"No games left to play on {day}.")
    net = {r["team"]: r["net"] for r in _card_data(day).get("ratings", [])}
    sb = _espn(f"scoreboard?dates={day.replace('-', '')}&groups=50&limit=500")
    info = {}
    for e in sb.get("events", []):
        c = e["competitions"][0]
        rk = [t.get("curatedRank", {}).get("current", 99) for t in c["competitors"]]
        nets = [n for b in c.get("broadcasts", []) for n in b.get("names", [])]
        info[int(e["id"])] = (rk, nets)
    def score(g):
        rk, tv = info.get(int(g["game_id"]), ([99, 99], []))
        ranked = sum(26 - r for r in rk if r and r <= 25)
        both = 30 if all(r and r <= 25 for r in rk) else 0
        nat = 15 if any(n in NATIONAL for n in tv) else 0
        q = min(net.get(g["home"], -30), net.get(g["away"], -30))
        return ranked + both + nat + q / 3
    card = card.assign(_s=card.apply(score, axis=1)).sort_values("_s", ascending=False)
    for _, g in card.iterrows():
        h, a = int(g["home_id"]), int(g["away_id"])
        sp, tot, nb = _market(day, h, a)
        if sp is not None:
            break
    else:
        raise SystemExit(f"No game on {day} has a market line yet.")
    rk, tv = info.get(int(g["game_id"]), ([99, 99], []))
    name = lambda team, r: (f"#{r} " if r and r <= 25 else "") + team
    home_r, away_r = (rk + [99, 99])[:2]
    comp = next((e["competitions"][0] for e in sb.get("events", []) if int(e["id"]) == int(g["game_id"])), None)
    if comp:
        side = {t["homeAway"]: t.get("curatedRank", {}).get("current", 99) for t in comp["competitors"]}
        home_r, away_r = side.get("home", 99), side.get("away", 99)
    st = pd.to_datetime(g["start"], utc=True, errors="coerce")
    tip = f"{st.tz_convert('America/New_York'):%-I:%M %p} ET" if pd.notna(st) else ""
    mm, mt = float(g["model_margin"]), float(g["model_total"])
    fav_mkt = g["home"] if sp <= 0 else g["away"]
    fav_mod = g["home"] if mm >= 0 else g["away"]
    b = tracker.load("v1")
    off = b[(b["date"] == day) & (b["game_id"] == g["game_id"]) & (b["status"] != "void")]
    if len(off):
        verdict = "OFFICIAL PLAY: " + ", ".join(_pick(x) + f" ({html.escape(str(bk))} {int(o):+d})".replace("-", MINUS)
                                                for x, bk, o in zip(off["pick"], off["book"], off["odds"]))
    else:
        verdict = "Not an official play: the gap is under our betting threshold. This is our number, not a pick."
    dsp = mm + sp            # home edge vs the market spread (model margin minus the market's home margin)
    lean = (f"Our number is {abs(dsp):.1f} points {'better for ' + html.escape(g['home']) if dsp > 0 else 'better for ' + html.escape(g['away'])} "
            f"than the market; total {abs(mt - tot):.1f} {'over' if mt > tot else 'under'} the market." if tot is not None else "")
    body = (f"<div class='l'>{_brand()}<div class='day'>{_day_label(pd.Timestamp(day))}</div><div class='big sm'>GAME OF</div>"
            f"<div class='big sm org' style='margin-top:0'>THE NIGHT</div><div class='split'>Our number vs. the betting market on "
            f"tonight's biggest game, play or not.</div></div>"
            f"<div class='mq'><div class='match'>{html.escape(name(g['away'], away_r))}<br><span style='color:#9aa3ad'>at</span> "
            f"{html.escape(name(g['home'], home_r))}</div><div class='meta'>{tip}{(' · ' + ', '.join(tv[:2])) if tv else ''}</div>"
            f"<table><tr><td class='k'>MARKET</td><td>{html.escape(_line(fav_mkt, -abs(sp)))}</td><td>Total {tot:g}</td></tr>"
            f"<tr><td class='k'>OUR NUMBER</td><td class='org'>{html.escape(_line(fav_mod, -abs(round(mm * 2) / 2)))}</td>"
            f"<td class='org'>Total {round(mt * 2) / 2:g}</td></tr></table>"
            f"<div class='verdict'>{lean}<br><span style='color:#c9ced4'>{verdict}</span></div></div>"
            f"<div class='f'><span>Market = the consensus number across {nb} sportsbooks at the latest pull. Our number = the model, rounded to the half point."
            f"</span><span class='h'>{HANDLE}</span></div>")
    png = _render(_page(body), f"marquee_{day}")
    cap = (f"Game of the night: {name(g['away'], away_r)} at {name(g['home'], home_r)}{', ' + tip if tip else ''}.\n\n"
           f"Market: {_line(fav_mkt, -abs(sp))}, total {tot:g}.\nOur number: {_line(fav_mod, -abs(round(mm * 2) / 2))}, "
           f"total {round(mt * 2) / 2:g}.\n\n"
           + (("Official play: " + ", ".join(str(x).replace(' -', ' ' + MINUS) for x in off['pick']) + ".") if len(off)
              else "Not an official play. Where do you have it?"))
    open(os.path.join(OUT, f"marquee_{day}.txt"), "w").write(cap + "\n")
    return png, cap


def power_ratings(day: str, n: int = 25) -> tuple[str, str]:
    """Our power ratings (the card's ratings table: points per 100 possessions better than an average team) next
    to the current AP poll; the caption names the biggest disagreements."""
    rt = pd.DataFrame(_card_data(day).get("ratings", []))
    if not len(rt):
        raise SystemExit(f"No ratings table on the {day} card.")
    rt = rt.sort_values("net", ascending=False).reset_index(drop=True)
    rt["ours"] = rt.index + 1
    ap = {}
    for poll in _espn("rankings").get("rankings", []):
        if "AP" in poll.get("name", ""):
            ap = {t["team"]["location"]: int(t["current"]) for t in poll.get("ranks", [])}
            apname = "AP Top 25" + (" (preseason)" if "reseason" in (poll.get("headline") or poll.get("name") or "") else "")
            break
    else:
        apname = "AP poll unavailable"
    top = rt.head(n)
    half = (len(top) + 1) // 2
    def col(part):
        return "".join(f"<div class='r'><span class='rk'>{int(r['ours'])}</span><span class='t'>{html.escape(r['team'])}</span>"
                       f"<span class='nt'>{_num(r['net'])}</span><span class='ap'>{('AP ' + str(ap[r['team']])) if r['team'] in ap else 'NR'}</span></div>"
                       for _, r in part.iterrows())
    under = [t for t in top["team"] if t not in ap][:3]
    over = sorted(((t, r, int(rt.loc[rt["team"] == t, "ours"].iloc[0]) if (rt["team"] == t).any() else None) for t, r in ap.items()),
                  key=lambda x: -((x[2] or 400) - x[1]))
    over = [(t, r, o) for t, r, o in over if o is None or o > 25][:3]
    split = ("<b>Higher on:</b> " + ", ".join(html.escape(t) for t in under) + "<br>" if under else "") + (
        "<b>Lower on:</b> " + ", ".join(f"{html.escape(t)} (AP {r}, ours {o or 'NR'})" for t, r, o in over) if over else "")
    body = (f"<div class='l'>{_brand()}<div class='day'>WEEK OF {f'{pd.Timestamp(day):%b}'.upper()}. {pd.Timestamp(day).day}</div>"
            f"<div class='big sm'>POWER</div><div class='big sm org' style='margin-top:0'>RATINGS</div>"
            f"<div class='split'>{split}</div></div><div class='pr'><div>{col(top.iloc[:half])}</div><div>{col(top.iloc[half:])}</div></div>"
            f"<div class='f'><span>Rating = points per 100 possessions better than an average D-I team (our model). Right: {html.escape(apname)}."
            f"</span><span class='h'>{HANDLE}</span></div>")
    png = _render(_page(body), f"ratings_{day}")
    cap = (f"Our top {n} vs the AP poll.\n\n"
           + (f"Higher on: {', '.join(under)}.\n" if under else "")
           + (f"Lower on: {', '.join(f'{t} (AP {r})' for t, r, o in over)}.\n" if over else "")
           + "\nWho are we wrong about?")
    open(os.path.join(OUT, f"ratings_{day}.txt"), "w").write(cap + "\n")
    return png, cap


def receipts(day: str, min_move: float = 2.0) -> tuple[str, str]:
    """The day's main plays whose primary close moved min_move+ points toward our number: posted line and time,
    closing line, move. Nothing when no play qualifies."""
    b = tracker.load("v1")
    d = b[(b["date"] == day) & (b["status"] != "void")].copy()
    if not len(d):
        raise SystemExit(f"No main plays on {day}.")
    p = clv_primary.primary(d).set_index("bet_id")
    d["close"], d["clv"] = d["bet_id"].map(p["close_primary"]), d["bet_id"].map(p["clv_primary"])
    q = d[d["clv"] >= min_move].sort_values("clv", ascending=False).head(10)
    if not len(q):
        raise SystemExit(f"No {day} play moved {min_move:g}+ points our way (yet).")
    rows = []
    for _, r in q.iterrows():
        t = pd.Timestamp(r["logged_at"]).tz_convert("America/New_York")
        close = (f"{r['close']:+g}".replace("-", MINUS) if r["market"] == "spread" else f"{r['close']:g}")
        rows.append(f"<div class='r' style='grid-template-columns:minmax(0,1fr) 230px 120px 90px;height:58px'>"
                    f"<span class='p' style='font-size:28px'>{_pick(r['pick'])}</span>"
                    f"<span class='s' style='font-size:19px'>posted {t:%a %-I:%M %p}</span>"
                    f"<span class='x' style='font-size:24px;color:#c9ced4'>close {close}</span>"
                    f"<span class='x org' style='font-size:28px'>{_num(r['clv'])}</span></div>")
    n_all = int(d["clv"].notna().sum())
    beat = int((d["clv"] > 0).sum())
    body = (f"<div class='l'>{_brand()}<div class='day'>{_day_label(pd.Timestamp(day))}</div><div class='big sm'>THE LINE</div>"
            f"<div class='big sm org' style='margin-top:0'>MOVED TO US</div><div class='split'><b>{beat} of {n_all}</b> plays beat the "
            f"closing line. These moved {min_move:g}+ points our way between the post and tip.</div></div>"
            f"<div class='rt' style='grid-template-columns:1fr'><div>{''.join(rows)}</div></div>"
            f"<div class='f'><span>Close = median of 6+ sportsbooks in the last 15 minutes before tip.</span><span class='h'>{HANDLE}</span></div>")
    png = _render(_page(body), f"receipts_{day}")
    top = q.iloc[0]
    cap = (f"We posted {str(top['pick']).replace(' -', ' ' + MINUS)}. It closed "
           f"{format(top['close'], '+g').replace('-', MINUS) if top['market'] == 'spread' else format(top['close'], 'g')}.\n\n"
           f"{len(q)} of tonight's plays moved {min_move:g}+ points our way before tip; {beat} of {n_all} beat the close.")
    open(os.path.join(OUT, f"receipts_{day}.txt"), "w").write(cap + "\n")
    return png, cap


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["recap", "top", "marquee", "ratings", "receipts"])
    ap.add_argument("--date")
    a = ap.parse_args()
    day = a.date or f"{_today_et() - pd.Timedelta(days=1 if a.kind == 'recap' else 0):%Y-%m-%d}"
    png, cap = {"recap": recap, "top": top_plays, "marquee": marquee, "ratings": power_ratings, "receipts": receipts}[a.kind](day)
    print(png)
    print(cap)
