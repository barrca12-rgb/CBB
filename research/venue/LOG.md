# Venue / neutral-flag check: log (Oct 31, 2026)

Reads and displays only. The flag the model uses is ESPN's and is unchanged. Code: `check.py` (research) and
`cbb/venue.py` (the live mark). Arena table: `data/home_arenas.csv`.

## Sources
- **Game venue:** ESPN scoreboard `competitions[0].venue` (id, fullName, address city and state). It was blank for 0
  of 1,250 November 2026 D-I games. History comes from the hoopR schedule (`venue_id`), which is ESPN's.
- **Arena on file:** ESPN's team venue id, from each scoreboard competitor's `team.venue.id`, else the schedule's
  `home_venue_id`. All 366 of 366 D-I teams have one (365 from the Nov 2026 scoreboard).
  - **Alternates:** any venue where a team hosted 3+ non-neutral home games in the prior three seasons; 26 teams
    have one.
- **Validity:** 98.3% of non-neutral home games in 2023-26 were at the home team's ESPN venue, and 0.6% of neutral
  games were at either team's.

## Classes
| Class | Meaning |
|---|---|
| confirmed | The flag agrees with the venue |
| conflict | The flag disagrees with the venue |
| unknown | No venue, or a team with no arena on file and a venue matching neither team |

Edge labels:
- **"home city":** a neutral game in a team's city, or a home game at another venue in the home team's own city.
- **"reversed":** the listed home team plays at the listed away team's arena.

## Results
| November | D-I games | Confirmed | Conflict | Unknown | "Home city" label |
|---|---|---|---|---|---|
| 2026 (Oct 31 pull) | 1,250 | 1,248 | **2 (0.2%)** | 0 | 8 |
| 2025 | 1,246 | 1,239 | 7 (0.6%) | 0 | 17 |
| 2024 | 1,213 | 1,204 | 9 (0.7%) | 0 | 10 |
| 2023 | 1,122 | 1,118 | 4 (0.4%) | 0 | 8 |

**November 2026 conflicts:**
- **Nov 2, Winthrop at Queens, flagged neutral:** played at Rock Hill Sports & Event Center, Winthrop's arena (Field
  of 68 Opening Day Marathon). So Winthrop is really at home.
- **Nov 14, LSU at Gonzaga, flagged home:** played at Spokane Numerica Veterans Arena, Spokane (Bad Boy Mowers
  Series). That's Gonzaga's city but not its arena, so it carries the "home city" label.

## Calibration: do conflicts cost money? (`out/nov_conflicts_rescored.csv`)
**Method:** the frozen live-like forecasts were re-scored with the venue-corrected flag:
- every flag-dependent input was recomputed with the model's own formulas;
- the walk-forward stage-2 coefficients were then applied to the changes.

**Correction checks:** the stage-1 recompute matches the frame within 0.3 points on average (max 1.3). The change
uses only the refit's home-court term and possessions. The market term matches exactly.

| Conflict games | Correction (mean) | Residual in the correction's direction | Abs error: given / corrected | Opener, model side: given / corrected |
|---|---|---|---|---|
| Nov 2025 (7) | −3.29 | −3.18 (SE 4.51) | 8.86 / 10.01 | 57.1% / 57.1% |
| Nov 2024 (9) | −4.15 | −0.74 (SE 4.38) | 9.44 / 9.15 | 44.4% / 55.6% |
| Nov 2023 (4) | −2.05 | −1.38 (SE 3.25) | 4.40 / 5.07 | 75.0% / 50.0% |
| **Pooled (20)** | −3.43 | **−1.72 (SE 2.51)** | 8.23 / 8.63 | 55.0% / 55.0% |

- **The given flag did slightly better on these games.** Neither trigger fires: November 2026 conflicts are 0.2%
  (bar about 2%), and the residual runs the wrong way (bar +1.5 in the correction's direction).
- **So there is no data-fix diff,** and the model's flag stays as ESPN gives it. Chad decides play by play from the
  mark.
- **Why:** 11 of the 20 are home games at another venue in the home team's own city (old gyms, downtown arenas).
  There the home flag is effectively right. The other 9 are too few to read.

## The mark (live)
- **Card:** "Venue ✓ / conflict / ?" on every play and band B play. Hovering shows the venue, city, reason and the
  flag the model used. A conflict adds a warning line under the play.
- **Phone alert:** a "Venue: …" line.
- **Discord:** a Venue field.
- **Cache:** `reports/venue_<date>.csv`, refreshed at most every 3 hours.
- **v1 unchanged:** the card CSV, the bet log and every v1 field are byte-identical with the mark on and off
  (`audit/test_venue.py`).
