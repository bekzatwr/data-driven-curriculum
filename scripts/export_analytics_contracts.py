"""Generate real JSON responses and OpenAPI, never invented display numbers."""
import json
from pathlib import Path
from fastapi.testclient import TestClient
from analytics.app import create_demo_app
from analytics.demo import DATASET_ID


def main():
    directory = Path(__file__).resolve().parents[1] / 'contracts'
    directory.mkdir(exist_ok=True)
    app = create_demo_app()
    with TestClient(app) as client:
        base = f'/api/datasets/{DATASET_ID}'
        examples = {
            'analytics-overview.response.json': client.get(base + '/overview'),
            'analytics-topic.response.json': client.get(base + '/topics/equations'),
            'analytics-comparison.response.json': client.get(base + '/comparison', params={
                'topic_id': 'equations', 'textbook_a': 'Учебник A', 'textbook_b': 'Учебник B'}),
            'analytics-empty.response.json': client.get(base + '/overview', params={
                'class_ids': '7A', 'textbook_ids': 'Учебник B'}),
            'analytics-error.response.json': client.get(base + '/overview', params={'class_ids': 'unknown'}),
            'analytics.openapi.json': client.get('/openapi.json'),
        }
        for name, response in examples.items():
            expected = 422 if name == 'analytics-error.response.json' else 200
            if response.status_code != expected:
                raise RuntimeError(f'{name}: {response.status_code}: {response.text}')
            (directory / name).write_text(json.dumps(response.json(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
