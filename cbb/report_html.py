"""Daily CBB bet card as a self-contained HTML page: today's plays, the odds board, the record and the ratings.

Laid out like a sportsbook odds screen: one typeface with tabular figures, neutral surfaces, color only where it
means something (best number, edge, win/loss). Light and dark follow the viewer's system setting. The Update button
works like the NFL card's (GitHub Actions workflow dispatch with a token kept in the browser). No external
dependencies except the Inter font (with system fallbacks).
"""
from __future__ import annotations

import html
import json
import math

import numpy as np
import pandas as pd

REPO = "barrca12-rgb/CBB"
NFL_SITE = "https://barrca12-rgb.github.io/NFL/"
SITE_URL = "https://barrca12-rgb.github.io/CBB/"
X_HANDLE = "OffTheGlassHQ"
# Off The Glass brand: shared <head> for the card and the record page (icons, link previews on X, fonts)
HEAD = f"""<meta name="description" content="Off The Glass: a college basketball betting model. Every play logged at the posted number, graded in public.">
<meta name="theme-color" content="#0A2C49">
<link rel="icon" type="image/png" sizes="32x32" href="assets/favicon-32.png">
<link rel="icon" type="image/png" sizes="64x64" href="assets/favicon-64.png">
<link rel="apple-touch-icon" href="assets/apple-touch-icon.png">
<meta property="og:site_name" content="Off The Glass">
<meta property="og:type" content="website">
<meta property="og:image" content="{SITE_URL}assets/otg-social.jpg">
<meta property="og:description" content="College basketball model: every play logged at the posted number, graded in public.">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@{X_HANDLE}">
<meta name="twitter:image" content="{SITE_URL}assets/otg-social.jpg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Graduate&family=Inter:wght@400;500;600;700;800&display=swap">"""
BRAND = ('<a class="brand" href="./" aria-label="Off The Glass home"><img src="assets/otg-logo-512.png" alt="" width="34" height="34">'
         '<span class="wordmark">Off The Glass</span></a>')


def _clean(v):
    if v is None:
        return None
    if isinstance(v, list):
        return [{k: _clean(x) for k, x in o.items()} for o in v]
    if isinstance(v, (np.floating, float)):
        return None if math.isnan(v) else round(float(v), 3)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return v if isinstance(v, (int, str, bool)) else str(v)


def build(card: pd.DataFrame, rt: pd.DataFrame, day: pd.Timestamp, season: int, replay: bool = False,
          record: dict | None = None) -> str:
    games = [{k: _clean(v) for k, v in r.items()} for r in card.to_dict("records")]
    t = rt.reset_index(names="espn_id")
    t["rank"] = range(1, len(t) + 1)
    rat = [{k: _clean(v) for k, v in r.items()} for r in
           t[["rank", "team", "net", "adj_oe", "adj_de", "adj_tempo"]].to_dict("records")]
    data = {"date": f"{day:%Y-%m-%d}", "season": season, "replay": replay, "repo": REPO, "nfl": NFL_SITE,
            "generated_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"), "games": games, "ratings": rat,
            "record": {"status": record["status"], "tripwire": record.get("tripwire"),
                       "recent": [{k: _clean(v) for k, v in r.items()} for r in record["recent"]],
                       "review": json.loads(json.dumps(record.get("review") or {}, default=_clean))}
            if record else None}
    payload = json.dumps(data).replace("</", "<\\/")
    title = f"Off The Glass · College Basketball · {day:%a %b} {day.day}"
    return (TEMPLATE.replace("__HEAD__", HEAD).replace("__BRAND__", BRAND).replace("__X__", X_HANDLE)
            .replace("__TITLE__", html.escape(title)).replace("__DATA__", payload))


TEMPLATE = r"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<meta property="og:title" content="__TITLE__">
__HEAD__
<style>
:root {
  --bg: #fbf6ea; --surface: #ffffff; --sunken: #f7f0e1; --line: #ebe1cd; --line-strong: #d9cbb0;
  --text: #0a2c49; --muted: #56627a; --faint: #8a93a3;
  --accent: #b84a08; --pos: #0f7b4b; --pos-bg: #e6f4ed; --neg: #c2352b; --warn: #8a5a00; --warn-bg: #fbf0d9;
  --brand: #fd6c0f; --bar: #0a2c49; --bar-text: #fbf6ea; --bar-muted: #b7c3d3;
  --font: "Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --display: "Graduate", "Rockwell", Georgia, serif;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #08090b; --surface: #12151a; --sunken: #181c22; --line: #242a33; --line-strong: #333b46;
    --text: #f6eedd; --muted: #a8b0bc; --faint: #6f7886;
    --accent: #ff8a3d; --pos: #3ccf8e; --pos-bg: #12301f; --neg: #ff6b5e; --warn: #f0b44a; --warn-bg: #33270f;
    --brand: #fd6c0f; --bar: #000000; --bar-text: #f6eedd; --bar-muted: #9aa2ae;
    color-scheme: dark;
  }
}
* { box-sizing: border-box }
.show-sm { display: none }
body { margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 var(--font); font-feature-settings: "tnum" 1, "cv11" 1; -webkit-font-smoothing: antialiased }
a { color: var(--accent); text-decoration: none } a:hover { text-decoration: underline }
.wrap { max-width: 1200px; margin: 0 auto; padding: 0 16px }

/* Top bar */
.top { background: var(--bar); border-bottom: 3px solid var(--brand); position: sticky; top: 0; z-index: 5 }
.top .wrap { display: flex; align-items: center; gap: 22px; height: 58px }
.brand { display: flex; align-items: center; gap: 10px; white-space: nowrap; color: var(--bar-text); text-decoration: none }
.brand:hover { text-decoration: none }
.brand img { width: 34px; height: 34px; border-radius: 7px; display: block }
.wordmark { font-family: var(--display); font-size: 19px; letter-spacing: .02em; text-transform: uppercase; color: var(--bar-text); line-height: 1 }
.tabs { display: flex; gap: 2px; height: 100% }
.tabs a { display: flex; align-items: center; padding: 0 12px; color: var(--bar-muted); font-weight: 600; font-size: 13px; letter-spacing: .04em;
  text-transform: uppercase; border-bottom: 3px solid transparent; margin-bottom: -3px; text-decoration: none }
