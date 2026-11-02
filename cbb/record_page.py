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

from . import autorefresh, clv_primary, report_html, tracker

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
    cv = clv_primary.coverage(s)   # primary close; decided plays with a close; missing counted, never zero
    return {"bets": int(len(s)), "rec": f"{w}-{l}" + (f"-{p}" if p else ""), "win": w / (w + l) if w + l else None,
            "units": units, "roi": units / staked if staked else None, "clv": cv["clv"], "beat": cv["beat"],
            "cov": f"{cv['with_close']}/{cv['decided']}" if cv["decided"] else "–", "cv": cv}


def _na(r) -> str:
    """'n/a' with the reason a settled play has no primary close (open plays show a dash)."""
    if r.get("status") != "settled":
        return "–"
    return f"<span title='{html.escape(str(r.get('clv_reason') or 'no primary close'))}'>n/a</span>"


def _close_cell(r) -> str:
    """The primary (consensus) close with its book count and quote ages, or n/a with the reason."""
    if r.get("status") != "settled" or pd.isna(r.get("close_line")):
        return _na(r)
    ages = ", ".join(f"{a} s" for a in json.loads(r.get("feed_age_s") or "[]"))
    nb = int(r["books_primary"])
    try:
        px = "; prices " + ", ".join(f"{q['book']} {q['line']:g} {q['price']:+.0f}" if q.get("price") is not None
                                    else f"{q['book']} {q['line']:g}" for q in json.loads(r.get("price_vs_close") or "[]"))
    except (TypeError, ValueError):
        px = ""
    return (f"<span title='{nb} book(s), quote ages {html.escape(ages)}{html.escape(px)}'>{r['close_line']:g}"
            f"<small> ({nb}{' book: one-book close' if nb == 1 else ''}; pregame "
            f"{html.escape(str(r.get('pregame_check') or 'not checked'))})</small></span>")


def _row(label: str, s: dict) -> str:
    cls = "pos" if s["units"] > 0 else "neg" if s["units"] < 0 else ""
    return (f"<tr><td class='b'>{html.escape(label)}</td><td class='r'>{s['bets']}</td><td class='r'>{s['rec']}</td>"
            f"<td class='r'>{_num(s['win'], '{:.1%}')}</td><td class='r {cls}'>{_num(s['units'])}</td>"
            f"<td class='r'>{_num(s['roi'], '{:+.1%}')}</td><td class='r'>{_num(s['clv'])}</td>"
            f"<td class='r'>{_num(s['beat'], '{:.0%}')}</td><td class='r'>{s['cov']}</td></tr>")


HEAD = ("<thead><tr><th></th><th class='r'>Plays</th><th class='r'>W-L</th><th class='r'>Win %</th><th class='r'>Units</th>"
        "<th class='r'>ROI</th><th class='r'>Alert CLV pts</th><th class='r'>Beat close</th><th class='r'>Close coverage</th></tr></thead>")


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


