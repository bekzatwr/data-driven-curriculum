"""Real imported data -> Aidana's planner -> persistent report and CSV."""
import csv
import io
import warnings
from dataclasses import replace

from fastapi.testclient import TestClient
import pytest

from backend.app.db.backup import backup_database
from backend.app.demo import demo_files
from backend.app.main import create_app
from .conftest import send_import


def imported(client):
    results, topics, metadata = demo_files()
    response = client.post('/api/datasets/import?dry_run=false', data={'metadata': metadata}, files={
        'results_file': ('results.csv', results), 'curriculum_file': ('curriculum.csv', topics)})
    assert response.status_code == 201
    return response.json()['dataset_id']


def test_two_csv_to_saved_report_restart_and_backup(client, settings, tmp_path):
    dataset_id = imported(client)
    path = f'/api/datasets/{dataset_id}/plans'
    payload = {'class_id': '7A'}
    preview = client.post(path + '/preview', json=payload)
    assert preview.status_code == 200
    proposed = preview.json()
    assert proposed['total_hours'] == 24 and len(proposed['items']) == 6
    assert all(i['n_post'] == 30 for i in proposed['items'])
    assert all(i['delta'] == 0 for i in proposed['items'] if i['is_locked'])
    hours = {i['topic_id']: i['proposed_hours'] for i in proposed['items']}
    saved = client.post(path, json={**payload, 'hours_by_topic': hours, 'comment': 'P0 integrated check'})
    assert saved.status_code == 201
    plan = saved.json()
    report_path = '/api/plans/' + plan['plan_id']
    assert client.get(report_path).json() == plan
    response = client.get(report_path + '/export.csv', headers={'Origin': 'http://localhost:5173'})
    assert response.status_code == 200 and response.content.startswith(b'\xef\xbb\xbf')
    assert 'Content-Disposition' in response.headers['access-control-expose-headers']
    rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
    assert {r['topic_id']: int(r['proposed_hours']) for r in rows} == hours
    assert sum(int(r['proposed_hours']) for r in rows) == 24
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(report_path).json() == plan
    backup = tmp_path / 'combined-backup.sqlite3'
    backup_database(settings.database_path, backup)
    with TestClient(create_app(replace(settings, database_path=backup))) as recovered:
        assert recovered.get(f'/api/datasets/{dataset_id}').status_code == 200
        assert recovered.get(report_path).json() == plan


def test_public_mode_limits_plans_to_demo_sources(client, settings):
    private_id = imported(client)
    private = client.post(f'/api/datasets/{private_id}/plans', json={'class_id': '7A'}).json()
    with TestClient(create_app(replace(settings, read_only_demo=True))) as public:
        assert public.get('/api/plans/' + private['plan_id']).status_code == 404
        assert public.get('/api/plans/' + private['plan_id'] + '/export.csv').status_code == 404
        assert public.post(f'/api/datasets/{private_id}/plans/preview', json={'class_id': '7A'}).status_code == 404
        assert public.post(f'/api/datasets/{private_id}/plans', json={'class_id': '7A'}).status_code == 403
        demo_id = public.post('/api/datasets/demo').json()['dataset_id']
        assert public.post(f'/api/datasets/{demo_id}/plans', json={'class_id': '7A'}).status_code == 403


@pytest.mark.parametrize('payload', [
    {'class_id': 'unknown'}, {'class_id': '7A', 'hours_by_topic': {'fractions': 99}},
    {'class_id': '7A', 'settings': {'target_pct': 90, 'donor_pct': 80}},
    {'class_id': '7A', 'constraints': {'not-a-topic': {}}},
])
def test_invalid_plan_does_not_save(client, payload):
    dataset_id = imported(client)
    response = client.post(f'/api/datasets/{dataset_id}/plans', json=payload)
    assert response.status_code == 422 and 'total_errors' in response.json()
    with client.app.state.store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM aidana_plan_snapshots').fetchone()[0] == 0


def test_frontend_contracts_and_cors(client):
    schema = client.get('/openapi.json').json()
    for path, method, status, model in (
        ('/api/datasets/{dataset_id}/plans/preview', 'post', '200', 'PlanPreview'),
        ('/api/datasets/{dataset_id}/plans', 'post', '201', 'SavedPlan'),
        ('/api/plans/{plan_id}', 'get', '200', 'SavedPlan'),
    ):
        response = schema['paths'][path][method]['responses'][status]
        assert response['content']['application/json']['schema']['$ref'].endswith('/' + model)
    csv_response = schema['paths']['/api/plans/{plan_id}/export.csv']['get']['responses']['200']
    assert set(csv_response['content']) == {'text/csv'}
    cors = client.options('/api/datasets/example/plans', headers={
        'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'content-type'})
    assert cors.status_code == 200
    assert cors.headers['access-control-allow-origin'] == 'http://localhost:5173'
    features = client.get('/api/capabilities').json()['features']
    assert features['plan_save'] is True and features['analytics'] is True
    assert features['textbook_comparison'] is True
    assert '/api/datasets/{dataset_id}/comparison' in schema['paths']
    # The legacy integration factory must not duplicate the built-in planner router.
    from planner.api import router
    app = create_app(client.app.state.settings, routers=(router,))
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter('always')
        combined = app.openapi()
    assert '/api/plans/{plan_id}' in combined['paths']
    assert not any('Duplicate Operation ID' in str(w.message) for w in captured)
