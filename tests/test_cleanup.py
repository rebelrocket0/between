import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
server.AUTO_SYNC_GOOGLE_TASKS = False

TASK = {"title": "Read chapter 3", "minutes": 20, "due": None, "due_date": None, "box": "plan", "area": "school"}


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.DATA = Path(self.tmp.name)
        server.DB_PATH = server.DATA / "test.sqlite"
        server.PHONE_TOKEN_PATH = server.DATA / "phone-token"
        server.init_db()

    def tearDown(self):
        self.tmp.cleanup()

    def open_task_count(self):
        with server.connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'open'").fetchone()[0]

    def test_same_title_is_not_added_twice(self):
        server.create_split_capture("Read chapter 3", "test", [dict(TASK)])
        server.create_split_capture("read chapter 3 again", "test", [dict(TASK)])
        self.assertEqual(self.open_task_count(), 1)

    def test_repeat_question_is_not_asked_twice(self):
        question = {"task_index": 0, "field": "minutes", "question": "How long?"}
        task = dict(TASK, minutes=None, due="soon")
        server.create_split_capture("Read chapter 3", "test", [task], [question])
        server.create_split_capture("Read chapter 3", "test", [task], [dict(question, question="How long again?")])
        self.assertEqual(len(server.open_questions()["questions"]), 1)

    def test_start_is_not_hobbies(self):
        slug, _ = server.pick_area("start the problem set")
        self.assertNotEqual(slug, "hobbies")

    def test_chapter_is_school(self):
        slug, _ = server.pick_area("chapter 3 reading")
        self.assertEqual(slug, "school")


if __name__ == "__main__":
    unittest.main(verbosity=2)
