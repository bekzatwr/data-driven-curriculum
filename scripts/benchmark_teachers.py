"""Reproduce /teachers performance on CSVs at the backend's default row limit.

Run from the repository: python scripts/benchmark_teachers.py --http --repeats 3
Add --baseline-ref <commit> to compare complete summaries with an older version.
Only temporary databases are created; the application's database is never used.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.demo import METADATA, RESULT_FIELDS, TOPIC_FIELDS, _csv
from analytics.teachers import compute_teachers
from backend.app.config import Settings
from backend.app.validation import validate_upload


CASES = ("20_teachers_1_school_paired", "10000_teachers_1_school", "10000_teachers_10000_schools")


def make_upload(name):
    topics = [{"topic_id": f"t{i:03d}", "topic_name": f"Topic {i}", "topic_order": i,
               "current_hours": 1, "min_hours": 0, "max_hours": 2,
               "importance": 1, "is_locked": False} for i in range(100)]
    rows = []
    for i in range(10_000):
        if name == "20_teachers_1_school_paired":
            pupil, topic = i // 20, i // 2 % 10
            stage = "pre" if i % 2 == 0 else "post"
            classroom = f"c{pupil // 25}"
            teacher, school = f"teacher{pupil // 25}", "school0"
        else:
            pupil, topic, stage = i, i % 100, "post"
            classroom, teacher = f"c{i}", f"teacher{i}"
            school = f"school{i}" if name == "10000_teachers_10000_schools" else "school0"
        rows.append({"student_id": f"pupil{pupil}", "school_id": school, "class_id": classroom,
                     "teacher_id": teacher, "textbook_id": "Book A", "topic_id": f"t{topic:03d}",
                     "test_version": "v1", "stage": stage, "score": 40 if stage == "pre" else 70,
                     "max_score": 100, "tested_at": "2026-09-01" if stage == "pre" else "2026-10-01"})
    results_csv, topics_csv = _csv(RESULT_FIELDS, rows), _csv(TOPIC_FIELDS, topics)
    upload = validate_upload(results_csv, topics_csv, json.dumps({
        **METADATA, "name": f"Synthetic teachers benchmark: {name}",
    }), Settings())
    return upload, len(results_csv) + len(topics_csv)


def load_baseline(ref):
    # Execute only this historical pure module, using current shared helpers.
    # No checkout, application mutation, or network access is involved.
    commit = subprocess.run(["git", "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"],
                            cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    source = subprocess.run(["git", "show", f"{commit}:analytics/teachers.py"], cwd=ROOT,
                            check=True, capture_output=True, encoding="utf-8").stdout
    namespace = {"__name__": "analytics._benchmark_baseline", "__package__": "analytics"}
    exec(compile(source, f"{commit}:analytics/teachers.py", "exec"), namespace)
    return namespace["compute_teachers"], commit, hashlib.sha256(source.encode()).hexdigest()


def timed(call, repeats):
    seconds, value = [], None
    for _ in range(repeats):
        start = perf_counter()
        value = call()
        seconds.append(perf_counter() - start)
    return value, seconds


def measure_http(upload, expected, repeats):
    from fastapi.testclient import TestClient
    from backend.app.main import create_app

    with tempfile.TemporaryDirectory(prefix="teachers-benchmark-") as directory:
        with TestClient(create_app(Settings(database_path=Path(directory) / "benchmark.sqlite3"))) as client:
            dataset, _ = client.app.state.store.save_upload(upload)
            response, seconds = timed(lambda: client.get(f"/api/datasets/{dataset['id']}/teachers"), repeats)
            if response.status_code != 200:
                raise AssertionError(f"HTTP {response.status_code}: {response.text[:1000]}")
            payload = response.json()
            if {key: payload[key] for key in expected} != expected:
                raise AssertionError("HTTP summary differs from the complete pure calculation")
            return seconds, len(response.content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--case", choices=CASES, action="append", dest="cases")
    parser.add_argument("--http", action="store_true", help="Also time complete GET responses via TestClient")
    parser.add_argument("--baseline-ref", help="Compare every summary field with this local Git revision (once per case)")
    parser.add_argument("--max-seconds", type=float, help="Fail if a current compute/HTTP median exceeds this budget")
    parser.add_argument("--output", type=Path, help="Write the measurements as JSON")
    args = parser.parse_args()
    if args.repeats < 1 or (args.max_seconds is not None and (
        not math.isfinite(args.max_seconds) or args.max_seconds <= 0
    )):
        parser.error("repeats must be positive and max-seconds must be finite and positive")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
    source = (ROOT / "analytics/teachers.py").read_text(encoding="utf-8")
    report = {"python": platform.python_version(), "platform": platform.platform(),
              "synthetic_data": True, "requested_budget_seconds": args.max_seconds, "passed": None,
              "measurement": {
                  "compute": "Pure compute_teachers call; CSV generation and backend validation are outside the timer",
                  "http": "In-process FastAPI TestClient GET, including SQLite reads, response validation and JSON serialization; no real network",
                  "excluded": "Application startup, SQLite fixture insertion, response.json parsing and temporary database cleanup",
                  "budget": "Median of current compute and optional HTTP repetitions, checked per case; historical baseline excluded",
              },
              "teacher_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
              "limits": {"max_results": Settings.max_results, "max_topics": Settings.max_topics,
                         "max_upload_bytes": Settings.max_upload_bytes}, "cases": []}
    baseline = None
    if args.baseline_ref:
        baseline, commit, source_hash = load_baseline(args.baseline_ref)
        report["baseline"] = {"commit": commit, "teacher_source_sha256": source_hash,
                              "shared_helpers": "current checkout"}
    exceeded = False
    for name in args.cases or CASES:
        print(f"Measuring {name}...", file=sys.stderr, flush=True)
        upload, csv_bytes = make_upload(name)
        result, seconds = timed(lambda: compute_teachers(upload.results, upload.topics), args.repeats)
        case = {"name": name, "records": len(upload.results), "topics": len(upload.topics),
                "teachers": result["total"]["teachers"], "schools": len(result["schools"]),
                "validated_csv_bytes": csv_bytes, "compute_seconds": seconds,
                "compute_median_seconds": statistics.median(seconds)}
        if baseline:
            before, baseline_seconds = timed(lambda: baseline(upload.results, upload.topics), 1)
            if before != result:
                raise AssertionError(f"Complete summary changed for {name}")
            case.update(baseline_compute_seconds=baseline_seconds[0], exact_summary_parity=True)
        medians = [case["compute_median_seconds"]]
        if args.http:
            http_seconds, response_bytes = measure_http(upload, result, args.repeats)
            case.update(http_seconds=http_seconds, http_median_seconds=statistics.median(http_seconds),
                        response_bytes=response_bytes)
            medians.append(case["http_median_seconds"])
        exceeded = exceeded or (args.max_seconds is not None and max(medians) > args.max_seconds)
        report["cases"].append(case)
        if args.output:
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(case), flush=True)
    report["passed"] = not exceeded
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if exceeded:
        print(f"A median exceeded the {args.max_seconds:g}s budget", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
