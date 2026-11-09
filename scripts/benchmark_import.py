"""Measure a full validated 10,000-row HTTP import against a temporary SQLite database."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
from backend.app.config import Settings
from backend.app.demo import METADATA, csv_bytes
from backend.app.main import create_app
from backend.app.validation import RESULT_FIELDS, TOPIC_FIELDS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-seconds", type=float, default=10)
    args = parser.parse_args()
    rows = []
    for student in range(5000):
        for stage, score, day in (("pre", 4, "2026-09-01"), ("post", 7, "2026-10-01")):
            rows.append(dict(zip(RESULT_FIELDS, [f"S{student:05}", "DEMO", f"C{student // 30}", "T1", "BookA",
                                                "t1", "v1", stage, score, 10, day])))
    topics = [dict(zip(TOPIC_FIELDS, ["t1", "Synthetic topic", 1, 5, 2, 8, 3, "false"]))]
    files = {"results_file": ("results.csv", csv_bytes(RESULT_FIELDS, rows)),
             "curriculum_file": ("curriculum.csv", csv_bytes(TOPIC_FIELDS, topics))}
    with tempfile.TemporaryDirectory() as directory:
        with TestClient(create_app(Settings(database_path=Path(directory) / "benchmark.sqlite3"))) as client:
            started = time.perf_counter()
            response = client.post("/api/datasets/import?dry_run=false", files=files,
                                   data={"metadata": json.dumps(METADATA)})
            elapsed = time.perf_counter() - started
            assert response.status_code == 201, response.text
            assert response.json()["counts"]["results"] == 10_000
            print(json.dumps({"rows": 10_000, "seconds": round(elapsed, 3), "limit_seconds": args.max_seconds,
                              "passed": elapsed < args.max_seconds}))
            if elapsed >= args.max_seconds:
                raise SystemExit(1)


if __name__ == "__main__":
    main()
