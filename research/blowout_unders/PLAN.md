# Unders in big mismatches (pre-registered Nov 7, 2026, before any result)

**Question (Chad, Nov 7, after Friday's 11-17-1 Unders):** do the model's Under plays lose when a big favorite
plays a small school? Friday's worst Unders were blowouts: UNC 109-70, BYU 108-67, Oklahoma State 118-68,
Alabama 101-86.

**Data:** the walk-forward backtest frame (`audit.common.frame`, production inputs), seasons with opening lines:
2015-2017 and 2024-2026. Plays exactly as the opener backtest makes them: total edge 3+ points against the opening
total, graded at that number (`audit.common.bets`). Spread size = |opening spread| (known when the play is posted),
the closing spread where there is no opener.

**Groups:** |spread| under 10, 10-15, 15-20, 20 or more.

**Read for each group, each period:** Under plays (and Overs for comparison): count, win %, ROI at -110, mean move
of the total toward us by the close. All games: actual total minus closing total (market bias), actual total minus
the model's total (model bias). Also November-only.

**Decision rule (fixed now):** propose a change only if Unders with |spread| 15+ win under 50% in **both**
periods, **and** below the Unders under 15 in both, **and** the close does not move toward us on them (mean
move <= 0). Then the change tested is: no Under plays at |spread| 15+, or a model total adjustment by spread size,
scored on all-games total accuracy and opener win %. Anything short of that is recorded as "no" in the backlog.
