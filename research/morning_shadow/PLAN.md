# Morning shadow: pre-registered plan

Written Nov 4, 2026, about 02:30 UTC, before the first morning window (Nov 4, 9:00 am ET). Approved by Chad on Nov 4
("Go ahead with 1-3 ... Predefine the morning shadow precisely"). Nothing in this plan changes after the first
shadow row is written. Any later change is a new, dated section below, and the original stays.

**What this is not.** The live strategy is unchanged. The complete-ratings rule (protocol v2.6 Appendix D) stays off.
The shadow logs no play, sends no alert, posts nothing and stakes nothing. Nothing is promoted automatically. A result
in favor of the morning strategy is a proposal to Chad, and he decides.

## 1. The two strategies

**C, current (live v1).** The main plays as logged in `bets/bets.csv` (bet type v1, not void). Each is logged at the
first card run where it qualifies, at that run's book, number and price. Stakes are the logged stakes, the
multiplier from `tracker.status`.

**M, morning.** One decision per game and market, on the game's own date D (ET). M is what the unchanged live card
decides at a fixed point in the morning:
- the verdict (BET or not);
- the side, book, number and price;
- the edge.

The opener rule, the bad-quote guards and the thresholds all apply exactly as live, because M reads the live card's
own output. Collection is in `cbb/morning_shadow.py`, and rows go to `bets/shadow_morning.csv`.

## 2. Morning decision, exactly

**Required source updates.** All four must hold on the deciding card run itself:

| Input | Required |
|---|---|
| Barttorvik | the card used the time-machine file dated D-1. A file dated X includes X's games (`audit/TIMING_AUDIT.md`, verified) |
| KenPom | FanMatch for D is published and used (it is built on KenPom's ratings through D-1) |
| Box scores | the hoopR schedule lists every Division I game of D-1 as final, postponed or cancelled, and every final one is in the games the stage-1 ratings are fit on |
| Injuries | this run's ESPN injury fetch succeeded |

**Window, per game (ET).**
- **Opens:** 09:00 on D.
- **Deadline:** 12:00 on D, or 30 minutes before the scheduled tip if that is earlier.

**Decision kinds:**
- **ready:** made at the first card run in the window with all four inputs ready.
- **fallback:** if no run is ready by the deadline, the first run at or after the deadline that is still before tip
  decides on what it has. The missing inputs are listed. This is the uncertain-timing case: the source worked, but
  had not updated.
- **no decision:** if no run decides before tip (tip before the window, or no card run), the row is logged with that
  reason. It counts as no bet.

**Hard failures** (a failed or empty source, not a late update) are logged as no bet, with the reason:
- no model number for the game;
- no named-book quote with a price.

**Quotes.** M uses only the decision run's own pull: the seven named books, with recorded prices. Each M play's row
carries the quote's source update time and age from that pull (`quotelog.generating_quote`, the same record C's plays
get in `bets/signal_log.csv`).

**Logged for every game and market**, whether bet or no bet:
- decision time and kind;
- each readiness flag, and what is missing;
- the Barttorvik file, the KenPom source and the last final box-score date;
- the card's verdict and gate;
- side, book, number, price, edge, EV, model and stake;
- quote source and times;
- code version and run id.

## 3. Same universe, same staking

**Universe.** Every game and market with a shadow row, for games dated 2026-11-04 through 2027-03-14 (the v1 forward
window), excluding games with no final score (postponed, cancelled). C's plays are matched to it by game and market.
C plays outside the universe (a day the shadow did not run) are counted and listed, never silently dropped.

**Cells.** Each game and market falls in exactly one:
- both, same side;
- both, opposite sides;
- C only (the early-only bets, mostly);
- M only;
- neither.

**Staking:**
- **Primary:** flat, 1 unit risked per play at its recorded price. This is the protocol's own evaluation rule (section 1:
  "This protocol evaluates flat 1 unit per signal").
- **Secondary:** as staked, with C's logged stake and M's `tracker.status` multiplier at its decision run. That is the
  same rule `tracker.log` uses.

**Exposure.** One play per game and market per strategy, as live.

**Reported per strategy and for M minus C:**
- bets;
- amount risked;
- profit;
- ROI;
- record;
- mean CLV;
- the share of plays that beat the close.

**CLV** is the primary close (protocol v2.5 section 7, `cbb/clv_primary.primary`), the same function for both
strategies, measured in points from each play's side.

**Uncertainty.** A bootstrap over game dates: 2,000 draws, seed 7. Every play on a game, and every game on a date,
moves together, so same-game and same-date dependence is kept. Intervals are 95% percentile intervals.

## 4. Reads and the decision

**Jan 15, 2027: descriptive only.** The tables in section 3 on games through Jan 14. No decision, no stopping and no
change.

**Mar 14, 2027: the fixed decision review.** Run once every game through Mar 14 is graded (about Mar 16).

**Primary comparison (declared now).** Δ = M's flat profit minus C's flat profit over the universe, with its 95%
interval.

| Outcome | Condition | What happens |
|---|---|---|
| **M better** | Δ's interval is above 0, and the interval for M's mean CLV minus C's does not lie wholly below 0 | A proposal to Chad to switch to M. Nothing switches automatically |
| **C better** | Δ's interval is below 0 | The current strategy stays, with this as the record |
| **Inconclusive** | anything else, including fewer than 200 game-markets where the strategies disagree (C only, M only or opposite sides) | Nothing changes |

The weekly read of early plays (`audit/ratings_shift.py`) continues as description only. The earlier
"after 40 closes" trigger is withdrawn.

**Expected power (stated so a null is read correctly).** A flat play's profit has a standard deviation near 1 unit.
With about 400 disagreeing game-markets by Mar 14, Δ's interval is roughly ±55 units wide. Only a large difference
would clear it. An inconclusive result is the likely outcome and is not evidence that the two are equal.

## 5. Files

| File | What |
|---|---|
| `cbb/morning_shadow.py` | collection, run inside the 10-minute card run |
| `bets/shadow_morning.csv` | one row per game and market |
| `research/morning_shadow/compare.py` | the section 3 tables: `--through 2027-01-14` for Jan 15, `--through 2027-03-14` for the decision |
| `audit/test_morning_shadow.py` | window, readiness, fallback, no-decision, hard-failure and cell tests |
