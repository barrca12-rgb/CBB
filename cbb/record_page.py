"""The public record page (reports/record.html, published as record.html on the site), rebuilt every card run from
bets/bets.csv: record, units, ROI and CLV for every play the model logged, by market and by month, then every play
as logged, losers and voids included, with links to check it (the bet log and its history, the OpenTimestamps proof,
the Discord channel). Plays count whether or not they were bet; a placed-only line sits beside the totals.

The Discord invite link, when there is one, goes in data/record_links.json as {"discord_invite": "https://discord.gg/..."}.
"""
from __future__ import annotations

import html
import json
import os

import numpy as np
import pandas as pd

from . import clv_primary, report_html, tracker

OUT = os.path.join(tracker.ROOT, "reports", "record.html")
VERIFY = os.path.join(tracker.ROOT, "reports", "verify.html")      # published unlisted at record/verify.html
CHARTS = os.path.join(tracker.ROOT, "site", "record", "charts.html")  # the Charts tab, published at record/charts.html
WEEKLY = os.path.join(tracker.ROOT, "site", "record", "weekly")     # cbb/record_chart.py, published at record/weekly/
LINKS = os.path.join(tracker.ROOT, "data", "record_links.json")
BRANCH = "claude/college-basketball-model-nmztcl"
GH = f"https://github.com/{report_html.REPO}"


def _num(x, fmt="{:+.2f}", empty="–"):
    return empty if x is None or (isinstance(x, float) and np.isnan(x)) else fmt.format(x)


def summary(s: pd.DataFrame) -> dict:
    """Record, units, ROI and CLV for settled plays s."""
    w, l, p = (s["result"] == "W").sum(), (s["result"] == "L").sum(), (s["result"] == "P").sum()
    staked = s["stake"].astype(float).sum()
    units = float(s["profit"].astype(float).sum())
    clv = s["clv_pts"].astype(float).dropna()
    return {"bets": int(len(s)), "rec": f"{w}-{l}" + (f"-{p}" if p else ""), "win": w / (w + l) if w + l else None,
            "units": units, "roi": units / staked if staked else None, "clv": float(clv.mean()) if len(clv) else None,
            "beat": float((clv > 0).mean()) if len(clv) else None}


def _row(label: str, s: dict) -> str:
    cls = "pos" if s["units"] > 0 else "neg" if s["units"] < 0 else ""
    return (f"<tr><td class='b'>{html.escape(label)}</td><td class='r'>{s['bets']}</td><td class='r'>{s['rec']}</td>"
            f"<td class='r'>{_num(s['win'], '{:.1%}')}</td><td class='r {cls}'>{_num(s['units'])}</td>"
            f"<td class='r'>{_num(s['roi'], '{:+.1%}')}</td><td class='r'>{_num(s['clv'])}</td>"
            f"<td class='r'>{_num(s['beat'], '{:.0%}')}</td></tr>")


HEAD = ("<thead><tr><th></th><th class='r'>Plays</th><th class='r'>W-L</th><th class='r'>Win %</th><th class='r'>Units</th>"
        "<th class='r'>ROI</th><th class='r'>CLV pts</th><th class='r'>Beat close</th></tr></thead>")


def _chart(s: pd.DataFrame) -> str:
    """Cumulative units over settled plays, in order settled (inline SVG; shown from 5 plays)."""
    if len(s) < 5:
        return ""
    y = s.sort_values(["date", "logged_at"])["profit"].astype(float).cumsum().to_numpy()
    y = np.r_[0.0, y]
    W, H, P = 1000, 180, 8
    lo, hi = min(y.min(), 0), max(y.max(), 0)
    span = (hi - lo) or 1
    xs = np.linspace(P, W - P, len(y))
    ys = P + (hi - y) / span * (H - 2 * P)
    zero = P + hi / span * (H - 2 * P)
    pts = " ".join(f"{a:.1f},{b:.1f}" for a, b in zip(xs, ys))
    color = "var(--pos)" if y[-1] >= 0 else "var(--neg)"
    return (f"<div style='padding:12px 16px'><svg viewBox='0 0 {W} {H}' width='100%' height='{H}' preserveAspectRatio='none' "
            f"role='img' aria-label='Cumulative units: {y[-1]:+.2f} after {len(y) - 1} plays'>"
            f"<line x1='0' x2='{W}' y1='{zero:.1f}' y2='{zero:.1f}' stroke='var(--line-strong)' stroke-dasharray='4 4'/>"
            f"<polyline points='{pts}' fill='none' stroke='{color}' stroke-width='2' vector-effect='non-scaling-stroke'/></svg>"
            f"<div class='m' style='font-size:12px;display:flex;justify-content:space-between'><span>first play</span>"
            f"<span>{y[-1]:+.2f} units after {len(y) - 1} plays</span></div></div>")


