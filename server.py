#!/usr/bin/env python3
import argparse
import hmac
import json
import mimetypes
import os
import re
import secrets
import socket
import sqlite3
import sys
from time import monotonic, sleep
import threading
from datetime import date, datetime, time, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gap_engine  # noqa: E402
import task_rules  # noqa: E402


ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
DATA = ROOT / "data"
DB_PATH = DATA / "life_brain.sqlite"
ENV_PATH = ROOT / ".env"
PHONE_TOKEN_PATH = DATA / "phone_capture_token"


AREAS = [
    ("health", "Health", "#16a085"),
    ("finance", "Finance", "#d97706"),
    ("work", "Work", "#2563eb"),
    ("school", "School", "#7c3aed"),
    ("home", "Home", "#db2777"),
    ("relationships", "Relationships", "#e11d48"),
    ("hobbies", "Hobbies", "#0f766e"),
    ("planning", "Planning", "#475569"),
    ("journal", "Journal", "#9333ea"),
]

AREA_KEYWORDS = {
    "health": [
        "doctor",
        "dentist",
        "health",
        "medicine",
        "meds",
        "magnesium",
        "sleep",
        "therapy",
        "gym",
        "workout",
        "pain",
        "symptom",
        "meal",
        "vitamin",
    ],
    "finance": [
        "bill",
        "budget",
        "card",
        "bank",
        "rent",
        "invoice",
        "tax",
        "pay",
        "payment",
        "spent",
        "subscription",
        "savings",
        "debt",
    ],
    "work": [
        "client",
        "work",
        "job",
        "jobs",
        "meeting",
        "email",
        "boss",
        "proposal",
        "portfolio",
        "resume",
        "interview",
    ],
    "school": [
        "canvas",
        "assignment",
        "chapter",
        "reading",
        "problem set",
        "prof",
        "class",
        "course",
        "hw",
        "homework",
        "statistics",
        "stats",
        "homework",
        "module",
        "exam",
        "quiz",
        "discussion",
        "lecture",
        "study",
        "professor",
    ],
    "home": [
        "laundry",
        "clean",
        "groceries",
        "grocery",
        "errand",
        "kitchen",
        "trash",
        "apartment",
        "house",
        "repair",
    ],
    "relationships": [
        "mom",
        "dad",
        "friend",
        "call",
        "text",
        "birthday",
        "dinner",
        "social",
        "family",
        "date",
    ],
    "hobbies": [
        "hobby",
        "music",
        "art",
        "game",
        "book",
        "photo",
        "cook",
        "garden",
        "project idea",
    ],
    "planning": [
        "plan",
        "schedule",
        "goal",
        "week",
        "month",
        "priority",
        "routine",
        "habit",
        "review",
    ],
    "journal": [
        "journal",
        "felt",
        "feel",
        "mood",
        "grateful",
        "dream",
        "today i",
        "i noticed",
    ],
}

TASK_PATTERNS = [
    r"\bneed to\b",
    r"\bhave to\b",
    r"\bremind me\b",
    r"\bto do\b",
    r"\btodo\b",
    r"\bfinish\b",
    r"\bsubmit\b",
    r"\bbook\b",
    r"\bschedule\b",
    r"\bcall\b",
    r"\bemail\b",
    r"\bsend\b",
    r"\bbuy\b",
    r"\bpay\b",
    r"\bpick up\b",
    r"\bcomplete\b",
    r"\bapply\b",
    r"\bedit\b",
    r"\bget\b",
    r"\bmake\b",
    r"\bcreate\b",
    r"\bwrite\b",
    r"\bstart\b",
    r"\bfix\b",
    r"\bupdate\b",
    r"\bprepare\b",
    r"\bprep\b",
    r"\bsubmit\b",
    r"\bturn in\b",
]

