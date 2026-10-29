# Sequential CLV read: lineup v2 vs v1 spreads, 2026-27 (pre-registered Oct 29, 2026, before any 2026-27 game)

Decision read for the lineup v2 and E2 shadows (Amendment 3 approved Oct 29). Nothing live changes by itself: a
crossing is a proposal that needs Chad's approval, a MODEL_FREEZE entry and a Discord note. Chad approved setting up weekly sequential CLV reads on Oct 29.

## Why
**Noise:** paired closing-line value separates v2 from v1 far faster than units.
- **Per-bet noise at openers (`out/rescore.txt`):** units 0.94; result vs line 11.4 points; CLV 2.0 points.
- **Evidence strength on the same 1,599 bets:** t = 4.3 for units and t = 26.6 for CLV.

**v2's track record on paired CLV:**

| Era | Total CLV vs v1 | 95% interval |
|---|---|---|
| Development | +255 points | +170 to +346 |
| Holdout | +122 points | +55 to +191 |

## Statistic (`sequential.py`, weekly)
- **Games:** 2026-27 games where the two strategies' spread picks differ, meaning one bets and the other doesn't, or
  they take opposite sides.
- **Pick sources:** v1's from `bets/bets.csv`, v2's from `bets/shadow_v2/signals.csv`, first logged pick per game.
- **Per game:** CLV(v2 pick) − CLV(v1 pick), with 0 for no pick.
  - **CLV:** the entry line minus the close, on the pick's side.
  - **The close:** for both strategies, the median across books of each book's last quote in the 60 minutes
    before the start. Quotes come from every committed pull of `lines/closing.csv`, rebuilt from git history
    (`closing_history.py`). The working-tree file holds only the latest pull.
  - **No close:** a game where any pick lacks a close is excluded and counted.
- **z:** cumulative mean difference ÷ its date-clustered SE.

## Boundaries
- **Weekly interim looks:** |z| ≥ 3.29 (Haybittle-Peto; keeps the overall error near 5%).
- **Final read, Mar 14, 2027:** |z| ≥ 1.96.
- **No futility stop:** the read continues to the final.

## Expected power (from the holdout: +0.307 points per differing game, SD 1.654)

| Differing games | Expected z |
|---|---|
| 50 | 1.3 |
| 100 | 1.9 |
| 150 | 2.3 |
| 200 | 2.6 |
| 250 | 2.9 |

- **Volume:** about 200 differing games a season (398 over the two holdout seasons).
- **Interim boundary:** reaching 3.29 needs about 314, so an early stop in-season is unlikely unless the true effect
  is larger than in the backtest.
- **Final read:** at 1.96, v2's backtest effect would be detected with about 80% power by about 230 games, near
  season's end.
- **Speed:** this is still years faster than units. On units the same difference would need several seasons.

## Amendment 3 to `research/v2_lineup/PLAN.md`: APPROVED by Chad on Oct 29, before any 2026-27 game (now active; text in that plan)
- **What changes:** this paired-CLV sequential read replaces v2's endpoint 1 (subset residual difference) as the
  primary decision endpoint.
  - **Interim proposal:** v2 may be proposed when |z| ≥ 3.29 at any weekly look.
  - **Final read:** Mar 14 at 1.96.
  - **Endpoint 1:** becomes a secondary, reported check.
- **Rationale:** on the backtest, endpoint 1 needs several seasons of games to separate the strategies; paired CLV
  needs about one.
- **Timing:** must be approved before the first 2026-27 game. After that, switching endpoints would be choosing
  among endpoints after seeing data.

## Known data issue (fixed in research code only)
- **The issue:** `research/v2_lineup/evaluate.py` reads closes from the working-tree `lines/closing.csv`, which
  holds only the latest pull. At Jan 15 it would find no close-time quotes for most plays.
- **The fix:** `research/power/closing_history.py` provides every committed pull. v2's endpoint 2 should read
  from it, a plumbing fix that changes no rule.

## Schedule
- **Weekly:** Mondays from Nov 9, 2026 through Mar 15, 2027, plus the Mar 14 final.
- **Each read:** commits `out/sequential_<date>.txt` and reports z and the boundary to Chad.

## E2 totals (added Oct 29 with the E2 shadow, before any 2026-27 game)
- **Same read, applied to totals:** E2's total picks (`bets/shadow_e2/signals.csv`) against v1's total plays
  (`bets/bets.csv`). Same close rule (median total), boundaries and approval path.
- **The plan:** `research/e2_shadow/PLAN.md`.

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
