# Connectors

Connectors are optional. The local brain keeps working without them.

## Canvas

1. Copy `.env.example` to `.env`.
2. Add your Canvas base URL, for example:

```text
CANVAS_BASE_URL=https://your-school.instructure.com
```

3. Add a Canvas access token:

```text
CANVAS_ACCESS_TOKEN=...
```

4. Restart the app.
5. Open `Connectors` and click `Sync Canvas`.

Canvas assignments import as School tasks. Existing imported assignments update instead of duplicating.

## Google Calendar

Google Calendar needs OAuth credentials:

```text
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
GOOGLE_CALENDAR_ID=primary
TIMEZONE=America/Phoenix
```

Once configured, `Plan` can use Google free/busy data to suggest task slots around real calendar events.

The first Google Calendar connector is read/free-busy only. Creating calendar events should stay manual approval until the planning flow feels reliable.

