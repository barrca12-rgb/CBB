# Input timing audit: what each alert could know, and when

Written Nov 4, 2026, at Chad's request: "Finish the timing audit across all inputs. ... Distinguish confirmed timing
from assumptions."

**Labels:**
- **[V] verified:** shown from our own logs, files or code in this audit.
- **[I] inferred:** a reading of [V] evidence.
- **[U] assumed or unknown.**

"First observed" means the first card run that had the data. It is never taken as the provider's publication time.

**Evidence sources:**
- Live first-observed times come from every committed card since Nov 1. `reports/cbb_<date>.csv` carries the
  freshness stamp, and `reports/features_<date>.csv` carries each game's KenPom, Barttorvik and stage-1 numbers.
  Both are committed every run, so `git log` dates each change to within about 10 minutes.
- Historical file semantics come from the private backup (CBB-Data): 2,147 Barttorvik time-machine files and 4,033
  KenPom API responses.

## 1. Summary

| Input | Live: which snapshot an alert uses | Date meaning | Backtest uses | Status |
|---|---|---|---|---|
| **Barttorvik** | newest non-empty time-machine file dated D-1 back to D-7 (`barttorvik.before`), else the live file | a file dated X **includes X's games**. It first appeared about 07:00 UTC on X+1 (Nov 2 file: first used 11:11 UTC Nov 3) | the same function: the D-1 file, so all games through D-1 | meaning [V]. Historical files possibly reconstructed later [U] |
| **KenPom, the card day once FanMatch is out** | FanMatch for D (`kenpom.fanmatch`), cached once non-empty | built on ratings through D-1. FanMatch for Nov 3 was first used at 07:32 UTC Nov 3 | production backtest: game-day FanMatch [V] | first-observed [V]; inputs behind FanMatch [I] |
| **KenPom, any day before FanMatch** | KenPom's *current* ratings, fetched fresh every run (`cache=False`) | **changes during the evening as games finish** (below). The DataThrough label does not mark completeness | live-like approximation: archive D-1, which is ratings through D-2 | intra-evening movement [V]; that each change is a finished game [I] |
| **Stage-1 ratings** (box scores) | hoopR schedule and box-score release, re-downloaded by the card; games before D | D-1 games entered at 11:31 UTC Nov 2 (Nov 1 games) and 12:02 UTC Nov 3 (Nov 2 games) | every game before D | [V] (two days); daily release time [U] |
| **Market context** | our own closes (`lines/closing.csv`) for completed games | moves with the box-score release (changed 12:02 UTC Nov 3) | ESPN consensus closes | [V] |
| **Injuries** | ESPN injury report, fetched every run | ESPN's own update times are not in the feed | none (the backtest has no injury report) | fetch time [V]; publication [U] |
| **Player availability** | last game's lineups from the box scores | same release as the box scores | the same, from box scores | [I] |
| **Referees** | ESPN officials, once posted near tip; 0 before | crews are absent at opener time on every card checked | retrospective crews, a known leak into totals | [V] (AUDIT_v2) |
| **Lines** | each run's pull of seven named books, with each quote's source update time | `bets/signal_log.csv` has the generating quote's source time | ESPN openers and closes, with no times | live [V]; historical [U] |
| **Preseason prior, projection weights, team HCA** | files frozen before the season (MODEL_FREEZE fingerprints) | fixed | the same files | [V] |

## 2. KenPom

**Selection logic** (`run_day.project`, `kenpom.py`):
- For a card day D on or before today, the card asks FanMatch for D.
- If FanMatch answers with rows, the card uses it. That answer is cached and never asked again.
- Otherwise (FanMatch not out yet, every future day, or an error), the card computes KenPom's margin and total from
  KenPom's current ratings. Those are fetched fresh every run and reused within the run.

**What the logs show [V].** For the Nov 6 card, the KenPom numbers changed on these runs (UTC):
- **Nov 2, daytime:** changes at 13:11, 16:33 and 19:01.
- **Nov 2-3, game night:** 37 card commits between 21:51 Nov 2 and 05:52 Nov 3 each moved all 59 games. The mean
  move per commit was up to 0.21 points of margin and 0.76 points of total.
- **Nov 3:** small moves at 07:32, 19:32, 20:13 and 22:32.

KenPom's DataThrough label read "Monday, November 2" from 13:11 UTC Nov 2 to 01:13 UTC Nov 4, the whole time.

**Reading:**
- KenPom's current ratings move many times over a game night, in step with games finishing [I].
- A play logged that evening used a part-updated KenPom state that no archive file reproduces.
- The DataThrough label does not say which games are in. `cbb/freshness.py` dates KenPom by that label, which is
  an assumption [U] that this evidence weakens.

**Archive and FanMatch history [V/U]:**
- KenPom's archive dated X behaves as ratings through X-1: a day's games first appear in the next day's archive
  (AUDIT_v2 [V]).
