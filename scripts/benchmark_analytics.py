"""Three measured runs against exactly 10,000 synthetic records."""
import json
from time import perf_counter
from fastapi.testclient import TestClient
from analytics.app import create_demo_app
from analytics.demo import DATASET_ID, demo_records


def main():
    app = create_demo_app()
    _, records = demo_records()
    expanded = [{**row, 'student_id': f"copy{batch}-{row['student_id']}"}
                for batch in range(7) for row in records][:10000]
    app.state.store.records = expanded
    durations = []
    with TestClient(app) as client:
        for _ in range(3):
            start = perf_counter()
            response = client.get(f'/api/datasets/{DATASET_ID}/overview')
            response.raise_for_status()
            durations.append(perf_counter() - start)
    print(json.dumps({'records': len(expanded), 'runs_seconds': durations,
                      'includes': 'HTTP adapter, calculation and serialization; excludes real database/network',
                      'target_seconds': 2, 'all_under_target': all(x < 2 for x in durations)}, indent=2))


if __name__ == '__main__':
    main()
