"""Calendar block sync. Google is always mocked here."""
import importlib.util
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
server.AUTO_SYNC_GOOGLE_TASKS = False  # never touch the real Google account from tests

TZ = ZoneInfo("America/Phoenix")


class BlockSyncTests(unittest.TestCase):
    def setUp(self):
        server.load_config = lambda: {"TIMEZONE": "America/Phoenix"}
        server.google_access_token = lambda: "fake-token"
        start = datetime.now(TZ).replace(hour=10, minute=0, second=0, microsecond=0)
        self.blocks = [{"task_id": 1, "title": "Essay", "start": start, "end": start + timedelta(hours=1)}]
        server.multi_day_plan = lambda: (self.blocks, [])
        self.calls = []
        self.delete_error = None

        def fake_call(token, method, path, payload=None):
            self.calls.append((method, path))
            if method == "GET":
                return {"items": [{"id": "old1"}, {"id": "old2"}]}
            if method == "DELETE" and path.endswith("/old1") and self.delete_error:
                raise ValueError(self.delete_error)
            return {}

        server.google_calendar_call = fake_call

    def test_already_deleted_block_does_not_stop_the_sync(self):
        self.delete_error = '410 from connector: {"error": {"message": "Resource has been deleted"}}'
        result = server.sync_blocks_to_calendar()
        self.assertEqual(result, {"ok": True, "removed": 2, "created": 1})
        self.assertIn(("POST", "/calendars/primary/events"), self.calls)

    def test_missing_block_404_is_also_fine(self):
        self.delete_error = "404 from connector: Not Found"
        self.assertTrue(server.sync_blocks_to_calendar()["ok"])

    def test_other_errors_still_stop_the_sync(self):
        self.delete_error = "403 from connector: insufficient authentication scopes"
        with self.assertRaises(ValueError):
            server.sync_blocks_to_calendar()
        self.assertNotIn("POST", [method for method, _ in self.calls])

    def test_lock_is_released_after_an_error(self):
        self.delete_error = "500 from connector: boom"
        with self.assertRaises(ValueError):
            server.sync_blocks_to_calendar()
        self.assertFalse(server._BLOCK_SYNC_LOCK.locked())


if __name__ == "__main__":
    unittest.main(verbosity=0)