ACCEPTED = os.path.join(tracker.ROOT, "bets", "accepted.csv")
FRESH_S = 600   # cohort B: quote observed at the generating pull, source timestamp no older than this


def cohorts(b: pd.DataFrame) -> tuple[str, str]:
    """Cohorts A (every logged signal), B (signal backed by a fresh observed quote at a named book at the logged
    number) and C (confirmed accepted bets, bets/accepted.csv, matched to A) side by side, and C's deterioration
    vs A. FORWARD_TEST_PROTOCOL.md section 6. A feed quote is never treated as proof of acceptance."""
    a = b[b["status"] != "void"]
    sl = os.path.join(tracker.ROOT, "bets", "signal_log.csv")
    sig = pd.read_csv(sl) if os.path.exists(sl) else pd.DataFrame(columns=["bet_id", "quote_status", "quote_age_s", "book", "line"])
    sig = sig.drop_duplicates("bet_id", keep="first").set_index("bet_id")
    age = pd.to_numeric(a["bet_id"].map(sig["quote_age_s"]), errors="coerce")
    fresh = (a["bet_id"].map(sig["quote_status"]) == "available") & age.between(-60, FRESH_S) & \
        (a["bet_id"].map(sig["book"]) == a["book"]) & \
        (pd.to_numeric(a["bet_id"].map(sig["line"]), errors="coerce") == pd.to_numeric(a["line"], errors="coerce"))
    unknown = ~a["bet_id"].isin(sig.index) | age.isna()
    acc = pd.read_csv(ACCEPTED) if os.path.exists(ACCEPTED) else pd.DataFrame(
        columns=["bet_id", "book", "placed_at", "line", "odds", "stake", "source"])
    acc = acc[acc["bet_id"].isin(a["bet_id"])]
    c = a.merge(acc, on="bet_id", suffixes=("", "_acc"))

    def col(d: pd.DataFrame, res_col="result", profit=None) -> str:
        s_ = d[d["status"] == "settled"]
        w, l, p = (s_[res_col] == "W").sum(), (s_[res_col] == "L").sum(), (s_[res_col] == "P").sum()
        u = s_["profit"].astype(float).sum() if profit is None else profit
        clv = s_["clv_pts"].astype(float).dropna()
        return (f"<td class='r'>{len(d)}</td><td class='r'>{len(s_)}</td><td class='r'>{w}-{l}-{p}</td>"
                f"<td class='r'>{_num(w / (w + l) if w + l else None, '{:.1%}')}</td><td class='r'>{_num(u)}</td>"
                f"<td class='r'>{_num(clv.mean() if len(clv) else None)}</td>")

    rows = (f"<tr><td class='b'>A. Every signal</td>{col(a)}</tr>"
            f"<tr><td class='b'>B. Fresh quote at a named book</td>{col(a[fresh])}</tr>"
            f"<tr><td class='b'>C. Confirmed accepted bets</td>{col(c) if len(c) else '<td class=r>0</td>' + '<td></td>' * 5}</tr>")
    head = ("<thead><tr><th>Cohort</th><th class='r'>Signals</th><th class='r'>Settled</th><th class='r'>W-L-P</th>"
            "<th class='r'>Win %</th><th class='r'>Units (logged price)</th><th class='r'>CLV pts</th></tr></thead>")
    nop = int(pd.to_numeric(a["odds"], errors="coerce").isna().sum())
    note = (f"Units use the recorded price; {nop} signal(s) without one are counted at -110 here and are left out of "
            f"the forward test's profitability figures. "
            f"B excludes {int(unknown.sum())} signal(s) logged before quote timestamps were recorded or without one. "
            f"C counts only bets confirmed with book, time, line, odds and stake (bets/accepted.csv); "
            f"{len(c)} of {len(a)} signals matched.")
    if len(c):
        # points better than signalled: spreads are from the bettor's side (higher is better); totals: lower is
        # better on an over, higher on an under
        diff = c["line_acc"].astype(float) - c["line"].astype(float)
        dline = np.where(c["side"] == "over", -diff, diff)
        delay = (pd.to_datetime(c["placed_at"], utc=True, errors="coerce") -
                 pd.to_datetime(c["logged_at"], utc=True, errors="coerce")).dt.total_seconds() / 60
        note += (f" Accepted vs signal: number {np.nanmean(dline):+.2f} pts (+ = better than signalled), "
                 f"price {np.nanmean(c['odds_acc'].astype(float) - c['odds'].astype(float)):+.1f} (American), "
                 f"median delay {np.nanmedian(delay):.0f} min.")
    return head + "<tbody>" + rows + "</tbody>", note