FE_START = pd.Timestamp("2026-10-26T19:20:50Z")   # audit/forward_eval.PROTOCOL_START (model v1 cohort start)


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
        cv = clv_primary.coverage(s_)   # primary close; for C the accepted number is graded against it (clv_pts set below)
        return (f"<td class='r'>{len(d)}</td><td class='r'>{len(s_)}</td><td class='r'>{w}-{l}-{p}</td>"
                f"<td class='r'>{_num(w / (w + l) if w + l else None, '{:.1%}')}</td><td class='r'>{_num(u)}</td>"
                f"<td class='r'>{_num(cv['clv'])}</td><td class='r'>{cv['with_close']}/{cv['decided']}</td>")

    v1 = a["cohort"] == "v1" if "cohort" in a else pd.Series(True, index=a.index)
    if len(c):   # cohort C: the accepted number against the same primary close (alert CLV is cohort A's)
        c = c.assign(clv_pts=clv_primary.accepted_clv(
            b, pd.DataFrame({"bet_id": c["bet_id"], "line": c["line_acc"]}, index=c.index)).to_numpy())
    cv1 = c[c["bet_id"].isin(a.loc[v1, "bet_id"])] if len(c) else c
    empty = "<td class=r>0</td>" + "<td></td>" * 6
    rows = (f"<tr><td class='b'>A. Every model v1 signal (alert number)</td>{col(a[v1])}</tr>"
            f"<tr><td class='b'>B. v1, fresh observed quote at the logged book and number</td>{col(a[v1 & fresh])}</tr>"
            f"<tr><td class='b'>C. v1, confirmed accepted bets (accepted number)</td>{col(cv1) if len(cv1) else empty}</tr>"
            f"<tr><td class='b'>Pre-freeze signals (reported separately, never pooled)</td>{col(a[~v1])}</tr>")
    head = ("<thead><tr><th>Cohort</th><th class='r'>Signals</th><th class='r'>Settled</th><th class='r'>W-L-P</th>"
            "<th class='r'>Win %</th><th class='r'>Units (logged price)</th><th class='r'>CLV pts (A, B: alert; C: accepted)</th>"
            "<th class='r'>Close coverage</th></tr></thead>")
    nop = int(pd.to_numeric(a["odds"], errors="coerce").isna().sum())
    note = (f"A, B and C are model v1 signals (logged from {FE_START:%b %-d, %H:%M} UTC); {int((~v1).sum())} pre-freeze "
            f"signal(s) are shown on their own row. CLV is against the protocol's primary close for every row (A and B at "
            f"the alert number, C at the accepted number); close coverage = decided plays with a primary close. "
            f"Units use the recorded price; {nop} signal(s) without one are counted at -110 here and are left out of "
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
    <div style="display:flex;gap:8px;flex-wrap:wrap"><a class="pagebtn" href="./">&larr; Card</a><a class="pagebtn" href="record.html">Record</a><a class="pagebtn" href="record/survivor.html">Survivor</a></div></div>
  {weekly()}
  <footer>
    <div><a class="follow" href="https://x.com/{report_html.X_HANDLE}" target="_blank" rel="noopener"><img src="assets/otg-logo-512.png" alt="">Follow @{report_html.X_HANDLE} on X for every play</a></div></footer>
</main>
</html>
"""


def _controls(tid: str) -> str:
    """Filter chips (result, market) and a running total for one plays table; sorting is on its column headers."""
    chip = lambda grp, v, t, on=False: (f"<button type='button' class='fchip' data-grp='{grp}' data-v='{v}' "
                                        f"aria-pressed='{'true' if on else 'false'}'>{t}</button>")
    return (f"<div class='recctl' data-for='rec-{tid}'><div class='fgrp' role='group' aria-label='Result'>"
            + chip("res", "", "All", True) + chip("res", "W", "Wins") + chip("res", "L", "Losses") + chip("res", "P", "Pushes")
            + chip("res", "O", "Open") + "</div><div class='fgrp' role='group' aria-label='Market'>"
            + chip("mk", "", "All", True) + chip("mk", "spread", "Spreads") + chip("mk", "total", "Totals")
            + "</div><span class='rectot m'></span></div>")


RECORD_CSS = """<style>
.wrap { max-width: 1600px }
table.rec td { white-space: normal } table.rec td:nth-child(1), table.rec td:nth-child(5), table.rec td:nth-child(7),
table.rec td:nth-child(9), table.rec td:nth-child(10) { white-space: nowrap }
table.rec th[data-k] { cursor: pointer; user-select: none } table.rec th[data-k]:hover { color: var(--text) }
table.rec th[aria-sort='ascending']::after { content: " \\25B2"; font-size: 9px }
table.rec th[aria-sort='descending']::after { content: " \\25BC"; font-size: 9px }
.recctl { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; padding: 10px 16px; border-bottom: 1px solid var(--line) }
.fgrp { display: flex; flex-wrap: wrap; gap: 6px }
.fchip { font: inherit; font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 999px; border: 1px solid var(--line-strong);
  background: var(--surface); color: var(--muted); cursor: pointer }
.fchip[aria-pressed='true'] { background: var(--text); border-color: var(--text); color: var(--bg) }
.rectot { font-size: 12px; margin-left: auto }
@media (max-width: 860px) { .rectot { margin-left: 0; width: 100% } }
</style>"""

# sort + filter for table.rec (keys in each row's data- attributes); the sort is kept per table in this browser
RECORD_JS = """<script>
document.querySelectorAll("table.rec").forEach((t) => {
  const tb = t.tBodies[0], rows = [...tb.rows].filter((r) => r.dataset.date !== undefined);
  if (!rows.length) return;
  const ctl = document.querySelector(".recctl[data-for='" + t.id + "']");
  const KEY = "otg-rec-sort:" + t.id, NUM = ["edge", "close", "clv", "sb", "units"];
  const RES = {W: 0, L: 1, P: 2, O: 3};
  let sort = {k: "date", dir: -1};
  try { const v = JSON.parse(localStorage.getItem(KEY) || "null"); if (v && v.k) sort = v; } catch (e) {}
  const f = {res: "", mk: ""};
  const val = (r, k) => { const v = r.dataset[k] ?? "";
    if (k === "res") return RES[v] ?? 9;
    if (NUM.includes(k)) return v === "" ? null : Number(v);
    return v.toLowerCase(); };
  const render = () => {
    const vis = rows.filter((r) => (!f.res || r.dataset.res === f.res) && (!f.mk || r.dataset.mk === f.mk));
    vis.sort((a, b) => { const x = val(a, sort.k), y = val(b, sort.k);
      if (x === null && y === null) return 0; if (x === null) return 1; if (y === null) return -1;
      return (x < y ? -1 : x > y ? 1 : 0) * sort.dir || (a.dataset.date < b.dataset.date ? 1 : -1); });
    rows.forEach((r) => { r.hidden = true; });
    vis.forEach((r) => { r.hidden = false; tb.appendChild(r); });
    t.querySelectorAll("th[data-k]").forEach((h) => h.setAttribute("aria-sort", h.dataset.k === sort.k ? (sort.dir > 0 ? "ascending" : "descending") : "none"));
    if (ctl) {
      const s = vis.filter((r) => ["W", "L", "P"].includes(r.dataset.res));
      const n = (c) => s.filter((r) => r.dataset.res === c).length;
      const u = s.reduce((a, r) => a + (Number(r.dataset.units) || 0), 0);
      const st = s.reduce((a, r) => a + (Number(r.dataset.stake) || 1), 0);
      ctl.querySelector(".rectot").textContent = "Showing " + vis.length + " of " + rows.length +
        (s.length ? " · " + n("W") + "-" + n("L") + (n("P") ? "-" + n("P") : "") + " · " + (u > 0 ? "+" : u < 0 ? "−" : "") +
          Math.abs(u).toFixed(2) + " u · ROI " + (u / st * 100).toFixed(1) + "%" : "");
    }
  };
  t.querySelectorAll("th[data-k]").forEach((h) => {
    const go = () => { const k = h.dataset.k;
      sort = sort.k === k ? {k, dir: -sort.dir} : {k, dir: ["date", "logged", "edge", "clv", "sb", "units", "close"].includes(k) ? -1 : 1};
      try { localStorage.setItem(KEY, JSON.stringify(sort)); } catch (e) {}
      render(); };
    h.addEventListener("click", go);
    h.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
  });
  if (ctl) ctl.querySelectorAll(".fchip").forEach((b) => b.addEventListener("click", () => {
    f[b.dataset.grp] = b.dataset.v;
    ctl.querySelectorAll(".fchip[data-grp='" + b.dataset.grp + "']").forEach((x) => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
    render(); }));
  render();
});
</script>"""


def _plays_table(live: pd.DataFrame, empty: str) -> str:
    """Every play in `live`, newest first (the "Bets placed" table)."""
    plays = []
    for _, r in live.sort_values(["date", "logged_at"], ascending=False).iterrows():
        res = {"W": "<span class='pos b'>Win</span>", "L": "<span class='neg b'>Loss</span>", "P": "Push"}.get(
            str(r["result"]), "Open")
        units = _num(float(r["profit"])) if r["status"] == "settled" else "–"
        logged = pd.Timestamp(r["logged_at"]).tz_convert("America/New_York")
        res_k = {"W": "W", "L": "L", "P": "P"}.get(str(r["result"]), "O")
        keys = {"date": f"{r['date']} {r['logged_at']}", "game": f"{r['away']} at {r['home']}", "play": str(r["pick"]),
                "book": str(r["book"]), "edge": r["edge"], "close": r.get("close_line"), "clv": r.get("clv_pts"),
                "sb": r.get("clv_same_book"), "res": res_k, "units": r["profit"] if r["status"] == "settled" else None,
                "logged": str(r["logged_at"]), "mk": r["market"], "stake": r["stake"]}
        attrs = " ".join(f"data-{k}='{html.escape('' if v is None or (isinstance(v, float) and np.isnan(v)) else str(v))}'"
                         for k, v in keys.items())
        plays.append(
            f"<tr {attrs}><td class='m'>{r['date']}</td><td>{_logo(r['away_id'])}{html.escape(str(r['away']))} at {_logo(r['home_id'])}{html.escape(str(r['home']))}</td>"
            f"<td class='b'>{html.escape(str(r['pick']))}</td><td>{html.escape(str(r['book']))} "
            f"<span class='m'>{_num(r['odds'], '{:+.0f}')}</span></td><td class='r'>{_num(r['edge'], '{:.1f}')}</td>"
            f"<td class='r'>{_close_cell(r)}</td><td class='r'>{_num(r['clv_pts'], '{:+.2f}', _na(r))}</td>"
            f"<td class='r m hide-sm hide-md'>{_num(r.get('clv_same_book'), '{:+.2f}')}</td>"
            f"<td>{res}</td><td class='r'>{units}</td>"
            f"<td class='m hide-sm hide-md'>{logged:%b %-d %-I:%M %p} ET</td></tr>")
    th = lambda k, t, c="", tip="": (f"<th data-k='{k}' class='{c}' tabindex='0' role='button'"
                                       + (f" title='{tip}'" if tip else "") + f">{t}</th>")
    return ("<thead><tr>" + th("date", "Date") + th("game", "Game") + th("play", "Play") + th("book", "Book")
            + th("edge", "Edge", "r") + th("close", "Close", "r")
            + th("clv", "Alert CLV", "r", "Points the line moved our way from the alert number to the close (primary close)")
            + th("sb", "Same-book CLV", "r hide-sm hide-md", "Diagnostic only: the close at the play's own book")
            + th("res", "Result") + th("units", "Units", "r") + th("logged", "Logged", "hide-sm hide-md")
            + "</tr></thead><tbody>" + "".join(plays) + "</tbody>") if plays else \
        f"<tbody><tr><td class='empty'>{empty}</td></tr></tbody>"


def _band_b_section() -> str:
    """Band B (cbb/tracker.py BAND_B): its own summary and plays, never pooled with v1. Always shown (Chad, Oct 30),
    with an empty table until the first band B play."""
    b = tracker.load(tracker.BAND_B)
    b = clv_primary.attach(b) if len(b) else b.assign(clv_pts=np.nan, close_line=np.nan, clv_same_book=np.nan)
    live = b[(b["status"] != "void") & (b["placed"].astype(str).str.lower() != "no")]
    s = live[live["status"] == "settled"]
    rows = [_row("Band B spreads", summary(s))]

    return (f"<section class='panel'><div class='panel-h'><h2>Band B (spreads, edge 2-2.5, 0.5 u)</h2>"
            f"<span class='note'>A separate bet type on spreads only, not included in the record above: v1's edge of "
            f"2-2.49 points, with v1's +2% EV rule, 0.5 unit flat. Units are at the 0.5-unit stake.</span></div>"
            f"<div class='scroll'><table>{HEAD}<tbody>{''.join(rows)}</tbody></table></div>"
            f"{_controls('bandb') if len(live) else ''}<div class='scroll'><table class='rec' id='rec-bandb'>"
            f"{_plays_table(live, 'No band B plays yet.')}</table></div></section>")


def _linemove_section() -> str:
    """Line-move plays (opener rule, Nov 2): the plays logged before the rule that qualified only after the line moved
    (tracker.LINEMOVE), and the signals the rule has stopped since (research only, never bet; cbb/linemove.py). Their
    own cell, never pooled with v1 or band B."""
    from . import linemove
    b = tracker.load(tracker.LINEMOVE)
    b = clv_primary.attach(b) if len(b) else b.assign(clv_pts=np.nan, close_line=np.nan, clv_same_book=np.nan)
    live = b[(b["status"] != "void") & (b["placed"].astype(str).str.lower() != "no")]
    rows = [_row("Logged before Nov 2", summary(live[live["status"] == "settled"]))]
    try:
        g = linemove.graded()
        rows.append(_row("Stopped since Nov 2*", linemove.summary(g)))
        n_sig = len(g)
    except Exception as e:
        print(f"Line-move research cell failed ({e}); continuing.")
        n_sig = 0
    return (f"<section class='panel'><div class='panel-h'><h2>Line-move plays (separate)</h2>"
            f"<span class='note'>Plays that qualified only after the line moved against the model, not at the opener. "
            f"From Nov 2 the card logs only plays that also qualify at the opener; the ones logged before stay as "
            f"logged and are graded here, never in the record above. *Signals stopped since the rule: graded at the "
            f"number and price they would have been bet at ({n_sig} so far); close = median of the books' last pregame "
            f"number (closing.csv).</span></div>"
            f"<div class='scroll'><table>{HEAD}<tbody>{''.join(rows)}</tbody></table></div>"
            f"{_controls('lm') if len(live) else ''}<div class='scroll'><table class='rec' id='rec-lm'>"
            f"{_plays_table(live, 'No line-move plays.')}</table></div></section>")


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
          ("ROI", _num(tot["roi"], "{:+.1%}")),
          ("Alert CLV", _num(tot["clv"], "{:+.2f} pts") + f"<small>{html.escape(clv_primary.coverage_text(tot['cv']))} · "
                      f"{html.escape(clv_primary.VERIFICATION_STATUS)}</small>"),
          ("Open plays", str(int((live["status"] == "open").sum())))]
    kpis = "".join(f"<div class='kpi'><div class='k'>{k}</div><div class='v'>{v}</div></div>" for k, v in kp)

    rows = [_row("All bets", tot)]
    rows += [_row(lbl, summary(s[s["market"] == mk])) for mk, lbl in (("spread", "Spreads"), ("total", "Totals"))]
    months = ""
    if len(s):
        m = s.assign(mo=pd.to_datetime(s["date"]).dt.to_period("M"))
        months = "".join(_row(p.strftime("%b %Y"), summary(g)) for p, g in sorted(m.groupby("mo"), key=lambda x: x[0], reverse=True))

    plays_t = _plays_table(live, "No placed bets yet.")

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
{autorefresh.meta(autorefresh.stamp())}
{report_html.HEAD}
{style}
{RECORD_CSS}
<header class="top"><div class="wrap">
  {report_html.BRAND}
  <nav class="tabs" aria-label="Sport"><a href="{report_html.NFL_SITE}">NFL</a>{report_html.NBA_TAB}<a href="./" aria-current="page"><span class="hide-sm">College Basketball</span><span class="show-sm">CBB</span></a></nav>
</div></header>
<main class="wrap">
  <img class="hero" src="assets/otg-banner.webp" alt="Off The Glass Hoops" width="2000" height="667">
  <div class="head"><div><h1>College Basketball Record</h1>
    <div class="sub">Bets placed on the model's plays, at the logged number and price. Updated {now:%b %-d, %-I:%M %p} ET.</div></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap"><a class="pagebtn" href="./">&larr; Card</a><a class="pagebtn" href="record/charts.html">Charts</a><a class="pagebtn" href="record/survivor.html">Survivor</a></div></div>
  <div class="kpis">{kpis}</div>
  <section class="panel"><div class="panel-h"><h2>Summary</h2><span class="note">Settled bets placed. Alert CLV = points the line moved our way from the alert (logged) number to the close; prices are shown separately and not converted (the forward test's primary close: each book's last fresh quote in the 15 minutes before tip, median). Break-even at -110 is 52.4%.</span></div>
    <div class="scroll"><table>{HEAD}<tbody>{''.join(rows)}</tbody></table></div>{_chart(s)}</section>
  {f"<section class='panel'><div class='panel-h'><h2>By month</h2></div><div class='scroll'><table>{HEAD}<tbody>{months}</tbody></table></div></section>" if months else ""}
  <section class="panel"><div class="panel-h"><h2>Bets placed</h2><span class="note">Newest first.</span></div>
    {_controls('v1') if len(live) else ''}<div class="scroll"><table class="rec" id="rec-v1">{plays_t}</table></div></section>{_band_b_section()}{_linemove_section()}
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
{RECORD_JS}
{autorefresh.SCRIPT}</html>
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
    try:   # the per-play primary-close table (books, quote ages, status and reason): bets/clv_primary.csv
        clv_primary.write()
    except Exception as e:
        print(f"CLV table failed ({e}); continuing.")
    try:   # band B's own per-play table (bets/clv_primary_bandB.csv); v1's table above is unchanged
        bb = tracker.load(tracker.BAND_B)
        if len(bb):
            clv_primary.primary(bb).to_csv(os.path.join(tracker.ROOT, "bets", "clv_primary_bandB.csv"), index=False)
    except Exception as e:
        print(f"Band B CLV table failed ({e}); continuing.")
    try:   # tip-time review before tip: open bets whose cutoff and ESPN / latest feed start differ by over 10 min
        from . import tipcheck
        tipcheck.check()
    except Exception as e:
        print(f"Tip-time check failed ({e}); continuing.")
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
