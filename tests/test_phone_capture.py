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
PLAIN_CONFIG = {"TIMEZONE": "America/Phoenix"}  # never read the real .env in tests


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
        server.load_config = lambda: dict(PLAIN_CONFIG)

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

    def test_non_ascii_token_is_refused_not_crashed(self):
        self.assertFalse(authorized("192.168.1.20", "/api/capture/%C3%A9t%C3%A9"))

    def test_shortcut_body_creates_a_capture(self):
        server.DB_PATH = server.DATA / "test.sqlite"
        server.init_db()
        server.load_config = lambda: {"TIMEZONE": "America/Phoenix"}  # no Gemini key: rule routing
        result = server.create_capture({"text": "email professor about extension", "source": "phone"})
        self.assertTrue(result["ok"])


class BehindProxyTests(unittest.TestCase):
    """Hosted behind Caddy on the same machine: every request looks local, so none is trusted."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.DATA = Path(self.tmp.name)
        server.PHONE_TOKEN_PATH = server.DATA / "phone_capture_token"
        self.token = server.get_or_create_phone_token()
        self.config = {"TIMEZONE": "America/Phoenix", "BETWEEN_BEHIND_PROXY": "1"}
        server.load_config = lambda: dict(self.config)

    def tearDown(self):
        server.load_config = lambda: dict(PLAIN_CONFIG)
        self.tmp.cleanup()

    def test_loopback_needs_the_token_behind_a_proxy(self):
        for address in ("127.0.0.1", "::1", "172.18.0.3"):
            self.assertFalse(authorized(address, "/api/today"), address)
            self.assertFalse(authorized(address, "/api/setup"), address)
            self.assertFalse(authorized(address, "/api/setup/reset-token"), address)
            self.assertFalse(authorized(address, "/api/capture"), address)

    def test_token_works_every_way_behind_a_proxy(self):
        self.assertTrue(authorized("127.0.0.1", f"/api/capture/{self.token}"))
        self.assertTrue(authorized("127.0.0.1", "/api/today", {"X-Life-Brain-Token": self.token}))
        self.assertTrue(authorized("127.0.0.1", "/api/today", {"Authorization": f"Bearer {self.token}"}))
        self.assertTrue(authorized("127.0.0.1", f"/api/today?token={self.token}"))

    def test_wrong_or_empty_token_is_refused_behind_a_proxy(self):
        self.assertFalse(authorized("127.0.0.1", "/api/today", {"X-Life-Brain-Token": "wrong"}))
        self.assertFalse(authorized("127.0.0.1", "/api/today?token="))

    def test_dashboard_files_load_without_a_token(self):
        # The page itself has no data; it reads ?token= and sends it on API calls.
        for path in ("/", "/app.js", "/styles.css"):
            self.assertTrue(authorized("127.0.0.1", path))

    def test_proxy_flag_values(self):
        for value, expected in (("1", True), ("true", True), ("yes", True), ("0", False), ("", False)):
            self.config["BETWEEN_BEHIND_PROXY"] = value
            self.assertEqual(server.behind_proxy(), expected, value)

    def test_without_the_flag_the_mac_is_still_trusted(self):
        del self.config["BETWEEN_BEHIND_PROXY"]
        self.assertTrue(authorized("127.0.0.1", "/api/today"))


class DashboardTokenTests(unittest.TestCase):
    """No browser here, so check the dashboard code for the token handling it must have."""

    def test_app_js_keeps_and_sends_the_token(self):
        js = (ROOT / "public" / "app.js").read_text()
        self.assertIn('searchParams.get("token")', js)
        self.assertIn("localStorage.setItem(TOKEN_KEY", js)
        self.assertIn('searchParams.delete("token")', js)
        self.assertIn("history.replaceState", js)
        self.assertIn('"X-Life-Brain-Token": token', js)
        self.assertEqual(js.count("fetch("), 1, "every API call must go through api()")

    def test_service_worker_never_caches_token_urls(self):
        self.assertIn('searchParams.has("token")', (ROOT / "public" / "sw.js").read_text())


if __name__ == "__main__":
    unittest.main(verbosity=0)
