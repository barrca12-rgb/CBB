# New head coaches: result (Oct 28, 2026; plan in PLAN.md, committed before the run as a8409cc)

`python -m research.new_coach.study` -> `out/result.csv`, `out/run.txt`. Difference = new-coach teams minus every
other team, points per game from the team's side, 95% interval from a date bootstrap.

**Primary window, the team's first 10 games:**

| Seasons | New-coach teams | vs the model | vs the close | vs the opener |
|---|---:|---:|---:|---:|
| 2025-26 (primary) | 64 | -0.29 [-1.28, +0.77] | -0.12 [-1.14, +0.96] | -0.22 [-1.22, +0.84] |
| 2021-22 to 2024-25 | 264 | +0.71 [+0.14, +1.31] | +0.56 [-0.04, +1.23] | +0.34 [-0.50, +1.25] (133 teams) |
| 2014-15 to 2019-20 | 315 | -0.23 [-0.74, +0.28] | -0.65 [-1.24, -0.06] | -1.33 [-2.28, -0.42] (132 teams) |
| 2021-26 pooled | 328 | +0.51 [-0.01, +1.02] | +0.43 [-0.10, +0.96] | |

**Decay (vs the model):** 2025-26 games 1-5 +0.23, 6-10 -0.83, 11-20 +0.11, 21+ +0.19. 2021-25: +1.02, +0.41,
-0.21, -0.54. 2014-20: -0.69, +0.23, +0.55, -0.12.

**Pre-registered splits, first 10 games, 2025-26 vs the model:** high-major -0.29, mid-major +0.32, low-major -0.45;
bad last season (likely firing) -0.11, not bad -0.45. All intervals span 0 by more than a point either way.

**Verdict under the reading rule: no bump.**
- Last season new-coach teams played slightly *worse* than the model in their first 10 games (-0.29), and about even
  with the close (-0.12): no early edge to capture.
- 2021-25 shows a modest positive effect (+0.7 vs the model, mostly games 1-5), but 2014-20 shows the opposite sign
  and 2025-26 does not repeat it. The rule needed the same sign in all three and at least 1.0 point last season; it
  fails on both.
- Against the market the 2021-25 effect is +0.56 with an interval touching 0; in 2014-20 the market was *over*-rating
  new-coach teams early (-0.65 vs the close). Nothing consistent enough to bet.
- No change to the model; nothing goes to the Jan 15 checkpoint from this study. Any narrower idea (for example a
  specific kind of hire) would need its own pre-registration before looking, not a cut of these results.

## Follow-up: high-major new coaches who brought transfers (plan PLAN_transfers.md, committed before the run)

`python -m research.new_coach.transfers` -> `out/transfers_run.txt`, `transfers_teams.csv`, `transfers_hires.csv`.
Group A = high-major new coach whose players from his previous school played 20%+ of the minutes in the first 5
games: 10 team-seasons in 2021-26 (72 high-major new hires in all). Games counted are Division I vs Division I.

| First 10 games | A teams | A vs everyone: vs the model | vs the close | A vs other high-major hires: vs the model |
|---|---:|---:|---:|---:|
| 2021-26 pooled | 10 | -0.11 [-2.68, +2.64] | -0.66 [-3.25, +2.11] | -0.69 [-3.53, +2.23] |
| 2025-26 | 3 | +1.36 [-3.66, +6.52] | +0.89 [-3.94, +5.64] | +2.02 [-3.70, +8.01] |

Games 1-5 vs 6-10 (pooled, vs the model): +1.49 then -1.55. With 2+ followers instead of the 20% rule (16
team-seasons): +0.22 vs the model, -0.20 vs the close.

| Season | Team (coach, from) | Followers, share of minutes | vs the model | vs the close |
|---|---|---|---:|---:|
| 2021-22 | Utah (Craig Smith, Utah State) | 2, 27% | -0.52 | -1.42 |
| 2022-23 | LSU (Matt McMahon, Murray State) | 3, 38% | -2.34 | -2.64 |
| 2022-23 | Missouri (Dennis Gates, Cleveland State) | 4, 24% | -1.47 | -0.75 |
| 2023-24 | Penn State (Mike Rhoades, VCU) | 2, 27% | +3.75 | +1.50 |
| 2023-24 | Providence (Kim English, George Mason) | 2, 27% | +0.18 | +0.65 |
| 2024-25 | Arkansas (John Calipari, Kentucky) | 4, 43% | -2.98 | -3.00 |
| 2024-25 | Louisville (Pat Kelsey, Charleston) | 3, 22% | -4.10 | -5.62 |
| 2025-26 | West Virginia (Ross Hodge, North Texas) | 2, 30% | +4.12 | +3.25 |
| 2025-26 | Iowa (Ben McCollum, Drake) | 5, 57% | +1.97 | +0.36 |
| 2025-26 | Xavier (Richard Pitino, New Mexico) | 2, 22% | -2.18 | -1.07 |

**Verdict under the reading rule: not real, not worth money.** Pooled, these teams were even with the model (-0.11)
and slightly behind the close (-0.66); the rule needed +1.0 with an interval above 0. Last season's +1.36 comes from
three teams, two of them good starts (West Virginia, Iowa), and earlier years run the other way (Louisville,
Arkansas, LSU). The early-game split (+1.5 in games 1-5, -1.6 in games 6-10) looks like noise, not a fading bump.
No change to the model.
