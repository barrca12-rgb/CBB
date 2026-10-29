# Player-impact ratings for absences: log and result (Oct 29, 2026)

Research only. Nothing live changed, nothing is promoted, and no follow-up variant is launched from the 2025-26
result. 2025-26 has been examined in many earlier studies, so this is **exploratory**.

## Verdict
**No.** Valuing absences with player-impact ratings did not add net units at the close.

| Closing spreads 2025-26 (primary) | Bets | Units | Δ vs baseline (95% date-clustered) |
|---|---|---|---|
| Baseline (v1, minutes-based `miss_diff`) | 861 | −22.91 | |
| **Candidate** (baseline + γ·J) | 859 | −22.82 | **+0.09 [−6.91, +7.18]** |
| Lineup v2 (strongest existing) | 826 | −3.18 | candidate − v2: **−19.64** |

**Frozen rule:**

| Condition | Result |
|---|---|
| (1) Choice is not "none" | yes |
| (2) Interval above 0 | **no** |
| (3) Coverage pool > 0 | **no** (−0.82) |
| (4) Beats lineup v2 | **no** |

**Why it changes so little:** the player value is real in the data, but almost none of it survives once the
current model's minutes-based absence term is in.
- The absence term J has an SD of about 1 point per game.
- The fitted weight γ on the baseline's residual is only +0.03 to +0.05, in every variant and both learning
  seasons.
- So the adjustment averages 0.05 points and moves 19 of about 870 bets at the close.

**ESPN openers are not evidence.** They show candidate − baseline +12.36 [+4.73, +20.73], which is descriptive
only (untimestamped).
- **The bets that changed:** only 19: 10 added (+5.27) and 9 dropped (−7.09 under the baseline).
- **Size of the change:** 0.05 points only flips bets sitting exactly at the threshold.
- **At the close:** the same change is +0.09.
- **Beyond the line:** the adjustment's coefficient is +0.95 (SE 3.05) at the opener and −0.64 (SE 3.09) at the
  close.

This is threshold noise, not a signal, and it does not count under the pre-registered rule.

## Data (CollegeBasketballData play-by-play with players on the floor; derived stints only, in the private repo)
**Pull:** 485 date calls (2023-24 has a leap day), plus about 23 re-pulled after a fix, plus retries. 434 of the
monthly allowance remain.

| Season | Schedule games | With stints | Final within ±3 (used) | Mismatch (excluded) | Possessions vs box |
|---|---|---|---|---|---|
| 2023-24 | 5,723 | 5,637 | 5,583 | 54 | 0.976 |
| 2024-25 | 5,759 | 5,640 | 5,481 | 159 | 0.981 |
| 2025-26 | 5,752 | 5,709 | 5,021 | **688 (12%)** | 1.000 |

- **Verification failure, recorded and not explained away:** 2025-26 fails the ≤ 5% mismatch check. The source's
  2025-26 on-floor data has more scoring gaps. Those games are excluded from rating fits but still used for
  minutes and absence status.
- **Irregular listings:** 4 or 6 players listed for a side are common, about 10-20% of plays early in 2023-24 and
  2025-26. They are weighted 5/n.
- **Coverage pool:** both teams' absence status observed in 72.6% of 2025-26 closing opportunities. There is none
  in week 1, and none when the team's last game has no stints.

## Every variant (learning: γ fit on 2023-24, validated on 2024-25; "none" = γ 0, MSE 126.9768)
| λ | ρ | γ (2023-24) | 2024-25 MSE | J SD |
|---|---|---|---|---|
| 500 | 0 | +0.030 | 126.9731 | 1.034 |
| **500** | **0.5** | +0.030 | **126.9727** | 1.119 |
| 1,000 | 0 | +0.040 | 126.9756 | 0.748 |
| 1,000 | 0.5 | +0.040 | 126.9754 | 0.832 |
| 2,000 | 0 | +0.042 | 126.9778 | 0.527 |
| 2,000 | 0.5 | +0.042 | 126.9779 | 0.604 |
| 4,000 | 0 | +0.025 | 126.9778 | 0.356 |
| 4,000 | 0.5 | +0.025 | 126.9780 | 0.420 |

**Frozen choice:** λ 500, ρ 0.5.
- **MSE gain:** 0.004 over "none".
- **γ:** refit on 2023-24 and 2024-25 to +0.052.
- **Frozen before 2025-26:** the choice and γ were committed before any 2025-26 rating was computed.

## Other pools and diagnostics (full tables in `out/report.txt`)
- **DraftKings sample (272 games, 3 dates, recorded prices):** identical bets to the baseline (+7.89).
  Lineup v2 made +8.82.
- **The sample's beyond-line coefficient** (+26, SE 0.63) is meaningless: there are only 3 date clusters and an
  adjustment of 0.05 points.
- **Accuracy at the close:** baseline MAE 8.992 and candidate 8.992. Lineup v2 is 8.977 and the line is 8.940.
- **Monthly candidate − baseline at the close:** Nov 0, Dec +0.91, Jan −0.91, Feb −1.91, Mar +1.09, Apr +0.91.
  15 dates differ.
- **Totals, descriptive:** (points − closing total) on the absence total term has slope −0.16 (SE 0.28). No
  signal.

## Reconciliation
- **Live-like opener spreads:** 462-335-0 (target 462-335-0).
- **DraftKings sample baseline:** 43 bets, 27-16-0, +7.89 (target matched).
- **Lineup v2 frame vs baseline margin:** max difference 2e-14.

## Verification (`verify.py`, `out/verify.txt`)
**Passed:**
- **Timing:** everything on or after Jan 15, 2025 was perturbed. Features for all 2,857 earlier games were
  unchanged, while 95% of later games changed.
- **Order:** the prediction hash matches, and `frozen.json` was committed before the 2025-26 features and
  predictions.
- **Grading:** all 12 pool × price × strategy results were recomputed exactly.
- **Untouched:** no study commit touches a file outside this folder. The 24 outside files that changed came from
  scheduled jobs.

**Failed:** the 2025-26 stint mismatch rate, as described above.

## What this says
- **For absences:** player-impact ratings built from three seasons of lineups don't improve on the live minutes
  rule.
- **Consistent with earlier work:** value-weighted absences and roster strength were tested before (in
  `cbb/player_ratings.py`) and also earned no place.
- **Where it does better:** lineup v2, which adjusts for rotation changes rather than "missed last game", still
  does better on these pools.
- **Possible next questions** (not launched; each needs its own plan):
  - player ratings as a preseason or roster input;
  - the ratings inside the injury-report study's T−60 status, instead of "missed last game".

Per instructions, nothing is pursued from the 2025-26 result.