def _logo(team_id, px: int = 16) -> str:
    """ESPN team logo (light and dark variants); removed by the browser if it fails to load."""
    try:
        i = int(float(team_id))
    except (TypeError, ValueError):
        return ""
    u = "https://a.espncdn.com/i/teamlogos/ncaa/{}/" + f"{i}.png"
    return (f"<picture class='tl'><source media='(prefers-color-scheme: dark)' srcset='{u.format('500-dark')}'>"
            f"<img src='{u.format('500')}' alt='' loading='lazy' width='{px}' height='{px}' onerror=\"this.closest('picture').remove()\"></picture>")


def weekly() -> str:
    """The Charts tab body: the newest weekly pair (cbb/record_chart.py) full width, then every past week."""
    idx = os.path.join(WEEKLY, "index.json")
    weeks = json.load(open(idx))["weeks"] if os.path.exists(idx) else []
    if not weeks:
        return ("<section class='panel'><div class='empty'>The first chart is drawn Monday morning, after the first "
                "week of games.</div></section>")
    lab = lambda w: f"{pd.Timestamp(w):%b} {pd.Timestamp(w).day}"
    img = lambda w, k: (f"<a href='record/weekly/{w}-{k}.png'><img src='record/weekly/{w}-{k}.png' alt='Through {lab(w)}: "
                        f"{'closing-line value' if k == 'clv' else 'units by week'}' width='1600' height='900' loading='lazy' "
                        f"style='width:100%;height:auto;display:block;border-radius:8px;border:1px solid var(--line)'></a>")
    d = weeks[0]
    out = (f"<section class='panel'><div class='panel-h'><h2>This week</h2><span class='note'>Through Sunday {lab(d)}, season "
           f"to date. Drawn every Monday from the bet log; every play counts. Tap an image to open it full size.</span></div>"
           f"<div style='padding:12px 16px;display:grid;gap:14px'>{img(d, 'clv')}{img(d, 'units')}</div></section>")
    if len(weeks) > 1:
        cards = "".join(f"<div><div class='m' style='font-size:12px;font-weight:600;margin-bottom:4px'>Through {lab(w)}</div>"
                        f"<div style='display:grid;gap:6px'>{img(w, 'clv')}{img(w, 'units')}</div></div>" for w in weeks[1:])
        out += (f"<section class='panel'><div class='panel-h'><h2>Past weeks</h2></div><div style='padding:12px 16px;display:grid;"
                f"gap:16px;grid-template-columns:repeat(auto-fill,minmax(min(100%,260px),1fr))'>{cards}</div></section>")
    return out


def build_charts() -> str:
    """The Charts tab (record/charts.html), next to Record on the card."""
    style = report_html.TEMPLATE[report_html.TEMPLATE.index("<style>"):report_html.TEMPLATE.index("</style>") + 8]
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<base href="../">
<title>Off The Glass · College Basketball Charts</title>
<meta property="og:title" content="Off The Glass · College Basketball Charts">
{report_html.HEAD}
{style}
<header class="top"><div class="wrap">
  {report_html.BRAND}
  <nav class="tabs" aria-label="Sport"><a href="{report_html.NFL_SITE}">NFL</a>{report_html.NBA_TAB}<a href="./" aria-current="page"><span class="hide-sm">College Basketball</span><span class="show-sm">CBB</span></a></nav>