DUE_PATTERNS = [
    r"\b(today|tonight|tomorrow|this week|next week|this month|next month)\b",
    r"\bdue:?\s+((?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?)\b",
    r"\bby\s+((?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?)\b",
    r"\bby\s+([a-z]+day)\b",
    r"\bdue\s+([a-z]+day)\b",
    r"\bon\s+([a-z]+day)\b",
    r"\bby\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b",
    r"\bon\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b",
    r"\bin\s+(\d+\s+(?:day|days|week|weeks))\b",
]


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect():
    DATA.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_time_logs_table():
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS time_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                minutes INTEGER NOT NULL,
                logged_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
            """
        )
        conn.commit()


def task_time_summary(conn, task_id):
    task = conn.execute("SELECT id, duration_minutes FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        raise ValueError("Task not found.")
    logged = conn.execute(
        "SELECT COALESCE(SUM(minutes), 0) FROM time_logs WHERE task_id = ?", (task_id,)
    ).fetchone()[0]
    estimate = task["duration_minutes"]
    summary = {
        "ok": True,
        "task_id": task_id,
        "logged_minutes": logged,
        "estimate_minutes": estimate,
        "remaining_minutes": None,
        "overrun": False,
        "suggested_estimate": None,
    }
    if estimate:
        summary["remaining_minutes"] = max(estimate - logged, 0)
        summary["overrun"] = logged > estimate
    if summary["overrun"]:
        # Placeholder until there is enough history to use real pace:
        # one more hour past what is already spent, rounded up to 15 minutes.
        summary["suggested_estimate"] = -(-(logged + 60) // 15) * 15
    return summary


def log_task_time(task_id, payload):
    try:
        minutes = int(payload.get("minutes"))
    except (TypeError, ValueError):
        raise ValueError("Minutes must be a whole number.")
    if not 1 <= minutes <= 720:
        raise ValueError("Log between 1 and 720 minutes at a time.")
    with connect() as conn:
        exists = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not exists:
            raise ValueError("Task not found.")
        conn.execute(
            "INSERT INTO time_logs (task_id, minutes, logged_at) VALUES (?, ?, ?)",
            (task_id, minutes, now_iso()),
        )
        conn.commit()
        return task_time_summary(conn, task_id)


def set_task_estimate(task_id, payload):
    try:
        minutes = int(payload.get("duration_minutes"))
    except (TypeError, ValueError):
        raise ValueError("Estimate must be a whole number of minutes.")
    if not 5 <= minutes <= 1440:
        raise ValueError("Estimate must be between 5 and 1440 minutes.")
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE tasks SET duration_minutes = ?, updated_at = ? WHERE id = ?",
            (minutes, now_iso(), task_id),
        )
        if cursor.rowcount == 0:
            raise ValueError("Task not found.")
        conn.commit()
        return task_time_summary(conn, task_id)


def ensure_task_columns():
    """Add the box, due date, skip count, and Google Tasks columns to existing databases."""
    with connect() as conn:
        ensure_column(conn, "tasks", "box", "TEXT")
        ensure_column(conn, "tasks", "due_date", "TEXT")
        ensure_column(conn, "tasks", "skips", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "tasks", "last_skipped_on", "TEXT")
        ensure_column(conn, "tasks", "google_task_id", "TEXT")
        ensure_column(conn, "tasks", "google_box", "TEXT")
        conn.commit()


def backfill_due_dates():
    """Older tasks have 'due Friday' text but no real date. Fill the date in once."""
    today = datetime.now(app_timezone()).date()
    with connect() as conn:
        for row in conn.execute(
            "SELECT id, due_text FROM tasks WHERE status = 'open' AND due_date IS NULL AND due_text IS NOT NULL"
        ).fetchall():
            due_date = task_rules.date_from_words(row["due_text"], today)
            if due_date:
                conn.execute("UPDATE tasks SET due_date = ? WHERE id = ?", (due_date, row["id"]))
        conn.commit()


def init_db():
    ensure_time_logs_table()
    ensure_questions_table()
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS areas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                color TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS inbox_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_text TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                area_id INTEGER,
                confidence REAL NOT NULL,
                status TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                processed_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(area_id) REFERENCES areas(id)
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inbox_item_id INTEGER,
                title TEXT NOT NULL,
                area_id INTEGER,
                status TEXT NOT NULL DEFAULT 'open',
                due_text TEXT,
                duration_minutes INTEGER,
                energy TEXT NOT NULL DEFAULT 'medium',
                scheduled_for TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(inbox_item_id) REFERENCES inbox_items(id),
                FOREIGN KEY(area_id) REFERENCES areas(id)
            );

            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inbox_item_id INTEGER,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                area_id INTEGER,
                kind TEXT NOT NULL DEFAULT 'note',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(inbox_item_id) REFERENCES inbox_items(id),
                FOREIGN KEY(area_id) REFERENCES areas(id)
            );

            CREATE TABLE IF NOT EXISTS external_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                external_id TEXT NOT NULL,
                title TEXT NOT NULL,
                item_type TEXT NOT NULL,
                area_id INTEGER,
                url TEXT,
                starts_at TEXT,
                due_at TEXT,
                raw_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(source, external_id),
                FOREIGN KEY(area_id) REFERENCES areas(id)
            );
            """
        )
        ensure_column(conn, "tasks", "external_item_id", "INTEGER")
        for slug, name, color in AREAS:
            conn.execute(
                """
                INSERT OR IGNORE INTO areas (slug, name, color, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (slug, name, color, now_iso()),
            )
    ensure_task_columns()
    backfill_due_dates()


def ensure_column(conn, table, column, declaration):
    columns = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")


def rows(conn, query, params=()):
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def load_config():
    config = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            config[key.strip()] = value
    # Shell variables only fill gaps; .env always wins, so a stale exported token can't shadow a fresh login.
    for key, value in os.environ.items():
        if key.startswith(("GOOGLE_", "CANVAS_", "LIFE_BRAIN_", "TIMEZONE")) and not config.get(key):
            config[key] = value
    return config


def configured(config, *keys):
    return all(config.get(key) for key in keys)


def app_timezone(config=None):
    config = config or load_config()
    name = config.get("TIMEZONE", "America/Phoenix")
    try:
        return ZoneInfo(name)
    except Exception:
        return datetime.now().astimezone().tzinfo or timezone.utc


def get_or_create_phone_token():
    DATA.mkdir(exist_ok=True)
    if PHONE_TOKEN_PATH.exists():
        token = PHONE_TOKEN_PATH.read_text(encoding="utf-8").strip()
        if token:
            return token
    return reset_phone_token()


def reset_phone_token():
    DATA.mkdir(exist_ok=True)
    token = secrets.token_urlsafe(24)
    PHONE_TOKEN_PATH.write_text(token + "\n", encoding="utf-8")
    PHONE_TOKEN_PATH.chmod(0o600)  # readable and writable by you only
    return token


def is_loopback(address):
    return address in {"127.0.0.1", "::1", "localhost"} or address.startswith("127.")


def supplied_token(handler, parsed):
    path_token_match = re.match(r"^/api/capture/([^/]+)$", parsed.path)
    if path_token_match:
        return unquote(path_token_match.group(1)).strip()
    auth = handler.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    header_token = handler.headers.get("X-Life-Brain-Token")
    if header_token:
        return header_token.strip()
    query_token = parse_qs(parsed.query).get("token", [""])[0]
    return query_token.strip()


def local_network_urls(port, token):
    urls = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            primary_ip = sock.getsockname()[0]
            if primary_ip and not is_loopback(primary_ip):
                urls.append(f"http://{primary_ip}:{port}/?token={token}")
    except OSError:
        pass
    hostname = socket.gethostname().split(".")[0]
    if hostname:
        urls.append(f"http://{hostname}.local:{port}/?token={token}")
    try:
        for address in socket.gethostbyname_ex(socket.gethostname())[2]:
            if address and not is_loopback(address):
                urls.append(f"http://{address}:{port}/?token={token}")
    except OSError:
        pass
    unique = []
    for url in urls:
        if url not in unique:
            unique.append(url)
    return unique


def normalize_text(text):
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return re.sub(r"\s+", " ", text.strip())


def value_to_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, (int, float)):
        return normalize_text(str(value))
    if isinstance(value, list):
        parts = [value_to_text(item) for item in value]
        return normalize_text(" ".join(part for part in parts if part))
    if isinstance(value, dict):
        for key in ["text", "Text", "value", "Value", "content", "Content", "result", "Result"]:
            text = value_to_text(value.get(key))
            if text:
                return text
    return ""


def capture_text_from_payload(payload):
    if isinstance(payload, str):
        return normalize_text(payload)
    if not isinstance(payload, dict):
        return ""
    for key in [
        "text",
        "Text",
        "input",
        "Input",
        "content",
        "Content",
        "note",
        "Note",
        "task",
        "Task",
        "Provided Input",
        "Dictated Text",
    ]:
        text = value_to_text(payload.get(key))
        if text:
            return text
    ignored = {"source", "Source", "token", "Token"}
    for key, value in payload.items():
        if key not in ignored:
            text = value_to_text(value)
            if text:
                return text
    return ""


def capture_source_from_payload(payload):
    if not isinstance(payload, dict):
        return "manual"
    return value_to_text(payload.get("source") or payload.get("Source")) or "manual"


def pick_area(text):
    lowered = text.lower()
    best_slug = "planning"
    best_score = 0
    for slug, keywords in AREA_KEYWORDS.items():
        score = sum(1 for keyword in keywords if re.search(r"\b" + re.escape(keyword), lowered))
        if score > best_score:
            best_slug = slug
            best_score = score
    return best_slug, best_score


def extract_due(text):
    lowered = text.lower()
    for pattern in DUE_PATTERNS:
        match = re.search(pattern, lowered)
        if match:
            return match.group(1)
    return None


def extract_duration(text):
    match = re.search(r"\b(\d+)\s*(min|mins|minute|minutes|hr|hrs|hour|hours)\b", text.lower())
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    return amount * 60 if unit.startswith(("hr", "hour")) else amount


DURATION_PHRASE = r"\b(?:for\s+)?\d+\s*(?:min|mins|minute|minutes|hr|hrs|hour|hours)\b"


def clean_title(text):
    title = normalize_text(text)
    title = re.sub(DURATION_PHRASE, "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s{2,}", " ", title).strip(" -,;:")
    title = re.sub(
        r"^(remind me to|i need to|need to|have to|i have to|todo:?|to do:?|please)\s+",
        "",
        title,
        flags=re.IGNORECASE,
    )
    title = title[0].upper() + title[1:] if title else "Untitled"
    if len(title) > 86:
        title = title[:83].rstrip() + "..."
    return title


def metadata_from_row(row):
    try:
        return json.loads(row["metadata_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def classify(text):
    lowered = text.lower()
    area_slug, area_score = pick_area(text)
    due_text = extract_due(text)
    duration = extract_duration(text)
    task_score = sum(1 for pattern in TASK_PATTERNS if re.search(pattern, lowered))
    has_money = "$" in text or bool(re.search(r"\b\d+(?:\.\d{2})?\s*(dollars|bucks)\b", lowered))

    kind = "note"
    if task_score:
        kind = "task"
    elif area_slug == "finance" and has_money:
        kind = "finance_log"
    elif area_slug == "health" and any(word in lowered for word in ["felt", "pain", "slept", "mood", "symptom"]):
        kind = "health_log"
    elif area_slug == "journal":
        kind = "journal"

    confidence = 0.58
    confidence += min(area_score * 0.08, 0.18)
    confidence += min(task_score * 0.12, 0.24)
    if due_text:
        confidence += 0.08
    if duration is not None:
        confidence += 0.14
        if kind == "note":
            kind = "task"
    if kind != "note":
        confidence += 0.08
    confidence = min(confidence, 0.96)

    status = "routed" if confidence >= 0.78 else "review"
    return {
        "kind": kind,
        "area_slug": area_slug,
        "title": clean_title(text),
        "due_text": due_text,
        "duration_minutes": duration,
        "energy": "medium",
        "confidence": round(confidence, 2),
        "status": status,
    }


def area_id_for_slug(conn, slug):
    row = conn.execute("SELECT id FROM areas WHERE slug = ?", (slug,)).fetchone()
    return row["id"] if row else None


TASK_AREAS = {slug for slug, _, _ in AREAS}
GEMINI_MODELS = ["gemini-4-hydrogen", "gemini-3.8-flash"]
# Tests turn this off so they never write to the real Google Tasks account.
AUTO_SYNC_GOOGLE_TASKS = True


def parse_split(raw):
    """Turn Gemini's JSON text into clean tasks and follow-up questions. Bad items are skipped."""
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        raise ValueError("Gemini did not return JSON.")
    items = data.get("tasks") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("Gemini returned no task list.")

    tasks = []
    kept = {}
    for raw_index, item in enumerate(items[:12]):
        if not isinstance(item, dict):
            continue
        title = clean_title(normalize_text(item.get("title")))
        if title == "Untitled":
            continue
        minutes = item.get("minutes")
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or not 5 <= minutes <= 1440:
            minutes = None
        else:
            minutes = int(minutes)
        due = normalize_text(item.get("due")) or None
        due_date = task_rules.valid_date(item.get("due_date"))
        box = item.get("box") if item.get("box") in task_rules.BOXES else None
        area = item.get("area") if item.get("area") in TASK_AREAS else "planning"
        kept[raw_index] = len(tasks)
        tasks.append({"title": title, "minutes": minutes, "due": due, "due_date": due_date, "box": box, "area": area})

    questions = []
    raw_questions = data.get("questions") if isinstance(data, dict) else None
    for item in raw_questions[:6] if isinstance(raw_questions, list) else []:
        if not isinstance(item, dict):
            continue
        task_ref = item.get("task")
        if isinstance(task_ref, bool) or not isinstance(task_ref, int) or task_ref not in kept:
            continue
        field = item.get("field")
        question = normalize_text(item.get("question"))
        if field not in ("minutes", "due") or not question:
            continue
        questions.append({"task_index": kept[task_ref], "field": field, "question": question[:200]})
    return tasks, questions


def parse_split_tasks(raw):
    return parse_split(raw)[0]


def calendar_context():
    """A short line for the Gemini prompt describing today's free time."""
    try:
        payload = free_time_payload()
    except Exception:
        return "Calendar: unavailable."
    if not payload.get("ok"):
        return "Calendar: unavailable."
    if payload.get("source") != "Google Calendar":
        return "Calendar: not connected."
    gaps = payload.get("gaps") or []
    if not gaps:
        return "Calendar: no free time left today."
    parts = [f"{g['start']}-{g['end']} ({g['minutes']} min)" for g in gaps[:6]]
    return "Calendar free today: " + "; ".join(parts) + "."


def split_with_gemini(text, config):
    """Ask Gemini to split a note into tasks and questions. Raises ValueError if every model fails."""
    api_key = config["GEMINI_API_KEY"]
    today = datetime.now(app_timezone(config)).strftime("%A, %B %d, %Y")
    prompt = (
        "You turn a short note into to-do items for a student's planner. "
        f"Today is {today}. {calendar_context()} "
        'Return only JSON shaped like {"tasks": [{"title": "...", "minutes": 30, "due": "Friday", "area": "school"}], '
        '"questions": [{"task": 0, "field": "minutes", "question": "How long will the reading take?"}]}. '
        "Each task also has box and due_date. "
        "Rules: one item per real to-do. Titles are short and start with a verb, with no durations in the title. "
        "minutes is your best estimate of focused time, or null if unclear. "
        "due is the deadline as written in the note, or null. "
        "due_date is that deadline as YYYY-MM-DD, using today's date to work out the day, or null if unclear. "
        "box is one of: do_now (important and urgent), plan (important, not urgent, or no deadline and it matters), "
        "quick (urgent but small), someday (no deadline and not important). "
        "area is one of: " + ", ".join(sorted(TASK_AREAS)) + ". "
        "Size tasks to the free stretches above when you can. "
        "Ask at most 3 questions, and only when a missing detail blocks a good plan: "
        "a big task with no time, or a deadline word with no date. "
        "task is the index of the task in your list, starting at 0. field is minutes or due. "
        'If the note has nothing to do, return {"tasks": [], "questions": []}. '
        f"Note: {text}"
    )
    models = [config["GEMINI_MODEL"]] if config.get("GEMINI_MODEL") else []
    models += [model for model in GEMINI_MODELS if model not in models]

    last_error = None
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            body, _ = json_request(
                url,
                method="POST",
                headers={"x-goog-api-key": api_key},
                payload={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json"},
                },
            )
            raw = body["candidates"][0]["content"]["parts"][0]["text"]
            return parse_split(raw)
        except (ValueError, KeyError, IndexError, TypeError, OSError) as exc:  # OSError: timeouts move on to the next model
            last_error = exc
    raise ValueError(f"Gemini could not split this note: {last_error}")


def ensure_questions_table():
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                field TEXT NOT NULL,
                question TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                answer TEXT,
                created_at TEXT NOT NULL,
                answered_at TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
            """
        )
        conn.commit()


def create_split_capture(text, source, tasks, questions=None):
    created = now_iso()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO inbox_items (
                raw_text, source, kind, title, area_id, confidence, status,
                metadata_json, processed_at, created_at
            )
            VALUES (?, ?, 'task', ?, NULL, 0.95, 'routed', ?, ?, ?)
            """,
            (
                text,
                source,
                tasks[0]["title"] if len(tasks) == 1 else f"{len(tasks)} tasks",
                json.dumps({"router": "gemini-v1", "task_count": len(tasks)}),
                created,
                created,
            ),
        )
        inbox_id = cursor.lastrowid
        task_ids = []
        for task in tasks:
            existing = conn.execute(
                "SELECT id FROM tasks WHERE status = 'open' AND LOWER(title) = LOWER(?) ORDER BY id LIMIT 1",
                (task["title"],),
            ).fetchone()
            if existing:
                task_ids.append(existing["id"])
                continue
            task_cursor = conn.execute(
                """
                INSERT INTO tasks (
                    inbox_item_id, title, area_id, due_text, duration_minutes,
                    energy, created_at, updated_at, box, due_date, skips
                )
                VALUES (?, ?, ?, ?, ?, 'medium', ?, ?, ?, ?, 0)
                """,
                (
                    inbox_id,
                    task["title"],
                    area_id_for_slug(conn, task["area"]),
                    task["due"],
                    task["minutes"],
                    created,
                    created,
                    task.get("box"),
                    task.get("due_date") or task_rules.date_from_words(task.get("due"), datetime.now(app_timezone()).date()),
                ),
            )
            task_ids.append(task_cursor.lastrowid)
        for question in questions or []:
            question_task_id = task_ids[question["task_index"]]
            already_asked = conn.execute(
                "SELECT 1 FROM pending_questions WHERE task_id = ? AND field = ? AND status = 'open'",
                (question_task_id, question["field"]),
            ).fetchone()
            if already_asked:
                continue
            conn.execute(
                """
                INSERT INTO pending_questions (task_id, field, question, status, created_at)
                VALUES (?, ?, ?, 'open', ?)
                """,
                (question_task_id, question["field"], question["question"], created),
            )
        conn.commit()
    plan_cache_clear()
    try:
        if AUTO_SYNC_GOOGLE_TASKS:
            sync_tasks_to_google()
    except Exception as exc:
        # Keep the capture even if Google Tasks is not connected yet.
        print(f"Google Tasks sync skipped: {friendly_google_error(exc)}", flush=True)
    try:
        if AUTO_SYNC_GOOGLE_TASKS:
            sync_blocks_to_calendar()
    except Exception as exc:
        print(f"Calendar block sync skipped: {friendly_google_error(exc)}", flush=True)
    return {"ok": True, "item": get_inbox_item(inbox_id), "route": {"router": "gemini-v1", "tasks": tasks}}


