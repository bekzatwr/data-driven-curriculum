"""Local-only Docker rehearsal with synthetic data and an explicitly fake UI build probe.

Run with the project's Python environment. Never publishes a port outside loopback,
never reads existing databases, and removes only containers/volumes created by this run.
The probe checks packaging/SPA delivery, NOT Damir's frontend. Real HTTP checks
exercise the integrated analytics, comparison and planner against synthetic CSVs.
"""
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.demo import demo_files


def main():
    run_id = "ddc-check-" + uuid4().hex[:10]
    artifacts = ROOT / "data" / "deployment-checks" / run_id
    artifacts.mkdir(parents=True)
    transcript = artifacts / "docker.log"
    containers, volumes = [], []
    backend_image, web_image = run_id + ":backend", run_id + ":web-probe"
    checks = []

    def command(*args, ok=True, timeout=600):
        print("$ " + " ".join(str(a) for a in args), flush=True)
        result = subprocess.run([str(a) for a in args], cwd=ROOT, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=timeout)
        with transcript.open("a", encoding="utf-8") as log:
            log.write("\n$ " + " ".join(str(a) for a in args) + "\n" + result.stdout + result.stderr)
        if ok and result.returncode:
            raise RuntimeError(result.stderr[-3000:] or result.stdout[-3000:])
        return result

    def volume(suffix):
        name = run_id + suffix
        command("docker", "volume", "create", name)
        volumes.append(name)
        return name

    def create(name, storage, database="/app/data/curriculum.sqlite3"):
        command("docker", "create", "--name", name, "-p", "127.0.0.1::8765",
                "--security-opt", "no-new-privileges:true", "--cap-drop", "ALL",
                "-e", "PORT=8765", "-e", "READ_ONLY_DEMO=false",
                "-e", "DATABASE_PATH=" + database, "-e", "REQUIRE_PERSISTENT_STORAGE=true",
                "-e", "CORS_ORIGINS=https://frontend.test", "-v", storage + ":/app/data", web_image)
        containers.append(name)

    def start(name):
        command("docker", "start", name)
        address = command("docker", "port", name, "8765/tcp").stdout.strip()
        base = "http://" + address
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                status, body, _ = http(base, "/api/health")
                if status == 200 and body["database"] == "ok":
                    return base
            except (URLError, TimeoutError, OSError):
                pass
            time.sleep(0.5)
        command("docker", "logs", name)
        raise RuntimeError("Container failed to become healthy")

    def http(base, path, method="GET", payload=None, headers=None, raw=False):
        headers = dict(headers or {})
        if isinstance(payload, dict):
            payload = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        try:
            response = urlopen(Request(base + path, data=payload, method=method, headers=headers), timeout=15)
        except HTTPError as error:
            response = error
        with response:
            data = response.read()
            return response.status, data if raw else json.loads(data), response.headers

    def persisted(base, dataset_id, plan, expected_csv, analytics):
        assert http(base, "/api/datasets/" + dataset_id)[0] == 200
        assert http(base, "/api/plans/" + plan["plan_id"])[1] == plan
        assert http(base, "/api/plans/" + plan["plan_id"] + "/export.csv", raw=True)[1] == expected_csv
        for path, expected in analytics.items():
            status, actual, _ = http(base, path)
            assert status == 200 and actual == expected

    try:
        command("docker", "info", "--format", "{{.ServerVersion}}", timeout=30)
        command("docker", "compose", "-f", "deploy/compose.yaml", "config", "--quiet")
        command("docker", "build", "--build-arg", "APP_TARGET=backend", "-t", backend_image, ".")
        # A disposable build context avoids writing anything into Damir's source directory.
        context = artifacts / "context"
        context.mkdir()
        for directory in ("backend", "planner", "analytics", "deploy"):
            shutil.copytree(ROOT / directory, context / directory,
                            ignore=shutil.ignore_patterns("__pycache__", "tests", ".env", "test-logs"))
        for filename in ("Dockerfile", ".dockerignore", "requirements.txt"):
            shutil.copy2(ROOT / filename, context / filename)
        frontend = context / "_probe_frontend"
        frontend.mkdir()
        package = {"name": "ddc-packaging-probe", "version": "0.0.0", "private": True,
                   "scripts": {"build": "node build.cjs"}}
        (frontend / "package.json").write_text(json.dumps(package), encoding="utf-8")
        (frontend / "package-lock.json").write_text(json.dumps({"name": package["name"], "version": "0.0.0",
            "lockfileVersion": 3, "requires": True, "packages": {"": {"name": package["name"], "version": "0.0.0"}}}), encoding="utf-8")
        (frontend / "build.cjs").write_text(
            "const fs=require('node:fs');fs.mkdirSync('dist/assets',{recursive:true});"
            "fs.writeFileSync('dist/index.html','<!doctype html><title>PACKAGING PROBE ONLY</title>');"
            "fs.writeFileSync('dist/assets/probe.js','/* synthetic packaging probe */');", encoding="utf-8")
        command("docker", "build", "--build-arg", "APP_TARGET=fullstack", "--build-arg",
                "FRONTEND_DIR=_probe_frontend", "-t", web_image, context)
        checks.append("backend and fullstack Docker builds (synthetic UI packaging probe)")
        refused = command("docker", "run", "--rm", "-e", "REQUIRE_PERSISTENT_STORAGE=true", backend_image, ok=False)
        assert refused.returncode != 0 and "refusing ephemeral storage" in refused.stderr
        checks.append("startup refuses missing persistent mount")
        storage = volume("-data")
        refused = command("docker", "run", "--rm", "-e", "REQUIRE_P0=true", "-v", storage + ":/app/data", backend_image, ok=False)
        assert refused.returncode != 0 and "frontend is missing" in refused.stderr
        checks.append("release startup refuses missing frontend")
        gate = command("docker", "run", "--rm", "-e", "REQUIRE_P0=true", "-v", storage + ":/app/data",
                       web_image, "python", "-c", "from deploy.run_server import preflight; preflight()", ok=False)
        assert gate.returncode == 0, gate.stderr
        checks.append("release preflight found all integrated analytics routes")
        name = run_id + "-app"
        create(name, storage)
        base = start(name)
        assert command("docker", "exec", name, "id", "-u").stdout.strip() != "0"
        for path in ("/", "/reports/example"):
            status, html, _ = http(base, path, raw=True)
            assert status == 200 and b"PACKAGING PROBE ONLY" in html
        assert http(base, "/assets/probe.js", raw=True)[0] == 200
        assert http(base, "/assets/missing.js")[0] == 404
        assert http(base, "/api/unknown")[0] == 404
        assert http(base, "/openapi.json")[0] == 200
        headers = {"Origin": "https://frontend.test", "Access-Control-Request-Method": "POST",
                   "Access-Control-Request-Headers": "content-type"}
        assert http(base, "/api/datasets/import", "OPTIONS", headers=headers, raw=True)[2]["Access-Control-Allow-Origin"] == headers["Origin"]
        headers["Origin"] = "https://unapproved.test"
        assert "Access-Control-Allow-Origin" not in http(base, "/api/datasets/import", "OPTIONS", headers=headers, raw=True)[2]
        checks.append("non-root runtime, dynamic PORT, SPA/assets/API routing, CORS allow/deny")
        release = command(sys.executable, "scripts/check_release.py", "--base-url", base, ok=False)
        assert release.returncode == 2 and "real frontend build" in release.stdout
        checks.append("read-only release check rejects the synthetic frontend probe")
        results, curriculum, metadata = demo_files()
        boundary = "ddc-" + uuid4().hex
        body = bytearray()
        for field, filename, content in (("metadata", None, metadata.encode()),
                ("results_file", "results.csv", results), ("curriculum_file", "curriculum.csv", curriculum)):
            body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"".encode())
            if filename:
                body.extend(f"; filename=\"{filename}\"\r\nContent-Type: text/csv".encode())
            body.extend(b"\r\n\r\n" + content + b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode())
        headers = {"Content-Type": "multipart/form-data; boundary=" + boundary}
        assert http(base, "/api/datasets/import?dry_run=true", "POST", bytes(body), headers)[0] == 200
        status, imported, _ = http(base, "/api/datasets/import?dry_run=false", "POST", bytes(body), headers)
        assert status == 201 and imported["counts"]["results"] == 1440
        dataset_id = imported["dataset_id"]
        assert http(base, "/api/datasets/import?dry_run=false", "POST", bytes(body), headers)[1]["dataset_id"] == dataset_id
        assert http(base, f"/api/datasets/{dataset_id}/filters")[0] == 200
        dataset_path = f"/api/datasets/{dataset_id}"
        comparison_query = urlencode({'topic_id': 'equations', 'textbook_a': 'Учебник A', 'textbook_b': 'Учебник B'})
        analytics = {}
        for suffix in ('/overview', '/topics/equations', '/comparison?' + comparison_query,
                       '/overview?class_ids=7A&class_ids=7B'):
            status, response, _ = http(base, dataset_path + suffix)
            assert status == 200 and response['is_demo'] is False
            analytics[dataset_path + suffix] = response
        overview = analytics[dataset_path + '/overview']
        comparison = analytics[dataset_path + '/comparison?' + comparison_query]
        assert overview['metrics']['n_students'] == 120
        assert overview['metrics']['n_post_results'] == 720
        assert overview['metrics']['n_pairs'] == 720 and len(overview['heatmap']) == 24
        assert analytics[dataset_path + '/topics/equations']['metrics']['n_pairs'] == 120
        assert analytics[dataset_path + '/overview?class_ids=7A&class_ids=7B']['metrics']['n_students'] == 60
        assert comparison['comparison_status'] == 'comparable'
        assert comparison['group_a']['mean_gain_pp'] == 16
        assert comparison['group_b']['mean_gain_pp'] == 8
        assert comparison['difference_gain_pp'] == 8 and comparison['baseline_gap_pp'] == 1
        checks.append("real HTTP topic analytics, heatmap, repeated class filters and paired textbook comparison")
        status, preview, _ = http(base, f"/api/datasets/{dataset_id}/plans/preview", "POST", {"class_id": "7A"})
        assert status == 200 and preview["total_hours"] == 24
        hours = {item["topic_id"]: item["proposed_hours"] for item in preview["items"]}
        status, plan, _ = http(base, f"/api/datasets/{dataset_id}/plans", "POST",
                               {"class_id": "7A", "hours_by_topic": hours, "comment": "Synthetic Docker rehearsal"})
        assert status == 201
        status, exported, _ = http(base, "/api/plans/" + plan["plan_id"] + "/export.csv", raw=True)
        assert status == 200 and exported.startswith(b"\xef\xbb\xbf")
        csv_rows = csv.DictReader(io.StringIO(exported.decode("utf-8-sig")))
        assert {row["topic_id"]: int(row["proposed_hours"]) for row in csv_rows} == hours
        persisted(base, dataset_id, plan, exported, analytics)
        checks.append("two synthetic CSVs -> import -> analytics -> textbook comparison -> planner -> saved JSON/CSV")
        command("docker", "restart", name)
        base = start(name)
        persisted(base, dataset_id, plan, exported, analytics)
        command("docker", "rm", "-f", name)
        containers.remove(name)
        create(name, storage)
        base = start(name)
        persisted(base, dataset_id, plan, exported, analytics)
        checks.append("identical dataset/analytics/comparison/plan/CSV after restart AND container replacement")
        command("docker", "exec", name, "python", "-m", "backend.app.db.backup",
                "--output", "/app/data/backups/rehearsal.sqlite3")
        backup = artifacts / "backup.sqlite3"
        command("docker", "cp", name + ":/app/data/backups/rehearsal.sqlite3", backup)
        restored_volume = volume("-restore")
        restored_name = run_id + "-restored"
        create(restored_name, restored_volume, "/app/data/recovery.sqlite3")
        command("docker", "cp", backup, restored_name + ":/app/data/recovery.sqlite3")
        # docker cp creates a root-owned file; ownership setup is limited to our fresh test volume.
        command("docker", "run", "--rm", "--user", "0", "-v", restored_volume + ":/app/data",
                backend_image, "chown", "appuser:appuser", "/app/data/recovery.sqlite3")
        restored_base = start(restored_name)
        persisted(restored_base, dataset_id, plan, exported, analytics)
        checks.append("off-volume backup restored to a NEW volume with identical dataset/analytics/comparison/plan/CSV")
        # Inspect Docker's real healthcheck, not just an external HTTP request.
        deadline = time.monotonic() + 45
        while True:
            health = command("docker", "inspect", "--format", "{{.State.Health.Status}}", restored_name).stdout.strip()
            if health == "healthy":
                break
            assert time.monotonic() < deadline, health
            time.sleep(2)
        checks.append("Docker HEALTHCHECK on nondefault PORT=8765")
        features = http(restored_base, "/api/capabilities")[1]["features"]
        assert all(features[key] for key in ('analytics', 'textbook_comparison', 'plan_preview', 'plan_save', 'plan_report', 'plan_csv'))
        report = {"infrastructure_passed": True, "server_p0_verified": True, "full_p0_verified": False, "synthetic_data_only": True,
                  "frontend": "synthetic build probe; Damir React app unavailable",
                  "analytics_available": features["analytics"], "comparison_available": features["textbook_comparison"],
                  "dataset_id": dataset_id, "plan_id": plan["plan_id"], "checks": checks,
                  "comparison_difference_gain_pp": comparison['difference_gain_pp'],
                  "plan_total_hours": plan['total_hours'],
                  "backup_sha256": hashlib.sha256(backup.read_bytes()).hexdigest()}
        (artifacts / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
        print("Artifacts: " + str(artifacts), flush=True)
    finally:
        for name in containers:
            command("docker", "logs", name, ok=False)
            command("docker", "rm", "-f", name, ok=False)
        for name in volumes:
            command("docker", "volume", "rm", name, ok=False)
        for name in (backend_image, web_image):
            command("docker", "image", "rm", name, ok=False)


if __name__ == "__main__":
    main()
