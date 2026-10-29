"""Possessions from cached ESPN play-by-play, with the game state before each possession, and per-game validation.

Research only (research/game_state/PLAN.md). Nothing here is read by the live model.

A possession belongs to one offense and runs until the ball changes hands: a defensive rebound, a turnover, a made
field goal (with any and-one free throw at the same clock), the last free throw of a trip, or the end of a period.
In the event stream that is a maximal run of events whose "offense" is the same team:

    field-goal attempt, free throw, offensive rebound, turnover  -> offense = the event's team
    defensive rebound                                             -> offense = the rebounding team (a new possession)
    fouls, steals, blocks, timeouts, dead-ball rebounds, jump balls, substitutions -> no offense (skipped)

and a same-team run is split when the previous event ended a possession (a turnover, a made field goal or a made
last free throw), so an unrecorded possession in between doesn't merge two of them; a same-team free throw right
after a made basket or free throw continues the trip instead (and-ones are sometimes logged a second later).
Technical-foul free throws (taken at the clock of a technical foul) never start or end a possession.

State before each possession, from information known at that moment only:
    margin  the offense's lead (points) before the possession's first event
    tau     seconds left in regulation (period 1: 1200 + clock; period 2: clock); in overtime, seconds left in that
            overtime period
    start   the clock when the previous possession ended (period start for the first one)

Points on a possession = the offense's score increase from its first event to the start of the next possession.
Points the other team scores inside it (technical free throws) are counted in that team's total but tagged
`stray_pts`.

    python -m research.game_state.possessions          # -> out/poss_<season>.parquet, out/games_<season>.parquet
"""
from __future__ import annotations

import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

from cbb import data

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "out")
PBP = os.path.join(HERE, "..", "..", "cbb", "cache", "pbp")
SEASONS = list(range(2014, 2027))
COLS = ["game_id", "game_play_number", "sequence_number", "type_text", "text", "team_id", "home_team_id",
        "away_team_id", "home_score", "away_score", "period_number", "clock_display_value", "scoring_play",
        "shooting_play", "score_value"]
FGA_TYPES = {"JumpShot", "Three Point Jump Shot", "LayUpShot", "DunkShot", "TipShot", "Shot"}
# Late-game fouling, inferred (ESPN does not label strategic fouls; "Intentional Foul" is a flagrant-type call):
# a personal foul by the trailing defense on a possession that started with <= LATE seconds left in regulation or
# overtime, offense ahead by 1..MAXM, committed within QUICK seconds of the possession's start.
LATE, MAXM, QUICK = 120, 12, 8


def clock_secs(c: pd.Series) -> np.ndarray:
    s = c.astype(str)
    has = s.str.contains(":")
    mm = pd.to_numeric(s.str.split(":").str[0].where(has), errors="coerce")
    ss = pd.to_numeric(s.str.split(":").str[1].where(has), errors="coerce")
    plain = pd.to_numeric(s.where(~has), errors="coerce")
    return np.where(has, mm * 60 + ss, plain)


