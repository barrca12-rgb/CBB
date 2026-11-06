# Check: does the F2 blend lean on underdogs in mismatches, and does that cost it? (pre-registered)

Written Nov 6, 2026, before computing. Prompted by the 2026-27 replay (the blend's spread plays 3-7 on favorites,
17-23 on underdogs). Backtest only.

- **Frames:** `audit/out/wf_own_base.pkl` (base) and `wf_rp4_R3.pkl` (F2 blend), 2015-2026.
- **Plays:** opener spreads at 2.5+ (`audit/common.bets`), graded at the opener, -110.
- **Splits:** favorite or underdog side; opener spread under 7, 7-14.5, 15+; days 0-20 and full season.
- **Also:** mean (blend - base) final margin from the favorite's side, by spread size, days 0-20.
- **Red flag (stated now):** in days 0-20, the blend's underdog plays on 15+ spreads win below 52.4%, or the blend's
  share of underdog plays is more than 10 points above base's while its underdog win % is below base's.