def open_questions():
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT pending_questions.id, pending_questions.field, pending_questions.question,
                   tasks.title AS task_title, tasks.duration_minutes
            FROM pending_questions
            JOIN tasks ON tasks.id = pending_questions.task_id
            WHERE pending_questions.status = 'open' AND tasks.status = 'open'
            ORDER BY pending_questions.id
            """
        ).fetchall()
    return {"ok": True, "questions": [dict(row) for row in rows]}


def answer_question(question_id, answer):
    answer = normalize_text(answer)
    if not answer:
        raise ValueError("Type an answer first.")
    with connect() as conn:
        row = conn.execute(
            "SELECT id, task_id, field FROM pending_questions WHERE id = ? AND status = 'open'",
            (question_id,),
        ).fetchone()
        if not row:
            raise ValueError("That question is already answered or doesn't exist.")
        now = now_iso()
        if row["field"] == "minutes":
            minutes = extract_duration(answer) or (int(answer) if answer.isdigit() else None)
            if not minutes or not 5 <= minutes <= 1440:
                raise ValueError("Give a time like '45 min' or '2 hours'.")
            conn.execute(
                "UPDATE tasks SET duration_minutes = ?, updated_at = ? WHERE id = ?",
                (minutes, now, row["task_id"]),
            )
        else:
            due_date = task_rules.date_from_words(answer, datetime.now(app_timezone()).date())
            conn.execute(
                "UPDATE tasks SET due_text = ?, due_date = COALESCE(?, due_date), updated_at = ? WHERE id = ?",
                (answer[:80], due_date, now, row["task_id"]),
            )
        conn.execute(
            "UPDATE pending_questions SET status = 'answered', answer = ?, answered_at = ? WHERE id = ?",
            (answer, now, question_id),
        )
        conn.commit()
    plan_cache_clear()
    return {"ok": True}


def create_capture(payload):
    text = capture_text_from_payload(payload)
    source = capture_source_from_payload(payload)
    if not text:
        fields = ", ".join(payload.keys()) if isinstance(payload, dict) and payload else "none"
        raise ValueError(
            "Capture text is required. The request reached Between, but the text value was empty. "
            f"Received fields: {fields}."
        )

    config = load_config()
    if configured(config, "GEMINI_API_KEY"):
        questions = []
        try:
            tasks, questions = split_with_gemini(text, config)
        except ValueError as exc:
            print(f"Gemini split skipped: {exc}", flush=True)
            tasks = []
        if tasks:
            return create_split_capture(text, source, tasks, questions)

    result = classify(text)
    created = now_iso()
    with connect() as conn:
        area_id = area_id_for_slug(conn, result["area_slug"])
        cursor = conn.execute(
            """
            INSERT INTO inbox_items (
                raw_text, source, kind, title, area_id, confidence, status,
                metadata_json, processed_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                text,
                source,
                result["kind"],
                result["title"],
                area_id,
                result["confidence"],
                result["status"],
                json.dumps(
                    {
                        "router": "rules-v0",
                        "due_text": result["due_text"],
                        "duration_minutes": result["duration_minutes"],
                    }
                ),
                created,
                created,
            ),
        )
        inbox_id = cursor.lastrowid

        if result["kind"] == "task":
            conn.execute(
                """
                INSERT INTO tasks (
                    inbox_item_id, title, area_id, due_text, duration_minutes,
                    energy, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    inbox_id,
                    result["title"],
                    area_id,
                    result["due_text"],
                    result["duration_minutes"],
                    result["energy"],
                    created,
                    created,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO notes (
                    inbox_item_id, title, body, area_id, kind, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    inbox_id,
                    result["title"],
                    text,
                    area_id,
                    result["kind"],
                    created,
                    created,
                ),
            )
        conn.commit()
    return {"ok": True, "item": get_inbox_item(inbox_id), "route": result}


def get_inbox_item(inbox_id):
    with connect() as conn:
        row = conn.execute(
            """
            SELECT inbox_items.*, areas.name AS area_name, areas.slug AS area_slug, areas.color AS area_color
            FROM inbox_items
            LEFT JOIN areas ON areas.id = inbox_items.area_id
            WHERE inbox_items.id = ?
            """,
            (inbox_id,),
        ).fetchone()
        return dict(row) if row else None


def get_state():
    with connect() as conn:
        areas = rows(
            conn,
            """
            SELECT
                areas.*,
                COUNT(DISTINCT tasks.id) FILTER (WHERE tasks.status = 'open') AS open_tasks,
                COUNT(DISTINCT notes.id) AS notes_count
            FROM areas
            LEFT JOIN tasks ON tasks.area_id = areas.id
            LEFT JOIN notes ON notes.area_id = areas.id
            GROUP BY areas.id
            ORDER BY areas.id
            """,
        )
        inbox = rows(
            conn,
            """
            SELECT inbox_items.*, areas.name AS area_name, areas.slug AS area_slug, areas.color AS area_color
            FROM inbox_items
            LEFT JOIN areas ON areas.id = inbox_items.area_id
            ORDER BY inbox_items.created_at DESC, inbox_items.id DESC
            LIMIT 120
            """,
        )
        tasks = rows(
            conn,
            """
            SELECT
                tasks.*,
                (SELECT COALESCE(SUM(minutes), 0) FROM time_logs WHERE time_logs.task_id = tasks.id) AS logged_minutes,
                areas.name AS area_name,
                areas.slug AS area_slug,
                areas.color AS area_color,
                external_items.source AS external_source,
                external_items.url AS external_url,
                external_items.due_at AS external_due_at
            FROM tasks
            LEFT JOIN areas ON areas.id = tasks.area_id
            LEFT JOIN external_items ON external_items.id = tasks.external_item_id
            ORDER BY
                CASE tasks.status WHEN 'open' THEN 0 ELSE 1 END,
                tasks.created_at DESC,
                tasks.id DESC
            LIMIT 120
            """,
        )
        today_local = datetime.now(app_timezone()).date()
        for task in tasks:
            task["category"] = task_rules.category_for(task.get("box"), task.get("due_date"), today_local)
        notes = rows(
            conn,
            """
            SELECT notes.*, areas.name AS area_name, areas.slug AS area_slug, areas.color AS area_color
            FROM notes
            LEFT JOIN areas ON areas.id = notes.area_id
            ORDER BY notes.created_at DESC, notes.id DESC
            LIMIT 120
            """,
        )
        stats = {
            "inbox": conn.execute("SELECT COUNT(*) FROM inbox_items").fetchone()[0],
            "review": conn.execute("SELECT COUNT(*) FROM inbox_items WHERE status = 'review'").fetchone()[0],
            "open_tasks": conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'open'").fetchone()[0],
            "notes": conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0],
        }
    return {
        "areas": areas,
        "inbox": inbox,
        "tasks": tasks,
        "notes": notes,
        "stats": stats,
        "connectors": connector_status(),
        "setup": setup_info(),
    }


def update_task(task_id, payload):
    status = payload.get("status")
    if status not in {"open", "done"}:
        raise ValueError("Task status must be open or done.")
    with connect() as conn:
        conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status, now_iso(), task_id),
        )
        conn.commit()
    plan_cache_clear()
    return {"ok": True}


def update_inbox_item(inbox_id, payload):
    status = payload.get("status")
    if status not in {"routed", "review", "archived"}:
        raise ValueError("Inbox status must be routed, review, or archived.")
    with connect() as conn:
        conn.execute("UPDATE inbox_items SET status = ? WHERE id = ?", (status, inbox_id))
        conn.commit()
    return {"ok": True}


def delete_inbox_item(inbox_id):
    with connect() as conn:
        exists = conn.execute("SELECT id FROM inbox_items WHERE id = ?", (inbox_id,)).fetchone()
        if not exists:
            raise ValueError("Inbox item not found.")
        conn.execute("DELETE FROM tasks WHERE inbox_item_id = ?", (inbox_id,))
        conn.execute("DELETE FROM notes WHERE inbox_item_id = ?", (inbox_id,))
        conn.execute("DELETE FROM inbox_items WHERE id = ?", (inbox_id,))
        conn.commit()
    return {"ok": True}


def setup_info(host_header=None):
    token = get_or_create_phone_token()
    port = "8765"
    if host_header and ":" in host_header:
        port = host_header.rsplit(":", 1)[1]
    urls = local_network_urls(port, token)
    capture_urls = []
    for url in urls:
        parsed = urlparse(url)
        capture_urls.append(f"{parsed.scheme}://{parsed.netloc}/api/capture")
    shortcut_url = (
        f"{capture_urls[0]}/{token}"
        if capture_urls
        else f"http://YOUR-MAC-IP:{port}/api/capture/{token}"
    )
    return {
        "mac_url": f"http://127.0.0.1:{port}/",
        "phone_urls": urls,
        "capture_urls": capture_urls,
        "phone_token": token,
        "run_for_phone_command": "/usr/bin/python3 server.py --host 0.0.0.0",
        "shortcut": {
            "url": shortcut_url,
            "method": "POST",
            "headers": {
                "Content-Type": "application/json",
                "X-Life-Brain-Token": token,
            },
            "body": {
                "text": "Shortcut Input",
                "source": "phone",
            },
        },
    }


def connector_status():
    config = load_config()
    with connect() as conn:
        canvas_count = conn.execute(
            "SELECT COUNT(*) FROM external_items WHERE source = 'canvas'"
        ).fetchone()[0]
    return {
        "canvas": {
            "configured": configured(config, "CANVAS_BASE_URL", "CANVAS_ACCESS_TOKEN"),
            "url_saved": bool(config.get("CANVAS_BASE_URL")),
            "token_saved": bool(config.get("CANVAS_ACCESS_TOKEN")),
            "imported_items": canvas_count,
        },
        "google_calendar": {
            "configured": configured(
                config,
                "GOOGLE_CLIENT_ID",
                "GOOGLE_CLIENT_SECRET",
                "GOOGLE_REFRESH_TOKEN",
            ),
            "calendar_id": config.get("GOOGLE_CALENDAR_ID", "primary"),
            "timezone": config.get("TIMEZONE", "America/Phoenix"),
        },
    }


def json_request(url, method="GET", headers=None, payload=None, form=None):
    headers = dict(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    if form is not None:
        data = urlencode(form).encode("utf-8")
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=25) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}, response.headers
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"{exc.code} from connector: {body[:500]}") from exc
    except URLError as exc:
        raise ValueError(f"Connector request failed: {exc.reason}") from exc


def canvas_next_link(link_header):
    if not link_header:
        return None
    for part in link_header.split(","):
        if 'rel="next"' in part:
            match = re.search(r"<([^>]+)>", part)
            if match:
                return match.group(1)
    return None


def canvas_fetch_assignments(days=90):
    config = load_config()
    if not configured(config, "CANVAS_BASE_URL", "CANVAS_ACCESS_TOKEN"):
        raise ValueError("Canvas is not configured yet.")
    base_url = config["CANVAS_BASE_URL"].rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url
    start = date.today()
    end = start + timedelta(days=days)
    params = urlencode(
        {
            "type": "assignment",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        }
    )
    url = f"{base_url}/api/v1/calendar_events?{params}"
    headers = {
        "Authorization": f"Bearer {config['CANVAS_ACCESS_TOKEN']}",
        "Accept": "application/json",
    }
    items = []
    for _ in range(10):
        body, response_headers = json_request(url, headers=headers)
        if not isinstance(body, list):
            raise ValueError("Canvas returned an unexpected response.")
        items.extend(body)
        url = canvas_next_link(response_headers.get("Link"))
        if not url:
            break
    return items


def sync_canvas_assignments():
    assignments = canvas_fetch_assignments()
    created = 0
    updated = 0
    skipped = 0
    now = now_iso()
    with connect() as conn:
        area_id = area_id_for_slug(conn, "school")
        for item in assignments:
            if item.get("workflow_state") == "deleted":
                skipped += 1
                continue
            external_id = str(item.get("id") or "")
            title = normalize_text(item.get("title") or "Canvas assignment")
            if not external_id or not title:
                skipped += 1
                continue
            due_at = item.get("start_at") or item.get("all_day_date")
            url = item.get("html_url") or item.get("url")
            conn.execute(
                """
                INSERT INTO external_items (
                    source, external_id, title, item_type, area_id, url,
                    starts_at, due_at, raw_json, created_at, updated_at
                )
                VALUES ('canvas', ?, ?, 'assignment', ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, external_id) DO UPDATE SET
                    title = excluded.title,
                    area_id = excluded.area_id,
                    url = excluded.url,
                    starts_at = excluded.starts_at,
                    due_at = excluded.due_at,
                    raw_json = excluded.raw_json,
                    updated_at = excluded.updated_at
                """,
                (
                    external_id,
                    title,
                    area_id,
                    url,
                    due_at,
                    due_at,
                    json.dumps(item),
                    now,
                    now,
                ),
            )
            external = conn.execute(
                "SELECT id FROM external_items WHERE source = 'canvas' AND external_id = ?",
                (external_id,),
            ).fetchone()
            existing = conn.execute(
                "SELECT id, status FROM tasks WHERE external_item_id = ?",
                (external["id"],),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE tasks
                    SET title = ?, due_text = ?, area_id = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (title, due_at, area_id, now, existing["id"]),
                )
                updated += 1
            else:
                conn.execute(
                    """
                    INSERT INTO tasks (
                        external_item_id, title, area_id, status, due_text,
                        duration_minutes, energy, created_at, updated_at
                    )
                    VALUES (?, ?, ?, 'open', ?, 45, 'medium', ?, ?)
                    """,
                    (external["id"], title, area_id, due_at, now, now),
                )
                created += 1
        conn.commit()
    return {"ok": True, "created": created, "updated": updated, "skipped": skipped}


def google_access_token():
    config = load_config()
    if not configured(config, "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"):
        raise ValueError("Google Calendar is not configured yet.")
    body, _ = json_request(
        "https://oauth2.googleapis.com/token",
        method="POST",
        form={
            "client_id": config["GOOGLE_CLIENT_ID"],
            "client_secret": config["GOOGLE_CLIENT_SECRET"],
            "refresh_token": config["GOOGLE_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        },
    )
    token = body.get("access_token")
    if not token:
        raise ValueError("Google did not return an access token.")
    return token


def google_freebusy(days=7):
    config = load_config()
    token = google_access_token()
    start = datetime.now(timezone.utc)
    end = start + timedelta(days=days)
    calendar_id = config.get("GOOGLE_CALENDAR_ID", "primary")
    body, _ = json_request(
        "https://www.googleapis.com/calendar/v3/freeBusy",
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        payload={
            "timeMin": start.isoformat().replace("+00:00", "Z"),
            "timeMax": end.isoformat().replace("+00:00", "Z"),
            "timeZone": config.get("TIMEZONE", "America/Phoenix"),
            "items": [{"id": calendar_id}],
        },
    )
    return body


def parse_remote_datetime(value, tz):
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=tz)
        return parsed.astimezone(tz)
    except ValueError:
        return None


def busy_blocks_from_google(freebusy, tz):
    blocks = []
    calendars = freebusy.get("calendars", {})
    for calendar in calendars.values():
        for block in calendar.get("busy", []):
            start = parse_remote_datetime(block.get("start"), tz)
            end = parse_remote_datetime(block.get("end"), tz)
            if start and end:
                blocks.append((start, end))
    return blocks


def overlaps(start, end, busy_blocks):
    return any(block_start < end and block_end > start for block_start, block_end in busy_blocks)


def gaps_between(now, end_of_day, busy_blocks):
    """Free stretches between now and end_of_day, given busy (start, end) pairs."""
    gaps = []
    cursor = now
    for start, end in sorted(busy_blocks):
        if end <= cursor:
            continue
        if start >= end_of_day:
            break
        if start > cursor:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
        if cursor >= end_of_day:
            break
    if cursor < end_of_day:
        gaps.append((cursor, end_of_day))
    return [(start, end) for start, end in gaps if end > start]


_FREE_TIME_CACHE = {"at": 0.0, "payload": None}


def free_time_payload():
    config = load_config()
    tz = app_timezone(config)
    if not connector_status()["google_calendar"]["configured"]:
        return {"ok": True, "source": "not connected", "gaps": [], "free_now_minutes": 0}

    cached = _FREE_TIME_CACHE
    if cached["payload"] and monotonic() - cached["at"] < 60:
        return cached["payload"]

    now = datetime.now(tz)
    end_of_day = now.replace(hour=23, minute=59, second=0, microsecond=0)
    try:
        busy = busy_blocks_from_google(google_freebusy(days=1), tz)
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "gaps": [], "free_now_minutes": 0}

    gaps = gaps_between(now, end_of_day, busy)
    free_now = 0
    if gaps and gaps[0][0] <= now:
        free_now = int((gaps[0][1] - now).total_seconds() // 60)
    payload = {
        "ok": True,
        "source": "Google Calendar",
        "free_now_minutes": free_now,
        "gaps": [
            {
                "start": start.strftime("%H:%M"),
                "end": end.strftime("%H:%M"),
                "minutes": int((end - start).total_seconds() // 60),
            }
            for start, end in gaps
        ],
    }
    _FREE_TIME_CACHE.update({"at": monotonic(), "payload": payload})
    return payload


def planning_suggestions():
    config = load_config()
    tz = app_timezone(config)
    calendar_source = "local schedule"
    connector_error = None
    busy_blocks = []
    if connector_status()["google_calendar"]["configured"]:
        try:
            freebusy = google_freebusy()
            busy_blocks = busy_blocks_from_google(freebusy, tz)
            calendar_source = "Google Calendar"
        except ValueError as exc:
            connector_error = str(exc)

    with connect() as conn:
        open_tasks = rows(
            conn,
            """
            SELECT tasks.*, areas.name AS area_name, areas.color AS area_color
            FROM tasks
            LEFT JOIN areas ON areas.id = tasks.area_id
            WHERE tasks.status = 'open' AND tasks.scheduled_for IS NULL
            ORDER BY tasks.due_text IS NULL, tasks.due_text, tasks.created_at
            LIMIT 12
            """,
        )

    suggestions = []
    now_local = datetime.now(tz)
    cursor_tasks = open_tasks[:]
    for day_offset in range(7):
        day = (now_local + timedelta(days=day_offset)).date()
        for hour in [9, 10, 11, 13, 14, 15, 16, 17]:
            if not cursor_tasks:
                break
            task = cursor_tasks[0]
            duration = int(task.get("duration_minutes") or 45)
            duration = max(20, min(duration, 90))
            start = datetime.combine(day, time(hour=hour), tzinfo=tz)
            if start < now_local + timedelta(minutes=20):
                continue
            end = start + timedelta(minutes=duration)
            if overlaps(start, end, busy_blocks):
                continue
            cursor_tasks.pop(0)
            suggestions.append(
                {
                    "task_id": task["id"],
                    "title": task["title"],
                    "area_name": task.get("area_name"),
                    "area_color": task.get("area_color"),
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "duration_minutes": duration,
                }
            )
            if len(suggestions) >= 5:
                return {
                    "ok": True,
                    "calendar_source": calendar_source,
                    "connector_error": connector_error,
                    "suggestions": suggestions,
                }
        if not cursor_tasks or len(suggestions) >= 5:
            break
    return {
        "ok": True,
        "calendar_source": calendar_source,
        "connector_error": connector_error,
        "suggestions": suggestions,
    }


def convert_inbox_item(inbox_id, payload):
    target_kind = payload.get("kind")
    if target_kind not in {"task", "note"}:
        raise ValueError("Conversion kind must be task or note.")

    with connect() as conn:
        item = conn.execute("SELECT * FROM inbox_items WHERE id = ?", (inbox_id,)).fetchone()
        if not item:
            raise ValueError("Inbox item not found.")

        item = dict(item)
        created = now_iso()
        metadata = metadata_from_row(item)
        title = item["title"] or clean_title(item["raw_text"])

        if target_kind == "task":
            conn.execute("DELETE FROM notes WHERE inbox_item_id = ?", (inbox_id,))
            exists = conn.execute(
                "SELECT id FROM tasks WHERE inbox_item_id = ?",
                (inbox_id,),
            ).fetchone()
            if not exists:
                conn.execute(
                    """
                    INSERT INTO tasks (
                        inbox_item_id, title, area_id, due_text, duration_minutes,
                        energy, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        inbox_id,
                        title,
                        item["area_id"],
                        metadata.get("due_text"),
                        metadata.get("duration_minutes"),
                        "medium",
                        created,
                        created,
                    ),
                )
        else:
            conn.execute("DELETE FROM tasks WHERE inbox_item_id = ?", (inbox_id,))
            exists = conn.execute(
                "SELECT id FROM notes WHERE inbox_item_id = ?",
                (inbox_id,),
            ).fetchone()
            if not exists:
                conn.execute(
                    """
                    INSERT INTO notes (
                        inbox_item_id, title, body, area_id, kind, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        inbox_id,
                        title,
                        item["raw_text"],
                        item["area_id"],
                        "note",
                        created,
                        created,
                    ),
                )

        conn.execute(
            """
            UPDATE inbox_items
            SET kind = ?, status = 'routed', confidence = MAX(confidence, 0.9)
            WHERE id = ?
            """,
            (target_kind, inbox_id),
        )
        conn.commit()
    return {"ok": True}


def plan_for_window(minutes):
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, title, status, duration_minutes, due_text,
                (SELECT COALESCE(SUM(minutes), 0) FROM time_logs WHERE time_logs.task_id = tasks.id) AS logged_minutes
            FROM tasks
            WHERE status = 'open'
            """
        ).fetchall()
    tasks = [dict(row) for row in rows]
    return {
        "ok": True,
        "minutes": minutes,
        "plan": gap_engine.plan_window(tasks, minutes),
        "fits": len(gap_engine.fits_window(tasks, minutes)),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "LifeBrain/0.1"

    def is_authorized(self, parsed):
        if not parsed.path.startswith("/api/"):
            return True
        if is_loopback(self.client_address[0]):
            return True
        token = supplied_token(self, parsed)
        return hmac.compare_digest(token, get_or_create_phone_token())

    def require_authorized(self, parsed):
        if self.is_authorized(parsed):
            return True
        self.send_json({"ok": False, "error": "Phone token required."}, status=401)
        return False

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Life-Brain-Token")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if not self.require_authorized(parsed):
            return
        if parsed.path == "/api/today":
            self.send_json(today_payload())
            return
        if parsed.path == "/api/questions":
            self.send_json(open_questions())
            return
        if parsed.path == "/api/free-time":
            self.send_json(free_time_payload())
            return
        if parsed.path == "/api/plan":
            try:
                minutes = int(parse_qs(parsed.query).get("minutes", ["15"])[0])
            except ValueError:
                minutes = 0
            if not 1 <= minutes <= 480:
                self.send_json({"ok": False, "error": "minutes must be between 1 and 480."}, 400)
                return
            self.send_json(plan_for_window(minutes))
            return
        if parsed.path == "/api/health":
            self.send_json({"ok": True, "time": now_iso()})
            return
        if parsed.path == "/api/state":
            self.send_json(get_state())
            return
        if parsed.path == "/api/setup":
            self.send_json(setup_info(self.headers.get("Host")))
            return
        if parsed.path == "/api/connectors":
            self.send_json(connector_status())
            return
        self.serve_static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        if not self.require_authorized(parsed):
            return
        if parsed.path == "/api/capture":
            self.handle_json(lambda payload: create_capture(payload), status=201)
            return
        if re.match(r"^/api/capture/[^/]+$", parsed.path):
            self.handle_json(lambda payload: create_capture(payload), status=201)
            return
        if parsed.path == "/api/setup/reset-token":
            self.send_json({"ok": True, "phone_token": reset_phone_token(), "setup": setup_info(self.headers.get("Host"))})
            return
        if parsed.path == "/api/connectors/canvas/sync":
            self.handle_json(lambda payload: sync_canvas_assignments())
            return
        if parsed.path == "/api/connectors/google/freebusy":
            self.handle_json(lambda payload: {"ok": True, "freebusy": google_freebusy()})
            return
        if parsed.path == "/api/plan/suggestions":
            self.handle_json(lambda payload: planning_suggestions())
            return
        if parsed.path == "/api/connectors/google/canvas/sync":
            self.handle_json(lambda payload: sync_canvas_calendar())
            return
        if parsed.path == "/api/connectors/google/blocks/sync":
            self.handle_json(lambda payload: sync_blocks_to_calendar())
            return
        if parsed.path == "/api/connectors/google/tasks/sync":
            self.handle_json(lambda payload: sync_tasks_to_google())
            return
        skip_match = re.match(r"^/api/tasks/(\d+)/skip$", parsed.path)
        if skip_match:
            skipped_id = int(skip_match.group(1))
            self.handle_json(lambda payload: skip_task(skipped_id))
            return
        task_action = re.match(r"^/api/tasks/(\d+)/(log|estimate)$", parsed.path)
        if task_action:
            task_id = int(task_action.group(1))
            if task_action.group(2) == "log":
                self.handle_json(lambda payload: log_task_time(task_id, payload), status=201)
            else:
                self.handle_json(lambda payload: set_task_estimate(task_id, payload))
            return
        answer_match = re.match(r"^/api/questions/(\d+)/answer$", parsed.path)
        if answer_match:
            self.handle_json(lambda payload: answer_question(int(answer_match.group(1)), payload.get("answer", "")))
            return
        convert_match = re.match(r"^/api/inbox/(\d+)/convert$", parsed.path)
        if convert_match:
            self.handle_json(lambda payload: convert_inbox_item(int(convert_match.group(1)), payload))
            return
        self.send_error(404)

    def do_PATCH(self):
        parsed = urlparse(self.path)
        if not self.require_authorized(parsed):
            return
        task_match = re.match(r"^/api/tasks/(\d+)$", parsed.path)
        inbox_match = re.match(r"^/api/inbox/(\d+)$", parsed.path)
        if task_match:
            self.handle_json(lambda payload: update_task(int(task_match.group(1)), payload))
            return
        if inbox_match:
            self.handle_json(lambda payload: update_inbox_item(int(inbox_match.group(1)), payload))
            return
        self.send_error(404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if not self.require_authorized(parsed):
            return
        inbox_match = re.match(r"^/api/inbox/(\d+)$", parsed.path)
        if inbox_match:
            try:
                self.send_json(delete_inbox_item(int(inbox_match.group(1))))
            except ValueError as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=404)
            return
        self.send_error(404)

    def handle_json(self, fn, status=200):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(body or "{}")
            result = fn(payload)
            self.send_json(result, status=status)
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except json.JSONDecodeError:
            self.send_json({"ok": False, "error": "Invalid JSON."}, status=400)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)

    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, path):
        if path == "/":
            path = "/index.html"
        requested = (PUBLIC / unquote(path.lstrip("/"))).resolve()
        if not str(requested).startswith(str(PUBLIC.resolve())):
            self.send_error(403)
            return
        if not requested.exists() or requested.is_dir():
            self.send_error(404)
            return
        mime_type, _ = mimetypes.guess_type(str(requested))
        body = requested.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))


