# Deploying Between

This guide describes the existing EC2 + Docker Compose + Caddy deployment. It uses placeholders, not the owner's host, IP address, region, or SSH key location. The developer confirms the hosted application is working. The repository publication updated documentation only and did not execute deployment commands.

The hosted server is the single source of truth. Keep the production Mac server stopped. Do not create billable resources, change cloud settings, replace hosted data, or deploy without the owner's approval.

## Existing-server prerequisites

The existing Ubuntu host must have Docker Compose, `/opt/between/.env`, and a persistent `/opt/between/data/` directory. DNS must point the approved domain to the host, and ports 80/443 must reach Caddy. Restrict SSH access to the operator's approved source address where practical. Keep the app's port internal to the Docker network.

On the Mac, configure these placeholders in your own shell with the approved deployment details:

```bash
export BETWEEN_DOMAIN='your-domain.example'
export BETWEEN_HOST='your-approved-server'
export BETWEEN_SSH_KEY='/path/to/your/private-key.pem'
```

The helpers read these variables through `deploy/common.sh`. Compose separately reads `DOMAIN` on the server; set `DOMAIN` and `APP_URL` to the correct domain in the server `.env`. Set `BETWEEN_BEHIND_PROXY=1`; `.env` overrides inherited app settings, so it must not disable that flag.

The server `.env` holds Gemini and Google credentials. Keep it mode 600 and `data/` mode 700, owned by the app's mapped user. Never paste either file's contents, phone tokens, SSH keys, or private links into chat, Git, or demo recordings.

## Updating the existing application

After reviewing the diff, passing tests, and obtaining deployment approval, run from the repository root:

```bash
deploy/deploy.sh
```

The script copies source, excluding `.env`, `data/`, `.git/`, and common credential files; rebuilds the app; starts Compose services; and checks HTTPS health. Review the source tree before running it: untracked documentation can also be copied because deployment uses rsync rather than Git.

**Do not use `--with-data` without explicit approval.** It stops the app and replaces the hosted database with the local copy. Ordinary code updates must preserve the server's data and token.

The credentials helper `deploy/push-env.sh` is for intentional configuration transfer. Do not use it for normal source updates or use its force option without reviewing the configuration change.

## Private links and the known token issue

After the hosted token has been initialized and confirmed valid, the Mac helpers copy links directly to the clipboard:

```bash
deploy/hosted-link.sh dashboard
deploy/hosted-link.sh shortcut
```

Open the dashboard link once per trusted browser. Paste the Shortcut link into its POST action, using JSON `{text: Dictated Text, source: "phone"}` and `Content-Type: application/json`. Never show the URL action or clipboard while recording.

For a newly provisioned host, confirm the persisted phone token exists before using these helpers. Fresh-host safeguards remain limited:

- `main()` initializes the database but does not ensure the token exists.
- Authentication short-circuits when a request supplies no token. An unauthenticated health request returns 401 without calling `get_or_create_phone_token()`.
- The link helper relies on that health request to create the file, then reads it remotely. Its remote `printf` can still exit successfully after `cat` fails, yielding an empty-token link and a misleading clipboard message.

A 401 proves the API requires authentication; it does **not** prove that the token file exists. Do not repeatedly rotate a working token to diagnose this. Rotation invalidates all existing browser and Shortcut links. Follow-up work should ensure initialization at startup, validate the persisted token before copying a link, fail without touching the clipboard on error, and test persistence and concurrent initialization. This documentation describes the limitation without changing production authentication.

## Verification after an approved deployment

Use the approved domain from your shell. This check prints only the status code:

```bash
curl -s -o /dev/null -w '%{http_code}\n' "https://$BETWEEN_DOMAIN/api/health"
```

Expect **401** without a token. An unauthenticated 200 requires investigation, even though the current deploy script accepts either status as a liveness result.

Then verify manually:

1. HTTPS loads with a valid certificate, and an unauthenticated browser receives no task data.
2. A valid private dashboard link loads tasks, removes `?token=` from the address bar, and survives a reload.
3. The desktop and iPhone show the same hosted data.
4. One clearly labeled demo capture sent from iPhone cellular appears once in Between.
5. Following a sync, the planned items appear in Google Calendar and Google Tasks.
6. Skipping changes today's dashboard plan; logging time updates the task's logged and remaining minutes.

These actions create or modify real data. Use owner-approved demo tasks and never replace the database for a rehearsal. Delete nothing without approval.

For a failure, inspect service status over SSH. Request logging now omits URLs and bodies, with regression coverage for token-bearing paths. Treat other application and connector error output as potentially sensitive. Do not paste raw logs into shared channels.

## Provisioning another host

Creating another instance is outside the normal update procedure and requires explicit approval. The initial `deploy/setup.sh` and server-side setup/DuckDNS scripts contain deployment-specific defaults; they are not a generic provisioning package. Review those defaults before using them elsewhere. Do not assume the Mac environment overrides every server-side domain setting.

An approved setup needs a chosen region, DNS, restricted SSH, persistent storage, secret configuration, HTTPS, a budget alert, and a verified token initialization path. Secrets Manager integration is not implemented; secrets currently reside in the private server `.env`.

Stopping an EC2 instance does not necessarily stop storage or other account charges. Review the actual account resources before changing or deleting infrastructure. This guide does not quote pricing or authorize resource changes.
