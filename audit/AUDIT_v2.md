# Backtest audit, follow-up (Oct 26, 2026)

This revises `audit/AUDIT.md`, which is kept unchanged with its scripts and outputs. New work is in `audit/b1_*`
through `audit/b7_*`, `audit/forward_eval.py` and `audit/patches/`. The forward-test protocol is
`FORWARD_TEST_PROTOCOL.md`, fingerprinted in `MODEL_FREEZE.md`.

Every statement carries one label:
- **[V]** independently verified in this audit, from code or data;
- **[I]** audit-derived inference;
- **[H]** hypothetical sensitivity;
- **[U]** unresolved claim.

## Revised verdict

**Promising but unverified.**
- **What changed:**
  - Removing the close-based opener cleaning does not reduce the edge [V].
  - Removing Barttorvik entirely does not reduce it [V].
  - The closest historical approximation of the live card shows the same pattern [V].
  - The baselines are now controlled: same games, same information cutoff, same rule [V].
- **What remains unresolved:**
  - when historical openers were posted, and at what price [U];
  - whether any historical pick could have existed while its opener was available [U];
  - a true out-of-sample result [U].
- **Predictive validity:** promising, not established. The true out-of-sample edge is unknown, with substantial
  risk that the historical estimates are optimistic, because every evaluated season was reused in design [I].
- **Practical bettability:** unverified. Only prospective, timestamped logging can settle it (protocol sections 2
  and 5) [I].
- **Interval caveat:** date-clustered intervals account for same-day dependence. They do not correct for model and
  threshold selection across reused seasons [I].

## 1. Which model is tested

- **The forward-test subject is the live card** at the frozen commit `dfb4bc7`. Its configuration, read from code,
  is the table in `FORWARD_TEST_PROTOCOL.md` section 1 [V].
- **The audit's earlier expectations came from `safe_lag1`,** a research variant. It is not the live configuration
  [V].
- **Referee crews:**
  - **Backtest:** each historical game's actual crew comes from `data.fetch("officials")` (`context.referees`),
    supplied retrospectively [V].
  - **Live:** crews are fetched from ESPN's game page at run time (`context.live_officials`). A game with no posted
    crew gets no row and its inputs are filled with 0 in `projection.add_features` (`cbb/context.py:224-253`,
    `cbb/run_day.py:174`) [V].
  - **On the cards right now:** 0 crews posted on the Nov 1 (2 games) and Nov 2 (119 games) cards [V].
  - **Conclusion:** opener-time totals run with crew inputs at 0, and crews enter only once ESPN posts them [V].
- **No historical table is the live configuration** [V]. The closest is the live-like approximation
  (`audit/b1_live_approx.py`); its remaining differences are listed in protocol section 1 [V]. The production
  backtest, `safe_lag1`, no-Barttorvik and live-like are research comparisons only [I].

## 2. Leakage audit, completed

**Close-dependent opener cleaning removed.** No filtering or correction at all, then three selection-time,
drop-only rules fixed before any result was seen (`audit/b2_opener_cleaning.py`, `audit/out/opener_cleaning*.csv`)
[V]:

| Conservative variant, spreads vs opener | 2015-17 selections, win % | 2024-26 selections, win % |
|---|---|---|
| close-based rule (as audited) | 1,856, 56.28% | 2,262, 57.45% |
| no filtering | 1,897, 56.52% | 2,391, 58.41% |
| A: range only (+-60) | 1,897, 56.52% | 2,391, 58.41% |
| B: + favorite disagrees 5+ with market ratings (closes before D-1) | 1,879, 56.31% | 2,296, 58.26% |
| C: + 8+ from market ratings | 1,885, 56.46% | 2,305, 57.99% |
| D: + 10+ from KenPom (archive D-1) | 1,874, 56.05% | 2,335, 57.84% |

- **Totals:** totals openers were never touched by the close rule; range rule A drops 1 (2015-17) [V].
- **Exclusion counts:**
  - rule A drops 0 spread openers (2015-17: 11,586 kept; 2024-26: 17,223);
  - B drops 69 and 388;
  - C drops 42 and 237;
  - D drops 23 and 56 [V].
- **Reading:** removing the close rule raises spread line value (2024-26: 1.04 to 1.51), consistent with
  mis-oriented openers re-entering. Every selection-time rule gives 56.0-58.4% [V]. No rule is preferred for its
  returns [V]. The proposed production fix uses rule A (`audit/patches/opener_cleaning_fix.diff`) [V].

