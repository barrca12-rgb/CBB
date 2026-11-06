# Improvement backlog

Ranked by expected gain and how soon it can be tested. Update after every weekly review. Closed items stay at the
bottom with their verdict, so nothing is retested by accident.

Last updated Nov 5, 2026 (speed read added).

## Open

| # | Idea | Evidence so far | First step |
|---|---|---|---|
| 1 | **Our own roster-based preseason ratings** | v1 0.805, v2 0.812, v3 (learned box weights, Nov 6) 0.817 correlation vs KenPom/Barttorvik 0.830; each step stopped at its gate. 2025-26: v3 0.836 vs 0.841. research/roster_prior | Recruit quality (needs an approved source); or a pre-registered full-model run of v3 on 2024-26 |
| 1b | **Absences valued by learned player weights** | Learned weights predict held-out lineup impact 0.53 vs Game Score 0.38 (roster_prior v3 step 0); absences today use minutes only | Pre-register: replace minutes share with learned-weight value in the absence input; backtest spreads and totals |
| 2 | **Speed to the opener** | Measured Nov 5 (research/speed/LIVE_REPORT.md): alerts ~5 min after a book posts; 97% of numbers last 10 min, 88% 30 min, 63% 4 hours; afternoon/evening alerts decay fastest. Polling is not the bottleneck; placing the bet is. No placement times recorded (accepted.csv empty). | Record real fills (Placed button or Pikkit export); then decide on a 3-5 min opener cadence |
| 3 | **Opening-day scoring level** (stage-1 intercept shrunk toward last season) | Ready: live opening week 15.9 -> 13.5, history unchanged (own_ratings Study A) | Proposal to Chad for next season's opener |
| 4 | **Late-posted plays** (crew posted, injury, line move after the open) | 14-7 live but no line-move check possible (posted too close to tip) | Grade late plays against the close at our book and against Novig; read at Jan 15 |
| 5 | **Early underdogs where Barttorvik agrees and KenPom doesn't** | ~42% on 50 historical plays; found after the fact (early_dogs) | Pre-register on 2027 live plays; read at Jan 15 |
| 6 | **Novig as a sharp reference** | Novig prices logged since Oct 30 (lines/novig_log.csv) | Does Novig's price at our alert predict the close better than the books do? Jan 15 read |
| 7 | **Totals in November** | Scoring-level tracking tested Nov 5 (research/totals_level): no historical level bias; recent-miss correction and a smooth environment both hurt opener totals. Live under-the-close run is a market effect. | Watch only; next totals idea must be game-specific (lineups, pace matchups at the opener) |

## Closed (verdicts)

| Idea | Verdict | Where |
|---|---|---|
| Totals scoring-level tracking (recent-miss correction, smooth environment) | No: hurts opener totals | research/totals_level |
| Trim stakes on same-game favorite + Over pairs | No: legs nearly independent | research/correlated_pairs |
| Early underdogs need our own rating to agree | Too few to tell (our ratings agree with nearly all) | research/early_dogs |
| Less KenPom / Barttorvik in stage 2 | No worse without Barttorvik; KenPom helps recent totals slightly | research/own_ratings |
| Player-impact values for absences | No net units at the close | research/player_impact |
| Team totals | Killed | research/team_totals |
| Moneylines | No edge | research/SUMMARY.md |
| Agreement and situation filters, overreaction, matchup totals features | Closed | research/SUMMARY.md |
