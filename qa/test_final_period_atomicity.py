"""Final integration QA only; no production or PR #10 changes."""
from contextlib import closing
import math
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

from backend.app.config import Settings
from backend.app.main import create_app
from planner import service, storage


def rows(path):
    with closing(sqlite3.connect(path)) as db:
        return (db.execute('SELECT id, snapshot FROM aidana_plan_snapshots ORDER BY id').fetchall(),
                db.execute('SELECT * FROM plans ORDER BY id').fetchall())


@pytest.fixture
def integration(tmp_path):
    settings = Settings(database_path=tmp_path / 'final-atomic.sqlite3')
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        dataset = client.post('/api/datasets/demo').json()['dataset_id']
        url = f'/api/datasets/{dataset}/plans'
        saved = []
        for request in ({'class_id': '7A'}, {'class_id': '7A', 'settings': {'mode': 'period'}}):
            response = client.post(url, json=request)
            assert response.status_code == 201, response.text
            saved.append(response.json())
        yield client, settings, url, saved


@pytest.mark.parametrize('failure,status', [
    ('invalid_percentage', 422), ('missing_metadata', 422), ('nonfinite_json', 500),
    ('invalid_utf8', 500), ('response_render', 500), ('after_insert', 500), ('at_commit', 500),
])
def test_period_failure_preserves_existing_p0_and_period(integration, monkeypatch, failure, status):
    client, settings, url, existing = integration
    before = rows(settings.database_path)
    request = {'class_id': '7A', 'settings': {'mode': 'period'}}
    trigger = failure in ('after_insert', 'at_commit')
    if trigger:
        with closing(sqlite3.connect(settings.database_path)) as db, db:
            if failure == 'at_commit':
                db.executescript('''
                    CREATE TABLE qa_parent (id INTEGER PRIMARY KEY);
                    CREATE TABLE qa_audit (parent_id INTEGER REFERENCES qa_parent(id)
                        DEFERRABLE INITIALLY DEFERRED);
                    CREATE TRIGGER qa_reject AFTER INSERT ON aidana_plan_snapshots
                    BEGIN INSERT INTO qa_audit VALUES (42); END;
                ''')
            else:
                db.executescript('''
                    CREATE TRIGGER qa_reject AFTER INSERT ON aidana_plan_snapshots
                    BEGIN SELECT RAISE(FAIL, 'Synthetic final QA failure after INSERT'); END;
                ''')
    with monkeypatch.context() as patch:
        if failure == 'at_commit':
            connect = sqlite3.connect
            def foreign_keys(*args, **kwargs):
                connection = connect(*args, **kwargs)
                connection.execute('PRAGMA foreign_keys=ON')
                return connection
            patch.setattr(storage, 'sqlite3', SimpleNamespace(connect=foreign_keys))
        elif failure == 'response_render':
            render = JSONResponse.render
            def broken_render(self, content):
                if self.status_code == 201:
                    raise RuntimeError('Synthetic final QA render failure')
                return render(self, content)
            patch.setattr(JSONResponse, 'render', broken_render)
        elif not trigger:
            preview = service.preview
            def broken_preview(*args, **kwargs):
                result = preview(*args, **kwargs)
                if failure == 'invalid_percentage':
                    result['metrics'][0]['mean_post_pct'] = math.nextafter(100.0, math.inf)
                elif failure == 'missing_metadata':
                    del result['source']['metadata']['name']
                elif failure == 'nonfinite_json':
                    result['metrics'][0]['max_score'] = math.nan
                else:
                    result['items'][0]['topic_name'] = '\ud800'
                return result
            patch.setattr(service, 'preview', broken_preview)
        response = client.post(url, json=request)
        assert response.status_code == status, response.text
    assert rows(settings.database_path) == before
    with closing(sqlite3.connect(settings.database_path)) as db, db:
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        if failure == 'at_commit':
            assert db.execute('SELECT COUNT(*) FROM qa_audit').fetchone()[0] == 0
        if trigger:
            db.execute('DROP TRIGGER qa_reject')
    for plan in existing:
        assert client.get('/api/plans/' + plan['plan_id']).json() == plan
    assert client.post(url, json=request).status_code == 201
    assert len(rows(settings.database_path)[0]) == len(before[0]) + 1


@pytest.mark.parametrize('violation', ['sum', 'min', 'max', 'locked', 'incomplete', 'fractional'])
def test_period_manual_errors_do_not_write(integration, violation):
    client, settings, url, existing = integration
    hours = {item['topic_id']: item['current_hours'] for item in existing[1]['items']}
    if violation == 'sum':
        hours['fractions'] += 1
    elif violation == 'min':
        hours.update(revision=0, fractions=8)
    elif violation == 'max':
        hours.update(statistics=6, fractions=4)
    elif violation == 'locked':
        hours.update(geometry=4, fractions=5)
    elif violation == 'incomplete':
        del hours['fractions']
    else:
        hours.update(fractions=6.5, equations=4.5)
    before = rows(settings.database_path)
    response = client.post(url, json={'class_id': '7A', 'settings': {'mode': 'period'}, 'hours_by_topic': hours})
    assert response.status_code == 422, response.text
    assert rows(settings.database_path) == before


@pytest.mark.parametrize('mode,status', [('period', 201), ('rules_v1', 422)])
def test_manual_plus_three_is_period_only(integration, mode, status):
    """Server contract for the frontend stepper bug: 5 -> 8 is valid in period."""
    client, settings, url, existing = integration
    before = rows(settings.database_path)
    hours = dict(fractions=6, equations=8, proportions=4, geometry=3,
                 statistics=2, revision=1)
    response = client.post(url, json={'class_id': '7A', 'settings': {'mode': mode},
                                     'hours_by_topic': hours})
    assert response.status_code == status, response.text
    if status == 422:
        assert rows(settings.database_path) == before
    else:
        saved = response.json()
        assert saved['algorithm_version'] == 'period_v1'
        assert saved['manually_modified'] is True
        assert sum(i['proposed_hours'] for i in saved['items']) == 24
        assert {i['topic_id']: i['proposed_hours'] for i in saved['items']} == hours
        equations = next(i for i in saved['items'] if i['topic_id'] == 'equations')
        assert equations['current_hours'] == 5 and equations['max_hours'] == 8
        assert equations['recommended_hours'] == 6
        assert equations['manually_modified'] is True
        assert client.get('/api/plans/' + saved['plan_id']).json() == saved
        assert len(rows(settings.database_path)[0]) == len(before[0]) + 1
    for plan in existing:
        assert client.get('/api/plans/' + plan['plan_id']).json() == plan
