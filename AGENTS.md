# AGENTS.md — Between (read this first)

Between is a solo hackathon project (Sun Hacks 2026). It turns a student's free gaps into done tasks. Brain dumps (typed, or dictated via an iPhone Shortcut) are split into tasks by Gemini; Google Calendar supplies busy time; Canvas due dates arrive from a "canvas" calendar; a two-week planner spreads each task's work before its deadline and writes "Between:" blocks to Google Calendar and a "Between · Today" list to Google Tasks. The web app shows three categories: Urgent & important, Urgent, Important. Companion character: Pip (original art; don't copy existing characters).

Current state: `docs/HANDOFF-short.md`, `docs/ROADMAP-STATUS.md`, and `docs/RELEASE-REVIEW.md`. Read the handoffs before changing anything. The project has been submitted; follow the newest user task and preserve the completed implementation. Portfolio documentation is post-submission work.

## Hard rules
- Never print, log, commit, or paste secrets: `.env` values, Google client secret / refresh token, Gemini key, the phone capture token, or private calendar links. `.env` is gitignored; keep it that way. If a secret appears in output, say so and help rotate it.
- Run Python with `/usr/bin/python3` (Apple Python). The python.org 3.14 install fails TLS verification against Google.
- Don't create billable AWS resources, change Google Cloud settings, or delete user data without asking first.
- One step at a time. Follow the newest user task; do not add unrequested features.
- Before every commit: `git status`, confirm no `.env`, `data/`, or `client_secret*.json`. Don't add co-author trailers.

## Run and test
```
cd ~/projects/between
/usr/bin/python3 -m unittest discover -s tests -p 'test_*.py'   # 261 tests at publication
node tests/frontend_runtime.cjs                              # 8 synthetic runtime checks
```
Run an app server only in an independent development checkout without production credentials. Do not start a competing production-connected local server. Account-level Google checks contact real services; run them only when authorized by the current task.

Dashboard needs a reload after file changes (assets/cache source are v6; bump if you change app.js/styles.css).

## Code map
- `server.py` — stdlib HTTP server, SQLite (`data/life_brain.sqlite`), routes, Gemini calls, Google sync, planner glue, 30-min background sync (6am–11pm, plus once at startup).
- `task_rules.py` — pure logic: boxes→categories, due-word parsing, `plan_blocks`, `validate_plan`, `spread_sessions`, skip rules.
- `gap_engine.py` — "fits your window" logic.
- `public/` — vanilla JS PWA (index.html, app.js, styles.css, sw.js).
- `scripts/` — `google_auth.py` (OAuth; scopes calendar.readonly, calendar.events, tasks), `check_google.py`, `dump_schedule.py`, `cleanup_duplicates.py`, `cleanup_old_lists.py`.
- `tests/` — unittest files; Gemini and Google are mocked in all of them. Tests must never touch the real Google account (`AUTO_SYNC_GOOGLE_TASKS = False` in tests).

Key routes: GET `/api/state`, `/api/today`, `/api/free-time`, `/api/plan?minutes=N`, `/api/questions`; POST `/api/capture` (token in header, path, or `?token=`; loopback skips it), `/api/tasks/<id>/log|estimate|skip`, `/api/questions/<id>/answer`, `/api/setup/reset-token`, `/api/connectors/google/{tasks,blocks,canvas}/sync`; PATCH `/api/tasks/<id>`.

## Config (.env keys, values never shown)
GEMINI_API_KEY, GEMINI_MODEL (=gemini-flash-lite-latest; others were too slow), GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN, TIMEZONE (America/Phoenix), optional GOOGLE_CALENDAR_ID, CANVAS_CALENDAR_NAME (default "canvas"), APP_URL (set when hosted).
`.env` wins over shell variables (a leftover `launchctl setenv` once overrode it; clear with `launchctl unsetenv` if it recurs).

## Completed project and follow-up scope

The submitted implementation includes remote Shortcut capture, hosted deployment, Smart Canvas processing, ordered task steps, conservative duplicate matching, quiet filing, Ask Pip, supported explanations, and evidence-gated observations. Read the current status documents rather than restarting the old build sequence.

Gemini Live and the remaining polish/reliability opportunities are future work. Do not add features, deploy, change data, or create billable resources unless the current user task authorizes them.

## Open decisions (ask the user, don't guess)
- Existing recurring commitments remain fixed unless the user explicitly reclassifies them. Keep personal event names and times out of public documentation.
- Planning window 7am–10pm; min session 10 min (20 would keep gaps between classes free).
- Canvas exam items already become preparation tasks with bounded estimates; do not change the configured priors silently.
- Gemini sees calendar times only, not titles (keep unless told otherwise).
- Change repository visibility only when explicitly authorized. Keep submission chronology and AI-tool credits accurate.

## Working style (from the user)
Simple step-by-step instructions. One thing at a time. Stay within the current task; don't drift. Never create billable AWS resources without asking. Keep Pip original (cozy, no copied art).
