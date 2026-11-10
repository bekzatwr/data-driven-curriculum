"""Read-only P0 release precheck. Does not replace team review or a browser E2E."""
import argparse
import json
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--mode", choices=("public", "local"), default="public")
    parser.add_argument("--require-https", action="store_true")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    blockers = []
    if args.require_https and not base.startswith("https://"):
        blockers.append("HTTPS URL required")
    try:
        def read(path):
            with urlopen(base + path, timeout=15) as response:
                return json.load(response)
        health, capabilities, schema = read("/api/health"), read("/api/capabilities"), read("/openapi.json")
        if health.get("database") != "ok":
            blockers.append("database health")
        public = args.mode == "public"
        if health.get("read_only_demo") is not public or capabilities.get("mode") != ("read_only_demo" if public else "local"):
            blockers.append("mode does not match " + args.mode)
        for feature in ("csv_import", "import_preview", "package_restore", "plan_save"):
            if capabilities["features"].get(feature) is not (not public):
                blockers.append("write policy: " + feature)
        for feature in ("analytics", "textbook_comparison", "plan_preview", "plan_report", "plan_csv"):
            if not capabilities["features"].get(feature):
                blockers.append("feature: " + feature)
        for path in ("/api/datasets/{dataset_id}/overview", "/api/datasets/{dataset_id}/topics/{topic_id}",
                     "/api/datasets/{dataset_id}/comparison"):
            if "get" not in schema["paths"].get(path, {}):
                blockers.append("GET " + path)
        with urlopen(base + "/", timeout=15) as response:
            html = response.read().lower()
            if "text/html" not in response.headers.get("Content-Type", "") or b"packaging probe only" in html:
                blockers.append("real frontend build")
    except (OSError, ValueError, KeyError) as exc:
        blockers.append("HTTP/precheck failure: " + str(exc))
    print(json.dumps({"technical_precheck_passed": not blockers, "mode": args.mode, "blockers": blockers,
                      "still_required": ["team review", "real browser full P0 E2E", "restart/restore rehearsal",
                                         "hosting/budget approval if paid"]}, ensure_ascii=False, indent=2))
    raise SystemExit(2 if blockers else 0)


if __name__ == "__main__":
    main()
