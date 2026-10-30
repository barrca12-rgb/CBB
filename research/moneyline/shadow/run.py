"""Opening-moneyline shadow on our spread plays (PLAN.md). Research log: reads bets/bets.csv and the card's price log
(lines/ml/), writes research/moneyline/shadow/plays.csv and out/summary.txt. Adds nothing to the card run.

    python -m research.moneyline.shadow.run [--through YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import glob
import os

import numpy as np
import pandas as pd
from scipy.stats import norm

from cbb import odds, tracker
from research.moneyline.devig_methods import implied, shin

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..", "..", "..")
ML = os.path.join(ROOT, "lines", "ml")
REPORTS = os.path.join(ROOT, "reports")
PLAYS = os.path.join(HERE, "plays.csv")
OUT = os.path.join(HERE, "out")
BOOKS = list(odds.BOOKS.values())                       # the seven frozen books
CONV_C, CONV_SIGMA, MARGIN_SIGMA = 0.092, 10.422, 10.322   # frozen: test 1 conversion, test 3 margin distribution


def payout(ml):
    ml = np.asarray(ml, float)
    return np.where(ml > 0, ml / 100, 100 / -ml)


def price_log() -> pd.DataFrame:
    fs = [f for f in sorted(glob.glob(os.path.join(ML, "*.csv"))) if not f.endswith("latest.csv")]
    if not fs:
        return pd.DataFrame()
    p = pd.concat([pd.read_csv(f) for f in fs], ignore_index=True)
    if "status" not in p:
        p["status"] = "ok"
    p["status"] = p["status"].fillna("ok")
    p["observed_at"] = pd.to_datetime(p["observed_at"], utc=True)
    return p


def _ours(rows: pd.DataFrame, home_id: int, side: str) -> pd.DataFrame:
    """Each row's price on our side and the other side, whichever way the feed lists the teams."""
    flip = rows["home_id"] != home_id
    our_home = side == "home"
    r = rows.assign(ours=np.where(flip ^ (not our_home), rows["away_ml"], rows["home_ml"]))
    return r.assign(theirs=np.where(flip ^ (not our_home), rows["home_ml"], rows["away_ml"]))


def _fair(r: pd.DataFrame) -> np.ndarray:
    """Shin no-vig probability on our side for each row with both prices."""
    h, _ = shin(implied(r["ours"]), implied(r["theirs"]))
    return h


