# Shared settings for the deploy scripts that run on the Mac. Sourced, not run.
# HOST: first argument (the IP, before DuckDNS points at it) or pipbetween.duckdns.org.
DOMAIN="${BETWEEN_DOMAIN:-pipbetween.duckdns.org}"
KEY="${BETWEEN_SSH_KEY:-$HOME/.ssh/between-key-3.pem}"
HOST="${1:-${BETWEEN_HOST:-$DOMAIN}}"
REMOTE_DIR=/opt/between
SSH_OPTS=(-i "$KEY" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15)

if [ ! -r "$KEY" ]; then
  echo "SSH key not found at $KEY" >&2
  exit 1
fi

remote() {
  ssh "${SSH_OPTS[@]}" "ubuntu@$HOST" "$@"
}