.tabs a:hover { color: var(--bar-text); text-decoration: none }
.tabs a[aria-current="page"] { color: var(--bar-text); border-bottom-color: var(--brand) }
.pagebtn { font-weight: 600; font-size: 13px; border: 1px solid var(--line-strong); border-radius: 6px; padding: 5px 12px; color: var(--text); background: var(--surface); text-decoration: none; white-space: nowrap }
.pagebtn:hover { background: var(--sunken); text-decoration: none }
.status { margin-left: auto; display: flex; align-items: center; gap: 12px; color: var(--bar-muted); font-size: 13px; min-width: 0 }
.status a { color: var(--bar-text) }
#upd-btn { background: transparent; color: var(--bar-text); border-color: rgba(251,246,234,.35) } #upd-btn:hover { background: rgba(251,246,234,.1) }
.status span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis }
button { font: inherit; font-weight: 600; font-size: 13px; color: var(--text); background: var(--surface); border: 1px solid var(--line-strong);
  border-radius: 6px; padding: 6px 12px; cursor: pointer } button:hover { background: var(--sunken) } button:disabled { opacity: .5; cursor: progress }

/* Page head */
.head { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 12px; padding: 24px 0 16px }
h1 { font-family: var(--display); font-weight: 400; font-size: 26px; letter-spacing: .01em; margin: 0; line-height: 1.15 }
.sub { color: var(--muted); margin-top: 2px }
.days { display: flex; gap: 4px; flex-wrap: wrap }
.days a { padding: 5px 10px; border-radius: 6px; color: var(--muted); font-weight: 500; font-size: 13px; text-decoration: none; border: 1px solid transparent }
.days a:hover { background: var(--sunken) }
.days a[aria-current="page"] { color: var(--text); border-color: var(--line-strong); background: var(--surface) }
.notice { border: 1px solid var(--line); background: var(--warn-bg); color: var(--warn); border-radius: 8px; padding: 10px 12px; margin-bottom: 16px; font-size: 13px }

/* KPI strip */
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); border: 1px solid var(--line); border-top: 3px solid var(--text); border-radius: 10px; background: var(--surface); margin-bottom: 24px; overflow: hidden; box-shadow: 0 1px 2px rgba(10,44,73,.06) }
.kpi { padding: 12px 16px; border-right: 1px solid var(--line) } .kpi:last-child { border-right: 0 }
.kpi .k { color: var(--muted); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em } .kpi .v { font-size: 21px; font-weight: 800; margin-top: 3px; letter-spacing: -.01em }
.kpi .v small { font-size: 12px; color: var(--muted); font-weight: 500; margin-left: 4px }

