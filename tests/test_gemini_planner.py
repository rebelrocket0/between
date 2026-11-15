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
    """Scheduling authority moved to rules; Gemini selects supported explanations only."""
    def setUp(self):
        from unittest.mock import Mock, patch
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        server.DATA = Path(self.tmp.name)
        server.DB_PATH = server.DATA / "test.sqlite"
        server.PHONE_TOKEN_PATH = server.DATA / "token"
        server.load_config = lambda: {"TIMEZONE": "America/Phoenix"}
        server.init_db()
        server.plan_cache_clear()
        self.today = datetime.now(TZ).date()
        server.planning_day_gaps = lambda days=tr.PLAN_HORIZON_DAYS: two_weeks(self.today)
        self.ai = Mock(return_value='{"reasons": [{"block":"0","fact_id":"0:due"}]}')
        patcher = patch.object(server, "pip_json", self.ai)
        patcher.start()
        self.addCleanup(patcher.stop)

    def add(self, title="Read statistics notes", minutes=30, skips=0):
        stamp = server.now_iso()
        due = (self.today + timedelta(days=2)).isoformat()
        with server.connect() as conn:
            return conn.execute("INSERT INTO tasks(title, duration_minutes, due_date, box, energy, created_at, updated_at, skips) VALUES (?, ?, ?, 'plan', 'medium', ?, ?, ?)", (title,minutes,due,stamp,stamp,skips)).lastrowid

    def test_deterministic_rules_have_authority(self):
        task_id = self.add()
        self.ai.return_value = '{"plan":[{"task_id":999,"start":"23:00"}]}'
        blocks, unplaced = server.multi_day_plan()
        self.assertEqual(unplaced, [])
        self.assertEqual(blocks[0]["task_id"], task_id)
        self.assertEqual(blocks[0]["start"].strftime('%H:%M'), '09:00')
        self.assertEqual(server.today_payload()["planner"], "rules")

    def test_only_supported_explanation_is_used(self):
        self.add()
        blocks, _ = server.multi_day_plan()
        self.assertIn('recorded deadline', blocks[0]['reason'])

    def test_unsupported_facts_do_not_override_rule_reasons(self):
        self.add()
        self.ai.return_value = '{"reasons":[{"block":"0","fact_id":"not-a-fact"}]}'
        blocks, _ = server.multi_day_plan()
        self.assertTrue(blocks[0]['reason'])
        self.assertNotIn('not-a-fact', blocks[0]['reason'])

    def test_network_failure_does_not_change_sessions(self):
        self.add()
        self.ai.side_effect = TimeoutError('timeout')
        first, _ = server.multi_day_plan()
        self.assertEqual(first[0]['start'].strftime('%H:%M'), '09:00')
        self.assertTrue(first[0]['reason'])

    def test_plan_and_explanations_are_cached(self):
        self.add()
        server.multi_day_plan()
        server.multi_day_plan()
        self.assertEqual(self.ai.call_count, 1)

    def test_new_task_invalidates_context(self):
        first = self.add()
        server.multi_day_plan()
        self.add('Complete algebra quiz')
        server.plan_cache_clear()
        server.multi_day_plan()
        self.assertEqual(self.ai.call_count, 2)

    def test_not_today_honors_the_rule_and_removes_the_window_suggestion(self):
        task = self.add()
        server.skip_task(task)
        blocks, _ = server.multi_day_plan()
        self.assertEqual(blocks[0]['start'].date(), self.today + timedelta(days=1))
        self.assertEqual(server.plan_for_window(30)['plan'], [])

    def test_logged_time_changes_the_remaining_schedule(self):
        task = self.add(minutes=60)
        server.multi_day_plan()
        server.log_task_time(task, {"minutes": 20})
        blocks, _ = server.multi_day_plan()
        self.assertEqual(int((blocks[0]['end']-blocks[0]['start']).total_seconds()/60), 40)

    def test_done_task_disappears(self):
        task = self.add()
        server.update_task(task, {"status": "done"})
        self.assertEqual(server.multi_day_plan()[0], [])

    def test_prompt_contains_fixed_decisions_without_busy_titles(self):
        self.add()
        server.multi_day_plan()
        prompt = self.ai.call_args[0][0]
        self.assertIn('fixed scheduling decision', prompt)
        self.assertIn('Read statistics notes', prompt)
        self.assertIn('untrusted data', prompt)


if __name__ == "__main__":
    unittest.main(verbosity=0)
