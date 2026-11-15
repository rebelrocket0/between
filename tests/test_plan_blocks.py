import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import task_rules  # noqa: E402

BASE = datetime(2026, 11, 15, 15, 0)


def gap(start_hour_min, minutes):
    start = BASE + timedelta(minutes=start_hour_min)
    return (start, start + timedelta(minutes=minutes))


def task(task_id, box, minutes, title=None):
    return {"id": task_id, "title": title or f"Task {task_id}", "box": box, "minutes": minutes}


class PlanBlocksTests(unittest.TestCase):
    def test_do_now_goes_first(self):
        blocks = task_rules.plan_blocks([gap(0, 60)], [task(1, "plan", 20), task(2, "do_now", 30)])
        self.assertEqual(blocks[0]["task_id"], 2)

    def test_small_tasks_first_within_a_box(self):
        blocks = task_rules.plan_blocks([gap(0, 120)], [task(1, "plan", 60), task(2, "plan", 20)])
        self.assertEqual([b["task_id"] for b in blocks], [2, 1])

    def test_blocks_are_separated_by_buffer(self):
        blocks = task_rules.plan_blocks([gap(0, 60)], [task(1, "do_now", 20), task(2, "do_now", 20)])
        self.assertEqual(blocks[1]["start"], blocks[0]["end"] + timedelta(minutes=task_rules.BLOCK_BUFFER_MINUTES))

    def test_task_that_does_not_fit_is_left_out(self):
        blocks = task_rules.plan_blocks([gap(0, 25)], [task(1, "do_now", 60)])
        self.assertEqual(blocks, [])

    def test_length_is_clamped(self):
        blocks = {b["task_id"]: b for b in task_rules.plan_blocks([gap(0, 300)], [task(1, "plan", 999), task(2, "plan", 1)])}
        self.assertEqual(blocks[1]["end"] - blocks[1]["start"], timedelta(minutes=task_rules.MAX_BLOCK_MINUTES))
        self.assertEqual(blocks[2]["end"] - blocks[2]["start"], timedelta(minutes=task_rules.MIN_BLOCK_MINUTES))

    def test_no_minutes_uses_default(self):
        blocks = task_rules.plan_blocks([gap(0, 60)], [task(1, "plan", None)])
        self.assertEqual(blocks[0]["end"] - blocks[0]["start"], timedelta(minutes=task_rules.DEFAULT_BLOCK_MINUTES))

    def test_someday_is_capped(self):
        tasks = [task(i, "someday", 15) for i in range(1, 6)]
        blocks = task_rules.plan_blocks([gap(0, 600)], tasks)
        self.assertEqual(len(blocks), task_rules.MAX_SOMEDAY_BLOCKS)

    def test_no_gaps_no_blocks(self):
        self.assertEqual(task_rules.plan_blocks([], [task(1, "do_now", 20)]), [])

    def test_often_skipped_task_goes_behind_its_box(self):
        skipped = {"id": 1, "title": "Skipped", "box": "plan", "minutes": 20, "skips": 2}
        fresh = {"id": 2, "title": "Fresh", "box": "plan", "minutes": 20, "skips": 0}
        blocks = task_rules.plan_blocks([gap(0, 25)], [skipped, fresh])
        self.assertEqual(blocks[0]["task_id"], 2)

    def test_do_now_is_not_pushed_back_by_skips(self):
        skipped = {"id": 1, "title": "Urgent", "box": "do_now", "minutes": 10, "skips": 5}
        fresh = {"id": 2, "title": "Other", "box": "do_now", "minutes": 20, "skips": 0}
        blocks = task_rules.plan_blocks([gap(0, 25)], [skipped, fresh])
        self.assertEqual(blocks[0]["task_id"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
