"""Daily CBB bet card as a self-contained HTML page: plays first, then the full slate and the ratings.

Same look and Update button as the NFL card (barrca12-rgb/NFL, model/report_html.py), so the two sites read as
one. No external dependencies except Google Fonts (with fallbacks).
"""
from __future__ import annotations

import html
import json
import math

import numpy as np
import pandas as pd

REPO = "barrca12-rgb/CBB"
NFL_SITE = "https://barrca12-rgb.github.io/NFL/"


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


def build(card: pd.DataFrame, rt: pd.DataFrame, day: pd.Timestamp, season: int, replay: bool = False) -> str:
    games = [{k: _clean(v) for k, v in r.items()} for r in card.to_dict("records")]
    t = rt.reset_index(names="espn_id")
    t["rank"] = range(1, len(t) + 1)
    rat = [{k: _clean(v) for k, v in r.items()} for r in
           t[["rank", "team", "net", "adj_oe", "adj_de", "adj_tempo"]].to_dict("records")]
    data = {"date": f"{day:%Y-%m-%d}", "season": season, "replay": replay, "repo": REPO, "nfl": NFL_SITE,
            "generated_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"), "games": games, "ratings": rat}
    payload = json.dumps(data).replace("</", "<\\/")
    title = f"{day:%a %b} {day.day} CBB Card"
    return TEMPLATE.replace("__TITLE__", html.escape(title)).replace("__CSS__", CSS).replace("__DATA__", payload)


