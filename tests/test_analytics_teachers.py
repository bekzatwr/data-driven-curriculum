import copy
import unittest

from analytics.common import AnalyticsError
from analytics.demo import demo_records
from analytics.teachers import compute_teachers


TOPICS = [{"topic_id": "t1", "current_hours": 6}, {"topic_id": "t2", "current_hours": 18}]


def row(student, score=60, *, teacher="T1", school="S1", classroom="7A", topic="t1",
        stage="post", version="v1", maximum=100, textbook="A"):
    return {"student_id": student, "score": score, "teacher_id": teacher, "school_id": school,
            "class_id": classroom, "topic_id": topic, "stage": stage, "test_version": version,
            "max_score": maximum, "textbook_id": textbook}


class TeacherMetricsTests(unittest.TestCase):
    def test_full_demo_counts_hours_and_known_gains(self):
        topics, records = demo_records()
        result = compute_teachers(records, topics)
        self.assertEqual(result["hours_per_class"], 24)
        self.assertEqual(result["missing_teacher_rows"], 0)
        self.assertEqual(result["total"], {
            "school_id": "Все школы", "teachers": 4, "students": 120, "classes": 4,
            "teacher_attribution": {"fully_attributed_students": 120, "partially_attributed_students": 0,
                                    "unattributed_students": 0, "fully_attributed_student_share": 1,
                                    "missing_teacher_rows": 0},
            "students_per_teacher": 30, "classes_per_teacher": 1, "hours_per_teacher": 24,
        })
        for teacher in result["teachers"]:
            self.assertEqual(teacher["students"], 30)
            self.assertEqual(teacher["upcoming_hours"], 24)
            self.assertEqual(teacher["n_post"], 180)
            self.assertEqual(teacher["n_pairs"], 180)
            self.assertEqual(teacher["n_post_students"], 30)
            self.assertEqual(teacher["topic_count"], 6)
            self.assertEqual(teacher["post_topic_count"], 6)
            self.assertEqual(teacher["n_complete_students"], 30)
            self.assertEqual(teacher["complete_student_share"], 1)
            self.assertEqual(teacher["n_paired_students"], 30)
            self.assertEqual(teacher["paired_student_share"], 1)
            self.assertEqual(teacher["pair_coverage"], 1)
            self.assertEqual(teacher["mean_post_paired_pct"], teacher["mean_post_pct"])
            self.assertAlmostEqual(teacher["mean_post_paired_pct"] - teacher["mean_pre_paired_pct"],
                                   teacher["mean_gain_pp"])
            self.assertFalse(teacher["is_missing_teacher"])
        self.assertAlmostEqual(result["teachers"][0]["mean_post_pct"], 434 / 6)
        self.assertAlmostEqual(result["teachers"][0]["mean_gain_pp"], 73 / 6)
        self.assertAlmostEqual(result["teachers"][2]["mean_post_pct"], 427 / 6)
        self.assertAlmostEqual(result["teachers"][2]["mean_gain_pp"], 65 / 6)

    def test_same_teacher_id_in_two_schools_is_not_merged(self):
        records = [row("a", school="S1", classroom="7A"),
                   row("b", school="S2", classroom="7A"),
                   row("c", school="S2", classroom="7B")]
        result = compute_teachers(records, TOPICS)
        self.assertEqual([(t["school_id"], t["teacher_id"], t["students"]) for t in result["teachers"]],
                         [("S1", "T1", 1), ("S2", "T1", 2)])
        self.assertEqual(result["total"]["teachers"], 2)
        self.assertEqual(result["total"]["classes"], 3)
        self.assertEqual(result["total"]["classes_per_teacher"], 1.5)
        self.assertEqual(result["schools"][0]["hours_per_teacher"], 24)
        self.assertEqual(result["schools"][1]["hours_per_teacher"], 48)

    def test_missing_and_literal_display_label_are_distinct_and_school_scoped(self):
        records = [row("known", teacher="Не указан"), row("missing", teacher=None),
                   row("blank", teacher=" \t"), row("other", teacher="", school="S2")]
        result = compute_teachers(records, TOPICS)
        self.assertEqual(result["missing_teacher_rows"], 3)
        self.assertEqual(result["total"]["teachers"], 1)
        self.assertEqual(result["total"]["students"], 4)
        self.assertEqual(result["total"]["students_per_teacher"], 4)
        self.assertEqual([(t["school_id"], t["is_missing_teacher"], t["students"]) for t in result["teachers"]],
                         [("S1", False, 1), ("S1", True, 2), ("S2", True, 1)])
        self.assertEqual(result["schools"][0]["students_per_teacher"], 3)
        self.assertIsNone(result["schools"][1]["students_per_teacher"])
        self.assertIsNone(result["schools"][1]["classes_per_teacher"])
        self.assertIsNone(result["schools"][1]["hours_per_teacher"])
        self.assertTrue(result["teachers"][1]["warnings"])
        self.assertTrue(any("неполную атрибуцию" in warning for warning in result["warnings"]))

    def test_nonblank_identifiers_preserved_and_sorting_is_deterministic(self):
        records = [row("a", teacher=" T1 "), row("b", teacher="T1"), row("c", teacher=None),
                   row("d", teacher="T0", school="S0")]
        result = compute_teachers(records, TOPICS)
        self.assertEqual(result, compute_teachers(list(reversed(records)), TOPICS))
        self.assertEqual([t["teacher_id"] for t in result["teachers"]], ["T0", " T1 ", "T1", "Не указан"])

    def test_coteaching_counts_links_not_unique_school_classes(self):
        records = [row("a", teacher="T1"), row("a", teacher="T2", topic="t2"),
                   row("b", teacher="T2", classroom="7B")]
        result = compute_teachers(records, TOPICS)
        self.assertEqual(result["total"]["students"], 2)
        self.assertEqual(result["total"]["classes"], 2)
        self.assertEqual(result["total"]["students_per_teacher"], 1)
        self.assertEqual(result["total"]["classes_per_teacher"], 1.5)
        self.assertEqual(result["total"]["hours_per_teacher"], 36)
        self.assertEqual([t["upcoming_hours"] for t in result["teachers"]], [24, 48])
        self.assertTrue(any("несколькими" in warning for warning in result["warnings"]))

    def test_pre_only_and_no_pre_keep_workload_without_inventing_gain(self):
        records = [row("pre", 30, stage="pre"), row("post", 70, teacher="T2")]
        result = compute_teachers(records, TOPICS)
        first, second = result["teachers"]
        self.assertEqual(first["students"], 1)
        self.assertEqual(first["upcoming_hours"], 24)
        self.assertEqual(first["n_post"], 0)
        self.assertIsNone(first["mean_post_pct"])
        self.assertIsNone(first["mean_pre_paired_pct"])
        self.assertIsNone(first["mean_post_paired_pct"])
        self.assertIsNone(first["pair_coverage"])
        self.assertEqual(first["n_paired_students"], 0)
        self.assertIsNone(first["paired_student_share"])
        self.assertEqual(second["mean_post_pct"], 70)
        self.assertEqual(second["pair_coverage"], 0)
        self.assertEqual(second["n_pairs"], 0)
        self.assertEqual(second["n_paired_students"], 0)
        self.assertEqual(second["paired_student_share"], 0)
        self.assertIsNone(second["mean_gain_pp"])
        self.assertIsNone(second["mean_pre_paired_pct"])
        self.assertIsNone(second["mean_post_paired_pct"])

    def test_paired_means_exclude_unmatched_pre_and_high_post(self):
        records = [row("paired", 40, stage="pre"), row("paired", 60),
                   row("post-only", 100), row("pre-only", 100, stage="pre")]
        teacher = compute_teachers(records, TOPICS)["teachers"][0]
        self.assertEqual(teacher["n_post"], 2)
        self.assertEqual(teacher["n_pairs"], 1)
        self.assertEqual(teacher["n_paired_students"], 1)
        self.assertEqual(teacher["mean_post_pct"], 80)
        self.assertEqual(teacher["mean_pre_paired_pct"], 40)
        self.assertEqual(teacher["mean_post_paired_pct"], 60)
        self.assertEqual(teacher["mean_gain_pp"], 20)
        self.assertEqual(teacher["mean_post_paired_pct"] - teacher["mean_pre_paired_pct"], teacher["mean_gain_pp"])

    def test_zero_paired_means_are_numbers_and_not_null(self):
        teacher = compute_teachers([row("zero", 0, stage="pre"), row("zero", 0)], TOPICS)["teachers"][0]
        self.assertEqual(teacher["mean_pre_paired_pct"], 0)
        self.assertEqual(teacher["mean_post_paired_pct"], 0)
        self.assertEqual(teacher["mean_gain_pp"], 0)

    def test_many_topic_pairs_of_one_pupil_do_not_inflate_paired_students(self):
        topics = [{"topic_id": f"t{i}", "current_hours": 4} for i in range(6)]
        records = [row(f"s{student}", 60, topic=topic["topic_id"])
                   for student in range(30) for topic in topics]
        records += [row("s0", 20, topic=topic["topic_id"], stage="pre") for topic in topics]
        teacher = compute_teachers(records, topics)["teachers"][0]
        self.assertEqual(teacher["n_post"], 180)
        self.assertEqual(teacher["n_post_students"], 30)
        self.assertEqual(teacher["n_pairs"], 6)
        self.assertEqual(teacher["n_paired_students"], 1)
        self.assertAlmostEqual(teacher["paired_student_share"], 1 / 30)
        self.assertEqual(teacher["mean_post_pct"], 60)
        self.assertEqual(teacher["mean_gain_pp"], 40)
        self.assertTrue(any("Мало учеников в парной выборке" in warning for warning in teacher["warnings"]))

    def test_pair_share_uses_unique_pupils_not_topic_observations(self):
        records = [row("a", 20, topic="t1", stage="pre"), row("a", 60, topic="t1"),
                   row("a", 30, topic="t2", stage="pre"), row("a", 70, topic="t2"),
                   row("b", 80, topic="t1")]
        teacher = compute_teachers(records, TOPICS)["teachers"][0]
        self.assertEqual(teacher["n_pairs"], 2)
        self.assertEqual(teacher["n_paired_students"], 1)
        self.assertAlmostEqual(teacher["pair_coverage"], 2 / 3)
        self.assertEqual(teacher["paired_student_share"], 1 / 2)

    def test_paired_pupil_warning_threshold_and_zero_pairs(self):
        for pupils, minimum, expected_warning in ((0, 10, False), (9, 10, True),
                                                  (10, 10, False), (11, 10, False),
                                                  (11, 12, True)):
            with self.subTest(pupils=pupils, minimum=minimum):
                records = [row(f"s{i}", 60) for i in range(30)]
                records += [row(f"s{i}", 20, stage="pre") for i in range(pupils)]
                teacher = compute_teachers(records, TOPICS, settings={"min_students": minimum})["teachers"][0]
                self.assertEqual(teacher["n_paired_students"], pupils)
                self.assertAlmostEqual(teacher["paired_student_share"], pupils / 30)
                warned = any("Мало учеников в парной выборке" in warning for warning in teacher["warnings"])
                self.assertEqual(warned, expected_warning)

    def test_changed_or_missing_teacher_does_not_receive_cross_teacher_gain(self):
        for post_teacher in ("T2", None, ""):
            with self.subTest(post_teacher=post_teacher):
                records = [row("a", 20, stage="pre"), row("a", 80, teacher=post_teacher)]
                result = compute_teachers(records, TOPICS)
                self.assertEqual(result["total"]["students"], 1)
                self.assertTrue(all(t["n_pairs"] == 0 and t["mean_gain_pp"] is None for t in result["teachers"]))
                self.assertTrue(all(t["n_paired_students"] == 0 for t in result["teachers"]))

    def test_compatible_pairs_and_negative_gain_use_shared_percentages(self):
        records = [row("a", 8, maximum=10, stage="pre"), row("a", 4, maximum=10),
                   row("b", 2, maximum=10, stage="pre"), row("b", 5, maximum=10)]
        teacher = compute_teachers(records, TOPICS)["teachers"][0]
        self.assertEqual(teacher["mean_post_pct"], 45)
        self.assertEqual(teacher["mean_pre_paired_pct"], 50)
        self.assertEqual(teacher["mean_post_paired_pct"], 45)
        self.assertEqual(teacher["mean_gain_pp"], -5)
        self.assertEqual(teacher["n_pairs"], 2)
        self.assertEqual(teacher["n_paired_students"], 2)
        self.assertEqual(teacher["paired_student_share"], 1)

    def test_pair_compatibility_rejects_textbook_class_school_and_scale_changes(self):
        for changes in ({"textbook": "B"}, {"classroom": "7B"}, {"school": "S2"},
                        {"version": "v2"}, {"maximum": 200}):
            with self.subTest(changes=changes):
                result = compute_teachers([row("a", 20, stage="pre"), row("a", 80, **changes)], TOPICS)
                self.assertTrue(all(t["n_pairs"] == 0 and t["mean_gain_pp"] is None for t in result["teachers"]))

    def test_mixed_versions_suppress_both_means_and_filter_recovers_slice(self):
        records = [row("a", 10, stage="pre"), row("a", 50),
                   row("b", 20, stage="pre", version="v2"), row("b", 80, version="v2")]
        teacher = compute_teachers(records, TOPICS)["teachers"][0]
        self.assertEqual(teacher["mixed_topic_ids"], ["t1"])
        self.assertEqual(teacher["n_pairs"], 2)
        self.assertIsNone(teacher["mean_post_pct"])
        self.assertIsNone(teacher["mean_pre_paired_pct"])
        self.assertIsNone(teacher["mean_post_paired_pct"])
        self.assertIsNone(teacher["mean_gain_pp"])
        filtered = compute_teachers(records, TOPICS, {"test_version": "v2"})["teachers"][0]
        self.assertEqual(filtered["mean_post_pct"], 80)
        self.assertEqual(filtered["mean_gain_pp"], 60)
        self.assertEqual(filtered["mean_pre_paired_pct"], 20)
        self.assertEqual(filtered["mean_post_paired_pct"], 80)
        self.assertEqual(filtered["n_paired_students"], 1)
        self.assertEqual(filtered["paired_student_share"], 1)
        self.assertEqual(filtered["mixed_topic_ids"], [])

    def test_mean_post_weights_observations_as_existing_teacher_ui(self):
        records = [row("a", 100), row("a", 0, topic="t2"), row("b", 100)]
        teacher = compute_teachers(records, TOPICS)["teachers"][0]
        self.assertAlmostEqual(teacher["mean_post_pct"], 200 / 3)
        self.assertNotEqual(teacher["mean_post_pct"], 75)
        self.assertEqual(teacher["n_post_students"], 2)
        self.assertEqual(teacher["n_post"], 3)

    def test_filters_apply_to_all_summaries_but_not_curriculum_hours(self):
        records = [row("a", 20, stage="pre"), row("a", 60),
                   row("b", 100, teacher="T2", classroom="7B", textbook="B"),
                   row("a", 90, topic="t2")]
        original = copy.deepcopy((records, TOPICS))
        filtered = compute_teachers(records, TOPICS, {
            "class_ids": ["7A"], "textbook_ids": ["A"], "topic_ids": ["t1"], "test_version": "v1",
        })
        self.assertEqual(filtered["hours_per_class"], 24)
        self.assertEqual(filtered["teachers"][0]["upcoming_hours"], 24)
        self.assertEqual(filtered["teachers"][0]["mean_gain_pp"], 40)
        self.assertEqual(filtered["total"]["teachers"], 1)
        self.assertEqual(filtered["total"]["students"], 1)
        self.assertEqual((records, TOPICS), original)
        empty = compute_teachers(records, TOPICS, {"class_ids": ["7A"], "textbook_ids": ["B"]})
        self.assertEqual(empty["teachers"], [])
        self.assertEqual(empty["schools"], [])
        self.assertEqual(empty["total"]["students"], 0)
        self.assertEqual(empty["hours_per_class"], 24)

    def test_zero_empty_and_missing_teacher_are_not_false_teachers(self):
        teacher = compute_teachers([row("a", 0)], TOPICS)["teachers"][0]
        self.assertEqual(teacher["mean_post_pct"], 0)
        empty = compute_teachers([], TOPICS)
        self.assertEqual(empty["total"]["teachers"], 0)
        self.assertIsNone(empty["total"]["students_per_teacher"])
        missing = compute_teachers([row("a", 0, teacher=None)], TOPICS)
        self.assertEqual(missing["total"]["teachers"], 0)
        self.assertEqual(missing["total"]["students"], 1)
        self.assertIsNone(missing["total"]["hours_per_teacher"])

    def test_duplicate_across_teacher_groups_raises_and_bad_settings_raise(self):
        with self.assertRaises(AnalyticsError) as context:
            compute_teachers([row("a"), row("a", teacher="T2")], TOPICS)
        self.assertEqual(context.exception.code, "DUPLICATE_RESULT")
        with self.assertRaises(AnalyticsError):
            compute_teachers([], TOPICS, settings={"min_students": 9})

    def test_maximum_records_with_distinct_teachers_and_schools(self):
        topics = [{"topic_id": f"t{i:03d}", "current_hours": 1} for i in range(100)]
        records = [row(f"p{i:05d}", 70, teacher=f"T{i:05d}", school=f"S{i:05d}",
                       classroom=f"C{i:05d}", topic=f"t{i % 100:03d}") for i in range(10_000)]
        result = compute_teachers(records, topics)
        self.assertEqual(len(result["teachers"]), 10_000)
        self.assertEqual(len(result["schools"]), 10_000)
        self.assertEqual(result["hours_per_class"], 100)
        self.assertEqual(result["total"], {
            "school_id": "Все школы", "teachers": 10_000, "students": 10_000, "classes": 10_000,
            "teacher_attribution": {"fully_attributed_students": 10_000, "partially_attributed_students": 0,
                                    "unattributed_students": 0, "fully_attributed_student_share": 1,
                                    "missing_teacher_rows": 0},
            "students_per_teacher": 1, "classes_per_teacher": 1, "hours_per_teacher": 100,
        })
        for index, (teacher, school) in enumerate(zip(result["teachers"], result["schools"])):
            self.assertEqual(teacher["school_id"], f"S{index:05d}")
            self.assertEqual(teacher["teacher_id"], f"T{index:05d}")
            self.assertEqual(teacher["mean_post_pct"], 70)
            self.assertEqual(teacher["upcoming_hours"], 100)
            self.assertEqual(teacher["n_pairs"], 0)
            self.assertEqual(teacher["n_paired_students"], 0)
            self.assertEqual(teacher["mixed_topic_ids"], [])
            self.assertEqual(school["school_id"], teacher["school_id"])
            self.assertEqual(school["teachers"], 1)
            self.assertEqual(school["hours_per_teacher"], 100)

    def test_sparse_mixed_topics_keep_curriculum_order_and_all_hours(self):
        topics = [{"topic_id": f"t{i:03d}", "current_hours": 1} for i in range(100)]
        topics.reverse()
        records = [row(f"p{i}-{version}", topic=f"t{i:03d}", version=version)
                   for i in (2, 70) for version in ("v1", "v2")]
        teacher = compute_teachers(records, topics)["teachers"][0]
        self.assertEqual(teacher["mixed_topic_ids"], ["t070", "t002"])
        self.assertEqual(teacher["upcoming_hours"], 100)
        self.assertIsNone(teacher["mean_post_pct"])
        self.assertIsNone(teacher["mean_gain_pp"])

    def test_full_pairs_on_one_of_hundred_topics_do_not_mean_complete_curriculum(self):
        topics = [{"topic_id": f"t{i:03d}", "current_hours": 1} for i in range(100)]
        records = [row(f"s{student}", 80 if stage == "pre" else 100, topic="t000", stage=stage)
                   for student in range(30) for stage in ("pre", "post")]
        teacher = compute_teachers(records, topics)["teachers"][0]
        self.assertEqual(teacher["mean_post_pct"], 100)
        self.assertEqual(teacher["pair_coverage"], 1)
        self.assertEqual(teacher["paired_student_share"], 1)
        self.assertEqual(teacher["topic_count"], 100)
        self.assertEqual(teacher["post_topic_count"], 1)
        self.assertEqual(teacher["n_complete_students"], 0)
        self.assertEqual(teacher["complete_student_share"], 0)
        self.assertTrue(any("отсутствие записей не означает отсутствие обучения" in warning
                            for warning in teacher["warnings"]))

    def test_topic_union_does_not_count_pupils_as_complete(self):
        records = [row(f"s{i}", topic="t1" if i < 15 else "t2") for i in range(30)]
        teacher = compute_teachers(records, TOPICS)["teachers"][0]
        self.assertEqual(teacher["post_topic_count"], 2)
        self.assertEqual(teacher["topic_count"], 2)
        self.assertEqual(teacher["n_complete_students"], 0)
        self.assertEqual(teacher["complete_student_share"], 0)
        self.assertTrue(any("Неполное покрытие" in warning for warning in teacher["warnings"]))

    def test_complete_share_uses_post_pupils_and_preserves_observation_weighting(self):
        records = [row("full", 100), row("full", 0, topic="t2"), row("partial", 100),
                   row("pre-only", 20, stage="pre"), row("pre-only", 30, topic="t2", stage="pre")]
        teacher = compute_teachers(records, TOPICS)["teachers"][0]
        self.assertEqual(teacher["students"], 3)
        self.assertEqual(teacher["n_post_students"], 2)
        self.assertEqual(teacher["n_complete_students"], 1)
        self.assertEqual(teacher["complete_student_share"], 0.5)
        self.assertAlmostEqual(teacher["mean_post_pct"], 200 / 3)
        pre_only = compute_teachers([row("pre", stage="pre"), row("pre", topic="t2", stage="pre")], TOPICS)["teachers"][0]
        self.assertEqual(pre_only["topic_count"], 2)
        self.assertEqual(pre_only["post_topic_count"], 0)
        self.assertEqual(pre_only["n_complete_students"], 0)
        self.assertIsNone(pre_only["complete_student_share"])

    def test_coverage_filters_records_but_keeps_full_curriculum_denominator(self):
        records = [row("a", topic="t1", version="v1", textbook="A"),
                   row("a", topic="t2", version="v2", textbook="B"),
                   row("b", topic="t1", classroom="7B"), row("b", topic="t2", classroom="7B")]
        complete = compute_teachers(records, TOPICS, {"class_ids": ["7B"]})["teachers"][0]
        self.assertEqual(complete["n_complete_students"], 1)
        self.assertEqual(complete["complete_student_share"], 1)
        for filter_values in ({"test_version": "v1"}, {"textbook_ids": ["A"]}, {"topic_ids": ["t1"]}):
            with self.subTest(filters=filter_values):
                teacher = compute_teachers(records, TOPICS, {"class_ids": ["7A"], **filter_values})["teachers"][0]
                self.assertEqual(teacher["n_post_students"], 1)
                self.assertEqual(teacher["topic_count"], 2)
                self.assertEqual(teacher["post_topic_count"], 1)
                self.assertEqual(teacher["n_complete_students"], 0)
                self.assertEqual(teacher["complete_student_share"], 0)
                self.assertEqual(teacher["upcoming_hours"], 24)

    def test_mixed_versions_keep_availability_counts_while_suppressing_means(self):
        records = [row(student, 40 if stage == "pre" else 60, topic=topic, stage=stage, version=version)
                   for student, version in (("a", "v1"), ("b", "v2"))
                   for topic in ("t1", "t2") for stage in ("pre", "post")]
        teacher = compute_teachers(records, TOPICS)["teachers"][0]
        self.assertEqual(teacher["mixed_topic_ids"], ["t1", "t2"])
        self.assertEqual(teacher["topic_count"], 2)
        self.assertEqual(teacher["post_topic_count"], 2)
        self.assertEqual(teacher["n_complete_students"], 2)
        self.assertEqual(teacher["complete_student_share"], 1)
        self.assertIsNone(teacher["mean_post_pct"])
        self.assertIsNone(teacher["mean_pre_paired_pct"])
        self.assertIsNone(teacher["mean_post_paired_pct"])
        self.assertIsNone(teacher["mean_gain_pp"])

    def test_unique_curriculum_topics_and_empty_curriculum_do_not_make_false_full_coverage(self):
        records = [row("a"), row("a", topic="t2")]
        unique = compute_teachers(records, [*TOPICS, TOPICS[0]])["teachers"][0]
        self.assertEqual(unique["topic_count"], 2)
        self.assertEqual(unique["n_complete_students"], 1)
        empty = compute_teachers(records, [])["teachers"][0]
        self.assertEqual(empty["topic_count"], 0)
        self.assertEqual(empty["post_topic_count"], 0)
        self.assertEqual(empty["n_complete_students"], 0)
        self.assertIsNone(empty["complete_student_share"])

    def test_coverage_stays_inside_teacher_and_school_group(self):
        records = [row("a", teacher="T1"), row("a", teacher="T2", topic="t2"),
                   row("b", teacher="T1", school="S2"), row("b", teacher="T1", school="S2", topic="t2")]
        groups = compute_teachers(records, TOPICS)["teachers"]
        self.assertEqual([(teacher["school_id"], teacher["teacher_id"], teacher["n_complete_students"])
                          for teacher in groups], [("S1", "T1", 0), ("S1", "T2", 0), ("S2", "T1", 1)])


if __name__ == "__main__":
    unittest.main()
