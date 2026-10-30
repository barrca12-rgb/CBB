# The flipped idea: bet the spread when a book's own moneyline disagrees. Plan (written Oct 30, 2026, before any number was computed)

Research only, historical. It uses the loader from tests 1-3 unchanged (`research.moneyline.test1.load`, clean
quotes) and the frozen 2014-17 spread-to-win conversion from test 1 (P(home wins) = Phi((-s + 0.092 x home_site) /
10.422)), which is not re-fit. Chronological development only, date-clustered intervals (2,000 draws), and every
specification is logged.

## Why
Test 1 showed that when a book's moneyline and spread disagree at the close, the moneyline is the better predictor. So
the margin implied by the moneyline, minus the book's spread, is a signal on the spread with a known direction.

## Prior
Low to moderate. Derivative markets at the same book are usually kept consistent, so gaps of 1+ point will be rare and
may be stale-spread moments.

## Seasons
Development 2018-2021, holdout 2022-2026. 2025-26 have one book per game; this test is within one book, so they count.

## 1. Implied margin
- **Devig:** Shin's method on the book's own pair gives p_home.
- **Inversion:** implied home spread = 0.092 x home_site - 10.422 x Phi^-1(p_home).
- **Noise floor, reported on 2014-17:** the inversion's mean absolute gap between implied spread and the book's
  spread, and its median.

## 2. Gap
- gap = the book's spread minus the implied spread, both in home-spread terms, on the same book at the same (last
  pre-tip) quote.
- A positive gap means the moneyline rates the home team stronger than the spread does, so the bet is the home side.
- **Reported:** the distribution by season and by book, and the share of quotes with |gap| of 0.5+, 1+ and 2+.

## 3. Rule
- **Bet:** with |gap| of 1+, the spread side the moneyline favors, at that book's spread.
- **Price:** ESPN's history has no spread prices, so -110 is assumed throughout. Written now: "recorded prices" in
  Chad's brief is read as -110.
- **One bet per game:** the quote with the largest |gap|.
- **Development cells:** win rate, ROI and count:
  - by gap size (1-2, 2+);
  - by favorite / underdog (the bet side's spread sign);
  - by book;
  - by season.
- **Robustness:** gap thresholds of 0.5 and 1.5.
- Pushes are out of win rates and count as 0 units.

## 4. Beyond-the-close check
- Against the consensus closing spread (the median of the OTHER books on the game), does the chosen side beat it more
  than 50% of the time?
- If the bet wins against the book's own number but not against the consensus, it is a stale-quote play: the Oct 30
  bad-quote case in slow motion. The write-up says which.

## Kill rule (holdout, 1-point gap)
The test fails if either holds:
- win rate under 53% at -110;
- under 150 qualifying bets in a holdout season.

## If it survives
- A close-time spread play, judged against our own close-time record, never the opener's.
- Write-up for Mar 14. The live requirement is a card run near tip that compares each book's moneyline and spread,
  which the price log already supports.
