"""Remove duplicate open tasks left over from testing.

Keeps the oldest open task for each title and deletes the newer copies
(plus their open questions and time logs). Run with --yes to actually delete;
without it, the script only shows what it would remove.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

really = "--yes" in sys.argv
with server.connect() as conn:
    rows = conn.execute(
        "SELECT id, title FROM tasks WHERE status = 'open' ORDER BY LOWER(title), id"
    ).fetchall()
    seen = {}
    doomed = []
    for row in rows:
        key = row["title"].strip().lower()
        if key in seen:
            doomed.append((row["id"], row["title"]))
        else:
            seen[key] = row["id"]
    if not doomed:
        print("No duplicate open tasks found.")
        raise SystemExit(0)
    for task_id, title in doomed:
        print(f"{'Deleting' if really else 'Would delete'}: #{task_id} {title}")
    if really:
        ids = [task_id for task_id, _ in doomed]
        marks = ",".join("?" * len(ids))
        conn.execute(f"DELETE FROM pending_questions WHERE task_id IN ({marks})", ids)
        conn.execute(f"DELETE FROM time_logs WHERE task_id IN ({marks})", ids)
        conn.execute(f"DELETE FROM tasks WHERE id IN ({marks})", ids)
        conn.commit()
        print(f"Removed {len(ids)} duplicate task(s).")
    else:
        print(f"\n{len(doomed)} duplicate(s). Run again with --yes to delete them.")
