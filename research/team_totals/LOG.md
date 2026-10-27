# Team totals (research only; nothing live changes)

## Background

- **Proxy result:** an earlier proxy test (team total = (closing total ± closing spread) / 2) won 55.5% at a 3+ point
  model edge, 2023-2026.
- **Real lines:** pulled Oct 26 (`cbb/research_team_totals.py`, `data/research/tt_lines.csv`): the books' team-total
  lines and prices about 45 minutes before tip. The games were the 1,334 games of 2025-26 where the model's edge
  against the proxy was 2.5+ (`data/research/tt_candidates.csv`).
- **Coverage:** DraftKings, FanDuel and Caesars. BetMGM is nearly absent.
- **Not yet done:** the real lines have not been graded.

## 2026-10-27: pre-registration (written before any real line was graded)

**Model team totals** (frozen live-like model, `audit/out/wf_live_approx.pkl`):
- home = (final_total + final_margin) / 2;
- away = (final_total - final_margin) / 2.

**Line:** per game and team, the first of DraftKings, FanDuel, Caesars that quotes it. Graded at that book's
number and price. Swapped records (`evaluate.swapped`) are excluded.

**Plays:** model - line, 3.0+ points for the over or 3.0- for the under (the proxy test's threshold). One play per
team, so a game can give two.

**Decisive:** ROI at the actual price, with a game-level bootstrap 95% interval.
- **PASS** (candidate for a forward team-total shadow log, not betting): the interval's lower bound is above 0.
- **PROMISING** (forward shadow log only): ROI above 0 but the interval includes 0.
- **KILL:** ROI at or below 0.

**Descriptive:**
- thresholds 2.5 / 3.0 / 4.0 / 5.0;
- the best of the three books;
- overs vs unders;
- win% vs break-even at the average price;
- book hold;
- real line vs proxy (the books' shading);
- by month.

**Caveat:** the candidates were chosen by the model's edge against the proxy, so plays below 2.5 are incomplete and
the sample is all 2025-26 (one season).

## 2026-10-27: results (`out/t_run.txt`, `out/t_ladder.csv`, `out/t_by_month.csv`, `out/t_plays.csv`): KILL

- **Sample:** 2,072 team lines graded (1,036 games). Hold: Caesars 4.95%, FanDuel 5.75%, DraftKings 6.92%.
- **Real lines vs the proxy:** the books barely shade: mean -0.01 points, mean absolute 0.53.
- **Accuracy:** model MAE 8.36, line MAE 8.08. The line is more accurate.
- **At 3.0+:** 566 plays, 48.2% won against a 53.7% break-even. ROI -10.2% [-18.5, -2.2]. Best of three books -8.4%.
- **Every threshold, overs and unders, is negative:**
  - 2.5: -10.2%;
  - 4.0: -12.3%;
  - 5.0: -13.2%.
- **By month:** every month is negative.
- **Why the proxy's 55.5% did not hold (exploratory, after the result):** graded at the proxy number, the same 566
  plays win 47.9%, and plays with 3+ against the proxy win 49.0% (468). So in 2025-26 the proxy edge itself was
  gone. It is not the real lines or prices. The 55.5% came from the earlier seasons of the 2023-26 window.
