# Between — checkpoint 4 (2026-11-15, ~04:30)

Start here. This replaces checkpoint 3. Never put keys, tokens, passwords, account IDs, or private calendar links in this file.

## What Between is now
A web app (PWA) that turns free gaps into done tasks. You brain-dump by typing (phone dictation later). Gemini splits the dump into tasks and asks follow-ups. Google Calendar supplies busy time; Canvas due dates arrive from the "canvas" calendar. A two-week planner spreads each task's work over the days before it's due; **Gemini now picks today's sessions and writes their reasons**, checked by `validate_plan`, with the rule planner as fallback. Google Calendar shows the sessions as "Between:" blocks; Google Tasks shows one list, "Between · Today". The web app shows three categories: Urgent & important, Urgent, Important. Clicking a Google Task leads to the web app (link in notes).

## Done since checkpoint 3
- **Git + GitHub.** Private repo: https://github.com/rebelrocket0/between (branch `main`). One commit on GitHub before this checkpoint (`2a16895`, initial). `.gitignore` covers `.env`, `.env.*` (except `.env.example`), `client_secret*.json`, `credentials.json`, `token.json`, `data/*.sqlite*`, `data/phone_capture_token` (the real file name), `data/schedule_snapshot.txt`, `__pycache__/`, `.DS_Store`. Secret scan of every committed file found nothing.
- **No co-author lines.** The first commit was rewritten without its Co-Authored-By trailer and force-pushed. `.claude/settings.local.json` turns attribution off for this project (kept out of git via `.git/info/exclude`).
- **`.env` now wins over shell variables** in `load_config()` (`server.py`). Shell `GOOGLE_*`/`CANVAS_*`/`LIFE_BRAIN_*`/`TIMEZONE` only fill keys that `.env` leaves empty. Cause found: the three `GOOGLE_*` values had been set with `launchctl setenv` (not in any profile file or LaunchAgent), which would have shadowed a fresh Google login. They vanish on logout/reboot; the user was asked to run `launchctl unsetenv` for all three (not confirmed).
- **Gemini planner wired in** (build item 2). See "How planning works".
- **"Not today" now changes the plan.** New column `tasks.last_skipped_on`. A task skipped today gets no session today (back tomorrow). After 2+ skips, a non-urgent task goes after others with the same deadline. Skip toast text updated.
- **Tests can no longer touch the real Google account.** Five server test files (`test_gemini_split`, `test_free_time`, `test_capture_routing`, `test_plan_route`, `test_time_logs`) never set `AUTO_SYNC_GOOGLE_TASKS = False`; running them synced test data to the real "Between · Today" list. All now set it; `test_gemini_split` also mocks the config. The server's startup sync rewrites the real list.
- **Gemini timeouts now try the next model** (both the split and day-plan model loops caught only `ValueError`, so a timeout gave up after the first model).
- **Uncommitted:** all code changes above (server.py, task_rules.py, public/app.js, tests) are local only as of this checkpoint. Only this file was committed with it.

## Run it (Mac)
```
cd ~/projects/between
for f in tests/test_*.py; do /usr/bin/python3 "$f" 2>&1 | tail -1; done   # 14 files, 137 tests, all OK
/usr/bin/python3 server.py        # must be /usr/bin/python3 (Apple Python); python.org 3.14 fails TLS
```
Dashboard: http://127.0.0.1:8765 (Cmd+Shift+R after changes). If it says 8766, an old server still held 8765 when it started: stop both, wait until `lsof -nP -iTCP:8765 -sTCP:LISTEN` shows nothing, then start again.

Google sign-in (one time, then check):
```
/usr/bin/python3 scripts/google_auth.py     # tick all three permission boxes
/usr/bin/python3 scripts/check_google.py    # want: three OK lines
```
Note: checkpoint 3 said `google_auth.py` prints the granted permissions and `check_google.py` warns about shell-variable overrides. The files on disk do neither; the `.env`-wins change makes the warning unnecessary.

## Files
- `server.py` — routes, DB, Gemini split, Gemini day plan (`gemini_day_plan`, `gemini_today_blocks`), Google sync, planner glue (`multi_day_plan`).
- `task_rules.py` — pure rules: boxes/categories, skips, `plan_blocks`, `validate_plan` (now with a daily-minutes cap), `spread_sessions` (now honors per-task `earliest` and skips), `plan_with_today`, `must_start_today`, `free_after_blocks`, `rule_reason`, `explain_blocks`, `within_plan_window`.
- `gap_engine.py` — original "fits your window" logic.
- `scripts/google_auth.py` — one-time Google sign-in; scopes: calendar.readonly, calendar.events, tasks.
- `scripts/check_google.py` — shows which permissions the saved login has.
- `scripts/cleanup_old_lists.py`, `scripts/cleanup_duplicates.py` — Google Tasks / duplicate cleanup.
- `scripts/dump_schedule.py` — writes `data/schedule_snapshot.txt` (all calendars, 14 days). Local only, git-ignored.
- `tests/test_gemini_planner.py` — new: 26 tests, Gemini always mocked.
- `docs/PLAN-tasks-and-boxes.md` — the original boxes/Tasks plan (partly superseded).
- `public/` — dashboard. Cards: Pip hero, **Today's plan**, Fits your window, stats, Drop a thought, Pip has a question, Your to-dos (grouped by category, with "Not today" and "Log time").

