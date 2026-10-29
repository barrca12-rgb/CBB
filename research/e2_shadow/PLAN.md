# E2 totals shadow, 2026-27 (declared Oct 29, 2026, before any 2026-27 game; approved by Chad)

A shadow strategy. It is never alerted, posted, staked or logged in `bets/bets.csv`, and it changes nothing in live
v1 (`MODEL_FREEZE.md`, Oct 29 entry).

## What E2 is
- **The model:** v1's stage-2 totals regression with two more inputs, neutral site and conference game
  (`research/quant`, E2).
- **The fit:** ridge λ = 1 on the production training frame, 2013-2026. The coefficients are the ones frozen on
  Oct 28 in `research/quant/out/e2_coefficients.json` (neutral −1.69, conference game −0.36). A fresh fit
  reproduces them exactly.
- **The forecast:** E2 total = the card's v1 total + (E2 stage-2 total − v1 stage-2 total), from the inputs the card
  saved for that run. In opening week the day's mean difference is removed, as v1's rule re-centres each day on
  KenPom.
- **Selection:** v1's totals rule exactly: best EV across books, edge 3+, EV ≥ +2%.

## Evidence so far (re-measured on seasons examined before; `research/power/out/rescore.txt`)
**Paired opener CLV vs v1:**

| Era | Total CLV | 95% interval |
|---|---|---|
| Development | +209 points | +66 to +346 |
| Holdout 2024-26 | +151 points | +36 to +271 |

**Units:** +45 and +34, with intervals including 0.

## Decision rule (the same as lineup v2's Amendment 3)
**The read (`research/power/sequential.py`, weekly):** paired closing-line value of E2's total picks minus v1's,
on games where they differ.
- **The close:** median across books of each book's last quote in the 60 minutes before the start, rebuilt from
  `lines/closing.csv`'s git history.

**Boundaries:**
- **Weekly interim looks:** |z| ≥ 3.29.
- **Mar 14, 2027 final:** |z| ≥ 1.96.

**What a crossing means:** a proposal only.
- **Approval path:** Chad's approval, a MODEL_FREEZE entry and a Discord note.
- **v1 continues** as a shadow.
- **Units:** reported alongside, never the decision.

## Relation to the Oct 28 prospective test (`research/quant/LOG.md`)
- **Approval:** approved by Chad on Oct 29, before any 2026-27 game.
- **Primary decision:** the paired-CLV sequential read above.
- **The Oct 28 rule becomes secondary:** neutral-site totals MAE, all-games MAE not worse, and opener win % not
  lower. It is still scored (`python -m research.quant.e2_shadow score`) and reported on Mar 14, but it doesn't
  decide.
- **Why:** this keeps E2 to one decision rule, as lineup v2's Amendment 3 does.

### Conditions added Oct 29, before any 2026-27 game (helper doc review; Chad approved Amendment 3 the same day)
1. **The close-record check, guarding against "looks like the close".** At a decision read, a crossing counts only
   if, on the differing games, the shadow's side is **no worse than v1's against the closing number**. The point
   estimate of the per-game (result − close) difference must be ≥ 0, with its date-clustered interval reported.
   - **Why:** a feature that only tracks what the market will price earns CLV without predicting the score; that is
     how recent form failed.
   - **Backtest (`research/power/out/close_record_check.csv`):** v2 +0.29 points (development) and 0.00 (holdout);
     E2 +0.71 and +0.82.
2. **Per-game statistic, with counts.** The rule is written on the mean CLV difference per differing game, not
   totals.
   - **Reported each read:** the number of differing games and the shadow-only share.
   - **Backtest per differing game:** v2 +0.39 / +0.31, E2 +0.27 / +0.27, all intervals above 0.
3. **Named sequential design.** Haybittle-Peto:
   - **Interim:** |z| ≥ 3.29 at most 18 weekly interim looks (Mondays, Nov 9, 2026 to Mar 8, 2027).
   - **Final:** |z| ≥ 1.96 at the Mar 14 read.
   - **Overall false-positive rate:** about 5%, at most 6.8% by the union bound.
   - **No other looks count**, and the boundaries do not change.
