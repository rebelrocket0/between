#!/usr/bin/env bash
# Runs ON the server (Ubuntu 24.04), once. Started from the Mac by deploy/setup.sh.
#   1. Installs Docker + Compose
#   2. Creates /opt/between (yours only) with data/ and an empty .env (chmod 600)
#   3. Asks for your DuckDNS token (hidden), stores it in ~/.config/duckdns/token (chmod 600)
#   4. Points pipbetween.duckdns.org at this server and keeps it pointed (cron)
# Safe to run again: it skips what's already done and never overwrites .env or the token.
set -euo pipefail

APP_DIR=/opt/between
DUCKDNS_DIR="$HOME/.config/duckdns"

echo "== 1/4 Docker"
if ! command -v docker >/dev/null 2>&1 || ! sudo docker compose version >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io docker-compose-v2 rsync curl
fi
sudo systemctl enable --now docker >/dev/null
sudo usermod -aG docker "$USER"   # takes effect on your next SSH login
sudo docker compose version

echo "== 2/4 $APP_DIR"
sudo mkdir -p "$APP_DIR/data"
sudo chown -R "$USER:$USER" "$APP_DIR"
chmod 750 "$APP_DIR"
chmod 700 "$APP_DIR/data"
if [ ! -f "$APP_DIR/.env" ]; then
  (
    umask 077
    cat > "$APP_DIR/.env" <<'EOF'
# Between on the server. chmod 600. Never commit or paste these values.
# Fill the empty ones with: nano /opt/between/.env   (or copy from the Mac with deploy/push-env.sh)
GEMINI_API_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REFRESH_TOKEN=
GEMINI_MODEL=gemini-flash-lite-latest
TIMEZONE=America/Phoenix
APP_URL=https://pipbetween.duckdns.org
BETWEEN_BEHIND_PROXY=1
EOF
  )
  echo "Created $APP_DIR/.env (empty secrets, chmod 600)."
else
  echo "$APP_DIR/.env already exists; left as is."
fi
chmod 600 "$APP_DIR/.env"

echo "== 3/4 DuckDNS token"
sudo install -m 755 /tmp/between-setup/duckdns-update.sh /usr/local/bin/duckdns-update
sudo install -m 755 /tmp/between-setup/duckdns-set-token.sh /usr/local/bin/duckdns-set-token
mkdir -p "$DUCKDNS_DIR"
chmod 700 "$DUCKDNS_DIR"
TOKEN_SHAPE='^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
if [ ! -s "$DUCKDNS_DIR/token" ]; then
  echo "Copy your token from https://www.duckdns.org (the 'token' line at the top, after you sign in)."
  read -r -s -p "Paste or type your DuckDNS token here (it stays hidden), then press Return: " token
  echo
  token=$(printf '%s' "$token" | tr -d ' \t\r\n')
  if ! [[ "$token" =~ $TOKEN_SHAPE ]]; then
    echo "That isn't a DuckDNS token (got ${#token} characters; want 36 like xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)." >&2
    echo "Nothing saved. If pasting into a hidden prompt keeps failing, use the file method instead:" >&2
    echo "  ssh in, then:  umask 077 && nano ~/duckdns-token.txt   (paste, save)   then:  duckdns-set-token" >&2
    exit 1
  fi
  (umask 077; printf '%s' "$token" > "$DUCKDNS_DIR/token")
  unset token
  echo "Saved to $DUCKDNS_DIR/token (chmod 600)."
else
  echo "DuckDNS token already saved; left as is."
fi
chmod 600 "$DUCKDNS_DIR/token"

echo "== 4/4 Point pipbetween.duckdns.org here"
if /usr/local/bin/duckdns-update; then
  echo "DuckDNS says OK."
else
  echo "DuckDNS did not say OK. Check the token (rm $DUCKDNS_DIR/token and run again)." >&2
  exit 1
fi
(crontab -l 2>/dev/null | grep -v duckdns-update || true
 echo "*/5 * * * * /usr/local/bin/duckdns-update >> $DUCKDNS_DIR/update.log 2>&1"
 echo "@reboot sleep 30 && /usr/local/bin/duckdns-update >> $DUCKDNS_DIR/update.log 2>&1") | crontab -
echo "Cron keeps the name pointed here every 5 minutes and after reboots."

my_ip=$(curl -s --max-time 10 https://checkip.amazonaws.com || true)
echo "This server's public IP: ${my_ip:-unknown}"
echo "Setup done."