class LifeBrainServer(ThreadingHTTPServer):
    allow_reuse_address = True


GOOGLE_TASKS_API = "https://tasks.googleapis.com/tasks/v1"


def google_tasks_call(token, method, path, payload=None):
    body, _ = json_request(
        f"{GOOGLE_TASKS_API}{path}",
        method=method,
        headers={"Authorization": f"Bearer {token}"},
        payload=payload,
    )
    return body


TODAY_LIST_TITLE = "Between · Today"


CANVAS_CALENDAR_NAME = "canvas"


def find_calendar_id_by_name(token, name):
    listing = google_calendar_call(token, "GET", "/users/me/calendarList?maxResults=250")
    for cal in listing.get("items", []):
        label = cal.get("summaryOverride") or cal.get("summary", "")
        if label.strip().lower() == name.strip().lower():
            return cal["id"]
    return None


def sync_canvas_calendar():
    """Import Canvas due dates from the Canvas calendar as school tasks.

    These are deadlines, not busy time, so they never block free time.
    """
    config = load_config()
    tz = app_timezone(config)
    token = google_access_token()
    calendar_id = find_calendar_id_by_name(token, config.get("CANVAS_CALENDAR_NAME", CANVAS_CALENDAR_NAME))
    if not calendar_id:
        raise ValueError("No calendar named Canvas was found on this Google account.")
    now = datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    query = urlencode({
        "timeMin": start.isoformat(),
        "timeMax": (start + timedelta(days=60)).isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 250,
    })
    events = google_calendar_call(
        token, "GET", f"/calendars/{quote(calendar_id, safe='')}/events?{query}"
    ).get("items", [])

    created = updated = skipped = 0
    stamp = now_iso()
    with connect() as conn:
        area_id = area_id_for_slug(conn, "school")
        for event in events:
            start_info = event.get("start", {})
            due = task_rules.valid_date(start_info.get("date") or (start_info.get("dateTime") or "")[:10])
            # Drop Canvas course codes like "[2026FallB-X-ASB300]" from the title.
            title = normalize_text(re.sub(r"\s*\[[^\]]*\]\s*$", "", event.get("summary") or ""))
            event_id = event.get("id")
            if event.get("status") == "cancelled" or not due or not title or not event_id:
                skipped += 1
                continue
            external_id = f"cal:{event_id}"
            conn.execute(
                """
                INSERT INTO external_items (
                    source, external_id, title, item_type, area_id, url,
                    starts_at, due_at, raw_json, created_at, updated_at
                )
                VALUES ('canvas', ?, ?, 'assignment', ?, NULL, ?, ?, ?, ?, ?)
                ON CONFLICT(source, external_id) DO UPDATE SET
                    title = excluded.title,
                    area_id = excluded.area_id,
                    starts_at = excluded.starts_at,
                    due_at = excluded.due_at,
                    updated_at = excluded.updated_at
                """,
                (external_id, title, area_id, due, due, json.dumps({"date": due}), stamp, stamp),
            )
            external = conn.execute(
                "SELECT id FROM external_items WHERE source = 'canvas' AND external_id = ?",
                (external_id,),
            ).fetchone()
            existing = conn.execute(
                "SELECT id FROM tasks WHERE external_item_id = ?", (external["id"],)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE tasks SET title = ?, due_text = ?, due_date = ?, area_id = ?, updated_at = ? WHERE id = ?",
                    (title, due, due, area_id, stamp, existing["id"]),
                )
                updated += 1
            else:
                conn.execute(
                    """
                    INSERT INTO tasks (
                        external_item_id, title, area_id, status, due_text, due_date,
                        duration_minutes, energy, created_at, updated_at
                    )
                    VALUES (?, ?, ?, 'open', ?, ?, 45, 'medium', ?, ?)
                    """,
                    (external["id"], title, area_id, due, due, stamp, stamp),
                )
                created += 1
        conn.commit()
    return {"ok": True, "created": created, "updated": updated, "skipped": skipped}


