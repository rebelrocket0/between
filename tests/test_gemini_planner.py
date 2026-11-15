"""Gemini day planning wired into the two-week planner. Gemini is always mocked here."""
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import task_rules as tr  # noqa: E402

spec = importlib.util.spec_from_file_location("server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
server.AUTO_SYNC_GOOGLE_TASKS = False  # never touch the real Google account from tests

TZ = ZoneInfo("America/Phoenix")
TODAY = date(2026, 11, 15)


def at(day, hour, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ)


def two_weeks(start_day, first_hour=9, last_hour=21):
    return {
        start_day + timedelta(days=i): [(at(start_day + timedelta(days=i), first_hour), at(start_day + timedelta(days=i), last_hour))]
        for i in range(tr.PLAN_HORIZON_DAYS)
    }


# ---------- Pure rules (fixed dates) ----------

class PlanWithTodayTests(unittest.TestCase):
    def test_gemini_session_today_and_the_rest_spreads_from_tomorrow(self):
        task = {"id": 1, "title": "Paper", "box": "plan", "due": "2026-11-20", "minutes": 180}
        ai = [{"task_id": 1, "title": "Paper", "start": at(TODAY, 14), "end": at(TODAY, 15), "reason": "Big paper, start early"}]
        blocks, unplaced = tr.plan_with_today(ai, [task], two_weeks(TODAY), TODAY)
        self.assertEqual(unplaced, [])
        self.assertEqual(len(blocks), 3)
        self.assertEqual(blocks[0]["reason"], "Big paper, start early")
        self.assertEqual([b["start"].date() for b in blocks[1:]], [TODAY + timedelta(days=1), TODAY + timedelta(days=2)])

    def test_task_gemini_left_out_waits_for_tomorrow(self):
        task = {"id": 2, "title": "Reading", "box": "plan", "due": "2026-11-25", "minutes": 60}
        blocks, _ = tr.plan_with_today([], [task], two_weeks(TODAY), TODAY)
        self.assertEqual(blocks[0]["start"].date(), TODAY + timedelta(days=1))

    def test_task_due_today_that_gemini_missed_still_gets_today(self):
        due_today = {"id": 3, "title": "Quiz", "box": "do_now", "due": TODAY.isoformat(), "minutes": 30}
        other = {"id": 4, "title": "Essay", "box": "plan", "due": "2026-11-22", "minutes": 60}
        ai = [{"task_id": 4, "title": "Essay", "start": at(TODAY, 9), "end": at(TODAY, 10), "reason": "x"}]
        blocks, unplaced = tr.plan_with_today(ai, [due_today, other], two_weeks(TODAY), TODAY)
        quiz = [b for b in blocks if b["task_id"] == 3]
        self.assertEqual(unplaced, [])
        self.assertEqual(quiz[0]["start"].date(), TODAY)
        self.assertGreaterEqual(quiz[0]["start"], at(TODAY, 10, 5))  # after Gemini's block plus buffer

    def test_today_cap_counts_gemini_minutes(self):
        ai = [
            {"task_id": i, "title": f"T{i}", "start": at(TODAY, 9 + i), "end": at(TODAY, 9 + i, 55), "reason": "x"}
            for i in range(4)
        ]
        tasks = [{"id": i, "title": f"T{i}", "box": "do_now", "due": TODAY.isoformat(), "minutes": 55} for i in range(4)]
        tasks.append({"id": 9, "title": "Late add", "box": "do_now", "due": TODAY.isoformat(), "minutes": 30})
        blocks, unplaced = tr.plan_with_today(ai, tasks, two_weeks(TODAY), TODAY)
        today_minutes = sum((b["end"] - b["start"]).seconds // 60 for b in blocks if b["start"].date() == TODAY)
        self.assertLessEqual(today_minutes, tr.MAX_DAY_TASK_MINUTES)
        self.assertEqual(unplaced, [9])


class SkipRuleTests(unittest.TestCase):
    def test_earliest_keeps_a_task_off_today(self):
        task = {"id": 1, "title": "A", "box": "plan", "due": None, "minutes": 30, "earliest": TODAY + timedelta(days=1)}
        blocks, _ = tr.spread_sessions([task], two_weeks(TODAY), TODAY)
        self.assertEqual(blocks[0]["start"].date(), TODAY + timedelta(days=1))

    def test_often_skipped_task_goes_after_others_with_same_deadline(self):
        skipped = {"id": 1, "title": "Skipped", "box": "plan", "due": "2026-11-18", "minutes": 30, "skips": 3}
        fresh = {"id": 2, "title": "Fresh", "box": "plan", "due": "2026-11-18", "minutes": 30, "skips": 0}
        blocks, _ = tr.spread_sessions([skipped, fresh], two_weeks(TODAY), TODAY)
        self.assertEqual(blocks[0]["task_id"], 2)

    def test_skips_never_push_back_urgent_work(self):
        urgent = {"id": 1, "title": "Urgent", "box": "do_now", "due": "2026-11-16", "minutes": 30, "skips": 5}
        later = {"id": 2, "title": "Later", "box": "plan", "due": "2026-11-16", "minutes": 30, "skips": 0}
        blocks, _ = tr.spread_sessions([later, urgent], two_weeks(TODAY), TODAY)
        self.assertEqual(blocks[0]["task_id"], 1)


class ReasonTests(unittest.TestCase):
    def test_every_rule_block_gets_a_specific_reason(self):
        tasks = [
            {"id": 1, "title": "Paper", "box": "plan", "due": "2026-11-20", "minutes": 120},
            {"id": 2, "title": "Quiz", "box": "do_now", "due": "2026-11-15", "minutes": 30},
            {"id": 3, "title": "Hobby", "box": "someday", "due": None, "minutes": 30},
        ]
        blocks, _ = tr.spread_sessions(tasks, two_weeks(TODAY), TODAY)
        tr.explain_blocks(blocks, tasks, TODAY)
        reasons = {(b["task_id"], b["reason"]) for b in blocks}
        self.assertIn((1, "Session 1 of 2 before it's due Fri Nov 20"), reasons)
        self.assertIn((1, "Session 2 of 2 before it's due Fri Nov 20"), reasons)
        self.assertIn((2, "Due today; one session finishes it"), reasons)
        self.assertTrue(any(task_id == 3 and "No deadline" in reason for task_id, reason in reasons))

    def test_gemini_reason_is_kept(self):
        blocks = [{"task_id": 1, "start": at(TODAY, 9), "end": at(TODAY, 10), "reason": "Gemini says so"}]
        tr.explain_blocks(blocks, [{"id": 1, "box": "plan", "due": None, "minutes": 60}], TODAY)
        self.assertEqual(blocks[0]["reason"], "Gemini says so")

    def test_skip_shows_in_reason(self):
        task = {"id": 1, "box": "plan", "due": None, "minutes": 30, "skipped_today": True, "skips": 1}
        self.assertIn("not today", tr.rule_reason(task, 1, 1, TODAY))
        task = {"id": 1, "box": "plan", "due": None, "minutes": 30, "skips": 3}
        self.assertIn("skipped it 3 times", tr.rule_reason(task, 1, 1, TODAY))


class ValidateCapTests(unittest.TestCase):
    def test_validate_plan_respects_daily_cap(self):
        gaps = [(at(TODAY, 8), at(TODAY, 22))]
        tasks = [{"id": i, "title": f"T{i}", "box": "plan", "minutes": 60} for i in range(6)]
        raw = [{"task_id": i, "start": f"{8 + 2 * i:02d}:00", "reason": "r"} for i in range(6)]
        blocks = tr.validate_plan(raw, gaps, tasks, max_total_minutes=240)
        self.assertEqual(len(blocks), 4)


class MustStartTodayTests(unittest.TestCase):
    def test_rules(self):
        self.assertTrue(tr.must_start_today({"due": TODAY.isoformat(), "minutes": 30}, TODAY))
        self.assertFalse(tr.must_start_today({"due": "2026-11-16", "minutes": 60}, TODAY))
        self.assertTrue(tr.must_start_today({"due": "2026-11-16", "minutes": 120}, TODAY))
        self.assertFalse(tr.must_start_today({"due": None, "minutes": 600}, TODAY))


# ---------- Server wiring (Gemini mocked, fixed free time on the real today) ----------

class GeminiModelFallbackTests(unittest.TestCase):
    def test_timeout_on_first_model_tries_the_next(self):
        real_json_request = server.json_request
        tried = []

        def fake_request(url, method="GET", headers=None, payload=None, form=None):
            tried.append(url.split("/models/")[1].split(":")[0])
            if len(tried) == 1:
                raise TimeoutError("The read operation timed out")
            return {"candidates": [{"content": {"parts": [{"text": '{"plan": []}'}]}}]}, {}

        server.json_request = fake_request
        try:
            self.assertEqual(server.gemini_json("x", {"GEMINI_API_KEY": "test"}), {"plan": []})
        finally:
            server.json_request = real_json_request
        self.assertEqual(tried, server.GEMINI_MODELS[:2])


class ServerPlannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.DATA = Path(self.tmp.name)
        server.DB_PATH = server.DATA / "test.sqlite"
        server.PHONE_TOKEN_PATH = server.DATA / "phone-token"
        server.init_db()
        server.plan_cache_clear()
        server._DAY_PLAN_CACHE.update({"key": None, "blocks": None, "at": 0.0, "failed_at": None})
        self.config = {"TIMEZONE": "America/Phoenix", "GEMINI_API_KEY": "test-key-not-real"}
        server.load_config = lambda: dict(self.config)
        self.today = datetime.now(TZ).date()
        server.planning_day_gaps = lambda days=tr.PLAN_HORIZON_DAYS: two_weeks(self.today)
        self.prompts = []
        self.gemini_answer = {"plan": []}

        def fake_gemini(prompt, config):
            self.prompts.append(prompt)
            if isinstance(self.gemini_answer, Exception):
                raise self.gemini_answer
            return self.gemini_answer

        server.gemini_json = fake_gemini

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, title, minutes, due_days=None, box="plan"):
        due = (self.today + timedelta(days=due_days)).isoformat() if due_days is not None else None
        server.create_split_capture(title, "test", [
            {"title": title, "minutes": minutes, "due": None, "due_date": due, "box": box, "area": "school"}
        ])
        with server.connect() as conn:
            return conn.execute("SELECT id FROM tasks WHERE title = ? ORDER BY id DESC", (title,)).fetchone()["id"]

    def today_blocks(self):
        blocks, unplaced = server.multi_day_plan()
        return [b for b in blocks if b["start"].date() == self.today], blocks, unplaced

    def test_gemini_plan_is_used_with_its_reasons(self):
        essay = self.add("Essay", 120, due_days=5)
        quiz = self.add("Quiz prep", 30, due_days=1)
        self.gemini_answer = {"plan": [
            {"task_id": quiz, "start": "10:00", "reason": "Quiz is tomorrow, short task for the morning"},
            {"task_id": essay, "start": "15:00", "reason": "Long afternoon gap fits a solid essay hour"},
        ]}
        today, everything, unplaced = self.today_blocks()
        self.assertEqual(server.today_payload()["planner"], "gemini")
        self.assertEqual([(b["task_id"], b["start"].strftime("%H:%M")) for b in today], [(quiz, "10:00"), (essay, "15:00")])
        self.assertEqual(today[0]["reason"], "Quiz is tomorrow, short task for the morning")
        later = [b for b in everything if b["start"].date() > self.today]
        self.assertEqual([b["task_id"] for b in later], [essay])  # the essay's second hour, from tomorrow
        self.assertTrue(later[0]["reason"].startswith("Session 2 of 2"))
        self.assertEqual(unplaced, [])

    def test_prompt_has_due_dates_and_skips_but_no_calendar_titles(self):
        self.add("Essay", 120, due_days=5)
        server.multi_day_plan()
        prompt = self.prompts[0]
        self.assertIn('"days_until_due": 5', prompt)
        self.assertIn('"times_skipped": 0', prompt)
        self.assertIn('"session_minutes": 60', prompt)
        self.assertIn("09:00-21:00", prompt)

    def test_gemini_error_falls_back_to_rules_with_reasons(self):
        self.add("Essay", 60, due_days=0)
        self.gemini_answer = ValueError("503 from connector")
        today, _, _ = self.today_blocks()
        payload = server.today_payload()
        self.assertEqual(payload["planner"], "rules")
        self.assertIn("Gemini unavailable", payload["planner_note"])
        self.assertEqual(len(today), 1)
        self.assertEqual(today[0]["reason"], "Due today; one session finishes it")

    def test_network_error_falls_back_too(self):
        self.add("Essay", 60, due_days=0)
        self.gemini_answer = TimeoutError("timed out")
        today, _, _ = self.today_blocks()
        self.assertEqual(len(today), 1)

    def test_failure_pauses_gemini_so_refreshes_stay_fast(self):
        self.add("Essay", 60, due_days=0)
        self.gemini_answer = ValueError("timed out")
        server.multi_day_plan()
        server.plan_cache_clear()
        self.gemini_answer = {"plan": []}
        server.multi_day_plan()
        self.assertEqual(len(self.prompts), 1)
        self.assertIn("failed recently", server.today_payload()["planner_note"])

    def test_unusable_gemini_plan_falls_back(self):
        task = self.add("Essay", 60, due_days=0)
        self.gemini_answer = {"plan": [
            {"task_id": 9999, "start": "10:00", "reason": "not a real task"},
            {"task_id": task, "start": "23:30", "reason": "outside free time"},
        ]}
        today, _, _ = self.today_blocks()
        self.assertEqual(server.today_payload()["planner"], "rules")
        self.assertEqual(len(today), 1)
        self.assertNotEqual(today[0]["start"].strftime("%H:%M"), "23:30")

    def test_no_api_key_never_calls_gemini(self):
        del self.config["GEMINI_API_KEY"]
        self.add("Essay", 60, due_days=2)
        server.multi_day_plan()
        self.assertEqual(self.prompts, [])

    def test_not_today_removes_task_from_today_and_from_gemini(self):
        skipped = self.add("Laundry", 30, box="someday")
        kept = self.add("Reading", 30, due_days=3)
        server.skip_task(skipped)
        self.gemini_answer = {"plan": [
            {"task_id": skipped, "start": "10:00", "reason": "Gemini tried anyway"},
            {"task_id": kept, "start": "11:00", "reason": "Reading for Wednesday"},
        ]}
        today, everything, _ = self.today_blocks()
        self.assertNotIn('"Laundry"', self.prompts[-1])
        self.assertIn('"Reading"', self.prompts[-1])
        self.assertEqual([b["task_id"] for b in today], [kept])
        moved = [b for b in everything if b["task_id"] == skipped]
        self.assertEqual(moved[0]["start"].date(), self.today + timedelta(days=1))
        self.assertIn("not today", moved[0]["reason"])

    def test_not_today_also_works_without_gemini(self):
        del self.config["GEMINI_API_KEY"]
        skipped = self.add("Laundry", 30, box="someday")
        server.skip_task(skipped)
        today, _, _ = self.today_blocks()
        self.assertNotIn(skipped, [b["task_id"] for b in today])

    def test_skip_message(self):
        task = self.add("Laundry", 30, box="someday")
        self.assertIn("back tomorrow", server.skip_task(task)["reason"])
        self.assertIn("after your other work", server.skip_task(task)["reason"])

    def test_gemini_answer_is_cached_between_refreshes(self):
        task = self.add("Essay", 60, due_days=2)
        self.gemini_answer = {"plan": [{"task_id": task, "start": "10:00", "reason": "r"}]}
        server.multi_day_plan()
        server.plan_cache_clear()
        server.multi_day_plan()
        self.assertEqual(len(self.prompts), 1)

    def test_new_task_asks_gemini_again(self):
        self.add("Essay", 60, due_days=2)
        server.multi_day_plan()
        self.add("Quiz", 30, due_days=1)  # capture clears the plan cache
        server.multi_day_plan()
        self.assertEqual(len(self.prompts), 2)

    def test_every_block_has_a_reason_in_both_planners(self):
        for title, minutes, due in (("Essay", 180, 6), ("Quiz", 30, 1), ("Hobby", 30, None)):
            self.add(title, minutes, due_days=due)
        _, with_gemini_off, _ = self.today_blocks()
        self.assertTrue(all(b["reason"] for b in with_gemini_off))
        server.plan_cache_clear()
        self.gemini_answer = {"plan": [{"task_id": 1, "start": "13:00", "reason": ""}]}  # empty reason gets filled
        _, with_gemini, _ = self.today_blocks()
        self.assertTrue(all(b["reason"] for b in with_gemini))


if __name__ == "__main__":
    unittest.main(verbosity=0)
