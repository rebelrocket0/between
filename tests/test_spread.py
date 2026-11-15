import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import task_rules as tr  # noqa: E402

TZ = ZoneInfo("America/Phoenix")
TODAY = date(2026, 11, 15)


def day_window(day, start_hour=9, hours=8):
    start = datetime(day.year, day.month, day.day, start_hour, tzinfo=TZ)
    return [(start, start + timedelta(hours=hours))]


def gaps_for(days, **kwargs):
    return {TODAY + timedelta(days=i): day_window(TODAY + timedelta(days=i), **kwargs) for i in range(days)}


class SpreadTests(unittest.TestCase):
    def test_one_session_per_day_spreads_work(self):
        task = {"id": 1, "title": "Paper", "box": "plan", "due": "2026-11-20", "minutes": 180}
        blocks, unplaced = tr.spread_sessions([task], gaps_for(14), TODAY)
        days = [b["start"].date() for b in blocks]
        self.assertEqual(len(blocks), 3)
        self.assertEqual(len(set(days)), 3)
        self.assertEqual(unplaced, [])

    def test_work_stays_before_due_date(self):
        task = {"id": 1, "title": "Quiz", "box": "plan", "due": "2026-11-17", "minutes": 60}
        blocks, _ = tr.spread_sessions([task], gaps_for(14), TODAY)
        self.assertTrue(all(b["start"].date() <= date(2026, 11, 17) for b in blocks))

    def test_earliest_deadline_gets_time_first(self):
        soon = {"id": 1, "title": "Soon", "box": "plan", "due": "2026-11-16", "minutes": 60}
        later = {"id": 2, "title": "Later", "box": "plan", "due": "2026-11-25", "minutes": 60}
        blocks, _ = tr.spread_sessions([later, soon], gaps_for(14), TODAY)
        self.assertEqual(blocks[0]["task_id"], 1)

    def test_no_deadline_uses_the_horizon(self):
        task = {"id": 1, "title": "Someday", "box": "someday", "due": None, "minutes": 60}
        blocks, unplaced = tr.spread_sessions([task], gaps_for(14), TODAY)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(unplaced, [])

    def test_daily_cap_is_respected(self):
        tasks = [{"id": i, "title": f"T{i}", "box": "plan", "due": "2026-11-16", "minutes": 120} for i in range(5)]
        blocks, unplaced = tr.spread_sessions(tasks, gaps_for(2, hours=12), TODAY)
        per_day = {}
        for b in blocks:
            per_day[b["start"].date()] = per_day.get(b["start"].date(), 0) + int((b["end"] - b["start"]).total_seconds() // 60)
        self.assertTrue(all(total <= tr.MAX_DAY_TASK_MINUTES for total in per_day.values()))
        self.assertTrue(unplaced)

    def test_blocks_do_not_overlap(self):
        tasks = [{"id": i, "title": f"T{i}", "box": "plan", "due": None, "minutes": 60} for i in range(3)]
        blocks, _ = tr.spread_sessions(tasks, gaps_for(3), TODAY)
        for a, b in zip(blocks, blocks[1:]):
            self.assertTrue(b["start"] >= a["end"])

    def test_no_free_time_means_unplaced(self):
        task = {"id": 1, "title": "Big", "box": "plan", "due": "2026-11-20", "minutes": 60}
        blocks, unplaced = tr.spread_sessions([task], {}, TODAY)
        self.assertEqual(blocks, [])
        self.assertEqual(unplaced, [1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
