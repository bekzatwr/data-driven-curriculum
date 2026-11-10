"""Regenerate machine contracts and examples from real app responses; requires dev dependencies."""
import csv
import io
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
from backend.app.config import Settings
from backend.app.demo import csv_bytes, demo_files
from backend.app.main import create_app
from backend.app.review_inputs import PlanReviewInput
from backend.app.schemas import DatasetPackage
from backend.app.validation import RESULT_FIELDS


def main():
    directory = ROOT / "contracts"
    directory.mkdir(exist_ok=True)

    def write(name, content):
        (directory / name).write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with tempfile.TemporaryDirectory() as temp:
        app = create_app(Settings(database_path=Path(temp) / "contracts.sqlite3"))
        write("openapi.json", app.openapi())
        write("plan-review-input.schema.json", PlanReviewInput.model_json_schema())
        write("dataset-package.schema.json", DatasetPackage.model_json_schema())
        with TestClient(app) as client:
            response = client.post("/api/datasets/demo")
            assert response.status_code == 201
            body = response.json()
            dataset_id = body["dataset_id"]
            timestamp = body["dataset"]["created_at"]

            def example(name, content):
                text = json.dumps(content, ensure_ascii=False).replace(dataset_id, "__DATASET_ID__").replace(timestamp, "__CREATED_AT__")
                write(name, json.loads(text))

            example("demo-import.response.json", body)
            example("filters.response.json", client.get(f"/api/datasets/{dataset_id}/filters").json())
            example("results-page.response.json", client.get(f"/api/datasets/{dataset_id}/results?limit=3").json())
            example("quality.response.json", client.get(f"/api/datasets/{dataset_id}/quality").json())
            for name, path, params in (
                ('integrated-analytics-overview.response.json', '/overview', {}),
                ('integrated-analytics-topic.response.json', '/topics/equations', {}),
                ('integrated-analytics-comparison.response.json', '/comparison', {
                    'topic_id': 'equations', 'textbook_a': 'Учебник A', 'textbook_b': 'Учебник B'}),
            ):
                analytics_response = client.get(f'/api/datasets/{dataset_id}' + path, params=params)
                assert analytics_response.status_code == 200, analytics_response.text
                example(name, analytics_response.json())
            plan_path = f"/api/datasets/{dataset_id}/plans"
            plan_preview = client.post(plan_path + "/preview", json={"class_id": "7A"})
            assert plan_preview.status_code == 200, plan_preview.text
            example("integrated-plan-preview.response.json", plan_preview.json())
            saved_response = client.post(plan_path, json={"class_id": "7A"})
            assert saved_response.status_code == 201, saved_response.text
            saved = saved_response.json()
            saved_id = saved["plan_id"]
            csv_report = client.get(f"/api/plans/{saved_id}/export.csv")
            assert csv_report.status_code == 200
            saved_text = json.dumps(saved, ensure_ascii=False).replace(saved_id, "__PLAN_ID__").replace(saved["created_at"], "__PLAN_CREATED_AT__")
            example("integrated-plan-saved.response.json", json.loads(saved_text))
            comment_response = client.post(f"/api/datasets/{dataset_id}/comments", json={
                "target_type": "plan_topic", "target_id": saved_id + ":fractions",
                "author_name": "Synthetic reviewer", "author_role": "methodist", "text": "Review the synthetic plan"})
            assert comment_response.status_code == 201, comment_response.text
            comment = comment_response.json()
            comment_text = json.dumps(comment, ensure_ascii=False).replace(saved_id, "__PLAN_ID__").replace(comment["id"], "__COMMENT_ID__").replace(comment["created_at"], "__COMMENT_CREATED_AT__")
            example("comment.response.json", json.loads(comment_text))
            write("ai-status-offline.response.json", {"configured": False, "providers": [], "models": {}})
            write("capabilities.response.json", client.get("/api/capabilities").json())
            results, curriculum, metadata = demo_files()
            rows = list(csv.DictReader(io.StringIO(results.decode("utf-8"))))
            small = client.post("/api/datasets/import?dry_run=false", data={"metadata": metadata}, files={
                "results_file": ("results.csv", csv_bytes(RESULT_FIELDS, rows[:2])),
                "curriculum_file": ("curriculum.csv", curriculum),
            })
            assert small.status_code == 201
            small_id = small.json()["dataset_id"]
            write("dataset-package.example.json", client.get(f"/api/datasets/{small_id}/package").json())
            rows[0]["score"] = "101"
            invalid = client.post("/api/datasets/import?dry_run=true", data={"metadata": metadata}, files={
                "results_file": ("results.csv", csv_bytes(RESULT_FIELDS, rows)),
                "curriculum_file": ("curriculum.csv", curriculum),
            })
            assert invalid.status_code == 422
            write("import-error.response.json", invalid.json())
            for name in ("results", "curriculum"):
                (directory / f"{name}.template.csv").write_bytes(client.get(f"/api/templates/{name}.csv").content)
    print(f"Contracts exported to {directory}")


if __name__ == "__main__":
    main()