CSS = r"""/* Copied from the NFL card (model/report_html.py) so both sites look the same. */
:root {
  /* Sportsbook-style dark theme: near-black canvas, raised cards, neon green for anything actionable */
  --bg: #0a0e13; --surface: #141a22; --ink: #f3f6f9; --muted: #8d99a8; --line: #222b37;
  --turf: #2fe27a; --turf-soft: #10301f; --amber: #ffb627; --amber-soft: #382a0c; --blue: #2f9bff;
  --chalk: #1c2430; --pass: #6d7887; --neg: #ff5c61; --on-accent: #06110b;
  --display: "Barlow Condensed", "Arial Narrow", "Roboto Condensed", sans-serif;
  --body: "Source Sans 3", "Segoe UI", system-ui, sans-serif;
  color-scheme: dark;
}
* { box-sizing: border-box }
body { margin: 0; background: radial-gradient(1200px 500px at 50% -200px, #12301f 0%, var(--bg) 60%) no-repeat, var(--bg); color: var(--ink); font: 15px/1.5 var(--body); }
.wrap { max-width: 1180px; margin: 0 auto; padding-block: 28px 64px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; gap: 36px; }
h1, h2, h3 { font-family: var(--display); font-weight: 700; letter-spacing: .01em; margin: 0; text-wrap: balance }
h1 { font-size: clamp(34px, 5vw, 52px); line-height: 1 }
h2 { font-size: 26px; line-height: 1.1 }
.eyebrow { font: 600 13px/1 var(--display); letter-spacing: .14em; text-transform: uppercase; color: var(--muted) }
.lede { color: var(--muted); max-width: 70ch; margin: 8px 0 0 }
header { display: grid; gap: 10px }
.meta { display: flex; flex-wrap: wrap; gap: 8px }
.chip { font: 600 13px/1 var(--body); padding: 6px 10px; border-radius: 999px; background: var(--chalk); color: var(--muted) }
/* Update bar: re-runs the model with live odds through GitHub Actions */
.update { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; background: var(--surface);
  border: 1px solid var(--line); border-radius: 10px; padding: 10px 14px; font-size: 14px }
.update button { font: 700 15px/1 var(--display); letter-spacing: .06em; text-transform: uppercase; cursor: pointer;
  padding: 11px 18px; border-radius: 999px; border: 0; background: var(--turf); color: var(--on-accent); box-shadow: 0 0 24px rgba(47,226,122,.35) }
.update button:disabled { opacity: .55; cursor: progress }
.update #upd-status { color: var(--muted); flex: 1 1 220px }
section { display: grid; gap: 14px; min-width: 0 }
.sec-head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px }
.note { color: var(--muted); font-size: 14px; max-width: 80ch; margin: 0 }

/* Model plays: one row per bet */
/* Week switcher */
.weeks { display: flex; flex-wrap: wrap; gap: 6px }
.weeks a { font: 700 14px/1 var(--display); letter-spacing: .06em; text-transform: uppercase; text-decoration: none;
  color: var(--muted); background: var(--chalk); padding: 9px 14px; border-radius: 999px; border: 1px solid var(--line) }
.weeks a:hover { color: var(--ink) }
.weeks a[aria-current="page"] { background: var(--ink); color: var(--bg); border-color: var(--ink) }
.weeks a .tag { font: 600 10px/1 var(--body); letter-spacing: .08em; margin-left: 6px; color: var(--turf) }
.weeks a[aria-current="page"] .tag { color: var(--bg) }

/* Model plays: tickets like the slate, plus the numbers behind the pick */
.plays { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 500px), 1fr)); gap: 14px }
.pk { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; display: grid; gap: 12px;
  min-width: 0; box-shadow: inset 0 3px 0 var(--turf), 0 0 0 1px rgba(47,226,122,.25) }
.pk.small { box-shadow: inset 0 3px 0 var(--amber), 0 0 0 1px rgba(255,182,39,.25) }
.pk.tz { box-shadow: inset 0 3px 0 var(--blue), 0 0 0 1px rgba(47,155,255,.25) }
.pk-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px }
.pk-pick { font: 700 30px/1 var(--display) } .pk-pick .price { color: var(--muted) }
.pk-game { color: var(--muted); font-size: 13px; margin-top: 4px }
.pk-stake { text-align: right; flex: none }
.pk-stake b { display: block; font: 700 26px/1 var(--display); color: var(--turf) }
.pk.small .pk-stake b { color: var(--amber) } .pk.tz .pk-stake b { color: var(--blue) }
.pk-stake span { font: 700 11px/1 var(--body); letter-spacing: .08em; text-transform: uppercase; color: var(--muted) }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(104px, 1fr)); gap: 6px }
.stat { background: var(--chalk); border-radius: 8px; padding: 8px 10px; min-width: 0 }
.stat span { display: block; font: 700 10px/1.2 var(--body); letter-spacing: .08em; text-transform: uppercase; color: var(--muted) }
.stat b { display: block; font: 700 19px/1.2 var(--display); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis }
.stat b.pos { color: var(--turf) }
.pk-why { color: var(--muted); font-size: 13px }
.cta { display: block; text-align: center; font: 700 16px/1 var(--display); letter-spacing: .06em; text-transform: uppercase;
  padding: 13px 16px; border-radius: 999px; text-decoration: none; background: var(--turf); color: var(--on-accent) }
.cta:hover { filter: brightness(1.1) }
.pk.tz .cta { background: var(--blue); color: #fff } .pk.small .cta { background: var(--amber) }
span.cta { opacity: .9 }
.empty { background: var(--surface); border: 1px dashed var(--line); border-radius: 10px; padding: 18px; color: var(--muted) }

/* Full slate: one ticket per game, books side by side */
.slate { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 500px), 1fr)); gap: 14px }
.game { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; display: grid; gap: 10px; min-width: 0 }
.game.has-play { box-shadow: inset 0 3px 0 var(--turf), 0 0 0 1px rgba(47,226,122,.25) }
.g-top { display: flex; justify-content: space-between; align-items: center; gap: 8px }
.g-title { font: 700 22px/1 var(--display) }
.g-kick { color: var(--muted); font-size: 13px }
/* odds grid: books are columns; on narrow screens it scrolls sideways with the row labels pinned */
.oddswrap { overflow-x: auto; margin: 0 -6px; padding: 0 6px; scrollbar-width: thin }
table.odds { font-size: 14px; width: 100%; border-collapse: separate; border-spacing: 4px; table-layout: auto }
table.odds.few { width: auto } table.odds.few td { min-width: 96px }
table.odds th, table.odds td { padding: 0; border: 0; white-space: nowrap }
table.odds thead th { position: static; background: none; cursor: default; font: 700 11px/1.1 var(--body);
  letter-spacing: .05em; text-transform: uppercase; color: var(--muted); text-align: center; padding: 0 2px 2px }
table.odds .abbr { display: none }
table.odds tbody th { text-align: left; font: 600 13px/1.1 var(--body); color: var(--muted); padding-right: 6px;
  position: sticky; left: 0; background: var(--surface); z-index: 1; min-width: 46px }
table.odds tr.cap th { font: 700 10px/1 var(--body); letter-spacing: .12em; text-transform: uppercase; color: var(--pass); padding-top: 8px }
table.odds td { background: var(--chalk); border-radius: 8px; text-align: center; font-weight: 700; min-width: 58px }
table.odds td .t { display: block; padding: 7px 4px; color: inherit; text-decoration: none; line-height: 1.15 }
table.odds td small { display: block; color: var(--muted); font-size: 12px; font-weight: 600 }
table.odds td a.t:hover, table.odds td a.t:focus-visible { background: #263142; border-radius: 8px; outline: none }
table.odds td.best { color: var(--turf); background: var(--turf-soft); box-shadow: inset 0 0 0 1px var(--turf) }
table.odds td.best small { color: var(--turf) }
table.odds td.none { background: transparent; color: var(--pass); font-weight: 400 }
table.odds tr.mine th { color: var(--ink); font-weight: 700 }
table.odds tr.mine th::before { content: "\2713 "; color: var(--turf) }
@media (max-width: 700px) { table.odds .full { display: none } table.odds .abbr { display: inline } table.odds td { min-width: 52px } }
.swipe { display: none; font-size: 12px; color: var(--pass) }
@media (max-width: 700px) { .swipe.on { display: block } }
.best-key { color: var(--turf) }
.g-model { font-size: 14px; color: var(--muted) } .g-model b { color: var(--ink) }
.g-play { font: 700 16px/1.2 var(--display); letter-spacing: .02em; color: var(--turf) }
.g-play a, a.bk { color: inherit; text-decoration: none } .g-play a:hover { text-decoration: underline }
a.bk:hover { filter: brightness(1.2) }
.g-play.none { color: var(--pass); font-weight: 600 }

/* Verdict pills */
.v { display: inline-block; font: 700 12px/1 var(--display); letter-spacing: .08em; padding: 5px 8px; border-radius: 4px }
.v.BET { background: var(--turf); color: var(--on-accent) }
.v.SMALL { background: var(--amber-soft); color: var(--amber) }
.v.H2H { background: var(--blue); color: #fff }
.v.WATCH { background: var(--chalk); color: var(--amber); box-shadow: inset 0 0 0 1px var(--amber) }
.v.PASS { background: var(--chalk); color: var(--pass) }
.v.FINAL, .v.LIVE { background: transparent; color: var(--muted); box-shadow: inset 0 0 0 1px var(--line) }
.v.LIVE { color: var(--neg); box-shadow: inset 0 0 0 1px var(--neg) }
.game.done { opacity: .6; align-self: start; align-content: start }
.g-score { font: 700 18px/1 var(--display) }

/* Tables */
.filters { display: flex; flex-wrap: wrap; gap: 6px }
.filters button { font: 600 13px/1 var(--body); padding: 7px 11px; border-radius: 999px; border: 1px solid var(--line);
  background: var(--surface); color: var(--ink); cursor: pointer }
.filters button[aria-pressed="true"] { background: var(--ink); color: var(--bg); border-color: var(--ink) }
.tbl { overflow-x: auto; background: var(--surface); border: 1px solid var(--line); border-radius: 10px }
table { border-collapse: collapse; width: 100%; font-size: 14px; font-variant-numeric: tabular-nums }
th, td { padding: 9px 10px; text-align: right; white-space: nowrap; border-bottom: 1px solid var(--line) }
th:first-child, td:first-child, th.l, td.l { text-align: left }
tbody tr:last-child td { border-bottom: 0 }
thead th { position: sticky; top: 0; background: var(--chalk); font: 600 12px/1.2 var(--body); letter-spacing: .04em;
  text-transform: uppercase; color: var(--muted); cursor: pointer; user-select: none }
thead th:hover, thead th:focus-visible { color: var(--ink); outline: none }
thead th[aria-sort="ascending"]::after { content: " \25B2"; font-size: 9px }
thead th[aria-sort="descending"]::after { content: " \25BC"; font-size: 9px }
tbody tr:hover { background: var(--chalk) }
td.pos { color: var(--turf); font-weight: 600 } td.neg { color: var(--neg) }
td.strong { font-weight: 700 }
details { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 12px 16px; display: grid; gap: 10px }
details > :not(summary) { margin-top: 10px }
summary { cursor: pointer; font: 700 18px/1.2 var(--display) }
details[open] summary { margin-bottom: 10px }
.glossary { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px }
.glossary div { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 14px; font-size: 14px }
.glossary b { font-family: var(--display); font-size: 17px; display: block; margin-bottom: 4px }
@media (prefers-reduced-motion: no-preference) { tbody tr { transition: background .12s } }
"""

