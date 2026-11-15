# Roadmap reconciliation — Phase 1 review

Reviewed 2026-11-15 against the current source and the owner's nine-phase roadmap. This document contains no production host identifiers, private task data, or authenticated links.

## Repository and evidence

At the start of this milestone, local `main` and remote `origin/main` both pointed to `6bd613b` (README story refresh). Dashboard fixes are in `4ded95f`: restored question markup, missing-element guards in `renderQuestions()`, and frontend asset/cache version 5. No new repository is needed.

The owner reports that the hosted dashboard and remote iPhone capture were successfully tested after deployment, and that 157 tests passed. Source review is not a new live deployment verification. No production server, capture, cloud resource, or Google sync was invoked for Phase 1.

`HANDOFF-FULL.md` remains a private, untracked reference. The older tracked handoffs describe earlier project states; the updated short handoff points here for the reconciliation. `docs/POLISH.md` was absent, so a clearly labeled backlog has been created from the owner's current instructions rather than reconstructing an unavailable file.

## What exists, and what remains

| Phase | Present in source | Remaining work |
| --- | --- | --- |
| 1 — Story and demo | README narrative, architecture and stack, privacy boundaries, safe development/deployment instructions; demo script and honest asset placeholders | Owner approved documentation milestone; timed rehearsal and real privacy-reviewed screenshots/recording remain pending |
| 2 — Smart Canvas | `sync_canvas_calendar()` imports by stable external event ID; repeated import updates the same task. Removes a trailing bracketed course suffix, preserves due date, defaults new tasks to 45 minutes. A separate older direct-Canvas import path also exists. | No Gemini title/type processing or per-type estimates. Reimports overwrite task titles; no user-edit provenance. Calendar import's metadata stores only the date, not the original full title/event. Add original metadata and processing state non-destructively; handle both import paths. |
| 3 — Decomposition | `spread_sessions()` divides estimated work into sessions across days | Sessions are not subtasks. No parent/child schema, ordered steps, dependencies, next-step presentation, or parent completion logic. |
| 4 — Duplicates and quiet filing | Gemini capture reuses an open task with an exact case-insensitive title. Canvas matches by source/event ID. `someday` exists as an internal box, and the capture prompt discourages unnecessary questions. | No conservative semantic merge, cross-source reconciliation, retry idempotency, or merge provenance. Same-title matching ignores differing deadlines/source identity, so it can also overmatch. Someday still appears as Important and can receive sessions; full quiet filing is not implemented. |
| 5 — Ask Pip | Capture and follow-up question routes exist | No `/api/ask`, grounded read-only conversational context builder, or dashboard conversation input. |
| 6 — Explanations | Rule reasons, Gemini-proposed reasons, validation, plan cache (3 minutes), Gemini proposal cache (30 minutes), failure backoff | Gemini still chooses today's sessions. Move to deterministic scheduling first, then a grounded explanation-only layer with appropriate invalidation. Current shared HTTP timeout is 25 seconds per request, with model fallbacks; it is not a 10-second total AI budget. |
| 7 — Patterns | `time_logs` records minutes and timestamps; tasks retain skip count and latest skip date | No complete skip-event history, sufficiently sampled summaries, 14-day gating, accept/dismiss UI, or personalized suggestions. Time logging does not automatically learn estimates. |
| 8 — Live voice | HTTPS and a working text-capture path from iPhone dictation, per owner verification | No Gemini Live browser/server session, realtime audio, transcription UI, or final-transcript deduplication. Verify official docs, models, auth, pricing, compatibility before implementation. |
| 9 — Polish | Existing cozy styles and original Pip artwork; restored question section and defensive guard | See `POLISH.md`. No full accessibility/mobile/motion audit performed. The manifest and v5 service worker exist, but no service-worker registration was found in the current dashboard, so offline operation is not established. |

## Scheduling and progress caveats

The two-week planner currently reads `duration_minutes` without subtracting time logs. `gap_engine` and dashboard task metadata do use logged time to calculate remaining work. `log_task_time()` and `set_task_estimate()` do not clear the plan cache, and skip does not immediately sync the external calendars/tasks. These are integration gaps to address with focused tests in a later approved scheduling milestone, not behaviors to promise in the demo.

Current values are left untouched: two-week planning uses 7am–10pm, a 10-minute minimum block, up to a 60-minute daily session per task, a 240-minute day cap, and five-minute buffers. The window-suggestion engine has its own 15-minute minimum. Do not unify or change those preferences silently. The owner's recurring study/commitment block remains fixed unless they choose otherwise; personal event labels should stay out of public documentation.

## Authentication incident and follow-up investigation

The owner reports that a missing hosted phone-token file was manually initialized, restoring dashboard and Shortcut access. The permanent safeguard is still pending.

Source inspection shows why the existing assumption is unreliable:

1. `main()` calls `init_db()` without ensuring the phone token exists.
2. `Handler.is_authorized()` uses `bool(token) and ... get_or_create_phone_token()`. Requests without a supplied token short-circuit before creation.
3. `deploy/hosted-link.sh` calls health without a token and assumes that initializes the file; it does not.
4. Remote `printf` substitutes `cat` output without a required non-empty-file check. A missing file can therefore produce an empty-token link with a success message.

Proposed separate reliability fix: initialize before serving requests, ensure atomic creation and stable permissions under concurrent calls, validate the persisted token before link generation, fail before clipboard writes when initialization/reading fails, and test restarts and invalid/missing files. Do not rotate an existing valid token during a normal start or link request. Changing live authentication or links needs a reviewed implementation and deployment approval.

The server's `log_message()` prints request text. Capture tokens in URL paths/query strings may therefore reach app logs; Caddy's lack of access logs does not prevent that. Redaction and error-output review remain pending. Treat logs as private. No secrets or token files were read for this milestone.

## Validation and approval boundary

Phase 1 adds source/HTML regression checks that detect missing referenced IDs (including both question elements), duplicate IDs, and inconsistent frontend versions or missing cached assets. Token tests cover a missing or empty file, stable explicit initialization, and the health-request short circuit using temporary directories only.

All 166 tests passed (157 existing + 9 new) with external HTTP and socket access blocked. Whitespace and local Markdown-link checks passed. These tests are not a real-browser or iPhone rehearsal. No frontend assets changed, so the PWA remains v5. Review the README's Mermaid diagram in GitHub preview and rehearse `DEMO.md` with owner-approved data before submission.

The owner approved Phase 1 commit/push and proceeding to Phase 2. No Phase 1 deployment is needed. Keep deployment, publication, and infrastructure changes behind explicit approval. No AI co-author trailer or private handoff/data files may be staged.
