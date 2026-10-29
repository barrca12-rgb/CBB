# Preseason exhibitions: do D-I vs D-I exhibition results predict early-season games? (pre-registered Oct 29, 2026, before any exhibition data was seen)

Research only. The live model, every shadow, schedule and the card are unchanged; nothing here adds a shadow.

## Why
- Since 2025-26 the NCAA allows up to two public preseason exhibitions against any school, including D-I, and
  scrimmages no longer have to be closed-door. Our ESPN data has no preseason games (checked: the 2025-26 and 2026-27
  schedules start at the regular season).
- The model is weakest in the first weeks, when ratings are mostly the preseason prior (KenPom + Torvik preseason
  average, `cbb/backtest.preseason_prior`). Exhibitions are the only D-I results played before then.

## Data
- **Source:** the neilball.org list of men's college exhibitions and scrimmages (provided by Chad as an export;
  the site blocks automated access).
- **Sample:** 2025-26 games between two D-I teams with a final score. Excluded: non-D-I opponents (no ratings),
  unscored or "closed" results, and games with a non-standard format (e.g. extra periods or a running clock, if
  noted). Team names are matched to ESPN ids with `data/teams.csv` and aliases; unmatched names are listed, not
  guessed.

## Signal (per team)
- **Expected exhibition margin:** from the preseason prior alone (no games yet): the two teams' prior efficiency
  difference, scaled to points with the stage-1 league pace and efficiency of 2024-25. Home edge: the league home
  edge if the page names a home team; 0 if neutral or unknown.
- **Expected exhibition total:** the same, for points.
- **Surprise:** actual minus expected margin, from the team's side, averaged over its D-I exhibitions (at most two);
  capped at ±25 per game. The same for totals.

## Outcomes
- Each team's first 10 regular-season games against D-I opponents in 2025-26, from the team's side:
  - **vs model:** result minus frozen v1's walk-forward forecast (live-like frame, opening-week rule);
  - **vs opener:** result plus the opening spread (and total minus the opening total);
  - **vs close:** the same against the close.
- Windows: games 1-10 (primary), 1-5 and 6-10 (secondary).

## Test
- **Model:** regression of each outcome on the team's surprise. SEs are clustered by team (a team's games share
  one surprise) and checked against date clustering.
- **Primary:** the margin slope vs the opener, games 1-10.
- **Pass:** the 95% interval excludes 0 in the expected (positive) direction, and a 10-point surprise implies at
  least 0.5 points against the opener.
- **Totals:** the same rule, reported separately.
- **Secondary:**
  - the slope vs the model (whether the model under-reacts);
  - the slope vs the close (whether the market already prices exhibitions);
  - n of teams and games;
  - the fixed-threshold record of the card's opener plays split by surprise sign (descriptive).

## Reading the result
- **One season of data:** the test can find only a sizable effect. A null means "no large effect", not "none".
- **Pass:** a hypothesis, not a change. 2026-27's exhibitions (played in October 2026) give a clean confirmation
  set. The same test, unchanged, would be scored on 2026-27 games 1-10 in early December, before any proposal.
- **No change** to the card either way without Chad's approval, a backtest, a MODEL_FREEZE entry and a Discord
  note.
