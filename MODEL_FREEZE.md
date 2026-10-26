# Model freeze: Oct 26, 2026 to Jan 15, 2027

Approved by Chad on Oct 26, 2026. From the commit below until the January 15, 2027 checkpoint, nothing that decides a
play changes: the ratings code and settings, the second-stage weights (data/projection.json), team home edges,
referee tendencies, the preseason prior, the opening-week totals rule, the spread and total cutoffs (2.5 / 3), the
+2% EV minimum and the win-chance table. The ratings still update from every result, as the frozen code does.

Allowed during the freeze: fixes to data feeds, alerts, the site, the bet log and the record (not to how plays are
picked), and logging. Any exception is versioned, announced in the Discord channel the day it goes live, and noted
here.

Frozen at commit: dfb4bc7196d4f72cdeb933abdfcbc87c951122b5

File fingerprints (sha256) at the freeze:

```
03b23da31156a2b5bb2c4931c1569296743b96bd7305920ba77559d748189856  cbb/backtest.py
2c478acb4b1d8a1f29e9a2d984779f9916196507ec1524c43f9f06c2d27a272b  cbb/barttorvik.py
acdc8c627b7b0d63a521a8cef45f9a826f13e6ae88f2d4370cb4dfc71f8dfb8e  cbb/kenpom.py
f324ffdafcc522ed5996ed8e99912ad296c3a44c2a60bdc1b9e570bac16bff23  cbb/ratings.py
8080e931e4face9a615dd4e8b8f7726741cf225bc01bd8959fd5a6b3779b4304  cbb/projection.py
11c8e18f0bb8ab6f447a46e52026fbd9c3d26a1b74fbd9b67707768d4d70e898  cbb/context.py
a61befe042dc8071466223b4b824e2d99bdb55f20dfdea60ed2e67342f3627d1  cbb/players.py
810146943b07047e527cdafd518ec32d314df5c9d199ed5cfe343ee653493e06  cbb/injuries.py
9c27151379e46355a1b29eec0279013544c5e1c94b3e3eca0c2269ba5733e280  cbb/run_day.py
d2fefc7bce0c77a7d550ddf73f50fe6d2db7f9ca7a1a5f900015d0cf42b85dd3  data/projection.json
6862f2ed74a114b1a23fb00eff9d0f4ce468a596e761399ebabc065fec06c040  data/referees.csv
b01cf85d894b68542db7483c9eec54329156fb619ef4b61385f67931757c4f58  data/barttorvik_preseason_2027.csv
3525ba4a52316c323e311c8411912497470720ec40c5d8e38ffdd21f2ae8262e  data/teams.csv
446346d90b515a8271ce9ca592708f797311de3181e10f4d618f380b05e7de50  data/team_aliases.csv
```

Check at the checkpoint: `sha256sum -c` on the lines above (run_day.py may differ only by non-picking changes, each
listed below).

## Forward-test declaration (v1.1, Oct 26, 2026, before the first games on Nov 1)

The primary forward-test configuration is the live card as it runs on the model files fingerprinted above ("live v1";
its configuration is spelled out in `FORWARD_TEST_PROTOCOL.md`, section 1). Cohort v1 starts at this freeze commit's
time, 2026-10-26T19:20:50Z; the 8 signals logged earlier are the pre-freeze cohort, reported separately. All other
variants (production backtest, `safe_lag1`, no-Barttorvik, live-like) are research comparisons. Checked
2026-10-26: every model-file fingerprint above still matches (`sha256sum -c`).

```
5aa4d6487a95a7feb5b4b32899b617a3e556dcc707a3eafaf309b38339da63dd  FORWARD_TEST_PROTOCOL.md
308631d1a1f6d5c923de3256d9043c4247c6fab71e13ab4ec4b985eeca46b422  audit/forward_eval.py
2531cec9e0509d9f511025f3ad8e36359d4624978f5817be743460c127fc36ca  audit/out/frozen_preseason_prior_2027.csv
```

The prior file is `backtest.preseason_prior(2027)` dumped at the freeze (KenPom preseason + saved Barttorvik
preseason). If a live run ever computes a different prior (for example KenPom's preseason archive changes), that is
a data-integrity event under protocol section 6.

## Changes during the freeze

None to the model files. Additions that do not touch any prediction or selection: the Discord freeze announcement
(`bets/announcements.json`), audit scripts and reports (`audit/`), the protocol and these fingerprints. Proposed
logging/reporting and evaluation fixes are in `audit/patches/`, not applied, awaiting Chad's approval.
