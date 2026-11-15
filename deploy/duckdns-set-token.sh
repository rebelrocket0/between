#!/usr/bin/env bash
# Runs ON the server. Saves your DuckDNS token without a hidden prompt:
#
#   umask 077 && nano ~/duckdns-token.txt     # paste the token, Ctrl+O, Return, Ctrl+X
#   duckdns-set-token                         # (installed as /usr/local/bin/duckdns-set-token)
#
# It reads the file, removes spaces/newlines, DELETES the file right away, checks the token's
# shape, saves it to ~/.config/duckdns/token (chmod 600), updates DuckDNS once, and makes sure
# the cron job that keeps the name pointed here exists. The token is never printed.
set -euo pipefail

SRC="${1:-$HOME/duckdns-token.txt}"
DIR="$HOME/.config/duckdns"

if [ ! -f "$SRC" ]; then
  echo "No file at $SRC. Make it with:  umask 077 && nano $SRC" >&2
  exit 1
fi
token=$(tr -d ' \t\r\n' < "$SRC")
rm -f "$SRC"   # gone before anything else can fail
echo "Read and deleted $SRC."

if ! [[ "$token" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
  echo "That isn't a DuckDNS token: expected 36 characters like xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" >&2
  echo "(lowercase letters a-f, digits, 4 dashes); got ${#token} characters. Nothing saved." >&2
  echo "Copy it from the 'token' line at the top of https://www.duckdns.org after signing in." >&2
  exit 1
fi

mkdir -p "$DIR"
chmod 700 "$DIR"
(umask 077; printf '%s' "$token" > "$DIR/token")
unset token
echo "Saved to $DIR/token (chmod 600)."

(crontab -l 2>/dev/null | grep -v duckdns-update || true
 echo "*/5 * * * * /usr/local/bin/duckdns-update >> $DIR/update.log 2>&1"
 echo "@reboot sleep 30 && /usr/local/bin/duckdns-update >> $DIR/update.log 2>&1") | crontab -
echo "Cron keeps the name pointed here every 5 minutes and after reboots."

/usr/local/bin/duckdns-update
