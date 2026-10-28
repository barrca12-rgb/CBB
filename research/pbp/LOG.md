# Play-by-play edge search (research only; nothing live changes)

Benchmark: the frozen live-like model and its stage-2 frames (`research/originator/out/d_frames_frozen.pkl`).

## 2026-10-27: pre-registration (written before any play-by-play was aggregated)

**Data:** ESPN play-by-play from sportsdataverse (`cbb/cache/pbp/`), 2014-2026. Shot coordinates exist for about
6% of shots and substitutions are absent, so shot location and on-court lineups are out of scope.

### P1. Shot-quality luck

**Shot classes, from the play text and type:**
- rim: layup, dunk, tip;
- two-point jumper;
- three-point jumper ("Three Point" in the text);
- each split into assisted and unassisted ("Assisted by").

**Expected points:** each class's league make rate for that season x its point value, summed over a team's
attempts.

**Shooting luck** = actual field-goal points - expected field-goal points, for the offense and for the points
allowed on defense.

### P2. Garbage time

- **Definition:** second half or overtime, 10 minutes or less left in the game, margin above 20 before the play.
- **Garbage net points** = the team's points minus its opponent's in those stretches.

### Features

Season-to-date, before each game, per game played, shrunk toward 0 with 5 games of prior:
- **Margin model:** (home luck off - home luck def) - (away luck off - away luck def), and home garbage net - away
  garbage net.
- **Totals model:** the sum of all four luck terms, and the sum of both teams' garbage points (both sides).

### Test

**How the features enter:** they are added to the stage-2 ridge (margin and total), fit walk-forward on the
live-like frames exactly like the existing inputs. Three challengers: P1 alone, P2 alone, P1 + P2.

**Scorecard 1:** margin and total MAE 2020-26 against the frozen model.

**Scorecard 2:**
- (a) the coefficient on (challenger - frozen) when regressing (result - close), controlling for the frozen edge
  vs the close, 2020-26, with a date-clustered CI;
- (b) opener CLV of the frozen rule's plays, development 2014-17 and confirmation 2024-26;
- opener spread and total win % (development 2014-17 + 2024; holdout 2025-26) are reported, not decisive.

**Pass (candidate for a v3 shadow):** (a)'s CI excludes 0 for the margin or the total, AND (b)'s CLV gain is
+0.05 points or more in both eras for that market. Otherwise killed.

**Priors:**
- P1: low-moderate (the 3-point luck regression already takes the largest part).
- P2: low (the ratings weight games, not garbage minutes, so the effect may be small).

## 2026-10-27: deviation, logged before any feature was computed

ESPN records "Assisted by" only on made shots, so a missed shot cannot be labeled assisted or unassisted and a
per-class make rate for the split is undefined (assisted makes would be 100% by construction). P1's classes are
therefore rim, two-point jumper and three only. Everything else is unchanged. Tip shots are counted as rim; any
other shot type with a 2-point value is counted as a two-point jumper.

## 2026-10-27: data fix, P2 rerun

The first run showed garbage time as zero in every season before 2023: `end_game_seconds_remaining` is wrong in
those files (e.g. 2686 seconds left midway through the first half). Time left now comes from the period clock
(`clock_display_value`), which is correct in all seasons. The definition is unchanged. P1 does not use the clock
and its numbers are unchanged; the first run's P2 and P1+P2 results are void.

## 2026-10-27: results (rerun with the clock fix; `out/p_result.csv`, `out/p_run.txt`)

| | frozen | P1 luck | P2 garbage | P1+P2 |
|---|---|---|---|---|
| margin MAE 2020-26 | 8.8823 | 8.8816 | 8.8817 | 8.8812 |
| total MAE 2020-26 | 13.1499 | 13.1520 | 13.1444 | 13.1466 |
| spread CLV dev / conf | 1.250 / 1.127 | 1.253 / 1.128 | 1.254 / 1.149 | 1.253 / 1.136 |
| total CLV dev / conf | 0.646 / 1.671 | 0.640 / 1.662 | 0.648 / 1.657 | 0.644 / 1.652 |
| beyond-close, margin coef (se) | | 3.51 (1.00) | 0.71 (0.48) | 0.98 (0.44) |
| beyond-close, total coef (se) | | 0.77 (0.62) | 1.15 (0.40) | 0.95 (0.31) |
| adjustment SD, margin / total (pts) | | 0.05 / 0.14 | 0.12 / 0.22 | 0.13 / 0.28 |
| opener spread win% dev / holdout | 56.76 / 57.66 | 56.72 / 57.92 | 56.82 / 58.13 | 56.84 / 58.06 |
| opener total win% dev / holdout | 55.45 / 55.53 | 55.28 / 55.13 | 55.38 / 54.81 | 55.40 / 54.92 |
| **verdict** | | **KILL** | **KILL** | **KILL** |