**Barttorvik removed entirely,** from the prior (KenPom-only stage 1) and from stage 2
(`audit/b3_no_barttorvik.py`) [V]:

| Conservative variant | Spreads 2015-17 | Spreads 2024-26 | Totals 2015-17 | Totals 2024-26 |
|---|---|---|---|---|
| with Barttorvik: win % [95% CI], line value | 56.28 [54.1, 58.6], 1.21 | 57.45 [55.4, 59.4], 1.04 | 57.72 [55.9, 59.6], 1.45 | 54.90 [53.3, 56.7], 1.67 |
| without Barttorvik | 56.18, 1.15 | 57.62, 0.94 | 57.69, 1.45 | 55.61, 1.67 |

All four results without Barttorvik fall inside the intervals with it [V].

**Inputs whose historical publication state cannot be verified [U]:**
- **Barttorvik time-machine files:** possibly reconstructed with a later algorithm.
- **ESPN historical openers and closes:** pulled in Oct 2026. Revisions and backfill are unknown. The 2015-17
  "Opening" source has no named book and no timestamp.
- **KenPom archive and FanMatch history:** pulled through the API in Oct 2026. They behave like as-of snapshots (a
  day's games first appear in the next day's archive [V]), but that is not proof of what was published then.
- **hoopR box scores and officials:** revisions are unknown.

A one-day lag does not prove a reconstructed file existed on that day. `safe_lag1` bounds the known timing leaks
only. It is not leakage-free [I].

## 3. Corrected counts and conventions

- **Reconciliation:** the headline 2,221 is decided selections (wins + losses). 1,283-938-8 is 2,229 selections
  including 8 pushes. Every reported "bets" count was decided selections [V].
- **ROI convention:**
  - flat 1 unit per selection;
  - pushes return the stake and stay in the denominator, and are excluded from win %;
  - voids are listed and excluded;
  - -110 is assumed throughout and labelled, because no historical spread or total price exists [V].
- **Voids and unsettled:** both are 0 in the backtest because its universe is completed games only. Postponed or
  cancelled games are absent rather than voided, which cannot be checked from stored data [U].

Full table, with intervals clustered by game date: `audit/out/consolidated_table.csv` (`audit/b7_tables.py`) [V].
Opener selections, spread 2.5+ / total 3+, ROI at an assumed -110:

| Variant | Market, seasons | Selections | W | L | P | Win % [95% CI] | ROI % [95% CI] | Line value | Same selections at close |
|---|---|---|---|---|---|---|---|---|---|
| Production backtest (as reported) | spread 15-17 | 1,981 | 1,114 | 821 | 46 | 57.57 [55.4, 59.7] | 9.7 [5.7, 13.7] | 1.26 | 53.20 |
| | spread 24-26 | 2,229 | 1,283 | 938 | 8 | 57.77 [55.8, 59.8] | 10.3 [6.5, 14.1] | 1.07 | 53.78 |
| | total 15-17 | 3,823 | 2,196 | 1,567 | 60 | 58.36 [56.6, 60.1] | 11.2 [7.8, 14.4] | 1.22 | 55.07 |
| | total 24-26 | 4,256 | 2,434 | 1,807 | 15 | 57.39 [55.8, 58.9] | 9.5 [6.6, 12.5] | 1.45 | 53.47 |
| Live-like approximation | spread 15-17 | 1,936 | 1,080 | 809 | 47 | 57.17 [55.0, 59.3] | 8.9 [4.8, 12.9] | 1.27 | 52.57 |
| | spread 24-26 | 2,217 | 1,270 | 939 | 8 | 57.49 [55.6, 59.5] | 9.7 [6.1, 13.5] | 1.07 | 53.53 |
| | total 15-17 | 3,628 | 2,068 | 1,516 | 44 | 57.70 [55.9, 59.5] | 10.0 [6.5, 13.5] | 1.39 | 54.58 |
| | total 24-26 | 3,719 | 2,060 | 1,647 | 12 | 55.57 [54.0, 57.1] | 6.1 [3.0, 8.9] | 1.67 | 50.98 |
| Conservative (safe_lag1) | spread 15-17 | 1,856 | 1,013 | 787 | 56 | 56.28 [54.1, 58.6] | 7.2 [3.1, 11.5] | 1.21 | 51.73 |
| | spread 24-26 | 2,262 | 1,295 | 959 | 8 | 57.45 [55.4, 59.4] | 9.7 [5.8, 13.4] | 1.04 | 53.68 |
| | total 15-17 | 3,046 | 1,738 | 1,273 | 35 | 57.72 [55.9, 59.6] | 10.1 [6.6, 13.6] | 1.45 | 54.57 |
| | total 24-26 | 3,149 | 1,726 | 1,418 | 5 | 54.90 [53.3, 56.7] | 4.8 [1.7, 8.2] | 1.67 | 50.52 |

