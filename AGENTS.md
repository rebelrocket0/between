# AGENTS.md — Between (read this first)

Between is a solo hackathon project (Sun Hacks 2026). It turns a student's free gaps into done tasks. Brain dumps (typed, or dictated via an iPhone Shortcut) are split into tasks by Gemini; Google Calendar supplies busy time; Canvas due dates arrive from a "canvas" calendar; a two-week planner spreads each task's work before its deadline and writes "Between:" blocks to Google Calendar and a "Between · Today" list to Google Tasks. The web app shows three categories: Urgent & important, Urgent, Important. Companion character: Pip (original art; don't copy existing characters).

Full state: `docs/HANDOFF.md` (detailed) and `docs/HANDOFF-short.md` (latest short version). Read both before changing anything.

## Hard rules
- Never print, log, commit, or paste secrets: `.env` values, Google client secret / refresh token, Gemini key, the phone capture token, or private calendar links. `.env` is gitignored; keep it that way. If a secret appears in output, say so and help rotate it.
- Run Python with `/usr/bin/python3` (Apple Python). The python.org 3.14 install fails TLS verification against Google.
- Don't create billable AWS resources, change Google Cloud settings, or delete user data without asking first.
- One step at a time. Follow the build order below; don't add features that aren't on it.
- Before every commit: `git status`, confirm no `.env`, `data/`, or `client_secret*.json`. Don't add co-author trailers.

## Run and test
```
cd ~/projects/between
for f in tests/test_*.py; do /usr/bin/python3 "$f" 2>&1 | tail -1; done   # 14 files, 137 tests, all OK
/usr/bin/python3 server.py          # http://127.0.0.1:8765 ; if it says 8766, an old server holds 8765 — stop it
/usr/bin/python3 scripts/check_google.py   # must show three OK lines
```
Dashboard needs a reload after file changes (assets are versioned `?v=3`; bump if you change app.js/styles.css).

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

## Build order (remaining, in this order)
1. **iPhone Shortcut** ("local brain capture"): structure is correct (menu Type/Dictate → POST JSON {text, source:"phone"} with Content-Type header). Needs: rotate the phone token via `POST /api/setup/reset-token`, put the new token after `/api/capture/` in both Get-contents actions, use `mac.local:8765` instead of the IP, remove the empty header row. Test on home Wi-Fi.
2. **README.md + 2-minute demo script** for judges.
3. **AWS** (only when the user says hours allow): EC2 t3.micro + Docker + HTTPS on a domain + Secrets Manager + $0 budget alert. User provides MFA/region/domain. Then set `APP_URL`.
4. **Gemini phase 2**: clean Canvas titles into verb-first tasks with per-type estimates (quiz < reading < reflection paper); break big tasks into steps, show only the next; merge Canvas/brain-dump duplicates and file low-urgency dumps as Someday without asking; a chat box answering "what should I do in the next 20 minutes?" / "am I on track for the exam?" from tasks + free time; pattern-noticing stub (needs weeks of data).
5. **Gemini Live voice** (needs HTTPS + server-side key; browser gets a short-lived token).
6. **Polish** from `docs/POLISH.md`.

## Open decisions (ask the user, don't guess)
- "LOCK IN !!!!" Tue/Thu 1:15–2:45: fixed commitment (current) or a study block to fill?
- Planning window 7am–10pm; min session 10 min (20 would keep gaps between classes free).
- Canvas "exam"/"midterm" items → "Study for: …" with a bigger estimate?
- Gemini sees calendar times only, not titles (keep unless told otherwise).
- Repo is private; flip to public at submission after a secret scan. Check Sun Hacks rules on AI-tool disclosure.

## Working style (from the user)
Simple step-by-step instructions. One thing at a time. Stay on the build order; don't drift. Never create billable AWS resources without asking. Keep Pip original (cozy, Bujji-like feel, no copied art).
