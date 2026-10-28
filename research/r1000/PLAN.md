# Ridge-1,000 shadow test (behind the scenes; not on the site; no posts, alerts or stakes)

**Approved by Chad, Oct 27 2026:** track ridge-1,000 spreads and totals behind the scenes and compare its record to
the current model at Jan 15.

## What it is
- **Same model, same inputs.** The live model's final step combines its inputs (our ratings, KenPom, Barttorvik,
  market ratings, rest, back-to-backs, missing players, altitude, referees and others) with weights fit by ridge
  regression. Ridge regression pulls every weight toward zero by an amount set by a penalty. The live model uses
  penalty 1; this version uses 1,000. Fit on the same 76,238 games 2013-2026 (`research/r1000/fit.py`,
  `data/shadow_r1000.json`; with penalty 1 the fit reproduces the live `data/projection.json` exactly).
- **In practice:**
  - **Large-scale inputs (ratings, KenPom, Barttorvik, market ratings, ref crews): barely move**, because a penalty
    of 1,000 is small against 76,000 games of variation in them.
  - **Small-scale inputs: cut substantially:**
    - missing-player minutes: -6.29 -> -1.97;
    - back-to-back: 1.92 -> 1.10;
    - altitude: 1.36 -> 0.94 (margin), 1.76 -> 1.20 (total);
    - home-court flag: 0.20 -> 0.09.
  - So ridge 1,000 mostly trusts the injury/absence, back-to-back and altitude adjustments less.

## Backtest (research/weights/LOG.md, at the opener)
- Pre-registered pass rule: **not met** (development gain for totals did not carry over to 2025-26).

| | live | ridge 1,000 |
|---|---|---|
| spreads 2014-17 + 2024 | 56.76%, +273u | 56.12%, +213u |
| spreads 2025-26 | 57.66%, +161u | 58.82%, +176u |
| totals 2014-17 + 2024 | 55.45%, +489u | 56.83%, +614u |
| totals 2025-26 | 55.53%, +157u | 55.44%, +151u |

## How it runs
- **Card:** `.github/workflows/update.yml` runs `python -m cbb.card_features`. That runs `cbb.run_day` unchanged
  and also saves each built day's stage-2 inputs to `reports/features_<date>.csv`. No frozen file changed.
- **Shadow:** `.github/workflows/shadow_r1000.yml` runs `python -m cbb.shadow_r1000` after every card run.
  - It prices every game with both versions against the same latest quotes, using the card's own rule (opening-week
    totals adjustment, best EV across books, spread 2.5+ / total 3+, EV +2%).
  - It logs each new play once per version to `bets/shadow_r1000/signals.csv` (`model` = v1 or r1000;
    `other_model_signal` = whether the other version had the same play at that quote).
  - Also `games_latest.csv` (both versions' numbers per game) and `runs.csv`.
- **Checks:** v1 in the shadow is recomputed from the saved inputs. `runs.csv` `v1_check_max_diff` must stay ~0,
  meaning the inputs match the card.
- **Not part of the site's record:** the site reads `bets/bets.csv` only.

## Reads
- **Jan 15 (descriptive):** `python -m research.r1000.evaluate`: record by market and version, and for plays only
  one version made.
- **March 14:** the same, with the full season (moved from March 16 on Oct 28, Chad: before the NCAA tournament).
- **Caveat:** at about 400 spread plays by Jan 15, a 1-point win% difference is well inside noise (±5 points). Jan 15
  shows direction only.
