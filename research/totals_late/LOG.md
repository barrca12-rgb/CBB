# Totals late-season / 2025-26: log

## Run 1 (Oct 28): structural, not broken; no adjustment clears the kill rule

`diag.py` and `candidates.py`, as pre-registered in PLAN.md. Full tables in `out/diag.txt` and `out/candidates.txt`.

### What the diagnostics show (2023-24 to 2025-26)

| | Win % vs opener | Win % vs close | Opener CLV |
|---|---|---|---|
| Nov-Dec, 2023-24 / 2024-25 / 2025-26 | 58.9 / 57.0 / 56.5 | 54.7 / 52.6 / 51.5 | 1.38 / 2.37 / 2.10 |
| Jan-Mar, 2023-24 / 2024-25 / 2025-26 | 53.3 / 55.8 / 53.6 | 50.9 / 50.8 / 47.7 | 1.02 / 1.03 / 2.24 |

1. **Late season, the close absorbs everything.** Early, our totals plays beat even the closing line (51.5-54.7%):
   the model knows something the market only partly prices by tip. From January our plays win about 50% against
   the close, so the win rate against the opener rests on line movement alone (about 1-2 points, worth roughly
   53-55%). The market's totals are sharper once teams have a season of games; ours do not get sharper as fast.
2. **2025-26 had an extra drag: more unders in a record-scoring season.** Under plays went from 41/86 (early/late)
   in 2023-24 to 360/318 in 2025-26: the model sat lower relative to the opener than before (model minus opener
   +0.3 in Jan-Mar 2025-26 vs +0.6 to +1.3 in earlier seasons). Scoring came in above model, opener and close all
   season (model minus actual -1.0 in November to -0.2 in March). Late unders won 51.6% (318 plays) and lost to the
   close (46.9%). The close itself overshot in 2025-26 Jan-Mar (47.7% vs close on all plays).
3. **Side:** late unders are weaker than late overs in every era (2014-17: 53.5 vs 58.3; 2023-26: 52.5 vs 54.9).
4. **Edge size, game type (March / conference / non-conference):** no consistent pattern.
5. **Total level (post hoc, not pre-registered):** in 2023-26 Jan-Mar, games with an opener of 150+ won about 50-52%
   on both sides (625 plays), under 140 about 57%. Not in 2014-17 (top third of totals 55.9%, bottom third 55.4%),
   so it is a hypothesis for forward data, not a finding.

### Candidates (dev 2014-17 + 2023-24, holdout 2024-25 + 2025-26)

| Candidate | Jan-Mar win % change, dev / holdout | Jan-Mar CLV change | Late plays kept | Verdict |
|---|---|---|---|---|
| (a) late threshold 4 | +0.1 / +0.7 | -0.03 / +0.40 | 75% / 49% | KILL |
| (b) two-regime totals fit | -0.1 / -0.5 | -0.03 / +0.01 | 101% / 99% | KILL |
| (c) recency weights h=2 | +0.2 / -0.1 | 0.00 / +0.01 | 102% / 107% | KILL |
| (d) late unders threshold 4 | +0.2 / **+1.2** | -0.01 / +0.02 | 93% / 84% | KILL (dev short of +1.0) |

Frozen Jan-Mar totals: dev 54.9% (+4.8% ROI, 5,759 plays), holdout 54.7% (+4.4%, 1,534).

### Verdict

Late-season totals are weaker for a structural reason (the market catches up by January; our totals edge after
that is the line movement we capture by betting early), and 2025-26 added an under-heavy year in a record-scoring
season. They are still profitable against the opener (+4.4% to +4.8% ROI at -110). No pre-registered adjustment
clears both eras, so nothing changes. Ready if needed:
- **Nearest fallback:** (d) late unders need a 4-point edge. Passed the holdout, missed dev; would need Chad's
  approval at a checkpoint and is a judgment call, not a test result.
- **Forward checks (2026-27, live):** at Jan 15 (descriptive) and the Mar 14 read, report totals by half, side and
  opener level, win % against the opener and the close. The 150+ hypothesis gets its first clean test on 2026-27
  January-March games.

## Run 2 (Oct 28): round 2 candidates (PLAN.md Part 3); all killed, recent form the one lead

`round2.py`; full table in `out/round2.txt`.

| Candidate | Jan-Mar win % change, dev / holdout | Jan-Mar CLV change | Nov-Dec win % change | Full-season win % change | Verdict |
|---|---|---|---|---|---|
| (e) drift correction, k = 1 (chosen on dev) | +1.6 / **-1.2** | +0.68 / -0.03 | +1.1 / -2.7 | +1.5 / -1.8 | KILL |
| (f) recent form (last-10 residual) | +0.6 / **+1.6** | +0.04 / +0.30 | +0.2 / -1.0 | **+0.5 / +0.5** | KILL (dev short of +1.0; holdout Nov-Dec -1.02) |
| (g) market anchor by month | -0.6 / +0.7 | -0.08 / +0.06 | 0 / 0 | -0.3 / +0.5 | KILL |
| (h) blowout term | +0.0 / -0.0 | 0.00 / 0.00 | -0.1 / -0.1 | 0.0 / 0.0 | KILL |

- **(e) drift** helps only where the model itself was biased: the dev-era walk-forward ran 2.5-4.6 points low (few
  training seasons), and the correction fixed that. In 2024-26 the model was close to unbiased, so the correction
  mostly adds noise and loses. Not a fix for a well-trained model; the January check watches the bias directly.
- **(f) recent form** is the only candidate positive in both eras on late totals and on the full season (+0.5
  win-% points each, late CLV +0.04 / +0.30). It failed the pre-registered bar (dev +0.6, needed +1.0; holdout
  November-December -1.02, limit -1.0). Lead for the March list: evaluate it on 2026-27 games at the Mar 14 read
  from the card's saved stage-2 inputs (reports/features_<date>.csv), which is fresh, out-of-sample data. That is a
  research read after the fact, not a third live shadow.
- **(g) month ratios:** the model's information beyond the close is not lower in January-February than in
  November-December in 2024-26 (ratio 1.0); it drops only in March (0.66-0.78). Late totals plays lose to the
  close because the close moves onto our opener edge, not because the model knows less in January.
- **(h) blowout term:** no effect (the 0.9-point gap in lopsided games was already captured or is noise).

**Verdict after both rounds:** eight pre-registered adjustments, none clears both eras. No change. Ready if needed:
fallback (d) late unders need a 4-point edge (holdout +1.2) and lead (f) recent form (both eras positive), both
judged on 2026-27 data at Jan 29 / Mar 14 before anything goes to Chad for approval.
