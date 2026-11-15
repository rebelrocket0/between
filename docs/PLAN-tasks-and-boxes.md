# Between: Google Tasks sync and priority boxes (plan)

Historical design proposal from 2026-11-15, retained to document early trade-offs. This is not the current implementation or an operational checklist. The completed release uses one app-managed `Between · Today` list, leaf-task scheduling, and quiet Someday filing. See [current status](ROADMAP-STATUS.md) and the [README](../README.md); do not execute the old setup steps below as publication work.

## Why
Tasks should show up every day in Google Calendar (Google Tasks side panel), sorted into boxes by urgency and importance. Things with no due date should still get done when there's spare time.

## Boxes (Eisenhower grid)
- `do_now`: urgent and important. Due within 2 days, or Gemini marked it important with a near due date.
- `plan`: important, not urgent. Has a due date further out, or no due date and Gemini marked it important.
- `quick`: urgent, not important. Due soon but small or low stakes.
- `someday`: neither. No due date, not marked important. Fills free time only when nothing else fits.

## Steps (in order)
1. **Fix the answer-box bug** (`public/app.js`). Pause the 30-second refresh while any answer box has text or focus. Only redraw questions that changed.
2. **Turn on Google Tasks.** Enable the Google Tasks API in the Between Google Cloud project. Add scope `https://www.googleapis.com/auth/tasks` next to `calendar.readonly`. Run `scripts/google_auth.py` again. It writes a new refresh token to `.env`. Delete the downloaded client JSON from Downloads afterward.
3. **Add a `box` field to tasks.** Values: `do_now`, `plan`, `quick`, `someday`. Gemini sets it in the split prompt, with a fallback to rules if Gemini doesn't return one.
4. **Daily rule.** Recalculate `do_now` from due dates each day. Due within 2 days becomes `do_now`. Nothing else is decided by Gemini on a schedule.
5. **One-way sync, Between to Google Tasks.** Create one Google Tasks list per box, named "Between: Do now", "Between: Plan", "Between: Quick", "Between: Someday". Each open task becomes one Google Task. Store the Google task ID on the Between task so updates don't duplicate. Marking done in Between completes it in Google Tasks.
6. **Skip counter.** Add a `skips` count. "Not today" increments it. After 2 skips on a `plan` or `someday` task, move it to another free slot and show the reason: "Moved because you skipped it twice."
7. **Tests.** Box rules, skip logic, and sync with the Google calls mocked. Same style as the existing test files.
8. **Manual check.** Add a note, open Google Calendar, confirm the task appears in the Tasks panel under the right list.

## Not in this plan
- Pattern learning from history (needs weeks of data; skip counter is the first step).
- Live voice, AWS, phone notifications.
- Google Tasks to Between sync (two-way). Later.

## Open decision
- Send calendar event titles to Gemini, or only times? Default: times only.

## Rules
- Never put keys, tokens, passwords, account IDs, or private calendar links in this file.
