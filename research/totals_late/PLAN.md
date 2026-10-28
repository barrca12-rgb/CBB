# Totals: why weaker in 2025-26 and from January (pre-registered Oct 28, 2026)

Chad's question (Oct 28): totals won 54.9% in 2025-26 (vs 55.6-56.3% the two seasons before) and 54.3% in
January-March (vs 57.4% in November-December) over 2023-24 to 2025-26, while opener CLV on totals was the highest
in 2025-26 (+2.18). Find out why, and have an adjustment tested and ready if one is warranted. Research only: no
live change (freeze; any adoption goes through a checkpoint with Chad's approval, a backtest, a MODEL_FREEZE entry
and a Discord note).

**Benchmark:** the frozen live-like stage 2 (`research/originator/d_common`: `frames()`, `walk_forward()`,
`oriented_openers()`), the frozen totals rule (edge 3+ against the consensus opener, one bet per game, -110), the
same plays as the Oct 28 backtest table. Halves: November-December vs January-April.

## Part 1. Diagnostics (descriptive; no kill rule)

All by season (2014-17 dev era and 2023-24, 2024-25, 2025-26) and half:
1. **Side:** overs vs unders: plays, win %, CLV.
2. **Bias:** mean (model total - actual), (opener - actual), (close - actual) by season and month.
3. **CLV vs result:** for the plays, win % against the opener, win % against the close (did the close itself
   cover in our direction), and the share of the opener edge the close took. If CLV is large but results do not
   follow, the close is overshooting or the late market is sharper than the early one.
4. **Edge size:** 3-4, 4-6, 6+.
5. **Game type:** conference vs non-conference, March (conference tournaments) vs January-February, total level
   (opener under 140 / 140-150 / 150+).
6. **Within-season drift:** mean (actual - model) by month in each recent season (does the model lag rising scoring
   late in the season?).

## Part 2. Candidate adjustments (each pre-registered; chosen on dev, confirmed on holdout)

- **(a) Late-season totals threshold 4** (January on), early stays 3.
- **(b) Two-regime totals fit:** separate stage-2 totals fits for November-December and January on (spreads
  unchanged). Earlier D1 tested regimes on combined CLV only.
- **(c) Season-recency weights for the totals fit** (h = 2 seasons), spreads unchanged.
- **(d) Side rule:** only if diagnostic 1 shows a side difference in both the dev era and 2024-26, the weaker
  side gets threshold 4 from January.

**Scoring:** January-April totals opener CLV (date-clustered SE), win % and ROI at -110, plays; November-December
reported to make sure it is not hurt.

**Dev / holdout:** choose on 2014-17 + 2024 (2023-24); confirm on 2025 + 2026.

**Kill rule (per candidate):** killed unless, in BOTH dev and holdout, January-April totals win % improves by 1.0
point or more AND opener CLV is not worse by 0.1 or more AND November-December totals are not worse by 0.1 CLV or
1.0 win-% point. A threshold candidate (a, d) also has to keep at least 60% of the late plays. A survivor is written
up for the Jan 15 checkpoint (it can only go live with Chad's approval); otherwise the verdict is "no change, here
is why".

**Prior:** moderate that diagnostics find a structural cause (late-season market sharper, or the model lagging
rising scoring); low that a candidate clears both eras (late-season totals still win 53-54%, above break-even).
