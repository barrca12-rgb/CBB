# Improvement backlog

Ranked by expected gain and how soon it can be tested. Update after every weekly review. Closed items stay at the
bottom with their verdict, so nothing is retested by accident.

Last updated Nov 5, 2026.

## Open

| # | Idea | Evidence so far | First step |
|---|---|---|---|
| 1 | **Our own roster-based preseason ratings** (returning minutes, transfers, recruits) | Last season's results alone are a much weaker prior: opener spreads ~53% vs 57.5% (own_ratings B4). November-December plays lean on outside preseason numbers. | Inventory free roster data (CBBD players and stints from 2023-24, rosters, transfer lists); pre-register a prior built from returning minutes x player value |
| 2 | **Speed to the opener** | The edge lives at the opener: ~60% at the opener vs ~52% at the close; first book to post 58.5% vs later books 54.4% (research/SUMMARY.md). Live: plays posted 18h+ before tip beat the close by +1.86, later ones by about 0. | Measure live minutes from a book's first quote to our alert for every play; find gaps in the poll schedule around when openers post |
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
