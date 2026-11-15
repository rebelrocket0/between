#!/usr/bin/env python3
"""One-time Google Calendar login for Between.

Run from the between folder:  python3 scripts/google_auth.py

It asks for your Client ID and Client secret, opens a sign-in link, then saves
GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and GOOGLE_REFRESH_TOKEN into .env.
Read-only access to your calendar. Nothing is printed except status messages.
"""
import getpass
import http.server
import json
import secrets
import stat
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
SCOPE = "https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/tasks"
PORT = 8787
REDIRECT = f"http://127.0.0.1:{PORT}/"


def write_env(updates):
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    seen = set()
    out = []
    for line in lines:
        key = line.partition("=")[0].strip()
        if key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(out) + "\n")
    ENV_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)  # readable and writable by you only


class CodeCatcher(http.server.BaseHTTPRequestHandler):
    code = None
    expected_state = None
    error = None

    def do_GET(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if params.get("state", [""])[0] != CodeCatcher.expected_state:
            self._reply("Sign-in did not match this request. Run the script again.")
            return
        CodeCatcher.error = params.get("error", [None])[0]
        CodeCatcher.code = params.get("code", [None])[0]
        if CodeCatcher.code:
            self._reply("Between is connected to your calendar. You can close this tab.")
        else:
            self._reply(f"Google did not approve access ({CodeCatcher.error}). Check the steps and try again.")
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def _reply(self, message):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"<h2>{message}</h2>".encode())

    def log_message(self, *args):
        pass


def read_client():
    """Read the Client ID and secret from Google's downloaded JSON file, or ask for them."""
    path = input(
        "Drag the downloaded client JSON file into this window, then press Return.\n"
        "(Or just press Return to type the two values instead.)\n> "
    ).strip().strip("'\"")
    if path:
        try:
            data = json.loads(Path(path).expanduser().read_text())
        except (OSError, json.JSONDecodeError) as err:
            sys.exit(f"Could not read that file: {err}")
        client = data.get("installed") or data.get("web") or {}
        client_id = client.get("client_id", "")
        client_secret = client.get("client_secret", "")
    else:
        client_id = input("Paste your Client ID, then press Return: ").strip()
        client_secret = getpass.getpass("Paste your Client secret (hidden), then press Return: ").strip()
    if not client_id or not client_secret:
        sys.exit("Client ID and secret are both required.")
    return client_id, client_secret


def main():
    client_id, client_secret = read_client()

    CodeCatcher.expected_state = secrets.token_urlsafe(16)
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": CodeCatcher.expected_state,
    })

    server = http.server.HTTPServer(("127.0.0.1", PORT), CodeCatcher)
    print("\nOpen this link in your browser and sign in with your student account:\n")
    print(auth_url)
    print("\nIf Google says the app isn't verified, click Advanced, then continue.\n")
    server.serve_forever()
    server.server_close()

    if not CodeCatcher.code:
        sys.exit("No approval received. Run the script again.")

    body = urllib.parse.urlencode({
        "code": CodeCatcher.code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT,
        "grant_type": "authorization_code",
    }).encode()
    try:
        with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=body) as res:
            tokens = json.load(res)
    except urllib.error.HTTPError as err:
        sys.exit(f"Google rejected the sign-in (status {err.code}). Check the Client ID and secret.")

    refresh = tokens.get("refresh_token")
    if not refresh:
        sys.exit("Google did not return a refresh token. Run the script again.")

    write_env({
        "GOOGLE_CLIENT_ID": client_id,
        "GOOGLE_CLIENT_SECRET": client_secret,
        "GOOGLE_REFRESH_TOKEN": refresh,
    })
    print("Saved to .env. Calendar is connected. Restart server.py to use it.")
    print("Delete the downloaded client JSON file from Downloads now. It holds your secret.")


if __name__ == "__main__":
    main()