</div></header>
<main class="wrap">
  <div class="head"><div><h1>College Basketball Charts</h1>
    <div class="sub">Closing-line value and units, season to date, every Monday.</div></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap"><a class="pagebtn" href="./">&larr; Card</a><a class="pagebtn" href="record.html">Record</a></div></div>
  {weekly()}
  <footer>
    <div><a class="follow" href="https://x.com/{report_html.X_HANDLE}" target="_blank" rel="noopener"><img src="assets/otg-logo-512.png" alt="">Follow @{report_html.X_HANDLE} on X for every play</a></div></footer>
</main>
</html>
"""


def build() -> str:
    # CLV and the close shown are the forward-test protocol's primary close (cbb/clv_primary.py), as the weekly chart
    b = clv_primary.attach(tracker.load())
    # Every play counts as placed (Chad bets them all, Oct 27) unless marked placed = "no"; voids are out.
    live = b[(b["status"] != "void") & (b["placed"].astype(str).str.lower() != "no")]
    s = live[live["status"] == "settled"]
    tot = summary(s)
    links = json.load(open(LINKS)) if os.path.exists(LINKS) else {}
    ann = json.load(open(os.path.join(tracker.ROOT, "bets", "announcements.json"))) \
        if os.path.exists(os.path.join(tracker.ROOT, "bets", "announcements.json")) else []

    kp = [("Record", tot["rec"]), ("Win %", _num(tot["win"], "{:.1%}")), ("Units", _num(tot["units"])),
          ("ROI", _num(tot["roi"], "{:+.1%}")), ("Avg CLV", _num(tot["clv"], "{:+.2f} pts")),
          ("Open plays", str(int((live["status"] == "open").sum())))]
    kpis = "".join(f"<div class='kpi'><div class='k'>{k}</div><div class='v'>{v}</div></div>" for k, v in kp)

    rows = [_row("All bets", tot)]
    rows += [_row(lbl, summary(s[s["market"] == mk])) for mk, lbl in (("spread", "Spreads"), ("total", "Totals"))]
    months = ""
    if len(s):
        m = s.assign(mo=pd.to_datetime(s["date"]).dt.to_period("M"))
        months = "".join(_row(p.strftime("%b %Y"), summary(g)) for p, g in sorted(m.groupby("mo"), key=lambda x: x[0], reverse=True))

    plays = []
    mine = live   # every play except voids and any marked placed = "no"
    for _, r in mine.sort_values(["date", "logged_at"], ascending=False).iterrows():
        res = {"W": "<span class='pos b'>Win</span>", "L": "<span class='neg b'>Loss</span>", "P": "Push"}.get(
            str(r["result"]), "Open")
        units = _num(float(r["profit"])) if r["status"] == "settled" else "–"
        logged = pd.Timestamp(r["logged_at"]).tz_convert("America/New_York")
        plays.append(
            f"<tr><td class='m'>{r['date']}</td><td>{_logo(r['away_id'])}{html.escape(str(r['away']))} at {_logo(r['home_id'])}{html.escape(str(r['home']))}</td>"
            f"<td class='b'>{html.escape(str(r['pick']))}</td><td>{html.escape(str(r['book']))} "
            f"<span class='m'>{_num(r['odds'], '{:+.0f}')}</span></td><td class='r'>{_num(r['edge'], '{:.1f}')}</td>"
            f"<td class='r'>{_num(r['close_line'], '{:g}')}</td><td class='r'>{_num(r['clv_pts'], '{:+.1f}')}</td>"
            f"<td>{res}</td><td class='r'>{units}</td>"
            f"<td class='m hide-sm'>{logged:%b %-d %-I:%M %p} ET</td></tr>")
    plays_t = ("<thead><tr><th>Date</th><th>Game</th><th>Play</th><th>Book</th><th class='r'>Edge</th><th class='r'>Close</th>"
               "<th class='r'>CLV</th><th>Result</th><th class='r'>Units</th>"
               "<th class='hide-sm'>Logged</th></tr></thead><tbody>" + "".join(plays) + "</tbody>") if plays else \
        "<tbody><tr><td class='empty'>No placed bets yet.</td></tr></tbody>"

    notes = "".join(f"<li><b>{html.escape(a['date'])}</b>: {html.escape(a['text'])}</li>" for a in reversed(ann))
    disc = (f"<li><a href='{html.escape(links['discord_invite'])}'>Discord channel</a>: every play posted when it was "
            f"logged, with its result and any correction. Posts are never edited.</li>") if links.get("discord_invite") else \
        "<li>Discord channel: every play posted when it was logged, with its result and any correction (invite on request).</li>"
    verify = (f"<li><a href='{GH}/blob/{BRANCH}/bets/bets.csv'>The bet log</a> and "
              f"<a href='{GH}/commits/{BRANCH}/bets/bets.csv'>every change to it</a>, each with its time.</li>"
              f"<li><a href='{GH}/blob/{BRANCH}/bets/bets.csv.ots'>OpenTimestamps proof</a>: anchors the current bet log "
              f"to a Bitcoin block (check it at <a href='https://opentimestamps.org'>opentimestamps.org</a> with the log file).</li>"
              + disc)

    coh_table, coh_note = cohorts(b)
    now = pd.Timestamp.now(tz="America/New_York")
    style = report_html.TEMPLATE[report_html.TEMPLATE.index("<style>"):report_html.TEMPLATE.index("</style>") + 8]
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Off The Glass · College Basketball Record</title>
<meta property="og:title" content="Off The Glass · College Basketball Record">
{report_html.HEAD}
{style}
<header class="top"><div class="wrap">
  {report_html.BRAND}
  <nav class="tabs" aria-label="Sport"><a href="{report_html.NFL_SITE}">NFL</a>{report_html.NBA_TAB}<a href="./" aria-current="page"><span class="hide-sm">College Basketball</span><span class="show-sm">CBB</span></a></nav>
</div></header>
<main class="wrap">
  <img class="hero" src="assets/otg-banner.webp" alt="Off The Glass Hoops" width="2000" height="667">
  <div class="head"><div><h1>College Basketball Record</h1>
    <div class="sub">Bets placed on the model's plays, at the logged number and price. Updated {now:%b %-d, %-I:%M %p} ET.</div></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap"><a class="pagebtn" href="./">&larr; Card</a><a class="pagebtn" href="record/charts.html">Charts</a></div></div>
  <div class="kpis">{kpis}</div>
  <section class="panel"><div class="panel-h"><h2>Summary</h2><span class="note">Settled bets placed. CLV = points the line moved our way from the logged number to the close (the forward test's primary close: each book's last fresh quote in the 15 minutes before tip, median). Break-even at -110 is 52.4%.</span></div>
    <div class="scroll"><table>{HEAD}<tbody>{''.join(rows)}</tbody></table></div>{_chart(s)}</section>
  {f"<section class='panel'><div class='panel-h'><h2>By month</h2></div><div class='scroll'><table>{HEAD}<tbody>{months}</tbody></table></div></section>" if months else ""}
  <section class="panel"><div class="panel-h"><h2>Bets placed</h2><span class="note">Newest first.</span></div>
    <div class="scroll"><table>{plays_t}</table></div></section>
  <footer>
    <div><a class="follow" href="https://x.com/{report_html.X_HANDLE}" target="_blank" rel="noopener"><img src="assets/otg-logo-512.png" alt="">Follow @{report_html.X_HANDLE} on X for every play</a></div>
    <div style="margin-top:10px"><a class="m" href="record/verify.html">verification</a></div></footer>
</main>
<script>
// phones: each table row becomes a small card, each cell labeled with its column header (styles in report_html)
document.querySelectorAll("main table").forEach((t) => {{
  const hs = [...t.querySelectorAll("thead th")].map((h) => h.textContent.trim());
  t.classList.add("stack");
  t.querySelectorAll("tbody tr").forEach((r) => [...r.children].forEach((c, k) => {{ if (hs[k]) c.dataset.l = hs[k]; }}));
}});
</script>
</html>
"""


