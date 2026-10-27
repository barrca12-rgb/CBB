# Structured miss review (research only; descriptive; nothing live changes)

## 2026-10-27: plan (written before any play was tagged)

**Question:** when the market moved against our plays, why? The aim is to see whether one cause dominates. This is
descriptive, with no pass/fail; any rule it suggests needs its own test.

**Plays:** the frozen live-like model (`audit/out/wf_live_approx.pkl`) under the frozen rule at the opener (spread
2.5+, total 3+, oriented openers, swapped records excluded).
- **Primary season:** 2025-26.
- **Check season:** 2024-25. A pattern counts only if it shows in both.

**Line value:** points the consensus close moved toward the play from the opener (as in `d_common.clv`).
- **Miss:** line value of -1.5 or worse (the market moved 1.5+ points against us).
- **Also reported:** win % at the opener.

**Tags (a play can carry several):**
- **absence, our side / other side:** a rotation player (20+ minutes a game over the team's last 5 games) did not
  play this game, for the team we bet on (spreads) or its opponent. Totals: either team. The market usually learns
  this before tip; the model does not.
- **early:** the team's first 5 games of the season (`games_before` < 5).
- **KenPom disagrees:** KenPom's own edge against the opener is on the other side or under 1 point.
- **low-major:** neither team in a high-major or mid-major conference (`d2_tiers.tiers`).
- **neutral site.**
- **big edge:** 5+ points (spreads) or 6+ (totals).

**Reported, per tag and season:** plays, share of plays, miss rate, mean line value, win % at the opener, and lift
(the tag's share among misses / its share among all plays).

**Attribution:** each miss gets one primary cause, in this order: absence (our side), absence (other side), early,
KenPom disagrees, low-major, none of these.

## 2026-10-27: results (`out/m_run.txt`, `out/m_tags_*.csv`, `out/m_plays.csv.gz`)

**Misses are rare.** The market moved 1.5+ points against the play on:
- spreads: 6.4% of plays (2025-26), 2.0% (2024-25);
- totals: 7.1%, 7.8%.

Mean line value is strongly positive: spreads +1.30 / +1.37, totals +2.18 / +1.54.

**Win % at the opener by line movement:**

| close vs opener | spreads 2024-25 | spreads 2025-26 | totals 2024-25 | totals 2025-26 |
|---|---|---|---|---|
| against 1.5+ | 50.0 (16) | 35.3 (51) | 40.9 (93) | 30.0 (100) |
| against < 1.5 | 55.4 (74) | 44.4 (63) | 47.0 (117) | 49.5 (103) |
| no move | 55.4 (202) | 53.7 (162) | 54.3 (210) | 52.6 (173) |
| for < 1.5 | 57.2 (208) | 61.8 (173) | 55.4 (260) | 54.2 (214) |
| for 1.5+ | 59.6 (302) | 63.8 (348) | 62.6 (505) | 59.3 (827) |

**No cause both dominates and repeats across the two seasons:**
- **Absence on our side:**
  - 2025-26 spreads: weaker (52.8% vs 58.0%, line value 0.87 vs 1.30);
  - 2024-25 spreads: no difference (57.3% vs 57.4%, zero misses);
  - totals: opposite directions (51.6% vs 54.9% in 2025-26; 58.7% vs 56.3% in 2024-25).
  - Not consistent.
- **Early season, totals 2025-26:** miss rate 30% (lift 4.2), line value -0.46, 47%. Not in 2024-25 (8.6%, +3.31,
  57%). This is the opening-week totals problem the live opening-week rule already addresses.
- **KenPom disagrees:** fewer misses than average in 3 of 4 cuts (lift 0.48-0.75; 1.29 in 2024-25 spreads), with
  similar win %. Disagreeing with KenPom is not what gets punished.
- **Low-major:**
  - spreads 2025-26: slightly weaker (55.7% vs 58.0%, lift 1.24);
  - spreads 2024-25: no difference;
  - totals: mixed.
- **Neutral sites:** fewer misses in 3 of 4 cuts, with good line value (consistent with the earlier neutral-site
  finding).
- **Big edges:** rarely miss.

**Reading:**
- Most losses are not plays the market saw through. They are variance on plays the market agreed with (moved
  toward).
- The model's edge shows up as line value on most plays, and the few plays the market moves hard against lose
  heavily.
- Last season gives no historical cause to target. The live miss review at Jan 15, with injury-news timing, remains
  the one place a new cause could appear.