def build_season(season: int):
    p = pd.read_parquet(os.path.join(PBP, f"play_by_play_{season}.parquet"), columns=COLS)
    p = p.sort_values(["game_id", "game_play_number", "sequence_number"], kind="mergesort").reset_index(drop=True)
    p["clock"] = clock_secs(p["clock_display_value"])
    tt = p["type_text"].astype(str)
    tx = p["text"].astype(str)
    ft = tt.eq("MadeFreeThrow") | tx.str.contains("Free Throw", regex=False)
    fga = tt.isin(FGA_TYPES) & ~ft
    tov = tt.str.contains("Turnover", regex=False)
    orb = tt.eq("Offensive Rebound")
    drb = tt.eq("Defensive Rebound")
    foul = tt.eq("PersonalFoul")
    tech = tt.eq("Technical Foul")
    team = pd.to_numeric(p["team_id"], errors="coerce")
    poss_rows, game_rows = [], []
    for gid, g in p.groupby("game_id", sort=False):
        idx = g.index.to_numpy()
        home, away = int(g["home_team_id"].iloc[0]), int(g["away_team_id"].iloc[0])
        hs = pd.to_numeric(g["home_score"], errors="coerce").ffill().fillna(0).to_numpy()
        as_ = pd.to_numeric(g["away_score"], errors="coerce").ffill().fillna(0).to_numpy()
        per = g["period_number"].to_numpy()
        clk = g["clock"].to_numpy()
        tm = team.loc[idx].to_numpy()
        is_fga, is_ft, is_tov, is_orb, is_drb = (fga.loc[idx].to_numpy(), ft.loc[idx].to_numpy(), tov.loc[idx].to_numpy(),
                                                  orb.loc[idx].to_numpy(), drb.loc[idx].to_numpy())
        is_foul, is_tech = foul.loc[idx].to_numpy(), tech.loc[idx].to_numpy()
        made = g["scoring_play"].fillna(False).astype(bool).to_numpy()
        n = len(idx)
        clock_bad = int(np.sum(np.isnan(clk)))
        # technical free throws: free throws at the same period and clock as a technical foul
        tech_keys = {(per[i], clk[i]) for i in range(n) if is_tech[i]}
        cur, ended, last_per, end_reason = None, False, None, ""
        poss = []          # [offense, period, start_clock, first_event_i, last_event_i, foul_quick_by_def]
        prev_end_clock = None
        for i in range(n):
            if per[i] != last_per:
                if cur is not None:
                    poss[-1][4] = i - 1
                cur, ended, last_per = None, False, per[i]
                prev_end_clock = 1200.0 if per[i] <= 2 else 300.0
            t = tm[i]
            if np.isnan(t) or int(t) not in (home, away):
                continue
            t = int(t)
            off = None
            if is_fga[i] or is_tov[i] or is_orb[i] or is_drb[i]:
                off = t
            elif is_ft[i]:
                if (per[i], clk[i]) in tech_keys and cur is not None and t != cur:
                    continue                                  # technical free throw by the defense
                off = t
            elif is_foul[i] and cur is not None and t != cur and len(poss):
                # observed personal foul by the defense; flag quick ones (inferred strategic fouling decided later)
                st = poss[-1][2]
                if not np.isnan(clk[i]) and st - clk[i] <= QUICK:
                    poss[-1][5] = True
                continue
            if off is None:
                continue
            # a same-team free throw after a made basket or a made free throw continues the trip (and-ones and
            # trips are sometimes logged a second apart); after a turnover it starts a new possession
            cont = off == cur and ended and is_ft[i] and end_reason != "tov"
            new = cur is None or off != cur or (ended and not cont)
            if new:
                if cur is not None:
                    poss[-1][4] = i - 1
                    prev_end_clock = clk[poss[-1][6]] if not np.isnan(clk[poss[-1][6]]) else prev_end_clock
                poss.append([off, per[i], prev_end_clock, i, n - 1, False, i])
                cur, ended = off, False
            poss[-1][6] = i                                   # last offensive event of this possession
            # does this event end the possession for the same team?
            end_reason = "tov" if is_tov[i] else "score"
            if is_tov[i]:
                ended = True
            elif is_fga[i] and made[i]:
                # and-one: free throws by the same team at the same clock keep the possession open
                j = i + 1
                andone = False
                while j < n and per[j] == per[i] and clk[j] == clk[i]:
                    if is_ft[j] and tm[j] == t:
                        andone = True
                        break
                    j += 1
                ended = not andone
            elif is_ft[i] and made[i]:
                # last free throw of a trip ends it unless another free throw by the same team follows at that clock
                j = i + 1
                more = False
                while j < n and per[j] == per[i] and clk[j] == clk[i]:
                    if is_ft[j] and tm[j] == t:
                        more = True
                        break
                    j += 1
                ended = not more
            else:
                ended = False
        if cur is not None:
            poss[-1][4] = n - 1
        # scores before each event (score after the previous event)
        hb = np.r_[0.0, hs[:-1]]
        ab = np.r_[0.0, as_[:-1]]
        rows = []
        for k, (off, pr, st, i0, i1, qf, ilast) in enumerate(poss):
            nxt_start = poss[k + 1][3] if k + 1 < len(poss) and poss[k + 1][1] == pr else None
            end_i = (nxt_start - 1) if nxt_start is not None else i1
            # points: score change from just before the first event to just before the next possession's first event
            h0, a0 = hb[i0], ab[i0]
            h1, a1 = (hb[nxt_start], ab[nxt_start]) if nxt_start is not None else (hs[end_i], as_[end_i])
            dh, da = h1 - h0, a1 - a0
            pts, stray = (dh, da) if off == home else (da, dh)
            margin = (h0 - a0) if off == home else (a0 - h0)
            end_clock = poss[k + 1][2] if nxt_start is not None else 0.0
            tau = (1200 + st) if pr == 1 else st
            rows.append((gid, off, pr, st, end_clock, margin, tau, pts, stray, qf))
        pdf = pd.DataFrame(rows, columns=["game_id", "offense", "period", "start", "end", "margin", "tau", "pts",
                                          "stray_pts", "quick_def_foul"])
        pdf["dur"] = (pdf["start"] - pdf["end"]).clip(lower=0)
        pdf["late_foul"] = pdf["quick_def_foul"] & (pdf["tau"] <= LATE) & ((pdf["period"] >= 2)) & pdf["margin"].between(1, MAXM)
        poss_rows.append(pdf)
        nh, na = int((pdf["offense"] == home).sum()), int((pdf["offense"] == away).sum())
        game_rows.append({"game_id": gid, "home_id": home, "away_id": away, "pbp_home_pts": hs[-1], "pbp_away_pts": as_[-1],
                          "pbp_periods": int(np.nanmax(per)), "events": n, "clock_missing": clock_bad,
                          "clock_increases": int(sum(1 for i in range(1, n) if per[i] == per[i - 1] and clk[i] > clk[i - 1] + 0.5)),
                          "poss_home": nh, "poss_away": na,
                          "sum_pts_home": float(pdf.loc[pdf["offense"] == home, "pts"].sum() + pdf.loc[pdf["offense"] == away, "stray_pts"].sum()),
                          "sum_pts_away": float(pdf.loc[pdf["offense"] == away, "pts"].sum() + pdf.loc[pdf["offense"] == home, "stray_pts"].sum()),
                          "observed_fouls": int(is_foul.sum()), "quick_def_fouls": int(pdf["quick_def_foul"].sum()),
                          "late_foul_poss": int(pdf["late_foul"].sum())})
    P = pd.concat(poss_rows, ignore_index=True)
    G = pd.DataFrame(game_rows)
    G["season"] = season
    return P, G


