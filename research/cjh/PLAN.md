# CJH Analytics: two pre-registered reads (written Oct 29, 2026, before any 2026-27 game)

Research only. Nothing live changes because of this file, and nothing is added to the card, the shadows or the bet
logs. Approved by Chad on Oct 29.

**Source:** cjhanalytics.com, an independent fan site.
- **Permissions:** robots.txt sets no content signals and no disallow rules. The only notice is about trademarks.
- **Storage:** the raw files are stored only in the private data repo. If the site's data is ever used in anything
  shared or sold, ask the owner first (colinhanleydev@gmail.com).

## Snapshots (`snapshot.py`, ledger `snapshots.csv`)
- **Files:**
  - `preseason_projections.json` (team ratings);
  - `manual_overrides/player_injuries_2026.json` (players ruled out for 2026-27);
  - `player_projections.json` (player BPM and minutes);
  - `players_current.json` (2025-26 season player lines);
  - `changelog.json`.
- **Where they live:** saved to `cbb-data/research/cjh/snapshots/<UTC time>/`, with hashes recorded in this repo.
- **Snapshots:** taken Oct 29 18:33 UTC, and again on Nov 2 (a one-time scheduled task).
- **Which one is used:** **the latest snapshot taken before the first 2026-27 tip (Nov 3).** Nothing fetched after
  that is used.

## Read 1: does CJH's preseason view carry information the market misses? (Dec 15)
**Our side:** the live model's frozen 2026-27 prior, `audit/out/frozen_preseason_prior_2027.csv` (KenPom +
Barttorvik preseason, fingerprinted in MODEL_FREEZE).

**Team disagreement:** each source is centered on the mean of the teams both rate, in points per 100 possessions.
- **Margin:** d = (CJH proj_em) − (our off + def).
- **Scoring:** u = (CJH proj_adjo + proj_adjd) − (our off − def), the team's contribution to game points.
- **Tempo:** τ = (CJH proj_adjt) − (our tempo).
- **Team names:** matched by the KenPom crosswalk (`cbb/teams.id_lookup("kenpom")`). 364 of 365 teams match.

**Game features** (0.68 = 68 possessions / 100; 2.1 = two teams × ~1.05 points per possession):
- **Margin:** G_m = (d_home − d_away) × 0.68.
- **Total:** G_t = (u_home + u_away) × 0.68 + (τ_home + τ_away) × 2.1.

**Games:**
- D-I vs D-I games, Nov 3 through Dec 12, 2026.
- Both teams must be matched and have a closing line.
- Sources: the protocol's primary close (`cbb/clv_primary.py`); openers from `lines/openers.csv`; the live
  projection from `reports/cbb_<date>.csv`.
- Every exclusion is listed with its reason.

**Primary test (one read, Dec 15):**
- **Regression:** OLS of (home margin + closing home spread) on G_m, with an intercept and date-clustered standard
  errors.
- **Pass:** the slope is > 0 and its 95% interval excludes 0. That means CJH's preseason disagreement predicts
  results beyond the close.

**Secondary (reported, never decisive):**
- **Totals:** the same regression with (total points − closing total) on G_t.
- **Openers:** both regressions at the opener.
- **Our own model:** (result − live projection) on G_m and G_t. This asks whether our model under-uses what CJH
  sees.
- **Our picks:** the card's logged plays split by whether CJH's disagreement points the same way as the play:
  win %, units at recorded prices, and closing line value.

**What a pass means:** a proposal only.
- **Mid-season:** nothing changes. By mid-December the preseason prior carries little weight.
- **Next season:** consider CJH's preseason ratings as a third prior source for 2027-28. That needs their past
  preseason ratings (to ask the owner for) and a backtest first.
- **A fail:** closes the idea.
- **Labels:** results are exploratory, with no re-specification after seeing data.

## Read 2: opening-week injury cross-check (Nov 20, with the injury-study build step)
**Players:** every player CJH lists as "out" in the pre-opening snapshot (10 on Oct 29). Their value comes from
`player_projections.json`: projected BPM and minutes (roster_mpg, else mpg). For players without a projection
(6 of 10 on Oct 29, Donnie Freeman among them), it comes from their 2025-26 line in `players_current.json` (BPM,
MPG). Matching is by name and team, else by name alone when unique (transfers: Freeman played for Syracuse,
Cason for Michigan). A player found in neither is listed as unvalued.

**Material:** projected BPM ≥ +2 or minutes ≥ 20 per game. Defined now.

**Per player, for the team's games Nov 3-9 (descriptive):**
1. **List accuracy:** did he appear in any 2026-27 box score (`data.fetch("player_box", 2027)`)?
2. **ESPN:** was he on ESPN's injury report (`injuries/log.csv`) at T−60 before his team's first game? Only
   listed players enter the live injury term.
3. **Our model:** did it account for him? Before a team's first game, "missed the last game" (`players.py`) cannot
   see him. So the live model sees him only through ESPN's report, or through KenPom and Barttorvik's preseason
   ratings, which we cannot observe.

**For teams with a material player out, their first two games:**
- **Market vs model:** mean (closing spread − our projection) and (result − closing spread), oriented to that team.
  This compares them with all other opening-week team-games.
- **Plays:** our logged plays on those games and their results.

**Decision rule (fixed now):** recommend building a preseason long-term-injury input only if both hold:
- material out-players are mostly missing from ESPN's report before the first game;
- the close sits on average at least 1 point further against those teams than our projection does.

Otherwise, record "not needed". The sample is tiny (10 listed players; 4 material on projections alone). This is a check, not
a test.

## Exclusions and honesty rules
- **Coverage:** unmatched teams and players, games without a close or projection, and non-D-I games are all
  listed.
- **No re-specification:** none of the inputs, cutoffs, thresholds or regressions change after the snapshot.
