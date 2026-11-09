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
            results, curriculum, metadata = demo_files()
            rows = list(csv.DictReader(io.StringIO(results.decode("utf-8"))))
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