TEMPLATE = r"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Source+Sans+3:wght@400;600;700&display=swap">
<style>
__CSS__
.sites { display: flex; gap: 6px } .sites a { font: 700 15px/1 var(--display); letter-spacing: .08em; text-transform: uppercase;
  text-decoration: none; color: var(--muted); padding: 8px 14px; border-radius: 999px; border: 1px solid var(--line) }
.sites a[aria-current="page"] { background: var(--turf); color: var(--on-accent); border-color: var(--turf) }
.stat.wide { grid-column: 1 / -1 }
.replay { background: var(--amber-soft); color: var(--amber); border-radius: 10px; padding: 10px 14px; font-size: 14px }
</style>

<div class="wrap">
  <header>
    <nav class="sites" aria-label="Sites"><a id="nfl-link" href="#">NFL</a><a href="./" aria-current="page">CBB</a></nav>
    <div class="eyebrow" id="eyebrow"></div>
    <h1 id="h1"></h1>
    <p class="lede">Every Division I game: the model's margin and total next to the live lines at each book. Plays are where the model and the line disagree by enough to have won in the backtest. Bet them early: the edge is against the opening number.</p>
    <nav class="weeks" id="days" aria-label="Days"></nav>
    <div class="meta" id="meta"></div>
    <div class="replay" id="replay" hidden>Replay of a past day with ESPN's stored closing lines (no prices or betslip links). Live cards use SportsGameOdds.</div>
    <div class="update">
      <button id="upd-btn" type="button">Update now</button>
      <span id="upd-status"></span>
    </div>
  </header>

  <section aria-labelledby="plays-h">
    <div class="sec-head"><h2 id="plays-h">Model plays</h2><span class="note" id="plays-sum"></span></div>
    <p class="note">Spreads: 3+ points of edge (57.5% against the opener in 2024-26). Totals: 4+ points (56.1%). Take each play only at the "good down to" number or better. Break-even at -110 is 52.4%.</p>
    <div class="plays" id="plays"></div>
  </section>

  <section aria-labelledby="watch-h">
    <div class="sec-head"><h2 id="watch-h">Watch list</h2></div>
    <p class="note">Not plays yet: each becomes one if its line moves to the number shown.</p>
    <div class="tbl"><table id="t-watch"></table></div>
  </section>

  <section aria-labelledby="slate-h">
    <div class="sec-head"><h2 id="slate-h">Full slate</h2><span class="note">Click a column to sort. Spreads are the home team's (-3 = home favored by 3).</span></div>
    <div class="tbl"><table id="t-slate"></table></div>
  </section>

  <section aria-labelledby="books-h">
    <div class="sec-head"><h2 id="books-h">Lines at every book</h2><span class="note">Best number in each row in green. Tap a price to open that book's betslip.</span></div>
    <div class="slate" id="books"></div>
  </section>

  <details>
    <summary>Power ratings</summary>
    <p class="note">Points per 100 possessions vs an average team, adjusted for opponent and venue, as of this morning. Net = offense + defense.</p>
    <div class="tbl"><table id="t-rat"></table></div>
  </details>

  <details>
    <summary>How the model works</summary>
    <div class="glossary">
      <div><b>Ratings</b>Offense, defense and tempo for every team from every D-I box score this season, adjusted for opponent and home court, recent games weighted more. Each team starts from KenPom's preseason rating.</div>
      <div><b>Final number</b>A second stage blends the ratings with KenPom and Barttorvik, the Four Factor matchups, rest and back-to-backs, each team's own home edge, and missing players (minutes from players who sat out the team's last game).</div>
      <div><b>Edge</b>Model margin or total minus the best line across books. The model never sees the line, so the edge is a real disagreement.</div>
      <div><b>Backtest</b>2014-2026, walk-forward (every game predicted only from earlier games). No edge against closing lines; 57.5% ATS and 55-56% on totals against opening lines in 2024-26. Details in BACKTEST.md.</div>
    </div>
  </details>
