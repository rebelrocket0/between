# Between — handoff (2026-11-15, 05:10)

Paste this into a new chat or give it to Claude Code. The full technical state lives in `~/projects/between/docs/HANDOFF.md` (checkpoint 4, written by Claude Code). This file is the short version plus what happened after it.

Rules: never put keys, tokens, passwords, account IDs, or private calendar links in any file or chat. Run Python as `/usr/bin/python3`. Don't create billable AWS resources without asking the user. One step at a time; stay on the build order.

## What works right now
- Web app at http://127.0.0.1:8765 (dashboard: Today's plan, Fits your window, Drop a thought, Pip's questions, to-dos in 3 categories with "Log time" and "Not today").
- Gemini splits brain dumps into tasks and asks follow-ups. Model: `gemini-flash-lite-latest` (the other two models were too slow and timed out).
- Google Calendar read (classes block time), Canvas calendar import (due dates become school tasks), two-week planner spreads work before due dates, "Between:" blocks written to Google Calendar, "Between · Today" list in Google Tasks. All three Google permissions confirmed OK.
- Root cause of the repeated sign-ins was fixed: old GOOGLE_* variables set via `launchctl setenv` overrode `.env`. `.env` now wins. Clear leftovers with `launchctl unsetenv` if they return before a reboot.
- Git: private GitHub repo `between`, co-author trailers removed and disabled. Check `git status` before each commit; `.gitignore` covers .env, data/, client_secret*.json.
- Tests: 14 files, 137 tests passing (Gemini and Google mocked everywhere).

## In progress: iPhone Shortcut ("local brain capture")
Structure is correct (menu Type/Dictate → Get contents of URL, POST, JSON body {text, source: phone}, Content-Type: application/json). Two fixes needed:
1. The token in the URL is stale and has appeared in screenshots. Rotate once: `curl -s -X POST http://127.0.0.1:8765/api/setup/reset-token` on the Mac, then paste the new token after `/api/capture/` in BOTH Get-contents actions. Never paste the token into chat.
2. Replace the IP with `mac.local:8765` in both actions. Remove the empty header row.
Test on home Wi-Fi: run shortcut → Dictate → "read chapter 4 for 20 minutes" → task appears on the dashboard.

## Build order (remaining)
1. Finish the Shortcut test above.
2. README + 2-minute demo script for judges (Claude Code can draft from docs/HANDOFF.md). Set `APP_URL` in `.env` once hosted so Google Tasks links open the hosted app.
3. AWS: user supplies MFA/region/domain. EC2 t3.micro + Docker + HTTPS + Secrets Manager + $0 budget alert. Only if hours allow; otherwise demo on home Wi-Fi and list AWS as next step.
4. Gemini phase 2 (after AWS): clean Canvas titles + per-type estimates; break big tasks into steps (show next step only); merge Canvas/brain-dump duplicates and file low-urgency dumps as Someday; chat box ("what should I do in the next 20 min?", "am I on track for the exam?"); pattern noticing stub.
5. Gemini Live voice (needs HTTPS + server-side key).
6. Polish list in `docs/POLISH.md` (user is collecting UI/wording changes there).

## Open decisions
- "LOCK IN !!!!" Tue/Thu 1:15–2:45: fixed commitment (current) or study block to fill with sessions?
- Planning window currently 7am–10pm; minimum session 10 min (consider 20 so gaps between classes stay free).
- Canvas items named "exam"/"midterm" should become "Study for: …" with a larger estimate.
- Gemini sees calendar times only (not event titles). Keep unless the user says otherwise.
- Repo is private; flip to public at submission after a final secret scan. Check Sun Hacks rules on AI-tool disclosure.

## Suggested first message for the next session
"Read docs/HANDOFF.md and this file. Confirm the server runs on /usr/bin/python3 at 8765 and tests pass. Then help me finish the iPhone Shortcut test, then the README and demo script. Don't start AWS until I say how many hours are left."