Voids 0 and unsettled 0 in every row (completed games only). The referee-fix, no-Barttorvik and
no-close-rule rows are in the CSV [V].

**Labels for the original audit's main statements:**
- All reported rows reproduce exactly [V].
- Referee crews leak into totals at the open [V].
- KenPom, Barttorvik, market-rating and one-day stage-1 timing changes each move results by 0-1 point [V].
- The opener is not an executable, timestamped, priced quote [V].
- Whether picks existed while openers were up [U].
- "Most of the profit is the opening number" [I]. The same-selections-at-close numbers are [V]; the
  interpretation is [I].
- The 1-point-worse and -115 ROI figures [H].
- The 5/15/30/60-minute execution claims [U]; protocol section 5 settles them.

## 4. Baselines, controlled

`audit/b4_baselines_fair.py`, `audit/out/baselines_fair.csv` [V]. Every source uses information from before D-1.
Barttorvik gets the same home-court rule as the KenPom method (home efficiency x1.02, away x0.98). The common
universe is 36,545 games where every source exists (2015-2026), restricted to games where both teams have 10+
earlier lined games.

- **Accuracy (margin MAE / total MAE):**

| Source | Margin MAE | Total MAE |
|---|---|---|
| Final model | 8.609 | 13.130 |
| Stage-1 only | 8.632 | 13.152 |
| KenPom | 8.714 | 13.339 |
| Barttorvik | 8.746 | 13.424 |
| Market ratings | 8.838 | n/a |
| Closing line (reference) | 8.579 | 13.037 |

- **Betting, same rule and openers, on that universe:**

| Source | Spreads 2015-17 / 2024-26 | Totals 2015-17 / 2024-26 |
|---|---|---|
| Final model | 57.9% / 59.2% | 56.9% / 54.3% |
| Stage-1 only | 55.7% / 57.0% | 57.6% / 52.2% |
| KenPom | 48.8% / 50.6% | 48.9% / 48.7% |
| Barttorvik | 49.2% / 51.5% | 49.6% / 48.4% |
| Market ratings | 52.7% / 51.6% | n/a |

- **Coverage and overlap:** selection counts and overlap with the final model's selections are in the CSV. The
  cohorts differ, so this is a controlled comparison of rules on one game universe, not of identical bets.
- **Shadow benchmark:** stage-1 only stays as a frozen shadow benchmark. The live card already records `raw_margin`
  and `raw_total` per game. Forward results are never used to switch to the better variant (protocol section 6).

## 7. Power

`audit/b5_power.py` [V]:
- **Independent SE** at 600 decided signals, with break-even 52.4%: 2.04 points.
- **Separation:** a true 57% sits 2.26 SE from break-even; 55% sits 1.28 SE; 54% sits 0.78 SE.
- **Same-day dependence:** the historical design effect is 0.92-1.22 (median 0.99), so the dependence-aware SE is
  1.9-2.2 points [V]. Live clustering will be re-measured [I].
- **Reads:** 600 is the interim floor, the final read is the full regular season, and "inconclusive" is a
  predeclared outcome [V].

## Remaining evidence gaps, and what settles each

| Gap | Settled by |
|---|---|
| Whether a pick can exist while the quote is available, and after what delay | `lines/obs*/` and `bets/signal_log.csv` from the logging diff, with targeted polling (protocol section 5) |
| Price at the logged number | logged prices (`bets.csv` odds; quote log) |
| Accepted size and price | cohort C (`bets/accepted.csv`, Pikkit). Limits are never inferred from stakes |
| Out-of-sample edge | cohort A over the regular season, read per protocol section 7 |
| Historical opener timing, prices and revisions | cannot be settled. Historical results stay "promising but unverified" whatever the forward test shows |

## Production changes awaiting Chad's review

All listed in `audit/patches/README.md`, with validation:
1. **Logging and reporting** (plus a 3-minute cron-job.org job and the Odds API spend).
2. **The referee fix** (evaluation only).
3. **The opener-cleaning fix** (evaluation only).

None changes a play this week [V].
