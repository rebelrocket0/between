# Between

A local-first personal capture system. Version 0.1 stores text captures, routes them into tasks or notes, keeps a review queue, and shows a local dashboard.

## Start It

```bash
cd ~/projects/between
/usr/bin/python3 server.py
```

Then open the URL printed by the server, usually:

```text
http://127.0.0.1:8765
```

## What Works Now

- Capture typed thoughts, reminders, notes, and tasks.
- Store every original capture in SQLite.
- Route captures into tasks or notes using local rules.
- Keep uncertain items in Review.
- Mark tasks complete.
- Convert Review items into tasks or notes.
- Suggest simple planning slots for open tasks.
- Show setup status for Canvas and Google Calendar.
- Import Canvas assignments when local credentials are configured.
- Cache the dashboard in the browser after first load.
- Queue captures locally in the browser if the server is temporarily unavailable.

## Phone Access

Same-Wi-Fi phone access:

```bash
scripts/start-phone.sh
```

Then open the app on your Mac, go to `Phone`, and use one of the phone URLs shown there.

More detail: [docs/PHONE_SETUP.md](docs/PHONE_SETUP.md)

## Connectors

Copy `.env.example` to `.env`, fill in the connector values you want, restart the app, then use the `Connectors` tab.

More detail: [docs/CONNECTORS.md](docs/CONNECTORS.md)

## What Comes Next

1. Add Ollama routing for smarter classification.
2. Add voice notes through local transcription.
3. Add Google Calendar event creation after approval.
4. Add offline phone sync beyond same-Wi-Fi access.

## Privacy Model

The app code is separate from private data. The database lives in `data/life_brain.sqlite`, which is ignored by Git.
Connector credentials live in `.env`, which is also ignored by Git.
