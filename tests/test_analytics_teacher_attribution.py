import copy
from itertools import product
import unittest

from analytics.common import select_records
from analytics.teacher_attribution import summarize_teacher_attribution


def row(student, teacher, *, school="S1", classroom="C1", topic="t1", stage="post",
        textbook="Book A", version="v1"):
    return {
        "student_id": student, "teacher_id": teacher, "school_id": school, "class_id": classroom,
        "topic_id": topic, "stage": stage, "textbook_id": textbook, "test_version": version,
        "score": 30 if stage == "pre" else 60, "max_score": 100,
        "tested_at": "2026-09-01" if stage == "pre" else "2026-10-01",
    }


def example_records():
    return [
        row("A", "T1", stage="pre"), row("A", "T1"),
        row("B", "T1", stage="pre"), row("B", None, topic="t2", textbook="Book B"),
        row("C", None, stage="pre"), row("C", None),
        row("D", "Не указан", school="S2", classroom="C2"),
        row("E", None, school="S2", classroom="C2"),
    ]


class TeacherAttributionTests(unittest.TestCase):
    def test_eight_rows_partition_pupils_and_count_missing_rows(self):
        records = example_records()
        original = copy.deepcopy(records)
        expected = {
            "fully_attributed_students": 2,
            "partially_attributed_students": 1,
            "unattributed_students": 2,
            "fully_attributed_student_share": 0.4,
            "missing_teacher_rows": 4,
        }
        self.assertEqual(summarize_teacher_attribution(records), expected)
        self.assertEqual(summarize_teacher_attribution(reversed(records)), expected)
        self.assertEqual(records, original)

    def test_empty_iterator_has_zero_counts_and_null_share(self):
        self.assertEqual(summarize_teacher_attribution(iter(())), {
            "fully_attributed_students": 0,
            "partially_attributed_students": 0,
            "unattributed_students": 0,
            "fully_attributed_student_share": None,
            "missing_teacher_rows": 0,
        })

    def test_pre_only_pupils_count_and_missing_pre_id_is_not_imputed(self):
        records = [row("pre-known", "T1", stage="pre"), row("pre-missing", None, stage="pre"),
                   row("paired", None, stage="pre"), row("paired", "T1")]
        result = summarize_teacher_attribution(records)
        self.assertEqual(result["fully_attributed_students"], 1)
        self.assertEqual(result["partially_attributed_students"], 1)
        self.assertEqual(result["unattributed_students"], 1)
        self.assertAlmostEqual(result["fully_attributed_student_share"], 1 / 3)
        self.assertEqual(result["missing_teacher_rows"], 2)

    def test_known_pre_and_missing_post_is_partial_even_with_any_id_present(self):
        result = summarize_teacher_attribution([row("A", "T1", stage="pre"), row("A", None)])
        self.assertEqual(result["fully_attributed_students"], 0)
        self.assertEqual(result["partially_attributed_students"], 1)
        self.assertEqual(result["unattributed_students"], 0)
        self.assertEqual(result["fully_attributed_student_share"], 0)
        self.assertEqual(result["missing_teacher_rows"], 1)

    def test_different_known_teacher_ids_still_mean_complete_presence(self):
        result = summarize_teacher_attribution([
            row("A", "T1", stage="pre"), row("A", "T2"),
            row("A", " T3 ", topic="t2"), row("B", "T1"),
        ])
        self.assertEqual(result["fully_attributed_students"], 2)
        self.assertEqual(result["partially_attributed_students"], 0)
        self.assertEqual(result["unattributed_students"], 0)
        self.assertEqual(result["fully_attributed_student_share"], 1)
        self.assertEqual(result["missing_teacher_rows"], 0)

    def test_missing_forms_and_literal_display_label_are_distinct(self):
        records = [row("missing", value, topic=f"t{i}") for i, value in enumerate((None, "", " \t\n"))]
        records += [row("partial", "T1", stage="pre"), row("partial", " "),
                    row("literal", "Не указан"), row("zero-id", "0")]
        result = summarize_teacher_attribution(records)
        self.assertEqual(result["fully_attributed_students"], 2)
        self.assertEqual(result["partially_attributed_students"], 1)
        self.assertEqual(result["unattributed_students"], 1)
        self.assertEqual(result["fully_attributed_student_share"], 0.5)
        self.assertEqual(result["missing_teacher_rows"], 4)

    def test_caller_filters_reclassify_pupils_instead_of_reusing_full_dataset_counts(self):
        records = example_records()
        known_book = summarize_teacher_attribution(select_records(records, {"textbook_ids": ["Book A"]}))
        self.assertEqual(known_book, {
            "fully_attributed_students": 3, "partially_attributed_students": 0,
            "unattributed_students": 2, "fully_attributed_student_share": 0.6, "missing_teacher_rows": 3,
        })
        missing_book = summarize_teacher_attribution(select_records(records, {"textbook_ids": ["Book B"]}))
        self.assertEqual(missing_book, {
            "fully_attributed_students": 0, "partially_attributed_students": 0,
            "unattributed_students": 1, "fully_attributed_student_share": 0, "missing_teacher_rows": 1,
        })
        empty = summarize_teacher_attribution(select_records(records, {
            "class_ids": ["C2"], "textbook_ids": ["Book B"],
        }))
        self.assertIsNone(empty["fully_attributed_student_share"])
        self.assertEqual(empty["missing_teacher_rows"], 0)

    def test_version_and_topic_filters_apply_to_all_selected_stages(self):
        records = [row("A", "T1", stage="pre"), row("A", "T1"),
                   row("A", None, topic="t2", version="v2")]
        complete = summarize_teacher_attribution(select_records(records, {"test_version": "v1"}))
        self.assertEqual(complete["fully_attributed_students"], 1)
        self.assertEqual(complete["missing_teacher_rows"], 0)
        missing = summarize_teacher_attribution(select_records(records, {"topic_ids": ["t2"]}))
        self.assertEqual(missing["unattributed_students"], 1)
        self.assertEqual(missing["fully_attributed_student_share"], 0)
        self.assertEqual(summarize_teacher_attribution(records)["partially_attributed_students"], 1)

    def test_every_presence_pattern_conserves_unique_pupils(self):
        for patterns in product(((True,), (False,), (True, False)), repeat=3):
            with self.subTest(patterns=patterns):
                records = [row(f"p{pupil}", "T1" if present else None, topic=f"t{topic}")
                           for pupil, pattern in enumerate(patterns) for topic, present in enumerate(pattern)]
                result = summarize_teacher_attribution(iter(records))
                self.assertEqual(result["fully_attributed_students"], sum(all(p) for p in patterns))
                self.assertEqual(result["partially_attributed_students"], sum(any(p) and not all(p) for p in patterns))
                self.assertEqual(result["unattributed_students"], sum(not any(p) for p in patterns))
                self.assertEqual(sum(result[key] for key in (
                    "fully_attributed_students", "partially_attributed_students", "unattributed_students",
                )), 3)
                self.assertEqual(result["missing_teacher_rows"], sum(not present for p in patterns for present in p))
                self.assertEqual(result["fully_attributed_student_share"], result["fully_attributed_students"] / 3)


if __name__ == "__main__":
    unittest.main()
