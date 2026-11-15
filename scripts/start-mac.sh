#!/usr/bin/env bash
# Start Between for this Mac only. Must be Apple Python (/usr/bin/python3); python.org Python fails TLS.
set -euo pipefail
cd "$(dirname "$0")/.."
/usr/bin/python3 server.py
