import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
server.AUTO_SYNC_GOOGLE_TASKS = False  # never touch the real Google account from tests


class PlanRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.DATA = Path(self.tmp.name)
        server.DB_PATH = Path(self.tmp.name) / "test.sqlite"
        server.PHONE_TOKEN_PATH = Path(self.tmp.name) / "phone_capture_token"
        server.init_db()
        now = server.now_iso()
        with server.connect() as conn:
            conn.executemany(
                "INSERT INTO tasks (title, status, energy, created_at, updated_at, duration_minutes, due_text)"
                " VALUES (?, 'open', 'medium', ?, ?, ?, ?)",
                [
                    ("Bayesian assignment", now, now, 300, None),
                    ("Email Prof K", now, now, 5, None),
                    ("Read chapter 3", now, now, 20, None),
                ],
            )
            conn.execute(
                "INSERT INTO time_logs (task_id, minutes, logged_at) VALUES (1, 60, ?)", (now,)
            )
            conn.commit()

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_for_one_hour_uses_logged_time(self):
        result = server.plan_for_window(60)
        self.assertTrue(result["ok"])
        titles = [p["title"] for p in result["plan"]]
        self.assertIn("Read chapter 3", titles)
        self.assertIn("Email Prof K", titles)
        total = sum(p["minutes"] for p in result["plan"])
        self.assertLessEqual(total, 60)

    def test_bayesian_session_respects_logged_time(self):
        result = server.plan_for_window(120)
        bayesian = [p for p in result["plan"] if p["title"] == "Bayesian assignment"][0]
        self.assertEqual(bayesian["minutes"], 90)  # capped session, not the 240 left

    def test_fits_count_is_returned(self):
        result = server.plan_for_window(30)
        self.assertEqual(result["fits"], 2)  # Email Prof K (5) and Read chapter 3 (20)


if __name__ == "__main__":
    unittest.main()
