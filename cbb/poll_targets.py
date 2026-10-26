"""Targeted quote polling for the forward-test execution check (FORWARD_TEST_PROTOCOL.md, section 5).

Run every 3 minutes by .github/workflows/quotes.yml. If any game is inside a watch window (from a signal's actual
alert through 95 minutes, or the last 20 minutes before its scheduled tip: quotelog.watched_games) it makes one Odds
API call for spreads and totals (2 credits) and logs every quote of the watched games to lines/obs_targeted/;
otherwise it spends nothing and writes nothing. It never touches the model, the card, the bet log, openers.csv or closing.csv.

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


if __name__ == "__main__":
    main()
