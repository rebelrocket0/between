#!/usr/bin/env bash
# Start Between so your phone can reach it on the same Wi-Fi.
# Must be Apple Python (/usr/bin/python3); python.org Python fails TLS.
set -euo pipefail
cd "$(dirname "$0")/.."
/usr/bin/python3 server.py --host 0.0.0.0
