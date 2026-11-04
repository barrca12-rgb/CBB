# Own ratings: results (pre-registered in PLAN.md, Nov 4, 2026)

Backtest only, as Chad asked. The live model, `cbb/ratings.py` and `data/projection.json` are unchanged.

**How the comparison was built:**
- **The base was rerun fresh.** A rerun of the current stage 1 differs by up to 1 point on a few games from the
  stored `cbb/output/backtest_2013_2026.csv` (the box-score data has been revised since). Every variant is
  therefore compared with a fresh rerun of the current code.
- **Files:**
  - `out/stage1.csv`
  - `out/stage1_by_season_*.csv`
  - `out/live_replay.csv`
  - `out/final_accuracy.csv`
  - `out/opener_plays.csv`
- **Rerun:** `python -m research.own_ratings.run stage1`, then `... score`.

## Study A: scoring level shrunk toward last season (K = 60 team-games)

### Stage-1 totals, average miss

| | Base | level60 | level20 | level200 |
|---|---|---|---|---|
| Days 0-20, 2014-2026 (12,689 games) | 13.820 | **13.818** | 13.817 | 13.840 |
| Full seasons, 2014-2026 | 13.332 | 13.331 | 13.331 | 13.333 |
| **Live replay, Nov 2-4, 2026 (138 games)** | **15.92 (bias −10.2)** | **13.50 (bias −1.8)** | 13.59 | 13.47 |

**Per season:** level60 against base runs from −0.012 to +0.004 on totals and changes margins by at most 0.001.
No season is worse by more than 0.02.

### Final model (walk-forward, 2015-2026)

**Average miss:** within 0.013 of base. Days 0-20 totals: 13.745 against 13.732.

**Opener plays:**

| Market | Seasons | Base win % | level60 win % |
|---|---|---|---|
| Spreads | 2015-17 | 57.51 | 57.38 |
| Spreads | 2024-26 | 57.69 | 57.74 |
| Totals | 2015-17 | 58.35 | 58.19 |
| Totals | 2024-26 | 57.54 | 57.56 |

Every cell moves less than 0.2 points: noise either way.

### Verdict against the pre-registered test

- **Primary improves: yes.** Days 0-20 are marginally better, and the live opening week goes from 15.9 to 13.5,
  level with KenPom (13.49).
- **No season worse by more than 0.02: yes.**
- **Opener plays not worse:** within noise. Two cells are 0.13 to 0.16 points lower and two are a hair higher.

**Reading.** The fix is insurance against a thin opening day, which happened for the first time this season. It is
not a historical improvement. It would go to Chad as a proposal: a stage-1 change, MODEL_FREEZE, Discord note.
Nothing changes now.

## Study B: the final model with less KenPom and Barttorvik

| Variant | Margin miss, days 0-20 / all | Total miss, days 0-20 / all | Spreads win % 15-17 / 24-26 | Totals win % 15-17 / 24-26 | Move toward us, spreads / totals 24-26 |
|---|---|---|---|---|---|
| Base (current) | 9.174 / 8.770 | 13.732 / 13.245 | 57.51 / 57.69 | 58.35 / 57.54 | 1.18 / 1.45 |
| B1, no Barttorvik | 9.175 / 8.772 | 13.731 / 13.244 | 57.42 / 57.67 | 58.36 / 57.43 | 1.15 / 1.46 |
| B2, no KenPom | 9.177 / 8.770 | 13.744 / 13.250 | 57.14 / 57.75 | 58.36 / 57.29 | 1.17 / 1.44 |
| B3, neither in stage 2 | 9.179 / 8.772 | 13.739 / 13.251 | 57.38 / 57.68 | 58.28 / **56.63** | 1.13 / 1.41 |
| B4, own preseason prior too | **9.771** / 8.965 | **13.917** / 13.290 | **53.00 / 53.41** | 57.23 / 56.00 | 0.53 / 1.22 |

**Reading, against the "no worse" test** (both average misses within 0.05, every win % within 1 point, move toward
us within 0.1):
- **B1: no worse.** Barttorvik adds nothing measurable in-season.
- **B2: no worse.** KenPom's in-season numbers add little once our own ratings have games.
- **B3: no worse, by the rule, but only just.** 2024-26 totals at the opener are 0.9 points lower (56.63 against
  57.54) with fewer units. That is the one place in-season KenPom earns its keep.
- **B4: clearly worse.** Margins early in the season miss by 0.6 points more, and spreads at the opener fall to
  about 53%. The plays nearly double (3,437 against 2,039 in 2015-17), because the model sees false edges.
  - Our own carry-over prior (last season's ratings at 60%) is much weaker than the KenPom/Barttorvik preseason
    ratings.
  - Those preseason ratings include roster information (returning minutes, transfers, recruits) that last
    season's results do not.

## What this means

1. **In-season, our own ratings already carry the model.** Removing Barttorvik changes nothing. Removing KenPom
   changes little, except a possible small loss on recent totals.
2. **The outside dependence that matters is the preseason prior**, the first weeks before teams have games.
   Replacing it needs a real roster-based preseason model (returning minutes, transfers, recruiting), not last
   season's results. That would be a separate, larger, pre-registered project.
3. **The scoring-level fix (A) is safe historically and fixes this season's opening-week totals.** It is ready to
   propose. It would apply from next season's opener, since this season is past that point.

No variant goes live from this study.
