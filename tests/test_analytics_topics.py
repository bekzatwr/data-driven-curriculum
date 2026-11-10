import copy
import unittest

from analytics.common import AnalyticsError, normalize_settings, paired_rows
from analytics.topics import compute_overview, compute_topics


def row(student, score, *, topic="t1", stage="post", version="v1", maximum=100,
        book="A", classroom="7A", school="s1"):
    return {"student_id": str(student), "topic_id": topic, "stage": stage,
            "score": score, "max_score": maximum, "test_version": version,
            "textbook_id": book, "class_id": classroom, "school_id": school,
            "teacher_id": "teacher-" + classroom}


class TopicMetricsTests(unittest.TestCase):
    def test_t05_hand_calculated_and_strict_threshold(self):
        result = compute_topics([row(1, 40), row(2, 60), row(3, 80)])[0]
        self.assertEqual(result["mean_post_pct"], 60)
        self.assertAlmostEqual(result["below_threshold_share"], 1 / 3)
        self.assertEqual(result["n_post"], 3)
        self.assertEqual(result["status"], "insufficient_data")
        self.assertFalse(result["problem_topic"])

    def test_t04_missing_pre_is_not_a_zero_or_gain(self):
        records = [row(1, 40, stage="pre"), row(1, 70), row(2, 100)]
        result = compute_topics(records)[0]
        self.assertEqual(result["mean_post_pct"], 85)
        self.assertEqual(result["n_pairs"], 1)
        self.assertEqual(result["mean_pre_paired_pct"], 40)
        self.assertEqual(result["mean_post_paired_pct"], 70)
        self.assertEqual(result["mean_gain_pp"], 30)
        self.assertEqual(result["pair_coverage"], 0.5)

    def test_nine_ten_and_exact_score_boundaries(self):
        for score, expected in ((59.9, "requires_attention"), (60, "needs_practice"),
                                (79.9, "needs_practice"), (80, "mastered")):
            records = [row(i, score) for i in range(10)]
            self.assertEqual(compute_topics(records)[0]["status"], expected)
            self.assertEqual(compute_topics(records[:-1])[0]["status"], "insufficient_data")

    def test_problem_share_is_inclusive_even_if_mean_is_acceptable(self):
        scores = [40] * 4 + [100] * 6
        result = compute_topics([row(i, score) for i, score in enumerate(scores)])[0]
        self.assertEqual(result["mean_post_pct"], 76)
        self.assertTrue(result["problem_topic"])
        result = compute_topics([row(i, 40 if i < 3 else 100) for i in range(10)])[0]
        self.assertFalse(result["problem_topic"])

    def test_empty_pre_only_and_zero_are_distinct(self):
        empty = compute_topics([], {"topic_ids": ["empty"]})[0]
        self.assertEqual(empty["status"], "no_data")
        self.assertIsNone(empty["mean_post_pct"])
        self.assertIsNone(empty["pair_coverage"])
        pre_only = compute_topics([row(1, 20, stage="pre")])[0]
        self.assertEqual(pre_only["n_post"], 0)
        self.assertIsNone(pre_only["mean_gain_pp"])
        zero = compute_topics([row(1, 0)])[0]
        self.assertEqual(zero["mean_post_pct"], 0)
        self.assertEqual(zero["below_threshold_share"], 1)

    def test_negative_gain_and_non_hundred_scale(self):
        result = compute_topics([row(1, 8, stage="pre", maximum=10), row(1, 4, maximum=10)])[0]
        self.assertEqual(result["mean_post_pct"], 40)
        self.assertEqual(result["mean_gain_pp"], -40)

    def test_mixed_versions_and_scales_cannot_be_pooled(self):
        for other in (row(2, 70, version="v2"), row(2, 7, maximum=10)):
            result = compute_topics([row(1, 50), other])[0]
            self.assertEqual(result["status"], "mixed_versions")
            self.assertEqual(result["n_post"], 2)
            self.assertIsNone(result["mean_post_pct"])
            self.assertIsNone(result["problem_topic"])
            self.assertEqual(len(result["available_slices"]), 2)
        result = compute_topics([row(1, 50), row(2, 70, version="v2")], {"test_version": "v2"})[0]
        self.assertEqual(result["mean_post_pct"], 70)

    def test_incompatible_pairs_are_excluded(self):
        for changes in ({"book": "B"}, {"version": "v2"}, {"maximum": 200},
                        {"school": "other"}, {"classroom": "7B"}):
            with self.subTest(changes=changes):
                records = [row(1, 30, stage="pre"), row(1, 60, **changes)]
                self.assertEqual(paired_rows(records), [])
                self.assertEqual(compute_topics(records)[0]["n_pairs"], 0)

    def test_duplicate_attempts_fail_instead_of_overwriting(self):
        for stage in ("pre", "post"):
            with self.assertRaises(AnalyticsError) as error:
                compute_topics([row(1, 30, stage=stage), row(1, 50, stage=stage)])
            self.assertEqual(error.exception.code, "DUPLICATE_RESULT")

    def test_filters_apply_to_both_stages_and_preserve_inputs(self):
        records = [row(1, 10, stage="pre"), row(1, 60),
                   row(2, 80, classroom="7B", book="B"), row(3, 100, topic="t2")]
        original = copy.deepcopy(records)
        filters = {"class_ids": ["7A"], "textbook_ids": ["A"], "topic_ids": ["t1", "missing"]}
        metrics = compute_topics(records, filters)
        self.assertEqual([x["topic_id"] for x in metrics], ["t1", "missing"])
        self.assertEqual(metrics[0]["mean_post_pct"], 60)
        self.assertEqual(metrics[0]["mean_gain_pp"], 50)
        self.assertEqual(metrics[1]["status"], "no_data")
        self.assertEqual(records, original)
        self.assertEqual(compute_topics(records, {"topic_ids": []}), [])

    def test_overview_weights_students_not_result_rows(self):
        records = [row(1, 100), row(1, 0, topic="t2"), row(2, 100)]
        result = compute_overview(records, ["t1", "t2"])
        self.assertEqual(result["mean_post_pct"], 75)  # mean(50, 100), not 200/3
        self.assertEqual(result["n_students"], 2)
        self.assertEqual(result["n_post_results"], 3)
        self.assertEqual(result["n_complete_students"], 1)
        self.assertTrue(result["warnings"])

    def test_overview_pairs_count_student_topics_and_filters(self):
        records = [row(1, 20, stage="pre"), row(1, 60),
                   row(1, 30, topic="t2", stage="pre"), row(1, 80, topic="t2"),
                   row(2, 100, classroom="7B"), row(3, 20, stage="pre")]
        result = compute_overview(records, ["t1", "t2"], {"class_ids": ["7A"]})
        self.assertEqual(result["n_students"], 2)
        self.assertEqual(result["n_post_students"], 1)
        self.assertEqual(result["n_pairs"], 2)
        self.assertEqual(result["pair_coverage"], 1)
        self.assertEqual(result["mean_post_pct"], 70)

    def test_overview_mixed_versions_do_not_change_denominator_silently(self):
        records = [row(1, 10), row(2, 90, version="v2"), row(1, 100, topic="t2")]
        result = compute_overview(records, ["t1", "t2"])
        self.assertIsNone(result["mean_post_pct"])
        self.assertEqual(result["mixed_topic_ids"], ["t1"])
        self.assertEqual(result["n_post_results"], 3)
        empty = compute_overview([], ["t1"])
        self.assertIsNone(empty["mean_post_pct"])
        self.assertIsNone(empty["pair_coverage"])

    def test_overview_distinguishes_pupil_coverage_from_result_coverage(self):
        records = [row(1, 20, stage="pre"), row(1, 60),
                   row(1, 30, topic="t2", stage="pre"), row(1, 80, topic="t2"),
                   row(2, 70), row(3, 10, stage="pre"), row(3, 50),
                   row(4, 30, stage="pre")]
        result = compute_overview(records, ["t1", "t2"])
        self.assertEqual(result["n_pairs"], 3)
        self.assertEqual(result["pair_coverage"], 3 / 4)
        self.assertEqual(result["n_paired_students"], 2)
        self.assertEqual(result["n_post_students"], 3)
        self.assertEqual(result["paired_student_share"], 2 / 3)
        self.assertEqual(result["n_students"], 4)  # Pre-only pupil is outside the denominator.
        empty = compute_overview([row(1, 20, stage="pre")], ["t1"])
        self.assertEqual(empty["n_paired_students"], 0)
        self.assertIsNone(empty["paired_student_share"])

    def test_invalid_settings_and_custom_thresholds(self):
        for bad in ({"min_students": 9}, {"min_students": True}, {"threshold_pct": float("nan")},
                    {"threshold_pct": 90, "mastered_pct": 80}, {"problem_share": 2}, {"unknown": 1}):
            with self.subTest(bad=bad), self.assertRaises(AnalyticsError):
                normalize_settings(bad)
        result = compute_topics([row(i, 65) for i in range(10)], settings={"threshold_pct": 70})[0]
        self.assertEqual(result["status"], "requires_attention")


if __name__ == "__main__":
    unittest.main()
