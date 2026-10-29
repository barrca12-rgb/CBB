# Player-impact ratings for absences (pre-registered Oct 29, 2026, before any rating was fit)

Research only. The live model, shadows, picks, alerts, thresholds, staking and bet logs are unchanged. Nothing is
promoted from this study. **2025-26 has been examined in many earlier studies; results are exploratory.**

## Question
Today the model values a missing player by **minutes only**. The term `miss_diff` is the excess share of usual
minutes from regulars who missed the team's last game, with a stage-2 weight learned on all players alike. A
player-impact rating says **how much the team changes** without that player.

Does valuing absences by player impact improve 2025-26 spread forecasts and net units beyond the current model and
the strongest existing candidate (lineup v2)?

## Data (`pull.py`; derived files only, in the private data repo)
**Source:** CollegeBasketballData play-by-play, pulled by UTC date with the players on the floor for every play.
- **Seasons:** 2023-24, 2024-25 and 2025-26. Earlier seasons have no on-floor data.
- **Size:** about 480 API calls on the free tier.
- **Storage:** raw plays are not kept, because the terms forbid redistribution and the files are several GB.

**Stints:** consecutive plays in a game with the same players on the floor.
- **Per stint:** seconds, and each side's points and possessions (FGA − ORB + TOV + 0.475 FTA).
- **Irregular listings:** the source sometimes lists 4 or 6 players for a side. Those sides are kept and each
  listed player is weighted 5/n. Plays outside 4-6 are dropped and counted.
- **Game link:** CBBD's `gameSourceId` is ESPN's game id.
- **Orientation check:** home/away is matched against the schedule's final score, and any mismatch is listed.
- **Coverage:** reported by season and month.

## Ratings (fit walk-forward; never on games on or after the cutoff)
**Model:** for each stint side, points per 100 possessions = μ + h·home + Σ offense_i − Σ defense_j.
- **Players:** weighted 5/n.
- **Observation weight:** possessions.
- **Estimation:** ridge, with each player's offense and defense shrunk toward a prior with weight λ (in
  possessions).
- **Prior:** ρ × the player's previous-season rating (same CBBD athlete id), else 0. 2023-24 has no previous
  season, so its prior is 0.
- **Refits:** weekly. The fit on Monday T uses stints dated before T and serves every game from T through the
  following Sunday. Every game's ratings therefore use only games at least 1 day older. That holds for the close
  and, at D−1, for openers too.
- **Net rating:** r = offense + defense (points per 100 possessions).
- **Replacement level:** the possession-weighted mean net rating of players with < 10% of their team's minutes in
  the same fit.

## Absence feature (pre-game information only)
**Regular:** a player who appeared in ≥ 3 of the team's earlier games this season (in CBBD data).

**Minutes share:** m_p = his seconds / the team's seconds over the team's earlier games (out of 5 floor spots).

**Missing:** a regular with 0 seconds in the team's most recent earlier game. This is the same signal the live
`miss_diff` uses. If that game is absent from CBBD data, the team gets no value: J = 0 and the row is flagged.

**Team impact:** D = Σ over missing p of m_p × (r_p − r_rep), in points per 100 possessions lost.
- **Excess:** the team's mean D over its earlier games is subtracted, mirroring `excess_missing`.
- **Game term:** J = (D_away − D_home) × (stage-1 predicted possessions / 100), in points of home margin.

**Forecast:** candidate margin = baseline v1 margin + γ·J.
- **γ:** fit by OLS without an intercept on (result − baseline margin).
- **Overlap:** the baseline already contains `miss_diff`, so γ measures only what player value adds beyond the
  minutes rule.

## Learning (before 2025-26 is scored; `out/frozen.json` is committed first)
- **Grid:** λ ∈ {500, 1,000, 2,000, 4,000} and ρ ∈ {0, 0.5}. That is 8 variants, all recorded.
- **Validation:** for each variant, γ is fit on 2023-24 rows and validated on 2024-25 rows. The choice is by
  margin MSE.
- **No-adjustment candidate:** included as γ = 0. If no variant beats it, the frozen choice is "none".
- **Final:** γ refit on 2023-24 + 2024-25 with the chosen λ and ρ.

## Scoring (2025-26) and verdict
**Pools** (identical opportunities, prices and selection rules for every comparison):

| Pool | Status | Inputs and prices |
|---|---|---|
| A: closing spreads | **primary** | assumed −110, live-like baseline (persistent_disagreement.baseline, 462-335-0 at openers) |
| B: ESPN openers | descriptive | untimestamped |
| C: DraftKings first-observed dated sample | sample | 272 games, strict inputs, recorded prices |

- **Totals:** secondary only. The offense and defense parts give a total term, reported descriptively.

**Comparisons:** baseline, candidate, and lineup v2 (the strongest existing spreads candidate).
- **Coverage pool:** the baseline is also reported on games where both teams' absence terms are observed.
- **Report:** opportunities, bets, W-L-P, win %, ROI and units.
- **Differences:** date-clustered paired bootstrap intervals.
- **Selection changes:** retained, added, dropped and reversed bets.
- **Breakdowns:** monthly results and concentration.
- **Diagnostics (supporting only):** MAE and bias, and the beyond-close coefficient of γJ.

**Verdict rule (fixed now).** "Adds net units" requires, on pool A, all of:
1. the frozen choice is not "none";
2. candidate − baseline > 0, with the 95% date-clustered interval above 0;
3. the same difference > 0 on the coverage pool;
4. candidate − lineup v2 > 0.

Otherwise the answer is **no**. There is no re-specification after scoring.

## Verification (separate script)
- **Stint accounting:** stint points sum to the finals, and the seconds and possession totals are plausible.
- **Timing:** every rating used for a game comes from stints dated before its weekly cutoff. Absence status comes
  only from earlier games. A perturbation test checks both.
- **Reconciliation:** the baseline is reconciled to earlier studies.
- **Grading:** recomputed independently.
- **Untouched:** no change outside this folder.
