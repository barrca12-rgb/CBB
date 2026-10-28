# New head coaches: an early-season bump? (pre-registered Oct 28, 2026, before any result was looked at)

Chad's question (Oct 28): do teams with a new head coach deserve an early-season adjustment, judged on 2025-26?
Research only: no change to the live v1 model, the card, selection or staking (frozen until the Jan 15 checkpoint).

**Data.** `research/calibration/out/base.pkl`: the frozen live-like benchmark's walk-forward prediction for every
Division I game 2014-2026 (`final_margin`), the result, the closing spread (`home_spread`) and, where logged, the
opener (`open_home_spread`). New coaches: `data/research/coaches.csv` (`new` = first season at the school).
Each game is used twice, once from each team's side. A team's game number counts its games in this table that
season, in date order.

**Groups.** New-coach team-games against all other team-games, in the same window. Games where both teams have a
new coach are dropped (the two sides cancel).

**Outcomes, team's side, points (+ = the team did better than the benchmark):**
1. vs the model: actual margin minus the model's margin (is the model too low on these teams?);
2. vs the close: actual margin plus the team's closing spread (would the market already have it?);
3. vs the opener, where logged (2025-26 has openers; earlier seasons mostly do not).

**Windows.** Primary: the team's first 10 games. Also games 1-5, 6-10, 11-20 and 21+ (the decay).

**Seasons.** Primary: 2025-26 (Chad's ask). Replication: 2021-22 to 2024-25 pooled, and 2014-15 to 2019-20 pooled
(2020-21 left out: short, irregular season). Statistics: mean difference with a 95% interval from a bootstrap over
game dates (2,000 draws, fixed seed).

**Pre-registered splits (no others):** conference tier of the team (high / mid / low, `research.originator.d2_tiers`
levels); last season's results (team's mean margin last season below 0, a likely firing, vs at or above 0, a likely
departure).

**Reading rule, fixed now.**
- A bump vs the model is **real** only if the primary window's difference has the same sign in 2025-26 and in both
  replication pools, at least 1.0 point in 2025-26, and the pooled 2021-25 interval excludes 0.
- It is **worth money** only if, in addition, the difference vs the close has the same sign, at least 0.5 point,
  with the pooled 2021-26 interval excluding 0. A model-only bump the close already has improves the model's
  numbers but would not win bets.
- Otherwise: no change; the result is recorded here either way. A real, money-worthy bump goes to Chad as a
  proposal for the Jan 15 checkpoint (walk-forward backtest of the adjusted model, freeze entry, Discord note).

**Caveats known in advance.** The benchmark is a walk-forward replica of v1, not the live model with its Oct 26
preseason prior; KenPom and Barttorvik preseason ratings already react to coaching moves, so some or all of any
effect may be priced in. Splits are small (about 64 new-coach teams a season, 10 games each).
