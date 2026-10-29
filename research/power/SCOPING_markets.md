# Scoping: more independent betting opportunities (research only, Oct 29 2026)

Nothing in cbb/, bets/, .github/, MODEL_FREEZE.md or any live/shadow file was touched. No commits, no paid calls, no
sign-ups. Only unauthenticated GETs: 4 HEAD/GET checks of GitHub release assets (plus downloads of women's files into the
scratchpad), ~300 ESPN core-API odds GETs (women's sampling), and one attempt at the-odds-api.com docs.
V = verified by file/request in this environment. A = assumption / outside knowledge.

## Bottom line
| Option | Rating | Main blocker |
|---|---|---|
| 1. Early (opener) totals, men's D-I | ALREADY LIVE; no new games | Same games as the spread card, so no independence gain. Expansion room is only a lower threshold, which the data does not support |
| 2. First-half spreads/totals, men's D-I | LOW (already tested and killed on Oct 27) | No edge: 0 of 2 markets passed; hold ~7% vs 4.8% |
| 3. Women's D-I (NCAAW) | MEDIUM-LOW for modelling, LOW for betting | Historical lines sparse (~10-25% of games 2025-26 at a real US book) and thin liquidity; no timestamps |

Honest framing: none of the three adds many independent bets soon. Women's is the only one that is genuinely new
volume, and it is also the only one with no line history, no tested edge, and the weakest market.

## 1. Opener totals, men's D-I
(a) Results/box/PBP: V. hoopR schedule + team_box + player_box 2013-2026, PBP 2014-2026 (cbb/cache; cbb/data.py).
(b) Historical lines: V. ESPN core odds feed via cbb/lines_hist.py, data/lines/espn_<season>.csv. ESPN carries
    no timestamps for openers, it only labels "open" vs "close" per book. Per season, games with an opening total
    (research/quant/out/frames.pkl `open_total`, after cbb.lines_hist.consensus; total games that season in brackets):
    - 2013: 0 [5,460]; 2014: 3,766 [5,496]; 2015: 3,162 [5,498]; 2016: 3,956 [5,461]; 2017: 3,674 [5,486]
      (2014-17 comes from ESPN's "Opening" pseudo-book; raw 3,816 in 2017 before orientation/cleaning)
    - 2018-2023: 0 for every season (ESPN stored only closes, 8-13 books)
    - 2024: 5,721 [5,723]; 2025: 5,757 [5,759]; 2026: 5,749 [5,752] (open/close from one book: ESPN BET, then DraftKings)
    So openers exist for 7 of 13 seasons. A 2018-2023 gap of six seasons is not fillable from ESPN.
    Odds API history (research/market/data, quotes_<date>.csv.gz, 12 sampled Saturdays 2022-11 to 2026-03, spreads and
    totals, ~12 books, snapshot timestamps every 30 min): V. Useful to verify opener quality (research/market), not
    to build a season-scale frame (~300-600 games/date; a full pull is the paid 20 credits/game-moment).
(c) Live lines going forward: V. lines/openers.csv, closing.csv, moves.csv are written by the live job (The Odds
    API plus SGO; last_pull.txt shows 35 book-game rows on Oct 29 and 57,694 Odds API credits left).
    First-seen timestamps for openers are recorded live, so the forward record is timestamped; the history is not.
Count of bettable games: the model already bets totals at edge 3+ vs the opener (cbb/run_day.py docstring).
    research/quant/LOG.md: 3,706 plays at the 3-point threshold across 2024-26 (about 1,235/season, ~56% win).
    Dropping to a 2-3 pt WATCH band is already a card tier.
Licensing: ESPN's undocumented core API, used with a plain UA; terms are not an open license. A: personal research
    use, no redistribution.
Rating: ALREADY LIVE. Independence note: totals residuals are on the same games as spreads, so a total bet adds
    some diversification (spread and total errors are only weakly correlated; A, not measured here) but not new games.
Main blocker: nothing to build. The notable open question is late-season totals (research/totals_late), where the
    close absorbs the edge; that is a different problem from coverage.

## 2. First-half spreads and totals, men's D-I
This was already investigated and closed in this repo on Oct 27 (research/market/LOG.md lines 171-280).
(a) Results: V. cbb/cache/pbp/play_by_play_<season>.parquet has period_number, home_score, away_score. 1H results are
    computable: game counts with a period-1 row vs games in the file: 2014 5,084/5,084, 2015 5,280, 2016 5,390,
    2017 5,479, 2018 5,645, 2019 5,474, 2020 5,394, 2021 4,015, 2022 5,830, 2023 6,116, 2024 6,151, 2025 6,136,
    2026 6,275 (all games in the file have period 1; period 2 is missing for 0-26 games per season). So: YES,
    near-complete coverage 2014-2026. The h1 test already used "score at the last play of period 1".
    (Caveat A: score at last period-1 play is assumed equal to the halftime score; not audited game by game.)
(b) Historical 1H lines: ESPN odds feed fields in lines_hist.py: NONE (it reads only homeTeamOdds/open/close for the
    full game; no 1H fields are parsed; I did not audit the raw feed for 1H keys, so ESPN having none is unverified). The Odds API has
    spreads_h1 and totals_h1 keys, but only in historical event odds from ~2023 (V: pulled in this repo; docs host
    the-odds-api.com returned a proxy 403, so I did not re-read the docs and did not try to bypass it).
    Repo already holds: research/market/data/h1_a_lines.csv (14,304 rows, 576 games on 5 dates in 2025-26, one
    snapshot at tip-15 min, DraftKings/FanDuel/BetMGM 20/20 coverage) and h1_pilot_*.csv.
(c) Live: coverage near tip was complete for DK/FD/MGM in the pilot (V from LOG.md); mornings 18/20 games, with
    low-majors missing. Live collection would use The Odds API (paid credits per call).
Games per season: all ~5,700 games have a 1H; lines exist for roughly all D-I games at tip in 2025-26.
Result (V, LOG.md): both markets KILL. Beyond-the-line coef spreads 0.29 [-0.82, 1.40], totals 0.07 [-0.21, 0.35];
    plays at the pre-registered thresholds: spreads 61 plays, 49.2%, ROI -8.7%; totals 108 plays, 50.0%, ROI -6.8%.
    Ladder negative at every threshold. Hold ~7% (DK, BetMGM) vs 4.8% on a -110 full game.
Not tested: early 1H lines (game-day morning); needs ~11,700 more credits, which would go below the 50k floor.
Licensing: Odds API paid plan terms apply to the pulled lines; the repo holds what it already paid for.
Rating: LOW. Blocker: no demonstrated edge, and the 1H market is derived from the same game forecast, so it would
    add correlated, not independent, bets even if lines were soft.

## 3. Women's D-I (NCAAW)
(a) Results/box/PBP: V. Same sportsdataverse-data release repo, analogous asset names, all reachable (HTTP 200 on
    each; downloaded to scratchpad). Patterns:
    espn_womens_college_basketball_schedules/wbb_schedule_{season}.parquet
    espn_womens_college_basketball_team_boxscores/team_box_{season}.parquet
    espn_womens_college_basketball_pbp/play_by_play_{season}.parquet  (player boxes not tested; A: same naming)
    Men's FILES use the mbb_ / mens_ names, so cbb/data.py would need a second FILES table (not changed).
    Completed games / D-I vs D-I (teams with a conference; same filter as cbb/data.py), schedule files:
    2015 5,603 / 5,356; 2020 5,434 / 5,172; 2024 5,908 / 5,540; 2025 5,634 / 5,289; 2026 6,030 / 5,625.
    Team box 2025: 5,626 games; PBP 2025: 1.97M rows, 5,473 games, has period_number/home_score/away_score.
    Seasons available: earlier than 2015 not checked (A: back to ~2003 per sportsdataverse docs).
(b) Historical lines: V (one sample per season, random 60 completed games each, women's endpoint
    womens-college-basketball/events/<id>/competitions/<id>/odds, same URL pattern as lines_hist.py):
    - 2022: 15/60 had a line at a real sportsbook (DraftKings, Caesars, SugarHouse, Unibet), 0 with open totals
    - 2024: 30/60 (mostly BetfairSportsbook, ESPN BET 18, Caesars, Unibet); 29 with open totals
    - 2025: 11/60 (ESPN BET only), all with open totals
    - 2026: 8/60 (DraftKings 7, ESPN BET 1), all with open totals
    - 2019/2023 25-game checks: 2019 1/25 (Unibet), 2023 23/25 but only via Betfair/accuscore and few US books.
    Compare men's: ~100% coverage 2019-2026. Women's is roughly 13-18% of games in the last two seasons, i.e. a few
    hundred to ~1,000 games a season at a US book (extrapolated from 60-game samples; wide error, +/- ~10 pts).
    No timestamps (same open/close fields as men's). Sampling error large: treat percentages as order-of-magnitude.
    Odds API historical for women's (sport key basketball_wncaab, A, from memory): a paid pull; not tried.
(c) Live lines: A. The Odds API lists NCAAW; coverage mostly on DK/FD/BetMGM for ranked/power-conference games and
    March; many regular-season games have no US line. SGO coverage not tested. Not checked: Kalshi/other exchanges.
Games per season: ~5,300-5,600 D-I games; bettable (with a US book line) ~700-1,000 (see above).
Liquidity concerns (A, standard for NCAAW): limits are lower than men's (often a few hundred dollars), lines are
    posted late and move on injury news, books shade for sharp action, and late-season/ tournament games dominate
    the volume. Hold on women's totals is typically at least that of men's (not measured).
Licensing: same as men's. sportsdataverse data is an ESPN scrape (released under the repo's MIT code license; data
    terms follow ESPN). Odds API paid terms for any pull.
Modelling effort (A): reuse the ridge-rating machinery on women's team_box (the structure is the same: schedule,
    team box, possessions). Needs a women's-specific preseason prior (no KenPom; Barttorvik has no women's
    equivalent; some analog like Her Hoop Stats / NCAA NET would be needed, unchecked), women's rules (four 10-minute
    quarters, not two halves) so a "1H" analog differs, and a new walk-forward calibration. Roughly one new model,
    not a config change.
Rating: MEDIUM-LOW (data for results is free and reachable; lines coverage and liquidity are the hard part).
Main blocker: historical lines for ~85% of games are missing, so the edge cannot be backtested at scale
    (2024-26 gives ~2,000-3,000 lines in total). A forward-only shadow log (collect lines from now, using existing
    Odds API calls) is the only affordable way to start.

## Recommendation (facts first, opinion last)
- Option 2 does not need more work; it was killed with a pre-registered test. Do not re-pull.
- Option 1 is already in the card. The one lever is the 2018-2023 opener gap (not recoverable from ESPN) and the
  timestamped Odds API snapshots, which are paid.
- Option 3 is the only new-volume candidate. Cheapest next step (my suggestion, nothing started): download women's
  schedule/team_box for 2015-2026 (free), build ratings, and record women's open/close totals and spreads from the
  free ESPN feed daily this season as a shadow log. That decides whether the 2024-26 line history is enough.

## What I did NOT verify
- Women's player_box file names, seasons before 2015, women's Odds API coverage and pricing, women's liquidity/limits.
- Whether a 1H line appears anywhere in the ESPN feed beyond the keys read by lines_hist.py.
- Any women's model quality; any claim about limits or hold at women's books.