_DAY_PLAN_CACHE = {"key": None, "blocks": None}


def gemini_json(prompt, config):
    """Ask Gemini for JSON. Tries each model in turn. Raises ValueError if all fail."""
    api_key = config["GEMINI_API_KEY"]
    models = [config["GEMINI_MODEL"]] if config.get("GEMINI_MODEL") else []
    models += [model for model in GEMINI_MODELS if model not in models]
    last_error = None
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            body, _ = json_request(
                url,
                method="POST",
                headers={"x-goog-api-key": api_key},
                payload={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json"},
                },
            )
            raw = body["candidates"][0]["content"]["parts"][0]["text"]
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
            last_error = ValueError("Gemini did not return an object.")
        except (ValueError, KeyError, IndexError, TypeError, OSError) as exc:  # OSError: timeouts move on to the next model
            last_error = exc
    raise ValueError(f"Gemini could not plan the day: {last_error}")


def gemini_day_plan(planned_input, gaps, config, today=None):
    """Ask Gemini to pick today's sessions and times inside the free time.

    planned_input: tasks with id, title, box, due, minutes (today's session length), skips.
    Only free-time ranges are sent, never calendar event titles.
    """
    today = today or datetime.now(app_timezone(config)).date()
    gap_text = "; ".join(f"{start:%H:%M}-{end:%H:%M}" for start, end in gaps) or "none"
    task_lines = []
    for task in planned_input:
        due = task_rules.valid_date(task.get("due"))
        task_lines.append({
            "task_id": task["id"],
            "title": task["title"],
            "category": task_rules.CATEGORY_NAMES[task_rules.CATEGORY_BY_BOX[task["box"]]],
            "session_minutes": task["minutes"],
            "due": due,
            "days_until_due": (date.fromisoformat(due) - today).days if due else None,
            "must_start_today": task_rules.must_start_today(dict(task, minutes=task.get("total_minutes")), today),
            "times_skipped": task.get("skips") or 0,
        })
    prompt = (
        "You plan a student's day. "
        f"Today is {today:%A, %B %d, %Y}. Free time today: {gap_text}. "
        f"Open tasks as JSON: {json.dumps(task_lines)}. "
        "Choose which tasks get a session today and when. Every task with must_start_today true goes today if it fits. "
        "Then prefer the nearest due dates: urgent and important first, then urgent, then important. "
        "Tasks skipped two or more times go after the others. At most two tasks without a due date. "
        f"Keep today's total under {task_rules.MAX_DAY_TASK_MINUTES} minutes. "
        "Tasks you leave out are scheduled on later days automatically, so don't cram. "
        "Each session lasts its session_minutes, must start inside a free stretch, and must end before that stretch ends. "
        "Leave 5 minutes between sessions. "
        "For each session give a reason of at most 15 plain words that says why today and why that time "
        "(for example the due date, or that it's a short task for a short gap). "
        'Return only JSON shaped like {"plan": [{"task_id": 1, "start": "15:10", "reason": "short reason"}]}.'
    )
    data = gemini_json(prompt, config)
    return data.get("plan", [])


