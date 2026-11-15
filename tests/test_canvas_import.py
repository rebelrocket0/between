import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
server.AUTO_SYNC_GOOGLE_TASKS = False

EVENTS = [
    {"id": "e1", "summary": "Module 5 Quiz [2026FallB-X-ASB300]", "start": {"date": "2026-11-22"}, "status": "confirmed"},
    {"id": "e2", "summary": "HW3 [2026FallC-T-DAT402]", "start": {"date": "2026-11-15"}, "status": "confirmed"},
]


def fake_calendar(token, method, path, payload=None):
    if path.startswith("/users/me/calendarList"):
        return {"items": [{"id": "cal-canvas", "summary": "canvas"}]}
    if "/events?" in path:
        return {"items": EVENTS}
    return {}


class CanvasImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.DATA = Path(self.tmp.name)
        server.DB_PATH = server.DATA / "test.sqlite"
        server.PHONE_TOKEN_PATH = server.DATA / "phone-token"
        server.init_db()
        server.load_config = lambda: {"TIMEZONE": "America/Phoenix"}
        server.google_access_token = lambda: "token"
        server.google_calendar_call = fake_calendar

    def tearDown(self):
        self.tmp.cleanup()

    def test_imports_once_and_updates_on_repeat(self):
        first = server.sync_canvas_calendar()
        second = server.sync_canvas_calendar()
        self.assertEqual((first["created"], second["created"]), (2, 0))
        self.assertEqual(second["updated"], 2)
        with server.connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        self.assertEqual(count, 2)

    def test_titles_drop_course_codes_and_keep_due_dates(self):
        server.sync_canvas_calendar()
        with server.connect() as conn:
            row = conn.execute("SELECT title, due_date FROM tasks WHERE due_date = '2026-11-22'").fetchone()
        self.assertEqual(row["title"], "Module 5 Quiz")

    def test_missing_canvas_calendar_is_reported(self):
        server.google_calendar_call = lambda token, method, path, payload=None: {"items": []}
        with self.assertRaises(ValueError):
            server.sync_canvas_calendar()


if __name__ == "__main__":
    unittest.main(verbosity=2)
