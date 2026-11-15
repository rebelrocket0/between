#!/usr/bin/env bash
# Run ON THE MAC:  deploy/hosted-link.sh dashboard|shortcut [--new-token]
# Copies a hosted link to the Mac clipboard. The token goes from the server straight into the
# clipboard and is never shown on screen.
#   dashboard  https://pipbetween.duckdns.org/?token=…   open once per device; the page keeps it
#   shortcut   https://pipbetween.duckdns.org/api/capture/…   for the iPhone Shortcut
#   --new-token  make a new server token first (old links and Shortcut URL stop working)
set -euo pipefail
cd "$(dirname "$0")/.."
KIND="${1:-}"
NEW=0
[ "${2:-}" = "--new-token" ] && NEW=1
case "$KIND" in dashboard|shortcut) ;; *) echo "Usage: deploy/hosted-link.sh dashboard|shortcut [--new-token]" >&2; exit 1;; esac
source deploy/common.sh ""

TOKEN_FILE="$REMOTE_DIR/data/phone_capture_token"
if [ "$NEW" = 1 ]; then
  remote "umask 077 && python3 -c 'import secrets; print(secrets.token_urlsafe(24))' > $TOKEN_FILE.new && mv $TOKEN_FILE.new $TOKEN_FILE"
  echo "Made a new token on the server. Old hosted links stop working."
fi
# The app creates the token on its first request; ask once so the file exists.
curl -s -o /dev/null --max-time 10 "https://$DOMAIN/api/health" || true

if [ "$KIND" = dashboard ]; then
  remote "printf 'https://$DOMAIN/?token=%s' \"\$(cat $TOKEN_FILE)\"" | pbcopy
  echo "Copied: https://$DOMAIN/?token=… (open it once on each device; it then disappears from the address bar)"
else
  remote "printf 'https://$DOMAIN/api/capture/%s' \"\$(cat $TOKEN_FILE)\"" | pbcopy
  echo "Copied: https://$DOMAIN/api/capture/… (paste into the Shortcut's Get Contents of URL)"
fi
echo "Don't paste it into chats or files."
