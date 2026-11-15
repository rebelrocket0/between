# Phase 2 — Smart Canvas task processing

This design note records the original Smart Canvas milestone. The completed release also includes task decomposition and cross-source duplicate checks, summarized below and in the [README](../README.md). The developer confirmed a working hosted application and submission; repository documentation was refined afterward.

## Data available to this feature

The active connector reads assignment entries from the Google calendar named `canvas`. It has event titles and deadlines, not necessarily the assignment contents. The legacy direct Canvas connector is also supported through the same persistence path.

Only the assignment title is sent to Gemini. Descriptions, URLs, calendar identifiers, raw event metadata, and unrelated busy-event titles are not supplied. The prompt explicitly says assignment contents and requirements are unavailable. Richer content-based estimation is not claimed.

## New assignment flow

1. Match the stable source identifier in `external_items` (`cal:<event-id>` for the calendar connector, or the existing direct-Canvas identifier).
2. For a new task, try the configured Gemini model once with JSON MIME type and a response schema requiring exactly `title`, `assignment_type`, and integer `minutes`. The HTTP timeout is eight seconds; there is no model retry loop for Canvas processing.
3. Validate the exact shape, field types, action wording, length, type bounds, and retained academic context. Reject extra fields, duplicate JSON keys, boolean/fractional estimates, conflicting explicit assignment types, dropped subject/course/problem numbers, or new title vocabulary unsupported by the source and the small permitted action vocabulary.
4. If no key is configured, the title exceeds the model-input bound, the call fails, or validation rejects it, use deterministic rules. Long fallback display titles are capped at 240 characters; the full original remains in source metadata.
5. Commit the task and processing decision together. Store the method (`gemini` or `rules`), processor version, original title/source snapshot, and result. Recurring syncs and restarts reuse this record, including rule fallbacks; adding a key later does not automatically reprocess old work.

This validation deliberately favors conservative fallbacks over creative paraphrases. It cannot prove a model's reasoning correct, and estimates remain suggestions based on limited title information.

The request uses Gemini's [structured-output API](https://ai.google.dev/gemini-api/docs/structured-output) plus application validation. No live Gemini call was made to verify model output in this milestone.

## Types and estimate priors

| Type | Default minutes | Normal accepted range |
| --- | ---: | ---: |
| Quiz | 25 | 20–30 |
| Reading / lecture | 40 | 30–45 |
| Homework / problem set | 90 | 60–120 |
| Discussion | 30 | 20–60 |
| Reflection | 120 | 90–180 |
| Paper | 150 | 90–180 |
| Project | 180 | 90–360 |
| Exam preparation | 180 | 120–480 |
| Unknown | 45 | 10–180 |

An explicitly labeled duration in the source title can extend that type's range, within a global 5–480-minute limit. For example, a “90-minute Physics Lecture” receives 90 minutes. Points, course numbers, and problem numbers are not treated as durations. These priors are not claims about actual assignment requirements or a student's pace.

Deterministic, offline-tested examples:

| Source title | Task title | Minutes |
| --- | --- | ---: |
| M5, Assignment 3: Positive Psychology Lecture | Watch the Positive Psychology lecture | 40 |
| STP 421 Exam 2 | Study for STP 421 Exam 2 | 180 |
| Module 6 Discussion Board | Complete Module 6 discussion | 30 |
| Linear Algebra Problem Set 7 | Solve Linear Algebra problem set 7 | 90 |

Exams are treated as preparation work. In the completed release, eligible newly imported large tasks can receive persistent steps, then the planner allocates their leaf work. Existing tasks and recorded progress are preserved. Generated steps must not invent unseen study materials or requirements.

## Repeat imports, source changes, and edits

An existing task's title, estimate, status, time logs, and progress fields are never rewritten by either Canvas sync path. This protects manual edits without needing to infer whether a value was user-edited. Even an unedited generated title stays stable if the upstream title later changes; the latest source title is retained separately for reference.

