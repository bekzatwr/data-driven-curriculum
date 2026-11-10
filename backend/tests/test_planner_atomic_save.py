"""Regression coverage for fractional scores and failure-atomic plan persistence."""
from contextlib import closing
import math
import sqlite3
from types import SimpleNamespace

from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse
import pytest

from backend.app.demo import demo_files
from planner.contracts import PlanPreview, SavedPlan
from planner.demo import DemoStore
from planner.models import PlanRequest
from planner import service, storage
from .conftest import send_import


def plan_rows(path):
    # Read through an independent real connection: only committed rows are visible.
    with closing(sqlite3.connect(path)) as db:
        return (db.execute('SELECT id, snapshot FROM aidana_plan_snapshots ORDER BY id').fetchall(),
                db.execute('SELECT COUNT(*) FROM plans').fetchone()[0])


@pytest.mark.parametrize('score,maximum,expected', [
    (0.69, 0.69, 100.0), (0.29, 0.29, 100.0), (0.0, 0.69, 0.0),
    (0.23, 0.69, 100 / 3), (0.1, 0.3, 100 / 3),
    (1e308, 1e308, 100.0), (5e-324, 5e-324, 100.0),
    (math.nextafter(0.69, 0.0), 0.69, 99.99999999999999),
])
def test_normalized_percentage_stays_within_contract(score, maximum, expected):
    source = DemoStore()
    for row in source.results:
        row.update(score=score, max_score=maximum)
    result = service.preview(source, 'aidana-demo', PlanRequest(class_id='7A'))
    PlanPreview.model_validate(result)
    for metric in result['metrics']:
        actual = metric['mean_post_pct']
        assert math.isfinite(actual) and 0 <= actual <= 100
        if expected in (0.0, 100.0):
            assert actual == expected  # No approximate comparison at the critical upper bound.
        else:
            assert actual == pytest.approx(expected, abs=1e-13, rel=0)
        if score < maximum and score > 0:
            assert actual < 100  # No rounding/clamping of near-perfect scores.


@pytest.fixture
def fractional_dataset(client, sample):
    for row in sample['rows']:
        row.update(score=0.69, max_score=0.69)
    response = send_import(client, sample)
    assert response.status_code == 201
    return response.json()['dataset_id']


def test_fractional_preview_returns_100(client, fractional_dataset):
    response = client.post(f'/api/datasets/{fractional_dataset}/plans/preview', json={'class_id': '7A'})
    assert response.status_code == 200
    plan = PlanPreview.model_validate(response.json())
    assert all(metric.mean_post_pct == 100.0 for metric in plan.metrics)


def test_fractional_save_returns_valid_committed_snapshot(client, settings, fractional_dataset):
    before = plan_rows(settings.database_path)
    response = client.post(f'/api/datasets/{fractional_dataset}/plans', json={'class_id': '7A'})
    assert response.status_code == 201
    plan = SavedPlan.model_validate(response.json())
    assert all(metric.mean_post_pct == 100.0 for metric in plan.metrics)
    assert len(plan_rows(settings.database_path)[0]) == len(before[0]) + 1
    assert client.get('/api/plans/' + plan.plan_id).json() == response.json()
    assert client.get('/api/plans/' + plan.plan_id + '/export.csv').status_code == 200


@pytest.mark.parametrize('score,maximum', [(-0.01, 0.69), (0.7, 0.69), (0, 0), (0, -0.69)])
def test_fractional_input_bounds_still_rejected(client, settings, sample, score, maximum):
    for row in sample['rows']:
        row.update(score=score, max_score=maximum)
    assert send_import(client, sample).status_code == 422
    assert client.get('/api/datasets').json()['total'] == 0
    assert plan_rows(settings.database_path) == ([], 0)


@pytest.fixture
def saved_case(client, settings, sample):
    response = send_import(client, sample)
    assert response.status_code == 201
    url = f"/api/datasets/{response.json()['dataset_id']}/plans"
    first = client.post(url, json={'class_id': '7A'})
    assert first.status_code == 201
    before = plan_rows(settings.database_path)
    assert len(before[0]) == 1
    # Deliberately inspect actual HTTP errors rather than TestClient re-raising them.
    with TestClient(client.app, raise_server_exceptions=False) as http:
        yield http, url, before


