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
            self.assertEqual(demo.status_code, 201, demo.text)
            visible = public.get(f"/api/datasets/{demo.json()['dataset_id']}/overview")
            self.assertEqual(visible.status_code, 200, visible.text)
            self.assertTrue(visible.json()["is_demo"])


if __name__ == "__main__":
    unittest.main()
