# Originator research: results (Oct 27, 2026)

**Benchmark:** the frozen live-like model. Everything here was pre-registered in `LOG.md`, with priors and kill
rules written before each run. Nothing changes live v1.

## In plain words

**Where is the frozen model's error predictable?**
- **Almost nowhere.** Its game-to-game misses break down exactly like the closing line's:
  - **Totals:** about a third each from the pace of the game, the home offense and the away offense.
  - **Margins:** essentially all from how well each offense shoots and scores on the night.
- **Pace and scoring-efficiency surprises are not predictable** from earlier games.
- **Who plays** is partly predictable, and a minutes-weighted rotation adjustment does carry a small real signal:
  about 0.4 points of margin per point of adjustment, with a confidence interval clear of zero. But it explains
  about a seventh of a percent of the miss.

**Is any of it information the market lacks?**
- **Mostly no.** What is predictable is either already in the closing line or too small to bet.
- **The one hint:** a team's past pace misses predicted the line's own miss slightly (point estimate positive,
  2.2 SEs at the team-points level). It fell below the pre-set predictability bar, so it is closed.
- **Parameter changes:** none of the re-tuning tests (recency weighting, early/late-season fits, tier-specific
  rating settings) moved forecast error by more than about 0.01 points or opener CLV by more than 0.03.
- **Conclusion:** the frozen model is already near its ceiling with this data. Its betting value comes from
  disagreeing with the opener before the market corrects, not from a fixable forecasting gap.

## Part A: error decomposition, 61,450 games 2014-2026

Share of the miss variance (the additive parts sum to 1):

| | Model: total | Line: total | Model: margin | Line: margin |
|---|---|---|---|---|
| Possessions (pace) | 0.32 | 0.32 | 0.00 | 0.00 |
| Home offense efficiency | 0.34 | 0.34 | 0.50 | 0.50 |
| Away offense efficiency | 0.34 | 0.34 | 0.50 | 0.50 |
| Overtime points, inside the above (2023-26 only) | 0.11 | 0.11 | 0.01 | 0.01 |
| Personnel shares (R2 with tonight's actual rotation; overlaps) | 0.002 | 0.003 | 0.012 | 0.012 |
| MAE | 13.41 | 13.15 | 8.76 | 8.72 |

**Breakdowns:** the same shares hold by month and by conference tier.

**Not decomposable:** late-game fouling and garbage time. They need play-by-play, which this repository does not
store. Every game is flagged rather than guessed. Ingesting play-by-play (a few GB) is the data requirement.

| Component | Out-of-sample R2 (fit 2014-19, test 2020-26) | Already in the line? |
|---|---|---|
| Possessions residual | 0.003 (**closed**, under 0.01) | Partly: the predictor's coefficient drops from 1.12 to 0.92 with the line term. A small remainder also predicts the line's miss (0.72, se 0.16, in team points) but sits below the bar |
| Offense efficiency residual | -0.019 (**closed**) | Not predictable at all |
| Personnel: absent share | 0.071 | Opens the Part B gate |
| Personnel: newly present share | 0.069 | Opens the Part B gate |

## Part B: rotation adjustment (gate)

- **Adjustment:** tonight's expected rotation minus the rotation the rating was built on, times each player's
  offensive and defensive box-score value relative to his team.
- **Result:** coefficient on the frozen model's margin miss 0.42 (95% CI 0.32-0.52, 2020-26), out-of-sample R2
  0.0014.
- **Verdict: FAIL** under the kill rule (R2 < 0.01). Per the pre-registration, no lineup simulator and no
  scorecards.
- **Note:** an effect of half a point cannot reach R2 0.01 against an 11-point miss. Whether that bar is right is
  a question for Chad and the helpers.

## Part D1: recency-weighted and two-regime stage 2

| Variant | Opener CLV gain, 2014-17 | Opener CLV gain, 2024-26 | Margin MAE 2020-26 (frozen 8.882) | Information beyond the close (margin coef, se) |
|---|---|---|---|---|
| Recency h=2 seasons | -0.011 | +0.030 | 8.881 | 0.21 (0.23) |
| Recency h=4 | -0.005 | +0.016 | 8.882 | 0.23 (0.44) |
| Two regimes (Nov-Dec / Jan on) | -0.007 | -0.012 | 8.881 | 0.18 (0.18) |
| Two regimes + h=4 | -0.008 | +0.016 | 8.881 | 0.18 (0.15) |

**All KILLED** (need +0.1 CLV in both eras).

## Part D2: tier-specific stage-1 parameters

- **Grid:** half-life 60/240, prior 3/12 games, luck 0.2/0.5. Six full stage-1 re-runs, 2013-2026.

| Tier | Chosen on 2014-19 | 2020-26 MAE | Frozen | Line | Gain |
|---|---|---|---|---|---|
| High | luck 0.5 | 8.970 | 8.976 | 8.918 | +0.006 |
| Mid | prior 12 | 8.829 | 8.818 | 8.786 | -0.011 |
| Low | luck 0.5 | 8.872 | 8.872 | 8.837 | **+0.0004** |

- **Verdict: KILLED** (low-major bar 0.03). Opener CLV was unchanged (1.456 vs 1.465 in 2024-26).

## Part C

Not run, as instructed. Part A's efficiency decomposition found no predictable matchup component, so no proposal
is written.

## Proposals for v2

**None.** Nothing passed both scorecards.