/* Panels and tables */
.panel { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; margin-bottom: 24px; overflow: hidden; box-shadow: 0 1px 2px rgba(10,44,73,.06) }
.panel-h { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; padding: 12px 16px; border-bottom: 1px solid var(--line) }
.panel-h h2 { font-size: 13px; font-weight: 800; margin: 0; text-transform: uppercase; letter-spacing: .07em; display: flex; align-items: center; gap: 8px }
.panel-h h2::before { content: ""; width: 4px; height: 14px; background: var(--brand); border-radius: 2px } .panel-h .note { color: var(--muted); font-size: 12px }
.scroll { overflow-x: auto }
table { width: 100%; border-collapse: collapse; font-size: 13px }
th { text-align: left; font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); padding: 8px 12px; border-bottom: 1px solid var(--line); background: var(--sunken); white-space: nowrap }
td { padding: 9px 12px; border-bottom: 1px solid var(--line); white-space: nowrap; vertical-align: middle }
tbody tr:last-child td { border-bottom: 0 }
.r { text-align: right } .c { text-align: center } .m { color: var(--muted) } .f { color: var(--faint) }
.pos { color: var(--pos) } .neg { color: var(--neg) } .b { font-weight: 600 }
.empty { padding: 28px 16px; color: var(--muted); text-align: center }
.betlink { font-weight: 600; font-size: 12px; border: 1px solid var(--line-strong); border-radius: 6px; padding: 4px 10px; color: var(--text); display: inline-block }
.betlink:hover { background: var(--sunken); text-decoration: none }
.tag { display: inline-block; font-size: 11px; font-weight: 600; padding: 1px 6px; border-radius: 4px; border: 1px solid var(--line-strong); color: var(--muted) }
.tag.bet { color: #fff; border-color: var(--brand); background: var(--brand) }

/* Segmented control */
.seg { display: inline-flex; border: 1px solid var(--line-strong); border-radius: 6px; overflow: hidden }
.seg button { border: 0; border-radius: 0; padding: 5px 12px; color: var(--muted); font-weight: 500; background: transparent }
.seg button + button { border-left: 1px solid var(--line-strong) }
.seg button[aria-pressed="true"] { background: var(--text); color: var(--surface) }
.ctrls { display: flex; flex-wrap: wrap; gap: 8px; align-items: center }
label.chk { display: inline-flex; gap: 6px; align-items: center; color: var(--muted); font-size: 13px; cursor: pointer }

/* Odds board: two rows per game (away, home) */
.board td { padding-top: 6px; padding-bottom: 6px }
.board tbody.g tr:first-child td { padding-top: 10px } .board tbody.g tr:last-child td { padding-bottom: 10px; border-bottom: 1px solid var(--line) }
.board tbody.g tr:first-child td { border-bottom: 0 }
.board tbody.g:last-child tr:last-child td { border-bottom: 0 }
.board .team { font-weight: 500 }
.inj { color: var(--warn); font-size: 11px; font-weight: 500; white-space: normal; max-width: 340px; margin-top: 1px } .board .tm { width: 72px; color: var(--muted); font-size: 12px }
.board .pts { color: var(--muted); width: 40px }
.odd { display: inline-flex; flex-direction: column; align-items: flex-end; min-width: 64px; padding: 3px 8px; border-radius: 6px; line-height: 1.25; color: var(--text); text-decoration: none }
.odd small { color: var(--faint); font-size: 11px }
a.odd:hover { background: var(--sunken); text-decoration: none }
.odd.best { background: var(--pos-bg); color: var(--pos) } .odd.best small { color: var(--pos) }
.na { color: var(--faint) }
.board th.bk, .board td.bk { text-align: right; width: 96px }
.board tbody.g.has-bet { background: linear-gradient(90deg, var(--brand) 0 3px, transparent 3px) }

details.panel > summary { list-style: none; cursor: pointer; padding: 12px 16px; font-weight: 600; font-size: 15px; display: flex; justify-content: space-between }
details.panel > summary::after { content: "Show"; color: var(--accent); font-size: 13px; font-weight: 500 }
details.panel[open] > summary::after { content: "Hide" }
details.panel[open] > summary { border-bottom: 1px solid var(--line) }
footer { color: var(--muted); font-size: 12px; padding: 8px 0 40px; max-width: 80ch }
.follow { display: inline-flex; align-items: center; gap: 8px; margin-top: 12px; font-weight: 700; color: var(--text) }
.follow img { width: 22px; height: 22px; border-radius: 5px }
.tl img { width: auto; vertical-align: -3px; margin-right: 5px; object-fit: contain }
.pick .tl img { vertical-align: -5px; margin-right: 6px }
.hero { display: block; height: 120px; width: auto; max-width: 100%; object-fit: contain; border-radius: 10px; margin-top: 18px; border: 1px solid var(--line) }
@media (max-width: 720px) { .hero { height: auto; width: 100% } }

@media (max-width: 720px) {
  .top .wrap { gap: 10px } .status span { display: none }
  .wordmark { display: none } .tabs a { padding: 0 8px; font-size: 12px }
  h1 { font-size: 21px }
  .kpi { border-right: 0; border-bottom: 1px solid var(--line) } .kpi:last-child { border-bottom: 0 }
  .hide-sm { display: none } .show-sm { display: inline }
  td, th { padding-left: 10px; padding-right: 10px }
  #t-plays td:first-child { white-space: normal; min-width: 150px }
}
</style>

<header class="top"><div class="wrap">
  __BRAND__
  <nav class="tabs" aria-label="Sport"><a id="nfl-link" href="#">NFL</a><a href="./" aria-current="page"><span class="hide-sm">College Basketball</span><span class="show-sm">CBB</span></a></nav>
  <div class="status"><span id="upd-status"></span><button id="upd-btn" type="button">Update</button></div>
</div></header>

<main class="wrap">
  <div class="head">
    <div><h1 id="h1"></h1><div class="sub" id="sub"></div></div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><nav class="days" id="days" aria-label="Days"></nav><a class="pagebtn" href="record.html">Record</a></div>
  </div>
  <div class="notice" id="replay" hidden>Replay of a past day using ESPN's stored closing lines. Prices and bet links appear on live cards only.</div>

  <div class="kpis" id="kpis"></div>

  <section class="panel" aria-labelledby="plays-h">
    <div class="panel-h"><h2 id="plays-h">Plays</h2><span class="note">Spread edge 2.5+ pts · total edge 3+ pts · +2% EV at the price · 1 unit each. Win % = backtest rate for that edge. Logged bets stay listed; their edge, win % and EV are at your number with today's model.</span></div>
    <div class="scroll"><table id="t-plays"></table></div>
  </section>

  <section class="panel" aria-labelledby="board-h">
    <div class="panel-h"><h2 id="board-h">Odds board</h2>
      <div class="ctrls">
        <div class="seg" role="group" aria-label="Market"><button data-m="spread" aria-pressed="true">Spread</button><button data-m="total">Total</button><button data-m="ml">Moneyline</button></div>
        <label class="chk"><input type="checkbox" id="only-plays"> Plays only</label>
      </div>
    </div>
    <div class="scroll"><table class="board" id="t-board"></table></div>
  </section>

  <section class="panel" aria-labelledby="watch-h" id="watch-sec">
    <div class="panel-h"><h2 id="watch-h">Watch list</h2><span class="note">Becomes a play if the line reaches the number shown.</span></div>
    <div class="scroll"><table id="t-watch"></table></div>
  </section>

  <section class="panel" aria-labelledby="rec-h" id="rec-sec" hidden>
    <div class="panel-h"><h2 id="rec-h">Record</h2><span class="note">Every play graded at the number it first appeared. CLV = points better than the closing line.</span></div>
    <div class="scroll"><table id="t-rec"></table></div>
  </section>

  <section class="panel" id="review-sec" hidden>
    <div class="panel-h"><h2>Loss review</h2><span class="note">Why bets lost. "Market disagreed" (the line moved against us with no news) are the real model misses; the rest is variance or late information.</span></div>
    <div class="scroll"><table id="t-review"></table></div>
    <div class="scroll"><table id="t-review2"></table></div>
    <div class="scroll"><table id="t-misses"></table></div>
  </section>

  <details class="panel" id="recent-sec" hidden><summary>Recent results</summary><div class="scroll"><table id="t-recent"></table></div></details>
  <details class="panel"><summary>Power ratings</summary><div class="scroll"><table id="t-rat"></table></div></details>

  <footer>
    <div><a class="follow" href="https://x.com/__X__" target="_blank" rel="noopener"><img src="assets/otg-logo-512.png" alt="">Follow @__X__ on X for every play</a></div>
  </footer>
</main>

<script id="data" type="application/json">__DATA__</script>
<script>
(() => {
  const D = JSON.parse(document.getElementById("data").textContent);
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const sgn = (x, d = 1) => x == null ? "–" : (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x).toFixed(d).replace(/\.0+$/, "");
  const ln = (x) => x == null ? "–" : Math.abs(x) < 0.05 ? "PK" : sgn(x);
  const num = (x, d = 1) => x == null ? "–" : Number(x).toFixed(d).replace(/\.0$/, "");
  // The half-point line a WATCH becomes a BET at (good_to is the exact number; books post halves).
  const gp = (o) => o == null ? "" : ", " + odds(o) + " or better";   // price a WATCH needs at that number
  const playAt = (v, higherBetter) => v == null ? null : (higherBetter ? Math.ceil(v * 2 - 1e-9) : Math.floor(v * 2 + 1e-9)) / 2;
  const watchTag = (text) => "<span class='tag'>Watch · " + text + "</span>";
  const odds = (x) => x == null ? "" : (x > 0 ? "+" : "−") + Math.abs(Math.round(x));
  const pct = (x) => x == null ? "–" : (100 * x).toFixed(1) + "%";
  const day = new Date(D.date + "T12:00:00");
  const tip = (g) => g.start ? new Date(g.start).toLocaleTimeString("en-US", {hour: "numeric", minute: "2-digit", timeZone: "America/New_York"}) : "";
  const matchup = (g) => g.away + (g.neutral ? " vs " : " @ ") + g.home;
  const logo = (id, px) => id == null ? "" : "<picture class='tl'><source media='(prefers-color-scheme: dark)' srcset='https://a.espncdn.com/i/teamlogos/ncaa/500-dark/" + Number(id) +
    ".png'><img src='https://a.espncdn.com/i/teamlogos/ncaa/500/" + Number(id) + ".png' alt='' loading='lazy' width='" + px + "' height='" + px +
    "' onerror=\"this.closest('picture').remove()\"></picture>";
  const matchupL = (g) => logo(g.away_id, 14) + esc(g.away) + (g.neutral ? " vs " : " @ ") + logo(g.home_id, 14) + esc(g.home);
  const pickId = (g, kind, side) => kind === "Spread" ? (side === "home" ? g.home_id : side === "away" ? g.away_id : null) : null;
  const BOOKS = ["FanDuel", "DraftKings", "BetMGM", "Caesars", "Fanatics", "bet365", "theScore Bet"];
  const bl = (g, bk) => (g.book_lines || []).find((x) => x.book === bk);

  $("nfl-link").href = D.nfl;
  $("h1").textContent = day.toLocaleDateString("en-US", {weekday: "long", month: "long", day: "numeric"});
  const withLines = D.games.filter((g) => g.n_books > 0).length;
  $("sub").textContent = D.games.length + " games · " + withLines + " with lines · " + (D.season - 1) + "–" + String(D.season).slice(2) + " season";
  $("replay").hidden = !D.replay;

  const navDays = (list, cur) => {
    $("days").innerHTML = list.slice(-7).map((d) => '<a href="cbb_' + d + '.html"' + (d === D.date ? ' aria-current="page"' : "") + ">" +
      new Date(d + "T12:00:00").toLocaleDateString("en-US", {weekday: "short", month: "short", day: "numeric"}) + "</a>").join("");
  };
  navDays([D.date]);
  fetch("days.json", {cache: "no-store"}).then((r) => r.json()).then((j) => navDays(j.days, j.current)).catch(() => {});

  // Plays
  const P = [];
  // A logged bet stays listed at the number it was logged at, with where the game stands now underneath.
  const logged = (g, mk) => {
    const pick = g[mk + "_logged_pick"];
    if (!pick) return false;
    const side = String(g[mk + "_logged_side"] || "").toLowerCase();
    const curSide = mk === "spread" ? g.spread_side : String(g.total_pick || "").toLowerCase();
    const still = g[mk + "_verdict"] === "BET" && curSide === side;
    // current line from the bet's side (the card's pick may now be the other team)
    const cur = mk === "spread" ? (g.spread_line == null ? null : ln(curSide === side ? g.spread_line : -g.spread_line))
      : (g.total_line == null ? null : num(g.total_line));
    const placed = String(g[mk + "_logged_placed"] || "").toLowerCase() === "yes";
    const now = still ? "still a play now at " + cur + " (" + g[mk + "_book"] + ")"
      : "line now " + (cur ?? "–") + ", not a play today · your bet stands";
    P.push({g, kind: mk === "spread" ? "Spread" : "Total", side, bet: pick, price: g[mk + "_logged_odds"], book: g[mk + "_logged_book"],
      link: still ? g[mk + "_link"] : null, warn: g[mk + "_warn"], edge: g[mk + "_now_edge"], p: g[mk + "_now_p"],
      ev: g[mk + "_now_ev"], model: mk === "spread" ? (side === "home" ? ln(-g.model_margin) : ln(g.model_margin)) : num(g.model_total),
      to: placed ? "Placed" : still ? (mk === "spread" ? ln(g.spread_good_to) : num(g.total_good_to)) : "–",
      open: mk === "spread" ? (g.open_home_spread != null ? ln(side === "home" ? g.open_home_spread : -g.open_home_spread) : null)
        : (g.open_total != null ? num(g.open_total) : null),
      units: g[mk + "_logged_stake"],
      bid: D.date + "|" + g.game_id + "|" + mk + "|" + side, placed,
      fill: {book: g[mk + "_logged_book"], line: g[mk + "_logged_line"], odds: g[mk + "_logged_odds"], stake: g[mk + "_logged_stake"]},
      status: "Logged at edge " + sgn(g[mk + "_logged_edge"]) + " · " + now});
    return true;
  };
  // Line shopping: every other book on the play's side, best number first, then best price.
  const others = (g, mk, side, used) => {
    const pay = (o) => o == null ? -1 : (o > 0 ? o / 100 : 100 / -o);
    const L = (g.book_lines || []).filter((x) => x.book !== used).map((x) => {
      if (mk === "spread") {
        if (x.home_spread == null) return null;
        const v = side === "home" ? x.home_spread : -x.home_spread;
        return {book: x.book, key: v, price: x[side + "_spread_odds"], txt: ln(v)};
      }
      if (x.total == null) return null;
      return {book: x.book, key: side === "over" ? -x.total : x.total, price: x[side + "_odds"], txt: (side === "over" ? "o" : "u") + num(x.total)};
    }).filter(Boolean).sort((p, q) => q.key - p.key || pay(q.price) - pay(p.price));
    return L.length ? "Also: " + L.map((x) => x.book + " " + x.txt + (x.price != null ? " (" + odds(x.price) + ")" : "")).join(" · ") : "";
  };
  D.games.forEach((g) => {
    const ls = logged(g, "spread"), lt = logged(g, "total");
    if (!ls && g.spread_verdict === "BET") P.push({g, kind: "Spread", side: g.spread_side, bet: g.spread_pick + " " + ln(g.spread_line), price: g.spread_odds, book: g.spread_book,
      link: g.spread_link, warn: g.spread_warn, edge: g.spread_edge, p: g.spread_p, ev: g.spread_ev, model: g.spread_side === "home" ? ln(-g.model_margin) : ln(g.model_margin), to: ln(g.spread_good_to),
      open: g.open_home_spread == null ? null : ln(g.spread_side === "home" ? g.open_home_spread : -g.open_home_spread), units: g.spread_units,
      also: others(g, "spread", g.spread_side, g.spread_book)});
    if (!lt && g.total_verdict === "BET") P.push({g, kind: "Total", bet: g.total_pick + " " + num(g.total_line), price: g.total_odds, book: g.total_book,
      link: g.total_link, warn: g.total_warn, edge: g.total_edge, p: g.total_p, ev: g.total_ev, model: num(g.model_total), to: num(g.total_good_to), open: g.open_total == null ? null : num(g.open_total), units: g.total_units,
      also: others(g, "total", String(g.total_pick || "").toLowerCase(), g.total_book)});
  });
  P.sort((a, b) => String(a.g.start).localeCompare(String(b.g.start)) || b.edge - a.edge);
  $("t-plays").innerHTML = P.length ? "<thead><tr><th>Bet</th><th>Book</th><th class='r hide-sm'>Model</th><th class='r'>Edge</th><th class='r hide-sm'>Win %</th><th class='r'>EV</th><th class='r'>Bet to</th><th class='r hide-sm'>Opened</th><th class='r hide-sm'>Units</th><th></th></tr></thead><tbody>" +
    P.map((p) => "<tr><td><div class='b pick'>" + logo(pickId(p.g, p.kind, p.side), 20) + esc(p.bet) + "</div><div class='f' style='font-size:12px'>" + matchupL(p.g) + " · " + esc(tip(p.g)) + " · " + p.kind + "</div>" +
      (p.kind === "Total" && p.g.crew ? "<div class='f' style='font-size:11px'>Refs: " + esc(p.g.crew) + "</div>" : "") +
      (p.status ? "<div class='f' style='font-size:12px'>" + esc(p.status) + "</div>" : "") +
      (p.also ? "<div class='f' style='font-size:12px'>" + esc(p.also) + "</div>" : "") +
      (p.g.news_flag ? "<div class='inj'>&#9888; " + esc(p.g.news_flag) + "</div>" : "") +
      (p.warn ? "<div class='inj'>&#9888; " + esc(p.warn) + "</div>" : "") +
      [["away", p.g.away], ["home", p.g.home]].filter(([sd]) => p.g[sd + "_injuries"]).map(([sd, nm]) => "<div class='inj'>" + esc(nm) + ": " + esc(p.g[sd + "_injuries"]) + "</div>").join("") + "</td><td>" +
      esc(p.book || "–") + (p.price != null ? " <span class='m'>" + esc(odds(p.price)) + "</span>" : "") + "</td><td class='r m hide-sm'>" + esc(p.model) + "</td><td class='r " + (p.edge >= (p.kind === "Spread" ? 2.5 : 3) ? "pos b" : p.edge < 0 ? "neg" : "m") + "'>" + sgn(p.edge) +
      "</td><td class='r m hide-sm'>" + pct(p.p) + "</td><td class='r'>" + (p.ev == null ? "–" : sgn(100 * p.ev) + "%") +
      "</td><td class='r'>" + esc(p.to) + "</td><td class='r m hide-sm'>" + esc(p.open ?? "–") + "</td><td class='r hide-sm'>" + num(p.units, 2) + "</td><td class='r'>" +
      (p.g.news_url ? "<a class='f' style='font-size:12px;margin-right:8px' href='" + esc(p.g.news_url) + "' target='_blank' rel='noopener'>News</a>" : "") +
      (p.link ? "<a class='betlink' href='" + esc(p.link) + "' target='_blank' rel='noopener'>Bet</a>" : "") +
      (p.bid && !D.replay ? (p.placed ? "<span class='f' style='font-size:12px;margin-left:8px'>Placed &#10003;</span>"
        : "<button type='button' class='pl-btn' data-i='" + P.indexOf(p) + "' style='font-size:12px;padding:4px 10px;margin-left:8px'>Placed</button>") : "") +
      "</td></tr>").join("") + "</tbody>"
    : "<tbody><tr><td class='empty'>" + (withLines ? "No plays. No line is far enough from the model." : "No lines posted yet. Openers usually post the night before.") + "</td></tr></tbody>";

  // KPIs
  const st = D.record ? D.record.status : null;
  const rec = (s) => s && s.bets ? s.w + "–" + s.l + (s.p ? "–" + s.p : "") : "0–0";
  const units = st ? (st.spread.units || 0) + (st.total.units || 0) : 0;
  const clvs = st ? [st.spread, st.total].filter((s) => s.clv_pts != null) : [];
  const kp = [["Plays today", P.length + "<small>" + P.reduce((s, p) => s + (p.units || 0), 0).toFixed(1).replace(/\.0$/, "") + "u</small>"],
    ["Spreads", rec(st && st.spread) + "<small>" + (st && st.spread.win != null ? pct(st.spread.win) : "") + "</small>"],
    ["Totals", rec(st && st.total) + "<small>" + (st && st.total.win != null ? pct(st.total.win) : "") + "</small>"],
    ["Units", "<span class='" + (units > 0 ? "pos" : units < 0 ? "neg" : "") + "'>" + sgn(units, 2) + "</span>"],
    ["Model check", (() => { const t = D.record && D.record.tripwire; if (!t) return "–";
      const m = t.model, e = t.execution;
      const lab = m.state === "collecting" ? "Collecting<small>" + m.n + "/150 bets</small>"
        : "<span class='" + (m.state === "ok" ? "pos" : "neg") + "'>" + {ok: "OK", review: "Review", pause: "Pause"}[m.state] + "</span><small>CLV " + sgn(m.clv, 2) + "</small>";
      return lab + (e.state === "review" ? "<small class='neg'> · slippage " + sgn(e.slip, 2) + "</small>" : ""); })()],
    ["Avg CLV", clvs.length ? sgn(clvs.reduce((s, x) => s + x.clv_pts * x.bets, 0) / clvs.reduce((s, x) => s + x.bets, 0), 2) + "<small>pts</small>" : "–"]];
  $("kpis").innerHTML = kp.map(([k, v]) => "<div class='kpi'><div class='k'>" + k + "</div><div class='v'>" + v + "</div></div>").join("");

  // Odds board
  let market = "spread";
  const cell = (val, price, link, best) => val == null ? "<span class='na'>–</span>" :
    "<" + (link ? "a href='" + esc(link) + "' target='_blank' rel='noopener'" : "span") + " class='odd" + (best ? " best" : "") + "'>" + esc(val) +
    (price != null ? "<small>" + esc(odds(price)) + "</small>" : "") + "</" + (link ? "a" : "span") + ">";
  const board = () => {
    const only = $("only-plays").checked;
    const G = D.games.filter((g) => !only || g.spread_verdict === "BET" || g.total_verdict === "BET")
      .sort((a, b) => String(a.start).localeCompare(String(b.start)) || a.home.localeCompare(b.home));
    const mh = {spread: "Model", total: "Model", ml: "Win %"}[market];
    let h = "<thead><tr><th>Time</th><th>Team</th><th class='r'>Proj</th><th class='r'>" + mh + "</th>" +
      BOOKS.map((b) => "<th class='bk'>" + b + "</th>").join("") + "<th class='r'>Edge</th></tr></thead>";
    if (!G.length) { $("t-board").innerHTML = h + "<tbody><tr><td class='empty' colspan='" + (BOOKS.length + 5) + "'>No games.</td></tr></tbody>"; return; }
    h += G.map((g) => {
      const sides = ["away", "home"];
      const hasBet = (market === "spread" && g.spread_verdict === "BET") || (market === "total" && g.total_verdict === "BET");
      const rows = sides.map((sd, i) => {
        const team = g[sd], pts = Math.round(g["model_" + sd + "_pts"]);
        let model, bookCells, edge = "";
        if (market === "spread") {
          model = ln(sd === "home" ? g.model_home_spread : -g.model_home_spread);
          const pick = g.spread_side === sd && ["BET", "WATCH"].includes(g.spread_verdict);
          bookCells = BOOKS.map((bk) => { const x = bl(g, bk); if (!x || x.home_spread == null) return cell(null);
            const v = sd === "home" ? x.home_spread : -x.home_spread;
            return cell(ln(v), x[sd + "_spread_odds"], x[sd + "_spread_link"], pick && g.spread_book === bk && v === g.spread_line); });
          if (pick && g.spread_verdict === "BET") edge = "<span class='tag bet'>BET " + sgn(g.spread_edge) + "</span>";
          else if (pick) { const at = playAt(g.spread_good_to, true);
            edge = watchTag(g.spread_line >= at ? "better price" : "bet at " + ln(at) + gp(g.spread_good_price)); }
        } else if (market === "total") {
          const ou = i === 0 ? "over" : "under";
          model = i === 0 ? num(g.model_total) : "";
          const pick = (g.total_pick || "").toLowerCase() === ou && ["BET", "WATCH"].includes(g.total_verdict);
          bookCells = BOOKS.map((bk) => { const x = bl(g, bk); if (!x || x.total == null) return cell(null);
            return cell((i === 0 ? "o" : "u") + num(x.total), x[ou + "_odds"], x[ou + "_link"], pick && g.total_book === bk && x.total === g.total_line); });
          if (pick && g.total_verdict === "BET") edge = "<span class='tag bet'>BET " + sgn(g.total_edge) + "</span>";
          else if (pick) { const at = playAt(g.total_good_to, ou === "under");
            edge = watchTag((ou === "under" ? g.total_line >= at : g.total_line <= at) ? "better price" : "bet at " + ou[0] + num(at) + gp(g.total_good_price)); }
        } else {
          const p = sd === "home" ? g.p_home_win : 1 - g.p_home_win;
          model = Math.round(100 * p) + "%";
          const prices = BOOKS.map((bk) => (bl(g, bk) || {})[sd + "_ml"]);
          const top = Math.max(...prices.filter((v) => v != null));
          bookCells = BOOKS.map((bk, j) => { const x = bl(g, bk); return x && x[sd + "_ml"] != null ? cell(odds(x[sd + "_ml"]), null, x[sd + "_ml_link"], prices[j] === top && prices.filter((v) => v != null).length > 1) : cell(null); });
        }
        return "<tr>" + (i === 0 ? "<td class='tm' rowspan='2'>" + esc(tip(g)) + (g.state === "post" ? "<div class='f'>Final</div>" : "") + "</td>" : "") +
          "<td class='team'>" + (i === 1 && !g.neutral ? "<span class='f'>@ </span>" : "") + logo(g[sd + "_id"], 18) + esc(team) +
          (g.state === "post" ? " <span class='m'>" + esc(g[sd + "_score"]) + "</span>" : "") +
          (g[sd + "_injuries"] ? "<div class='inj'>" + esc(g[sd + "_injuries"]) + "</div>" : "") + "</td><td class='r pts'>" + pts + "</td><td class='r b'>" + model + "</td>" +
          bookCells.map((c) => "<td class='bk'>" + c + "</td>").join("") + "<td class='r'>" + edge + "</td></tr>";
      }).join("");
      return "<tbody class='g" + (hasBet ? " has-bet" : "") + "'>" + rows + "</tbody>";
    }).join("");
    $("t-board").innerHTML = h;
  };
  document.querySelectorAll(".seg button").forEach((b) => b.onclick = () => {
    market = b.dataset.m; document.querySelectorAll(".seg button").forEach((x) => x.setAttribute("aria-pressed", x === b)); board(); });
  $("only-plays").onchange = board;
  board();

  // Watch list
  const W = [];
  D.games.forEach((g) => {
    if (g.spread_verdict === "WATCH") W.push([tip(g), matchup(g), g.spread_pick, ln(g.spread_line), ln(playAt(g.spread_good_to, true)) + gp(g.spread_good_price), sgn(g.spread_edge)]);
    if (g.total_verdict === "WATCH") W.push([tip(g), matchup(g), g.total_pick, num(g.total_line), num(playAt(g.total_good_to, g.total_pick === "Under")) + gp(g.total_good_price), sgn(g.total_edge)]);
  });
  if (!W.length) $("watch-sec").hidden = true;
  else $("t-watch").innerHTML = "<thead><tr><th>Time</th><th>Game</th><th>Side</th><th class='r'>Now</th><th class='r'>Play at</th><th class='r'>Edge now</th></tr></thead><tbody>" +
    W.map((r) => "<tr><td class='m'>" + esc(r[0]) + "</td><td>" + esc(r[1]) + "</td><td class='b'>" + esc(r[2]) + "</td><td class='r'>" + esc(r[3]) + "</td><td class='r'>" + esc(r[4]) + "</td><td class='r m'>" + esc(r[5]) + "</td></tr>").join("") + "</tbody>";

  // Record
  if (st) {
    $("rec-sec").hidden = false;
    $("t-rec").innerHTML = "<thead><tr><th>Market</th><th class='r'>Record</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>ROI</th><th class='r'>Avg CLV</th><th class='r'>Beat close</th><th class='r'>Stake</th><th class='r'>Open</th></tr></thead><tbody>" +
      Object.entries(st).map(([mk, s]) => "<tr><td>" + mk[0].toUpperCase() + mk.slice(1) + "</td><td class='r'>" + rec(s) + "</td><td class='r'>" + pct(s.win) + "</td><td class='r " +
        (s.units > 0 ? "pos" : s.units < 0 ? "neg" : "") + "'>" + sgn(s.units, 2) + "</td><td class='r'>" + pct(s.roi) + "</td><td class='r'>" + (s.clv_pts == null ? "–" : sgn(s.clv_pts, 2)) +
        "</td><td class='r'>" + pct(s.beat_close) + "</td><td class='r'>" + Math.round(100 * s.multiplier) + "%</td><td class='r m'>" + s.open + "</td></tr>").join("") + "</tbody>";
    const R = D.record.recent || [];
    if (R.length) {
      $("recent-sec").hidden = false;
      $("t-recent").innerHTML = "<thead><tr><th>Date</th><th>Game</th><th>Bet</th><th>Book</th><th class='r'>Close</th><th class='r'>CLV</th><th class='r'>Final</th><th class='r'>Result</th><th class='r'>Units</th></tr></thead><tbody>" +
        R.map((x) => "<tr><td class='m'>" + esc(x.date) + "</td><td>" + esc(x.away + " @ " + x.home) + "</td><td class='b'>" + esc(x.pick) + "</td><td>" + esc(x.book || "–") +
          "</td><td class='r'>" + num(x.close_line) + "</td><td class='r'>" + sgn(x.clv_pts) + "</td><td class='r m'>" + esc(x.away_score) + "–" + esc(x.home_score) +
          "</td><td class='r b " + (x.result === "W" ? "pos" : x.result === "L" ? "neg" : "") + "'>" + esc(x.result) + "</td><td class='r'>" + sgn(x.profit, 2) + "</td></tr>").join("") + "</tbody>";
    }
  }

  // Loss review (review.py)
  const RV = D.record && D.record.review;
  if (RV && RV.by_reason) {
    $("review-sec").hidden = false;
    const rows = (obj, label) => Object.entries(obj || {}).map(([k, a]) => "<tr><td>" + esc(k) + "</td><td class='r'>" + a.bets + "</td><td class='r'>" + a.w + "–" + a.l +
      "</td><td class='r'>" + pct(a.win) + "</td><td class='r " + (a.units > 0 ? "pos" : a.units < 0 ? "neg" : "") + "'>" + sgn(a.units, 2) + "</td><td class='r'>" + (a.clv == null ? "–" : sgn(a.clv, 2)) +
      "</td>" + (label ? "<td class='r m'>" + ((RV.losses_by_reason || {})[k] || 0) + "</td>" : "") + "</tr>").join("");
    const head = (first, extra) => "<thead><tr><th>" + first + "</th><th class='r'>Bets</th><th class='r'>Record</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Avg CLV</th>" + (extra ? "<th class='r'>Losses</th>" : "") + "</tr></thead>";
    $("t-review").innerHTML = head("Reason", true) + "<tbody>" + rows(RV.by_reason, true) + "</tbody>";
    $("t-review2").innerHTML = head("Split", false) + "<tbody>" + rows(Object.fromEntries([
      ...Object.entries(RV.by_market || {}).map(([k, v]) => [k[0].toUpperCase() + k.slice(1), v]),
      ...Object.entries(RV.by_edge || {}).map(([k, v]) => ["Edge " + k, v]),
      ...Object.entries(RV.by_month || {}),
      ...Object.entries(RV.by_venue || {}).filter(([k]) => !k.startsWith("Total"))]), false) + "</tbody>";
    const HC = RV.home_court || {};
    if (HC.home) {
      const h = HC.home, nn = HC.neutral || {};
      const verdict = h.resid_se && Math.abs(h.resid) > 2 * h.resid_se ? (h.resid > 0 ? "home edge looks too low" : "home edge looks too high") : "no evidence our home edge is off";
      $("t-review2").insertAdjacentHTML("afterend", "<div class='scroll'><table><thead><tr><th>Home court check</th><th class='r'>Games</th><th class='r'>Result vs model</th><th class='r'>Close vs model</th></tr></thead><tbody>" +
        "<tr><td>Home games <span class='m'>(" + verdict + ")</span></td><td class='r'>" + h.games + "</td><td class='r'>" + sgn(h.resid, 2) + (h.resid_se ? " <span class='f'>± " + num(2 * h.resid_se, 2) + "</span>" : "") +
        "</td><td class='r'>" + (h.vs_close == null ? "–" : sgn(h.vs_close, 2)) + "</td></tr>" +
        (nn.games ? "<tr><td>Neutral sites</td><td class='r'>" + nn.games + "</td><td class='r'>" + sgn(nn.resid, 2) + "</td><td class='r'>" + (nn.vs_close == null ? "–" : sgn(nn.vs_close, 2)) + "</td></tr>" : "") +
        "</tbody></table></div><p class='note' style='padding:8px 16px 12px'>+ = home teams did better than our projection (or the closing line gave them more than we did). Biggest team misses at home: " +
        esc((HC.teams_high || []).map((t) => t[0] + " " + sgn(t[1])).join(", ")) + " · " + esc((HC.teams_low || []).map((t) => t[0] + " " + sgn(t[1])).join(", ")) + "</p>");
    }
    const MM = RV.model_misses || [];
    if (MM.length) $("t-misses").innerHTML = "<thead><tr><th>Market disagreed: biggest misses</th><th class='r'>Bet</th><th class='r'>Close</th><th class='r'>CLV</th><th class='r'>Model (home margin)</th><th class='r'>Final</th></tr></thead><tbody>" +
      MM.map((x) => "<tr><td>" + esc(x.date + " · " + x.away + " @ " + x.home) + "</td><td class='r b'>" + esc(x.pick) + "</td><td class='r'>" + num(x.close_line) + "</td><td class='r neg'>" + sgn(x.clv_pts) +
        "</td><td class='r m'>" + num(x.model) + "</td><td class='r m'>" + esc(x.away_score) + "–" + esc(x.home_score) + "</td></tr>").join("") + "</tbody>";
  }

  // Ratings
  $("t-rat").innerHTML = "<thead><tr><th class='r'>#</th><th>Team</th><th class='r'>Net</th><th class='r'>Offense</th><th class='r'>Defense</th><th class='r'>Tempo</th></tr></thead><tbody>" +
    D.ratings.map((r) => "<tr><td class='r m'>" + r.rank + "</td><td>" + esc(r.team) + "</td><td class='r b'>" + sgn(r.net) + "</td><td class='r'>" + num(r.adj_oe) +
      "</td><td class='r'>" + num(r.adj_de) + "</td><td class='r'>" + num(r.adj_tempo) + "</td></tr>").join("") + "</tbody>";

  // Update: starts the "Update CBB card" workflow (token for this repo kept only in this browser)
  const REPO = D.repo, WF = "update.yml", API = "https://api.github.com/repos/" + REPO + "/actions";
  const RUNS_URL = "https://github.com/" + REPO + "/actions/workflows/" + WF;
  const store = { get: () => { try { return localStorage.getItem("gh_token_cbb") || ""; } catch (e) { return ""; } },
                  set: (v) => { try { v ? localStorage.setItem("gh_token_cbb", v) : localStorage.removeItem("gh_token_cbb"); } catch (e) {} } };
  const gen = new Date(D.generated_at);
  const ago = (d) => { const m = Math.round((Date.now() - d) / 60000);
    return m < 1 ? "just now" : m < 60 ? m + " min ago" : m < 1440 ? Math.round(m / 60) + " hr ago" : Math.round(m / 1440) + " days ago"; };
  const say = (t) => { $("upd-status").innerHTML = t; };
  say("Updated " + gen.toLocaleString("en-US", {weekday: "short", hour: "numeric", minute: "2-digit"}) + " · " + ago(gen));
  const askKey = () => { const t = prompt("Paste a GitHub fine-grained token for " + REPO + " with Actions: Read and write.\nIt is saved only in this browser. Leave blank to remove it.", store.get());
    if (t !== null) store.set(t.trim()); return store.get(); };
  const gh = (path, opts) => fetch(API + path, Object.assign({ headers: { Accept: "application/vnd.github+json",
    Authorization: "Bearer " + store.get(), "X-GitHub-Api-Version": "2022-11-28" } }, opts || {}));
  const followRun = (since) => {
    const btn = $("upd-btn"); btn.disabled = true; const t0 = Date.now();
    const tick = async () => {
      try {
        const run = (await (await gh("/workflows/" + WF + "/runs?per_page=1")).json()).workflow_runs?.[0];
        const mins = Math.floor((Date.now() - t0) / 60000);
        if (!run || new Date(run.created_at) < since) say("Starting…");
        else if (run.status !== "completed") say("Updating… " + mins + " min · <a href='" + run.html_url + "' target='_blank' rel='noopener'>details</a>");
        else if (run.conclusion === "success") { say("Done. Reloading…"); setTimeout(() => location.replace(location.pathname + "?t=" + Date.now()), 4000); return; }
        else { say("Update failed · <a href='" + run.html_url + "' target='_blank' rel='noopener'>details</a>"); btn.disabled = false; return; }
      } catch (e) { say("Reconnecting…"); }
      setTimeout(tick, 10000);
    };
    tick();
  };
  $("upd-btn").onclick = async () => {
    if (!store.get() && !askKey()) { window.open(RUNS_URL, "_blank", "noopener"); say("No token: use Run workflow on GitHub"); return; }
    const since = new Date(Date.now() - 5000);
    say("Starting…");
    const branch = (await (await fetch("https://api.github.com/repos/" + REPO)).json().catch(() => ({}))).default_branch || "main";
    const r = await gh("/workflows/" + WF + "/dispatches", { method: "POST", body: JSON.stringify({ ref: branch }) }).catch(() => null);
    if (r && r.status === 204) followRun(since);
    else if (r && [401, 403, 404].includes(r.status)) { store.set(""); say("Token refused (" + r.status + "). Click Update to enter a new one."); }
    else say("Couldn't reach GitHub");
  };
  if (store.get()) gh("/workflows/" + WF + "/runs?per_page=1").then((r) => r.json()).then((j) => {
    const run = j.workflow_runs?.[0]; if (run && run.status !== "completed") followRun(new Date(run.created_at)); }).catch(() => {});

  // Placed: records what was actually taken (book, line, odds, stake) through the "Record placed bet" workflow,
  // which marks the bet placed and adds it to bets/accepted.csv. Uses the same browser token as Update.
  const dlg = document.createElement("dialog");
  dlg.style.cssText = "border:1px solid var(--line-strong);border-radius:10px;padding:18px;background:var(--surface);color:var(--text);max-width:340px;width:90%";
  document.body.appendChild(dlg);
  const field = (k, label, v) => "<label style='display:block;margin:8px 0;font-size:13px'>" + label +
    "<input id='pl-" + k + "' value='" + esc(v ?? "") + "' style='display:block;width:100%;margin-top:3px;padding:6px;font:inherit;border:1px solid var(--line-strong);border-radius:6px;background:var(--surface);color:var(--text)'></label>";
  $("t-plays").addEventListener("click", (ev) => {
    const btn = ev.target.closest(".pl-btn");
    if (!btn) return;
    const p = P[Number(btn.dataset.i)];
    dlg.innerHTML = "<div class='b' style='margin-bottom:4px'>Placed: " + esc(p.bet) + "</div><div class='f' style='font-size:12px'>" + esc(matchup(p.g)) +
      "</div>" + field("book", "Book", p.fill.book) + field("line", p.kind === "Spread" ? "Line (your side)" : "Total", p.fill.line) +
      field("odds", "Odds", p.fill.odds) + field("stake", "Units", p.fill.stake) +
      "<div id='pl-msg' class='f' style='font-size:12px;min-height:16px'></div><div style='display:flex;gap:8px;justify-content:flex-end;margin-top:8px'>" +
      "<button type='button' id='pl-cancel'>Cancel</button><button type='button' id='pl-save'>Save</button></div>";
    dlg.showModal();
    $("pl-cancel").onclick = () => dlg.close();
    $("pl-save").onclick = async () => {
      const v = (k) => $("pl-" + k).value.trim();
      const msg = (t) => { $("pl-msg").textContent = t; };
      if (!v("book") || [v("line"), v("odds"), v("stake")].some((x) => x === "" || isNaN(Number(x)))) { msg("Fill in book, line, odds and units."); return; }
      if (!store.get() && !askKey()) { msg("No GitHub token: use Update's token prompt first."); return; }
      msg("Saving…");
      const branch = (await (await fetch("https://api.github.com/repos/" + REPO)).json().catch(() => ({}))).default_branch || "main";
      const inputs = {bet_id: p.bid, book: v("book"), line: v("line"), odds: v("odds"), stake: v("stake")};
      const r = await gh("/workflows/placed.yml/dispatches", { method: "POST", body: JSON.stringify({ ref: branch, inputs }) }).catch(() => null);
      if (r && r.status === 204) { dlg.close(); btn.outerHTML = "<span class='f' style='font-size:12px;margin-left:8px'>Saved &#10003;</span>"; }
      else if (r && [401, 403, 404].includes(r.status)) { store.set(""); msg("Token refused (" + r.status + "). Click Update to enter a new one."); }
      else msg("Couldn't reach GitHub. Try again.");
    };
  });
})();
</script>
"""
