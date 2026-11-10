"""Audit safeguards: tolerances must not hide missing values or lost records."""
import copy
import unittest

from scripts.verify_teachers_parity import ParityError, compare_legacy, legacy_projection, source_sha256


def summary():
    school = {"school_id": "S1", "teachers": 1, "students": 30, "classes": 2,
              "students_per_teacher": 30, "classes_per_teacher": 2, "hours_per_teacher": 48}
    teacher = {"teacher_id": "T1", "school_id": "S1", "class_ids": ["7B", "7A"],
               "students": 30, "textbooks": ["B", "A"], "n_post": 180,
               "mean_post_pct": 72.5, "n_pairs": 180, "mean_gain_pp": 12.5, "upcoming_hours": 48}
    return {"teachers": [teacher], "schools": [school], "total": {**school, "school_id": "Все школы"},
            "hours_per_class": 24, "missing_teacher_rows": 0}


class TeacherParitySafeguardTests(unittest.TestCase):
    def test_sorting_additive_fields_and_float_noise_do_not_fail_parity(self):
        ui, backend = summary(), summary()
        backend["teachers"][0]["class_ids"].reverse()
        backend["teachers"][0]["textbooks"].reverse()
        backend["teachers"][0]["mean_post_pct"] += 5e-11
        backend["teachers"][0]["n_paired_students"] = 30
        backend["teachers"][0]["paired_student_share"] = 1
        backend["warnings"] = ["Additional context"]
        before = copy.deepcopy((ui, backend))
        comparison = compare_legacy(legacy_projection(ui, "UI"), legacy_projection(backend, "backend"))
        self.assertEqual(comparison["differences"], [])
        self.assertLessEqual(comparison["maximum_absolute_numeric_difference"], 1e-10)
        self.assertEqual((ui, backend), before)

    def test_differences_have_stable_paths_and_null_zero_and_bool_are_distinct(self):
        ui, backend = summary(), summary()
        ui["teachers"][0]["mean_gain_pp"] = None
        backend["teachers"][0]["mean_gain_pp"] = 0
        backend["teachers"][0]["n_pairs"] = 179
        backend["missing_teacher_rows"] = False
        comparison = compare_legacy(legacy_projection(ui, "UI"), legacy_projection(backend, "backend"))
        self.assertEqual([item["path"] for item in comparison["differences"]],
                         ["missing_teacher_rows", "teachers[0].mean_gain_pp", "teachers[0].n_pairs"])
        backend["teachers"][0]["mean_post_pct"] += 1e-8
        comparison = compare_legacy(legacy_projection(ui, "UI"), legacy_projection(backend, "backend"))
        self.assertIn("teachers[0].mean_post_pct", [item["path"] for item in comparison["differences"]])

    def test_duplicates_missing_fields_and_checkout_line_endings_are_checked(self):
        ui, backend = summary(), summary()
        backend["teachers"][0]["class_ids"].append("7B")
        comparison = compare_legacy(legacy_projection(ui, "UI"), legacy_projection(backend, "backend"))
        self.assertIn({"path": "teachers[0].class_ids", "reason": "Different array length",
                       "ui_length": 2, "backend_length": 3}, comparison["differences"])
        del backend["teachers"][0]["n_pairs"]
        with self.assertRaisesRegex(ParityError, r"backend\.teachers\[0\]\.n_pairs"):
            legacy_projection(backend, "backend")
        self.assertEqual(source_sha256(b"a\r\nb\rc\n"), source_sha256(b"a\nb\nc\n"))


if __name__ == "__main__":
    unittest.main()
