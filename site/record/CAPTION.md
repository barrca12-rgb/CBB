# Weekly X caption: the one fixed template

Filled by `cbb/record_chart.py` every Monday into `site/record/weekly/<date>-caption.txt`, from the same numbers as
the chart. Chad copies it with the image. No adjectives, no streaks, no individual results; the template changes only
with a dated note in MODEL_FREEZE.md.

```
Week {N}, through Sun {Mon D}.
Plays logged: {plays}. Record: {W}-{L}-{P}. Units (flat 1u): {units}.
CLV spreads: {clv_spreads} pts (close for {n_spreads} of {decided_spreads} decided). CLV totals: {clv_totals} pts (close for {n_totals} of {decided_totals} decided).
Every play alerted and timestamped before tip. Record and verification: https://barrca12-rgb.github.io/CBB/record.html
```

- **Week N:** the week ending that Sunday, counting the week of the first logged play (ending Sun Nov 1) as Week 1.
- **Plays logged:** every non-void play dated on or before that Sunday (cohort A, bet or not).
- **Record and units:** settled plays; units at a flat 1 unit, pushes returned.
- **CLV:** mean points per play against the forward-test primary close (`cbb/clv_primary.py`), per market, over decided
  plays that have a primary close; "close for n of N decided" is the coverage (changed Oct 28, recorded in
  MODEL_FREEZE.md). Plays without a primary close are counted, never treated as zero. "–" when n is 0.