GEMINI_PLAN_CACHE_SECONDS = 1800
GEMINI_RETRY_AFTER_FAILURE_SECONDS = 600
GEMINI_PLAN_MAX_TASKS = 25
_LAST_PLANNER = {"name": "rules", "note": None}


def gemini_today_blocks(planned, today_gaps, today, config):
    """Today's sessions chosen by Gemini and checked by validate_plan.

    Returns [] when Gemini isn't set up, fails, or gives nothing usable; the caller then
    uses the rule planner. Gemini's raw answer is cached for 30 minutes per (day, tasks,
    free-time shape) so the dashboard doesn't call it on every refresh.
    """
    if not configured(config, "GEMINI_API_KEY") or not today_gaps:
        return []
    candidates = [
        dict(task, minutes=task_rules.today_session_minutes(task), total_minutes=task.get("minutes"))
        for task in planned
        if (task.get("earliest") or today) <= today
    ]
    candidates.sort(key=lambda t: (task_rules.valid_date(t.get("due")) or "9999-12-31", task_rules.BOX_ORDER.get(t["box"], 9)))
    candidates = candidates[:GEMINI_PLAN_MAX_TASKS]
    if not candidates:
        return []
    key = (
        today.isoformat(),
        tuple((t["id"], t["minutes"], t["total_minutes"], t["box"], t.get("due"), t.get("skips") or 0) for t in candidates),
        tuple(end.isoformat() for _, end in today_gaps),
    )
    cached = _DAY_PLAN_CACHE
    failed_at = cached.get("failed_at")
    if failed_at is not None and monotonic() - failed_at < GEMINI_RETRY_AFTER_FAILURE_SECONDS:
        _LAST_PLANNER["note"] = "Gemini failed recently, used rules"
        return []
    if cached["key"] == key and monotonic() - cached.get("at", 0.0) < GEMINI_PLAN_CACHE_SECONDS:
        raw = cached["blocks"]
    else:
        try:
            raw = gemini_day_plan(candidates, today_gaps, config, today=today)
        except (ValueError, OSError) as exc:
            # Don't make every refresh wait on a failing Gemini; try again after a pause.
            cached["failed_at"] = monotonic()
            _LAST_PLANNER["note"] = f"Gemini unavailable, used rules ({str(exc)[:80]})"
            return []
        cached.update({"key": key, "blocks": raw, "at": monotonic(), "failed_at": None})
    blocks = task_rules.validate_plan(raw, today_gaps, candidates, max_total_minutes=task_rules.MAX_DAY_TASK_MINUTES)
    if not blocks:
        _LAST_PLANNER["note"] = "Gemini's plan didn't fit your free time, used rules"
    return blocks


