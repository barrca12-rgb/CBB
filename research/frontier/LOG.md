# Frontier tests: log

**Bottom line (Oct 27):** no public system or layer tested beats the frozen model; every challenger run fails its
pre-registered kill rule (opener CLV gains under 0.1, MAE changes under the 0.02 noise floor). The Prediction Tracker
comparison could not be run (browser check), so the frontier claim is not yet confirmed against named systems. Best
near-miss: a Poisson stage 1 for totals (+0.06, +0.05 opener CLV).

Every specification run, in order, including failures. Pre-registration: PLAN.md (committed before any run).

## B1 rematch effects (run 1, Oct 27) — KILL

Spec as pre-registered (`b1_rematch.py`). 21,850 conference games are rematches (2nd or 3rd meeting); the earlier
meeting had a closing line in 83.7%; venue flipped in 87.3%; median 28 days apart.

- Free check: frozen model's margin residual in rematches vs the earlier meeting's residual against the line,
  r = -0.025 [-0.039, -0.010], n = 18,293 (same venue -0.035, flipped -0.023). Against the close: r = -0.022.
  Totals: r = +0.015 vs the model, -0.005 vs the close. Real but tiny: a team that beat the line by 10 in the
  first meeting does about 0.24 points worse than the model expects in the rematch.
- Stage-2 coefficient on `rm_resid`: -0.024 (se 0.008), interval excludes zero; `rm_flag` and `rm_flip` on margin
  include zero.
- Scoreboard: margin MAE 8.8823 -> 8.8822, total MAE 13.1499 -> 13.1454 (both under the 0.02 noise floor).
  Opener CLV gain (dev 2014-17, conf 2024-26): spread -0.021, +0.010; total +0.035, +0.045 — all under 0.1.
  Holdout win %: spread 57.66 -> 57.93, total 55.53 -> 55.47. Information beyond the close: margin 0.545 (0.341),
  total 0.338 (0.160), on adjustments with SD 0.17 and 0.51 points.
- Verdict: KILL (opener CLV gain under 0.1 in both eras and both markets).
- Side finding, not the pre-registered mechanism: on totals, same-venue rematches carry -2.2 points (`rm_flag`
  -2.21, `rm_flip` +2.43, both well outside zero). Same-venue rematches are mostly conference-tournament games
  (neutral floor, third meetings), so this is a postseason scoring effect, not a rematch effect. Noted for the
  March list as a question (is the existing season-type handling already catching it at the opener?), not tested.

## B2 public-team bias (run 1, Oct 27) — KILL

Data: ESPN scoreboard for all 1,844 game dates 2014-2026 (`b2_fetch.py`), matched to 70,778 of 70,778 frame
games. Broadcast field present for every game in every season; AP rank (curatedRank) at game time on every team.
National TV (primary networks) 11-17% of games by season, broad national 22-32%, at least one ranked team 11-14%.

- Split (a), frozen-rule spread plays with exactly one team ranked: on the ranked side 58.5% at the opener
  (se 2.7, n 342), 54.7% at the close; against it 59.9% (se 2.7, n 319), 55.6% at the close. Against minus on at
  the opener +1.4 (se 3.8): under one standard error. Line move open -> close toward the ranked side: +0.040 pts
  (se 0.026, n 3,584), i.e. no measurable public push on ranked teams.
- Split (b), plays on home vs away, national TV vs not, at the opener: TV home 58.3% (se 2.6), TV away 55.4%
  (se 2.4); off-TV home 57.2%, away 57.0% (se 1.1). Difference of differences -2.7 (se 3.9): under one standard
  error.
- Stage-2 coefficients: margin `rk_diff` -0.07 [-0.38, +0.25]; margin `tv_nat` +0.35 [+0.10, +0.60]; total
  `rk_any` +0.33 [-0.11, +0.77]; total `tv_nat` -0.07 [-0.52, +0.38].
- Scoreboard: margin MAE 8.8823 -> 8.8816, total 13.1499 -> 13.1506 (under the noise floor). Opener CLV gain
  (dev, conf): spread +0.012, +0.012; total -0.020, +0.023. Holdout win %: spread 57.66 -> 57.04, total
  55.53 -> 55.37.
- Verdict: KILL (no split beyond one standard error; opener CLV gain under 0.1).
- Side finding: home teams beat stage 2 by about 0.35 points in national-TV games (interval excludes zero), but it
  moves neither forecast error nor opener CLV. Not a lead.

## D. The gap, split by late news — pending data (definition fixed Oct 27)

