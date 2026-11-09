"""Check the running Compose demo via real HTTP, including persistence across restart."""
import argparse
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request(path, method="GET"):
    try:
        with urlopen(Request("http://127.0.0.1:8000" + path, method=method), timeout=5) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect-existing", action="store_true")
    args = parser.parse_args()
    deadline = time.monotonic() + 60
    while True:
        try:
            status, health = request("/api/health")
            if status == 200:
                break
        except (URLError, TimeoutError, ConnectionError):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError("Container did not become ready within 60 seconds")
        time.sleep(1)
    assert health["read_only_demo"] is True, health
    assert request("/api/datasets/import", "POST")[0] == 403
    state_file = Path("data/container-check.json")
    if args.expect_existing:
        previous = json.loads(state_file.read_text(encoding="utf-8"))
        assert request("/api/datasets/" + previous["dataset_id"])[0] == 200
    status, demo = request("/api/datasets/demo", "POST")
    assert status in (200, 201), demo
    assert demo["counts"]["results"] == 1440
    if args.expect_existing:
        assert status == 200 and demo["dataset_id"] == previous["dataset_id"]
    status, repeated = request("/api/datasets/demo", "POST")
    assert status == 200 and repeated["dataset_id"] == demo["dataset_id"]
    status, filters = request(f'/api/datasets/{demo["dataset_id"]}/filters')
    assert status == 200 and len(filters["classes"]) == 4
    result = {"passed": True, "read_only_demo": True, "dataset_id": demo["dataset_id"],
              "results": 1440, "persistence_checked": args.expect_existing}
    state_file.parent.mkdir(exist_ok=True)
    state_file.write_text(json.dumps(result), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
