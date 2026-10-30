# The 3-4 totals band on live-like inputs: result (Oct 31, 2026)

Plan: `PLAN.md`, written before this run. It discloses that the 3-3.5 numbers were seen on Oct 30. Code: `run.py`;
output: `out/run.txt`, `out/bands.csv`, `out/leak.csv`. Research only. Nothing live changed and no tag was added.

## Verdict: 3-3.49 is supported. The Oct 26 decision stands on live-like evidence.
- **Kill rule (fails only if win % ≤ 53.0 in both eras, or pooled opener CLV < +0.3):** win % was 55.5 in 2014-17
  and 53.6 in 2024-26. Pooled CLV was +1.01. Neither condition holds.
- **Not tagged:** 3.0-3.49 plays are not tagged `t3`.
- **The weak cell:** 2024-26, where 3-3.49 won 53.6% ±3.0 (+2.3% ROI at −110) and overs alone 52.9% (752 plays).
  The Nov 16 read splits live totals into 3-3.49 / 3.5-3.99 / 4+ (scheduled).

## Live-like bands (ESPN opener, live opening-week rule, swapped records out; ± is a date-clustered 95% interval)
| Band | 2014-17: win %, ROI, CLV (plays) | 2024-26: win %, ROI, CLV (plays) |
|---|---|---|
| 3-3.49 | 55.5% ±3.7, +5.9%, +0.87 (779) | 53.6% ±3.0, +2.3%, +1.12 (1,060) |
| 3.5-3.99 | 56.3% ±3.8, +7.5%, +1.00 (676) | 57.4% ±3.5, +9.7%, +1.38 (776) |
| 4-4.99 | 56.3% ±3.2, +7.5%, +1.16 (929) | 55.2% ±3.0, +5.3%, +1.63 (989) |
| 5+ | 60.6% ±3.5, +15.8%, +1.87 (1,244) | 57.8% ±3.4, +10.3%, +2.70 (820) |

By side, 2024-26:
- 3-3.49: overs 52.9% (752), unders 55.4% (308).
- 3.5-3.99: overs 59.1% (593), unders 51.9% (183).

The full side split is in `out/run.txt`.

## The leak, per band (production frame minus live-like, win-rate points)
| Band | 2014-17 | 2024-26 |
|---|---|---|
| 3-3.49 | +3.4 | +1.2 |
| 3.5-3.99 | +2.8 | −2.3 |
| 4-4.99 | −0.3 | +2.7 |
| 5+ | −1.3 | +3.6 |

- **CLV:** the production frame's CLV is never higher (leak 0 to −0.5). The leak shows in results, not in the line
  move.
- **Check against the Oct 26 table:** this production frame gives 3-4 overs 55.7% (1,931) and unders 57.8% (1,499).
  The table had 56.2% (1,860) and 54.8% (1,561). So this frame approximates the Oct 26 one rather than reproducing it
  exactly. Its 3-4 pooled is 56.6% against 55.5% live-like, about 1.1 points of leak.
- **The table's own 3-4 numbers** (about 55.6% pooled) are close to the live-like 55.5%. The leak mainly inflated
  the 2-3 band, which is band B's question.

## Recorded DraftKings prices (first-observed quotes, 3 dates a season), after the +2% EV rule
| Season | 3-3.49 | 3.5-3.99 | 4-4.99 | 5+ |
|---|---|---|---|---|
| 2025-26 | 20 of 24 pass, 9-11, −2.76 u | 7 of 7, 5-2, +2.56 u | 17 of 17, 13-4, +7.88 u | 20 of 20, 11-9, +0.89 u |
| 2024-25 | 30 of 30, 17-13, +2.64 u | 13 of 13, 6-7, −1.52 u | 17 of 17, 11-6, +4.05 u | 10 of 10, 5-5, −0.53 u |

Median prices run −110 to −112. There are too few plays to read a win rate; the table shows the EV rule keeps
nearly every 3+ edge at real prices.
