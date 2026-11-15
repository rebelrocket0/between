#!/usr/bin/env python3
"""Copy the phone Shortcut URL to the clipboard. The token is never printed in full.

Run from the between folder, in your own Terminal:
    /usr/bin/python3 scripts/phone_link.py              # copy the Shortcut URL
    /usr/bin/python3 scripts/phone_link.py --new-token  # make a fresh token first (old Shortcut URL stops working)

With Universal Clipboard (same Apple ID, Bluetooth + Wi-Fi on), you can paste it on your iPhone.
The running server picks up a new token right away; no restart needed.
"""
import argparse
import importlib.util
import subprocess
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--new-token", action="store_true", help="make a fresh phone token first")
    parser.add_argument("--port", default="8765")
    parser.add_argument("--ip", action="store_true", help="use the Mac's IP address instead of its .local name")
    args = parser.parse_args()

    token = server.reset_phone_token() if args.new_token else server.get_or_create_phone_token()
    if args.ip:
        urls = server.local_network_urls(args.port, token)
        hosts = [urlparse(u).netloc for u in urls if urlparse(u).hostname and urlparse(u).hostname[0].isdigit()]
        if not hosts:
            raise SystemExit("Couldn't find this Mac's Wi-Fi address. Is Wi-Fi on?")
        host = hosts[0]
    else:
        host = f"{server.bonjour_name()}.local:{args.port}"
    shortcut_url = f"http://{host}/api/capture/{token}"
    subprocess.run(["pbcopy"], input=shortcut_url.encode(), check=True)

    if args.new_token:
        print("Made a new phone token. Any old Shortcut URL no longer works.")
    print(f"Copied to clipboard: http://{host}/api/capture/{token[:3]}…")
    print("Paste it into the Shortcut's 'Get Contents of URL' actions. Don't paste it into chats.")
    if args.ip:
        print("If your Mac's Wi-Fi address changes, run this again and update the Shortcut.")
    else:
        print("If the phone can't reach this name (some campus Wi-Fi blocks it), run again with --ip.")


if __name__ == "__main__":
    main()
