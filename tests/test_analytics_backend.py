"""Optional real-backend checks; add backend/bekzat to PYTHONPATH to run.

The analytics branch does not vendor the backend branch. These checks are
skipped when its package is unavailable and use temporary SQLite databases.
"""
import csv
import importlib.util
import io
import tempfile
import unittest
import warnings
from dataclasses import replace
from pathlib import Path

BACKEND_AVAILABLE = importlib.util.find_spec("backend") is not None

if BACKEND_AVAILABLE:
    from fastapi.testclient import TestClient

    from analytics.app import create_integrated_app
    from analytics.demo import demo_files
    from backend.app.config import Settings


@unittest.skipUnless(BACKEND_AVAILABLE, "backend/bekzat is not on PYTHONPATH")
class BackendAnalyticsIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings = Settings(database_path=Path(self.directory.name) / "curriculum.sqlite3")
        self.client = TestClient(create_integrated_app(self.settings))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def import_analytics_demo(self):
        results, curriculum, metadata = demo_files()
        response = self.client.post(
            "/api/datasets/import?dry_run=false",
            data={"metadata": metadata},
            files={
                "results_file": ("results.csv", results, "text/csv"),
                "curriculum_file": ("curriculum.csv", curriculum, "text/csv"),
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["dataset_id"]

    def import_result_rows(self, rows, curriculum, metadata):
        content = io.StringIO(newline="")
        writer = csv.DictWriter(content, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        response = self.client.post("/api/datasets/import?dry_run=false", data={"metadata": metadata}, files={
            "results_file": ("results.csv", content.getvalue().encode("utf-8")),
            "curriculum_file": ("curriculum.csv", curriculum),
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["dataset_id"]

    def assert_analytics_and_saved_plan(self, dataset_id, *, is_demo):
        base = f"/api/datasets/{dataset_id}"
        filters_response = self.client.get(base + "/filters")
        self.assertEqual(filters_response.status_code, 200, filters_response.text)
        filters = filters_response.json()
        class_id = filters["classes"][0]["id"]
        topic_id = filters["topics"][0]["topic_id"]
        books = [book["id"] for book in filters["textbooks"]]

        overview = self.client.get(base + "/overview")
        self.assertEqual(overview.status_code, 200, overview.text)
        body = overview.json()
        self.assertEqual(body["dataset_id"], dataset_id)
        self.assertEqual(body["is_demo"], is_demo)
        self.assertEqual(len(body["topics"]), 6)
        self.assertTrue(body["heatmap"])
        self.assertIn("metrics", body)
        self.assertIn("applied_filters", body)

        topic = self.client.get(base + f"/topics/{topic_id}")
        self.assertEqual(topic.status_code, 200, topic.text)
        self.assertEqual(topic.json()["metrics"]["n_post"], 120)
        comparison = self.client.get(base + "/comparison", params={
            "topic_id": topic_id, "textbook_a": books[0], "textbook_b": books[1],
        })
        self.assertEqual(comparison.status_code, 200, comparison.text)
        self.assertEqual(comparison.json()["comparison_status"], "comparable")
        self.assertIsNotNone(comparison.json()["difference_gain_pp"])

        preview = self.client.post(base + "/plans/preview", json={"class_id": class_id})
        self.assertEqual(preview.status_code, 200, preview.text)
        proposed = preview.json()
        self.assertEqual(proposed["total_hours"], 24)
        hours = {item["topic_id"]: item["proposed_hours"] for item in proposed["items"]}
        self.assertEqual(sum(hours.values()), 24)
        saved = self.client.post(base + "/plans", json={
            "class_id": class_id, "hours_by_topic": hours, "comment": "Analytics integration check",
        })
        self.assertEqual(saved.status_code, 201, saved.text)
        plan = saved.json()
        report_path = "/api/plans/" + plan["plan_id"]
        self.assertEqual(self.client.get(report_path).json(), plan)
        exported = self.client.get(report_path + "/export.csv")
        self.assertEqual(exported.status_code, 200, exported.text)
        rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
        self.assertEqual({row["topic_id"]: int(row["proposed_hours"]) for row in rows}, hours)

        with TestClient(create_integrated_app(self.settings)) as restarted:
            self.assertEqual(restarted.get(report_path).json(), plan)
            self.assertEqual(restarted.get(base + "/overview").json(), body)

    def test_csv_import_analytics_plan_and_persistent_report(self):
        self.assert_analytics_and_saved_plan(self.import_analytics_demo(), is_demo=False)

    def test_backend_demo_analytics_plan_and_persistent_report(self):
        response = self.client.post("/api/datasets/demo")
        self.assertEqual(response.status_code, 201, response.text)
        self.assert_analytics_and_saved_plan(response.json()["dataset_id"], is_demo=True)

    def test_imported_same_teacher_ids_in_different_schools_stay_distinct(self):
        results, curriculum, metadata = demo_files()
        rows = list(csv.DictReader(io.StringIO(results.decode('utf-8'))))
        for row in rows:
            if row['class_id'] == '7B':
                row['school_id'] = 'SECOND-SCHOOL'
                row['teacher_id'] = 'T1'
        content = io.StringIO(newline='')
        writer = csv.DictWriter(content, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        imported = self.client.post('/api/datasets/import?dry_run=false', data={'metadata': metadata}, files={
            'results_file': ('results.csv', content.getvalue().encode('utf-8')),
            'curriculum_file': ('curriculum.csv', curriculum),
        })
        self.assertEqual(imported.status_code, 201, imported.text)
        base = f"/api/datasets/{imported.json()['dataset_id']}"
        compared = self.client.get(base + '/comparison', params={
            'topic_id': 'equations', 'textbook_a': 'Учебник A', 'textbook_b': 'Учебник B'})
        self.assertEqual(compared.status_code, 200, compared.text)
        self.assertEqual(compared.json()['group_a']['n_teachers'], 2)
        self.assertEqual(compared.json()['difference_gain_pp'], 8)
        teachers = self.client.get(base + '/teachers').json()['teachers']
        self.assertEqual(len([row for row in teachers if row['teacher_id'] == 'T1']), 2)

    def test_imported_teacher_ids_on_both_stages_describe_book_pairs(self):
        results, curriculum, metadata = demo_files()
        source = list(csv.DictReader(io.StringIO(results.decode("utf-8"))))
        cases = [
            ("known_changed", "T-old", "T-new", 2, 60, False),
            ("known_missing", "T-old", "", 1, 0, False),
            ("missing_known", "", "T-new", 1, 0, False),
            ("both_missing", "", "", 0, 0, False),
            ("stable", "T-same", "T-same", 1, 0, False),
            ("unmatched_extra", "T-same", "T-same", 1, 0, True),
        ]
        for name, pre_teacher, post_teacher, count, differing_pairs, add_unmatched in cases:
            with self.subTest(case=name):
                rows = [dict(row) for row in source]
                for row in rows:
                    if row["textbook_id"] == "Учебник A":
                        row["teacher_id"] = pre_teacher if row["stage"] == "pre" else post_teacher
                if add_unmatched:
                    for stage in ("pre", "post"):
                        template = next(row for row in rows if row["student_id"] == "S001"
                                        and row["topic_id"] == "equations" and row["stage"] == stage)
                        rows.append({**template, "student_id": f"extra-{stage}", "teacher_id": f"T-extra-{stage}"})
                dataset_id = self.import_result_rows(rows, curriculum, metadata)
                response = self.client.get(f"/api/datasets/{dataset_id}/comparison", params={
                    "topic_id": "equations", "textbook_a": "Учебник A", "textbook_b": "Учебник B",
                })
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                self.assertEqual(body["group_a"]["n_teachers"], count)
                self.assertEqual(body["group_a"]["n_pairs"], 60)
                self.assertEqual(body["group_a"]["mean_pre_paired_pct"], 52)
                self.assertEqual(body["group_a"]["mean_post_paired_pct"], 68)
                self.assertEqual(body["group_a"]["mean_gain_pp"], 16)
                self.assertEqual(body["comparison_status"], "comparable")
                self.assertEqual(body["difference_gain_pp"], 8)
                self.assertEqual(body["baseline_gap_pp"], 1)
                notices = [warning for warning in body["warnings"]
                           if warning.startswith("Учебник A:") and "различающимися" in warning]
                self.assertEqual(len(notices), int(differing_pairs > 0))
                if notices:
                    self.assertIn(f"pre/post: {differing_pairs}.", notices[0])

    def test_integrated_factory_does_not_duplicate_analytics_routes(self):
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            schema = self.client.app.openapi()
        duplicates = [str(item.message) for item in captured if "Duplicate Operation ID" in str(item.message)]
        self.assertEqual(duplicates, [])
        for suffix in ("overview", "topics/{topic_id}", "comparison"):
            self.assertIn(f"/api/datasets/{{dataset_id}}/{suffix}", schema["paths"])

    def test_public_demo_hides_uploaded_data_on_every_analytics_route(self):
        private_id = self.import_analytics_demo()
        filters = self.client.get(f"/api/datasets/{private_id}/filters").json()
        topic_id = filters["topics"][0]["topic_id"]
        books = [book["id"] for book in filters["textbooks"]]
        comparison = {"topic_id": topic_id, "textbook_a": books[0], "textbook_b": books[1]}
        with TestClient(create_integrated_app(replace(self.settings, read_only_demo=True))) as public:
            for suffix, params in (("overview", {}), (f"topics/{topic_id}", {}), ("comparison", comparison)):
                with self.subTest(route=suffix):
                    response = public.get(f"/api/datasets/{private_id}/{suffix}", params=params)
                    self.assertEqual(response.status_code, 404, response.text)
                    self.assertEqual(response.json()["code"], "DATASET_NOT_FOUND")
            demo = public.post("/api/datasets/demo")
            # Public requests only retrieve the demo seeded before serving HTTP.
            self.assertEqual(demo.status_code, 200, demo.text)
            self.assertFalse(demo.json()["created"])
            visible = public.get(f"/api/datasets/{demo.json()['dataset_id']}/overview")
            self.assertEqual(visible.status_code, 200, visible.text)
            self.assertTrue(visible.json()["is_demo"])


if __name__ == "__main__":
    unittest.main()
