import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gap_engine as g


def task(id, title, minutes, logged=0, due=None, status="open"):
    return {
        "id": id,
        "title": title,
        "status": status,
        "duration_minutes": minutes,
        "logged_minutes": logged,
        "due_text": due,
    }


class RemainingTests(unittest.TestCase):
    def test_remaining_subtracts_logged(self):
        self.assertEqual(g.remaining_minutes(task(1, "a", 300, logged=60)), 240)

    def test_remaining_never_negative(self):
        self.assertEqual(g.remaining_minutes(task(1, "a", 20, logged=35)), 0)

    def test_no_estimate_means_none(self):
        self.assertIsNone(g.remaining_minutes(task(1, "a", None)))


class FitsWindowTests(unittest.TestCase):
    def test_only_tasks_that_fit_are_returned(self):
        tasks = [task(1, "long", 120), task(2, "short", 20), task(3, "medium", 45)]
        ids = [t["id"] for t in g.fits_window(tasks, 60)]
        self.assertEqual(ids, [3, 2])  # largest that fits first

    def test_done_and_unestimated_tasks_are_left_out(self):
        tasks = [task(1, "done", 10, status="done"), task(2, "no estimate", None)]
        self.assertEqual(g.fits_window(tasks, 60), [])


class PlanWindowTests(unittest.TestCase):
    def test_short_window_prefers_small_task(self):
        tasks = [task(1, "big", 40), task(2, "small", 10)]
        plan = g.plan_window(tasks, 20)
        self.assertEqual(plan[0]["task_id"], 2)
        self.assertEqual(plan[0]["kind"], "finish")

    def test_long_window_prefers_bigger_task_that_fits(self):
        tasks = [task(1, "small", 15), task(2, "big", 45)]
        plan = g.plan_window(tasks, 60)
        self.assertEqual(plan[0]["task_id"], 2)

    def test_big_task_gets_a_session_not_the_whole_estimate(self):
        tasks = [task(1, "bayesian", 300)]
        plan = g.plan_window(tasks, 60)
        self.assertEqual(plan, [{"task_id": 1, "title": "bayesian", "minutes": 60, "kind": "session"}])

    def test_sessions_are_capped(self):
        tasks = [task(1, "bayesian", 300)]
        plan = g.plan_window(tasks, 180)
        self.assertEqual(plan[0]["minutes"], g.MAX_SESSION)

    def test_plan_never_exceeds_window(self):
        tasks = [task(1, "a", 30), task(2, "b", 30), task(3, "c", 30)]
        plan = g.plan_window(tasks, 50)
        self.assertLessEqual(sum(p["minutes"] for p in plan), 50)

    def test_window_below_minimum_gives_nothing(self):
        self.assertEqual(g.plan_window([task(1, "a", 5)], 10), [])

    def test_urgent_task_goes_first(self):
        tasks = [task(1, "later", 10), task(2, "due friday", 40, due="Friday")]
        plan = g.plan_window(tasks, 60)
        self.assertEqual(plan[0]["task_id"], 2)

    def test_logged_time_reduces_what_is_planned(self):
        tasks = [task(1, "half done", 60, logged=50)]
        plan = g.plan_window(tasks, 60)
        self.assertEqual(plan[0]["minutes"], 10)
        self.assertEqual(plan[0]["kind"], "finish")


if __name__ == "__main__":
    unittest.main()
