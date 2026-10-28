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
