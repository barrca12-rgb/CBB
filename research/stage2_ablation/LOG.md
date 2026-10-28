# Stage-2 ablation: log

## Run 1 (Oct 28) — KenPom needed only for November-December totals (recent seasons); Barttorvik not needed

`run.py`, as pre-registered; full table in `out/run.txt` and `out/ablation.csv`. Differences vs the frozen model
(variant minus frozen; CLV in points per play, date-clustered SE in the table):

| Variant | Era | Half | d spread CLV | d total CLV | d margin MAE |
|---|---|---|---|---|---|
| (a) no KenPom | dev 2014-17 | Nov-Dec | +0.03 | -0.02 | -0.002 |
| (a) no KenPom | dev 2014-17 | Jan-Mar | -0.00 | +0.03 | -0.001 |
| (a) no KenPom | conf 2024-26 | Nov-Dec | +0.04 | **-0.24** (frozen 1.96, se 0.15) | +0.002 |
| (a) no KenPom | conf 2024-26 | Jan-Mar | +0.03 | -0.02 | +0.000 |
| (b) no Barttorvik | any | any | -0.04 to -0.00 | -0.03 to +0.01 | +0.002 to +0.006 |
| (c) neither | conf 2024-26 | Nov-Dec | +0.00 | -0.25 | +0.006 |

- Kill rule for "KenPom is needed": breached in one cell only, totals in November-December of 2024-26 (-0.24 CLV,
  about 1.5 standard errors of the frozen cell; total win % there 57.4 -> 56.8). Every other cell is inside 0.1 CLV
  and 0.02 MAE; margin MAE moves by at most 0.002 anywhere.
- Spreads: KenPom adds nothing measurable in any era or month (removing it is +0.00 to +0.04 CLV, inside noise).
- Barttorvik: inside every bound in every cell.
- Verdict: KenPom earns its place only for early-season totals in the recent era, about a quarter point of opener
  CLV in November-December; it is redundant for spreads and from January on. Barttorvik is redundant throughout.
  No live change (freeze); for the March list as a question, not a proposal.
