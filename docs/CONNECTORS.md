# Connector setup

Use an independent development account and clean checkout for integration development. The hosted application is the source of truth; a second instance must not synchronize against its production Google account.

## Google Calendar and Google Tasks

Google integration uses OAuth credentials stored privately in `.env`:

```text
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REFRESH_TOKEN=
GOOGLE_CALENDAR_ID=primary
TIMEZONE=America/Phoenix
```

[`scripts/google_auth.py`](../scripts/google_auth.py) requests Calendar read, event write, and Tasks scopes. Keep all resulting credentials private. [`scripts/check_google.py`](../scripts/check_google.py) checks the saved account's access; run it only when an account-level check is intended.

The current implementation reads event timing from the configured calendar and ignores cancelled, transparent, declined, and Between-tagged events. It retains real commitments that overlap Between blocks. Unrelated event titles are not requested for planning.

The deterministic plan is exported to Between-tagged Google Calendar events and one `Between · Today` Google Tasks list. Sync rewrites the app's outputs. Treat that list as app-managed, and never use a production account for test fixtures. Progress changes queue synchronization; startup and active-hour background jobs also refresh outputs.

Authenticated connector routes include:

- `POST /api/connectors/google/canvas/sync`
- `POST /api/connectors/google/tasks/sync`
- `POST /api/connectors/google/blocks/sync`

These routes can write real data. Do not invoke them merely to inspect the source.

## Canvas through Google Calendar

The active workflow imports assignments from a Google calendar named `canvas`, typically populated by a Canvas calendar subscription. Keep the subscription URL private. Configure a different calendar name with `CANVAS_CALENDAR_NAME` if needed.

This path uses the existing Google OAuth setup; no direct Canvas access token is required. Smart processing uses titles and due dates, preserves source metadata and user edits, and reuses its persisted processing decision on later imports. See [SMART-CANVAS.md](SMART-CANVAS.md).

## Legacy direct Canvas API

A direct adapter remains available with private `CANVAS_BASE_URL` and `CANVAS_ACCESS_TOKEN` configuration and `POST /api/connectors/canvas/sync`. It shares the processing/persistence path but uses its own external identifier namespace. Do not assume assignments from separate source namespaces will always reconcile.

## Gemini

Add `GEMINI_API_KEY` and optionally `GEMINI_MODEL` to the private `.env`. The project configuration uses `gemini-flash-lite-latest`. Without a configured key, local rules supply capture and intelligence fallbacks. Calendar-backed availability still requires Google access.

The credential-free `.env.example` lists local configuration fields; the README explains their roles. Never paste real `.env` values, authenticated URLs, or API responses containing private task data into repository documentation.
