"""Three cold-database HTTP runs of import, overview and plan at the 10k limit.

Run from any directory with the project's installed requirements:
    python scripts/benchmark_pipeline.py --output benchmark.json
Timing covers each complete TestClient request, including response serialization.
It excludes input generation and application startup, and is a local measurement,
not a promise about production or network latency. All records are artificial.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from math import isclose
from pathlib import Path
import platform
from statistics import mean
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from analytics.demo import METADATA, RESULT_FIELDS, TOPIC_FIELDS, _csv, demo_records
from backend.app.config import Settings
from backend.app.main import create_app


LIMITS_SECONDS = {"import": 10.0, "overview": 2.0, "plan_preview": 2.0}


def benchmark_input():
    """Seven copies with disjoint pupils, trimmed at a complete pre/post pair."""
    topics, original = demo_records()
    records = [
        {**row, "student_id": f"copy{copy + 1}-{row['student_id']}"}
        for copy in range(7) for row in original
    ][:10_000]
    if len(records) != 10_000:
        raise RuntimeError("The demo fixture no longer expands to 10,000 records.")
    metadata = {**METADATA, "name": "Искусственный benchmark Тони: 10 000 результатов"}
    files = {
        "results_file": ("results.csv", _csv(RESULT_FIELDS, records), "text/csv"),
        "curriculum_file": ("curriculum.csv", _csv(TOPIC_FIELDS, topics), "text/csv"),
    }
    return topics, records, files, json.dumps(metadata, ensure_ascii=False)


def check(condition, message):
    # Do not use assert: verification must also run when Python has -O enabled.
    if not condition:
        raise RuntimeError(message)


def payload(response, status, label):
    check(response.status_code == status,
          f"{label}: expected HTTP {status}, got {response.status_code}: {response.text[:2000]}")
    return response.json()


def expected_metrics(records, topics):
    by_student = defaultdict(list)
    covered = defaultdict(set)
    by_topic = defaultdict(list)
    for row in records:
        if row["stage"] == "post":
            score = 100 * row["score"] / row["max_score"]
            by_student[row["student_id"]].append(score)
            covered[row["student_id"]].add(row["topic_id"])
            by_topic[row["topic_id"]].append(score)
    return {
        "n_students": len({row["student_id"] for row in records}),
        "n_post_students": len(by_student),
        "n_post_results": sum(len(values) for values in by_student.values()),
        "n_complete_students": sum(len(ids) == len(topics) for ids in covered.values()),
        "mean_post_pct": mean(mean(values) for values in by_student.values()),
        "topic_means": {tid: mean(values) for tid, values in by_topic.items()},
        "topic_counts": {tid: len(values) for tid, values in by_topic.items()},
    }


def run_once(run_number, topics, records, files, metadata, expected):
    # Every repetition creates a new SQLite database: no duplicate-import shortcut.
    with TemporaryDirectory(prefix="ddc-benchmark-") as directory:
        settings = Settings(database_path=Path(directory) / "benchmark.sqlite3", read_only_demo=False)
        with TestClient(create_app(settings)) as client:
            started = perf_counter()
            response = client.post("/api/datasets/import?dry_run=false", files=files,
                                   data={"metadata": metadata})
            import_seconds = perf_counter() - started
            imported = payload(response, 201, "import")
            check(imported["created"] is True, "Import must create a new dataset.")
            check(imported["counts"]["results"] == 10_000, "Import lost results.")
            check(imported["counts"]["students"] == expected["n_students"], "Import student count differs.")
            check(imported["counts"]["classes"] == 4 and imported["counts"]["topics"] == 6,
                  "Expected four classes and six curriculum topics.")
            dataset_id = imported["dataset_id"]

            started = perf_counter()
            response = client.get(f"/api/datasets/{dataset_id}/overview")
            overview_seconds = perf_counter() - started
            overview = payload(response, 200, "overview")
            check(overview["dataset_id"] == dataset_id, "Overview returned a different dataset.")
            metrics = overview["metrics"]
            for field in ("n_students", "n_post_students", "n_post_results", "n_complete_students"):
                check(metrics[field] == expected[field], f"Overview {field} differs from the input.")
            check(metrics["n_pairs"] == 5000 and metrics["pair_coverage"] == 1,
                  "Overview must retain all 5,000 complete pairs.")
            check(isclose(metrics["mean_post_pct"], expected["mean_post_pct"], rel_tol=0, abs_tol=1e-10),
                  "Overview mean is not weighted equally by student.")
            check(len(overview["topics"]) == 6 and len(overview["heatmap"]) == 24,
                  "Overview is missing topics or class/topic cells.")
            for topic in overview["topics"]:
                tid = topic["topic_id"]
                check(topic["n_post"] == expected["topic_counts"][tid], f"Topic {tid} lost post results.")
                check(isclose(topic["mean_post_pct"], expected["topic_means"][tid], rel_tol=0, abs_tol=1e-10),
                      f"Topic {tid} mean differs from the input.")

            started = perf_counter()
            response = client.post(f"/api/datasets/{dataset_id}/plans/preview", json={"class_id": "7A"})
            plan_seconds = perf_counter() - started
            plan = payload(response, 200, "plan_preview")
            check(plan["dataset_id"] == dataset_id and plan["class_id"] == "7A",
                  "Plan returned a different dataset or class.")
            total = sum(topic["current_hours"] for topic in topics)
            check(plan["total_hours"] == total == 24, "Plan changed the total budget.")
            check(sum(item["proposed_hours"] for item in plan["items"]) == total,
                  "Proposed hours do not preserve the budget.")
            check({item["topic_id"] for item in plan["items"]} == {topic["topic_id"] for topic in topics},
                  "Plan is missing curriculum topics.")
            check(bool(plan["transfers"]), "Expected a nontrivial plan with donors and recipients.")
            for item in plan["items"]:
                hours = item["proposed_hours"]
                check(type(hours) is int and item["min_hours"] <= hours <= item["max_hours"],
                      "Plan violates integer hours or bounds.")
                check(abs(hours - item["current_hours"]) <= 2, "Plan violates the ±2 hour limit.")
                check(not item["is_locked"] or hours == item["current_hours"], "Plan changed a locked topic.")
                check(item["n_post"] == 210, "Plan did not use all 210 pupils of class 7A.")
            seconds = {"import": import_seconds, "overview": overview_seconds, "plan_preview": plan_seconds}
            return {
                "run": run_number,
                "fresh_database": True,
                "seconds": seconds,
                "passed": all(seconds[name] < limit for name, limit in LIMITS_SECONDS.items()),
                "verified": {"results": 10_000, "students": expected["n_students"], "pairs": 5000,
                             "topics": 6, "heatmap_cells": 24, "plan_students_per_topic": 210,
                             "total_hours": total},
            }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional UTF-8 JSON report path")
    args = parser.parse_args()
    topics, records, files, metadata = benchmark_input()
    expected = expected_metrics(records, topics)
    runs = [run_once(number, topics, records, files, metadata, expected) for number in range(1, 4)]
    report = {
        "benchmark": "integrated_http_pipeline_10000_records",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "synthetic_data": True,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "measurement": "Local TestClient HTTP requests; includes validation, SQLite operations and JSON serialization; excludes app startup and CSV generation.",
        "limits_seconds": LIMITS_SECONDS,
        "runs": runs,
        "maximum_seconds": {name: max(run["seconds"][name] for run in runs) for name in LIMITS_SECONDS},
        "passed": all(run["passed"] for run in runs),
    }
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
