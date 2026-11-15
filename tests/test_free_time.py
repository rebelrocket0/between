import importlib.util
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


def t(hour, minute=0):
    return datetime(2026, 11, 14, hour, minute)


class GapTests(unittest.TestCase):
    def test_free_all_day_when_nothing_busy(self):
        gaps = server.gaps_between(t(14), t(23, 59), [])
        self.assertEqual(gaps, [(t(14), t(23, 59))])

    def test_busy_meeting_splits_the_day(self):
        busy = [(t(15), t(16))]
        gaps = server.gaps_between(t(14), t(23, 59), busy)
        self.assertEqual(gaps, [(t(14), t(15)), (t(16), t(23, 59))])

    def test_meeting_in_progress_means_no_free_time_now(self):
        busy = [(t(13, 30), t(14, 30))]
        gaps = server.gaps_between(t(14), t(23, 59), busy)
        self.assertEqual(gaps[0][0], t(14, 30))

    def test_past_meetings_are_ignored(self):
        busy = [(t(9), t(10))]
        gaps = server.gaps_between(t(14), t(23, 59), busy)
        self.assertEqual(gaps, [(t(14), t(23, 59))])

    def test_overlapping_meetings_are_merged(self):
        busy = [(t(15), t(16)), (t(15, 30), t(17))]
        gaps = server.gaps_between(t(14), t(23, 59), busy)
        self.assertEqual(gaps, [(t(14), t(15)), (t(17), t(23, 59))])

    def test_no_free_time_after_day_ends(self):
        busy = [(t(14), t(23, 59))]
        self.assertEqual(server.gaps_between(t(14), t(23, 59), busy), [])


if __name__ == "__main__":
    unittest.main()
