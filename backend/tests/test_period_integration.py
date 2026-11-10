import csv
import io

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from .test_p0_integration import imported
from .conftest import send_import


def test_period_import_overview_comparison_manual_save_restart_csv(client, settings):
    dataset = imported(client)
    root = f'/api/datasets/{dataset}'
    overview = client.get(root + '/overview')
    assert overview.status_code == 200
    assert client.get(root + '/topics/equations').status_code == 200
    comparison = client.get(root + '/comparison', params={
        'topic_id': 'equations', 'textbook_a': 'Учебник A', 'textbook_b': 'Учебник B'})
    assert comparison.status_code == 200
    payload = {'class_id': '7A', 'settings': {'mode': 'period'}}
    preview = client.post(root + '/plans/preview', json=payload)
    assert preview.status_code == 200, preview.text
    computed = preview.json()
    hours = {i['topic_id']: i['proposed_hours'] for i in computed['items']}
    donor = next(i for i in computed['items'] if not i['is_locked'] and i['proposed_hours'] > i['min_hours'])
    recipient = next(i for i in computed['items'] if i['topic_id'] != donor['topic_id'] and not i['is_locked'] and i['proposed_hours'] < i['max_hours'])
    hours[donor['topic_id']] -= 1
    hours[recipient['topic_id']] += 1
    response = client.post(root + '/plans', json={**payload, 'hours_by_topic': hours, 'comment': 'Period QA'})
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved['settings'] == computed['settings']
    assert saved['metrics'] == computed['metrics']
    assert saved['algorithm_version'] == 'period_v1'
    assert saved['manually_modified'] is True
    for item, recommendation in zip(saved['items'], computed['items']):
        assert item['recommended_hours'] == recommendation['proposed_hours']
        assert item['proposed_hours'] == hours[item['topic_id']]
        assert item['manually_modified'] == (item['proposed_hours'] != item['recommended_hours'])
    path = '/api/plans/' + saved['plan_id']
    assert client.get(path).json() == saved
    csv_response = client.get(path + '/export.csv')
    assert csv_response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(csv_response.content.decode('utf-8-sig'))))
    for row, item in zip(rows, saved['items']):
        for field in ('proposed_hours', 'recommended_hours', 'delta', 'current_hours', 'min_hours', 'max_hours'):
            assert int(row[field]) == item[field]
        assert row['manually_modified'] == str(item['manually_modified'])
        assert row['algorithm_version'] == 'period_v1'
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(path).json() == saved
        assert restarted.get(path + '/export.csv').content == csv_response.content


@pytest.mark.parametrize('payload', [
    {'settings': {'mode': 'period'}, 'hours_by_topic': {}},
    {'settings': {'mode': 'period'}, 'constraints': {'fractions': {'min_hours': 100}}},
    {'settings': {'mode': 'period'}, 'constraints': {'fractions': {'min_hours': 25, 'max_hours': 30}}},
    {'settings': {'mode': 'unknown'}},
])
def test_invalid_period_save_is_atomic(client, payload):
    dataset = imported(client)
    path = f'/api/datasets/{dataset}/plans'
    existing = client.post(path, json={'class_id': '7A', 'settings': {'mode': 'period'}})
    assert existing.status_code == 201
    with client.app.state.store.connect() as db:
        before = db.execute('SELECT * FROM aidana_plan_snapshots').fetchall()
    failed = client.post(path, json={'class_id': '7A', **payload})
    assert failed.status_code == 422, failed.text
    with client.app.state.store.connect() as db:
        assert db.execute('SELECT * FROM aidana_plan_snapshots').fetchall() == before


def test_legacy_saved_plan_without_mode_remains_readable(client):
    dataset = imported(client)
    response = client.post(f'/api/datasets/{dataset}/plans', json={'class_id': '7A'})
    plan = response.json()
    assert plan['algorithm_version'] == 'rules_v1'
    import json
    plan['settings'].pop('mode')
    with client.app.state.store.connect() as db, db:
        db.execute('UPDATE aidana_plan_snapshots SET snapshot=? WHERE id=?', (json.dumps(plan), plan['plan_id']))
    assert client.get('/api/plans/' + plan['plan_id']).json() == plan


def test_period_fractional_scores_and_bounds_above_original_hours(client, sample):
    for row in sample['rows']:
        row.update(score=.69, max_score=.69)
    imported_response = send_import(client, sample)
    assert imported_response.status_code == 201
    path = f"/api/datasets/{imported_response.json()['dataset_id']}/plans"
    payload = {'class_id': '7A', 'settings': {'mode': 'period'}}
    preview = client.post(path + '/preview', json=payload)
    assert preview.status_code == 200
    assert all(m['mean_post_pct'] == 100 for m in preview.json()['metrics'])
    saved = client.post(path, json=payload)
    assert saved.status_code == 201
    # Existing imported baseline stays valid; period constraints may exceed its
    # individual current allocation when the total can still be distributed.
    dataset = imported(client)
    saved = client.post(f'/api/datasets/{dataset}/plans', json={**payload,
        'constraints': {'fractions': {'min_hours': 9, 'max_hours': 10}}})
    assert saved.status_code == 201, saved.text
    plan = saved.json()
    assert plan['items'][0]['proposed_hours'] >= 9 > plan['items'][0]['current_hours']
    assert not plan['manually_modified']
    assert client.get('/api/plans/' + plan['plan_id']).json() == plan


def test_period_response_render_failure_leaves_existing_rows(client, monkeypatch):
    from planner import api
    from .test_planner_atomic_save import plan_rows
    dataset = imported(client)
    path = f'/api/datasets/{dataset}/plans'
    payload = {'class_id': '7A', 'settings': {'mode': 'period'}}
    assert client.post(path, json=payload).status_code == 201
    before = plan_rows(client.app.state.settings.database_path)
    def fail_render(*args, **kwargs):
        raise ValueError('Synthetic response render failure')
    monkeypatch.setattr(api, 'JSONResponse', fail_render)
    with TestClient(client.app, raise_server_exceptions=False) as http:
        assert http.post(path, json=payload).status_code == 500
    assert plan_rows(client.app.state.settings.database_path) == before
