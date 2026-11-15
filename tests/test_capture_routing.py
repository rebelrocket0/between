import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class TitleTests(unittest.TestCase):
    def test_hours_are_removed_from_title(self):
        self.assertEqual(
            server.clean_title("Complete bayesian statistics assignment 5 hours"),
            "Complete bayesian statistics assignment",
        )

    def test_for_minutes_is_removed_from_title(self):
        self.assertEqual(server.clean_title("Read chapter 3 for 20 min"), "Read chapter 3")

    def test_prefix_and_minutes_are_both_removed(self):
        self.assertEqual(server.clean_title("Need to email Prof K 5 min"), "Email Prof K")

    def test_plain_numbers_are_kept(self):
        self.assertEqual(server.clean_title("Read chapter 3"), "Read chapter 3")


class RoutingTests(unittest.TestCase):
    def test_capture_with_duration_routes_as_task(self):
        result = server.classify("Read chapter 3 for 20 min")
        self.assertEqual(result["kind"], "task")
        self.assertEqual(result["status"], "routed")
        self.assertEqual(result["duration_minutes"], 20)

    def test_vague_capture_still_goes_to_review(self):
        result = server.classify("clean")
        self.assertEqual(result["status"], "review")


if __name__ == "__main__":
    unittest.main()
