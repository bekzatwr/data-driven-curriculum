"""Cross-module boundaries through the standard API and a real SQLite import."""
import math
import json

import pytest

from analytics.demo import METADATA, demo_records
from backend.app.demo import csv_bytes
from backend.app.validation import RESULT_FIELDS, TOPIC_FIELDS
from planner.contracts import SavedPlan
from .conftest import send_import


@pytest.mark.parametrize('score,maximum,expected', [
    (0.69, 0.69, 100.0), (0.29, 0.29, 100.0), (0, 0.69, 0.0),
    (0.23, 0.69, 100 / 3), (0.6, 1, 60.0),
    (1e308, 1e308, 100.0), (5e-324, 5e-324, 100.0),
    (math.nextafter(0.69, 0), 0.69, 99.99999999999999),
])
def test_percentage_consistent_across_import_analytics_comparison_and_save(client, score, maximum, expected):
    topics, records = demo_records()
    for row in records:
        row.update(score=0 if row['stage'] == 'pre' else score, max_score=maximum)
    imported = send_import(client, None, raw=(
        csv_bytes(RESULT_FIELDS, records), csv_bytes(TOPIC_FIELDS, topics),
        json.dumps(METADATA, ensure_ascii=False),
    ))
    assert imported.status_code == 201, imported.text
    base = '/api/datasets/' + imported.json()['dataset_id']

    def get(path, **params):
        response = client.get(base + path, params=params)
        assert response.status_code == 200, response.text
        return response.json()

    overview = get('/overview')
    topic = get('/topics/equations')
    comparison = get('/comparison', topic_id='equations', textbook_a='Учебник A', textbook_b='Учебник B')
    assert comparison['comparison_status'] == 'comparable'
    assert comparison['difference_gain_pp'] == 0.0
    assert comparison['baseline_gap_pp'] == 0.0
    for name in ('group_a', 'group_b'):
        assert comparison[name]['n_pairs'] == 60
        assert comparison[name]['mean_pre_paired_pct'] == 0.0
        assert comparison[name]['mean_gain_pp'] == comparison[name]['mean_post_pct']

    preview = client.post(base + '/plans/preview', json={'class_id': '7A'})
    assert preview.status_code == 200, preview.text
    saved = client.post(base + '/plans', json={'class_id': '7A'})
    assert saved.status_code == 201, saved.text
    plan = SavedPlan.model_validate(saved.json())
    values = [overview['metrics']['mean_post_pct'], topic['metrics']['mean_post_pct'],
              comparison['group_a']['mean_post_pct'], comparison['group_b']['mean_post_pct'],
              *[m['mean_post_pct'] for m in preview.json()['metrics']],
              *[m.mean_post_pct for m in plan.metrics]]
    assert len(set(values)) == 1
    for value in values:
        assert math.isfinite(value) and 0 <= value <= 100
        if score in (0, maximum):
            assert value == expected
        else:
            assert value == pytest.approx(expected, rel=0, abs=1e-13)
            assert value < 100  # Near-full scores must not be rounded up.
    assert client.get('/api/plans/' + plan.plan_id).json() == saved.json()
    assert client.get('/api/plans/' + plan.plan_id + '/export.csv').status_code == 200