@pytest.mark.parametrize('failure,status', [
    ('out_of_range', 422), ('missing_snapshot_field', 422),
    ('nonfinite_json', 500), ('invalid_utf8', 500),
])
def test_snapshot_failure_leaves_existing_rows_unchanged(saved_case, settings, monkeypatch, failure, status):
    http, url, before = saved_case
    original = service.preview

    def broken_snapshot(*args, **kwargs):
        result = original(*args, **kwargs)
        if failure == 'out_of_range':
            result['metrics'][0]['mean_post_pct'] = math.nextafter(100.0, math.inf)
        elif failure == 'missing_snapshot_field':
            del result['source']['metadata']['name']
        elif failure == 'nonfinite_json':
            result['metrics'][0]['max_score'] = math.nan
        else:
            result['items'][0]['topic_name'] = '\ud800'
        return result

    monkeypatch.setattr(service, 'preview', broken_snapshot)
    response = http.post(url, json={'class_id': '7A'})
    assert response.status_code == status
    assert plan_rows(settings.database_path) == before


def test_response_render_failure_does_not_commit(saved_case, settings, monkeypatch):
    http, url, before = saved_case
    render = JSONResponse.render

    def fail_created_response(self, content):
        if self.status_code == 201:
            raise RuntimeError('Injected response rendering failure')
        return render(self, content)

    monkeypatch.setattr(JSONResponse, 'render', fail_created_response)
    assert http.post(url, json={'class_id': '7A'}).status_code == 500
    assert plan_rows(settings.database_path) == before


@pytest.mark.parametrize('at_commit', [False, True], ids=['after_insert', 'deferred_commit'])
def test_sqlite_failure_rolls_back_actual_transaction(saved_case, settings, monkeypatch, at_commit):
    http, url, before = saved_case
    with closing(sqlite3.connect(settings.database_path)) as db, db:
        if at_commit:
            db.executescript('''
                CREATE TABLE required_parent (id INTEGER PRIMARY KEY);
                CREATE TABLE save_audit (parent_id INTEGER REFERENCES required_parent(id)
                    DEFERRABLE INITIALLY DEFERRED);
                CREATE TRIGGER reject_snapshot AFTER INSERT ON aidana_plan_snapshots
                BEGIN INSERT INTO save_audit VALUES (42); END;
            ''')
        else:
            # FAIL keeps the insert pending until the enclosing transaction rolls back.
            db.executescript('''
                CREATE TRIGGER reject_snapshot AFTER INSERT ON aidana_plan_snapshots
                BEGIN SELECT RAISE(FAIL, 'Injected failure after INSERT'); END;
            ''')
    if at_commit:
        connect = sqlite3.connect

        def with_foreign_keys(*args, **kwargs):
            connection = connect(*args, **kwargs)
            connection.execute('PRAGMA foreign_keys=ON')
            return connection

        monkeypatch.setattr(storage, 'sqlite3', SimpleNamespace(connect=with_foreign_keys))
    assert http.post(url, json={'class_id': '7A'}).status_code == 500
    assert plan_rows(settings.database_path) == before
    with closing(sqlite3.connect(settings.database_path)) as db, db:
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        if at_commit:
            assert db.execute('SELECT COUNT(*) FROM save_audit').fetchone()[0] == 0
        db.execute('DROP TRIGGER reject_snapshot')
    assert http.post(url, json={'class_id': '7A'}).status_code == 201
    assert len(plan_rows(settings.database_path)[0]) == len(before[0]) + 1


@pytest.mark.parametrize('violation', [None, 'sum', 'min', 'max', 'locked', 'delta', 'incomplete'])
def test_hour_rules_and_manual_validation_remain_intact(client, settings, violation):
    response = send_import(client, None, raw=demo_files())
    assert response.status_code == 201
    url = f"/api/datasets/{response.json()['dataset_id']}/plans"
    preview = client.post(url + '/preview', json={'class_id': '7A'}).json()
    assert sum(i['proposed_hours'] for i in preview['items']) == preview['total_hours'] == 24
    for item in preview['items']:
        assert item['min_hours'] <= item['proposed_hours'] <= item['max_hours']
        assert abs(item['delta']) <= 2
        if item['is_locked']:
            assert item['delta'] == 0
    hours = {item['topic_id']: item['current_hours'] for item in preview['items']}
    if violation == 'sum':
        hours['fractions'] += 1
    elif violation == 'min':
        hours.update(revision=0, fractions=8)
    elif violation == 'max':
        hours.update(statistics=6, fractions=4)
    elif violation == 'locked':
        hours.update(geometry=4, fractions=5)
    elif violation == 'delta':
        hours.update(fractions=3, equations=8)
    elif violation == 'incomplete':
        del hours['fractions']
    before = plan_rows(settings.database_path)
    saved = client.post(url, json={'class_id': '7A', 'hours_by_topic': hours})
    assert saved.status_code == (422 if violation else 201)
    if violation:
        assert plan_rows(settings.database_path) == before
    else:
        assert {i['topic_id']: i['proposed_hours'] for i in saved.json()['items']} == hours
