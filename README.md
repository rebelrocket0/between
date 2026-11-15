# Between

**Turn the gaps in your day into done things.**

You have 25 minutes before class. A reading due tonight. A quiz on Friday. And a reminder you told yourself you would remember.

The time is there, but figuring out what to do with it takes time too. A calendar shows where you need to be. A to-do list shows what you owe. You still have to connect the two.

Between connects them.

Built as a solo project for **Sun Hacks 2026**, Between turns scattered thoughts, school deadlines, and the free spaces in a student's calendar into a plan they can act on. Tell it what's on your mind, tell it how much time you have, and take the next small step.

## From “I need to…” to “I did”

Imagine leaving class and remembering three things at once:

> “Read chapter four for 20 minutes, start my reflection paper before Friday, and email my professor.”

Type it into Between or dictate it through an iPhone Shortcut. Gemini separates the thought into tasks and asks for clarification when it needs more information. Google Calendar supplies the busy times, and a connected Canvas calendar brings in school deadlines.

Between then spreads the work across the next two weeks, fitting sessions into available time before each deadline. Gemini helps choose today's sessions and explains why they belong there. A rule-based planner checks those suggestions and provides a fallback when Gemini is unavailable.

The result shows up where you already look: **“Between:” blocks in Google Calendar**, a **“Between · Today” list in Google Tasks**, and a dashboard that answers a smaller, more useful question:

**What can I do with the time I have right now?**

## A little help from Pip

Pip is Between's original companion character: a small, cozy presence beside the plan. When a thought needs a little more detail, Pip has a question. When you have a gap, the dashboard helps you find something that fits.

Tasks appear in three groups: **Urgent & important**, **Urgent**, and **Important**. You can log time, mark work complete, or say **“Not today”** and let the planner adjust. The point is to make getting started feel manageable, even when the whole week doesn't.

## What works today

- **Capture by text or voice.** Brain-dump in the dashboard or send dictated thoughts through an iPhone Shortcut.
- **Turn thoughts into tasks.** Gemini separates captures into actionable items and follow-up questions.
- **Plan around real commitments.** Google Calendar busy times keep work sessions out of class and other events.
- **Bring in school deadlines.** Assignments arrive through a Google Calendar named `canvas`.
- **Spread work before it's due.** A two-week planner schedules sessions, with reasons for today's choices.
- **Find a task for your gap.** Choose how many minutes you have and see work that fits.
- **Keep the plan close.** Sync to Google Calendar and Google Tasks, and use the installable web app on your phone.

Between is deployed to AWS with HTTPS, and iPhone voice capture is working. The latest reported test run passed **157 tests**.

## Under the hood

The dashboard uses vanilla JavaScript, HTML, and CSS. A Python standard-library HTTP server handles capture, planning, and integrations, with SQLite storing tasks and captures. Gemini handles brain-dump interpretation and today's planning suggestions; Python rules validate the plan and keep scheduling available when the model cannot respond.

The hosted version runs on AWS EC2 with Docker and Caddy for HTTPS. Voice capture uses Apple's Shortcuts app to send dictated text to the same capture endpoint as the dashboard.

## Run locally

On the development Mac:

```bash
cd ~/projects/between
cp .env.example .env
```

Configure the integrations you want in `.env`. Gemini uses `GEMINI_API_KEY` and `GEMINI_MODEL` (currently `gemini-flash-lite-latest`). Google integrations use `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REFRESH_TOKEN`; the OAuth helper is `scripts/google_auth.py`. Canvas deadline import uses the Google calendar named `canvas` by default, configurable with `CANVAS_CALENDAR_NAME`.

Start the server with Apple Python:

```bash
/usr/bin/python3 server.py
```

Open **http://127.0.0.1:8765**.

Use one running instance per Google account: running the local and hosted servers together can cause their calendar and task syncs to overwrite each other's plans.

For phone setup on home Wi-Fi, see [Phone Setup](docs/PHONE_SETUP.md). For the hosted setup, HTTPS, and phone access away from home, see [Deployment](docs/DEPLOY.md).

## Tests

```bash
for f in tests/test_*.py; do /usr/bin/python3 "$f"; done
```

Tests mock Gemini and Google integrations and disable automatic Google Tasks sync so they do not write test tasks to the real account.

## Data and privacy

Captures and tasks live in SQLite on the machine running Between. Credentials stay in `.env`; the database and phone capture token stay in `data/`. These private files are excluded from Git.

Gemini receives task information and calendar time ranges for planning, **not calendar event titles**. Google receives the task list and calendar blocks created by sync. Hosted access uses a private token-bearing link; treat that link like a password.

## What's next

Next comes richer task breakdowns, better Canvas assignment titles and estimates, and merging duplicate tasks across captures and school deadlines. Longer term, Between aims to support conversational planning, live voice, and estimates informed by the time you actually spend on work.

For now, it starts with the gap you already have.