- The API returns these now. That they equal what was published on X is unproven [U].
- The live-like backtest's "archive D-1" is therefore ratings through D-2. Early live plays (logged the evening of
  D-1) used part of D-1's games. The production backtest's FanMatch for D used all of them.

**The gap.** The live evening state sits between the two backtests. It has never been reproducible, because KenPom
keeps no intra-day history. From Nov 4 every alert keeps it (section 5).

## 3. Barttorvik

**Selection logic** (`barttorvik.before`, used by `predict` in both live and backtest):
- the newest non-empty file dated D-1, then D-2, and so on back to D-7;
- live only: otherwise the live ratings file.

A date with no file is asked again at most hourly while within 10 days of today. A non-empty file is cached and never
fetched again.

**Date meaning [V], from two independent checks:**
1. **Live first-observed times.** The Nov 1 file was first used at 07:01 UTC Nov 2. The Nov 2 file was first used at
   11:11 UTC Nov 3.
   - When the Nov 2 file replaced the Nov 1 file, every game's Barttorvik total moved about 2.5 points, as the
     scoring level took in the 119 opening-night games.
   - Margins moved most for teams that played Nov 2: 0.35-0.43 points, against 0.08-0.11 for games where neither
     team played.
   - A file dated X is therefore posted after X's games, overnight.
2. **2025 files (CBB-Data).** Between the files dated X-1 and X, teams that played on X moved about 1.4 rating points
   (1.22-1.54 across six dates). Teams that did not play on X moved 0.19-0.80.

**Consequences:**
- The card's rule "games on D use the D-1 file" includes all of D-1's games, with nothing from D. The docstring is
  correct.
- A play logged before about 07:00 UTC on D (the evening of D-1) used the D-2 file, one day behind the backtest's
  D-1 file. `audit/a2_timing.py`'s `bt_prev` variant measures exactly that lag: 0-1 point of win rate (AUDIT_v2 [V]).

**Earlier concern withdrawn.** On Nov 4, before this audit, I said the Nov 4 card "still used the Nov 2 file at
13:30 UTC" might be a failure. It was not. That build was on Nov 3, when the Nov 3 file did not exist yet. The Nov 3
file is due about 07:00-11:00 UTC Nov 4.

**Unverified [U].** Whether the historical time-machine files are exactly what was posted on each date, or rebuilt
later with a newer method.

## 4. What an early alert knows that the backtest does or does not

For a play on game date D, logged the evening of D-1 (most plays so far):

| Input | Live early alert | Production backtest | Live-like backtest |
|---|---|---|---|
| Barttorvik | D-2 file (through D-2) | D-1 file (through D-1) | D-1 file |
| KenPom | current ratings, part of D-1 | FanMatch D (through D-1) | archive D-1 (through D-2) |
| Stage-1 | through D-2 (D-1 box scores arrive about 08:00 ET on D) | through D-1 | through D-1 |
| Referees | none | posted crews (a leak) | none |

The backtest is ahead of an early alert on Barttorvik and stage-1 by one day of games. On KenPom it is ahead
(production) or behind (live-like). The morning shadow measures what waiting for the update is worth on live data
(`research/morning_shadow/PLAN.md`).

## 5. Snapshots behind each alert (from Nov 4; `cbb/snapshots.py`)

