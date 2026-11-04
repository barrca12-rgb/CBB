"""Do referee-crew tendencies hold up live? (Chad, Nov 4: "we need to track that to ensure the trend holds for
crews.") Read-only: nothing here changes the model or a play.

The model shifts a game's total by 0.834 x ref_fouls + 0.800 x ref_pts (data/projection.json), where ref_fouls is
the crew's fouls per game above average and ref_pts its points above our model's projection, each official shrunk
toward 0 and averaged over the crew (cbb/context.py). Crews post on ESPN about an hour before tip, so only games
whose crew was in the card before tip count. For every graded 2026-27 game with a posted crew:

  fouls     did low-foul crews call fewer fouls? (actual fouls minus this season's average, against ref_fouls)
  points    did the crew shift show up in the score? (actual total minus the model's total without the crew shift,
            against the shift; a slope near 1 means the adjustment is the right size, near 0 means it is noise)
  accuracy  totals average miss with and without the crew shift, same games
  plays     main total plays logged with a crew posted, and the ones the crew made: without the crew shift the edge
            was under the 3-point bar, or the play had been stopped by the opener rule until the crew posted
            (Butler-FDU Under 156.5 on Nov 4 is the first)
  backtest  every graded 2026-27 game with its actual crew (hoopR officials, after the fact) and the crew table the
            model saved before the season (data/referees.csv): the same slope and accuracy on all games, so the
            check does not wait for crews to post before tip. Model totals are the last card version before tip.

    python -m audit.crew_check        # -> audit/out/crew_check.txt
"""
from __future__ import annotations

import glob
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(os.path.dirname(__file__), "out")
THR = 3.0


def weights() -> tuple[float, float]:
    t = json.load(open(os.path.join(ROOT, "data", "projection.json")))["total"]
    return float(t["ref_fouls"]), float(t["ref_pts"])


def games(through: str | None = None) -> pd.DataFrame:
    """One row per 2026-27 game with a crew on its card: crew shift, model total, final score and fouls."""
    from cbb import data
    from research.morning_shadow.compare import finals
    wf, wp = weights()
    today = pd.Timestamp.now(tz="America/New_York").strftime("%Y-%m-%d")
    rows = []
    for p in sorted(glob.glob(os.path.join(ROOT, "reports", "cbb_2026-1*.csv")) + glob.glob(os.path.join(ROOT, "reports", "cbb_2027-*.csv"))):
        day = os.path.basename(p)[4:14]
        if day >= today or (through and day > through):
            continue
        c = pd.read_csv(p)
        if "crew" not in c:
            continue
        c = c[c["crew"].notna() & (c["crew"].astype(str).str.len() > 0)]
        fp = os.path.join(ROOT, "reports", f"features_{day}.csv")
        if not len(c) or not os.path.exists(fp):
            continue
        f = pd.read_csv(fp, usecols=lambda k: k in ("game_id", "ref_fouls", "ref_pts")).set_index("game_id")
        c = c.join(f, on="game_id")
        c["date"] = day
        rows.append(c[["date", "game_id", "home", "away", "home_id", "crew", "model_total", "ref_fouls", "ref_pts"]])
    if not rows:
        return pd.DataFrame()
    g = pd.concat(rows, ignore_index=True).dropna(subset=["ref_fouls", "ref_pts"])
    g["shift"] = wf * g["ref_fouls"] + wp * g["ref_pts"]
    g["model_no_crew"] = g["model_total"] - g["shift"]
    fin = finals(g["date"])
    g["actual"] = [sum(fin[int(i)][1:]) if int(i) in fin else np.nan for i in g["game_id"]]
    try:
        box = data.fetch("team_box", 2027, refresh=True)
        fouls = box.groupby("game_id")["fouls"].sum()
        g["fouls"] = g["game_id"].astype(int).map(fouls)
        g["foul_dev"] = g["fouls"] - fouls.mean()
    except Exception:
        g["fouls"] = g["foul_dev"] = np.nan
    return g.dropna(subset=["actual"])


