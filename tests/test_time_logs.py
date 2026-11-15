import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class TimeLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.DATA = Path(self.tmp.name)
        server.DB_PATH = Path(self.tmp.name) / "test.sqlite"
        server.PHONE_TOKEN_PATH = Path(self.tmp.name) / "phone_capture_token"
        server.init_db()
        with server.connect() as conn:
            conn.execute(
                "INSERT INTO tasks (title, status, energy, created_at, updated_at, duration_minutes)"
                " VALUES ('Bayesian assignment', 'open', 'medium', ?, ?, 300)",
                (server.now_iso(), server.now_iso()),
            )
            conn.commit()
        self.task_id = 1

    def tearDown(self):
        self.tmp.cleanup()

    def test_logging_reduces_remaining(self):
        result = server.log_task_time(self.task_id, {"minutes": 60})
        self.assertEqual(result["logged_minutes"], 60)
        self.assertEqual(result["remaining_minutes"], 240)
        self.assertFalse(result["overrun"])
        self.assertIsNone(result["suggested_estimate"])

    def test_multiple_sessions_add_up(self):
        server.log_task_time(self.task_id, {"minutes": 60})
        result = server.log_task_time(self.task_id, {"minutes": 45})
        self.assertEqual(result["logged_minutes"], 105)
        self.assertEqual(result["remaining_minutes"], 195)

    def test_overrun_flags_and_suggests_estimate(self):
        result = server.log_task_time(self.task_id, {"minutes": 320})
        self.assertTrue(result["overrun"])
        self.assertEqual(result["remaining_minutes"], 0)
        # 320 + 60 = 380, rounded up to the next 15 minutes = 390
        self.assertEqual(result["suggested_estimate"], 390)

    def test_task_without_estimate_has_no_remaining(self):
        with server.connect() as conn:
            conn.execute("UPDATE tasks SET duration_minutes = NULL WHERE id = ?", (self.task_id,))
            conn.commit()
        result = server.log_task_time(self.task_id, {"minutes": 30})
        self.assertIsNone(result["remaining_minutes"])
        self.assertFalse(result["overrun"])

    def test_accepting_suggested_estimate_clears_overrun(self):
        server.log_task_time(self.task_id, {"minutes": 320})
        result = server.set_task_estimate(self.task_id, {"duration_minutes": 390})
        self.assertFalse(result["overrun"])
        self.assertEqual(result["remaining_minutes"], 70)

    def test_rejects_bad_input(self):
        for bad in [{"minutes": 0}, {"minutes": 721}, {"minutes": "lots"}, {}]:
            with self.assertRaises(ValueError):
                server.log_task_time(self.task_id, bad)

    def test_unknown_task_is_rejected(self):
        with self.assertRaises(ValueError):
            server.log_task_time(999, {"minutes": 10})

    def test_state_includes_logged_minutes(self):
        server.log_task_time(self.task_id, {"minutes": 25})
        state = server.get_state()
        self.assertEqual(state["tasks"][0]["logged_minutes"], 25)


if __name__ == "__main__":
    unittest.main()
