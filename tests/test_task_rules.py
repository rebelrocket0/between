import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import task_rules  # noqa: E402

TODAY = date(2026, 11, 15)


class EffectiveBoxTests(unittest.TestCase):
    def test_due_tomorrow_is_do_now(self):
        self.assertEqual(task_rules.effective_box("plan", "2026-11-16", TODAY), "do_now")

    def test_due_in_two_days_is_do_now(self):
        self.assertEqual(task_rules.effective_box("plan", "2026-11-17", TODAY), "do_now")

    def test_due_later_keeps_gemini_box(self):
        self.assertEqual(task_rules.effective_box("plan", "2026-12-01", TODAY), "plan")

    def test_no_due_keeps_someday(self):
        self.assertEqual(task_rules.effective_box("someday", None, TODAY), "someday")

    def test_no_box_and_dated_is_plan(self):
        self.assertEqual(task_rules.effective_box(None, "2026-12-01", TODAY), "plan")

    def test_no_box_and_undated_is_someday(self):
        self.assertEqual(task_rules.effective_box(None, None, TODAY), "someday")

    def test_bad_date_is_ignored(self):
        self.assertEqual(task_rules.effective_box("quick", "next week", TODAY), "quick")


class ValidDateTests(unittest.TestCase):
    def test_accepts_iso_date(self):
        self.assertEqual(task_rules.valid_date("2026-11-20"), "2026-11-20")

    def test_rejects_words_and_bad_dates(self):
        self.assertIsNone(task_rules.valid_date("Friday"))
        self.assertIsNone(task_rules.valid_date("2026-13-40"))
        self.assertIsNone(task_rules.valid_date(None))


class SkipTests(unittest.TestCase):
    def test_second_skip_moves_plan_task(self):
        self.assertTrue(task_rules.should_move_after_skip(2, "plan"))

    def test_first_skip_does_not_move(self):
        self.assertFalse(task_rules.should_move_after_skip(1, "plan"))

    def test_do_now_never_moves(self):
        self.assertFalse(task_rules.should_move_after_skip(5, "do_now"))


class GoogleTaskBodyTests(unittest.TestCase):
    def test_body_has_title_notes_and_due_date(self):
        body = task_rules.google_task_body("Read chapter 3", "do_now", "2026-11-16", 20, "School")
        self.assertEqual(body["title"], "Read chapter 3")
        self.assertEqual(body["notes"], "School · 20 min")
        self.assertEqual(body["due"], "2026-11-16T00:00:00.000Z")
        self.assertEqual(body["status"], "needsAction")

    def test_no_due_has_no_due_field(self):
        body = task_rules.google_task_body("Get a driver's license", "someday", None, None, "")
        self.assertNotIn("due", body)
        self.assertEqual(body["notes"], task_rules.BOX_LABELS["someday"])


class CategoryTests(unittest.TestCase):
    def test_due_soon_is_urgent_and_important(self):
        self.assertEqual(task_rules.category_for("plan", "2026-11-16", TODAY), "urgent_important")

    def test_quick_is_urgent(self):
        self.assertEqual(task_rules.category_for("quick", None, TODAY), "urgent")

    def test_no_deadline_is_important(self):
        self.assertEqual(task_rules.category_for("someday", None, TODAY), "important")
        self.assertEqual(task_rules.category_for("plan", "2026-12-20", TODAY), "important")

    def test_every_box_has_a_category(self):
        for box in task_rules.BOXES:
            self.assertIn(task_rules.CATEGORY_BY_BOX[box], task_rules.CATEGORY_ORDER)


class DateFromWordsTests(unittest.TestCase):
    SUNDAY = date(2026, 11, 15)

    def test_weekday_name_is_next_occurrence(self):
        self.assertEqual(task_rules.date_from_words("by Friday", self.SUNDAY), "2026-11-20")

    def test_tomorrow_and_today(self):
        self.assertEqual(task_rules.date_from_words("tomorrow", self.SUNDAY), "2026-11-16")
        self.assertEqual(task_rules.date_from_words("today", self.SUNDAY), "2026-11-15")

    def test_same_weekday_means_next_week(self):
        self.assertEqual(task_rules.date_from_words("Sunday", self.SUNDAY), "2026-11-22")

    def test_unclear_words_give_none(self):
        self.assertIsNone(task_rules.date_from_words("soon", self.SUNDAY))
        self.assertIsNone(task_rules.date_from_words(None, self.SUNDAY))


if __name__ == "__main__":
    unittest.main(verbosity=2)
