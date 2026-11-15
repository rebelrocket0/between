#!/usr/bin/env bash
# Runs ON the server. Points the DuckDNS name at this server's current public IP.
# DuckDNS sees the IP the request comes from (ip= left empty), so no IP is needed here.
#
# Token: ~/.config/duckdns/token (chmod 600), typed once by server-setup.sh. Never in git.
# Installed as /usr/local/bin/duckdns-update and run by cron every 5 minutes and at boot.
set -euo pipefail

NAME="${DUCKDNS_NAME:-pipbetween}"
TOKEN_FILE="${DUCKDNS_TOKEN_FILE:-$HOME/.config/duckdns/token}"

if [ ! -r "$TOKEN_FILE" ]; then
  echo "No DuckDNS token at $TOKEN_FILE. Run server-setup.sh again." >&2
  exit 1
fi

# The URL (with the token) goes to curl on stdin (-K -), so the token never
# appears in the process list or in any log. Only DuckDNS's OK/KO is printed.
result=$(printf 'url = "https://www.duckdns.org/update?domains=%s&token=%s&ip="\n' \
  "$NAME" "$(cat "$TOKEN_FILE")" | curl -s --max-time 20 -K -)

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) duckdns $NAME.duckdns.org: ${result:-no answer}"
[ "$result" = "OK" ]
