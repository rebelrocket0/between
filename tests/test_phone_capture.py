"""Phone capture over home Wi-Fi: token checks and the token file. No network."""
import importlib.util
import stat
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
server.AUTO_SYNC_GOOGLE_TASKS = False  # never touch the real Google account from tests


class FakeRequest:
    """Just enough of a request handler for is_authorized."""

    def __init__(self, address, headers=None):
        self.client_address = (address, 50000)
        self.headers = headers or {}


def authorized(address, path, headers=None):
    return server.Handler.is_authorized(FakeRequest(address, headers), urlparse(path))


class PhoneTokenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.DATA = Path(self.tmp.name)
        server.PHONE_TOKEN_PATH = server.DATA / "phone_capture_token"
        self.token = server.get_or_create_phone_token()

    def tearDown(self):
        self.tmp.cleanup()

    def test_token_file_is_owner_only(self):
        mode = stat.S_IMODE(server.PHONE_TOKEN_PATH.stat().st_mode)
        self.assertEqual(mode, 0o600)
        server.reset_phone_token()
        self.assertEqual(stat.S_IMODE(server.PHONE_TOKEN_PATH.stat().st_mode), 0o600)

    def test_phone_capture_url_with_token_is_allowed(self):
        self.assertTrue(authorized("192.168.1.20", f"/api/capture/{self.token}"))

    def test_wrong_or_missing_token_is_refused_from_wifi(self):
        self.assertFalse(authorized("192.168.1.20", "/api/capture/wrong-token"))
        self.assertFalse(authorized("192.168.1.20", "/api/capture"))
        self.assertFalse(authorized("192.168.1.20", "/api/today"))

    def test_old_token_stops_working_after_reset(self):
        old = self.token
        server.reset_phone_token()
        self.assertFalse(authorized("192.168.1.20", f"/api/capture/{old}"))

    def test_mac_itself_needs_no_token(self):
        self.assertTrue(authorized("127.0.0.1", "/api/today"))

    def test_header_token_works_too(self):
        self.assertTrue(authorized("192.168.1.20", "/api/today", {"X-Life-Brain-Token": self.token}))

    def test_shortcut_body_creates_a_capture(self):
        server.DB_PATH = server.DATA / "test.sqlite"
        server.init_db()
        server.load_config = lambda: {"TIMEZONE": "America/Phoenix"}  # no Gemini key: rule routing
        result = server.create_capture({"text": "email professor about extension", "source": "phone"})
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=0)
