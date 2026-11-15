"""Smart Canvas integration tests: temporary SQLite, mocked Google and Gemini only."""
import concurrent.futures
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("smart_canvas_server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
server.AUTO_SYNC_GOOGLE_TASKS = False
REAL_JSON_REQUEST = server.json_request


def event(identifier="exam-2", title="STP 421 Exam 2", due="2026-11-22"):
    return {"id": identifier, "summary": title, "start": {"date": due}, "status": "confirmed",
            "htmlLink": "https://calendar.example/event", "description": "Only source metadata; not supplied to Gemini"}


def model_response(title="Study for STP 421 Exam 2", kind="exam", minutes=180):
    raw = json.dumps({"title": title, "assignment_type": kind, "minutes": minutes})
    return {"candidates": [{"content": {"parts": [{"text": raw}]}}]}, {}


class SmartCanvasTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = {"TIMEZONE": "America/Phoenix", "GEMINI_API_KEY": "fake-key", "GEMINI_MODEL": "test-model"}
        server.DATA = Path(self.tmp.name)
        server.DB_PATH = server.DATA / "test.sqlite"
        server.PHONE_TOKEN_PATH = server.DATA / "phone-token"
        self.patch(server, "load_config", lambda: dict(self.config))
        self.patch(server, "google_access_token", lambda: "fake-google-token")
        self.events = [event()]
        self.patch(server, "google_calendar_call", self.google)
        self.ai = self.patch(server, "json_request", Mock(return_value=model_response()))
        # This suite isolates Phase 2 processing; the intelligence suite covers real child creation.
        self.patch(server, "ensure_task_steps", Mock())
        server.init_db()
        server.plan_cache_clear()

    def patch(self, obj, name, value):
        patcher = patch.object(obj, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def google(self, token, method, path, payload=None):
        if path.startswith("/users/me/calendarList"):
            return {"items": [{"id": "test-canvas-calendar", "summary": "canvas"}]}
        if "/events?" in path:
            return {"items": self.events}
        raise AssertionError("Unexpected Google call")

    def task(self):
        with server.connect() as conn:
            return dict(conn.execute("SELECT * FROM tasks ORDER BY id LIMIT 1").fetchone())

    def external(self):
        with server.connect() as conn:
            return dict(conn.execute("SELECT * FROM external_items ORDER BY id LIMIT 1").fetchone())

    def test_new_import_uses_validated_gemini_result_and_preserves_source(self):
        self.assertEqual(server.sync_canvas_calendar()["created"], 1)
        task = self.task()
        self.assertEqual((task["title"], task["assignment_type"], task["duration_minutes"]),
                         ("Study for STP 421 Exam 2", "exam", 180))
        external = self.external()
        self.assertEqual(external["external_id"], "cal:exam-2")
        self.assertEqual(external["title"], "STP 421 Exam 2")
        self.assertEqual(json.loads(external["raw_json"])["event"], self.events[0])
        processing = json.loads(external["processing_json"])
        self.assertEqual(processing["method"], "gemini")
        self.assertEqual(processing["original_title"], self.events[0]["summary"])
        self.assertEqual(processing["original_source"]["calendar_id"], "test-canvas-calendar")
        self.assertEqual(task["due_date"], "2026-11-22")

    def test_repeated_import_does_not_duplicate_or_call_gemini(self):
        server.sync_canvas_calendar()
        server.sync_canvas_calendar()
        self.assertEqual(self.ai.call_count, 1)
        with server.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM external_items").fetchone()[0], 1)

    def test_duplicate_events_in_one_response_are_processed_once(self):
        self.events.append(dict(self.events[0]))
        result = server.sync_canvas_calendar()
        self.assertEqual((result["created"], result["updated"]), (1, 1))
        self.assertEqual(self.ai.call_count, 1)

    def test_distinct_source_ids_with_the_same_title_stay_separate(self):
        self.events.append(event(identifier="another-exam"))
        self.assertEqual(server.sync_canvas_calendar()["created"], 2)
        self.assertEqual(self.ai.call_count, 2)

    def test_json_request_honors_the_canvas_timeout(self):
        # Check the HTTP boundary, not just the keyword sent to a mocked helper.
        import io
        response = io.BytesIO(b'{}')
        response.headers = {}
        with patch.object(server, "urlopen", return_value=response) as opened:
            REAL_JSON_REQUEST("https://example.invalid", timeout=8)
        self.assertEqual(opened.call_args.kwargs["timeout"], 8)

    def test_changed_deadline_updates_task_and_metadata_without_reprocessing(self):
        server.sync_canvas_calendar()
        self.events[0]["start"] = {"dateTime": "2026-11-25T18:00:00-07:00"}
        server._PLAN_CACHE.update({"at": server.monotonic(), "value": ([], [])})
        server.sync_canvas_calendar()
        self.assertEqual(self.task()["due_date"], "2026-11-25")
        self.assertEqual(self.external()["due_at"], "2026-11-25T18:00:00-07:00")
        self.assertEqual(self.task()["due_text"], "2026-11-25")
        original = json.loads(self.external()["processing_json"])["original_source"]
        self.assertEqual(original["event"]["start"], {"date": "2026-11-22"})
        self.assertEqual(self.ai.call_count, 1)
        self.assertIsNone(server._PLAN_CACHE["value"])

    def test_user_estimate_is_never_overwritten(self):
        server.sync_canvas_calendar()
        server.set_task_estimate(self.task()["id"], {"duration_minutes": 235})
        server.sync_canvas_calendar()
        self.assertEqual(self.task()["duration_minutes"], 235)
        self.assertEqual(self.ai.call_count, 1)

    def test_user_title_survives_source_title_changes(self):
        server.sync_canvas_calendar()
        with server.connect() as conn:
            conn.execute("UPDATE tasks SET title = 'My exam preparation plan'")
        self.events[0]["summary"] = "STP 421 Exam 2 (revised)"
        server.sync_canvas_calendar()
        self.assertEqual(self.task()["title"], "My exam preparation plan")
        self.assertEqual(self.external()["title"], "STP 421 Exam 2 (revised)")
        self.assertEqual(json.loads(self.external()["processing_json"])["original_title"], "STP 421 Exam 2")
        self.assertEqual(self.ai.call_count, 1)

    def test_completed_task_and_time_logs_survive_repeat_sync(self):
        server.sync_canvas_calendar()
        task_id = self.task()["id"]
        server.log_task_time(task_id, {"minutes": 35})
        server.update_task(task_id, {"status": "done"})
        server.sync_canvas_calendar()
        self.assertEqual(self.task()["status"], "done")
        with server.connect() as conn:
            self.assertEqual(conn.execute("SELECT minutes FROM time_logs WHERE task_id = ?", (task_id,)).fetchone()[0], 35)
        self.assertEqual(self.ai.call_count, 1)

    def test_invalid_model_outputs_use_persisted_fallback(self):
        for response in ({}, {"candidates": []}, model_response(minutes=1)[0],
                         model_response(title="Study for STP 421 Exam 2 chapter 9")[0]):
            with self.subTest(response=response):
                self.ai.return_value = (response, {})
                self.events = [event(identifier="bad-" + str(self.ai.call_count))]
                server.sync_canvas_calendar()
                before = self.ai.call_count
                server.sync_canvas_calendar()
                self.assertEqual(self.ai.call_count, before)
        with server.connect() as conn:
            rows = conn.execute("SELECT processing_json FROM external_items").fetchall()
        self.assertTrue(all(json.loads(r[0])["method"] == "rules" for r in rows))

    def test_timeout_uses_rules_once_without_logging_response_or_key(self):
        self.ai.side_effect = TimeoutError("fake-key should never be logged")
        with patch("builtins.print") as printed:
            server.sync_canvas_calendar()
            server.sync_canvas_calendar()
        printed.assert_not_called()
        self.assertEqual(self.ai.call_count, 1)
        self.assertEqual(self.task()["duration_minutes"], 180)
        self.assertEqual(json.loads(self.external()["processing_json"])["method"], "rules")

    def test_request_is_structured_title_only_and_bounded(self):
        server.sync_canvas_calendar()
        request = self.ai.call_args.kwargs
        self.assertEqual(request["timeout"], 8)
        generation = request["payload"]["generationConfig"]
        self.assertEqual(generation["responseMimeType"], "application/json")
        self.assertEqual(set(generation["responseSchema"]["required"]), {"title", "assignment_type", "minutes"})
        prompt = request["payload"]["contents"][0]["parts"][0]["text"]
        self.assertIn("STP 421 Exam 2", prompt)
        self.assertNotIn(self.events[0]["description"], prompt)
        self.assertNotIn("calendar.example", prompt)
        self.assertNotIn("fake-key", prompt)

    def test_no_key_uses_rules_and_does_not_later_reprocess(self):
        self.config.pop("GEMINI_API_KEY")
        server.sync_canvas_calendar()
        self.config["GEMINI_API_KEY"] = "fake-key"
        server.sync_canvas_calendar()
        self.ai.assert_not_called()
        self.assertEqual(self.task()["assignment_type"], "exam")

    def test_long_source_title_skips_model(self):
        self.events[0]["summary"] = "Project " + "context " * 100
        server.sync_canvas_calendar()
        self.ai.assert_not_called()
        self.assertEqual(self.external()["title"], self.events[0]["summary"])

    def test_source_title_is_preserved_exactly(self):
        self.config.pop("GEMINI_API_KEY")
        self.events[0]["summary"] = "  STP 421   Exam 2  "
        server.sync_canvas_calendar()
        self.assertEqual(self.external()["title"], "  STP 421   Exam 2  ")
        self.assertEqual(json.loads(self.external()["processing_json"])["original_title"], "  STP 421   Exam 2  ")

    def test_utc_deadline_is_converted_to_the_planning_day(self):
        self.events[0]["start"] = {"dateTime": "2026-11-23T02:00:00Z"}
        server.sync_canvas_calendar()
        self.assertEqual(self.task()["due_date"], "2026-11-22")
        self.assertEqual(self.external()["due_at"], "2026-11-23T02:00:00Z")

    def test_restart_keeps_processing_decision(self):
        server.sync_canvas_calendar()
        server.init_db()
        self.ai.reset_mock()
        server.sync_canvas_calendar()
        self.ai.assert_not_called()

    def test_corrupt_provenance_does_not_overwrite_existing_work(self):
        server.sync_canvas_calendar()
        for bad in ('not json', '{"result": []}', '{"result": {}}',
                    '{"result": {"title": "Bad", "assignment_type": [], "minutes": 10}}'):
            with server.connect() as conn:
                conn.execute("UPDATE external_items SET processing_json = ?", (bad,))
                conn.execute("UPDATE tasks SET title = 'My task', duration_minutes = 275")
            server.sync_canvas_calendar()
            self.assertEqual((self.task()["title"], self.task()["duration_minutes"]), ("My task", 275))
        self.assertEqual(self.ai.call_count, 1)

    def test_invalid_or_cancelled_events_do_not_call_model(self):
        self.events = [event(due="invalid"), event(title=""), dict(event(), status="cancelled"),
                       {"summary": "No identifier", "start": {"date": "2026-11-22"}}]
        self.assertEqual(server.sync_canvas_calendar()["skipped"], 4)
        self.ai.assert_not_called()

    def test_concurrent_syncs_do_not_process_or_insert_twice(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: server.sync_canvas_calendar(), range(2)))
        self.assertEqual(sum(r["created"] for r in results), 1)
        self.assertEqual(self.ai.call_count, 1)

    def test_legacy_task_values_are_preserved_without_gemini(self):
        self.config.pop("GEMINI_API_KEY")
        server.sync_canvas_calendar()
        with server.connect() as conn:
            conn.execute("UPDATE external_items SET processing_json = NULL")
            conn.execute("UPDATE tasks SET title = 'Legacy custom title', duration_minutes = 213, status = 'done', assignment_type = NULL")
        self.config["GEMINI_API_KEY"] = "fake-key"
        server.sync_canvas_calendar()
        task = self.task()
        self.assertEqual((task["title"], task["duration_minutes"], task["status"]), ("Legacy custom title", 213, "done"))
        self.ai.assert_not_called()
        self.assertEqual(json.loads(self.external()["processing_json"])["method"], "legacy-preserved")

    def test_direct_canvas_import_shares_processing_and_edit_protection(self):
        self.patch(server, "canvas_fetch_assignments", lambda: [
            {"id": "42", "title": "STP 421 Exam 2", "start_at": "2026-11-22T12:00:00Z", "description": "source"}])
        server.sync_canvas_assignments()
        server.set_task_estimate(self.task()["id"], {"duration_minutes": 220})
        server.sync_canvas_assignments()
        self.assertEqual(self.task()["duration_minutes"], 220)
        self.assertEqual(self.task()["due_date"], "2026-11-22")
        self.assertEqual(self.external()["external_id"], "42")
        self.assertEqual(self.ai.call_count, 1)

    def test_exam_work_is_spread_as_sessions_without_subtasks(self):
        from datetime import date, datetime, timedelta
        server.sync_canvas_calendar()
        task = self.task()
        today = date(2026, 11, 20)
        gaps = {today + timedelta(days=i): [(datetime(2026, 11, 20 + i, 10), datetime(2026, 11, 20 + i, 14))] for i in range(3)}
        blocks, unplaced = server.task_rules.spread_sessions([
            {"id": task["id"], "title": task["title"], "box": "plan", "minutes": task["duration_minutes"], "due": task["due_date"]}], gaps, today)
        self.assertEqual(len(blocks), 3)
        self.assertEqual(unplaced, [])
        self.assertTrue(all(b["task_id"] == task["id"] for b in blocks))


class LegacySchemaTests(unittest.TestCase):
    def test_migration_is_additive_repeatable_and_preserves_old_data(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "old.sqlite"
            # Relevant pre-Phase-2 tables, including existing IDs and progress data.
            with sqlite3.connect(db) as conn:
                conn.executescript("""
                    CREATE TABLE tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, inbox_item_id INTEGER,
                        external_item_id INTEGER, title TEXT NOT NULL, area_id INTEGER,
                        status TEXT NOT NULL DEFAULT 'open', due_text TEXT, duration_minutes INTEGER,
                        energy TEXT NOT NULL, scheduled_for TEXT, created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL, box TEXT, due_date TEXT,
                        skips INTEGER NOT NULL DEFAULT 0, last_skipped_on TEXT,
                        google_task_id TEXT, google_box TEXT
                    );
                    CREATE TABLE external_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL,
                        external_id TEXT NOT NULL, title TEXT NOT NULL, item_type TEXT NOT NULL,
                        area_id INTEGER, url TEXT, starts_at TEXT, due_at TEXT, raw_json TEXT NOT NULL,
                        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                        UNIQUE(source, external_id)
                    );
                    CREATE TABLE time_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL,
                        minutes INTEGER NOT NULL, logged_at TEXT NOT NULL
                    );
                """)
            with sqlite3.connect(db) as conn:
                conn.execute("INSERT INTO tasks (title, duration_minutes, status, energy, created_at, updated_at) VALUES ('Legacy task', 117, 'done', 'medium', '2026-11-15', '2026-11-15')")
                conn.execute("INSERT INTO time_logs (task_id, minutes, logged_at) VALUES (1, 25, '2026-11-15')")
            with patch.object(server, "DATA", Path(folder)), patch.object(server, "DB_PATH", db), patch.object(server, "load_config", lambda: {"TIMEZONE": "America/Phoenix"}):
                server.init_db()
                server.init_db()
            with sqlite3.connect(db) as conn:
                self.assertEqual(conn.execute("SELECT title, duration_minutes, status, assignment_type FROM tasks").fetchone(), ("Legacy task", 117, "done", None))
                self.assertEqual(conn.execute("SELECT minutes FROM time_logs").fetchone()[0], 25)
                self.assertIn("processing_json", [r[1] for r in conn.execute("PRAGMA table_info(external_items)")])


if __name__ == "__main__":
    unittest.main()
