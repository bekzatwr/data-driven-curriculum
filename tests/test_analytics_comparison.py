"""Manual-oracle cases for the T04, T07 and T08 acceptance requirements."""
import unittest

from analytics.common import AnalyticsError
from analytics.comparison import DISCLAIMER, compare_textbooks


def group(book, pre=50, post=70, n=10, version="v1", maximum=100, teacher="teacher"):
    rows = []
    for index in range(n):
        for stage, score in (("pre", pre), ("post", post)):
            rows.append({
                "student_id": f"{book}{index}", "school_id": "school", "class_id": book,
                "teacher_id": teacher, "textbook_id": book, "topic_id": "fractions",
                "test_version": version, "max_score": maximum, "score": score, "stage": stage,
                "tested_at": "2026-09-01" if stage == "pre" else "2026-10-01",
            })
    return rows


def compare(rows, **kwargs):
    return compare_textbooks(rows, "fractions", "A", "B", **kwargs)


class TextbookComparisonTests(unittest.TestCase):
    def test_manual_known_gain_and_paired_population(self):
        rows = group("A", pre=52, post=68, n=60) + group("B", pre=53, post=61, n=60)
        # A high-scoring student without a pre must not inflate paired post/gain.
        extra = {**rows[1], "student_id": "unpaired", "score": 100}
        result = compare(rows + [extra])
        self.assertEqual(result["comparison_status"], "comparable")
        self.assertEqual(result["group_a"]["n_post"], 61)
        self.assertEqual(result["group_a"]["n_pairs"], 60)
        self.assertEqual(result["group_a"]["mean_post_paired_pct"], 68)
        self.assertEqual(result["group_a"]["mean_gain_pp"], 16)
        self.assertAlmostEqual(result["group_a"]["mean_post_pct"], (60 * 68 + 100) / 61)
        self.assertAlmostEqual(result["group_a"]["pair_coverage"], 60 / 61)
        self.assertEqual(result["difference_gain_pp"], 8)
        self.assertEqual(result["baseline_gap_pp"], 1)

    def test_missing_pre_preserves_descriptive_post(self):
        result = compare([r for r in group("A") if r["stage"] == "post"] + group("B"))
        self.assertEqual(result["comparison_status"], "insufficient_data")
        self.assertEqual(result["group_a"]["mean_post_pct"], 70)
        self.assertEqual(result["group_a"]["pair_coverage"], 0)
        self.assertIsNone(result["group_a"]["mean_post_paired_pct"])
        self.assertIsNone(result["group_a"]["mean_gain_pp"])
        self.assertIsNone(result["difference_gain_pp"])
        self.assertTrue(any("прирост недоступен" in reason for reason in result["reasons"]))

    def test_nine_pairs_insufficient_ten_pairs_allowed(self):
        self.assertEqual(compare(group("A", n=9) + group("B"))["comparison_status"], "insufficient_data")
        self.assertEqual(compare(group("A") + group("B"))["comparison_status"], "comparable")

    def test_baseline_exactly_ten_allowed_above_ten_rejected(self):
        allowed = compare(group("A", pre=50) + group("B", pre=60))
        self.assertEqual(allowed["comparison_status"], "comparable")
        rejected = compare(group("A", pre=50) + group("B", pre=60.01))
        self.assertEqual(rejected["comparison_status"], "not_comparable")
        self.assertIsNone(rejected["difference_gain_pp"])
        self.assertTrue(any("входных" in reason for reason in rejected["reasons"]))

    def test_different_versions_or_maximum_do_not_compare(self):
        for other in (group("B", version="v2"), group("B", pre=25, post=35, maximum=50)):
            with self.subTest(other=other[0]["test_version"], maximum=other[0]["max_score"]):
                result = compare(group("A") + other)
                self.assertEqual(result["comparison_status"], "not_comparable")
                self.assertIsNone(result["difference_gain_pp"])
                self.assertIsNotNone(result["group_b"]["mean_gain_pp"])
                self.assertIsNone(result["test_version"])

    def test_mixed_versions_are_not_blended_inside_group(self):
        extra = group("A", pre=10, post=100, version="v2")
        for row in extra:
            row["student_id"] += "-v2"
        result = compare(group("A") + extra + group("B"))
        self.assertEqual(result["comparison_status"], "not_comparable")
        self.assertEqual(result["group_a"]["n_pairs"], 20)
        self.assertEqual(len(result["group_a"]["available_slices"]), 2)
        self.assertIsNone(result["group_a"]["mean_post_pct"])
        self.assertIsNone(result["group_a"]["mean_gain_pp"])
        self.assertIsNone(result["difference_gain_pp"])

    def test_negative_gains_and_equal_gains(self):
        result = compare(group("A", pre=60, post=40) + group("B", pre=60, post=50))
        self.assertEqual(result["group_a"]["mean_gain_pp"], -20)
        self.assertEqual(result["difference_gain_pp"], -10)
        self.assertIn("группы B", result["conclusion"])
        tie = compare(group("A", pre=60, post=40) + group("B", pre=55, post=35))
        self.assertEqual(tie["difference_gain_pp"], 0)
        self.assertEqual(tie["conclusion"], "Одинаковый наблюдаемый прирост.")

    def test_zero_and_empty_are_distinct(self):
        zeros = compare(group("A", pre=0, post=0) + group("B", pre=0, post=0))
        self.assertEqual(zeros["group_a"]["mean_post_pct"], 0)
        empty = compare([])
        self.assertEqual(empty["comparison_status"], "insufficient_data")
        self.assertIsNone(empty["group_a"]["mean_post_pct"])
        self.assertIsNone(empty["group_a"]["pair_coverage"])
        self.assertIsNone(empty["difference_gain_pp"])

    def test_confounds_teacher_unknown_and_paired_class_counts(self):
        rows = group("A", teacher=None) + group("B")
        # Unpaired post in another class does not inflate paired class counts.
        rows.append({**rows[1], "student_id": "other", "class_id": "extra"})
        result = compare(rows)
        self.assertEqual(result["group_a"]["n_classes"], 1)
        self.assertEqual(result["group_a"]["n_teachers"], 0)
        self.assertEqual(result["group_b"]["n_teachers"], 1)
        self.assertIn(DISCLAIMER, result["warnings"])
        self.assertTrue(any("одним классом" in warning for warning in result["warnings"]))
        self.assertTrue(any("одним учителем" in warning for warning in result["warnings"]))
        self.assertTrue(any("неполно" in warning for warning in result["warnings"]))

    def test_overlapping_students_rejected_even_unpaired(self):
        rows_a = group("A")
        rows_b = group("B")
        rows_b[0]["student_id"] = rows_a[0]["student_id"]
        with self.assertRaises(AnalyticsError) as caught:
            compare(rows_a + rows_b)
        self.assertEqual(caught.exception.code, "OVERLAPPING_STUDENTS")

    def test_teacher_ids_are_scoped_by_school_in_paired_population(self):
        first_school = group("A", teacher="T1")
        second_school = [{**row, "student_id": "second-" + row["student_id"],
                          "school_id": "second-school", "class_id": "second-A"}
                         for row in first_school]
        result = compare(first_school + second_school + group("B"))
        self.assertEqual(result["group_a"]["n_teachers"], 2)
        self.assertEqual(result["group_a"]["n_classes"], 2)
        self.assertEqual(result["group_a"]["n_pairs"], 20)
        self.assertFalse(any(w.startswith("A:") and "одним учителем" in w for w in result["warnings"]))

    def test_same_book_and_duplicate_result_rejected(self):
        with self.assertRaises(AnalyticsError) as caught:
            compare_textbooks(group("A"), "fractions", "A", "A")
        self.assertEqual(caught.exception.code, "SAME_TEXTBOOK")
        rows = group("A") + group("B")
        with self.assertRaises(AnalyticsError) as caught:
            compare(rows + [dict(rows[0])])
        self.assertEqual(caught.exception.code, "DUPLICATE_RESULT")

    def test_incompatible_pre_post_not_used_as_pair(self):
        rows = group("A") + group("B")
        rows[0]["class_id"] = "different"
        result = compare(rows)
        self.assertEqual(result["group_a"]["n_pairs"], 9)
        self.assertEqual(result["comparison_status"], "insufficient_data")

    def test_settings_change_minimum_and_baseline_limit(self):
        rows = group("A", pre=50, n=12) + group("B", pre=56, n=12)
        self.assertEqual(compare(rows, settings={"max_baseline_gap_pp": 5})["comparison_status"], "not_comparable")
        self.assertEqual(compare(rows, settings={"min_students": 13})["comparison_status"], "insufficient_data")


if __name__ == "__main__":
    unittest.main()
