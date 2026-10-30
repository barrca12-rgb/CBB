# Test 2 re-run with a proper devig and a price band: plan (written Oct 30, 2026, before any number was computed)

Research only, historical. It uses the loader from tests 1-3 unchanged (`research.moneyline.test1.load`, clean
quotes). Chronological development only, date-clustered intervals (2,000 draws), and every specification is logged,
including failures.

## Why
- Test 2's outliers were 95% longshots (median +500).
- A proportional devig overstates longshot probability (the favorite-longshot bias), so those looked like value and
  were not.
- The after-the-fact slices (favorites +11% on 311 bets; near pick'em +11.5% on 428) are what that bias predicts.
  They are not findings.

## Prior
- Small positive on favorites and near pick'em.
- Zero on underdogs beyond +200.

## Seasons
- **Development:** 2021-2023.
- **Holdout:** 2024-2026, as Chad wrote it. Written now, before any number: ESPN's history carries one book per game
  in 2025 and 2026 (ESPN BET, then DraftKings). The "3+ other books" reference therefore exists only in 2024, so the
  holdout is 2024 in practice. 2025-26 are reported as "no reference possible", not as zero bets.

## 1. Devig method (chosen on 2021-23 calibration only, then frozen)
- **Methods, applied to each book's two-way moneyline:**
  - Shin's method (primary): the insider-share z solved numerically per pair;
  - the power method (robustness): k with p_home^k + p_away^k = 1;
  - proportional is reported too, for reference.
- **Calibration on all games, by price band of the side's price:** -300 or shorter, -299 to -150, -149 to +149
  (pick'em), +150 to +299, +300 or longer. Each band shows the mean devigged probability against the win rate.
  Reported for 2021-23 and, separately, for 2024.
- **Choice:** the method with the lowest 2021-23 Brier score across all sides wins, and is frozen.

## 2. Reference
For each book, the reference is the median devigged probability (frozen method) of the OTHER books quoting the game,
never the book being tested. 3+ other clean books are required.

## 3. Signal and price band
- **Signal:** the book's own devigged probability on a side is 3+ percentage points lower than the reference. The book
  is offering more than the market says the side is worth.
- **Price band:** the book's price between -200 and +200 only.
- **One bet unit:** the best signal per game and side across books (largest gap), at that book's price, 1 unit.
  Every-signal results are reported too.

## Development cells and the frozen structure
- **Reported on 2021-23:** ROI, win rate and count:
  - by side (favorite / underdog);
  - by band (-200 to -121, -120 to +120, +121 to +200);
  - by book;
  - by season.
- **Candidate structures, fixed now:**
  - all signals;
  - favorites only;
  - underdogs only;
  - band -200 to -121;
  - band -120 to +120;
  - band +121 to +200.
- **The frozen structure** is the candidate with the highest 2021-23 ROI among those with 300+ bets in every
  development season. If none qualifies, the test is closed at development.
- The holdout reports exactly that structure.

## Kill rule (holdout)
The test fails if any of these holds:
- ROI under +2%;
- the 95% interval includes 0;
- under 300 qualifying bets in a holdout season with a reference (2024).

(Chad wrote "under +2% with the interval including zero". It is read here as either condition failing, the stricter
reading, fixed now.)

## If it survives
- It is a close-side price-selection layer.
- The write-up compares it with our own close-side spread record (about 53%) on the same games, and says whether the
  two overlap.
- No live change. It goes on the Mar 14 list as a possible hand-bet layer.
