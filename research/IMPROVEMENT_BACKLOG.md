# Improvement backlog

Ranked by expected gain and how soon it can be tested. Update after every weekly review. Closed items stay at the
bottom with their verdict, so nothing is retested by accident.

Last updated Nov 5, 2026 (speed read added).

## Open

| # | Idea | Evidence so far | First step |
|---|---|---|---|
| 1 | **Our own roster-based preseason ratings** (returning minutes, transfers, recruits) | v1 tested Nov 5 (research/roster_prior): closes ~half the gap to KenPom/Barttorvik (early margin miss 9.49 vs 9.17 base, 9.77 last-season-only; opener spreads ~55% vs 57.5%); does not replace them or improve the model. | v2: player development by class year, transfer level adjustment, better player values (on/off from 2023-24); each pre-registered |
| 2 | **Speed to the opener** | Measured Nov 5 (research/speed/LIVE_REPORT.md): alerts ~5 min after a book posts; 97% of numbers last 10 min, 88% 30 min, 63% 4 hours; afternoon/evening alerts decay fastest. Polling is not the bottleneck; placing the bet is. No placement times recorded (accepted.csv empty). | Record real fills (Placed button or Pikkit export); then decide on a 3-5 min opener cadence |
| 3 | **Opening-day scoring level** (stage-1 intercept shrunk toward last season) | Ready: live opening week 15.9 -> 13.5, history unchanged (own_ratings Study A) | Proposal to Chad for next season's opener |
| 4 | **Late-posted plays** (crew posted, injury, line move after the open) | 14-7 live but no line-move check possible (posted too close to tip) | Grade late plays against the close at our book and against Novig; read at Jan 15 |
| 5 | **Early underdogs where Barttorvik agrees and KenPom doesn't** | ~42% on 50 historical plays; found after the fact (early_dogs) | Pre-register on 2027 live plays; read at Jan 15 |
| 6 | **Novig as a sharp reference** | Novig prices logged since Oct 30 (lines/novig_log.csv) | Does Novig's price at our alert predict the close better than the books do? Jan 15 read |
| 7 | **Totals in November** | Games landing 2.7 under the close live; first-week overs historically. Market effect, not model skill. | Watch only; check whether the model's totals miss by date stays within backtest range |

## Closed (verdicts)

| Idea | Verdict | Where |
|---|---|---|
| Trim stakes on same-game favorite + Over pairs | No: legs nearly independent | research/correlated_pairs |
| Early underdogs need our own rating to agree | Too few to tell (our ratings agree with nearly all) | research/early_dogs |
| Less KenPom / Barttorvik in stage 2 | No worse without Barttorvik; KenPom helps recent totals slightly | research/own_ratings |
| Player-impact values for absences | No net units at the close | research/player_impact |
| Team totals | Killed | research/team_totals |
| Moneylines | No edge | research/SUMMARY.md |
| Agreement and situation filters, overreaction, matchup totals features | Closed | research/SUMMARY.md |