No completed regular-season games yet: the injury feeds (injuries/sources, every source's first_seen time) start
Oct 26, 2026 and the first card games tip Nov 2-3. Definition fixed now, to run at the Jan 15 read:
- Card run: the first committed version of reports/features_<date>.csv containing the game; its final_margin and
  final_total are the model's numbers, its commit time the card time.
- Late news: any row in injuries/sources/first_seen.csv for either team with first_seen after the card time and
  before tip (start).
- Report: model MAE against the closing consensus spread and total, games with late news vs without, with counts
  and date-clustered standard errors; and the same split of the model's MAE against the result.
If the model-to-close gap concentrates in late-news games, the doc's wording changes to "matches the market's final
number using only what was public at the opener."

## C1 ensemble breadth — snapshot started Oct 27; archive answer

Hosts allowed by Chad on Oct 27.
- Haslametrics: public. The current ratings file (ratings.xml) carries every team's full time-dependent ratings
  (offense, defense, tempo, shooting splits); today it holds the 2026-27 preseason (365 teams). Archive: one file
  per season 2015-2026 (351-365 teams), pulled to snapshots/haslametrics_archive/. Each has end-of-season ratings
  (not usable for past games: look-ahead) and a daily rank history per team (overall, offense, defense ranks by
  day), not daily rating values or game predictions. So a historical test is possible only on daily ranks; the
  full test needs the forward snapshots.
- EvanMiya: the team-ratings table is public (team, obpr, dbpr, bpr, tempo, opponent and pace adjustments, ranks;
  365 teams). Game predictions and the past-games archive are subscriber-only ("Basic Subscription required"); not
  fetched (no purchase or login without Chad's approval). No public dated archive of ratings found.
- Snapshot: `c1_snapshot.py`, daily at 13:17 UTC by .github/workflows/frontier_snapshot.yml (reads only; writes
  research/frontier/snapshots/). First day, Oct 27 20:15 UTC: Haslametrics 365 teams, EvanMiya 365 teams.
- Plan unchanged: with one full season of snapshots, each system as a stage-2 input beside KenPom and Barttorvik,
  plus equal-weight and fitted blends as a benchmark. Optional earlier read on the Haslametrics daily-rank
  history (2015-2026) as a weaker, rank-only version; not run yet.

## A. Prediction Tracker — blocked by a browser check

thepredictiontracker.com (allowed host) answers every scripted request with a Cloudflare "Enable JavaScript and
cookies" page (HTTP 403); www.thepredictiontracker.com is not on the allowed list. Not worked around. Ways forward:
Chad saves ncaaresults.php and its per-season archive pages from a browser and uploads them, or Part A stays open.

## C2 stage-1 functional form (run 1, Oct 27) — KILL (Poisson totals noted as a near-miss)

Spec as pre-registered (`c2_forms.py`, `c2_score.py`). The frozen stage-1 file reproduces exactly from
cbb.backtest (2019: max difference 1e-13), so the alternatives differ only in the efficiency form; pace, Four
Factors, half-life, prior strength and the 3-point luck regression are unchanged. Spec details fixed during the
run: the multiplicative form carries a smearing correction (arithmetic, not geometric, mean level); the Poisson
form uses a log(possessions) offset (a first attempt with log(possessions/100) diverged and was discarded), and its
ridge pull is scaled by mean Fisher information so the prior is still worth 6 games. Dispersion 0.68-0.71 in every
season (underdispersed after the luck regression), so the negative binomial variant does not apply.

- Stage-1 MAE, 2020-26 (2014-26): additive margin 8.9014 (8.7544), total 13.1686 (13.3325); mult margin 8.9096
  (8.7611), total 13.1580 (13.3262); Poisson margin 8.9065 (8.7590), total 13.1520 (13.3214). Every difference
  within 0.02: margin +0.005 to +0.008 worse, total -0.006 to -0.017 better.
- Through the unchanged stage 2: margin MAE 8.8823 -> 8.8870 (mult), 8.8849 (Poisson); total MAE 13.1499 ->
  13.1362, 13.1332. Opener CLV gain (dev, conf): mult spread -0.055, -0.008, total +0.043, +0.037; Poisson spread
  -0.019, +0.016, total +0.062, +0.053. Holdout win %: spread 57.66 -> 58.37 / 57.66; total 55.53 -> 54.83 /
  55.23. Information beyond the close, total: mult 0.464 (0.144), Poisson 0.559 (0.153); margin near zero.
- Verdict: KILL by the pre-registered rule (stage-1 MAE within 0.02 of the current form).
- Near-miss for the March write-up, not a change: the Poisson form's totals are better in both CLV eras (+0.06,
  +0.05) with information beyond the close that clears two standard errors; holdout total win % does not improve.
  If anything is carried forward it is a totals-only question (Poisson total as a stage-2 input beside the
  additive one), to be pre-registered separately.

## C1-rank: Haslametrics daily ranks as a stage-2 input — pre-registration (written before the run, Oct 27)

The only historical C1 test the archive allows (the full test waits for a season of snapshots).
- Data: snapshots/haslametrics_archive/ratings15-26.xml (seasons 2015-2026): per team, the daily overall,
  offense and defense rank. Team ids in the file are ESPN ids.
- Timing: for a game on date D, the ranks of day D-1 (no same-day information). Days before the file's first day,
  and seasons 2013-2014 (no file), get 0 (average).
- Features: z = inverse-normal of the rank percentile, z = Phi^-1(1 - (rank - 0.5) / N), N = teams in that file.
  Margin input `hs_net` = z_overall(home) - z_overall(away). Total input `hs_tot` = z_off(home) + z_off(away)
  - z_def(home) - z_def(away).
- Prior: positive coefficient on `hs_net` with an interval excluding zero (ranks carry some of the rating), but
  most of it already in KenPom and Barttorvik; opener CLV gain under 0.1.
- Kill rule (as C1): coefficient interval includes zero, or opener CLV gain under 0.1 in both eras.

## C1-rank run 1 (Oct 27) — KILL

Coverage: both teams' day-before ranks in 82-84% of games 2015-2020 (the daily history starts in late November)
and 98% from 2021; 0 in 2013-2014 (no file).
- Stage-2 coefficients: margin `hs_net` -0.097 [-0.263, +0.069] (includes zero); total `hs_tot` -0.500
  [-0.697, -0.303] (a small correction against the rank-implied scoring, not an independent signal).
- Scoreboard: margin MAE 8.8823 -> 8.8824, total 13.1499 -> 13.1478 (under the noise floor). Opener CLV gain
  (dev, conf): spread -0.004, -0.011; total +0.008, -0.032. Holdout win %: spread 57.66 -> 57.80, total
  55.53 -> 54.96.
- Verdict: KILL. Daily ranks carry nothing beyond KenPom and Barttorvik. Says nothing yet about Haslametrics'
  rating values or predictions; that waits for the forward snapshots.