def _slope(x, y) -> tuple[float, float]:
    """Least-squares slope of y on x and a rough standard error."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3 or np.var(x) == 0:
        return np.nan, np.nan
    b = np.cov(x, y, bias=True)[0, 1] / np.var(x)
    r = y - y.mean() - b * (x - x.mean())
    se = np.sqrt((r ** 2).sum() / (len(x) - 2) / ((x - x.mean()) ** 2).sum())
    return float(b), float(se)


def _shift_for(day: str, gid) -> float:
    wf, wp = weights()
    fp = os.path.join(ROOT, "reports", f"features_{day}.csv")
    if not os.path.exists(fp):
        return np.nan
    f = pd.read_csv(fp, usecols=lambda k: k in ("game_id", "ref_fouls", "ref_pts")).set_index("game_id")
    return float(wf * f.loc[gid, "ref_fouls"] + wp * f.loc[gid, "ref_pts"]) if gid in f.index else np.nan


def plays(g: pd.DataFrame) -> pd.DataFrame:
    """Main total plays logged after the crew posted, with the edge they would have had without the crew shift, and
    whether the opener rule had stopped them before the crew posted."""
    from cbb import tracker
    b = tracker.load("v1")
    b = b[(b["market"] == "total") & (b["status"] != "void")]
    s = pd.read_csv(os.path.join(ROOT, "bets", "signal_log.csv"), usecols=lambda k: k in ("bet_id", "crew_posted"))
    b = b.merge(s, on="bet_id", how="left")
    b = b[b["crew_posted"].astype(str).str.lower() == "true"].copy()
    if not len(b):
        return b
    b["shift"] = [_shift_for(d, gid) for d, gid in zip(b["date"], b["game_id"])]
    sign = np.where(b["side"] == "over", 1.0, -1.0)
    b["edge_without_crew"] = (b["edge"] - sign * b["shift"]).round(2)
    lm = os.path.join(ROOT, "research", "linemove", "signals.csv")
    gated = set()
    if os.path.exists(lm):
        x = pd.read_csv(lm, usecols=lambda k: k in ("game_id", "market", "pick"))
        x = x[x["market"] == "total"]
        gated = set(zip(x["game_id"].astype(int), x["pick"].astype(str).str.split().str[0]))
    b["opener_rule_before"] = [(int(gid), str(pk).split()[0]) in gated for gid, pk in zip(b["game_id"], b["pick"])]
    b["crew_made_it"] = (b["edge_without_crew"] < THR) | b["opener_rule_before"]
    return b[["date", "pick", "home", "away", "edge", "edge_without_crew", "opener_rule_before", "crew_made_it", "status",
              "result", "profit"]]


def season_backtest() -> pd.DataFrame:
    """Every graded 2026-27 game with its actual crew: pre-tip model total (crew shift backed out), the shift from
    the pre-season crew table, final score and fouls."""
    import io
    import subprocess
    from cbb import data
    from research.morning_shadow.compare import finals
    wf, wp = weights()
    tab = pd.read_csv(os.path.join(ROOT, "data", "referees.csv")).set_index("official")
    off = data.fetch("officials", 2027, refresh=True)
    crew = off.groupby("game_id")["official_display_name"].apply(list)
    box = data.fetch("team_box", 2027)
    fouls = box.groupby("game_id")["fouls"].sum()
    today = pd.Timestamp.now(tz="America/New_York").strftime("%Y-%m-%d")
    rows = []
    for p in sorted(glob.glob(os.path.join(ROOT, "reports", "features_2026-1*.csv")) + glob.glob(os.path.join(ROOT, "reports", "features_2027-*.csv"))):
        day = os.path.basename(p)[9:19]
        if day >= today:
            continue
        rel = f"reports/features_{day}.csv"
        log = [l.split() for l in subprocess.run(["git", "log", "--format=%H %cI", "--", rel], capture_output=True, text=True,
                                                 cwd=ROOT).stdout.split("\n") if l]
        vers = sorted((pd.Timestamp(t), h) for h, t in log)
        card = pd.read_csv(os.path.join(ROOT, "reports", f"cbb_{day}.csv"), usecols=["game_id", "start"])
        fin = finals([day])
        cache = {}
        for _, g in card.iterrows():
            gid = int(g["game_id"])
            if gid not in fin or gid not in crew.index:
                continue
            pre = [v for v in vers if v[0] < pd.Timestamp(g["start"])]
            if not pre:
                continue
            h = pre[-1][1]
            if h not in cache:
                cs = subprocess.run(["git", "show", f"{h}:reports/cbb_{day}.csv"], capture_output=True, text=True, cwd=ROOT).stdout
                fs = subprocess.run(["git", "show", f"{h}:{rel}"], capture_output=True, text=True, cwd=ROOT).stdout
                cache[h] = (pd.read_csv(io.StringIO(cs)).set_index("game_id"), pd.read_csv(io.StringIO(fs)).set_index("game_id"))
            c, f = cache[h]
            if gid not in c.index or gid not in f.index:
                continue
            card_shift = wf * float(f.loc[gid, "ref_fouls"] or 0) + wp * float(f.loc[gid, "ref_pts"] or 0)
            names = crew[gid]
            rf = np.mean([tab["ref_fouls"].get(n, 0.0) for n in names])
            rp = np.mean([tab["ref_pts"].get(n, 0.0) for n in names])
            rows.append({"date": day, "game_id": gid, "model_no_crew": float(c.loc[gid, "model_total"]) - card_shift,
                         "shift": wf * rf + wp * rp, "ref_fouls": rf, "actual": sum(fin[gid][1:]),
                         "fouls": fouls.get(gid, np.nan), "known_officials": sum(n in tab.index for n in names), "crew_size": len(names)})
    d = pd.DataFrame(rows)
    if len(d):
        d["foul_dev"] = d["fouls"] - d["fouls"].mean()
    return d


def _summary(g: pd.DataFrame, L: list, label: str) -> None:
    resid = g["actual"] - g["model_no_crew"]
    b, se = _slope(g["shift"], resid)
    L.append(f"  {label}: {len(g)} games; crew shift {g['shift'].min():+.1f} to {g['shift'].max():+.1f} (mean {g['shift'].mean():+.2f})")
    L.append(f"    points: actual minus model-without-crew on the crew shift, slope {b:.2f} (se {se:.2f}); 1 = right size, 0 = noise")
    for lab, x in (("low-scoring crews (shift <= -1)", g[g["shift"] <= -1]), ("high-scoring crews (shift >= +1)", g[g["shift"] >= 1])):
        if len(x):
            L.append(f"    {lab}: {len(x)} games, predicted {x['shift'].mean():+.2f}, actual vs model-without-crew "
                     f"{(x['actual'] - x['model_no_crew']).mean():+.2f}")
    with_c = g["model_no_crew"] + g["shift"]
    L.append(f"    accuracy: totals average miss {np.abs(g['actual'] - with_c).mean():.2f} with the crew shift, "
             f"{np.abs(g['actual'] - g['model_no_crew']).mean():.2f} without")
    if g["foul_dev"].notna().any():
        fb, fse = _slope(g["ref_fouls"], g["foul_dev"])
        L.append(f"    fouls: actual fouls vs average on the crew's foul tendency, slope {fb:.2f} (se {fse:.2f}); "
                 "the tendency is shrunk, so above 1 is expected if it is real")


def main() -> str:
    L = ["Referee crews, 2026-27 (audit/crew_check.py)"]
    g = games()
    if len(g):
        _summary(g, L, "live: crew on the card before tip")
    else:
        L.append("  live: no graded games with a crew posted before tip yet")
    try:
        bt = season_backtest()
        if len(bt):
            _summary(bt, L, "season backtest: actual crews, pre-season crew table, pre-tip model")
            L.append(f"    officials with history in the table: {bt['known_officials'].sum()} of {bt['crew_size'].sum()}")
            bt.to_csv(os.path.join(OUT, "crew_backtest_2027.csv"), index=False)
    except Exception as e:
        L.append(f"  season backtest failed ({e})")
    p = plays(g)
    if len(p):
        m = p[p["crew_made_it"]]
        dec = m[m["status"] == "settled"]
        L.append(f"  main total plays logged with a crew posted: {len(p)}; made by the crew: {len(m)}, graded {len(dec)}: "
                 f"{(dec['result'] == 'W').sum()}-{(dec['result'] == 'L').sum()}, {dec['profit'].sum():+.2f}u")
        L.append(p.to_string(index=False))
    L.append("  Read: description only until there are a few hundred crew games; the shift is a model input, decided "
             "only at a pre-registered review.")
    txt = "\n".join(L)
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "crew_check.txt"), "w").write(txt + "\n")
    return txt


if __name__ == "__main__":
    print(main())
