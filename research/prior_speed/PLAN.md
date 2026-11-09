# How fast ratings leave the preseason prior (pre-registered Nov 9, 2026; Chad: "yes run it, test it and push it")

Stage 1 shrinks each team toward its preseason prior with a strength of 6 games. Variants already rerun for 2013-2026
(research/originator/d2_stage1_grid.py): prior 3 games (faster) and 12 (slower). The earlier read judged full-season
accuracy only. This read: each variant through the full model (stage 2 refit walk-forward, blowout on), judged on
**games in the first 30 days of a season** (margin and total error, both eras) and **opener plays** (spreads 2.5+,
totals 3+) in 2015-17 and 2024-26.

**Ship rule:** a variant ships only if early-season margin AND total errors are lower in both eras (2014-19, 2020-26)
AND opener win % is not lower by more than 0.3 in any market-period AND higher in at least one. Otherwise no.
