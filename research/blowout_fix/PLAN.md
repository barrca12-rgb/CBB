# Blowout correction (pre-registered Nov 7, 2026; Chad: "make the correction to the live model")

**Finding behind it** (research/blowout_unders Part 2): when the model projects a big margin, the favorite scores
more than projected, so the margin is too small and the total too low; strongest in 2023-26.

**Correction:** extra favorite points `x = k * max(0, M - T)`, M = the model's projected margin (absolute). The
favorite's margin and the game total each rise by x. Two numbers, k and T.

**Fit (walk-forward, no peeking):** for each test season s in 2023-2026, choose (T, k) on the three seasons before s
(T in 16..28 step 2, k in 0..0.40 step 0.02) by the smallest sum of squared margin and total errors, then apply to
season s. Live uses the fit on 2023-2026.

**Judge on 2023-2026 (out of sample):**
1. Margin and total mean absolute error, all games and games with M 20+.
2. Opener plays 2024-26 (spreads 2.5+, totals 3+): win % and close movement, all and at |spread| 20+.

**Ship rule (fixed now):** go live only if the 20+ margin and total errors both fall, all-games errors do not
rise by more than 0.005, and opener win % falls by no more than 0.3 points in either market. Otherwise report and
do not ship.
