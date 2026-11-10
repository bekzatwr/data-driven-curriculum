"""Execute historical TypeScript and current Python on the same artificial data.

Requires local Git history containing the frontend commit and Node.js 24+.
No fetch, npm installation, network client, or cached result is used. The original
TypeScript bytes run unchanged; LF normalization is used only for source hashes.

python scripts/verify_teachers_parity.py --node /path/to/node --output parity.json
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from math import isclose, isfinite
from pathlib import Path
import platform
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.demo import demo_records
from analytics.teachers import compute_teachers


DEFAULT_FRONTEND_REF = "03395ef5db68ac9fab379f622ddf6fbe09112327"
FRONTEND_PATH = "web/src/lib/teachers.ts"
EPSILON = 1e-10
TEACHER_FIELDS = (
    "teacher_id", "school_id", "class_ids", "students", "textbooks", "n_post",
    "mean_post_pct", "n_pairs", "mean_gain_pp", "upcoming_hours",
)
SCHOOL_FIELDS = (
    "school_id", "teachers", "students", "classes", "students_per_teacher",
    "classes_per_teacher", "hours_per_teacher",
)
SUMMARY_FIELDS = ("teachers", "schools", "total", "hours_per_class", "missing_teacher_rows")

# Only the invocation/serialization wrapper is ours. computeTeachers is imported
# directly from the unchanged source returned by git show.
NODE_RUNNER = """import { readFileSync, writeFileSync } from 'node:fs';
import { computeTeachers } from './teachers.ts';
const input = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const result = computeTeachers(input.rows, input.topics);
writeFileSync(process.argv[3], JSON.stringify({ runtime: process.version, result }), 'utf8');
"""


class ParityError(RuntimeError):
    """An unavailable prerequisite or an invalid result prevented comparison."""


def source_sha256(data):
    """Stable source hash across checkouts: CRLF and bare CR become LF."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def _run(command, *, cwd, operation):
    try:
        result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=30, check=False, shell=False)
    except FileNotFoundError as exc:
        raise ParityError(f"{operation}: executable not found: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ParityError(f"{operation}: exceeded the 30-second timeout") from exc
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()[:2000]
        raise ParityError(f"{operation}: exit {result.returncode}. {detail}")
    return result.stdout


def _fields(value, fields, location):
    if not isinstance(value, dict):
        raise ParityError(f"{location}: expected an object")
    for field in fields:
        if field not in value:
            raise ParityError(f"{location}.{field}: required legacy field is missing")
    return {field: value[field] for field in fields}


def legacy_projection(summary, label):
    """Preserve every legacy value; ignore additive backend fields deliberately."""
    result = _fields(summary, SUMMARY_FIELDS, label)
    for field in ("teachers", "schools"):
        if not isinstance(result[field], list):
            raise ParityError(f"{label}.{field}: expected an array")
    teachers = [_fields(item, TEACHER_FIELDS, f"{label}.teachers[{index}]")
                for index, item in enumerate(result["teachers"])]
    for index, teacher in enumerate(teachers):
        for field in ("class_ids", "textbooks"):
            values = teacher[field]
            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                raise ParityError(f"{label}.teachers[{index}].{field}: expected an array of strings")
            teacher[field] = sorted(values)  # Sorting only; duplicates remain visible.
    schools = [_fields(item, SCHOOL_FIELDS, f"{label}.schools[{index}]")
               for index, item in enumerate(result["schools"])]
    for index, teacher in enumerate(teachers):
        if not isinstance(teacher["school_id"], str) or not isinstance(teacher["teacher_id"], str):
            raise ParityError(f"{label}.teachers[{index}]: expected string school_id and teacher_id")
    if any(not isinstance(school["school_id"], str) for school in schools):
        raise ParityError(f"{label}.schools: expected string school_id")
    return {
        "teachers": sorted(teachers, key=lambda item: (item["school_id"], item["teacher_id"])),
        "schools": sorted(schools, key=lambda item: item["school_id"]),
        "total": _fields(result["total"], SCHOOL_FIELDS, f"{label}.total"),
        "hours_per_class": result["hours_per_class"],
        "missing_teacher_rows": result["missing_teacher_rows"],
    }


def compare_legacy(ui, backend):
    """Deterministic paths and strict missing/zero/type handling, with float tolerance."""
    differences, numeric_deltas = [], []
    fields_checked = 0

    def display(value):
        return str(value) if type(value) is float and not isfinite(value) else value

    def visit(left, right, path=""):
        nonlocal fields_checked
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(left.keys() | right.keys()):
                child = f"{path}.{key}" if path else key
                if key not in left or key not in right:
                    differences.append({"path": child, "reason": "Missing field in " + ("UI" if key not in left else "backend")})
                else:
                    visit(left[key], right[key], child)
        elif isinstance(left, list) and isinstance(right, list):
            if len(left) != len(right):
                differences.append({"path": path, "reason": "Different array length",
                                    "ui_length": len(left), "backend_length": len(right)})
            for index, (a, b) in enumerate(zip(left, right)):
                visit(a, b, f"{path}[{index}]")
        else:
            fields_checked += 1
            numeric = type(left) in (int, float) and type(right) in (int, float)
            finite = numeric and isfinite(left) and isfinite(right)
            if finite:
                numeric_deltas.append(abs(left - right))
            equal = (isclose(left, right, rel_tol=0, abs_tol=EPSILON) if finite
                     else type(left) is type(right) and left == right and not numeric)
            if not equal:
                differences.append({"path": path, "ui": display(left), "backend": display(right)})

    visit(ui, backend)
    return {
        "absolute_tolerance": EPSILON,
        "relative_tolerance": 0,
        "ordering": "Teachers sorted by school_id/teacher_id; schools by school_id; class_ids and textbooks sorted. No deduplication.",
        "teacher_fields": list(TEACHER_FIELDS),
        "school_fields": list(SCHOOL_FIELDS),
        "leaf_values_checked": fields_checked,
        "maximum_absolute_numeric_difference": max(numeric_deltas, default=0),
        "differences": differences,
    }


def verify(frontend_ref=DEFAULT_FRONTEND_REF, node="node"):
    """Run both actual implementations and return their complete parity evidence."""
    # Explicit relative paths retain their meaning after the child cwd becomes
    # the temporary directory. A bare executable name still resolves via PATH.
    if "/" in node or "\\" in node:
        node = str(Path(node).expanduser().resolve())
    commit = _run(["git", "rev-parse", "--verify", "--end-of-options", f"{frontend_ref}^{{commit}}"],
                  cwd=ROOT, operation=f"Resolve local frontend commit {frontend_ref!r} (the script does not fetch history)").decode().strip()
    source = _run(["git", "show", f"{commit}:{FRONTEND_PATH}"], cwd=ROOT,
                  operation=f"Read {FRONTEND_PATH} from local commit {commit}")
    node_version = _run([node, "--version"], cwd=ROOT, operation="Check Node.js version").decode().strip()
    match = re.fullmatch(r"v(\d+)\.\d+\.\d+(?:[-+].*)?", node_version)
    if not match or int(match.group(1)) < 24:
        raise ParityError(f"Node.js 24 or newer is required for native TypeScript execution; got {node_version!r}")
    topics, rows = demo_records()
    input_bytes = json.dumps({"rows": rows, "topics": topics}, sort_keys=True,
                             ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    with TemporaryDirectory(prefix="ddc-teachers-parity-") as temporary:
        directory = Path(temporary)
        (directory / "teachers.ts").write_bytes(source)
        (directory / "package.json").write_text('{"type":"module"}\n', encoding="utf-8")
        (directory / "run-original.mjs").write_text(NODE_RUNNER, encoding="utf-8", newline="\n")
        (directory / "input.json").write_bytes(input_bytes)
        _run([node, "--experimental-strip-types", str(directory / "run-original.mjs"),
              str(directory / "input.json"), str(directory / "node-result.json")],
             cwd=directory, operation="Execute original frontend TypeScript")
        try:
            node_result = json.loads((directory / "node-result.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ParityError("Original TypeScript did not produce a valid JSON result") from exc
    if not isinstance(node_result, dict) or "result" not in node_result or "runtime" not in node_result:
        raise ParityError("Original TypeScript result is missing runtime or result")
    python_result = compute_teachers(rows, topics)
    ui = legacy_projection(node_result["result"], "UI")
    backend = legacy_projection(python_result, "backend")
    comparison = compare_legacy(ui, backend)
    teacher_extras = {field for teacher in python_result["teachers"] for field in teacher if field not in TEACHER_FIELDS}
    excluded_fields = sorted([field for field in python_result if field not in SUMMARY_FIELDS]
                             + [f"teachers[].{field}" for field in teacher_extras])
    return {
        "check": "Original frontend TypeScript computeTeachers versus Python compute_teachers on the canonical synthetic demo",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "passed": not comparison["differences"],
        "source": {
            "repository": "https://github.com/bekzatwr/data-driven-curriculum",
            "frontend_commit": commit,
            "frontend_path": FRONTEND_PATH,
            "frontend_sha256": source_sha256(source),
            "frontend_raw_sha256": hashlib.sha256(source).hexdigest(),
            "frontend_execution": "Unchanged git-show bytes executed by Node with --experimental-strip-types; no translated substitute or cached output",
            "backend_path": "analytics/teachers.py",
            "backend_sha256": source_sha256((ROOT / "analytics/teachers.py").read_bytes()),
            "fixture": "analytics.demo.demo_records()",
            "fixture_sha256": source_sha256((ROOT / "analytics/demo.py").read_bytes()),
            "hash_normalization": "Source hashes replace CRLF and bare CR with LF before SHA-256; executed TypeScript bytes are not normalized. frontend_raw_sha256 hashes the exact executed bytes.",
            "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
            "input_encoding": "UTF-8 canonical JSON: sorted keys, compact separators, no ASCII escaping; the same data is passed to both implementations.",
            "synthetic_data": True,
        },
        "runtime": {"node": node_result["runtime"], "python": platform.python_version(), "platform": platform.platform()},
        "comparison": comparison,
        "verified_counts": {
            "input_results": len(rows), "topics": len(topics),
            "teachers": backend["total"]["teachers"], "students": backend["total"]["students"],
            "classes": backend["total"]["classes"],
            "students_per_teacher": backend["total"]["students_per_teacher"],
            "hours_per_teacher": backend["total"]["hours_per_teacher"],
            "hours_per_class": backend["hours_per_class"],
            "post_results_per_teacher": [teacher["n_post"] for teacher in backend["teachers"]],
            "pairs_per_teacher": [teacher["n_pairs"] for teacher in backend["teachers"]],
        },
        "original_ui_result": ui,
        "backend_legacy_fields": backend,
        "additional_backend_fields_excluded_from_legacy_comparison": excluded_fields,
        "intentional_differences_outside_this_demo_parity_check": [
            {"case": "The same teacher_id in several schools",
             "backend_behavior": "Teacher identity is scoped by school.", "executed_in_this_report": False},
            {"case": "Missing teacher and a real ID equal to the display label Не указан",
             "backend_behavior": "Missing identity is distinct from a label-valued known identity.", "executed_in_this_report": False},
            {"case": "Mixed versions/scales or incompatible pre/post records",
             "backend_behavior": "Shared compatibility rules suppress mixed-topic means and exclude incompatible pairs.", "executed_in_this_report": False},
            {"case": "Duplicate student/topic/stage records",
             "backend_behavior": "Duplicates are rejected, not overwritten or counted twice.", "executed_in_this_report": False},
        ],
        "limitations": "Only the canonical synthetic demo is executed on both implementations. Edge cases listed separately are documented differences, not fabricated cross-runtime results. This verifies calculations, not teacher quality or causal effects.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-ref", default=DEFAULT_FRONTEND_REF,
                        help="Frontend commit/ref already present in local Git history")
    parser.add_argument("--node", default="node", help="Node.js 24+ executable name or path")
    parser.add_argument("--output", type=Path, help="Optional UTF-8 JSON report path")
    args = parser.parse_args(argv)
    try:
        report = verify(args.frontend_ref, args.node)
        encoded = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
            print(json.dumps({"passed": report["passed"], "output": str(args.output),
                              "leaf_values_checked": report["comparison"]["leaf_values_checked"],
                              "maximum_absolute_numeric_difference": report["comparison"]["maximum_absolute_numeric_difference"]}))
        else:
            print(encoded, end="")
        return 0 if report["passed"] else 1
    except (ParityError, OSError, ValueError) as exc:
        print(f"Teacher parity verification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
