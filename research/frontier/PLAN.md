# Frontier tests: pre-registration

Written 2026-10-27, before any of the runs below. Research only: nothing here touches live v1, the card, the
logger, either shadow or the forward-test protocol. No new shadow before March 16; anything that survives is
written up for the March decision. Source prompt: the helper's "frontier tests" prompt (Oct 27).

Claim under test: "the frozen model is at the frontier of public team-level box-score systems, within 0.05 of the
close." Scale: hundredths of a point of margin MAE, tenths of a point of opener CLV. Noise floor: 0.02 MAE,
0.1 CLV. Any result under it is reported as under the noise floor.

## Standard scoreboard (same as research/pbp and research/originator)

- Benchmark: the frozen live-like variant (research/originator/d_common `frames()` + `walk_forward()`), chronological
  only: each season's stage 2 fit on earlier seasons.
- Forecast: margin and total MAE, test seasons 2020-2026.
- Opener CLV of the frozen rule (spread 2.5+, total 3+): development 2014-2017, confirmation 2024-2026.
- Win % at the opener for the same rule: development 2014-2017 + 2024, holdout 2025-2026.
- Information beyond the close: OLS of (result - close) on (challenger - frozen), frozen edge as control,
  date-clustered standard errors, 2020-2026.

## Part A. Prediction Tracker benchmark (blocked: host not reachable from this environment)

Prior: the frozen model sits in the top quarter of Prediction Tracker's systems on MAE and behind the line; one or
two systems (likely market-informed or ensembles) beat it in some seasons.
Comparison is "comparable" only if our MAE is computed on Prediction Tracker's game universe and line definition;
otherwise labeled approximate.
Kill rule for the frontier claim: any public system beats our MAE by 0.05 or more in three or more seasons on a
comparable universe -> claim withdrawn, that system goes to the top of Part C.

## Part B1. Rematch effects

Universe: conference games where the same two teams already met earlier in the same season (2nd and 3rd meetings).
Features (oriented to the current home team, from the most recent earlier meeting):
- `rm_resid`: that meeting's margin against its closing spread (margin + home spread), sign flipped if the current
  home team was the away team then. Total version `rm_tresid`: that meeting's points minus its closing total.
- `rm_flag`: 1 if a rematch, else 0 (all features 0 for non-rematches).
- `rm_flip`: 1 if the venue flipped (the current home team was the away team in the earlier meeting).
- Days between meetings: reported, not a model input.

Free check first: correlation of the frozen model's residual (result - model) in rematches with `rm_resid`
(and total versions), with a 95% interval.
Prior: small negative correlation (the earlier result over-informs the market and the ratings slightly; coaches
adjust), |r| under 0.05. Stage-2 coefficient on `rm_resid` near zero.
Kill rule: coefficient interval includes zero, or opener CLV gain under 0.1 (both eras), or holdout win % below frozen.

## Part B2. Public-team bias

Data: ESPN scoreboard per game date (research/frontier/b2_fetch.py): AP rank at game time (curatedRank) and TV
networks. Definitions fixed now:
- Ranked: AP top 25 at game time. Features: `rk_home`, `rk_away` (1/0), margin input `rk_diff` = rk_home - rk_away,
  total input `rk_any` (either ranked).
- National TV (primary): ESPN, ESPN2, ABC, CBS, FOX, FS1, TNT, TBS, truTV, NBC. Broad national (secondary, reported
  only): primary plus ESPNU, CBSSN, BTN, SEC Network, ACC Network, Pac-12 Network, Big Ten Network, FS2. Streaming
  (ESPN+, ESPN3, Peacock, Paramount+, conference streams) is not TV. Completeness of the broadcast field reported by
  season.
- Splits (the mechanism: public money pushes the line past the model on the brand-name side): among frozen-rule
  spread plays, win % at the opener and at the close for (a) plays on vs against the ranked side when exactly one
  team is ranked, (b) on vs against the home side in national-TV games vs not; also mean line move (open to close)
  toward the ranked side.
- Stage-2 inputs: `rk_diff` (margin), `rk_any` and `tv_nat` (total), and `tv_nat` x home as `tv_home` (margin).

Prior: ranked teams are slightly overpriced at the close (under one point), little of it at the opener; the split
differs by less than one standard error; stage-2 coefficients near zero after KenPom and Barttorvik.
Kill rule: no split differs by more than one standard error, or opener CLV gain under 0.1.

## Part C1. Ensemble breadth (EvanMiya, Haslametrics; blocked: hosts not reachable from this environment)

Daily snapshot of team ratings and game predictions with fetch time, from the first day it runs; archive check first.
Prior: each adds a small positive stage-2 weight beside KenPom and Barttorvik; opener CLV gain under 0.1.
Kill rule: coefficient near zero, or opener CLV within 0.1 of the frozen model.

## Part C2. Stage-1 functional form

Current stage 1: decayed ridge on additive points per possession. Alternatives on the same data, schedule, half-life,
prior and luck regression:
- (a) multiplicative efficiency: ratings on log points per possession (KenPom's form), predictions exp(sum).
- (b) a possession-level count model: Poisson (and negative binomial if overdispersed) of each team's points with
  log(possessions) offset.
Report stage-1 margin and total MAE, and through the unchanged stage 2, the standard scoreboard.
Prior: (a) within 0.02 of the current form (the additive and multiplicative forms nearly coincide around average
teams; they differ only for mismatches); (b) likewise.
Kill rule: stage-1 MAE within 0.02 of the current form.

## Part D. The gap, split by late news (reporting only)

Model MAE against the close on games with no injury-feed change between the card run and tip vs games with one.
Data limits fixed now: the injury feeds (injuries/) start in the 2026-27 season, so the split uses this season's
logged cards only; it is reported with its sample size and is expected to be thin until January.
If the gap concentrates in late-news games, the doc's wording changes to "matches the market's final number using
only what was public at the opener."
