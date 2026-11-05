# Working on the Off The Glass model

Chad's standing rule (Nov 5, 2026): **constant self-improvement.** The model today is not good enough, and an edge
has to be proven live, not assumed from backtests. Always be looking for the next improvement.

## How that works in practice

- **Every session, look for an improvement.** After any task, check `research/IMPROVEMENT_BACKLOG.md` and the live
  results. If something new showed up (a losing segment, a missing input, a market we don't cover, a slow alert),
  add it to the backlog with the evidence.
- **Weekly review.** Compare live results with the backtests by segment: market, side (favorite/underdog,
  over/under), spread size, edge band, time posted before tip, book. Also compare all-games accuracy against the
  closing line. Write findings in `research/IMPROVEMENT_LOG.md`, dated, including "nothing new".
- **Test before believing.** Each idea gets a plan written before any result (`research/<name>/PLAN.md`), a
  backtest, and a report (`REPORT.md`) that keeps every number, including the ones that lose. Correct earlier
  claims in writing when a test shows they were wrong.
- **Rank by value.** Work the backlog in order of expected gain times how soon it can be tested. Small live samples
  are leads, not conclusions.
- **Live changes need Chad.** Nothing reaches the live model, the card's selection or stakes without Chad's approval,
  a MODEL_FREEZE.md entry with fingerprints, and a Discord note (`bets/announcements.json`).

## Standing rules from Chad

- Push only to `claude/college-basketball-model-nmztcl`. No pull requests unless asked.
- Never ask for tokens or keys. No purchases or credit-using data pulls without approval. Don't work around network
  policy or bot protection (including Barttorvik's).
- Odds come from The Odds API for the card; SGO is a separate feed. Play books: DraftKings, FanDuel, BetMGM,
  Caesars, Fanatics, theScore Bet, BetRivers. Novig is display only. bet365 is removed.
- **X (@OffTheGlassHQ, via Typefully):** drafts by default; publish only when Chad says to post. Never mention
  KenPom or Barttorvik in anything public. Every number comes from the bet log or the scripts; the official record
  is main plays (band B separate).
