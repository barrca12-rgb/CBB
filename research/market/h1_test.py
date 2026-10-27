"""First-half test, option A (pre-registered in LOG.md). Needs data/h1_a_lines.csv from h1_pull.py.

    python -m research.market.h1_test
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from cbb import evaluate
from research.market.h1_pilot import DATA
from research.market.s1_sample_report import OUT, ROOT
from research.market.s3_followups import payout, units

PBP = os.path.join(ROOT, "cbb", "cache", "pbp")
REF = ["draftkings", "fanduel", "betmgm"]
THR = {"spreads_h1": 1.5, "totals_h1": 2.0}
LADDER = {"spreads_h1": [1.0, 1.5, 2.0, 2.5], "totals_h1": [1.5, 2.0, 2.5, 3.0]}


def first_halves() -> pd.DataFrame:
    path = os.path.join(OUT, "h1_scores.pkl")
    if os.path.exists(path):
        return pd.read_pickle(path)
    parts = []
    for s in range(2014, 2027):
        p = pd.read_parquet(os.path.join(PBP, f"play_by_play_{s}.parquet"), columns=["game_id", "period_number", "home_score", "away_score"])
        h = p[p["period_number"] == 1].groupby("game_id")[["home_score", "away_score"]].last()
        parts.append(h.reset_index())
    out = pd.concat(parts).drop_duplicates("game_id").rename(columns={"home_score": "h1_home", "away_score": "h1_away"})
    out.to_pickle(path)
    return out


def model_h1(w: pd.DataFrame) -> pd.DataFrame:
    """Walk-forward OLS: first-half margin on final_margin, first-half total on final_total."""
    w = w.copy()
    w["h1_margin"], w["h1_total"] = w["h1_home"] - w["h1_away"], w["h1_home"] + w["h1_away"]
    w["m_h1_margin"], w["m_h1_total"] = np.nan, np.nan
    for s in range(2015, 2027):
        tr = w[(w["season"] < s) & (w["season"] >= 2014)].dropna(subset=["h1_margin", "final_margin"])
        te = w["season"] == s
        for y, x in (("h1_margin", "final_margin"), ("h1_total", "final_total")):
            b = np.polyfit(tr[x].to_numpy(float), tr[y].to_numpy(float), 1)
            w.loc[te, f"m_{y}"] = b[1] + b[0] * w.loc[te, x]
    return w


def cluster_coef(x, y, g):
    X = np.column_stack([np.ones(len(x)), x])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    bread = np.linalg.inv(X.T @ X)
    s = pd.DataFrame(X * e[:, None]).groupby(g).sum().to_numpy()
    se = np.sqrt(np.diag(bread @ (s.T @ s) @ bread))
    return b[1], se[1]


def boot(v, n=5000, seed=20261027):
    v = np.asarray(v, float)
    i = np.random.default_rng(seed).integers(0, len(v), (n, len(v)))
    return np.quantile(v[i].mean(axis=1), [.025, .975])


def main() -> None:
    games = pd.read_csv(os.path.join(DATA, "h1_a_games.csv"))
    lines = pd.read_csv(os.path.join(DATA, "h1_a_lines.csv"))
    w = pd.read_pickle(os.path.join(ROOT, "audit", "out", "wf_live_approx.pkl"))
    w = model_h1(w.merge(first_halves(), on="game_id", how="left"))
    w = w[~evaluate.swapped(w.assign(pred_margin=w["final_margin"]))]
    l = lines.merge(games[["game_id", "home_team", "flip", "date"]], on="game_id")
    l["side"] = np.where(l["market"] == "spreads_h1", np.where((l["outcome"] == l["home_team"]) != l["flip"].astype(bool), "home", "away"),
                         l["outcome"].str.lower())
    l = l.merge(w[["game_id", "season", "h1_margin", "h1_total", "m_h1_margin", "m_h1_total", "home_pts", "away_pts",
                   "final_margin", "home_spread"]], on="game_id").dropna(subset=["h1_margin"])
    # home-side spread number / over number per book; skip a book whose two sides do not mirror
    rows = []
    for (gid, bk, mk), x in l.groupby(["game_id", "book", "market"]):
        a = x.set_index("side")
        if mk == "spreads_h1":
            if not {"home", "away"} <= set(a.index) or abs(a.loc["home", "point"] + a.loc["away", "point"]) > 1e-9:
                continue
            line, model, res = a.loc["home", "point"], x["m_h1_margin"].iloc[0], x["h1_margin"].iloc[0]
            edge = model + line                         # > 0: home side
            sides = {"home": (a.loc["home", "point"], a.loc["home", "price"], res + line),
                     "away": (a.loc["away", "point"], a.loc["away", "price"], -(res + line))}
        else:
            if not {"over", "under"} <= set(a.index) or a.loc["over", "point"] != a.loc["under", "point"]:
                continue
            line, model, res = a.loc["over", "point"], x["m_h1_total"].iloc[0], x["h1_total"].iloc[0]
            edge = model - line                         # > 0: over
            sides = {"over": (line, a.loc["over", "price"], res - line), "under": (line, a.loc["under", "price"], line - res)}
        rows.append({"game_id": gid, "date": x["date"].iloc[0], "season": x["season"].iloc[0], "book": bk, "market": mk,
                     "line": line, "model": model, "res": res, "edge": edge,
                     **{f"{s}_{k}": v for s, (pt, pr, m) in sides.items() for k, v in (("pt", pt), ("price", pr), ("m", m))}})
    q = pd.DataFrame(rows)
    q.to_csv(os.path.join(OUT, "h1_quotes.csv.gz"), index=False)
    ref = q[q["book"].isin(REF)].assign(o=lambda d: d["book"].map({b: i for i, b in enumerate(REF)})).sort_values("o").drop_duplicates(["game_id", "market"])

    def side_of(r):
        if r["market"] == "spreads_h1":
            return "home" if r["edge"] > 0 else "away"
        return "over" if r["edge"] > 0 else "under"

    out, ladder = [], []
    for mk in ("spreads_h1", "totals_h1"):
        d = ref[ref["market"] == mk].copy()
        sign = 1 if mk == "totals_h1" else 1
        # scorecard 1: (result - line) on (model - line), oriented as home margin + line / total - line
        y = (d["res"] + d["line"]) if mk == "spreads_h1" else (d["res"] - d["line"])
        b, se = cluster_coef(d["edge"].to_numpy(float), y.to_numpy(float), d["date"].to_numpy())
        # full-game benchmark on the same games vs the ESPN close
        fg = w[w["game_id"].isin(d["game_id"])].dropna(subset=["home_spread"])
        if mk == "spreads_h1":
            bf, sef = cluster_coef((fg["final_margin"] + fg["home_spread"]).to_numpy(float),
                                   (fg["home_pts"] - fg["away_pts"] + fg["home_spread"]).to_numpy(float), fg["date"].astype(str).to_numpy())
        else:
            fg = w[w["game_id"].isin(d["game_id"])].dropna(subset=["total"])
            bf, sef = cluster_coef((fg["final_total"] - fg["total"]).to_numpy(float),
                                   (fg["home_pts"] + fg["away_pts"] - fg["total"]).to_numpy(float), fg["date"].astype(str).to_numpy())
        for t in LADDER[mk]:
            p = d[d["edge"].abs() >= t].copy()
            p["side"] = p.apply(side_of, axis=1)
            p["m"] = [r[f"{s}_m"] for s, (_, r) in zip(p["side"], p.iterrows())]
            p["price"] = [r[f"{s}_price"] for s, (_, r) in zip(p["side"], p.iterrows())]
            p["u"] = [units("W" if m > 0 else ("L" if m < 0 else "P"), pr) for m, pr in zip(p["m"], p["price"])]
            # best number then price across the three reference books, same side
            best_u = []
            for gid, s in zip(p["game_id"], p["side"]):
                c = q[(q["game_id"] == gid) & (q["market"] == mk) & q["book"].isin(REF)]
                v = c[f"{s}_pt"] * (-1 if s == "over" else 1)
                c = c.assign(v=v, pay=c[f"{s}_price"].map(payout)).sort_values(["v", "pay"]).iloc[-1]
                mm = c[f"{s}_m"]
                best_u.append(units("W" if mm > 0 else ("L" if mm < 0 else "P"), c[f"{s}_price"]))
            dec = p[p["m"] != 0]
            ci = boot(p["u"]) if len(p) > 1 else (np.nan, np.nan)
            rec = {"market": mk, "threshold": t, "plays": len(p), "win%": round(100 * (dec["m"] > 0).mean(), 2),
                   "ROI %": round(100 * p["u"].mean(), 2), "ROI 95% CI": f"[{100*ci[0]:.1f}, {100*ci[1]:.1f}]",
                   "ROI % best of 3": round(100 * np.mean(best_u), 2),
                   "win% 2025 / 2026": " / ".join(f"{100 * (dec.loc[dec['season'] == s, 'm'] > 0).mean():.1f} ({(dec['season'] == s).sum()})" for s in (2025, 2026))}
            ladder.append(rec)
            if t == THR[mk]:
                main_rec = rec
        out.append({"market": mk, "games": len(d), "beyond-line coef (se)": f"{b:.3f} ({se:.3f})",
                    "95% CI": f"[{b - 1.96 * se:.3f}, {b + 1.96 * se:.3f}]",
                    "full-game benchmark coef (se)": f"{bf:.3f} ({sef:.3f})",
                    "model MAE": round(float((d["model"] - d["res"]).abs().mean()), 3),
                    "line MAE": round(float((((-d["line"]) if mk == "spreads_h1" else d["line"]) - d["res"]).abs().mean()), 3),
                    "plays at pre-registered threshold": main_rec["plays"], "win%": main_rec["win%"], "ROI %": main_rec["ROI %"],
                    "ROI 95% CI": main_rec["ROI 95% CI"],
                    "verdict": "PASS" if (b - 1.96 * se > 0 and main_rec["ROI %"] > 0) else "KILL"})
    o, lad = pd.DataFrame(out), pd.DataFrame(ladder)
    o.to_csv(os.path.join(OUT, "h1_result.csv"), index=False)
    lad.to_csv(os.path.join(OUT, "h1_ladder.csv"), index=False)
    pd.set_option("display.width", 250)
    print(o.T.to_string())
    print(lad.to_string(index=False))


if __name__ == "__main__":
    main()
