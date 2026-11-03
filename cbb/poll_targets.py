"""Targeted quote polling for the forward-test execution check (FORWARD_TEST_PROTOCOL.md, section 5).

Run every 3 minutes by .github/workflows/quotes.yml. If any game is inside a watch window (from a signal's actual
alert through 95 minutes, or the last 20 minutes before its scheduled tip: quotelog.watched_games) it makes one Odds
API call for spreads and totals (2 credits) and logs every quote of the watched games to lines/obs_targeted/;
otherwise it spends nothing and writes nothing. Games in their last 20 minutes that The Odds API does not carry are
asked of SportsGameOdds by event id (one entity each; approved by Chad, Nov 3). It never touches the model, the card, the bet log, openers.csv or closing.csv.

    python -m cbb.poll_targets
"""
from __future__ import annotations

from . import odds_api, quotelog


def main() -> None:
    # own files, so this workflow and the card workflow never append to the same file
    polls, obs_dir = quotelog.POLLS, quotelog.OBS_DIR
    quotelog.POLLS = polls.replace("polls.csv", "polls_targeted.csv")
    quotelog.OBS_DIR = obs_dir + "_targeted"
    try:
        _poll()
        quotelog.compact()
    finally:
        quotelog.POLLS, quotelog.OBS_DIR = polls, obs_dir


def _poll() -> None:
    t = quotelog.now()
    watched = quotelog.watched_games(t)
    if not watched:   # idle: no API call and no log row (the Actions run history shows the schedule is alive)
        print("Nothing to watch.")
        return
    if not odds_api.budget_ok():   # live credit reserve (odds_api.MIN_LEFT), from the card runs' latest balance
        quotelog.poll("oddsapi-targeted", "error", quotelog.now(),
                      error=f"credit reserve: stopped below {odds_api.MIN_LEFT} credits left")
        print(f"Credit reserve reached (below {odds_api.MIN_LEFT}); no targeted poll.")
        return
    try:
        obs, info = odds_api.fetch_quotes()
    except Exception as e:
        quotelog.poll("oddsapi-targeted", "error", quotelog.now(), error=e)
        print(f"Targeted poll failed: {e}")
        return
    pid = quotelog.poll("oddsapi-targeted", "ok", info["observed_at"], events=info["events"], quotes=len(obs),
                        cost=info["cost"], remaining=info["remaining"])
    n = quotelog.observations(obs, pid, info["observed_at"], watched)
    print(f"Watched {len(watched)} game(s); logged {n} observation(s); cost {info['cost']}, {info['remaining']} left.")
    _sgo_close(watched, obs)


def _sgo_close(watched: set, oa_obs: list) -> None:
    """Games in their last TIP_WATCH minutes that The Odds API does not carry get the same poll from SportsGameOdds,
    asking for just those events (Chad, Nov 3: approved; Nov 2, six plays on SGO-only games had no close). Logging
    only: quotes go to lines/obs_targeted/ like every targeted quote; the card, picks and bet log are untouched."""
    from . import odds
    t = quotelog.now()
    starts = quotelog._signal_starts()
    have = {r["game_key"] for r in oa_obs if r.get("status") == "available" and r.get("line") is not None}
    need = sorted(g for g in watched if g in starts and starts[g] - quotelog.TIP_WATCH <= t < starts[g] and g not in have)
    if not need:
        return
    ev = _sgo_events(need)
    if not ev:
        print(f"SGO close poll: no SGO event id for {len(need)} game(s) without Odds API quotes.")
        return
    try:
        odds.fetch(event_ids=sorted(set(ev.values())))
    except Exception as e:
        quotelog.poll("sgo-targeted", "error", quotelog.now(), error=e)
        print(f"SGO close poll failed: {e}")
        return
    f = odds.fetch
    u = getattr(f, "usage", {}) or {}
    asked = len(set(ev.values()))
    if f.events > max(3 * asked, asked + 5):   # SGO ignored the event filter: log it and stand down for this game day
        print(f"SGO close poll: asked {asked} event(s), SGO returned {f.events}; event filter not honoured.")
        quotelog.poll("sgo-targeted", "error", f.observed_at, events=f.events, quotes=0, cost=f.events,
                      error=f"event filter not honoured ({asked} asked, {f.events} returned)")
        return
    pid = quotelog.poll("sgo-targeted", "ok", f.observed_at, events=f.events, quotes=len(f.observations), cost=f.events,
                        remaining=(u["max"] - u["used"] - f.events) if u else None)
    n = quotelog.observations(f.observations, pid, f.observed_at, set(need))
    print(f"SGO close poll: {asked} event(s) asked, {f.events} returned; logged {n} observation(s).")


def _sgo_events(keys: list) -> dict:
    """game_key -> the SGO event id of that game (lines/closing.csv, the latest SGO row)."""
    import pandas as pd
    try:
        c = pd.read_csv(quotelog.os.path.join(quotelog.LINES, "closing.csv"))
    except Exception:
        return {}
    c = c[c["sgo_event"].notna() & ~c["sgo_event"].astype(str).str.startswith("oa:")]
    st = pd.to_datetime(c["start"], utc=True, errors="coerce", format="ISO8601")
    lo = c[["home_id", "away_id"]].min(axis=1).astype(int).astype(str)
    hi = c[["home_id", "away_id"]].max(axis=1).astype(int).astype(str)
    c = c.assign(gk=st.dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d") + "|" + lo + "|" + hi)
    c = c.sort_values("pulled_at").drop_duplicates("gk", keep="last")
    m = dict(zip(c["gk"], c["sgo_event"].astype(str)))
    return {k: m[k] for k in keys if k in m}


if __name__ == "__main__":
    main()