All three meet (a) for at least one market (CI excludes 0) and none meets (b): CLV gains are 0.00-0.02 points
against the +0.05 needed in both eras.

**Reading:** the information is real and the closing line does not fully price it (coefficients near or above 1,
P1 margin 3.5). But the stage-2 ridge, fit to final scores, gives it almost no weight: the adjustments are
0.05-0.28 points, too small to change which games we play. This motivates fitting such features to the market
residual instead of the score. That would be a separate test, pre-registered before it is run.

## 2026-10-27: R1 pre-registration, market-residual correction (written before it was run)

**Idea:** the stage-2 ridge is fit to final scores, where these signals are small next to game noise, so it
nearly ignores them. Fit them instead to what the market misses: the result minus the closing line.

**Inputs (season-to-date, known before the opener; no line information):**
- margin: `luck_margin`, `garbage_margin` (P1/P2 above), lineup adjustment margin `(h_off + h_def) - (a_off + a_def)`
  (research/originator/b_rotation, `out/b_adjustments.csv.gz`);
- total: `luck_total`, `garbage_total`, lineup adjustment total `(h_off + a_off) - (h_def + a_def)`.

**Fit:** OLS with intercept, walk-forward by season. Season s is fit on seasons 2014..s-1, target (home margin +
closing home spread) for the margin and (total points - closing total) for the total. Swapped records are excluded
from fitting. First predicted season 2015.

**Forecast:** frozen live-like margin + the predicted margin residual; the same for totals. The frozen play rule
(spread edge 2.5+, total 3+) is applied at the opener.

**Scorecards:**
- opener CLV of the plays, dev 2015-17 and confirm 2024-26 (2014 has no fit);
- opener win% dev (2015-17 + 2024) and holdout (2025-26);
- for reference, the walk-forward beyond-close coefficient 2020-26.

**Pass:** CLV gain +0.05 or more over frozen in both eras for a market, AND that market's holdout opener win% not
below frozen. Otherwise killed. One specification, no tuning.

**Prior:** low-moderate. The lineup part alone is what the v2 shadow already tracks.

## 2026-10-27: R1 results (`out/r1_result.csv`, `out/r1_coefs.csv`, `out/r1_run.txt`): KILL

| | frozen | R1 |
|---|---|---|
| spread CLV dev / conf | 1.297 / 1.127 | 1.311 / 1.116 |
| total CLV dev / conf | 1.358 / 1.671 | 1.331 / 1.456 |
| spread win% dev / holdout | 57.13 / 57.66 | 57.25 / 57.49 |
| total win% dev / holdout | 57.22 / 55.53 | 57.76 / 55.15 |
| plays, spread dev/hold | 2596 / 1599 | 2732 / 1743 |
| plays, total dev/hold | 4691 / 2602 | 5616 / 3416 |

Beyond-close coefficients 2020-26 are significant (margin 1.45, se 0.27; total 0.68, se 0.12). But the corrections
are small (SD 0.21 margin, 0.67 total) and do not improve opener CLV in either era. Most of the total correction
is the intercept: about +0.7 points, so games finish slightly over the close on average. That pushes more plays to
the over and lowers CLV. Of the margin terms, only the lineup adjustment carries weight (0.14-0.16), and it is
already in the v2 shadow.

## 2026-10-28: R2 pre-registration, luck-only totals correction (written and committed before it was run)

**Why:** in R1 the one stable shot-quality weight was `luck_total` (about -0.10 every season: games where teams have
been shooting luckily finish slightly under the close), but the total correction was dominated by the intercept
(+0.7), which pushed plays to the over and cut CLV. R2 isolates the luck term. Asked for by Chad, Oct 28.

**Input:** `luck_total` only (P1, season-to-date, known before the opener; no line information).
**Fit:** OLS **without an intercept**, walk-forward by season: season s fit on 2014..s-1, target (total points -
closing total), swapped records excluded. First predicted season 2015. Spreads are not touched.
**Forecast:** frozen live-like total + coefficient x `luck_total`; the frozen play rule (total edge 3+) at the opener.
**Scorecards:** total opener CLV, dev 2015-17 and confirm 2024-26; total opener win% dev (2015-17 + 2024) and
holdout (2025-26); for reference the beyond-close coefficient 2020-26 and the correction's SD.
**Pass:** total CLV gain +0.05 or more over frozen in both eras AND holdout total win% not below frozen. Otherwise
killed. One specification, no tuning.
**Prior:** low (the correction's SD will be small, about 0.1 x the luck spread).
