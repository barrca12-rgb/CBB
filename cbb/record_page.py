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

from . import report_html, tracker

OUT = os.path.join(tracker.ROOT, "reports", "record.html")
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


def build() -> str:
    b = tracker.load()
    live = b[b["status"] != "void"]
    s = live[live["status"] == "settled"]
    placed = s[s["placed"].astype(str).str.lower() != "no"]
    tot = summary(s)
    links = json.load(open(LINKS)) if os.path.exists(LINKS) else {}
    ann = json.load(open(os.path.join(tracker.ROOT, "bets", "announcements.json"))) \
        if os.path.exists(os.path.join(tracker.ROOT, "bets", "announcements.json")) else []

    kp = [("Record", tot["rec"]), ("Win %", _num(tot["win"], "{:.1%}")), ("Units", _num(tot["units"])),
          ("ROI", _num(tot["roi"], "{:+.1%}")), ("Avg CLV", _num(tot["clv"], "{:+.2f} pts")),
          ("Open plays", str(int((live["status"] == "open").sum())))]
    kpis = "".join(f"<div class='kpi'><div class='k'>{k}</div><div class='v'>{v}</div></div>" for k, v in kp)

    rows = [_row("All plays", tot), _row("Placed only", summary(placed))]
    rows += [_row(lbl, summary(s[s["market"] == mk])) for mk, lbl in (("spread", "Spreads"), ("total", "Totals"))]
    months = ""
    if len(s):
        m = s.assign(mo=pd.to_datetime(s["date"]).dt.to_period("M"))
        months = "".join(_row(p.strftime("%b %Y"), summary(g)) for p, g in sorted(m.groupby("mo"), key=lambda x: x[0], reverse=True))

    plays = []
    mine = b[(b["status"] != "void") & (b["placed"].astype(str).str.lower() == "yes")]   # bets Chad placed
    for _, r in mine.sort_values(["date", "logged_at"], ascending=False).iterrows():
        res = {"W": "<span class='pos b'>Win</span>", "L": "<span class='neg b'>Loss</span>", "P": "Push"}.get(
            str(r["result"]), "Open")
        units = _num(float(r["profit"])) if r["status"] == "settled" else "–"
        logged = pd.Timestamp(r["logged_at"]).tz_convert("America/New_York")
        plays.append(
            f"<tr><td class='m'>{r['date']}</td><td>{html.escape(str(r['away']))} at {html.escape(str(r['home']))}</td>"
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
<title>CBB Model Record</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">
{style}
<header class="top"><div class="wrap">
  <a class="brand" href="https://barrca12-rgb.github.io/" style="color:inherit;text-decoration:none">Model Card</a>
  <nav class="tabs" aria-label="Pages"><a href="{report_html.NFL_SITE}">NFL</a><a href="./"><span class="hide-sm">College Basketball</span><span class="show-sm">CBB</span></a><a href="record.html" aria-current="page">Record</a></nav>
</div></header>
<main class="wrap">
  <div class="head"><div><h1>CBB model record</h1>
    <div class="sub">Every play the model logged, as logged, whether or not it was bet. Updated {now:%b %-d, %-I:%M %p} ET.</div></div></div>
  <div class="kpis">{kpis}</div>
  <section class="panel"><div class="panel-h"><h2>Summary</h2><span class="note">Settled plays. CLV = points the line moved our way from the logged number to the close. Break-even at -110 is 52.4%.</span></div>
    <div class="scroll"><table>{HEAD}<tbody>{''.join(rows)}</tbody></table></div>{_chart(s)}</section>
  <section class="panel"><div class="panel-h"><h2>Signals, quotes and accepted bets</h2><span class="note">{html.escape(coh_note)}</span></div>
    <div class="scroll"><table>{coh_table}</table></div></section>
  {f"<section class='panel'><div class='panel-h'><h2>By month</h2></div><div class='scroll'><table>{HEAD}<tbody>{months}</tbody></table></div></section>" if months else ""}
  <section class="panel"><div class="panel-h"><h2>Bets placed</h2><span class="note">Newest first. Every logged play, including ones not bet and voided ones, is in the bet log and on Discord (below).</span></div>
    <div class="scroll"><table>{plays_t}</table></div></section>
  <section class="panel"><div class="panel-h"><h2>Check it</h2></div><ul style="margin:12px 0;padding:0 16px 0 34px;line-height:1.7">{verify}</ul></section>
  {f"<section class='panel'><div class='panel-h'><h2>Model changes</h2><span class='note'>Announced the day each went live</span></div><ul style='margin:12px 0;padding:0 16px 0 34px;line-height:1.6'>{notes}</ul></section>" if notes else ""}
  <footer>Plays come from the model's card, logged automatically at the posted number and price. Results are graded against final scores; closing lines are the median of the tracked books.</footer>
</main>
</html>
"""


def write() -> str:
    with open(OUT, "w") as fh:
        fh.write(build())
    return OUT


if __name__ == "__main__":
    print(write())
