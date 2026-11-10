"""Import/restore HTTP failures must not leave silently committed datasets."""
from contextlib import closing
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.app.api import datasets
from .conftest import send_import


def counts(path):
    with closing(sqlite3.connect(path)) as db:
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        return tuple(db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                     for table in ('datasets', 'topics', 'results'))


@pytest.mark.parametrize('operation', ['import', 'demo', 'restore', 'duplicate'])
@pytest.mark.parametrize('failure', ['validation', 'serialization'])
def test_import_response_failure_rolls_back(client, settings, sample, monkeypatch, operation, failure):
    # Preserve an existing dataset while a different upload/restore is attempted.
    existing = send_import(client, sample)
    assert existing.status_code == 201
    if operation != 'duplicate':
        sample['metadata']['name'] = 'Another synthetic dataset'
    if operation == 'restore':
        package = client.get(f"/api/datasets/{existing.json()['dataset_id']}/package").json()
        # Restore a previously exported valid package into an empty database.
        with client.app.state.store.connect() as db:
            db.execute('DELETE FROM results')
            db.execute('DELETE FROM topics')
            db.execute('DELETE FROM datasets')
    before = counts(settings.database_path)

    def fail(*args, **kwargs):
        raise ValueError('Injected import response failure')

    with TestClient(client.app, raise_server_exceptions=False) as http:
        with monkeypatch.context() as patch:
            patch.setattr(datasets, 'ImportResponse' if failure == 'validation' else 'JSONResponse', fail)
            if operation in ('import', 'duplicate'):
                response = send_import(http, sample)
            elif operation == 'demo':
                response = http.post('/api/datasets/demo')
            else:
                response = http.post('/api/datasets/restore?dry_run=false', json=package)
            assert response.status_code == 500
            assert counts(settings.database_path) == before
        # A retry after the failure is a real creation (or the same existing duplicate).
        if operation in ('import', 'duplicate'):
            retry = send_import(http, sample)
        elif operation == 'demo':
            retry = http.post('/api/datasets/demo')
        else:
            retry = http.post('/api/datasets/restore?dry_run=false', json=package)
        assert retry.status_code == (200 if operation == 'duplicate' else 201)
        assert counts(settings.database_path)[0] == before[0] + (operation != 'duplicate')


def test_import_commit_failure_does_not_return_success(client, settings, sample):
    # This FK is checked at COMMIT, after all rows and response bytes exist.
    with client.app.state.store.connect() as db:
        db.executescript('''
            CREATE TABLE import_parent(id INTEGER PRIMARY KEY);
            CREATE TABLE import_audit(parent_id INTEGER REFERENCES import_parent(id)
                DEFERRABLE INITIALLY DEFERRED);
            CREATE TRIGGER reject_import AFTER INSERT ON results
            BEGIN INSERT INTO import_audit VALUES (42); END;
        ''')
    before = counts(settings.database_path)
    with TestClient(client.app, raise_server_exceptions=False) as http:
        assert send_import(http, sample).status_code == 500
    assert counts(settings.database_path) == before
    with client.app.state.store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM import_audit').fetchone()[0] == 0
        db.execute('DROP TRIGGER reject_import')
    assert send_import(client, sample).status_code == 201
