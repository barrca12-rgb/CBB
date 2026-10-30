"""Venue / neutral-flag check, November 2026 and the November 2025 calibration (Chad's Oct 30 brief, item 1).

Reads and displays only; the model's flag is never changed. Steps:
  arenas    data/home_arenas.csv: each D-I team's home arena (ESPN's team venue id: from the Nov 2026 scoreboard,
            else last season's schedule) plus alternate home arenas (3+ non-neutral home games there in the three
            seasons before), with names and cities from ESPN's game venues
  nov2026   every game on ESPN's scoreboard Nov 1-30, 2026, classified by cbb/venue.py
  nov2025   the same classification on Nov 2025 (arenas as of that season, alternates from 2023-2025), then on the
            conflicts the frozen live-like model re-scored with the venue-corrected flag

Re-scoring: the corrected venue value v is +1 (listed home team at home), 0 (neutral) or -1 (listed away team at
home). Every input that depends on the flag is recomputed with the model's own formulas: stage-1 home court
(ratings refit per date, cbb/ratings.predict), KenPom's +-2% home edge (cbb/kenpom._predict), the venue and team
home-court terms (cbb/projection), the market rating's home term (cbb/context.market re-run), altitude, and the
stage-1 four-factor home terms. The frozen 2025-26 stage-2 coefficients (walk-forward fit on 2013-2025, ridge 1)
are applied to the changes. Other games' flags inside the rating fits are left as recorded.

    python -m research.venue.check arenas | nov2026 | nov2025 | all
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

from cbb import backtest, context, data, projection, ratings, teams, venue

OUT = os.path.join(os.path.dirname(__file__), "out")
L: list[str] = []


def say(s=""):
    L.append(str(s))
    print(s, flush=True)


def schedules(seasons) -> pd.DataFrame:
    s = pd.concat([data.fetch("schedule", y).assign(season=y) for y in seasons], ignore_index=True)
    ids = set(teams.load()["espn_id"])
    s = s[s["home_id"].isin(ids) & s["away_id"].isin(ids)].copy()
    s["date"] = pd.to_datetime(s["date"]).dt.tz_localize(None).dt.normalize() if pd.to_datetime(s["date"]).dt.tz is not None \
        else pd.to_datetime(s["date"]).dt.normalize()
    s["neutral_site"] = s["neutral_site"].astype(bool)
    return s


def venue_names(s: pd.DataFrame) -> pd.DataFrame:
    v = s.dropna(subset=["venue_id"]).drop_duplicates("venue_id", keep="last")
    return v.set_index(v["venue_id"].astype(int))[["venue_full_name", "venue_address_city", "venue_address_state"]]


def build_arenas(alt_seasons, primary: dict | None = None, primary_season: int | None = None) -> pd.DataFrame:
    """One row per D-I team. primary: team -> venue id (ESPN's current team venue); falls back to the latest
    home_venue_id in primary_season's schedule."""
    t = teams.load()
    s = schedules(sorted(set(alt_seasons) | ({primary_season} if primary_season else set())))
    names = venue_names(s)
    last = {}
    if primary_season:
        ps = s[s["season"] == primary_season].sort_values("date")
        for col_t, col_v in (("home_id", "home_venue_id"), ("away_id", "away_venue_id")):
            for tid, vid in zip(ps[col_t], ps[col_v]):
                if pd.notna(vid):
                    last[int(tid)] = int(vid)
    prim = {**last, **(primary or {})}
    al = s[s["season"].isin(alt_seasons) & ~s["neutral_site"]]
    cnt = al.groupby(["home_id", "venue_id"]).size()
    rows = []
    for _, r in t.iterrows():
        tid = int(r["espn_id"])
        pv = prim.get(tid)
        alts = sorted(int(v) for (h, v), n in cnt.items() if h == tid and n >= 3 and int(v) != pv) if tid in cnt.index.get_level_values(0) else []
        nm = names.reindex([pv]).iloc[0] if pv is not None and pv in names.index else None
        rows.append({"espn_id": tid, "team": r.get("espn_location"), "venue_id": pv,
                     "arena": nm["venue_full_name"] if nm is not None else None,
                     "city": nm["venue_address_city"] if nm is not None else None,
                     "state": nm["venue_address_state"] if nm is not None else None,
                     "alt_venue_ids": ";".join(map(str, alts)),
                     "alt_arenas": "; ".join(str(names.loc[v, "venue_full_name"]) for v in alts if v in names.index),
                     "source": "ESPN scoreboard team venue (Nov 2026)" if primary and tid in primary else
                               (f"ESPN team venue, {primary_season} schedule" if pv is not None else "none")})
    return pd.DataFrame(rows)


def counts(df: pd.DataFrame, label: str) -> pd.DataFrame:
    c = df["venue_state"].value_counts().reindex(["confirmed", "conflict", "unknown"], fill_value=0)
    out = pd.DataFrame({"games": c, "share %": (100 * c / max(len(df), 1)).round(1)})
    say(f"\n{label}: {len(df)} D-I games")
    say(out.to_string())
    for flag in (True, False):
        sub = df[df["neutral"] == flag]
        say(f"  flagged {'neutral' if flag else 'home'}: {len(sub)} games, " +
            ", ".join(f"{k} {v}" for k, v in sub["venue_state"].value_counts().items()))
    say("  conflict reasons: " + "; ".join(f"{k} {v}" for k, v in df.loc[df['venue_state'] == 'conflict', 'reason'].value_counts().items()))
    say("  edge cases: " + "; ".join(f"{k} {v}" for k, v in df.loc[df['edge'].fillna('') != '', 'edge'].value_counts().items()) or "  edge cases: none")
    return out


# ------------------------------------------------------------------------------------------------- Nov 2026

def nov2026() -> pd.DataFrame:
    # current team venues straight from the scoreboard (competitor team.venue.id), then the table, then classify
    import json
    import urllib.request
    days = pd.date_range("2026-11-01", "2026-11-30")
    raw, prim = [], {}
    for d in days:
        req = urllib.request.Request(venue.SCOREBOARD.format(d.strftime("%Y%m%d")), headers={"User-Agent": "cbb-model"})
        with urllib.request.urlopen(req, timeout=60) as r:
            j = json.load(r)
        raw.append((d, j))
        for ev in j.get("events") or []:
            for t in ((ev.get("competitions") or [{}])[0].get("competitors") or []):
                vid = (t.get("team", {}).get("venue") or {}).get("id")
                if str(vid or "").isdigit():
                    prim[int(t["team"]["id"])] = int(vid)
    a = build_arenas([2024, 2025, 2026], primary=prim, primary_season=2026)
    a.to_csv(venue.ARENAS, index=False)
    ids = set(teams.load()["espn_id"])
    have = a["venue_id"].notna()
    say(f"home_arenas.csv: {int(have.sum())} of {len(a)} D-I teams have an arena on file "
        f"({int(a['espn_id'].isin(prim).sum())} from the Nov 2026 scoreboard, the rest from the 2025-26 schedule); "
        f"{int((a['alt_venue_ids'] != '').sum())} teams have an alternate home arena")
    parts = [venue.fetch_day(d) for d in days]
    g = pd.concat(parts, ignore_index=True)
    g = g[g["home_id"].isin(ids) & g["away_id"].isin(ids)]
    say(f"venue field: competitions[0].venue (id, fullName, address.city/state); blank for "
        f"{int(g['venue_id'].isna().sum())} of {len(g)} D-I games")
    g.to_csv(os.path.join(OUT, "nov2026.csv"), index=False)
    counts(g, "November 2026 (ESPN scoreboard, Oct 31 pull)")
    tn = teams.load().set_index("espn_id")["espn_location"]
    conf = g[g["venue_state"] == "conflict"].assign(home=lambda x: x["home_id"].map(tn), away=lambda x: x["away_id"].map(tn))
    say("\nNovember 2026 conflicts:")
    say(conf[["date", "away", "home", "neutral", "venue", "city", "event", "reason"]].to_string(index=False) if len(conf) else "none")
    ed = g[g["edge"].fillna("") != ""].assign(home=lambda x: x["home_id"].map(tn), away=lambda x: x["away_id"].map(tn))
    if len(ed):
        say("\nNovember 2026 edge cases (not conflicts):")
        say(ed[["date", "away", "home", "neutral", "venue", "city", "event", "edge"]].to_string(index=False))
    return g


# ------------------------------------------------------------------------------------------------- Nov 2025

def nov_classify(season: int) -> pd.DataFrame:
    """November of `season` (2026 = Nov 2025), arenas as of that season, alternates from the three before."""
    s = schedules([season])
    y = season - 1
    nov = s[(s["date"] >= f"{y}-11-01") & (s["date"] <= f"{y}-11-30")].copy()
    a = build_arenas([season - 3, season - 2, season - 1], primary=None, primary_season=season)
    a.to_csv(os.path.join(OUT, f"home_arenas_{y}-{str(season)[2:]}.csv"), index=False)
    sets, city = venue._venue_sets(a)
    rows = []
    for _, r in nov.iterrows():
        st, why, edge = venue.classify(bool(r["neutral_site"]), r["venue_id"], r["venue_address_city"], int(r["home_id"]),
                                       int(r["away_id"]), sets, city, r["home_venue_id"], r["away_venue_id"])
        rows.append({"game_id": int(r["game_id"]), "date": r["date"].strftime("%Y-%m-%d"), "home_id": int(r["home_id"]),
                     "away_id": int(r["away_id"]), "neutral": bool(r["neutral_site"]), "venue_id": r["venue_id"],
                     "venue": r["venue_full_name"], "city": r["venue_address_city"], "event": r.get("notes_headline"),
                     "venue_state": st, "reason": why, "edge": edge})
    g = pd.DataFrame(rows)
    g.to_csv(os.path.join(OUT, f"nov{y}.csv"), index=False)
    counts(g, f"November {y} (calibration; hoopR schedule = ESPN)")
    return g


def corrected_v(reason: str) -> float | None:
    return {"flagged neutral at the home team's arena": 1.0, "flagged neutral at the away team's arena": -1.0,
            "home game at the listed away team's arena": -1.0, "home game at an arena belonging to neither team": 0.0}.get(reason)


def rescore(conf: pd.DataFrame, season: int = 2026) -> pd.DataFrame:
    """Frozen live-like forecasts for the conflicts with the flag as given and venue-corrected."""
    from research.persistent_disagreement.common import baseline
    from research.quant.common import base_frames
    from research.originator.d_common import ridge_w
    train, _ = base_frames()
    w = baseline()
    w = w[w["game_id"].isin(conf["game_id"])].merge(conf[["game_id", "reason", "venue_state"]], on="game_id")
    w["v_old"] = (~w["neutral"].astype(bool)).astype(float)
    w["v_new"] = w["reason"].map(corrected_v)
    # stage-2 coefficients, season 2026 (fit on 2013-2025, as fit_predict)
    tr = train[(train["season"] < season) & (train["season"] >= 2013)]
    mf, tf = projection.MARGIN_FEATURES, projection.TOTAL_FEATURES
    cm = ridge_w(tr[mf].to_numpy(float), tr["margin"].to_numpy(float), np.ones(len(tr)), 1.0)
    ct = ridge_w(tr[tf].to_numpy(float), tr["points"].to_numpy(float), np.ones(len(tr)), 1.0)
    # stage 1: refit on each date, as backtest.season
    g, t = data.season_games(season)
    ids = sorted(set(t["team_id"]))
    pr = backtest.preseason_prior(season)
    league = ratings.league_averages(data.season_games(season - 1)[1])
    hca_tab = projection.team_hca_table(train, season)
    d = {f: np.zeros(len(w)) for f in mf + tf}
    check = []
    for day, idx in w.groupby("date").groups.items():
        r = ratings.fit(t, pd.Timestamp(day), ids, pr, None, league)
        x = w.loc[idx]
        p_old = ratings.predict(r, x["home_id"], x["away_id"], x["neutral"])
        check += list(np.abs(p_old["margin"].to_numpy() - x["pred_margin"].to_numpy()))
        dv = (x["v_new"] - x["v_old"]).to_numpy()
        pos = w.index.get_indexer(idx)
        d["pred_margin"][pos] = 2 * r["hca"] * p_old["poss"].to_numpy() / 100 * dv
        for f, fr in (r.get("factors") or {}).items():
            if f"{f}_diff" in d:
                d[f"{f}_diff"][pos] = 2 * fr["hca"] * dv
    # KenPom (frame values are KenPom's own method, +-2%): rescale each side's points
    hp = (w["kp_total"] + w["kp_margin"]) / 2
    ap = (w["kp_total"] - w["kp_margin"]) / 2
    hp2 = hp * (1 + 0.02 * w["v_new"]) / (1 + 0.02 * w["v_old"])
    ap2 = ap * (1 - 0.02 * w["v_new"]) / (1 - 0.02 * w["v_old"])
    d["kp_margin"] = ((hp2 - ap2) - w["kp_margin"]).fillna(0).to_numpy()
    d["kp_total"] = ((hp2 + ap2) - w["kp_total"]).fillna(0).to_numpy()
    d["pred_margin_x_early"] = d["pred_margin"] * w["early"].to_numpy()
    d["kp_margin_x_early"] = d["kp_margin"] * w["early"].to_numpy()
    d["kp_total_x_early"] = d["kp_total"] * w["early"].to_numpy()
    d["venue"] = (w["v_new"] - w["v_old"]).to_numpy()
    th = lambda tid: float(hca_tab.get(tid, 0.0))
    team_term = lambda v, h, a: th(h) if v > 0 else (-th(a) if v < 0 else 0.0)
    d["team_hca"] = np.array([team_term(n, h, a) - team_term(o, h, a) for n, o, h, a in
                              zip(w["v_new"], w["v_old"], w["home_id"], w["away_id"])])
    alt = lambda v, h, a: (1.0 if (v > 0 and h in context.ALTITUDE and a not in context.ALTITUDE) else
                           -1.0 if (v < 0 and a in context.ALTITUDE and h not in context.ALTITUDE) else 0.0)
    d["altitude"] = np.array([alt(n, h, a) - alt(o, h, a) for n, o, h, a in zip(w["v_new"], w["v_old"], w["home_id"], w["away_id"])])
    # market rating: re-run with the corrected flag (the home term is bm[1] * v); v = -1 by swapping teams
    closes = context.backtest_closes([season])
    keys = w[["game_id", "season", "date", "home_id", "away_id", "neutral"]].copy()
    m_old = context.market(keys, closes).set_index("game_id")["mkt_margin"]
    k2 = keys.copy()
    k2["neutral"] = w["v_new"] == 0
    sw = w["v_new"] < 0
    k2.loc[sw, ["home_id", "away_id"]] = keys.loc[sw, ["away_id", "home_id"]].to_numpy()
    k2.loc[sw, "neutral"] = False
    m_new = context.market(k2, closes).set_index("game_id")["mkt_margin"]
    m_new[w.loc[sw, "game_id"].to_numpy()] = -m_new[w.loc[sw, "game_id"].to_numpy()]
    wt = np.minimum(w["mkt_n"].fillna(0) / 10, 1).to_numpy()
    d["mkt_m"] = ((m_new.reindex(w["game_id"]).to_numpy() - m_old.reindex(w["game_id"]).to_numpy()) * wt)
    d["mkt_m"] = np.nan_to_num(d["mkt_m"])
    mcheck = np.nanmax(np.abs(m_old.reindex(w["game_id"]).to_numpy() * wt - w["mkt_m"].to_numpy())) if len(w) else 0
    w["d_margin"] = sum(cm[1 + j] * d[f] for j, f in enumerate(mf))
    w["d_total"] = sum(ct[1 + j] * d[f] for j, f in enumerate(tf) if f in ("kp_total", "kp_total_x_early", "altitude"))
    w["corr_margin"] = w["final_margin"] + w["d_margin"]
    w["corr_total"] = w["final_total"] + w["d_total"]
    say(f"\nre-score checks ({season}): stage-1 margin recomputed with the given flag vs the frame: mean |diff| "
        f"{np.mean(check) if check else 0:.3f}, max {max(check) if check else 0:.3f} (the change uses only the refit's home "
        f"court and possessions); "
        f"market term: max |diff| {mcheck:.4f}")
    return w


def grade(w: pd.DataFrame, label: str) -> None:
    w = w.copy()
    w["res"] = w["margin"] - w["final_margin"]
    w["res_c"] = w["margin"] - w["corr_margin"]
    s = np.sign(w["d_margin"])
    say(f"\n{label}: {len(w)} games with a forecast; mean change from the correction "
        f"{w['d_margin'].mean():+.2f} (|mean| {w['d_margin'].abs().mean():.2f}) points")
    say(f"  residual in the direction the correction predicts, sign(change) x (result - given forecast): "
        f"{(s * w['res']).mean():+.2f} points (SE {(s * w['res']).std(ddof=1) / np.sqrt(max(len(w), 2)):.2f})")
    say(f"  mean absolute error: given flag {w['res'].abs().mean():.2f}, corrected {w['res_c'].abs().mean():.2f}; "
        f"mean residual given {w['res'].mean():+.2f}, corrected {w['res_c'].mean():+.2f}")
    for line, lab in (("open_home_spread", "opener"), ("home_spread", "close")):
        x = w.dropna(subset=[line])
        for col, nm in (("final_margin", "given"), ("corr_margin", "corrected")):
            e = x[col] + x[line]
            cov = np.sign(e) * (x["margin"] + x[line])
            dec = cov[cov != 0]
            plays = (e.abs() >= 2.5) & (cov != 0)
            say(f"  vs the {lab} ({nm} flag): {len(dec)} decided games, model side won {100 * (dec > 0).mean():.1f}%; "
                f"edge 2.5+: {int(plays.sum())} plays, {int((cov[plays] > 0).sum())}-{int((cov[plays] < 0).sum())}")
    tn = teams.load().set_index("espn_id")["espn_location"]
    w["home"], w["away"] = w["home_id"].map(tn), w["away_id"].map(tn)
    cols = ["date", "away", "home", "neutral", "reason", "edge", "final_margin", "d_margin", "corr_margin", "margin",
            "open_home_spread", "home_spread"]
    return w[[c for c in cols if c in w]].round(2)


def main(what: str) -> None:
    os.makedirs(OUT, exist_ok=True)
    if what in ("nov2026", "all"):
        nov2026()
    if what in ("nov2025", "all"):
        tn = teams.load().set_index("espn_id")["espn_location"]
        allw, fulls = [], []
        for season in (2026, 2025, 2024):          # Nov 2025 (the brief's calibration), then Nov 2024 and Nov 2023
            g = nov_classify(season)
            conf = g[g["venue_state"] == "conflict"]
            say(f"\nNovember {season - 1} conflicts:")
            say(conf.assign(home=conf["home_id"].map(tn), away=conf["away_id"].map(tn))[
                ["date", "away", "home", "neutral", "venue", "city", "event", "reason", "edge"]].to_string(index=False) if len(conf) else "none")
            if len(conf):
                w = rescore(conf, season).merge(conf[["game_id", "edge"]], on="game_id", how="left")
                allw.append(grade(w, f"Nov {season - 1} conflicts re-scored"))
                fulls.append(w)
        if fulls:
            p = pd.concat(fulls, ignore_index=True)
            grade(p, "All three Novembers pooled")
            grade(p[p["edge"].fillna("") != "home city"], "Pooled, excluding home games at another venue in the home team's city")
        if allw:
            a = pd.concat(allw, ignore_index=True)
            a.to_csv(os.path.join(OUT, "nov_conflicts_rescored.csv"), index=False)
            say("\nPer game (all three Novembers):")
            say(a.to_string(index=False))
    open(os.path.join(OUT, f"check_{what}.txt"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
