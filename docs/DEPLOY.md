# Deploy Between to AWS (pipbetween.duckdns.org)

Server: EC2 t3.micro, Ubuntu 24.04, us-west-2. Login `ubuntu`, key `~/.ssh/between-key-3.pem`.
Every command below runs **on the Mac** in `~/projects/between` unless it says "on the server".
Never paste tokens, keys, or `.env` values into chat. Replace `SERVER_IP` with the instance's Public IPv4 address.

## 1. First login (checks the key works)

```bash
ssh -i ~/.ssh/between-key-3.pem ubuntu@SERVER_IP
```
Type `yes` if asked about the fingerprint (first time only), then `exit`.
"Connection timed out" usually means your IP changed: EC2 → Security Groups → the group's SSH rule → **My IP** → Save.

## 2. Set up the server + point the DuckDNS name

```bash
deploy/setup.sh SERVER_IP
```
It installs Docker and Compose, creates `/opt/between` (yours only) with `data/` and an empty `.env` (chmod 600),
then **asks for your DuckDNS token on the server** in a hidden prompt:
`Paste or type your DuckDNS token here (it stays hidden)`. That's the only place you type it.
It then points `pipbetween.duckdns.org` at the server (DuckDNS answers `OK`) and adds a cron job that keeps it pointed
every 5 minutes and after reboots (the IP changes if the instance is stopped and started).

Check from the Mac (should print the server's IP):
```bash
dig +short pipbetween.duckdns.org
```

## 3. Put the secrets in the server's `.env` (pick one)

**A. Copy from the Mac (easiest; nothing to type):**
```bash
deploy/push-env.sh SERVER_IP
```
Copies this Mac's `.env` over SSH, sets `APP_URL=https://pipbetween.duckdns.org` and `BETWEEN_BEHIND_PROXY=1`,
and prints only the key names.

**B. Type them on the server:**
```bash
ssh -i ~/.ssh/between-key-3.pem ubuntu@SERVER_IP
nano /opt/between/.env      # fill the empty lines; Ctrl+O, Return, Ctrl+X
exit
```

## 4. Deploy

```bash
deploy/deploy.sh SERVER_IP --with-data     # first time: also copies your tasks from the Mac
deploy/deploy.sh                           # later updates (uses pipbetween.duckdns.org)
```
It copies the project (never `.env`, `data/`, `.git`, keys), builds, starts the app and Caddy,
and waits until `https://pipbetween.duckdns.org/api/health` answers (401 = up and asking for the token).

## 5. Stop the Mac server

Both servers would otherwise sync to the same Google account and overwrite each other's
"Between:" blocks and "Between · Today" list. Stop the Mac one (Ctrl+C in its Terminal, or):
```bash
kill $(lsof -tnP -iTCP:8765 -sTCP:LISTEN)
```

## 6. Links (the token goes straight to the clipboard, never on screen)

```bash
deploy/hosted-link.sh dashboard   # open once in each browser (Mac + iPhone Safari)
deploy/hosted-link.sh shortcut    # paste into the Shortcut's Get Contents of URL
```

## Checklist

- [ ] `https://pipbetween.duckdns.org` loads in Safari with a **padlock** (click it: certificate from Let's Encrypt).
- [ ] `curl -s -o /dev/null -w '%{http_code}\n' https://pipbetween.duckdns.org/api/health` prints `401` (up, token required).
- [ ] Opening `https://pipbetween.duckdns.org` **without** the token: the dashboard shows "This device needs the Between link with ?token= once".
- [ ] Opening the `dashboard` link from step 6: tasks load, and `?token=` disappears from the address bar. Reload: still works.
- [ ] Mac and iPhone dashboards show the **same** tasks.
- [ ] iPhone on **cellular** (Wi-Fi off): run the Shortcut with the `shortcut` link → say a task → it appears on both dashboards.
- [ ] Google Calendar still shows "Between:" blocks and "Between · Today" updates (now from the server).

## Useful on the server

```bash
ssh -i ~/.ssh/between-key-3.pem ubuntu@pipbetween.duckdns.org
cd /opt/between
sudo docker compose ps                 # both running?
sudo docker compose logs --tail 50     # recent output (no tokens are logged)
sudo docker compose restart between
cat ~/.config/duckdns/update.log | tail -3   # DuckDNS OK/KO only
```

## Cost control

Stop the instance (EC2 → Instances → Instance state → **Stop**) when you don't need it; the cron job re-points
DuckDNS when it starts again. **Terminate** after the hackathon to end all charges. Budget alert: "between-monthly".
