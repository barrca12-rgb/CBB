# Early-season underdog spread plays: results (pre-registered in PLAN.md, Nov 5, 2026)

Backtest only. Nothing live changes. Rerun: `python -m research.early_dogs.backtest` (output in `out/results.txt`).

## Verdict: too few to tell. No proposal.

The primary rule (V1: an early underdog play also needs our own stage-1 rating on its side) would remove almost
nothing. Our own ratings agree with nearly every early underdog play: 455 of 455 in 2014-17 and 363 of 365 in
2024-26. Live, they agreed with all 36 underdog plays Nov 1-4. The pre-registered minimum of 60 removed plays is not
met (2 removed).

**Correction to what I told Chad on Nov 5.** I said the underdog edges "mostly come from the outside ratings". That is
wrong. Our own box-score ratings sit on the underdog's side in every one of those plays too. KenPom and Barttorvik
usually agree as well, but they are not what creates the plays.

## What the data shows (days 0-20, openers at -110)

| | 2014-17 | 2024-26 |
|---|---|---|
| Favorites | 518 plays, 56.5%, move +1.33, +38.1u | 589 plays, 57.9%, move +0.97, +35.9u |
| Underdogs | 455 plays, 57.3%, move +0.89, +39.3u | 365 plays, 55.2%, move +0.54, +19.9u |

- **Early underdog plays have been profitable** in both periods. In 2024-26 they were weaker than favorites, with
  less line movement toward us (+0.54 against +0.97). That is the same shape as the live start, at a smaller gap.
- **Removing Barttorvik changes nothing** (V2). Early underdogs: 54.2% with it, 54.1% without (2024-26);
  59.0% and 59.2% (2014-17).
- **One weak cell, found after the fact:** underdogs where Barttorvik is on our side but KenPom is not went 15-23
  (2014-17) and 6-6 (2024-26), about 42% on 50 plays. That is a split I did not pre-register, so it is a lead to
  check later, not a rule. Live, only 1 or 2 underdog plays have fallen in it.

## Reading

Live underdogs are 15-21 against a history of about 55-57%. Every source agreed with those plays, and history has
no rule that would have screened them out. Most likely this is variance on a small sample, on a play type whose edge
was already a bit thinner than favorites' in 2024-26. The Jan 15 read should report underdog and favorite spread
plays separately, with their line move.
