# Sharp opener, step 1 (Nov 9, 2026): is a sharper number up when our plays go out?

- Pinnacle: up before 21 of 102 plays since Nov 6; those had worse Pinnacle CLV (REPORT.md).
- Kalshi: a market up at posting for 17% of 283 plays since Oct 30. Too sparse.
- Novig: up for 63 of 249 settled plays. With Novig up and our number about 3 points better than Novig's: 22-31,
  -10.8u flat, Pinnacle CLV -2.15%, 36% beat the close. With no Novig line yet: 98-86, +2.9u, CLV +3.67%, 51%.
  When a sharper market is already up and still disagrees with us, the model is usually the one that is wrong.
- BetOnline (an early, sharper book) now logged in the card call's free 10th slot (lines/betonline_log.csv) to
  measure how often it is up before our plays. Step 2 (historical openers, about 2,000-4,000 credits) only if it is.

## Correction (Nov 10, 2026)

The Novig numbers above included empty exchange quotes: with no money on a game, Novig's feed lists a ladder rung at
a fake line priced around -9900 (e.g. a 131.5 total with the market at 152.5). The "about 3 points better than
Novig" groups were partly built on those. With them dropped (both sides within +/-200), the finding still holds, but
the split is different: with a real sharp line up (Novig, Pinnacle or BetOnline) and the model still 2+ points off
it, main plays are **30-38, -10.2u flat, Pinnacle CLV -3.6%, 28% beat the close**; all other main plays are 138-110,
+15.2u flat, CLV +3.0%. Shadow set up in research/sharp_shadow/PLAN.md.