def validate(G: pd.DataFrame, season: int) -> pd.DataFrame:
    """Join the schedule's final score and periods and the box-score possession estimate; flag valid games."""
    g, t = data.season_games(season)
    s = g.set_index("game_id")[["home_pts", "away_pts", "periods"]]
    G = G.join(s, on="game_id")
    box = t.groupby("game_id")["poss"].first()                 # average of both teams' box estimates (full game)
    G["box_poss"] = G["game_id"].map(box)
    G["in_model"] = G["game_id"].isin(s.index)
    G["final_ok"] = (G["pbp_home_pts"] == G["home_pts"]) & (G["pbp_away_pts"] == G["away_pts"])
    G["periods_ok"] = G["pbp_periods"] == G["periods"]
    G["sum_ok"] = (G["sum_pts_home"] == G["home_pts"]) & (G["sum_pts_away"] == G["away_pts"])
    G["balance"] = (G["poss_home"] - G["poss_away"]).abs()
    G["clock_ok"] = (G["clock_missing"] == 0) & (G["clock_increases"] == 0)
    G["poss_ratio"] = ((G["poss_home"] + G["poss_away"]) / 2) / G["box_poss"]
    G["valid"] = G["in_model"] & G["final_ok"] & G["periods_ok"] & G["sum_ok"] & G["clock_ok"] & \
        (G["balance"] <= G["pbp_periods"] + 1) & G["poss_ratio"].between(0.9, 1.1)
    return G


def run(season: int):
    P, G = build_season(season)
    G = validate(G, season)
    P.to_parquet(os.path.join(OUT, f"poss_{season}.parquet"), index=False)
    G.to_parquet(os.path.join(OUT, f"games_{season}.parquet"), index=False)
    return season, len(G), int(G["valid"].sum())


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    if sys.argv[1:] == ["summary"]:
        txt = summary()
        open(os.path.join(OUT, "possession_validation.txt"), "w").write(txt + "\n")
        print(txt)
        return
    seasons = [int(x) for x in sys.argv[1:]] or SEASONS
    with Pool(4) as pool:
        for s, n, v in pool.imap_unordered(run, seasons):
            print(s, n, v, flush=True)


def summary() -> str:
    """Coverage and validation table across seasons (out/possession_validation.txt)."""
    rows = []
    for s in SEASONS:
        G = pd.read_parquet(os.path.join(OUT, f"games_{s}.parquet"))
        P = pd.read_parquet(os.path.join(OUT, f"poss_{s}.parquet"))
        g, _ = data.season_games(s)
        m = G[G["in_model"]]
        v = m[m["valid"]]
        pv = P[P["game_id"].isin(v["game_id"])]
        ot = v[v["periods"] > 2]
        late = pv[(pv["period"] >= 2) & (pv["tau"] <= LATE)]
        rows.append({
            "season": s, "model games": len(g), "with pbp": len(m), "valid": len(v),
            "coverage %": 100 * len(v) / len(g),
            "fail final": int((~m["final_ok"]).sum()), "fail periods": int((m["final_ok"] & ~m["periods_ok"]).sum()),
            "fail points sum": int((m["final_ok"] & m["periods_ok"] & ~m["sum_ok"]).sum()),
            "fail clock": int((~m["clock_ok"]).sum()), "fail balance/ratio": int((m["final_ok"] & m["periods_ok"] & m["sum_ok"] & m["clock_ok"] & ~m["valid"]).sum()),
            "poss/box mean": v["poss_ratio"].mean(), "poss/box sd": v["poss_ratio"].std(),
            "OT games": len(ot), "OT poss/game": len(pv[pv["period"] > 2]) / max(len(ot), 1),
            "observed fouls/game": v["observed_fouls"].mean(),
            "late-foul poss/game": v["late_foul_poss"].mean(),
            "late-foul pts/poss": pv.loc[pv["late_foul"], "pts"].mean(),
            "late (<=2:00) pts/poss": late["pts"].mean(), "all pts/poss": pv["pts"].mean(),
        })
    t = pd.DataFrame(rows)
    return t.round(3).to_string(index=False)


if __name__ == "__main__":
    main()