Every logged play now gets one row per input in `bets/input_snapshots.csv`. Each row records:
- the input and its source;
- its date label (the file date, or KenPom's DataThrough or FanMatch day);
- the sha256 of the exact table;
- row count;
- where the table is stored;
- retrieval time;
- first time our system observed that exact table (`bets/snapshots/seen.csv`, written every run, alert or not);
- `provider_published_at` = unknown;
- code version (the commit) and model version.

| Input | Stored where |
|---|---|
| Barttorvik table, stage-1 ratings, injuries, referees, market context, features, the play's quotes | `bets/snapshots/<input>/<hash>.csv.gz`, once per distinct table |
| projection.json, referees.csv, teams.csv and other config | hash only; the file is in git at the recorded commit |
| hoopR box-score files | hash, last final date and download time only (public and re-downloadable, but revisable [U]) |
| KenPom FanMatch and ratings | **not in the public repo** (licensed). Kept in the runner cache `cbb/cache/snapshots/kenpom/` |

**The open item: KenPom has no permanent private copy.** The runner cache is private to the repository's workflows.
GitHub deletes cache entries unused for 7 days, and with a card run every 10 minutes the chain stays alive. Even so,
it is not an archive. A permanent copy needs a private place a workflow can write to. Two ways:
- **(a) Chad adds a write credential for the private CBB-Data repository as a CBB repository secret.** Chad creates it
  himself; I never see or ask for its value. A workflow step would then push each new KenPom table there.
- **(b) Encrypt the KenPom tables with a key derived from the existing KenPom secret** and commit the ciphertext.
  This puts licensed data, though unreadable, in the public repository. If the key changes, old copies become
  unreadable. I do not recommend it without Chad's say-so.

The prediction itself is already reproducible without KenPom's table. Each game's KenPom margin and total are in the
stored features table, and the stored features plus projection.json at the recorded commit give the model's number.

## 6. Existing safeguards: hard source failures vs uncertain timing

A code survey, file:line in the survey notes. Three findings were spot-checked against the code.

**Hard failures (a fetch failed or returned junk):**

| Input | What happens now |
|---|---|
| KenPom FanMatch | the error is swallowed; the card falls back to current ratings |
| KenPom ratings | **raises, so the whole run fails** (spot-checked: `run_day.project` calls `predict_from_ratings` outside any try). Nothing is committed or published, and no alert is sent |
| Barttorvik | 403, 5xx or a bot-check page is treated as missing; earlier files are tried, then the live file, then KenPom fills. The play is marked "unknown: no Barttorvik ratings yet". One hole: a live file with valid JSON in the wrong shape would fail the run |
| hoopR box scores | if `season_games` fails, the card **silently** fits stage-1 on the preseason prior alone, zeroes market context and uses last season's scoring level (spot-checked: the `except Exception` at `run_day.py:171`, commented "season hasn't started"). Plays are still logged and alerted, marked only "unknown". A schedule download failure fails the run |
| Injuries | a failure prints "Injury report unavailable"; the adjustment becomes 0; the stamp falls back to the last good pull (reads fresh up to 12 h) |
| Player availability, referees, market context | a failure gives 0 with no log line and no mark on the card |
| Lines | a feed failure prints and uses the other feed; both failing gives a card with no plays |

**Shared by every input:**
- **Bad-quote guards:** no price, off-market, or an edge above the maximum makes the play REVIEW, never BET.
- **A crashed run alerts nobody.** The site keeps the last card.
- **Stale-feed phone alert:** fires after 24 h, for four feeds only.
- **Nothing blocks a play.** The freshness stamp labels; it never gates.

**Uncertain timing (the fetch worked, the provider may not have updated):**
- A missing Barttorvik D-1 file falls back to D-2 with no wait.
- KenPom is used as fetched.
- A stale hoopR release reads fresh, because its stamp is the download time.
- A FanMatch answer fetched early is cached for good.

**Not tested:** a KenPom ratings crash, a hoopR failure, an injury failure, an empty availability table, referees,
market context and a failed workflow run.

**Plays that can come from a defaulted input with no mark on the card:**
- a failed availability download;
- referees;
- market context;
- teams missing from KenPom or Barttorvik (stage-1 fills, and the stamp reads fresh);
- an empty but valid injury report;
- a stale hoopR release.

**Not changed here.** A hold rule for failed sources is item 4 of Nov 4 and needs Chad's approval.

## 7. Historical odds we already own, and what historical replay lacks

| Data | Coverage | Times and prices |
|---|---|---|
| The Odds API historical snapshots (`research/market/data/quotes_*.csv.gz`) | 12 full slates, 2022-11-12 to 2026-03-07. Each covers about 17:00 UTC on D-1 to 05:00 UTC on D+1 | 9-19 books. Snapshot every 30 min (every 5 min on 2025-01-11). Prices and each book's `last_update` |
| First-half and team-total pulls (`h1_*`, `tt_lines.csv`, `data/research/h2_*`) | 576 games 2025-26 (first half), 2025-26 team totals, 510 games 2023-26 | timed and priced, but not full-game spreads or totals (h2 is closes only) |
| ESPN openers and closes (`data/lines/espn_*.csv`) | 2013-2026, every game | no times, no named book for 2015-17 openers, no prices [U] |
| Live 2026-27 (`lines/obs`, `obs_targeted`, `moves.csv`, `openers.csv`, `closing.csv`) | from Oct 26, 2026 | named books, prices and source update times [V] |

**What a historical replay of early vs morning needs, and what is missing:**
- **Odds at both decision times:** present for the 12 sample slates only, about 1,000 games. Absent for every other
  historical date. ESPN has no timestamps.
- **Ratings at the morning decision:** reproducible from the archives: KenPom archive D, Barttorvik file D-1 and box
  scores through D-1. Subject to the [U] on whether archives equal what was published.
- **Ratings at the evening decision:** **not reproducible.** KenPom's part-updated evening state was never archived
  by anyone. The nearest stand-ins are archive D-1 and Barttorvik D-2.

So the missing piece for an exact replay is the ratings snapshot, mainly KenPom's evening state. The odds are only
partly missing. A replay on the 12 slates could compare morning against a stand-in evening. It would be an
approximation, labeled as one. It is not run here. The live shadow is the exact comparison.
