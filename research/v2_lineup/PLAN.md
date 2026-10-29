# Lineup v2 shadow test: plan (declared Oct 27, 2026, before any live data)

Chad asked for this after the originator research (`research/originator/RESULTS.md`, review follow-up 3). v2 is a
shadow strategy. It is never alerted, posted, staked or logged in `bets/bets.csv`, and it changes nothing in live v1
(the frozen files in `MODEL_FREEZE.md` stay untouched).

## What v2 is

**v2 spread margin** = the frozen v1 margin + beta x the lineup adjustment.

**Lineup adjustment**, per team, from games before this one only, as in `research/originator/b_rotation.py`:
- **Expected minutes tonight:** the last-5-game weighted average, shrunk toward the embedded minutes; 0 if the
  player sat out the team's previous game.
- **Embedded minutes:** the rotation the team rating was built on (weights 0.5^(days/120)).
- **Player value:** offensive and defensive box-score value relative to the team, shrunk.
- **The adjustment:** the sum of (expected - embedded minutes)/200 x value x possessions/100.
- **Game margin adjustment:** home minus away.

**beta:** fit by OLS of the frozen model's margin residual on the adjustment.
- **Backtest:** walk-forward, fit on seasons before each test season.
- **Live shadow:** fixed at the 2014-2026 fit and recorded here before Nov 1.

**Totals:** unchanged. The total adjustment failed (out-of-sample R2 below 0). v2's totals are v1's.

**Selection:** v1's rule exactly, applied to the v2 margin:
- **Thresholds:** spread edge 2.5+ and EV >= +2% at the book's price.
- **Books and ranking:** best EV across the 7 books, ties to DraftKings, using the same win-chance table.

## Backtest before the shadow starts (`backtest.py`)

- **Plays:** v1 vs v2 spread plays at the opener. Openers oriented by moneyline, swapped records excluded.
- **Seasons:** development 2014-17 and 2024; holdout 2025-26.
- **Report:** plays, win %, ROI at -110, opener CLV. Picks only v2 makes, only v1 makes, and both.
- **No kill rule:** this is a description for Chad, not a gate (the gate was the review's subset rule, already
  passed).

## The shadow

- **Code:** `cbb/lineup.py` (adjustment for the next game) and `cbb/shadow_v2.py` (selection and log).
  - `cbb/lineup.py` reproduces the research adjustments exactly: max difference 4e-16 over 11,152 team-games in
    2025; the next-game state equals the game-day row for all 290 teams playing Feb 15, 2025.
  - **beta = 0.4022**, frozen in `cbb/lineup.py`.
- **Trigger:** `.github/workflows/shadow_v2.yml`, which runs when each "Update CBB card" run completes. That means
  no new schedule and no change to `update.yml`.
- **Inputs, read from what the card run committed:** the card CSVs `reports/cbb_<date>.csv` (v1 margins), the
  current book lines `lines/closing.csv`, and this season's player box scores.
- **Log:** `bets/shadow_v2/signals.csv`, one row per v2 spread signal (first qualifying run, once per `bet_id`),
  with v1 margin, adjustment, v2 margin, book, line, price, edge, EV and logged time. Plus
  `bets/shadow_v2/runs.csv`, one row per shadow run (games, adjustments computed, signals, errors).

## Evaluation (Jan 15 descriptive; season-end read for the decision)

- **Signal sets, same games:**
  - v2-only signals;
  - v1-only signals;
  - shared signals.
- **For each set:**
  - line value against the close from `lines/closing.csv` (books observed within 60 minutes of the start, median
    across books), the same source for v1 and v2. The forward test's strict close comes from the quote logger,
    which watches v1's games only (it is frozen), so it cannot grade v2-only signals;
  - ROI at recorded prices;
  - date-clustered intervals.

  `research/v2_lineup/evaluate.py` implements this, written before any live data.
- **The question:** do v2-only signals beat v1-only signals on line value and ROI? Shared signals are the same
  bet.
- **Decision:** no automatic switch. A v2 for live use needs Chad's approval at a checkpoint, per forward-test
  protocol section 8. v1 then continues as a shadow.

## Amendment, Oct 27, 2026: the helpers' endpoints

Added before any v2 signal with a non-zero adjustment (the first live runs had no 2026-27 box scores, so every
adjustment was 0 and v2 = v1).

**Subset:** games where either team's lineup adjustment is 2+ points in absolute value. It is flagged per game in
`bets/shadow_v2/games_latest.csv`, which logs every card game's latest pregame v1 margin, adjustments and v2
margin.

**Primary endpoints, on the subset:**
1. **Residual difference:** mean |result - v1 margin| minus mean |result - v2 margin|, with the date-clustered
   interval.
2. **Opener CLV:** on spread plays the two versions disagree on (v2-only and v1-only), separately. Openers come
   from `lines/openers.csv` (first seen per book, median), the close from `lines/closing.csv`.

The all-games comparison in the evaluation section above stays as the secondary read.

**Reads:** Jan 15 descriptive; March 14 the decision read (moved from March 16 on Oct 28, Chad: before the NCAA tournament). If v2 clears it, it can replace v1 for 2027-28 by the
normal approval path (protocol section 8); if not, it is closed with the others.

**Form of the adjustment:** v2 adds beta x adjustment to v1's final margin, with beta fit walk-forward on the
frozen model's residual in the backtest. That is equivalent to adding the adjustment as one more stage-2 input
while holding the other stage-2 weights fixed. Live beta is frozen at 0.4022.

**Discord and the site:** Chad decided on Oct 27 that v2 is tracked behind the scenes only.
- **Not posted:** v2 signals never go to Discord. The posting code exists in `cbb/shadow_v2.py` but stays off
  (`SHADOW_V2_DISCORD` is not set).
- **Not on the site:** v2 is never part of the site's record or play tracking, which read `bets/bets.csv` only.
- **Where it lives:** `bets/shadow_v2/`, for the Jan 15 and March 14 evaluations.

## Amendment 2, Oct 29, 2026: a Jan 15 decision point (Chad: "if something is working we need to know before the end of the season")

Added before any non-zero v2 adjustment existed. Every shadow run so far shows "no adjustments: HTTP 404" (no 2026-27
box scores), so no v2 result has been seen.

- **Jan 15 read (games through Jan 10): now a decision point, not only descriptive.**
  - **Endpoint 1 (subset residual difference):** v2 may be proposed for the rest of the season only if the
    date-clustered **99.5%** interval is above 0.
  - **Endpoint 2 (opener CLV):** the v2-only plays' opener CLV must also be above the v1-only plays' (point
    estimate) in the subset.
  - **Why 99.5%:** this is a two-look sequential design, so the final read keeps an overall error near 5%.
- **March 14 read:** unchanged, the 95% interval on endpoint 1 with endpoint 2 as stated.
- **A Jan 15 pass is a proposal, not a switch.**
  - **Approval path:** Chad's approval, a MODEL_FREEZE entry and a Discord note, as in protocol section 8.
  - **v1 continues** as a shadow, so the forward test of v1 stays clean through March 14.
- **Sample warning:** about 280 subset games a season, so by Jan 10 perhaps 100-150. Only a large effect can pass on
  Jan 15. A non-pass there is not evidence against v2; it goes to March 14.
