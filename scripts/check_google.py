"""Check the saved Google login: which permissions it has and whether any are missing.

Prints permission names and results only. No tokens or account details are shown.
"""
import importlib.util
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

REQUIRED = {
    "https://www.googleapis.com/auth/calendar.readonly": "read your calendar (free time and Canvas)",
    "https://www.googleapis.com/auth/calendar.events": "add Between blocks to your calendar",
    "https://www.googleapis.com/auth/tasks": "write today's list to Google Tasks",
}

config = server.load_config()
if not server.configured(config, "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"):
    print("Not signed in to Google yet. Run scripts/google_auth.py.")
    raise SystemExit(1)

try:
    token = server.google_access_token()
except ValueError as exc:
    print(f"Google refused the saved login: {exc}")
    print("Run scripts/google_auth.py again. If it keeps happening, the app is in Testing mode (see the steps).")
    raise SystemExit(1)

info, _ = server.json_request(
    "https://oauth2.googleapis.com/tokeninfo?" + urlencode({"access_token": token}),
)
granted = set((info.get("scope") or "").split())
missing = 0
for scope, purpose in REQUIRED.items():
    if scope in granted:
        print(f"OK       {purpose}")
    else:
        missing += 1
        print(f"MISSING  {purpose}")
if missing:
    print("\nRun scripts/google_auth.py again and check every permission box on the Google page.")
else:
    print("\nAll permissions are granted.")
