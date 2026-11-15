#!/usr/bin/env bash
# Run ON THE MAC (optional):  deploy/push-env.sh [server-ip] [--force]
# Copies this Mac's .env to /opt/between/.env on the server over SSH (encrypted), so you don't
# have to type the long Google refresh token by hand. Sets APP_URL and BETWEEN_BEHIND_PROXY for
# hosting. No value is printed, written to a temp file, or sent anywhere but the server.
# Refuses to replace a server .env that already has secrets filled in, unless --force.
set -euo pipefail
cd "$(dirname "$0")/.."
FORCE=0
ARGS=()
for arg in "$@"; do
  if [ "$arg" = "--force" ]; then FORCE=1; else ARGS+=("$arg"); fi
done
source deploy/common.sh "${ARGS[0]:-}"

[ -r .env ] || { echo "No .env on this Mac." >&2; exit 1; }

if [ "$FORCE" = 0 ] && remote "grep -qE '^(GEMINI_API_KEY|GOOGLE_REFRESH_TOKEN)=.+' $REMOTE_DIR/.env 2>/dev/null"; then
  echo "The server's .env already has secrets. Not replacing it. Use --force to replace." >&2
  exit 1
fi

/usr/bin/python3 - "$DOMAIN" <<'PY' | remote "umask 077 && cat > $REMOTE_DIR/.env.new && mv $REMOTE_DIR/.env.new $REMOTE_DIR/.env && chmod 600 $REMOTE_DIR/.env"
import sys
domain = sys.argv[1]
hosted = {"APP_URL": f"https://{domain}", "BETWEEN_BEHIND_PROXY": "1"}
out, seen = [], set()
for line in open(".env", encoding="utf-8").read().splitlines():
    key = line.split("=", 1)[0].strip()
    if key in hosted:
        out.append(f"{key}={hosted[key]}")
        seen.add(key)
    else:
        out.append(line)
out += [f"{k}={v}" for k, v in hosted.items() if k not in seen]
sys.stdout.write("\n".join(out) + "\n")
PY

echo "Copied .env to $HOST:$REMOTE_DIR/.env (chmod 600). Keys on the server:"
remote "cut -d= -f1 $REMOTE_DIR/.env | grep -v '^#' | grep -v '^$'"
