import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import task_rules as tr  # noqa: E402

TZ = ZoneInfo("America/Phoenix")
D = datetime(2026, 11, 15, 15, 0, tzinfo=TZ)
GAP = [(D, D + timedelta(hours=2))]
TASKS = [
    {"id": 1, "title": "A", "box": "plan", "minutes": 20},
    {"id": 2, "title": "B", "box": "do_now", "minutes": 30},
]


class ValidatePlanTests(unittest.TestCase):
    def test_keeps_valid_block(self):
        blocks = tr.validate_plan([{"task_id": 1, "start": "15:10", "reason": "soon"}], GAP, TASKS)
        self.assertEqual(blocks[0]["start"].strftime("%H:%M"), "15:10")
        self.assertEqual(blocks[0]["reason"], "soon")

    def test_rejects_unknown_task(self):
        self.assertEqual(tr.validate_plan([{"task_id": 99, "start": "15:10"}], GAP, TASKS), [])

    def test_rejects_duplicate_task(self):
        plan = [{"task_id": 1, "start": "15:10"}, {"task_id": 1, "start": "15:40"}]
        self.assertEqual(len(tr.validate_plan(plan, GAP, TASKS)), 1)

    def test_rejects_time_outside_gap(self):
        self.assertEqual(tr.validate_plan([{"task_id": 1, "start": "20:00"}], GAP, TASKS), [])

    def test_rejects_block_running_past_gap(self):
        self.assertEqual(tr.validate_plan([{"task_id": 2, "start": "16:45"}], GAP, TASKS), [])

    def test_rejects_bad_time_text(self):
        self.assertEqual(tr.validate_plan([{"task_id": 1, "start": "soon"}], GAP, TASKS), [])

    def test_rejects_non_list(self):
        self.assertEqual(tr.validate_plan({"oops": 1}, GAP, TASKS), [])

    def test_blocks_do_not_overlap(self):
        plan = [{"task_id": 1, "start": "15:00"}, {"task_id": 2, "start": "15:10"}]
        self.assertEqual(len(tr.validate_plan(plan, GAP, TASKS)), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
