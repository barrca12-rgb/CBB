# Our own roster-based preseason ratings: results (pre-registered in PLAN.md, Nov 5, 2026)

Backtest only. Nothing live changes. Rerun: `python -m research.roster_prior.build check`, then `... priors`,
`... stage1 roster`, `... stage1 blend`, `... score` (output in `out/step1.txt`, `out/step2.txt`, `out/*.csv`).

## Verdict

- **Step 1 passed.** The roster prior tracks the season's final team rating far better than last season's results.
- **Step 2: no variant meets its bar.** The roster prior closes about half the gap to KenPom/Barttorvik when it
  replaces them, but it does not replace them, and it does not improve the current model. No proposal.

## Step 1: preseason priors against the final margin rating, 2016-2026 (3,890 team-seasons)

| Prior | RMSE | Correlation |
|---|---|---|
| (a) KenPom/Barttorvik preseason | 6.24 | 0.830 |
| (b) Last season x 0.6 | 5.69 | 0.754 |
| (c) Roster prior | **5.00** | 0.805 |

The RMSE favors (c) partly because (a) is on a wider scale than our ratings (it was not refit to them). On
correlation, which ignores scale, the roster prior closes 67% of the gap between (b) and (a). The pre-registered gate
(RMSE) passed; it would also pass on correlation.

## Step 2: the full model, 2015-2026 (roster prior used from 2016)

| Variant | Margin miss, days 0-20 / all | Total miss, days 0-20 / all | Spreads win % 15-17 / 24-26 | Totals win % 15-17 / 24-26 |
|---|---|---|---|---|
| Base (KenPom/Barttorvik prior and stage 2) | 9.174 / 8.770 | 13.732 / 13.245 | 57.51 / 57.69 | 58.35 / 57.54 |
| B4: last season x0.6, no outside | 9.771 / 8.965 | 13.917 / 13.290 | 53.00 / 53.41 | 57.23 / 56.00 |
| **R1: roster prior, no outside** | 9.488 / 8.875 | 13.878 / 13.282 | 55.00 / 54.70 | 57.88 / 57.09 |
| R2: roster prior + outside in stage 2 | 9.190 / 8.792 | 13.824 / 13.267 | 55.43 / 56.57 | 57.56 / 57.64 |
| R3: blended prior + outside in stage 2 | 9.165 / 8.771 | 13.759 / 13.249 | 56.81 / 57.27 | 58.23 / 57.94 |

