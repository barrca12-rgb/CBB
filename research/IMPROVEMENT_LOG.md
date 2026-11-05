# Improvement log

Dated findings from each review, newest first. "Nothing new" is a valid entry.

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
