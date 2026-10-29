# Luck-adjusted outcomes for evaluating models (pre-registered Oct 29, 2026, before any expected-points value was computed)

Research only. Bets are always settled on the real score. This only changes how models are **compared** when the
comparison has to use results, for example closing-line strategies where CLV is zero by construction.

## Idea
- **The noise:** a game's result swings about 11 points around the closing spread and about 17 around the closing
  total. Part of that swing is shot-making luck: whether open threes fell, and free-throw percentage on the night.
- **The fix:** replacing made shots with their expected value given who shot and who defended keeps the real
  information (attempts, turnovers, rebounds, free-throw trips) and removes that luck.
- **The payoff:** less noise in outcomes means a real difference between forecasts shows up in fewer games.

## Expected points (`luck.py`), per team-game, from cached ESPN play-by-play (2014-2026)
**Valid games only:** the play-by-play final must equal the official final (`research/game_state` validity).

**Attempt classes:** rim (layup, dunk, tip), two-point jumper, three, free throw.

**Make probability for a class:**
p̂ = league rate + shrink(offense rate − league) + shrink(opponent-allowed rate − league).
- **What feeds it:** season-to-date rates from games before this one only.
- **Shrinkage:** k = 300 attempts for field-goal classes and 150 for free throws, as n/(n + k).
- **Free throws:** the opponent term is 0 (defenses don't affect free-throw percentage).
- **Before any games:** the league rate is the previous season's.

**Expected points** E = Σ over classes of attempts × p̂ × value. Free throws count 1 each.

**Luck-adjusted results:** margin = E_home − E_away and total = E_home + E_away.
- **Kept as they happened:** attempts, turnovers, rebounds and fouls drawn.

## Questions and pre-registered criteria
**Q1, noise:**
- **What's compared:** the SD of (result − closing line) vs the SD of (luck-adjusted result − closing line).
- **Which games:** all valid games with a close, for spreads and totals, by era: 2014-15 to 2018-19,
  2019-20 to 2022-23, 2023-24 to 2025-26.

**Q2, validity:** the luck-adjusted outcome must keep the real signal.
- **Slopes:** the beyond-close slopes of the existing forecasts are estimated with both outcomes.
  - v1 on (forecast − close);
  - the incremental slopes of v2 (spreads) and of E2 and C2 (totals) from `rescore.py`.
- **Agreement:** each pair must agree within 2 combined SEs.
- **Bias:** mean(luck-adjusted − actual) should be near 0 (reported).

**Q3, adoption rule:** luck-adjusted outcomes become the **secondary** result scoreboard in the power scorecard
only if both hold:
- the SE of v1's beyond-close slope falls by at least 20% in both markets (at least 36% fewer games needed);
- every Q2 pair agrees.

Otherwise it is not adopted. CLV stays primary for early-line strategies either way.

## Not allowed
- **No re-specification after seeing results:** not the shrinkage, the classes or the criteria.
- **No grading:** luck-adjusted outcomes never grade a bet and never feed the live model.
