#!/usr/bin/env bash
# Runs ON the server. Points the DuckDNS name at this server's current public IP.
# DuckDNS sees the IP the request comes from (ip= left empty), so no IP is needed here.
#
# Token: ~/.config/duckdns/token (chmod 600), saved by server-setup.sh or duckdns-set-token.
# Installed as /usr/local/bin/duckdns-update and run by cron every 5 minutes and at boot.
set -euo pipefail

NAME="${DUCKDNS_NAME:-pipbetween}"
TOKEN_FILE="${DUCKDNS_TOKEN_FILE:-$HOME/.config/duckdns/token}"
stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }

if [ ! -r "$TOKEN_FILE" ]; then
  echo "$(stamp) No DuckDNS token at $TOKEN_FILE. Run duckdns-set-token." >&2
  exit 1
fi
token=$(tr -d ' \t\r\n' < "$TOKEN_FILE")
if ! [[ "$token" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
  echo "$(stamp) The saved DuckDNS token is malformed (${#token} characters, want 36). Run duckdns-set-token." >&2
  exit 1
fi

# The URL (with the token) goes to curl on stdin (-K -), so the token never
# appears in the process list or in any log. Only the HTTP status and OK/KO are printed.
out=$(printf 'url = "https://www.duckdns.org/update?domains=%s&token=%s&ip="\n' "$NAME" "$token" \
  | curl -s --max-time 20 -w '\n%{http_code}' -K - || true)
unset token
body=$(printf '%s' "$out" | head -n1)
code=$(printf '%s' "$out" | tail -n1)
case "$body" in OK|KO) ;; *) body="no answer" ;; esac

echo "$(stamp) duckdns $NAME.duckdns.org: $body (HTTP ${code:-none})"
if [ "$body" = "KO" ]; then
  echo "KO means DuckDNS rejected the token or the name '$NAME' isn't on your DuckDNS account." >&2
fi
[ "$body" = "OK" ]