def build_verify() -> str:
    """The unlisted verification page (record/verify.html; linked only from the record page's footer): the
    forward-test cohorts, the bet log and its history, the OpenTimestamps proof, and every model-change note."""
    b = clv_primary.attach(tracker.load())
    links = json.load(open(LINKS)) if os.path.exists(LINKS) else {}
    ap = os.path.join(tracker.ROOT, "bets", "announcements.json")
    ann = json.load(open(ap)) if os.path.exists(ap) else []
    coh_table, coh_note = cohorts(b)
    disc = (f"<li><a href='{html.escape(links['discord_invite'])}'>Discord channel</a>: every play posted when it was "
            f"logged, with its result and any correction. Posts are never edited.</li>") if links.get("discord_invite") else ""
    notes = "".join(f"<li><b>{html.escape(a['date'])}</b>: {html.escape(a['text'])}</li>" for a in reversed(ann))
    freeze = ""
    mf = os.path.join(tracker.ROOT, "MODEL_FREEZE.md")
    if os.path.exists(mf):
        c = next((l.split(":", 1)[1].strip() for l in open(mf) if l.startswith("Frozen at commit:")), "")
        freeze = (f"<li><a href='{GH}/blob/{BRANCH}/MODEL_FREEZE.md'>Model freeze</a>: frozen at commit "
                  f"<a href='{GH}/commit/{c}'><code>{c[:7]}</code></a>, with file fingerprints.</li>") if c else ""
    now = pd.Timestamp.now(tz="America/New_York")
    style = report_html.TEMPLATE[report_html.TEMPLATE.index("<style>"):report_html.TEMPLATE.index("</style>") + 8]
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<base href="../">
<meta name="robots" content="noindex">
<title>Off The Glass · Verification</title>
{report_html.HEAD}
{style}
<header class="top"><div class="wrap">
  {report_html.BRAND}