## Key routes
GET `/api/state`, `/api/today` (now also returns `planner`: "gemini" or "rules", and `planner_note`), `/api/free-time`, `/api/plan?minutes=N`, `/api/questions`.
POST `/api/capture`, `/api/tasks/<id>/log|estimate|skip`, `/api/questions/<id>/answer`,
`/api/connectors/google/tasks/sync`, `/api/connectors/google/blocks/sync`, `/api/connectors/google/canvas/sync`.
PATCH `/api/tasks/<id>` {status}.

## How planning works
- Tasks have `box` (do_now/plan/quick/someday, set by Gemini), `due_date`, `skips`, `last_skipped_on`. Due within 2 days ⇒ do_now. Boxes map to the 3 categories.
- **Today (Gemini):** if `GEMINI_API_KEY` is set, Gemini gets today's free-time ranges (times only, never event titles) and up to 25 open tasks (title, category, session length ≤60 min, due date, days until due, `must_start_today`, times skipped). Tasks skipped today are not sent. `validate_plan` keeps only real tasks, used once, starting and ending inside free time, ≤2 no-deadline tasks, ≤240 min total. Gemini's reason is kept; an empty one gets a rule reason.
- **Rest of the two weeks:** `plan_with_today` builds days 2–14 around Gemini's picks with `spread_sessions`. A task Gemini scheduled today continues from tomorrow with what's left. A task Gemini left out waits for tomorrow, unless it can't get all its sessions in before its due date without today (`must_start_today`); then it may use today's leftover time.
- **Fallback (rules):** no key, Gemini error/timeout, or nothing usable ⇒ `spread_sessions` plans everything. Rules: earliest deadline first, often-skipped non-urgent tasks after others with the same deadline, ≤1 session/task/day (60 min), ≤240 task-min/day, 7am–10pm, 14-day horizon, 5-min buffers.
- **Reasons:** every block has one. Rule reasons, e.g. "Session 2 of 3 before it's due Fri Nov 20", "Due today; one session finishes it", "No deadline yet; fits your free time", plus "· moved off today because you said not today" or "· placed after other work because you skipped it 3 times".
- **Caching:** plan cached 3 min, cleared on capture/skip/done. Gemini's raw answer cached 30 min per (day, task set, free-time ends). After a Gemini failure, Gemini is skipped for 10 min so refreshes stay fast.
- Sync (startup, then every 30 min 6am–11pm): Canvas import → Google Tasks "Between · Today" (cleared and rewritten) → calendar blocks (tagged, deleted and recreated for 14 days).

## Known state / issues
- **Gemini is too slow right now, so the live app uses the rule planner.** `gemini-4-hydrogen` and `gemini-3.8-flash` (the `GEMINI_MODELS` list) and `gemini-flash-latest` all took over 25 s even for a trivial prompt (2026-11-15 ~04:00). `gemini-flash-lite-latest` answered in 0.9 s. Both configured models exist for the key. This likely affects brain-dump splitting too. See open decisions.
- **Calendar blocks still need the calendar.events permission.** The user has not yet run `scripts/google_auth.py` since checkpoint 3. Google Auth Platform: scope added, app is Internal.
- Google Tasks sync works. Canvas import works.
- Today's live plan (rules) has 6 sessions, all due today, and 2 tasks unplaced.
- Test data: duplicate tasks from repeated captures still in `data/life_brain.sqlite`. Not deleted (user's data).
- Phone token appeared in terminal output pasted into chat during checkpoint 2/3 work; rotate if it leaked (`POST /api/setup/reset-token`).

## Open decisions
- **Gemini model** (asked, not answered): (a) put `gemini-flash-lite-latest` first for planning and splitting, (b) lite for planning only, or (c) keep current models (each plan waits ~50 s, then rules, while they're slow).
- "LOCK IN !!!!" Tue/Thu 1:15–2:45 — fixed commitment (blocks time, current) or study block to fill?
- Gemini sees calendar event titles or times only. Implemented as times only; keep unless the user wants titles.
- Commit the uncommitted code changes (Gemini planner, skip handling, test guards).

## Build order
1. Finish Google permission → see blocks in Calendar + "Between · Today". **In progress** — waiting on the user to run `google_auth.py` and get three OKs from `check_google.py`.
2. Gemini: write reasons / adjust the plan (wire `gemini_day_plan` with `validate_plan`). **Done in code** (local, uncommitted; 137 tests pass, Gemini mocked). **Not working live** until the model decision: live Gemini times out, so the rule fallback runs (with real reasons).
3. Phone shortcut (dictation → `/api/capture`) on home Wi-Fi. **Not started.**
4. AWS: MFA, region, domain → EC2 t3.micro + Docker + HTTPS + Secrets Manager + $0 budget alert. Set `APP_URL` in `.env` so Google Tasks links open the hosted app. **Not started.** Don't create AWS resources without asking.
5. Gemini Live voice (needs HTTPS + server-side key). **Not started.**
6. Learning from logged time / skips (needs weeks of data). **Not started**; skips now feed the planner, and `last_skipped_on` is recorded.

## Ideas parked
Claude plugin / MCP server exposing tasks + free time; browser extension that detects task sites (opt-in, privacy-sensitive).
