#!/usr/bin/env bash
# Run ON THE MAC, once:  deploy/setup.sh <server-ip>
# Copies the two server scripts over and runs server-setup.sh there. It will ask for your
# DuckDNS token in a hidden prompt on the server; nothing is typed into chat or saved on the Mac.
set -euo pipefail
cd "$(dirname "$0")/.."
source deploy/common.sh "${1:-}"

echo "Setting up ubuntu@$HOST ..."
remote "mkdir -p /tmp/between-setup"
scp "${SSH_OPTS[@]}" -q deploy/server-setup.sh deploy/duckdns-update.sh deploy/duckdns-set-token.sh "ubuntu@$HOST:/tmp/between-setup/"
ssh -t "${SSH_OPTS[@]}" "ubuntu@$HOST" "bash /tmp/between-setup/server-setup.sh"
