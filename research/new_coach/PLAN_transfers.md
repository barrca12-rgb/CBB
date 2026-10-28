# Follow-up: high-major new coaches who brought transfers with them (pre-registered Oct 28, 2026, before any result)

Chad's narrower hypothesis after the general new-coach study (LOG.md: no bump): a high-major team whose new coach
brings players from his previous school starts faster than the model and the market expect, because the core already
knows the system. Research only; no change to v1, the card, selection or staking.

**Definitions (fixed now).**
- *High-major*: the team's conference tier is "high" (`research.originator.d2_tiers.HIGH`, as in PLAN.md).
- *New coach with a previous head job*: `data/research/coaches.csv` marks the team-season new, and the same coach
  name is the head coach of a different team in the previous season.
- *Followers*: players with minutes for the coach's previous team last season and minutes for the new team this
  season (`cbb.player_ratings.player_games`, by athlete id).
- *Brought transfers* (group A): followers played at least 20% of the new team's minutes in its first 5 games.
  Sensitivity, reported but not used for the verdict: at least 2 followers, any minutes.
- Group B: other high-major new-coach team-seasons (no previous head job, or followers under 20%).
- Group C: every other team-game. Games where both teams have a new coach are dropped, as in PLAN.md.

**Outcomes and windows** as in PLAN.md: team's side, vs the model, vs the close, vs the opener where logged; primary
window the first 10 games, also 1-5 and 6-10.

**Seasons.** 2021-22 to 2025-26 pooled (the transfer-portal era; one-time transfers without sitting out began
2021-22). 2025-26 also shown alone. Expected sample: a handful of group-A teams a season, so intervals will be wide.

**Reading rule.**
- *Real*: A minus C vs the model, first 10 games, pooled 2021-26: at least +1.0 point with the interval excluding 0,
  and 2025-26 alone the same sign.
- *Worth money*: additionally A minus C vs the close at least +0.5 with the interval excluding 0 (pooled) and the
  same sign in 2025-26.
- A minus B is reported to show whether it is the followers or just being a high-major new hire.
- Every group-A team-season is listed with its own first-10-game numbers, so one outlier cannot hide.
- Otherwise no change. A real, money-worthy effect goes to Chad as a proposal for the Jan 15 checkpoint.
