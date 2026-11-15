import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
# Never touch the real Google account or Gemini from tests.
server.AUTO_SYNC_GOOGLE_TASKS = False
server.load_config = lambda: {"TIMEZONE": "America/Phoenix"}


class ParseTests(unittest.TestCase):
    def test_valid_tasks_are_parsed(self):
        raw = json.dumps({"tasks": [
            {"title": "Email Prof K", "minutes": 5, "due": None, "due_date": None, "box": None, "area": "school"},
            {"title": "Finish problem set", "minutes": 120, "due": "Friday", "due_date": None, "box": None, "area": "school"},
        ]})
        tasks = server.parse_split_tasks(raw)
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[1], {"title": "Finish problem set", "minutes": 120, "due": "Friday", "due_date": None, "box": None, "area": "school"})

    def test_durations_are_stripped_from_titles(self):
        raw = json.dumps({"tasks": [{"title": "read chapter 3 for 20 min", "minutes": 20, "area": "school"}]})
        self.assertEqual(server.parse_split_tasks(raw)[0]["title"], "Read chapter 3")

    def test_unclear_minutes_become_none(self):
        raw = json.dumps({"tasks": [{"title": "Clean kitchen", "minutes": None, "area": "home"}]})
        self.assertIsNone(server.parse_split_tasks(raw)[0]["minutes"])

    def test_absurd_minutes_are_dropped(self):
        raw = json.dumps({"tasks": [{"title": "Thing", "minutes": 99999, "area": "home"}]})
        self.assertIsNone(server.parse_split_tasks(raw)[0]["minutes"])

    def test_unknown_area_falls_back_to_planning(self):
        raw = json.dumps({"tasks": [{"title": "Thing", "minutes": 10, "area": "moon base"}]})
        self.assertEqual(server.parse_split_tasks(raw)[0]["area"], "planning")

    def test_empty_titles_are_skipped(self):
        raw = json.dumps({"tasks": [{"title": "   ", "minutes": 10}, {"title": "Real one", "minutes": 10}]})
        titles = [t["title"] for t in server.parse_split_tasks(raw)]
        self.assertEqual(titles, ["Real one"])

    def test_empty_list_is_fine(self):
        self.assertEqual(server.parse_split_tasks(json.dumps({"tasks": []})), [])

    def test_bad_json_raises(self):
        with self.assertRaises(ValueError):
            server.parse_split_tasks("not json at all")

    def test_missing_task_list_raises(self):
        with self.assertRaises(ValueError):
            server.parse_split_tasks(json.dumps({"something": "else"}))


class SplitCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.DATA = Path(self.tmp.name)
        server.DB_PATH = Path(self.tmp.name) / "test.sqlite"
        server.PHONE_TOKEN_PATH = Path(self.tmp.name) / "phone_capture_token"
        server.init_db()

    def tearDown(self):
        self.tmp.cleanup()

    def test_split_creates_one_inbox_item_and_several_tasks(self):
        tasks = [
            {"title": "Email Prof K", "minutes": 5, "due": None, "due_date": None, "box": None, "area": "school"},
            {"title": "Buy a charger", "minutes": 15, "due": "Thursday", "due_date": None, "box": None, "area": "home"},
        ]
        result = server.create_split_capture("Email Prof K and buy a charger before Thursday", "manual", tasks)
        self.assertTrue(result["ok"])
        with server.connect() as conn:
            inbox = conn.execute("SELECT status, kind FROM inbox_items").fetchall()
            rows = conn.execute("SELECT title, due_text, duration_minutes FROM tasks ORDER BY id").fetchall()
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]["status"], "routed")
        self.assertEqual([r["title"] for r in rows], ["Email Prof K", "Buy a charger"])
        self.assertEqual(rows[1]["due_text"], "Thursday")
        self.assertEqual(rows[1]["duration_minutes"], 15)


class QuestionParseTests(unittest.TestCase):
    def test_question_points_at_the_right_task_after_a_skip(self):
        raw = json.dumps({
            "tasks": [
                {"title": "   ", "minutes": 10, "area": "school"},
                {"title": "Read chapter 3", "minutes": None, "area": "school"},
            ],
            "questions": [{"task": 1, "field": "minutes", "question": "How long is the reading?"}],
        })
        tasks, questions = server.parse_split(raw)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(questions, [{"task_index": 0, "field": "minutes", "question": "How long is the reading?"}])

    def test_bad_questions_are_dropped(self):
        raw = json.dumps({
            "tasks": [{"title": "Thing", "minutes": 10, "area": "home"}],
            "questions": [
                {"task": 5, "field": "minutes", "question": "Out of range"},
                {"task": 0, "field": "color", "question": "Wrong field"},
                {"task": 0, "field": "due", "question": ""},
            ],
        })
        self.assertEqual(server.parse_split(raw)[1], [])

    def test_missing_questions_key_is_fine(self):
        raw = json.dumps({"tasks": [{"title": "Thing", "minutes": 10, "area": "home"}]})
        self.assertEqual(server.parse_split(raw)[1], [])


class QuestionAnswerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.DATA = Path(self.tmp.name)
        server.DB_PATH = Path(self.tmp.name) / "test.sqlite"
        server.PHONE_TOKEN_PATH = Path(self.tmp.name) / "phone_capture_token"
        server.init_db()
        tasks = [
            {"title": "Bayesian assignment", "minutes": None, "due": None, "due_date": None, "box": None, "area": "school"},
            {"title": "Pay rent", "minutes": None, "due": None, "due_date": None, "box": None, "area": "home"},
        ]
        questions = [
            {"task_index": 0, "field": "minutes", "question": "How long will it take?"},
            {"task_index": 1, "field": "due", "question": "When is rent due?"},
        ]
        server.create_split_capture("Bayesian assignment and pay rent", "manual", tasks, questions)

    def tearDown(self):
        self.tmp.cleanup()

    def test_open_questions_lists_both(self):
        self.assertEqual(len(server.open_questions()["questions"]), 2)

    def test_minutes_answer_sets_the_estimate(self):
        qid = server.open_questions()["questions"][0]["id"]
        server.answer_question(qid, "about 2 hours")
        with server.connect() as conn:
            minutes = conn.execute("SELECT duration_minutes FROM tasks WHERE title = 'Bayesian assignment'").fetchone()[0]
        self.assertEqual(minutes, 120)
        self.assertEqual(len(server.open_questions()["questions"]), 1)

    def test_due_answer_sets_the_deadline(self):
        qid = server.open_questions()["questions"][1]["id"]
        server.answer_question(qid, "Friday")
        with server.connect() as conn:
            due = conn.execute("SELECT due_text FROM tasks WHERE title = 'Pay rent'").fetchone()[0]
        self.assertEqual(due, "Friday")

    def test_unclear_time_is_rejected_and_question_stays_open(self):
        qid = server.open_questions()["questions"][0]["id"]
        with self.assertRaises(ValueError):
            server.answer_question(qid, "soon")
        self.assertEqual(len(server.open_questions()["questions"]), 2)

    def test_answering_twice_is_rejected(self):
        qid = server.open_questions()["questions"][1]["id"]
        server.answer_question(qid, "Friday")
        with self.assertRaises(ValueError):
            server.answer_question(qid, "Monday")


if __name__ == "__main__":
    unittest.main()
