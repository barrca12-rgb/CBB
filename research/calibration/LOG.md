# Calibration and data checks on the frozen model's margin error (research only; nothing live changes)

Brief: `/root/.claude/uploads/.../main-session-prompt-calibration-checks.md` (helper, Oct 27).
- **Scale:** the frozen live-like model misses the margin by 8.88 and the close by about 8.84, so a tenth is a third
  of the gap.
- **Noise floor:** below 0.02 margin MAE or 0.1 opener CLV is reported as noise.
- **Rules:** no live change and no new shadow before March 16. A candidate is written up for the March decision.

**Benchmark:** frozen live-like stage-2 walk-forward (`research/originator/d_common.frames()` + `walk_forward`;
crews zeroed, KenPom from the day before), openers oriented (`oriented_openers`), swapped records excluded where
lines are used. Intervals are date-clustered (OLS sandwich, or a bootstrap over dates).

## 2026-10-27: pre-registration (written before any of the five was run)

### 1. Calibration slope by edge size
- **Overall:** OLS of actual margin on predicted margin, 2020-26, slope and intercept.
- **Walk-forward calibration:** for each season s from 2020, fit (a, b) on 2014..s-1 and predict a + b x
  prediction. Report the MAE change on 2020-26.
- **By bucket:** |edge| against the opener and against the close in [0, 2.5), [2.5, 4), [4, 6), 6+.
  - The bucket "slope" is the calibration ratio: mean realized edge (result minus line, from the model's side) over
    mean predicted edge, with a bootstrap interval over dates.
  - Close: 2020-26. Opener: every season with openers (2014-17, 2024-26), since 2020-23 have none.
  - Totals the same way.
- **Kill:** every bucket's ratio within 0.03 of 1.
- **If not killed:**
  - re-fit the win-chance rule (p = 0.5 + k x edge, capped) to realized cover rates on earlier seasons, and report
    it on later ones;
  - report what the re-fit changes in play count and opener CLV.
  - The Jan 15 win-chance-cap question is answered from the 5+ bucket's realized win % at the opener against the
    0.58 cap.
- **Prior:** large edges overstated (ratio under 1 in the top buckets), moderate.

### 2. Residual persistence by team
- **Residual:** team-side residual r = actual - predicted margin from that team's side.
- **Predictor:** the mean of the team's previous 5 games in the same season (5 required).
- **Fit:** OLS of r on that mean, date-clustered, 2014-26. Also by month and by the team's conference tier, and
  out of sample (coefficient fit on seasons before s, R2 on 2020-26).
- **Events, coefficient within each subset:**
  - a coaching change: the first 10 games of a season with a new coach (`data/research/coaches.csv`);
  - after a first absence: the 5 games after the team's first game this season missing a rotation player (20+ mpg
    over the previous 5 games);
  - a transfer-heavy preseason: the first 10 games of a season where under 40% of the team's minutes in its first
    5 games went to players who played for it last season.
- **Kill:** coefficient under 0.05, or its interval includes 0.
- **If not killed:** a team-specific decay test, specified then.
- **Prior:** near zero overall (the 120-day half-life was tuned); possibly concentrated after events.

### 3. Home edge by season
- **By season, non-neutral games, 2014-26:**
  - mean home residual of the frozen model, with an interval;
  - realized mean home margin;
  - the model's mean predicted home margin;
  - the stage-2 home terms' contribution (prediction minus prediction with `venue` and `team_hca` set to 0, same
    fitted coefficients).
- **Kill:** no season's mean home residual outside ±0.3 (the interval is reported).
- **If not killed:** a season-level in-season home term. From each season's 301st non-neutral game on, add the mean
  residual of that season's earlier non-neutral games (walk-forward by date). Report the MAE change 2020-26 and
  opener CLV.
- **Prior:** the model tracked the drift. An earlier read (`research/hca/LOG.md`) had seasons within ±0.33.

### 4. Venue and neutral-flag audit
For every game 2014-26, compare ESPN's neutral flag with the venue (schedule `venue_id`, city, name) against each
team's home venue (`home_venue_id` / `away_venue_id`) and home city (the most common city of its non-neutral home
games that season).

| Flag | Definition |
|---|---|
| F1 | neutral, venue = home team's home venue |
| F2 | neutral, venue = away team's home venue |
| F3 | neutral, venue city = either team's home city (not F1/F2) |
| F4 | not neutral, home team's game at a venue other than its home venue and outside its home city |
| F5 | neutral, a team's location name in the venue name (not F1-F3) |