</div>

<script id="data" type="application/json">__DATA__</script>
<script>
(() => {
  const D = JSON.parse(document.getElementById("data").textContent);
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const sgn = (x, d = 1) => x == null ? "—" : (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x).toFixed(d).replace(/\.0$/, "");
  const ln = (x) => x == null ? "—" : x === 0 ? "PK" : sgn(x);
  const num = (x, d = 1) => x == null ? "—" : Number(x).toFixed(d);
  const odds = (x) => x == null ? "" : (x > 0 ? "+" : "") + Math.round(x);
  const day = new Date(D.date + "T12:00:00");
  const tip = (g) => g.start ? new Date(g.start).toLocaleTimeString("en-US", {hour: "numeric", minute: "2-digit", timeZone: "America/New_York"}) + " ET" : "";
  const matchup = (g) => g.away + (g.neutral ? " vs " : " @ ") + g.home;
  // Model's projected final score, winner first: "Duke 82, North Carolina 74"
  const score = (g) => { const h = Math.round(g.model_home_pts), a = Math.round(g.model_away_pts);
    return h >= a ? g.home + " " + h + ", " + g.away + " " + a : g.away + " " + a + ", " + g.home + " " + h; };

  $("nfl-link").href = D.nfl;
  $("eyebrow").textContent = "College basketball · " + (D.season - 1) + "–" + String(D.season).slice(2);
  $("h1").textContent = day.toLocaleDateString([], {weekday: "short", month: "short", day: "numeric"}) + " bet card";
  $("replay").hidden = !D.replay;
  const withLines = D.games.filter((g) => g.n_books > 0).length;
  [D.games.length + " games", withLines + " with lines", "Ratings through " + day.toLocaleDateString([], {month: "short", day: "numeric"})]
    .forEach((t) => { const c = document.createElement("span"); c.className = "chip"; c.textContent = t; $("meta").appendChild(c); });

  // Day switcher (days.json is written next to the pages)
  const navDays = (list, cur) => {
    $("days").innerHTML = list.slice(-10).map((d) => '<a href="cbb_' + d + '.html"' + (d === D.date ? ' aria-current="page"' : "") + ">" +
      new Date(d + "T12:00:00").toLocaleDateString([], {month: "short", day: "numeric"}) + (d === cur ? '<span class="tag">Now</span>' : "") + "</a>").join("");
  };
  navDays([D.date], null);
  fetch("days.json", {cache: "no-store"}).then((r) => r.json()).then((j) => navDays(j.days, j.current)).catch(() => {});

  // Plays: one card per spread or total play
  const P = [];
  D.games.forEach((g) => {
    if (g.spread_verdict === "BET") P.push({g, kind: "spread", v: g.spread_verdict, units: g.spread_units, edge: g.spread_edge,
      pick: g.spread_pick + " " + ln(g.spread_line), price: odds(g.spread_odds), book: g.spread_book, link: g.spread_link,
      model: (g.spread_side === "home" ? g.home + " " + ln(-g.model_margin) : g.away + " " + ln(g.model_margin)),
      good: g.spread_pick + " " + ln(g.spread_good_to), open: g.open_home_spread == null ? null : (g.spread_side === "home" ? ln(g.open_home_spread) : ln(-g.open_home_spread))});
    if (g.total_verdict === "BET") P.push({g, kind: "total", v: g.total_verdict, units: g.total_units, edge: g.total_edge,
      pick: g.total_pick + " " + num(g.total_line), price: odds(g.total_odds), book: g.total_book, link: g.total_link,
      model: num(g.model_total), good: g.total_pick + " " + num(g.total_good_to), open: null});
  });
  P.sort((a, b) => (b.v === "BET") - (a.v === "BET") || b.edge - a.edge);
  const units = P.reduce((s, p) => s + p.units, 0);
  $("plays-sum").textContent = P.length ? P.length + " plays · " + units + "u" : "";
  $("plays").innerHTML = P.length ? P.map((p) => {
    const st = [["Model score", score(p.g)], ["Model", p.model], ["Edge", sgn(p.edge) + " pts"], ["Good down to", p.good], ["Book", p.book || "—"]];
    if (p.open) st.splice(3, 0, ["Opened", p.open]);
    return '<article class="pk' + (p.v === "SMALL" ? " small" : "") + '"><div class="pk-top"><div><div class="pk-pick">' + esc(p.pick) +
      ' <span class="price">' + esc(p.price) + '</span></div><div class="pk-game">' + esc(matchup(p.g)) + " · " + esc(tip(p.g)) + (p.g.note ? " · " + esc(p.g.note) : "") +
      '</div></div><div class="pk-stake"><b>' + p.units + 'u</b><span>' + p.v + " · " + p.kind + '</span></div></div><div class="stats">' +
      st.map(([k, v]) => '<div class="stat' + (k === "Model score" ? " wide" : "") + '"><span>' + k + "</span><b" + (k === "Edge" ? ' class="pos"' : "") + ">" + esc(v) + "</b></div>").join("") + "</div>" +
      (p.link ? '<a class="cta" href="' + esc(p.link) + '" target="_blank" rel="noopener">Bet at ' + esc(p.book) + "</a>" : "") + "</article>";
  }).join("") : '<div class="empty">' + (withLines ? "No plays today: no line is 3+ points (spread) or 4+ points (total) off the model." : "No lines posted yet. Run Update closer to tip-off; openers usually post the evening before.") + "</div>";

  // Sortable table helper
  const table = (el, cols, rows) => {
    let key = null, dir = -1;
    const draw = () => {
      const r = key == null ? rows : [...rows].sort((a, b) => { const x = a[key], y = b[key];
        return (x == null) - (y == null) || (typeof x === "string" ? String(x).localeCompare(y) : (x - y)) * dir; });
      el.innerHTML = "<thead><tr>" + cols.map((c, i) => '<th tabindex="0" class="' + (c.l ? "l" : "") + '" data-i="' + i + '"' +
        (key === c.k ? ' aria-sort="' + (dir > 0 ? "ascending" : "descending") + '"' : "") + ">" + c.h + "</th>").join("") + "</tr></thead><tbody>" +
        r.map((x) => "<tr>" + cols.map((c) => '<td class="' + (c.l ? "l " : "") + (c.cls ? c.cls(x) : "") + '">' + (c.f ? c.f(x) : esc(x[c.k] ?? "—")) + "</td>").join("") + "</tr>").join("") + "</tbody>";
      el.querySelectorAll("th").forEach((th) => th.onclick = th.onkeydown = (e) => { if (e.type === "keydown" && e.key !== "Enter") return;
        const c = cols[+th.dataset.i]; dir = key === c.k ? -dir : (typeof rows[0]?.[c.k] === "string" ? 1 : -1); key = c.k; draw(); });
    };
    draw();
  };
  const pill = (v) => v ? '<span class="v ' + v + '">' + v + "</span>" : "";
  const S = D.games.map((g) => Object.assign({}, g, {matchup: matchup(g), tip: tip(g),
    fav_win: Math.max(g.p_home_win, 1 - g.p_home_win), fav: g.p_home_win >= 0.5 ? g.home : g.away}));
  table($("t-slate"), [
    {h: "Tip", k: "start", l: 1, f: (x) => esc(x.tip) + (x.state === "post" ? " · F " + x.away_score + "–" + x.home_score : "")},
    {h: "Game", k: "matchup", l: 1},
    {h: "Model score", k: "model_total", l: 1, f: (x) => esc(score(x))},
    {h: "Model", k: "model_home_spread", f: (x) => ln(x.model_home_spread)},
    {h: "Line", k: "line_home_spread", f: (x) => ln(x.line_home_spread)},
    {h: "Spread play", k: "spread_edge", l: 1, f: (x) => x.spread_pick ? pill(x.spread_verdict) + " " + esc(x.spread_pick + " " + ln(x.spread_line)) + " (" + sgn(x.spread_edge) + ")" : "—"},
    {h: "Model total", k: "model_total", f: (x) => num(x.model_total)},
    {h: "Line total", k: "line_total", f: (x) => num(x.line_total)},
    {h: "Total play", k: "total_edge", l: 1, f: (x) => x.total_pick ? pill(x.total_verdict) + " " + esc(x.total_pick + " " + num(x.total_line)) + " (" + sgn(x.total_edge) + ")" : "—"},
    {h: "Winner", k: "fav_win", l: 1, f: (x) => esc(x.fav) + " " + Math.round(100 * x.fav_win) + "%"},
    {h: "Books", k: "n_books"},
  ], S);
  const W = [];
  D.games.forEach((g) => {
    if (g.spread_verdict === "WATCH") W.push({matchup: matchup(g), tip: tip(g), pick: g.spread_pick, now: ln(g.spread_line), at: ln(g.spread_good_to), edge: g.spread_edge, kind: "Spread"});
    if (g.total_verdict === "WATCH") W.push({matchup: matchup(g), tip: tip(g), pick: g.total_pick, now: num(g.total_line), at: num(g.total_good_to), edge: g.total_edge, kind: "Total"});
  });
  table($("t-watch"), [{h: "Game", k: "matchup", l: 1}, {h: "Tip", k: "tip", l: 1}, {h: "Bet", k: "kind", l: 1}, {h: "Side", k: "pick", l: 1},
    {h: "Line now", k: "now"}, {h: "Play at", k: "at"}, {h: "Edge now", k: "edge", f: (x) => sgn(x.edge)}], W);
  table($("t-rat"), [{h: "#", k: "rank"}, {h: "Team", k: "team", l: 1}, {h: "Net", k: "net", f: (x) => sgn(x.net)},
    {h: "Off", k: "adj_oe", f: (x) => num(x.adj_oe)}, {h: "Def", k: "adj_de", f: (x) => num(x.adj_de)}, {h: "Tempo", k: "adj_tempo", f: (x) => num(x.adj_tempo)}], D.ratings);

  // Lines at every book: one ticket per game, books as columns (our four first, then any others in the feed)
  const ORDER = ["FanDuel", "DraftKings", "BetMGM", "Caesars"];
  const ABBR = {FanDuel: "FD", DraftKings: "DK", BetMGM: "MGM", Caesars: "CZR", "ESPN BET": "ESPN", Fanatics: "FAN", BetRivers: "BR", "Hard Rock": "HR", bet365: "365"};
  const cell = (val, price, link, best) => {
    if (val == null && price == null) return '<td class="none">—</td>';
    const inner = '<b>' + esc(val ?? "") + '</b><small>' + esc(odds(price)) + "</small>";
    return '<td' + (best ? ' class="best"' : "") + ">" + (link ? '<a class="t" href="' + esc(link) + '" target="_blank" rel="noopener">' + inner + "</a>" : '<span class="t">' + inner + "</span>") + "</td>";
  };
  const better = (a, b, dir) => a == null ? false : b == null ? true : dir * (a - b) > 0;
  const bestIdx = (L, key, dir, priceKey) => {
    let bi = -1;
    L.forEach((x, i) => { if (x[key] == null) return; const b = L[bi];
      if (bi < 0 || better(x[key], b[key], dir) || (x[key] === b[key] && better(x[priceKey], b[priceKey], 1))) bi = i; });
    return bi;
  };
  const G = D.games.filter((g) => (g.book_lines || []).length).sort((a, b) => String(a.start).localeCompare(String(b.start)));
  $("books").innerHTML = G.length ? G.map((g) => {
    const L = [...g.book_lines].sort((a, b) => ((ORDER.indexOf(a.book) + 99) % 99) - ((ORDER.indexOf(b.book) + 99) % 99) || a.book.localeCompare(b.book));
    const away = L.map((x) => Object.assign({}, x, {away_spread: x.home_spread == null ? null : -x.home_spread}));
    const rows = [
      ["Spread", null],
      [g.away, (i) => cell(ln(away[i].away_spread), L[i].away_spread_odds, L[i].away_spread_link, i === bestIdx(away, "away_spread", 1, "away_spread_odds"))],
      [g.home, (i) => cell(ln(L[i].home_spread), L[i].home_spread_odds, L[i].home_spread_link, i === bestIdx(L, "home_spread", 1, "home_spread_odds"))],
      ["Total", null],
      ["Over", (i) => cell(L[i].total == null ? null : "o" + num(L[i].total), L[i].over_odds, L[i].over_link, i === bestIdx(L, "total", -1, "over_odds"))],
      ["Under", (i) => cell(L[i].total == null ? null : "u" + num(L[i].total), L[i].under_odds, L[i].under_link, i === bestIdx(L, "total", 1, "under_odds"))],
      ["Moneyline", null],
      [g.away, (i) => cell(L[i].away_ml == null ? null : "ML", L[i].away_ml, L[i].away_ml_link, i === bestIdx(L, "away_ml", 1, "away_ml"))],
      [g.home, (i) => cell(L[i].home_ml == null ? null : "ML", L[i].home_ml, L[i].home_ml_link, i === bestIdx(L, "home_ml", 1, "home_ml"))],
    ];
    const play = [g.spread_verdict === "BET" ? g.spread_pick + " " + ln(g.spread_line) : "", g.total_verdict === "BET" ? g.total_pick + " " + num(g.total_line) : ""].filter(Boolean).join(" · ");
    return '<article class="game' + (play ? " has-play" : "") + '"><div class="g-top"><div class="g-title">' + esc(matchup(g)) + '</div><div class="g-kick">' + esc(tip(g)) + "</div></div>" +
      '<div class="g-model">Model: <b>' + esc(score(g)) + "</b> · " + esc(g.home) + " " + ln(g.model_home_spread) + " · total " + num(g.model_total) + "</div>" +
      (play ? '<div class="g-play">Play: ' + esc(play) + "</div>" : "") +
      '<div class="oddswrap"><table class="odds' + (L.length <= 3 ? " few" : "") + '"><thead><tr><th></th>' +
      L.map((x) => '<th><span class="full">' + esc(x.book) + '</span><span class="abbr">' + esc(ABBR[x.book] || x.book) + "</span></th>").join("") + "</tr></thead><tbody>" +
      rows.map(([label, f]) => f ? "<tr><th>" + esc(label) + "</th>" + L.map((_, i) => f(i)).join("") + "</tr>" : '<tr class="cap"><th colspan="' + (L.length + 1) + '">' + label + "</th></tr>").join("") +
      "</tbody></table></div></article>";
  }).join("") : '<div class="empty">No lines posted yet.</div>';

  // Update bar: starts the "Update CBB card" workflow (same as the NFL page's button; token kept only in this browser)
  const REPO = D.repo, WF = "update.yml", API = "https://api.github.com/repos/" + REPO + "/actions";
  const RUNS_URL = "https://github.com/" + REPO + "/actions/workflows/" + WF;
  const store = { get: () => { try { return localStorage.getItem("gh_token_cbb") || ""; } catch (e) { return ""; } },
                  set: (v) => { try { v ? localStorage.setItem("gh_token_cbb", v) : localStorage.removeItem("gh_token_cbb"); } catch (e) {} } };
  const gen = new Date(D.generated_at);
  const ago = (d) => { const m = Math.round((Date.now() - d) / 60000);
    return m < 1 ? "just now" : m < 60 ? m + " min ago" : m < 1440 ? Math.round(m / 60) + " h ago" : Math.round(m / 1440) + " days ago"; };
  $("upd-status").textContent = "Lines and picks as of " + gen.toLocaleString([], {weekday: "short", hour: "numeric", minute: "2-digit"}) + " (" + ago(gen) + ")";
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
        if (!run || new Date(run.created_at) < since) $("upd-status").textContent = "Starting run…";
        else if (run.status !== "completed") $("upd-status").innerHTML = "Pulling lines and running the model… " + mins + " min (usually 3–6). <a href='" + run.html_url + "' target='_blank' rel='noopener'>Progress</a>";
        else if (run.conclusion === "success") { $("upd-status").textContent = "Done. Loading the new card…"; setTimeout(() => location.replace(location.pathname + "?t=" + Date.now()), 4000); return; }
        else { $("upd-status").innerHTML = "The run failed (" + esc(run.conclusion) + "). <a href='" + run.html_url + "' target='_blank' rel='noopener'>See why</a>"; btn.disabled = false; return; }
      } catch (e) { $("upd-status").textContent = "Lost contact with GitHub, retrying…"; }
      setTimeout(tick, 10000);
    };
    tick();
  };
  $("upd-btn").onclick = async () => {
    if (!store.get() && !askKey()) { window.open(RUNS_URL, "_blank", "noopener"); $("upd-status").innerHTML = "No token saved: on GitHub, click <b>Run workflow</b>, then reload this page when it finishes."; return; }
    const since = new Date(Date.now() - 5000);
    $("upd-status").textContent = "Starting run…";
    const branch = (await (await fetch("https://api.github.com/repos/" + REPO)).json().catch(() => ({}))).default_branch || "main";
    const r = await gh("/workflows/" + WF + "/dispatches", { method: "POST", body: JSON.stringify({ ref: branch }) }).catch(() => null);
    if (r && r.status === 204) followRun(since);
    else if (r && [401, 403, 404].includes(r.status)) { store.set(""); $("upd-status").textContent = "GitHub refused the saved token (" + r.status + "). Click Update now to enter a new one."; }
    else $("upd-status").textContent = "Couldn't reach GitHub. Try again in a minute.";
  };
  if (store.get()) gh("/workflows/" + WF + "/runs?per_page=1").then((r) => r.json()).then((j) => {
    const run = j.workflow_runs?.[0]; if (run && run.status !== "completed") followRun(new Date(run.created_at)); }).catch(() => {});
})();
</script>
"""
