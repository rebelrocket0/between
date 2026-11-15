# Between — current handoff

## Submission and repository status

Between has been submitted to **SunHacks 2026**. The developer confirms the hosted application is working. Implementation preservation and portfolio documentation are post-submission repository work; commit dates have not been backdated.

The completed implementation is preserved separately from the documentation update. See [README](../README.md), [feature status](ROADMAP-STATUS.md), and [release validation](RELEASE-REVIEW.md). `HANDOFF-FULL.md` is private and ignored by Git, Docker, and deployment source transfer.

## Current implementation

- Typed and iPhone Shortcut/dictation capture, shared hosted state, retry receipts, and clarification questions.
- Smart Canvas titles/types/estimates with provenance, stable imports, and preserved edits/progress.
- Persistent ordered steps for eligible new large tasks, leaf-only execution, and parent progress aggregation.
- Conservative normalized-title duplicates, source identity checks, quiet Someday filing and activation.
- Read-only Ask Pip, deterministic scheduling, supported explanation facts, and evidence-gated observations with accept/dismiss state.
- Google Calendar commitment filtering, Between work blocks, Google Tasks output, queued progress refreshes, and scheduled synchronization.
- Additive SQLite migrations, v6 frontend assets/cache source, temporary-data tests, and request-log URL/body redaction.

## Validation and boundaries

261 backend tests and 8 synthetic frontend runtime checks passed, with zero failures. Python/JavaScript syntax, shell syntax, and migration/persistence checks passed. Backend validation blocked external connections. Browser coverage, offline PWA operation, and performance benchmarks are not established by these checks.

The hosted instance is the source of truth. Do not start a local instance using production credentials, change the database, rotate the working device token, deploy, restart AWS, or create billable infrastructure without an explicit task authorizing that work. Local development uses an independent clean checkout and test account.

The prototype remains single-user. Gemini Live and automatic behavioral rescheduling are absent. Service-worker registration is not established. Fresh-host token initialization/link validation and cross-service sync recovery remain documented limitations; do not casually rotate a valid token to investigate them.

Never print, commit, or paste credentials, tokens, personal task data, private links, SSH keys, or private infrastructure identifiers. Use `/usr/bin/python3` on the development Mac. Commits have no AI co-author trailers.
