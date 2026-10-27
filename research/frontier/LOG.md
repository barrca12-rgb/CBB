# Frontier tests: log

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