</div></header>
<main class="wrap">
  <div class="head"><div><h1>Verification</h1>
    <div class="sub">How to check the College Basketball record yourself. Updated {now:%b %-d, %-I:%M %p} ET.</div></div><a class="pagebtn" href="record.html">&larr; Record</a></div>
  <section class="panel"><div class="panel-h"><h2>Forward-test cohorts</h2><span class="note">{html.escape(coh_note)}</span></div>
    <div class="scroll"><table>{coh_table}</table></div></section>
  <section class="panel"><div class="panel-h"><h2>Check it</h2></div><ul style="margin:12px 16px 16px;padding-left:18px;line-height:1.7">
    <li><a href='{GH}/blob/{BRANCH}/bets/bets.csv'>The bet log</a> and <a href='{GH}/commits/{BRANCH}/bets/bets.csv'>every change to it</a>, each with its time.</li>
    <li><a href='{GH}/blob/{BRANCH}/bets/bets.csv.ots'>OpenTimestamps proof</a>: anchors the current bet log to a Bitcoin block (check it at <a href='https://opentimestamps.org'>opentimestamps.org</a> with the log file).</li>
    <li><a href='{GH}/commits/{BRANCH}/site/record/weekly'>Every weekly chart</a>, committed by the Monday run with the data it was drawn from.</li>
    {freeze}{disc}</ul></section>
  <section class="panel"><div class="panel-h"><h2>Model changes</h2><span class="note">Every change, as announced the day it went live.</span></div>
    <ul style="margin:12px 16px 16px;padding-left:18px;line-height:1.6">{notes or "<li>None.</li>"}</ul></section>
</main>
<script>
document.querySelectorAll("main table").forEach((t) => {{
  const hs = [...t.querySelectorAll("thead th")].map((h) => h.textContent.trim());
  t.classList.add("stack");
  t.querySelectorAll("tbody tr").forEach((r) => [...r.children].forEach((c, k) => {{ if (hs[k]) c.dataset.l = hs[k]; }}));
}});
</script>
</html>
"""


def write() -> str:
    with open(OUT, "w") as fh:
        fh.write(build())
    with open(VERIFY, "w") as fh:
        fh.write(build_verify())
    os.makedirs(os.path.dirname(CHARTS), exist_ok=True)
    with open(CHARTS, "w") as fh:
        fh.write(build_charts())
    return OUT


if __name__ == "__main__":
    print(write())
