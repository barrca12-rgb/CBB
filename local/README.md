# Barttorvik's daily file from Chad's computer

Barttorvik refuses GitHub's servers (HTTP 403 since Oct 30), so the card cannot download his daily ratings file
itself. `fetch_barttorvik.py` runs on your own computer, where his site works normally. Three times a day it checks
the last three dates. Any file it doesn't have yet, it asks for once, five seconds apart. It saves the four columns the
model uses to `data/barttorvik_tm/`, then commits and pushes. The card reads those files from the repo and never
contacts Barttorvik for them.

The first daily file is expected around Nov 2 (last season's was Nov 2). Until then the script prints "not posted
yet", which is normal.

## What you need
- Git and Python 3. A Mac has both after `xcode-select --install`; on Windows, install Git for Windows and
  Python from python.org.
- Git signed in to GitHub with push access to barrca12-rgb/CBB. If `git push` asks for a password, run
  `gh auth login` once, or sign in through Git Credential Manager on Windows.
- A computer that is on and awake at the run times. If it is asleep, that run is skipped and the next one catches up.

## Mac (or Linux)
1. Open Terminal and make a clone used only for this:
   ```
   git clone https://github.com/barrca12-rgb/CBB.git ~/cbb-fetch
   cd ~/cbb-fetch && git checkout claude/college-basketball-model-nmztcl
   ```
2. Test it once, without pushing:
   ```
   python3 local/fetch_barttorvik.py --no-push
   ```
   You should see "not posted yet" for each date (before the season), or "saved 365 teams". An error that says
   **403** means Barttorvik refuses your connection too. Stop there and tell Claude.
3. Schedule it at 7:17 am, 1:17 pm and 7:17 pm. Run `crontab -e` and add this one line:
   ```
   17 7,13,19 * * * cd ~/cbb-fetch && /usr/bin/python3 local/fetch_barttorvik.py >> ~/cbb-fetch.log 2>&1
   ```
   To check later: `tail ~/cbb-fetch.log`.

## Windows
1. In PowerShell:
   ```
   git clone https://github.com/barrca12-rgb/CBB.git $HOME\cbb-fetch
   cd $HOME\cbb-fetch; git checkout claude/college-basketball-model-nmztcl
   py local\fetch_barttorvik.py --no-push
   ```
   Same check as step 2 above.
2. Task Scheduler, Create Basic Task, "CBB Barttorvik", Daily at 7:17 am:
   - Program: `py`
   - Arguments: `local\fetch_barttorvik.py`
   - Start in: your `cbb-fetch` folder

   Then open the task's Triggers tab and add 1:17 pm and 7:17 pm.

## How to tell it is working
- The repo gets a commit "Barttorvik daily file(s) from Chad's machine: ...".
- The card run's log says "Barttorvik for <date> games: time-machine file <date> (repo copy from Chad's machine)".
- Each play's input stamp stops reading "No Barttorvik ratings yet".

The script only ever writes to `data/barttorvik_tm/`. It keeps the four columns the model uses (team, adjusted
offense, adjusted defense, tempo), the same as the preseason file already in `data/`.