def planning_day_gaps(days=task_rules.PLAN_HORIZON_DAYS):
    """Free time for each of the next `days` days, inside waking hours. {date: [(start, end)]}."""
    config = load_config()
    tz = app_timezone(config)
    now = datetime.now(tz)
    today = now.date()
    busy = busy_blocks_from_google(google_freebusy(days=days), tz)
    day_gaps = {}
    for offset in range(days):
        day = today + timedelta(days=offset)
        window_start = max(datetime(day.year, day.month, day.day, PLANNING_START_HOUR, tzinfo=tz), now)
        window_end = datetime(day.year, day.month, day.day, PLANNING_END_HOUR, tzinfo=tz)
        day_gaps[day] = gaps_between(window_start, window_end, busy) if window_end > window_start else []
    return day_gaps


_PLAN_CACHE = {"at": 0.0, "value": None}
PLAN_CACHE_SECONDS = 180


def plan_cache_clear():
    _PLAN_CACHE.update({"at": 0.0, "value": None})


def multi_day_plan():
    """The two-week plan: (blocks, unplaced_task_ids). Each block has a category and a reason."""
    if _PLAN_CACHE["value"] is not None and monotonic() - _PLAN_CACHE["at"] < PLAN_CACHE_SECONDS:
        return _PLAN_CACHE["value"]
    config = load_config()
    today = datetime.now(app_timezone(config)).date()
    tomorrow = today + timedelta(days=1)
    with connect() as conn:
        open_tasks = rows(
            conn,
            "SELECT id, title, box, due_date, duration_minutes, skips, last_skipped_on FROM tasks WHERE status = 'open'",
        )
    planned = []
    for task in open_tasks:
        skipped_today = task["last_skipped_on"] == today.isoformat()
        planned.append({
            "id": task["id"],
            "title": task["title"],
            "box": task_rules.effective_box(task["box"], task["due_date"], today),
            "due": task_rules.valid_date(task["due_date"]),
            "minutes": task["duration_minutes"],
            "skips": task["skips"] or 0,
            # "Not today" means no session today; the task picks up again tomorrow.
            "earliest": tomorrow if skipped_today else None,
            "skipped_today": skipped_today,
        })
    day_gaps = planning_day_gaps()
    _LAST_PLANNER.update({"name": "rules", "note": None})
    ai_blocks = gemini_today_blocks(planned, day_gaps.get(today, []), today, config)
    if ai_blocks:
        blocks, unplaced = task_rules.plan_with_today(ai_blocks, planned, day_gaps, today)
        _LAST_PLANNER["name"] = "gemini"
    else:
        blocks, unplaced = task_rules.spread_sessions(planned, day_gaps, today)
    task_rules.explain_blocks(blocks, planned, today)
    for block in blocks:
        block["category"] = task_rules.CATEGORY_BY_BOX.get(block.get("box"), "important")
    _PLAN_CACHE.update({"at": monotonic(), "value": (blocks, unplaced)})
    return blocks, unplaced


