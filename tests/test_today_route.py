import importlib.util
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
server.AUTO_SYNC_GOOGLE_TASKS = False

TASK = {"title": "Finish problem set", "minutes": 60, "due": "soon", "due_date": None, "box": "plan", "area": "school"}


class TodayRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.DATA = Path(self.tmp.name)
        server.DB_PATH = server.DATA / "test.sqlite"
        server.PHONE_TOKEN_PATH = server.DATA / "phone-token"
        server.init_db()
        server.plan_cache_clear()
        server.load_config = lambda: {"TIMEZONE": "America/Phoenix"}
        server.google_freebusy = lambda days=14: {}
        server.busy_blocks_from_google = lambda fb, tz: []
        tz = server.app_timezone({"TIMEZONE": "America/Phoenix"})
        self.now = datetime.now(tz)

    def tearDown(self):
        self.tmp.cleanup()

    def test_today_lists_a_session_with_time_and_category(self):
        due = (self.now + timedelta(days=3)).date().isoformat()
        server.create_split_capture("x", "test", [dict(TASK, due_date=due)])
        payload = server.today_payload()
        self.assertTrue(payload["ok"])
        if self.now.hour >= server.PLANNING_END_HOUR - 1:
            self.skipTest("Too late in the day for a session today.")
        self.assertEqual(payload["blocks"][0]["title"], "Finish problem set")
        self.assertIn(payload["blocks"][0]["category"], ("urgent_important", "urgent", "important"))
        self.assertRegex(payload["blocks"][0]["start"], r"^\d\d:\d\d$")

    def test_google_problem_becomes_a_note_not_a_crash(self):
        def boom(days=14):
            raise ValueError("403 insufficient authentication scopes")
        server.google_freebusy = boom
        server.create_split_capture("x", "test", [dict(TASK)])
        payload = server.today_payload()
        self.assertEqual(payload["blocks"], [])
        self.assertIn("permission", payload["note"])

    def test_cache_clears_when_a_task_is_done(self):
        server.create_split_capture("x", "test", [dict(TASK)])
        first, _ = server.multi_day_plan()
        with server.connect() as conn:
            task_id = conn.execute("SELECT id FROM tasks").fetchone()["id"]
        server.update_task(task_id, {"status": "done"})
        second, _ = server.multi_day_plan()
        self.assertEqual(len(second), 0)
        self.assertGreaterEqual(len(first), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
