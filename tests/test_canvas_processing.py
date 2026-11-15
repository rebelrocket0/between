"""Canvas wording and strict model-response validation, entirely offline."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import canvas_processing as cp


class CanvasRulesTests(unittest.TestCase):
    def test_example_transformations(self):
        examples = [
            ("M5, Assignment 3: Positive Psychology Lecture", "Watch the Positive Psychology lecture", "lecture", 40),
            ("STP 421 Exam 2", "Study for STP 421 Exam 2", "exam", 180),
            ("Module 6 Discussion Board", "Complete Module 6 discussion", "discussion", 30),
            ("Linear Algebra Problem Set 7", "Solve Linear Algebra problem set 7", "problem set", 90),
        ]
        for source, title, kind, minutes in examples:
            with self.subTest(source=source):
                self.assertEqual(cp.fallback(source), {"title": title, "assignment_type": kind, "minutes": minutes})

    def test_all_supported_types_have_reasonable_fallbacks(self):
        for kind, title in {
            "quiz": "Module 3 Quiz", "reading": "Reading chapter 2", "lecture": "Physics Lecture",
            "homework": "HW3", "problem set": "Problem set 2", "discussion": "Discussion board",
            "reflection": "Week 2 Reflection", "paper": "History Essay", "project": "Robotics Project",
            "exam": "Statistics midterm", "unknown": "Office form",
        }.items():
            with self.subTest(kind=kind):
                result = cp.fallback(title)
                self.assertEqual(result["assignment_type"], kind)
                self.assertEqual(result["minutes"], cp.ESTIMATES[kind][1])

    def test_course_codes_and_academic_brackets_survive(self):
        title = "STP 421 Exam 2 [Bayes] [2026FallB-X-STP421]"
        result = cp.fallback(title)
        self.assertEqual(result["title"], "Study for STP 421 Exam 2 [Bayes]")

    def test_existing_action_is_not_duplicated(self):
        self.assertEqual(cp.fallback("Read chapter 4")["title"], "Read chapter 4")
        self.assertEqual(cp.fallback("Study for STP 421 Exam 2")["title"], "Study for STP 421 Exam 2")

    def test_generic_assignment_does_not_invent_a_type(self):
        self.assertEqual(cp.fallback("Assignment 7")["assignment_type"], "unknown")

    def test_explicit_duration_overrides_the_type_prior_but_not_the_global_bound(self):
        self.assertEqual(cp.fallback("90-minute Physics Lecture")["minutes"], 90)
        self.assertEqual(cp.fallback("Physics Lecture 1.5 hours")["minutes"], 90)
        self.assertEqual(cp.fallback("Quiz 60 points")["minutes"], 25)
        self.assertEqual(cp.fallback("Quiz 900 minutes")["minutes"], 25)
        self.assertEqual(cp.fallback("Quiz due in 2 hours")["minutes"], 25)
        result = cp.fallback("90-minute Physics Lecture")
        self.assertEqual(cp.validate(json.dumps(result), "90-minute Physics Lecture"), result)

    def test_compact_academic_labels_are_recognized(self):
        for title, kind in (("Quiz2", "quiz"), ("STP 421 Exam2", "exam"), ("Pset7", "problem set")):
            with self.subTest(title=title):
                self.assertEqual(cp.fallback(title)["assignment_type"], kind)


class CanvasValidationTests(unittest.TestCase):
    SOURCE = "STP 421 Exam 2"
    VALID = {"title": "Study for STP 421 Exam 2", "assignment_type": "exam", "minutes": 180}

    def test_valid_json_is_accepted(self):
        self.assertEqual(cp.validate(json.dumps(self.VALID), self.SOURCE), self.VALID)

    def test_rejects_invalid_json_and_shapes(self):
        for raw in ("not JSON", "[]", "null", "{}", "```json\n{}\n```", "x" * 4097, '[' * 1500 + ']' * 1500,
                    '{"title":"a","title":"b","assignment_type":"exam","minutes":180}'):
            with self.subTest(raw=raw[:30]):
                with self.assertRaises(ValueError):
                    cp.validate(raw, self.SOURCE)

    def test_rejects_wrong_fields_types_and_estimates(self):
        for change in (
            {"extra": "ignored?"}, {"minutes": True}, {"minutes": 180.0}, {"minutes": "180"},
            {"minutes": 0}, {"minutes": 481}, {"assignment_type": "test"}, {"assignment_type": []},
            {"assignment_type": "quiz", "minutes": 25}, {"title": None},
            {"title": "Exam 2"}, {"title": "Study for STP 421 Exam 2\n"},
        ):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    cp.validate(json.dumps(dict(self.VALID, **change)), self.SOURCE)

    def test_rejects_invented_requirements_and_lost_context(self):
        for title in ("Study for Exam 2", "Study for STP 421 Exam 3", "Study for STP 2 Exam 421",
                      "Study for STP 421 Exam 2 chapter 9", "Study for STP 421 Exam 2 <script>"):
            with self.subTest(title=title):
                with self.assertRaises(ValueError):
                    cp.validate(json.dumps(dict(self.VALID, title=title)), self.SOURCE)

    def test_enforces_each_types_minimum_and_maximum(self):
        for source in ("Quiz 1", "Lecture 2", "Homework 3", "Paper 4", "Project 5", "Exam 6", "Form 7"):
            result = cp.fallback(source)
            low, _, high = cp.ESTIMATES[result["assignment_type"]]
            for minutes in (low - 1, high + 1):
                with self.subTest(source=source, minutes=minutes):
                    with self.assertRaises(ValueError):
                        cp.validate(json.dumps(dict(result, minutes=minutes)), source)


if __name__ == "__main__":
    unittest.main()
