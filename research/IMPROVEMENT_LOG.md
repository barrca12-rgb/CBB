# Improvement log

Dated findings from each review, newest first. "Nothing new" is a valid entry.

## 2026-11-06: duplicate alerts fixed; one-game check; absence values

- Duplicate alerts (4 plays this season): a queued card run checked out its trigger commit, not the branch tip. Fixed.
- One-game rosters are not why the 2026-27 replay shifted mismatches (gap -0.27 vs 1.5 threshold). The replay used
  the current model's stage-2 weights; the blend's own weights offset most of the shift. A fair live test needs the
  blend's own stage 2.
- Absences by learned values: margin miss slightly lower, opener spreads slightly lower. No proposal.

## 2026-11-06: roster prior v4 (different fits)

- F2 (learned box rates + v3 features) chosen on 2016-21, confirmed on 2022-26 (0.826 vs 0.816).
- Full model: the F2 blend improved early margins and recent opener results but missed its rule by 0.005 in early
  totals. No live change; proposed a live shadow.

## 2026-11-06: roster prior v3 (xRAPM-style)

- Learned box weights predict held-out 2026 lineup impact 0.53 vs Game Score 0.38.
- Team priors: correlation 0.812 -> 0.817 (gate needed 0.822): stopped. 2025-26: 0.836 vs KenPom/Barttorvik 0.841.
- Box-anchored lineup ratings added nothing. New lead: absences valued by learned weights (backlog 1b).

## 2026-11-05: totals scoring level; weekly review set up

- Totals: no historical scoring-level bias (within 0.1 point all season). Recent-miss correction cut misses by 0.01
  but cost 0.35-0.70 points of opener totals win %; smooth environment no better. No proposal.
- Weekly review: `python -m research.weekly_review`, scheduled Mondays 1:17 pm ET (first Nov 9).

## 2026-11-05: roster-based preseason ratings (v2)

- Development, transfer level and lineup values: correlation 0.805 -> 0.812, RMSE 5.00 -> 4.92. Gate needed +0.010
  or -0.10: stopped. Larger gain in 2024-26 (0.810 -> 0.823), noted after the result. Missing piece: recruits.

## 2026-11-05: roster-based preseason ratings (v1)

- Step 1: roster prior correlation with final ratings 0.805 (KenPom/Barttorvik 0.830, last season 0.754).
- Step 2: replacing the outside numbers, early margin miss 9.49 (base 9.17, last season only 9.77); opener spreads
  55.0/54.7% (base 57.5/57.7%). Blending did not beat base under the rule. No proposal; v2 ideas in the backlog.

## 2026-11-05: speed to the opener

- Alerts arrive a median 4.7 min after a book posts (10-min polling), plus 30 s processing; 77% in the first run
  that shows the number.
- Alerted numbers: 97% still up at 10 min, 88% at 30 min, 82% at 1 hour, 63% at 4 hours, 38% near tip. Noon-11 pm
  alerts decay fastest. Execution, not polling, is where the edge leaks. Placement times are not recorded yet.

## 2026-11-05 (live Nov 1-4)

- **All games:** model total miss 13.31 vs closing line 12.96; margin 10.18 vs 10.08. The gap to the close is
  smaller than in past opening weeks (0.35 vs about 0.7 on totals).
- **Plays:** official 62-47, +9.33u. Plays posted the night before beat the close by +1.86 (backtest about +1.0).
- **Underdog spreads 15-21, favorites 34-23.** Backtested (research/early_dogs): no rule would have screened them;
  likely variance. Correction: our own ratings agreed with every underdog play.
- **Same-game pairs:** nearly independent (research/correlated_pairs). Correction to the claim that favorite +
  Under pairs hedge.
- **Late-posted plays:** 14-7; they can't be judged by line movement. Added to the backlog.
