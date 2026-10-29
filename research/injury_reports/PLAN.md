# Injury reports: is the live injury adjustment calibrated and sized right? (pre-registered Oct 29, 2026, before any 2026-27 game)

Research only. Nothing live changes because of this file. Any change it supports is a proposal for Chad, and needs
his approval, a backtest where one is possible, a MODEL_FREEZE entry and a Discord note. It is not a new shadow.
The analysis is scored after the fact from files the card already writes.

**Timing goal:** an answer during the season, not after it.
- **Early look:** Dec 15.
- **Decision read:** Jan 15.
- **Fallback read:** Feb 15, only if the Jan 15 sample is too small.
- That leaves about two months of regular season and the tournaments if something works.

## What is already live (v1, `cbb/injuries.py`)
- Each player on ESPN's injury report who **played the team's last game** adds P(miss) × his share of team minutes
  to the team's missing minutes. Players who sat out the last game are already counted by `players.py`.
- That feeds the projection's missing-minutes weight (about −6.3 points of margin per 1.0 of minutes missing).
- **P(miss) by status is a guess:** out 1.0, doubtful 0.75, questionable 0.4, day-to-day 0.35, probable 0.1.
  There was no history to fit it.
- **The weight was learned from a different signal:** "missed the last game", which includes players who come
  right back.
- **Neither has been checked.** Injury reports have no history, so this season is the first data.

## Data (all already logged; nothing new is collected)
- `injuries/log.csv`: every ESPN pull with `pulled_at` (model source).
- `injuries/sources/first_seen.csv`: the first time each source listed each player and status.
- `reports/cbb_<date>.csv` and `reports/features_<date>.csv`: the card's saved games and inputs.
- Player box scores for 2026-27 (`data.fetch("player_box", 2027)`): who actually played.
- Lines: `lines/openers.csv` and `lines/closing.csv`; the protocol's primary close (`cbb/clv_primary.py`).
- **Injury state per game** is rebuilt from `injuries/log.csv` at two fixed moments:
  - **T−60:** the last pull at least 60 minutes before the verified tip;
  - **T-open:** the last pull at or before the first logged quote for the game.
- **Scope:** D-I vs D-I games from Nov 3. Exhibitions and non-D-I games are excluded.

## Questions and pre-registered tests
**Q1. Is P(miss) calibrated?**
- **Data:** listed players at T−60. The outcome is that the player did not appear in the box score.
- **Report:** the observed miss rate by status, with a Wilson 95% interval and n, for ESPN, and by source as a
  secondary.
- **Proposal rule:**
  - For any status with ≥ 40 listings whose interval excludes the current guess, propose the observed rate.
  - It is shrunk toward the guess with 20 listings of weight: (misses + 20 × guess) / (n + 20).
  - Statuses with < 40 listings keep the guess.

**Q2. Is the injury adjustment sized right? (primary)**
- **Term:** each game's injury term in points, J = weight × (home injury minutes − away injury minutes) at T−60.
  This is the live formula; it is 0 when nobody qualifies.
- **(a) Against the model:** regress the margin residual (result − v1 projected margin) on J.
  - A slope of 0 means the live size is right; > 0 means the model under-reacts; < 0 means it over-reacts.
  - SEs are clustered by date.
- **(b) Against the market:** regress the residual against the closing spread on J. This asks whether the market
  already prices the report.
  - **Secondary, for timing:** the same at the opener, with J at T-open.
- **Proposal rule:**
  - If (a)'s interval excludes 0 (see the reads below), propose scaling the live injury term by (1 + slope), capped
    at [0, 3].
  - **Not proposed alone:** a scale-up that (b) shows the closing market fully prices, meaning the
    beyond-the-close slope is ≤ 0. Such a change could only shift picks toward lines that have already moved; it
    is reported, not proposed alone.
- **Minimum sample:** 300 games with J ≠ 0.

**Q3. Totals.**
- **Gap:** v1's totals do not use missing minutes.
- **Test:** regress the totals residual (result − v1 total) on combined injury minutes (home + away) at T−60, with
  date-clustered SEs, in 300+ games.
- **Use:** descriptive at Dec 15; a proposal at Jan 15 only under the same interval rule as Q2. Any proposal is a
  new totals input and needs a backtest proxy using "missed last game" minutes, 2014-2026, before it can go anywhere.

**Q4. Did injury-moved picks do better or worse?** (descriptive)
- **Which plays:** logged plays whose edge crossed the threshold only because of the injury term, meaning they
  would not be plays with J = 0.
- **Report:** their record, units at recorded prices, and CLV at the primary close, against all other plays.

## Reads (sequential, with the false-positive rate controlled)
- **Dec 15 (early look, games through Dec 12):**
  - **Q1:** any status meeting its rule can be proposed. It is a calibration, not a bet rule.
  - **Q2:** a proposal only if (a)'s **99.9%** interval excludes 0 (Haybittle-Peto). Otherwise descriptive.
  - **Q3, Q4:** descriptive.
- **Jan 15 (decision read, games through Jan 10):**
  - Q2 and Q3 use the **95%** interval (Haybittle-Peto keeps the overall error near 5%).
  - If Q2 has fewer than 300 games with J ≠ 0, the decision moves to **Feb 15** (games through Feb 12), same rule.
- **What each read reports:**
  - n at each step;
  - the date-clustered intervals;
  - the result split by source (ESPN vs the source chosen by `injury_sources`);
  - every exclusion with its reason.
- **No re-specification after seeing data:** not J, the time cutoffs, the regressions or the thresholds.

## What a "pass" means
- **The proposal:** a mid-season proposal of a small, named change: the P(miss) table and/or one scaling factor
  on an existing term. These are the kinds of changes that can be made safely within a season.
- **What still has to happen:** Chad decides. The protocol's mid-season rules apply: version tag, MODEL_FREEZE
  entry, Discord note, and the forward test continuing on v1 if he switches.
- **A fail or a too-small sample:** leaves v1 unchanged.

## Data checks to run before Dec 15 (so the read cannot be blocked by plumbing)
- `injuries/log.csv` starts filling once games begin. ESPN's feed is empty preseason, so the file does not exist yet.
  Confirm at the Nov 4 shadow check.
- 2026-27 player box scores load (the same 404 the v2 shadow is waiting on).
- Verified tip times exist for every game. They come from the tip-time check; unresolved conflicts are excluded and
  listed.
- The evaluation script (`research/injury_reports/evaluate.py`) is written and committed **before Dec 15**, run once
  on November data for plumbing only, without reading results.
