#!/usr/bin/env bash
# Run ON THE MAC:  deploy/deploy.sh [server-ip] [--with-data]
# Copies the project to /opt/between (never .env, data/, .git, keys), builds with Docker Compose,
# and starts the app + Caddy (HTTPS on pipbetween.duckdns.org).
#   --with-data  also copies this Mac's task database once (stops the app first). The phone
#                token is NOT copied: the server makes its own (get links with hosted-link.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
WITH_DATA=0
ARGS=()
for arg in "$@"; do
  if [ "$arg" = "--with-data" ]; then WITH_DATA=1; else ARGS+=("$arg"); fi
done
source deploy/common.sh "${ARGS[0]:-}"

echo "== 1/4 Checks"
remote "test -d $REMOTE_DIR/data && test -f $REMOTE_DIR/.env" \
  || { echo "Run deploy/setup.sh first." >&2; exit 1; }
if ! remote "grep -qE '^GEMINI_API_KEY=.+' $REMOTE_DIR/.env && grep -qE '^GOOGLE_REFRESH_TOKEN=.+' $REMOTE_DIR/.env"; then
  echo "The server's .env still has empty secrets. Fill it (nano $REMOTE_DIR/.env) or run deploy/push-env.sh." >&2
  exit 1
fi

echo "== 2/4 Copy project to $HOST:$REMOTE_DIR"
# --delete removes old files on the server, but never the excluded ones (.env, data/).
rsync -az --delete \
  --exclude '.env' --exclude '.env.*' --exclude 'data/' --exclude '.git/' --exclude '.claude/' \
  --exclude '__pycache__/' --exclude '*.pyc' --exclude '.DS_Store' --exclude '*.pem' \
  --exclude 'client_secret*.json' --exclude 'credentials.json' --exclude 'token.json' \
  -e "ssh ${SSH_OPTS[*]}" ./ "ubuntu@$HOST:$REMOTE_DIR/"

if [ "$WITH_DATA" = 1 ]; then
  echo "== Copy task database (once)"
  remote "cd $REMOTE_DIR && (sudo docker compose stop between 2>/dev/null || true)"
  /usr/bin/sqlite3 data/life_brain.sqlite ".backup '/tmp/between-deploy.sqlite'"
  scp "${SSH_OPTS[@]}" -q /tmp/between-deploy.sqlite "ubuntu@$HOST:$REMOTE_DIR/data/life_brain.sqlite"
  rm -f /tmp/between-deploy.sqlite
  remote "chmod 600 $REMOTE_DIR/data/life_brain.sqlite && rm -f $REMOTE_DIR/data/life_brain.sqlite-wal $REMOTE_DIR/data/life_brain.sqlite-shm"
fi

echo "== 3/4 Build and start"
remote "cd $REMOTE_DIR && sudo docker compose up -d --build && sudo docker compose ps"

echo "== 4/4 Wait for https://$DOMAIN/api/health (Caddy may need a minute for the certificate)"
for i in $(seq 1 40); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "https://$DOMAIN/api/health" || true)
  # 401 = up and correctly asking for the phone token.
  if [ "$code" = "401" ] || [ "$code" = "200" ]; then
    echo "https://$DOMAIN is up (health answered $code)."
    exit 0
  fi
  sleep 3
done
echo "Not answering yet. Logs: ssh in, then: cd $REMOTE_DIR && sudo docker compose logs --tail 50" >&2
exit 1