Against the pre-registered reading:
- **R1 replaces the outside prior?** No. Early margin miss is 0.31 above base (allowed 0.10) and opener spreads are
  2.5 and 3.0 points lower (allowed 1.5). It does close **47%** of B4's early-margin gap and lifts opener spreads
  from 53% to about 55%, with fewer false edges (2,495 spread plays in 2015-17 against B4's 3,437).
- **R2 improves the model?** No. Every miss is higher than base and opener spreads are lower.
- **R3 improves the model?** No. Early margin miss is a hair lower (9.165 vs 9.174), but early totals are higher
  (13.759 vs 13.732) and 2015-17 opener spreads fall 0.7 points (allowed 0.5). 2024-26 totals are 0.4 points
  higher, which is not enough under the rule.

## Reading

Our roster data gets about halfway to what KenPom and Barttorvik know before the season. What it is missing, in the
order I would try next:
1. **Better player values.** The box-score rating uses fixed weights. Lineup on/off data exists from 2023-24 (CBBD),
   which is short but direct.
2. **Development by class.** Players improve most from freshman to sophomore year; we treat every returner as
   staying the same. Class year is on ESPN rosters, not in our box scores.
3. **Level of transfers.** A low-major star moving up rates lower against high-major opponents; we carry the rating
   over unchanged.
4. **Recruits.** Every freshman gets the same newcomer value. Recruiting rankings are not in our data and would need
   a source Chad approves.

The leak noted in the plan (rosters from the first 5 games) helps the roster prior, so the real gap is if anything
a little larger.

# Version 2 (pre-registered in PLAN_v2.md, Nov 5, 2026): development, transfer level, better player values

Rerun: `python -m research.roster_prior.build_v2 check` (output in `out/v2_step1.txt`, `out/v2_step1.csv`).

## Verdict: stopped at the step-1 gate. No step 2, no proposal.

| Prior vs final margin rating, 2016-2026 | RMSE | Correlation |
|---|---|---|
| KenPom/Barttorvik preseason | 6.24 | 0.830 |
| Roster v1 | 5.00 | 0.805 |
| **Roster V2a** (development + transfer level + level/relative features) | 4.92 | 0.812 |
| Roster V2b (V2a + lineup ratings, 2025-26 priors) | 4.92 | 0.812 |

The gate needed +0.010 in correlation or -0.10 in RMSE over v1. V2a gave +0.007 and -0.08. By the rule, step 2 does
not run.

## What the additions did

- **Development:** players with 200+ minutes in both seasons gain 6.0 rating points after their first season, 4.1
  after the second and about 3.4 after that. Part of this is selection (players who keep minutes are the ones who
  improved), which the ridge then partly corrects.
- **Transfer level:** a transfer's rating falls 0.50 points for each point of team margin he moves up, as expected.
- **Lineup ratings (3b):** a small further gain where available (2025-26 RMSE 5.13 -> 5.10).
- **By season (correlation, found after the result):** V2a's gain is larger in recent seasons: 2024-2026 average
  0.823 against v1's 0.810, closing about half the remaining gap to KenPom/Barttorvik (0.834). In 2021, the COVID
  season, every roster version beat KenPom/Barttorvik (0.79 vs 0.76).

## Reading

The three additions help, mostly in the transfer-portal years, but not by enough to pass the bar set in advance.
The biggest piece still missing is freshman and recruit quality: every newcomer gets one value, while KenPom and
Barttorvik use recruiting rankings. That needs a data source Chad approves.

# Version 3 (pre-registered in PLAN_v3.md, Nov 6, 2026): learned box weights and box-anchored lineup ratings

Prompted by the xRAPM article (roycewebb.com, NBA). Rerun: `python -m research.roster_prior.build_v3 check` (output in
`out/v3_step1.txt`, `out/v3_step1.csv`).

## Verdict: stopped at the step-1 gate. No step 2, no proposal.

## Step 0: learned weights value players much better

Predicting 2026 lineup ratings (818 players with 300+ possessions, possession-weighted correlation):

| Player rating | Correlation |
|---|---|
| Game Score fixed weights (current) | 0.379 |
| **Learned weights, fit on 2024-2025 lineup data** | **0.529** |

The learned weights (2024-2026) reward assists, offensive rebounds and steals; penalize turnovers heavily (offense
-0.23 and defense -0.12 per turnover per 100 possessions) and missed shots; and give defensive credit to steals,
blocks and defensive rebounds. Points alone earn far less than in Game Score once shot attempts are charged.

## Step 1: team priors

| Prior vs final margin rating, 2016-2026 | RMSE | Correlation | 2025-2026 correlation |
|---|---|---|---|
| KenPom/Barttorvik | 6.24 | 0.830 | 0.841 |
| Roster V2a | 4.92 | 0.812 | 0.827 |
| **Roster V3a** (learned weights) | 4.86 | 0.817 | **0.836** |
| Roster V3b (+ box-anchored lineup ratings) | 4.88 | 0.816 | 0.827 |

The gate needed +0.010 correlation or -0.10 RMSE over V2a; V3a gave +0.005 and -0.06. Step 2 does not run.

## Reading

- The learned weights are a clear improvement in valuing players (0.38 -> 0.53 on a held-out season), but most of
  that gain washes out at the team level: a roster average smooths over individual errors.
- Box-anchored lineup ratings (V3b) add nothing on top of the learned weights; on two seasons of lineup data the
  lineup part is still noise.
- Found after the result: in 2025-2026, V3a's correlation (0.836) is within 0.005 of KenPom/Barttorvik (0.841). Across
  all seasons, roster ratings have moved 0.805 -> 0.812 -> 0.817 (v1 -> v2 -> v3) against 0.830.
- The learned weights are reusable: injury absences are valued today with minutes only (`miss_diff`); valuing an
  absent player by learned-weight impact is a separate, testable idea (backlog).
