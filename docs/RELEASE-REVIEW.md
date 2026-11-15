# Submission release review — 2026-11-15

This review supersedes the older implementation-status statements in the handoffs and Phase 2 notes. Branch: `development/pip-intelligence`. Historical review: the implementation was uncommitted and no deployment was performed by the reviewer at that point. The developer subsequently confirmed submission and a working hosted application. Repository preservation and portfolio documentation were completed after submission; the commands below remain a historical operational plan, not evidence of execution.

## Implemented and tested offline

- Existing typed/Shortcut JSON capture and token authentication; iPhone dictation enters through the same capture path. Retry receipts prevent repeated submissions from creating extra work.
- Dashboard refresh, ordered task steps, parent progress, completion, time logging, skips, and Someday activation.
- New tasks estimated at 90+ minutes receive persistent steps, with validated Gemini output or deterministic fallback. Existing progress is preserved; old tasks are not bulk rewritten.
- Conservative normalized-title duplicate matching, including Canvas/capture matches; ambiguous matches and distinct Canvas IDs stay separate. Low-urgency tasks can be quietly filed.
- Read-only Ask Pip, constrained to recorded facts; supported scheduling explanations. The deterministic planner now controls placement; Gemini selects supported explanation facts.
- Behavioral observations gated by sample counts and at least two weeks of evidence. Accepting an observation does not automatically change scheduling preferences.
- Google Calendar busy-time filtering excludes Between's own blocks, preserving real overlapping commitments. Calendar and Tasks exports use the ordered leaf plan; progress queues a refresh.
- Smart Canvas titles, assignment types, estimates, persisted processing, source deadline refresh, and preservation of existing edits/logs.

## Critical fixes in this review

1. Follow-up deadline answers now update existing child steps and invalidate the plan.
2. Ask Pip excludes tasks and parent families skipped for today.
3. Calendar/Tasks sync builds the replacement plan before clearing existing output; planning failure leaves Google output untouched.
4. Git, Docker context, and deployment exclude the private full handoff. Git ignores the entire local data directory and PEM keys; deployment excludes prefixed client-secret filenames too.

## Validation and limits

- **261 Python tests passed; 0 failures/errors/skips.** External HTTP and socket connections were blocked. Temporary databases and mocked integrations were used.
- **8 frontend runtime checks passed** using the actual dashboard JavaScript in a synthetic DOM, including full dashboard loading, task/step rendering, escaping, Ask Pip, and capture retries. This is not a visual browser test.
- Python syntax: 31 files. JavaScript syntax: dashboard, service worker, and runtime harness. Shell syntax and `git diff --check`: passed.
- Secret scan: no known local credential values or common credential signatures found in tracked/candidate text files. No local databases or credential files are tracked. `HANDOFF-FULL.md` contains private infrastructure details and must stay ignored.
- Migrations add columns, tables, and indexes; legacy migration/restart fixtures preserve task IDs, completion, estimates, and logs. **The previous app is not a safe semantic rollback once steps exist:** it does not understand parent/child planning, even though SQLite can read the additive schema.
- Dockerfile includes all Python modules; Compose retains `data/`, read-only `.env`, and Caddy volumes. Docker is unavailable on this Mac, so an image build/run has not been verified here.
- Frontend assets and service-worker cache are v6. The worker avoids API/token URLs, but registration is absent; offline operation is not a release claim. Hard-reload after deployment.
- Gemini Live/browser voice is absent. Use the existing iPhone dictation Shortcut. Broad semantic deduplication and automatic behavioral rescheduling are not implemented.
- Existing hosted token must be present before release; startup still does not proactively initialize it. The command below fails before stopping anything if the token is absent. Do not rotate the working token.
- Live Gemini, OAuth permissions, phone delivery, browser rendering, and asynchronous Google refresh require the production rehearsal below. Sync is best effort, not a transaction across Google services; an external API failure during writes can still leave partial output.

## Exact deployment sequence — only after approval

Use the already approved `BETWEEN_HOST`, `BETWEEN_DOMAIN`, and `BETWEEN_SSH_KEY` settings read by `deploy/common.sh`. Do not copy local configuration or databases. The following command creates a private backup on the existing host and briefly stops only the app for a consistent database snapshot. Caddy and its certificate volumes stay in place. The trap restarts the existing app even if backup fails.

```bash
cd ~/projects/between
bash -euo pipefail <<'LOCAL'
source deploy/common.sh
remote 'bash -se' <<'REMOTE'
set -euo pipefail
cd /opt/between
test -s .env
test -s data/phone_capture_token
test -s data/life_brain.sqlite
container_id=$(sudo docker compose ps -q between)
test -n "$container_id"
previous_image=$(sudo docker inspect --format '{{.Image}}' "$container_id")
release_stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_dir="/opt/between-backups/$release_stamp"
sudo install -d -m 700 /opt/between-backups "$backup_dir"
sudo docker image tag "$previous_image" "between-rollback:$release_stamp"
trap 'sudo docker compose start between >/dev/null' EXIT
sudo docker compose stop between
sudo tar -C /opt/between -czf "$backup_dir/between.tar.gz" .
sudo chmod 600 "$backup_dir/between.tar.gz"
sudo tar -tzf "$backup_dir/between.tar.gz" >/dev/null
printf 'Backup verified: %s/between.tar.gz\n' "$backup_dir"
REMOTE
deploy/deploy.sh
status=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "https://$DOMAIN/api/health")
test "$status" = 401
printf 'Unauthenticated HTTPS health: 401 as expected\n'
remote 'cd /opt/between && sudo docker compose exec -T between python -' <<'PY'
import sqlite3
db = sqlite3.connect('file:/app/data/life_brain.sqlite?mode=ro', uri=True)
assert db.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
assert not db.execute('PRAGMA foreign_key_check').fetchall()
print('Hosted database integrity: OK')
PY
LOCAL
```

Record the printed backup path privately. The archive contains the hosted database, token, OAuth configuration, and previous source; never download it into the repository or expose its contents. The old image is retained under the printed timestamp. Ordinary deployment preserves the live mounted data, credentials, and Caddy volumes. Never use `--with-data`, `push-env.sh`, `docker compose down -v`, or a local database copy for this release.

If deployment fails, stop before rehearsal or submission. Inspect service status privately. Before any rollback, preserve the current hosted data too. Do not run the old image against new parent/child data or restore the old database over new captures without explicit approval; restoring the snapshot can discard post-backup work. No rollback or data restoration is authorized by this plan.

## One real end-to-end rehearsal after deployment

1. Hard-reload the authenticated HTTPS dashboard; confirm old tasks and logged time remain. Check desktop and iPhone show the same data. Keep the private link and Shortcut action off recordings.
2. From iPhone cellular, dictate one clearly labeled demo task with a future deadline and a 90-minute estimate. Confirm one parent appears, with ordered steps totaling the estimate. Retry the same Shortcut once; confirm it still appears once.
3. Ask Pip what to do in 20 minutes. Check its response against the actual free window and next step. Answer any follow-up deadline and confirm the steps use that date.
4. Log a few minutes on the first step, complete it, and verify the next step appears. Choose Not today on that next step; confirm today's plan and Ask Pip respect it.
5. Allow the queued refresh or use the existing Google sync controls. Check Calendar and `Between · Today` match the app, without parent double-counting or overlap with commitments. Repeat Canvas sync and verify an existing assignment stays single and retains edits/progress.

Do not delete rehearsal data without approval. Do not fake behavioral history for the demo. The developer later authorized implementation/documentation commits and GitHub pushes after submission. Repository visibility changes and production operations are separate actions; this publication did not perform them.
