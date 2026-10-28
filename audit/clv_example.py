"""One play's CLV, traced end to end (audit/CLV_VERIFICATION.md, item 6): the alert entry, every quote observed around
the closing window with each inclusion or exclusion and its reason, the consensus close, the signed CLV in points and
the price comparison, and what every surface shows, with an explicit agreement check. Read only.

    python -m audit.clv_example "2026-11-01|401920982|total|under"     # -> audit/examples/clv_<bet_id>.md
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

from audit import forward_eval as fe

OUT = os.path.join(os.path.dirname(__file__), "examples")


def _fmt(x, f="{:+.2f}"):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f.format(x)


def poll_timeline(cutoff) -> pd.DataFrame:
    """Every poll attempt (card pulls and targeted polls) in the 20 minutes before the cutoff."""
    if cutoff is None:
        return pd.DataFrame()
    parts = []
    for name in ("polls.csv", "polls_targeted.csv"):
        f = os.path.join(fe.ROOT, "lines", name)
        if os.path.exists(f):
            parts.append(pd.read_csv(f).assign(log=name.replace(".csv", "")))
    if not parts:
        return pd.DataFrame()
    p = pd.concat(parts, ignore_index=True)
    p["t"] = pd.to_datetime(p["observed_at"], utc=True, errors="coerce", format="ISO8601")
    return p[(p["t"] >= cutoff - pd.Timedelta(minutes=20)) & (p["t"] < cutoff)].sort_values("t")


def window_rows(og: pd.DataFrame, b: pd.Series, cutoff) -> pd.DataFrame:
    """Every observation of the play's market from 20 minutes before the cutoff to 10 minutes after, each labeled
    with what the protocol does with it (the selection itself is fe.strict_close's; this only explains it)."""
    if cutoff is None or not len(og):
        return pd.DataFrame()
    w = og[(og["market"] == b["market"]) & (og["t"] >= cutoff - pd.Timedelta(minutes=20)) &
           (og["t"] < cutoff + pd.Timedelta(minutes=10))].copy()
    valid = w["book"].isin(fe.BOOKS) & (w["t"] >= cutoff - fe.STRICT_WINDOW) & (w["t"] < cutoff) & \
        ~(w["t"] >= w["st"]) & (w["status"] == "available") & w["age"].between(-fe.CLOCK_SKEW_S, fe.STRICT_MAX_AGE_S) & \
        w["line"].notna()
    last = w[valid].groupby("book", sort=True).tail(1).index      # the same deterministic order as strict_close

    def why(i, r):
        if i in last:
            return "INCLUDED: the book's last valid quote in the window"
        if not r["book"] in fe.BOOKS:
            return "excluded: not one of the 7 eligible books"
        if r["t"] >= cutoff or r["t"] >= r["st"]:
            return "excluded: at or after the tip cutoff / its own reported start (in play)"
        if r["t"] < cutoff - fe.STRICT_WINDOW:
            return "excluded: before the 15-minute window"
        if r["status"] != "available":
            return f"excluded: status {r['status']}"
        if not (-fe.CLOCK_SKEW_S <= r["age"] <= fe.STRICT_MAX_AGE_S) if pd.notna(r["age"]) else True:
            return f"excluded: feed timestamp {'missing' if pd.isna(r['age']) else f'{int(r['age'])} s old'} (limit {fe.STRICT_MAX_AGE_S} s)"
        if pd.isna(r["line"]):
            return "excluded: no number"
        return "superseded: a later valid quote from the same book was used"
    w["role"] = [why(i, r) for i, r in w.iterrows()]
    return w


def build(bet_id: str) -> str:
    from cbb import clv_primary, record, record_chart, record_page, report_html, review, tracker
    bets = tracker.load()
    b = bets[bets["bet_id"] == bet_id]
    if not len(b):
        raise SystemExit(f"no bet {bet_id}")
    b = b.iloc[0]
    a = clv_primary.attach(bets)
    r = a[a["bet_id"] == bet_id].iloc[0]
    p = clv_primary.primary(bets[bets["bet_id"] == bet_id]).iloc[0]
    o = clv_primary._load_obs(None)
    key = f"{b['date']}|{min(int(b['home_id']), int(b['away_id']))}|{max(int(b['home_id']), int(b['away_id']))}"
    og = o[o["game_key"] == key] if len(o) else o
    cutoff = pd.Timestamp(p["cutoff"]) if p["cutoff"] else None
    L = []
    L.append(f"# CLV traced: {b['pick']} ({b['away']} at {b['home']}, {b['date']})\n")
    L.append(f"Bet id `{bet_id}`. Generated {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC by `python -m audit.clv_example`. "
             f"CLV tracking status: **{clv_primary.VERIFICATION_STATUS}**.\n")

    L.append("## 1. Entry (as logged at the alert; never edited)\n")
    L.append("| Field | Value |\n|---|---|")
    for k in ("market", "side", "line", "alert_line", "odds", "book", "edge", "model", "logged_at", "placed", "stake"):
        L.append(f"| {k} | {b.get(k)} |")
    L.append(f"| cohort | {p['cohort']} (model v1 cohort A starts {fe.PROTOCOL_START:%Y-%m-%d %H:%M:%S} UTC) |")
    al = os.path.join(fe.ROOT, "bets", "alert_log.csv")
    if os.path.exists(al):
        x = pd.read_csv(al)
        x = x[x["id"] == bet_id]
        L.append(f"| alert sends (bets/alert_log.csv) | {'; '.join(f'{c} {k} at {t} ok={ok}' for c, k, t, ok in zip(x['channel'], x['kind'], x['sent_at'], x['ok'])) or 'none recorded (logged before the alert log existed)'} |")
    sl = os.path.join(fe.ROOT, "bets", "signal_log.csv")
    s = pd.read_csv(sl) if os.path.exists(sl) else pd.DataFrame(columns=["bet_id"])
    s = s[s["bet_id"] == bet_id]
    L.append(f"| cohort B record (bets/signal_log.csv) | "
             + (f"{s.iloc[0]['book']} {s.iloc[0]['line']} at {s.iloc[0]['odds']}, quote status {s.iloc[0]['quote_status']}, age {s.iloc[0]['quote_age_s']} s"
                if len(s) else "none: no observed generating quote, so this play is not in cohort B") + " |")
    acc = os.path.join(fe.ROOT, "bets", "accepted.csv")
    c = pd.read_csv(acc) if os.path.exists(acc) else pd.DataFrame(columns=["bet_id"])
    c = c[c["bet_id"] == bet_id]
    L.append(f"| cohort C record (bets/accepted.csv) | "
             + (f"{c.iloc[0]['book']} {c.iloc[0]['line']} at {c.iloc[0]['odds']}, placed {c.iloc[0]['placed_at']} ({c.iloc[0]['source']})"
                if len(c) else "none: no confirmed fill. The `placed` flag is not a confirmation; this entry is the alert price, not a filled bet") + " |\n")

    L.append("## 2. Tip cutoff\n")
    L.append(f"- Cutoff: **{p['cutoff']}** (source: {p['cutoff_source']}; `forward_eval.tip_cutoff`: the start carried by the "
             f"latest observation made before its own reported start, else `lines/closing.csv`'s start). All times UTC.")
    L.append(f"- ESPN scheduled start (card file, diagnostic): {p['espn_start']}; difference {p['start_gap_min']} min.")
    L.append(f"- Window: [{(cutoff - fe.STRICT_WINDOW).isoformat() if cutoff is not None else 'n/a'}, {p['cutoff']}), "
             f"freshness: feed timestamp at most {fe.STRICT_MAX_AGE_S} s old (up to {fe.CLOCK_SKEW_S} s ahead accepted).\n")

    L.append("## 3. Every quote observed around the window\n")
    w = window_rows(og, b, cutoff)
    if len(w):
        L.append("| Observed (UTC) | Poll | Log | Feed | Book | Side | Line | Price | Feed timestamp | Age (s) | Status | Reported start | Role |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for _, x in w.iterrows():
            L.append(f"| {x['t']:%H:%M:%S} | {x.get('poll_id', '')} | {x['log']} | {x['source']} | {x['book']} | {x['side']} | {x['line']} | {x['price']} | "
                     f"{x['source_updated_at']} | {'' if pd.isna(x['age']) else int(x['age'])} | {x['status']} | {x['start']} | {x['role']} |")
    else:
        L.append("No observations of this game's market around the window.")
    L.append("")
    polls = poll_timeline(cutoff)
    L.append("### Polls in the 20 minutes before the cutoff (lines/polls.csv, lines/polls_targeted.csv)\n")
    if len(polls):
        L.append("| Poll (UTC) | Log | Source | Status | Quotes | Note |\n|---|---|---|---|---|---|")
        L += [f"| {r['t']:%H:%M:%S} | {r['log']} | {r['source']} | {r['status']} | {r.get('quotes', '')} | {r.get('error', '') if pd.notna(r.get('error')) else ''} |"
              for _, r in polls.iterrows()]
        gaps = polls[polls["status"] == "ok"]["t"].sort_values().diff().dt.total_seconds().dropna()
        L.append(f"\nLongest gap between successful polls: {int(gaps.max()) if len(gaps) else 'n/a'} s.")
    else:
        L.append("No poll recorded in that window.")
    L.append("")

    L.append("## 4. Consensus close and CLV\n")
    L.append(f"- Status: **{p['clv_status']}**: {p['clv_reason']}")
    L.append(f"- Books: {p['books_primary']}; quote ages (s): {p['feed_age_s']}; observed before cutoff (s): {p['obs_before_cutoff_s']}")
    L.append(f"- Consensus close (median, from the play's side): **{_fmt(p['close_primary'], '{:g}')}**")
    L.append(f"- CLV, points (`forward_eval.line_value`, + = better entry than the close): **{_fmt(p['clv_primary'])}**")
    pv = json.loads(p["price_vs_close"] or "[]")
    if pv:
        L.append("- Price, each closing book on the play's side vs the entry (protocol measure A: number, then payout; no "
                 "conversion to probability):\n\n| Book | Close line | Close price | Age (s) | Close quote vs the entry |\n|---|---|---|---|---|")
        L += [f"| {v['book']} | {v['line']} | {v['price']} | {v['age_s']} | {v['vs_entry']} |" for v in pv]
        L.append("\n  Read each row as \"is this closing quote at least as good as the entry?\" (protocol measure A, from the "
                 "bettor's side). \"no: ...\" = the closing quote was worse, so the entry beat it (by number, or by price at the same "
                 "number); \"yes: ...\" = a bettor at the close could match or beat the entry; \"ambiguous\" = a better number at a "
                 "worse price, which the protocol does not convert.")
    L.append(f"- Same-book close (grader, `bets/bets.csv`, diagnostic only): {_fmt(b['close_line'], '{:g}')}; "
             f"same-book CLV {_fmt(b['clv_pts'])}\n")

    L.append("## 5. What every surface shows\n")
    rows = []
    rows.append(("bets/clv_primary.csv (stored)", _fmt(p["clv_primary"])))
    if r["status"] == "settled":
        f = {x["name"]: x["value"] for x in record._settled(r)["embeds"][0]["fields"]}
        rows.append(("Discord result post (payload)", f.get("CLV", "").replace(" pts", "")))
    v = report_html._clv_view()
    rec = {x["bet_id"] if "bet_id" in x else x["pick"]: x for x in (v.get("recent") or [])}
    rr = next((x for x in (v.get("recent") or []) if x["pick"] == b["pick"] and x["date"] == b["date"]), None)
    rows.append(("Card recent-results table", _fmt(rr["clv_pts"]) if rr else "not settled"))
    st = a[(a["status"] == "settled")]
    pr = record_page.summary(st)
    rows.append(("Record page play row", _fmt(r["clv_pts"]) if r["status"] == "settled" else "not settled"))
    cl = review.classify().set_index("bet_id")["reason"] if r["status"] == "settled" else pd.Series(dtype=str)
    rows.append(("Loss review reason", str(cl.get(bet_id, "not settled"))))
    t = tracker.tripwires()["model"]
    L.append("| Surface | CLV for this play |\n|---|---|")
    L += [f"| {k} | {val} |" for k, val in rows]
    vals = {val for k, val in rows if k not in ("Loss review reason",) and val not in ("not settled",)}
    L.append(f"\n**Agreement:** {'all surfaces show ' + vals.pop() if len(vals) == 1 else 'MISMATCH: ' + ', '.join(sorted(vals))}.\n")
    L.append("Averages that include this play (decided plays with a primary close; coverage beside each):\n")
    L.append("| Surface | Average CLV | Coverage |\n|---|---|---|")
    L.append(f"| Card Avg CLV tile | {_fmt(v['all']['clv'])} | {v['all']['with_close']}/{v['all']['decided']} |")
    L.append(f"| Record page Avg CLV | {_fmt(pr['clv'])} | {pr['cov']} |")
    ch = record_chart.stats(a, pd.Timestamp(b["date"]) + pd.Timedelta(days=7))
    for mk in ("spread", "total"):
        tl = ch["tiles"][mk]
        L.append(f"| Weekly chart, {mk}s | {_fmt(tl['mean']) if tl['n'] else 'n/a'} | {tl['n']}/{tl['decided']} |")
    L.append(f"| Model-check tripwire | {_fmt(t['clv'])} | {t['with_close']} with a close, {t['missing']} missing; state {t['state']} (fires from {t['min']}) |")
    cv = clv_primary.coverage(a[(a["status"] == "settled")])
    L.append(f"\nClosing-data coverage, all decided plays: {clv_primary.coverage_text(cv)}.\n")

    # evidence checklist: "first live capture verified" only when every check passes
    inc = w[w["role"].str.startswith("INCLUDED")] if len(w) else pd.DataFrame()
    checks = [
        ("Original entry present (line, odds, book, logged time)", all(pd.notna(b.get(k)) for k in ("line", "odds", "book", "logged_at"))),
        ("Game settled (final score graded)", r["status"] == "settled"),
        ("Cutoff known and its source stated", bool(p["cutoff"]) and bool(p["cutoff_source"])),
        ("Tip time consistent: cutoff within 10 min of ESPN's start and the feed's latest start", p["tip_check"] == "ok"),
        ("At least 2 eligible books with a fresh quote in the window", int(p["books_primary"] or 0) >= 2),
        ("Every included quote: observed in the window, before the cutoff and its own start, age <= 300 s",
         len(inc) > 0 and bool(((inc["t"] >= cutoff - fe.STRICT_WINDOW) & (inc["t"] < cutoff) & (inc["t"] < inc["st"]) &
                                inc["age"].between(-fe.CLOCK_SKEW_S, fe.STRICT_MAX_AGE_S)).all())),
        ("Included books match the stored book count", len(inc) == int(p["books_primary"] or 0)),
        ("Signed CLV equals the protocol's line value at the stored close",
         pd.notna(p["clv_primary"]) and abs(float(p["clv_primary"]) - fe.line_value(b, float(p["close_primary"]))) < 1e-9),
        ("Every surface shows the same CLV", len({val for k, val in rows if k != "Loss review reason" and val != "not settled"}) == 1),
    ]
    L.append("## 6. Evidence checklist\n")
    L.append("| Check | Result |\n|---|---|")
    L += [f"| {k} | {'pass' if ok else 'FAIL'} |" for k, ok in checks]
    open_items = []
    if p["tip_check"] != "ok":
        open_items.append(f"tip time {p['tip_check']}: cutoff {p['cutoff']} vs ESPN {p['espn_start']} / feed latest {p['feed_latest_start']}")
    if 0 < int(p["books_primary"] or 0) < 7:
        open_items.append(f"{p['books_primary']} of 7 books in the close")
    if not len(c):
        open_items.append("no confirmed fill (cohort C); CLV is the alert price's")
    L.append("\n**Open items (stay visible whatever the verdict):** " + ("; ".join(open_items) if open_items else "none") + ".")
    verdict = all(ok for _, ok in checks)
    L.append(f"\n**Verdict: {'first live capture verified' if verdict else 'first live capture NOT verified: ' + '; '.join(k for k, ok in checks if not ok)}.** "
             f"The overall CLV tracking status stays \"{clv_primary.VERIFICATION_STATUS}\" until Chad changes it.\n")
    return "\n".join(L) + "\n"


def main() -> None:
    bet_id = sys.argv[1] if len(sys.argv) > 1 else "2026-11-01|401920982|total|under"
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"clv_{bet_id.replace('|', '_')}.md")
    with open(path, "w") as fh:
        fh.write(build(bet_id))
    print(path)


if __name__ == "__main__":
    main()
