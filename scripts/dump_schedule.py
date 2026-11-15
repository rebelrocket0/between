"""Save a summary of your calendars and the next 14 days of events to data/schedule_snapshot.txt.

Titles stay on your computer. Nothing is sent to Gemini or anywhere else.
"""
import importlib.util
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote, urlencode

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

config = server.load_config()
tz = server.app_timezone(config)
start = server.datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
end = start + timedelta(days=14)
token = server.google_access_token()

calendars = server.google_calendar_call(token, "GET", "/users/me/calendarList?maxResults=250").get("items", [])
out_lines = [f"Calendars on this account: {len(calendars)}", ""]
for cal in calendars:
    name = cal.get("summaryOverride") or cal.get("summary", "(unnamed)")
    cal_id = cal["id"]
    query = urlencode({
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 250,
    })
    try:
        events = server.google_calendar_call(token, "GET", f"/calendars/{quote(cal_id, safe='')}/events?{query}").get("items", [])
    except ValueError as exc:
        out_lines.append(f"== {name}: could not read ({exc})")
        continue
    out_lines.append(f"== {name} ({cal.get('accessRole', '?')}): {len(events)} events in the next 14 days")
    for event in events:
        start_info = event.get("start", {})
        end_info = event.get("end", {})
        if "date" in start_info:
            when = f"{start_info['date']} all day"
        else:
            when = f"{start_info['dateTime'][:16].replace('T', ' ')} to {end_info.get('dateTime', '')[11:16]}"
        flags = []
        if event.get("transparency") == "transparent":
            flags.append("marked free")
        if event.get("status") == "cancelled":
            flags.append("cancelled")
        out_lines.append(f"   {when} | {event.get('summary', '(no title)')} | {', '.join(flags) or 'busy'}")
    out_lines.append("")

out_dir = ROOT / "data"
out_dir.mkdir(exist_ok=True)
out_path = out_dir / "schedule_snapshot.txt"
out_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
print("\n".join(line for line in out_lines if line.startswith(("Calendars", "=="))))
print(f"Saved to {out_path}")
