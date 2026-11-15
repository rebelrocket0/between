# Between — current handoff (2026-11-15)

Read `AGENTS.md`, then this file and `docs/ROADMAP-STATUS.md`. The owner's newest nine-phase roadmap supersedes the older build order. `docs/HANDOFF.md` is a historical checkpoint; its local-server, phone-setup, hosting, version, and test-count statements are stale. `HANDOFF-FULL.md` is a private untracked reference and must remain untracked.

## Current operational state

- The AWS-hosted server is the single source of truth. The owner reports working HTTPS, dashboard, Gemini capture, Calendar/Tasks sync, Canvas calendar import, follow-up questions, and remote iPhone dictation capture.
- Do not start a competing Mac server connected to production Google integrations. Tests use temporary data and mocked services.
- Dashboard/question guards and PWA asset/cache v5 are committed in `4ded95f`. At Phase 1 start, local and remote `main` matched `6bd613b`, the README story update.
- Never print or commit secrets, task data, authenticated links, private infrastructure details, or AI co-author trailers. Use `/usr/bin/python3` on this Mac.

## Phase 1 milestone approved

Updated README: motivation, student story, current features, architecture, stack, Gemini's actual role, isolated local development, deployment boundaries, privacy, roadmap, and explicit screenshot/demo placeholders.

New `docs/DEMO.md`: a timed two-minute story covering phone capture, structured tasks, a real follow-up, gaps around commitments, Google outputs, skip, and time logging. Rehearsal and recording are still pending; no fabricated screenshots or live results.

`docs/DEPLOY.md` now uses placeholders and separates approved existing-host updates from provisioning. It documents the token incident and data-copy prohibition. `docs/POLISH.md` was missing; a labeled backlog was created from the latest owner requirements.

Frontend contract checks and token failure-case tests were added without changing runtime code or frontend assets. Validation: all 166 tests passed (157 existing + 9 new) with external HTTP and socket access blocked. Whitespace and local Markdown-link checks also passed. Browser/phone rehearsal remains pending.

## Important implementation gaps

- Gemini currently chooses today's sessions subject to validation; Phase 6's explanation-only role is not implemented.
- Canvas import uses a default 45-minute estimate, overwrites titles on repeat sync, and lacks original-title metadata/user-edit provenance.
- No parent/subtask model, semantic merging, Ask Pip, supported behavioral insights, or Gemini Live implementation.
- Skip updates the dashboard plan; external sync follows separately. Logged time reduces dashboard/window remaining work but the two-week planner still reads full estimates. Do not claim automatic learning or instant calendar adjustment.
- Missing hosted token was manually initialized, per owner report. Startup does not ensure it exists; unauthenticated health requests short-circuit before creation, defeating the link helper's assumption. A separate startup/link-generation safeguard and request-log redaction need investigation. Do not rotate a working token casually.
- The v5 service worker exists, but registration was not found; offline behavior is unverified.

Detailed source reconciliation and follow-up acceptance criteria: `docs/ROADMAP-STATUS.md`.

## Next action

The owner approved Phase 1 commit/push and proceeding to Phase 2. Implement Smart Canvas processing incrementally, then wait for approval before deployment. No Phase 1 deployment is needed. Do not use `--with-data` without explicit approval to replace hosted data.

Planning hours, minimum session length, and fixed-versus-fillable commitments remain owner decisions. Keep busy-event titles out of Gemini context. Do not make the repo public or claim hackathon disclosure compliance without a separate review.
