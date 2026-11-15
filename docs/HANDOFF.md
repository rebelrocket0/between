# Between — checkpoint 3 (2026-11-15, ~02:45)

Start here. This replaces checkpoint 2. Never put keys, tokens, passwords, account IDs, or private calendar links in this file.

## What Between is now
A web app (PWA) that turns free gaps into done tasks. You brain-dump by typing (phone dictation later). Gemini splits the dump into tasks and asks follow-ups. Google Calendar supplies busy time; Canvas due dates arrive from the "canvas" calendar. A two-week planner spreads each task's work over the days before it's due. Google Calendar shows the sessions as "Between:" blocks; Google Tasks shows one list, "Between · Today". The web app shows three categories: Urgent & important, Urgent, Important. Clicking a Google Task leads to the web app (link in notes).

## Run it (Mac)
```
cd ~/projects/between
for f in tests/test_*.py; do /usr/bin/python3 "$f" 2>&1 | tail -1; done   # 13 files, all OK
/usr/bin/python3 server.py        # must be /usr/bin/python3 (Apple Python); python.org 3.14 fails TLS
```
Dashboard: http://127.0.0.1:8765 (Cmd+Shift+R after changes). If it says 8766, an old server holds 8765; stop it.

## Files
- `server.py` — routes, DB, Gemini split, Google sync, planner glue.
- `task_rules.py` — pure rules: boxes/categories, skips, `plan_blocks`, `validate_plan`, `spread_sessions`, `within_plan_window`.
- `gap_engine.py` — original "fits your window" logic.
- `scripts/google_auth.py` — one-time Google sign-in; scopes: calendar.readonly, calendar.events, tasks. Prints granted permissions at the end.
- `scripts/check_google.py` — shows which permissions the saved login has, and warns if shell variables override `.env`.
- `scripts/cleanup_old_lists.py` — deletes only old Between lists in Google Tasks (none existed).
- `scripts/dump_schedule.py` — writes `data/schedule_snapshot.txt` (all calendars, 14 days). Local only.
- `docs/PLAN-tasks-and-boxes.md` — the original boxes/Tasks plan (partly superseded by this file).
- `public/` — dashboard. Cards: Pip hero, **Today's plan**, Fits your window, stats, Drop a thought, Pip has a question, Your to-dos (grouped by category, with "Not today" and "Log time").

## Key routes
GET `/api/state`, `/api/today`, `/api/free-time`, `/api/plan?minutes=N`, `/api/questions`.
POST `/api/capture`, `/api/tasks/<id>/log|estimate|skip`, `/api/questions/<id>/answer`,
`/api/connectors/google/tasks/sync`, `/api/connectors/google/blocks/sync`, `/api/connectors/google/canvas/sync`.
PATCH `/api/tasks/<id>` {status}.

## How planning works
- Tasks have `box` (do_now/plan/quick/someday, set by Gemini), `due_date`, `skips`. Due within 2 days ⇒ do_now. Boxes map to the 3 categories.
- `spread_sessions`: earliest deadline first, ≤1 session/task/day (60 min), ≤240 task-min/day, 7am–10pm, 14-day horizon, 5-min buffers. Someday tasks capped at 2 blocks.
- Sync (startup, then every 30 min 6am–11pm): Canvas import → Google Tasks "Between · Today" (cleared and rewritten) → calendar blocks (tagged, deleted and recreated for 14 days). Plan cached 3 min; cleared on capture/skip/done.
- Gemini day-planning code (`gemini_day_plan`, `validate_plan`) exists but is NOT wired in; the rule planner runs. Reasons are plain text.

## Known state / issues
- **Calendar blocks need the calendar.events permission.** `check_google.py` showed it MISSING. The scope was added to the Google Auth Platform Data Access page (saved) and app is **Internal** (no 7-day expiry). The login script on the Mac now requests all 3 scopes. NEXT: run `scripts/google_auth.py`, tick every box, then `scripts/check_google.py` → all OK. If still missing, check for `GOOGLE_*` shell variables (the check script warns).
- Google Tasks sync works (Tasks API enabled). Canvas import works (18 items/2 weeks).
- Test data: duplicate tasks from repeated captures still in `data/life_brain.sqlite`. Not deleted (user's data).
- Decision pending: "LOCK IN !!!!" Tue/Thu 1:15–2:45 — fixed commitment (blocks time, current) or study block to fill?
- Decision pending: Gemini sees calendar event titles or times only (default: times only).
- Phone token appeared in terminal output pasted into chat; rotate if it leaked (`POST /api/setup/reset-token`).

## Build order (unchanged)
1. Finish Google permission → see blocks in Calendar + "Between · Today".
2. Gemini: write reasons / adjust the plan (wire `gemini_day_plan` with `validate_plan`).
3. Phone shortcut (dictation → `/api/capture`) on home Wi-Fi.
4. AWS: MFA, region, domain → EC2 t3.micro + Docker + HTTPS + Secrets Manager + $0 budget alert. Set `APP_URL` in `.env` so Google Tasks links open the hosted app.
5. Gemini Live voice (needs HTTPS + server-side key).
6. Learning from logged time / skips (needs weeks of data).

## Ideas parked
Claude plugin / MCP server exposing tasks + free time; browser extension that detects task sites (opt-in, privacy-sensitive).
