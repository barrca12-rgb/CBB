"""Check 4: venue and neutral-flag audit (LOG.md). Saves out/c4_flagged_games.csv for the March crowd test.

    python -m research.calibration.c4_venue
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import teams
from research.calibration.common import OUT, base, boot_mean

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
COLS = ["game_id", "neutral_site", "venue_id", "venue_full_name", "venue_address_city", "venue_address_state",
        "home_venue_id", "away_venue_id"]


def schedule(s: int) -> pd.DataFrame:
    d = pd.read_parquet(os.path.join(ROOT, "cbb", "cache", f"mbb_schedule_{s}.parquet"))
    return d[[c for c in COLS if c in d]].drop_duplicates("game_id").assign(season=s)


def plays(d: pd.DataFrame, line: str, side_col: str = "fav_flag") -> tuple[int, float]:
    x = d.dropna(subset=[line])
    e = x["final_margin"] + x[line]
    x = x[e.abs() >= 2.5]
    m = (x["margin"] + x[line]) * np.sign(e[e.abs() >= 2.5])
    m = m[m != 0]
    return len(m), (round(100 * (m > 0).mean(), 1) if len(m) else np.nan)


def main() -> None:
    w = base()
    w = w[w["season"].between(2014, 2026)]
    sch = pd.concat([schedule(s) for s in range(2014, 2027)])
    d = w.merge(sch, on=["game_id", "season"], how="left")
    loc = teams.load().drop_duplicates("espn_id").set_index("espn_id")["espn_location"]
    # each team's home city per season: most common city of its non-neutral home games
    hc = d[~d["neutral"].astype(bool)].groupby(["season", "home_id"])["venue_address_city"].agg(
        lambda s: s.mode().iloc[0] if s.notna().any() else None)
    d["home_city"] = [hc.get((s, h)) for s, h in zip(d["season"], d["home_id"])]
    d["away_city"] = [hc.get((s, a)) for s, a in zip(d["season"], d["away_id"])]
    neu = d["neutral"].astype(bool)
    vid = d["venue_id"]
    f1 = neu & (vid == d["home_venue_id"])
    f2 = neu & (vid == d["away_venue_id"]) & ~f1
    city = d["venue_address_city"].astype(str).str.lower()
    f3 = neu & ~f1 & ~f2 & ((city == d["home_city"].astype(str).str.lower()) | (city == d["away_city"].astype(str).str.lower()))
    f4 = ~neu & d["home_venue_id"].notna() & (vid != d["home_venue_id"]) & (city != d["home_city"].astype(str).str.lower())
    vn = d["venue_full_name"].astype(str).str.lower()
    name_in = [(str(loc.get(h, "")).lower() in v and len(str(loc.get(h, ""))) > 3) or (str(loc.get(a, "")).lower() in v and len(str(loc.get(a, ""))) > 3)
               for h, a, v in zip(d["home_id"], d["away_id"], vn)]
    f5 = neu & ~f1 & ~f2 & ~f3 & pd.Series(name_in, index=d.index)
    d["flag"] = np.select([f1, f2, f3, f4, f5], ["F1 neutral at home team's arena", "F2 neutral at away team's arena",
                                                  "F3 neutral in a team's home city", "F4 home game away from home arena/city",
                                                  "F5 neutral, team name in venue"], "")
    # residual from the side the flag favors: F1, F3-home, F4 -> home side as is; F2 -> away (the true host)
    host_away = (d["flag"].str.startswith("F2")) | (d["flag"].str.startswith("F3") & (city == d["away_city"].astype(str).str.lower()))
    d["flag_res"] = np.where(host_away, -d["res"], d["res"])
    rows = []
    for fl, g in d[d["flag"] != ""].groupby("flag"):
        g = g.dropna(subset=["res"])
        m, lo, hi = boot_mean(g["flag_res"], g["date"].astype(str))
        no, wo = plays(g[~g["swapped"]], "open_home_spread")
        nc, wc = plays(g[~g["swapped"]], "home_spread")
        rows.append({"flag": fl, "games": len(g), "mean residual, host side": round(m, 2), "interval": f"[{lo:.2f}, {hi:.2f}]",
                     "opener plays / win%": f"{no} / {wo}", "close plays / win%": f"{nc} / {wc}",
                     "seasons": ", ".join(f"{s}:{n}" for s, n in g["season"].value_counts().sort_index().items())})
    rest = d[(d["flag"] == "")].dropna(subset=["res"])
    m, lo, hi = boot_mean(rest["res"], rest["date"].astype(str))
    no, wo = plays(rest[~rest["swapped"]], "open_home_spread")
    nc, wc = plays(rest[~rest["swapped"]], "home_spread")
    rows.append({"flag": "unflagged", "games": len(rest), "mean residual, host side": round(m, 2), "interval": f"[{lo:.2f}, {hi:.2f}]",
                 "opener plays / win%": f"{no} / {wo}", "close plays / win%": f"{nc} / {wc}"})
    t = pd.DataFrame(rows)
    keep = ["game_id", "season", "date", "home_id", "away_id", "neutral", "venue_full_name", "venue_address_city",
            "venue_address_state", "home_city", "away_city", "flag", "res", "flag_res"]
    d.loc[d["flag"] != "", keep].sort_values(["season", "date"]).to_csv(os.path.join(OUT, "c4_flagged_games.csv"), index=False)
    t.to_csv(os.path.join(OUT, "c4_result.csv"), index=False)
    pd.set_option("display.width", 250, "display.max_colwidth", 120)
    print(t.to_string(index=False))


if __name__ == "__main__":
    main()