def build(through: str | None = None) -> pd.DataFrame:
    b = tracker.load("all")
    b = b[(b["market"] == "spread") & (b["status"] != "void")]
    if through:
        b = b[b["date"] <= through]
    log = price_log()
    start = log["observed_at"].min() if len(log) else None
    rows = []
    for _, bet in b.iterrows():
        h, a, side = int(bet["home_id"]), int(bet["away_id"]), str(bet["side"]).lower()
        at = pd.Timestamp(bet["logged_at"])
        rec = {"bet_id": bet["bet_id"], "type": bet["bet_type"] if isinstance(bet["bet_type"], str) and bet["bet_type"] else "v1",
               "date": bet["date"], "game_id": bet["game_id"], "pick": bet["pick"], "side": side, "spread_line": bet["line"],
               "spread_book": bet["book"], "logged_at": bet["logged_at"], "status": bet["status"],
               "spread_units": float(bet["profit"]) / float(bet["stake"]) if pd.notna(bet["profit"]) and float(bet["stake"]) else np.nan}
        line = float(bet["line"])
        g = log[((log["home_id"] == h) & (log["away_id"] == a)) | ((log["home_id"] == a) & (log["away_id"] == h))] if len(log) else log
        # model win probability for our side (both versions, labeled)
        rep = os.path.join(REPORTS, f"cbb_{bet['date']}.csv")
        neutral = False
        if os.path.exists(rep):
            c = pd.read_csv(rep, usecols=lambda k: k in ("game_id", "neutral"))
            n = c.loc[c["game_id"].astype(str) == str(bet["game_id"]), "neutral"]
            neutral = bool(n.iloc[0]) if len(n) else False
        m = float(bet["model"])
        p_conv = norm.cdf((m + CONV_C * (0 if neutral else 1)) / CONV_SIGMA)
        p_marg = norm.cdf(m / MARGIN_SIGMA)
        rec.update(p_conversion=p_conv if side == "home" else 1 - p_conv, p_margin=p_marg if side == "home" else 1 - p_marg)
        if start is None or at < start:
            rec.update(ml_state="before the price log")
            rows.append(rec)
            continue
        now = _ours(g[g["observed_at"] <= at].sort_values("observed_at").drop_duplicates("book", keep="last"), h, side)
        okb = now[(now["status"] == "ok") & now["book"].isin(BOOKS)]
        pb = okb[okb["book"] == bet["book"]]
        rec["ml_state"] = "quoted at the play's book" if len(pb) else "no quote at the play's book"
        if len(pb):
            r = pb.iloc[0]
            rec.update(ml_book_price=r["ours"], ml_book_at=r["observed_at"].isoformat(), ml_book_fair=float(_fair(pb)[0]))
        if len(okb):
            r = okb.assign(pay=payout(okb["ours"])).sort_values("pay", ascending=False).iloc[0]
            rec.update(ml_best_price=r["ours"], ml_best_book=r["book"], ml_best_at=r["observed_at"].isoformat(),
                       ml_best_fair=float(_fair(okb[okb["book"] == r["book"]])[0]))
        dog = line > 0 or (line == 0 and rec.get("ml_best_price", rec.get("ml_book_price", 0)) > 0)
        rec["dog_fav"] = "underdog" if dog else "favorite"
        # close: each book's last ok pair before tip, Shin no-vig on our side, median across books
        tip = pd.to_datetime(g["start"], utc=True, errors="coerce").dropna()
        if len(tip):
            pre = g[g["observed_at"] < tip.iloc[0]].sort_values("observed_at").drop_duplicates("book", keep="last")
            pre = _ours(pre[(pre["status"] == "ok") & pre["book"].isin(BOOKS)], h, side)
            if len(pre) and bet["status"] == "settled":
                close = float(np.median(_fair(pre)))
                rec["close_fair"] = close
                for k in ("book", "best"):
                    if f"ml_{k}_fair" in rec:
                        rec[f"ml_{k}_clv_pp"] = round(100 * (close - rec[f"ml_{k}_fair"]), 2)
        if bet["status"] == "settled" and pd.notna(bet["home_score"]):
            margin = (float(bet["home_score"]) - float(bet["away_score"])) * (1 if side == "home" else -1)
            won = margin > 0
            rec["ml_won"] = won
            for k in ("book", "best"):
                if f"ml_{k}_price" in rec:
                    rec[f"ml_{k}_units"] = float(payout(rec[f"ml_{k}_price"])) if won else -1.0
        rows.append(rec)
    return pd.DataFrame(rows)


def summary(p: pd.DataFrame) -> str:
    L = [f"Spread plays (v1 and band B, not void): {len(p)}"]
    if not len(p):
        return "\n".join(L)
    live = p[p["ml_state"] != "before the price log"]
    L.append(f"  logged before the price log started (kept out of the reads): {int((p['ml_state'] == 'before the price log').sum())}")
    if len(live):
        q = (live["ml_state"] == "quoted at the play's book").mean()
        L.append(f"  moneyline on our side quoted at the play's book when logged: {100 * q:.0f}% of {len(live)}")
    g = live[live.get("ml_won").notna()] if "ml_won" in live else live.iloc[0:0]
    rows = []
    for lab, x in [("all", g)] + (list(g.groupby("dog_fav")) if len(g) else []):
        r = {"group": lab, "plays": len(x)}
        for k in ("book", "best"):
            u = x.get(f"ml_{k}_units", pd.Series(dtype=float)).dropna()
            r[f"ML units ({k})"] = round(float(u.sum()), 2)
            r[f"ML ROI % ({k})"] = round(100 * float(u.mean()), 1) if len(u) else None
            c = x.get(f"ml_{k}_clv_pp", pd.Series(dtype=float)).dropna()
            r[f"ML CLV pp ({k})"] = round(float(c.mean()), 2) if len(c) else None
        s = x["spread_units"].dropna()
        r["spread units"] = round(float(s.sum()), 2)
        r["spread ROI %"] = round(100 * float(s.mean()), 1) if len(s) else None
        rows.append(r)
    L.append("\nGraded plays recorded after the price log started:")
    L.append(pd.DataFrame(rows).to_string(index=False) if rows and rows[0]["plays"] else "  none graded yet")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--through")
    a = ap.parse_args()
    p = build(a.through)
    p.to_csv(PLAYS, index=False)
    os.makedirs(OUT, exist_ok=True)
    s = summary(p)
    open(os.path.join(OUT, "summary.txt"), "w").write(s + "\n")
    print(s)


if __name__ == "__main__":
    main()