def today_payload():
    """Today's plan for the dashboard. Works without Google too (empty plan with a note)."""
    try:
        blocks = todays_blocks()
        _, unplaced = multi_day_plan()
    except ValueError as exc:
        return {"ok": True, "blocks": [], "unplaced": 0, "note": friendly_google_error(exc)}
    return {
        "ok": True,
        "unplaced": len(unplaced),
        "planner": _LAST_PLANNER["name"],
        "planner_note": _LAST_PLANNER["note"],
        "blocks": [
            {
                "task_id": b["task_id"],
                "title": b["title"],
                "start": b["start"].strftime("%H:%M"),
                "end": b["end"].strftime("%H:%M"),
                "minutes": int((b["end"] - b["start"]).total_seconds() // 60),
                "category": b["category"],
                "reason": b.get("reason", ""),
            }
            for b in blocks
        ],
    }


def todays_blocks():
    """Today's blocks from the two-week plan."""
    today = datetime.now(app_timezone()).date()
    blocks, _ = multi_day_plan()
    return [block for block in blocks if block["start"].date() == today]


def sync_tasks_to_google():
    """Make the Google Tasks list "Between · Today" show exactly today's planned tasks."""
    config = load_config()
    token = google_access_token()
    listing = google_tasks_call(token, "GET", "/users/@me/lists?maxResults=100")
    list_id = next((item["id"] for item in listing.get("items", []) if item["title"] == TODAY_LIST_TITLE), None)
    if list_id is None:
        list_id = google_tasks_call(token, "POST", "/users/@me/lists", {"title": TODAY_LIST_TITLE})["id"]

    # Clear yesterday's and earlier items, then write today's plan.
    existing = google_tasks_call(
        token, "GET", f"/lists/{list_id}/tasks?showCompleted=true&showHidden=true&maxResults=100"
    ).get("items", [])
    for item in existing:
        google_tasks_call(token, "DELETE", f"/lists/{list_id}/tasks/{item['id']}")

    app_url = config.get("APP_URL", "http://127.0.0.1:8765")
    blocks = todays_blocks()
    for block in blocks:
        minutes = int((block["end"] - block["start"]).total_seconds() // 60)
        google_tasks_call(
            token,
            "POST",
            f"/lists/{list_id}/tasks",
            {
                "title": f"{block['start'].strftime('%H:%M')} · {block['title']}",
                "notes": "\n".join(
                    part
                    for part in (
                        f"{task_rules.CATEGORY_NAMES[block['category']]} · {minutes} min",
                        f"Why: {block['reason']}" if block.get("reason") else "",
                        f"Open in Between: {app_url}",
                    )
                    if part
                ),
                "status": "needsAction",
            },
        )
    return {"ok": True, "list": TODAY_LIST_TITLE, "created": len(blocks), "cleared": len(existing)}


def skip_task(task_id):
    """Record a 'not today'. Non-urgent tasks that are skipped twice get moved to another slot."""
    with connect() as conn:
        row = conn.execute("SELECT id, box, skips FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise ValueError("Task not found.")
        skips = (row["skips"] or 0) + 1
        today = datetime.now(app_timezone()).date().isoformat()
        conn.execute(
            "UPDATE tasks SET skips = ?, last_skipped_on = ?, updated_at = ? WHERE id = ?",
            (skips, today, now_iso(), task_id),
        )
        conn.commit()
    plan_cache_clear()
    moved = task_rules.should_move_after_skip(skips, row["box"])
    return {
        "ok": True,
        "skips": skips,
        "moved": moved,
        "reason": (
            f"Off today's plan. Skipped {skips} times, so it now goes after your other work."
            if moved
            else "Off today's plan. It'll be back tomorrow."
        ),
    }


CALENDAR_API = "https://www.googleapis.com/calendar/v3"
BLOCK_TAG = "between"


def google_calendar_call(token, method, path, payload=None):
    body, _ = json_request(
        f"{CALENDAR_API}{path}",
        method=method,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        payload=payload,
    )
    return body


PLANNING_START_HOUR = 7
PLANNING_END_HOUR = 22


def free_gap_datetimes():
    """Free stretches from now until end of day, as (start, end) datetimes. No cache."""
    tz = app_timezone()
    now = datetime.now(tz)
    end_of_day = now.replace(hour=23, minute=59, second=0, microsecond=0)
    busy = busy_blocks_from_google(google_freebusy(days=1), tz)
    gaps = gaps_between(now, end_of_day, busy)
    # Plan only within waking hours, so nothing gets scheduled in the middle of the night.
    window_start = now.replace(hour=PLANNING_START_HOUR, minute=0, second=0, microsecond=0)
    window_end = now.replace(hour=PLANNING_END_HOUR, minute=0, second=0, microsecond=0)
    clipped = []
    for start, end in gaps:
        start, end = max(start, window_start), min(end, window_end)
        if end > start:
            clipped.append((start, end))
    return clipped


_BLOCK_SYNC_LOCK = threading.Lock()


def sync_blocks_to_calendar():
    """Put today's planned tasks into free time on Google Calendar.

    Removes the blocks this app made earlier today, then creates fresh ones.
    Only events tagged as Between blocks are ever deleted. One sync at a time, so the
    startup/30-minute sync and a manual sync can't delete each other's blocks.
    """
    with _BLOCK_SYNC_LOCK:
        return _sync_blocks_to_calendar()


def google_event_already_gone(exc):
    """True if Google says the event was already deleted (404/410)."""
    return str(exc).startswith(("404 ", "410 "))


def _sync_blocks_to_calendar():
    config = load_config()
    tz = app_timezone(config)
    calendar_id = config.get("GOOGLE_CALENDAR_ID", "primary")
    token = google_access_token()
    now = datetime.now(tz)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=task_rules.PLAN_HORIZON_DAYS)

    listing = google_calendar_call(
        token,
        "GET",
        f"/calendars/{calendar_id}/events?"
        + urlencode(
            {
                "privateExtendedProperty": f"{BLOCK_TAG}=block",
                "timeMin": day_start.isoformat(),
                "timeMax": day_end.isoformat(),
                "singleEvents": "true",
                "maxResults": 250,
            }
        ),
    )
    removed = 0
    for event in listing.get("items", []):
        try:
            google_calendar_call(token, "DELETE", f"/calendars/{calendar_id}/events/{event['id']}")
        except ValueError as exc:
            if not google_event_already_gone(exc):
                raise
        removed += 1

    blocks, _unplaced = multi_day_plan()
    for block in blocks:
        google_calendar_call(
            token,
            "POST",
            f"/calendars/{calendar_id}/events",
            {
                "summary": f"Between: {block['title']}",
                "description": "Open Between to start, log time, or mark it done.",
                "start": {"dateTime": block["start"].isoformat(), "timeZone": config.get("TIMEZONE", "America/Phoenix")},
                "end": {"dateTime": block["end"].isoformat(), "timeZone": config.get("TIMEZONE", "America/Phoenix")},
                "extendedProperties": {"private": {BLOCK_TAG: "block", "task_id": str(block["task_id"])}},
            },
        )
    return {"ok": True, "removed": removed, "created": len(blocks)}


SYNC_INTERVAL_SECONDS = 30 * 60


def friendly_google_error(exc):
    """Turn Google's long permission error into one plain line."""
    text = str(exc)
    if "insufficient authentication scopes" in text or "ACCESS_TOKEN_SCOPE_INSUFFICIENT" in text:
        return "Google needs one more permission. Run: /usr/bin/python3 scripts/google_auth.py and tick every box."
    if "has not been used in project" in text or "it is disabled" in text:
        return "A Google API is turned off for this project. Open the link in the error once to enable it: " + text[:300]
    return text[:300]


def run_scheduled_sync():
    """Sync Google Tasks and calendar blocks: once at startup, then every 30 minutes from 6am to 11pm."""
    sleep(5)  # let the server finish starting first
    first_run = True
    while True:
        hour = datetime.now(app_timezone()).hour
        if AUTO_SYNC_GOOGLE_TASKS and (first_run or 6 <= hour < 23):
            for label, job in (
                ("Canvas due dates", sync_canvas_calendar),
                ("Google Tasks", sync_tasks_to_google),
                ("Calendar blocks", sync_blocks_to_calendar),
            ):
                try:
                    job()
                except Exception as exc:
                    print(f"Scheduled {label} sync skipped: {friendly_google_error(exc)}", flush=True)
        first_run = False
        sleep(SYNC_INTERVAL_SECONDS)


def find_port(start):
    port = start
    while port < start + 20:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                port += 1
    raise RuntimeError("No free port found.")


def main():
    parser = argparse.ArgumentParser(description="Run the local Between app.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    init_db()
    port = find_port(args.port) if args.host in {"127.0.0.1", "localhost"} else args.port
    server = LifeBrainServer((args.host, port), Handler)
    print(f"Between running at http://{args.host}:{port}", flush=True)
    if args.host not in {"127.0.0.1", "localhost"}:
        # Never print the token: logs and terminal output get pasted around.
        for url in local_network_urls(port, "TOKEN"):
            print(f"Phone URL: {url.split('?')[0]}  (get the link with scripts/phone_link.py)", flush=True)
    print(f"Database: {DB_PATH}", flush=True)
    threading.Thread(target=run_scheduled_sync, daemon=True).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