- **Report:** counts by season, the frozen model's mean residual on flagged vs other games (from the side the flag
  favors), and win % at the opener and close for 2.5+ plays on flagged games.
- **Data fix if systematic:** a residual of 2+ points on a few hundred games. Applied to the evaluation first and
  proposed for the card as a reviewable diff.
- **The list is saved** for the March conference-tournament crowd test.

### 5. Referee home bias on margin (close only)
- **Per official:** the home-side residual of the frozen model's margin over earlier games (strictly earlier
  dates), shrunk with 30 games of prior (`context.REF_PRIOR`), averaged over the crew = `ref_home`.
- **Fit:** added to the stage-2 margin inputs, walk-forward, with crews known (close only; benchmark refit on the
  same frame).
- **Kill:** margin MAE 2020-26 within 0.01 of the benchmark, or the close spread win rate (2.5+ vs the close,
  2020-26) within 0.5 points.
- **Prior:** low.

### Summary deliverable
- One table: check, number, interval, verdict (closed / candidate for v3 at March 16 / data fix proposed).
- One top sentence: the total margin MAE these would remove together, against the gap to the close.

## 2026-10-27: results (`out/c*_run.txt`, `out/c*_result.csv`; flagged games `out/c4_flagged_games.csv`)

**Total:** together these five would take about **0.005** off margin MAE. That is half a hundredth, under the 0.02
noise floor and about a tenth of the 0.047 gap to the closing line (model 8.880 vs close 8.833 on the same 37,486
games, 2020-26). None is worth a v3 change.

| Check | Number | Interval | Verdict |
|---|---|---|---|
| 1. Calibration, overall slope (actual on predicted, 2020-26) | spread 0.993, total 1.003 | [0.978, 1.007], [0.984, 1.022] | closed |
| 1. Walk-forward recalibration, MAE change 2020-26 | spread -0.001, total +0.082 | | closed |
| 1. Realized/predicted edge vs opener, buckets 0-2.5 / 2.5-4 / 4-6 / 6+ | 0.50 / 0.57 / 0.49 / 0.77 | e.g. [0.46, 0.69] for 2.5-4 | see note |
| 2. Residual persistence (next game on previous 5) | -0.005 | [-0.017, 0.008] | closed (also flat by month, tier, new coach, after an absence, low returning minutes; OOS R2 0.000) |
| 3. Home residual by season | -0.33 to +0.24; 2015 -0.30, 2022 -0.33 | 2022 [-0.73, 0.11] | closed: in-season home term MAE 8.8823 -> 8.8829, CLV 1.250 / 1.127 -> 1.250 / 1.119 |
| 4. Neutral flag audit | F1+F2 (neutral at one team's arena): 84 games, host residual +2.5 / +1.6 | [-0.22, 5.30] / [-1.26, 4.65] | closed (too few games to matter); list saved for March |
| 5. Referee home bias on margin (close only) | MAE -0.0035; close win % 52.22 -> 52.60 | | closed (under 0.01 and 0.5) |

**Note on check 1.** The literal kill rule (every bucket ratio within 0.03 of 1) is not met, but the ratio measures
the market, not miscalibration:
- **Why it is below 1:** against a line, realized edge is about half of predicted edge (opener) and about a quarter
  (close) in every bucket, because the line carries information. The model itself is calibrated (slope about 1,
  recalibration gains nothing).
- **The win-chance rule** is fit to realized cover rates and matches them at the opener in 2024-26:

| Edge | Realized | Rule |
|---|---|---|
| 2.5-3 | 56.0% | 57.0% |
| 3-4 | 58.4% | 58.0% |
| 4-5 | 59.4% | 58.0% |
| 5-6 | 59.5% | 58.0% |
| 6+ | 66.7% | 58.0% (cap) |

- **Re-fit:** fitting the slope on 2014-17 gives 0.0183 per point, which fits 2024-26 worse than the current 0.0255.
- **Large edges are not overstated relative to small ones:** the 6+ bucket's ratio is the highest.

**Jan 15 win-chance-cap question, answered now:**
- The cap (58%) understates 5+ edges: they won 66.2% of 394 at the opener.
- But at -110 the +2% EV rule only binds below 1.34 points of edge, so the cap changes no play at normal prices. It
  matters only at about -138 or worse.
- **Close it:** no change needed. Raising the cap would only change displayed win % and EV.

**Totals oddity (check 1):** totals edges of 6+ against the opener (mean predicted 10.7) realized only 1.8 (ratio
0.17, 4,522 games). Nearly all are large early-season or old-opener gaps. This matches the opening-week totals problem
the live rule already handles, and is not a new finding.
