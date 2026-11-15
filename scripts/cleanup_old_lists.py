"""Delete the Google Tasks lists that earlier Between builds created.

Only lists with these exact names are touched. Your own lists are left alone.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

OLD_LIST_NAMES = {
    "Between: Do now",
    "Between: Plan",
    "Between: Quick",
    "Between: Someday",
    "Between: Urgent & important",
    "Between: Urgent",
    "Between: Important",
}

token = server.google_access_token()
listing = server.google_tasks_call(token, "GET", "/users/@me/lists?maxResults=100")
targets = [item for item in listing.get("items", []) if item.get("title") in OLD_LIST_NAMES]
if not targets:
    print("No old Between lists found.")
for item in targets:
    server.google_tasks_call(token, "DELETE", f"/users/@me/lists/{item['id']}")
    print(f"Deleted: {item['title']}")
print(f"Done. Removed {len(targets)} old list(s).")