Source deadlines and raw metadata refresh on sync. All-day dates stay unchanged; timestamp deadlines retain their original timestamp in metadata and use the configured time zone for the task's planning date. A changed deadline clears the plan cache. This does not force an immediate external Calendar/Tasks sync; the existing sync sequence remains in charge.

The existing unique source/identifier constraint prevents repeated external rows, and a shared import lock prevents duplicate processing/insertion by concurrent syncs in the single server process. Different source identifiers remain separate even when titles match. The completed release additionally attempts conservative normalized-title matching against unambiguous open roots. Distinct Canvas source IDs remain separate; Google Calendar IDs and direct Canvas IDs keep their existing namespaces.

## Additive migration and existing tasks

`init_db()` adds two nullable columns if absent:

- `tasks.assignment_type` — assignment classification.
- `external_items.processing_json` — processing provenance and initial source snapshot.

No tables are replaced, rows deleted, or IDs reassigned by this column migration. Repeated initialization is tested. The completed Pip release also adds parent/child fields and activity/receipt tables; earlier application code does not understand those semantics, so SQL readability alone is not a safe rollback guarantee.

Old Canvas tasks lack reliable edit provenance. On their next sync, the importer preserves their title and estimate exactly, assigns a type from rules only if missing, and records `legacy-preserved` provenance without a Gemini call. They are not bulk rewritten or re-estimated. The original source snapshot for such rows begins with the first Phase 2 sync; older details that the previous importer discarded cannot be reconstructed.

The same conservative path handles damaged or missing processing metadata for an existing task. The feature does not attempt to remove pre-existing duplicate tasks.

## Files and packaging

- `canvas_processing.py`: pure cleanup, classification, estimate priors, prompting, and validation.
- `server.py`: additive columns, bounded Gemini request, shared persistence, both connector adapters, and plan-cache invalidation.
- `Dockerfile`: copies the new module into the existing image.
- `tests/test_canvas_processing.py`, `tests/test_smart_canvas_import.py`, and the existing Canvas import test: offline regression coverage.
- README and handoff/status documents: updated implementation status and review instructions.

That original milestone changed no frontend assets. The completed Pip release uses v6 frontend assets and cache source, ordered steps, and authenticated Pip endpoints. No new service or package dependency is required; offline operation remains unverified.

## Validation and manual review

The full suite result is recorded in `docs/HANDOFF-short.md`. Tests use temporary databases and mocked Google/Gemini calls, with HTTP and socket access blocked during the full validation run. Coverage includes the example transformations, source metadata, stable IDs, repeat/concurrent imports, changed deadlines, explicit durations, user titles/estimates, completed tasks/time logs, distinct same-title assignments, invalid output, timeout fallback, restart persistence, and repeated migration from the old schema.

Safe review now, without contacting production:

```bash
/usr/bin/python3 -m unittest discover -s tests -p 'test_canvas_processing.py' -v
/usr/bin/python3 -m unittest discover -s tests -p 'test_smart_canvas_import.py' -v
```

After deployment is explicitly approved, use an owner-approved demo assignment/feed and the authenticated hosted app:

1. Import one genuinely new source item and inspect its actionable title, type in `/api/state`, estimate, and original source metadata in a private operator view. There is no new provenance dashboard in this phase; do not expose database contents or tokens in a recording.
2. Repeat sync and reload. Confirm the same task appears once and retains its title/estimate.
3. Change the source deadline; sync again and confirm the local planning date updates without losing the task.
4. Change an estimate through the existing estimate action, log time, and mark a demo task done. Sync and verify these values remain. Title-edit preservation is covered by controlled temporary-database tests; no title-edit UI is added here.
5. Check a pre-existing imported task: its old title/estimate should remain, with no automatic bulk enrichment.
6. For a real failure rehearsal, use a separate isolated test account/configuration. Do not break the production Gemini key or rotate auth tokens to test fallbacks.

Do not use `--with-data`, start a competing production-connected local server, or deploy this phase before approval.
