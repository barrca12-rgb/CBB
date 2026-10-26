# Historical market research (separate from live v1)

Research on timestamped quotes and on existing data. Nothing here touches the frozen model, the live card,
selection rules, staking, the bet log or the forward-test protocol. Everything lives under `research/market/`, with
outputs in `research/market/out/`. Every experiment and every specification tried is logged in `LOG.md`,
failures included.

| Step | Status | Files |
|---|---|---|
| 1. Sample and completeness check (The Odds API historical snapshots) | **stopped before spending: cost reported, approval needed** | `STEP1_REPORT.md` |
| 2. Opener and execution test on real quotes | waits for the full-pull approval | |
| 2a. Model edge vs favourable quote | run on existing ESPN multi-book data | `s2a_decompose.py`, `out/s2a_*` |
| 3. Book-lag replay | waits for the full-pull approval | |
| 4. Market overreaction to a shooting night | run on existing closes and box scores | `s4_shooting.py`, `out/s4_*` |

Rules: chronological development only (fit on earlier seasons, test on later). Any candidate that survives is
written up as a proposal for a future versioned v2 with shadow testing, and goes to Chad for a decision.
