"""Public HTTP must never mutate SQLite, including valid planner requests."""
import sqlite3
from dataclasses import replace

from fastapi.testclient import TestClient
import pytest

from backend.app.main import create_app
from deploy.seed_demo_report import prepare_report


def snapshot(path):
    with sqlite3.connect(path) as db:
        return list(db.iterdump())


@pytest.mark.parametrize('method,path,body', [
    ('POST', '/api/datasets/import?dry_run=false', b'invalid multipart'),
    ('POST', '/api/datasets/import/?dry_run=true', b''),
    ('POST', '/api/datasets/restore', b'{'),
    ('POST', '/api/datasets/{id}/plans', b'{"class_id":"7A"}'),
    ('POST', '/api/datasets/{id}/plans/', b'{'),
    ('POST', '/api/datasets/{id}/plans', b'x' * 65536),
    ('DELETE', '/api/datasets/{id}', b''),
    ('PATCH', '/api/plans/missing', b'{}'),
    ('PUT', '/api/future-write-endpoint', b'{}'),
])
def test_public_mutations_blocked_before_body_parse(settings, method, path, body):
    with TestClient(create_app(replace(settings, read_only_demo=True))) as client:
        demo_id = client.post('/api/datasets/demo').json()['dataset_id']
        before = snapshot(settings.database_path)
        response = client.request(method, path.format(id=demo_id), content=body,
                                  headers={'content-type': 'application/json'})
        assert response.status_code == 403
        assert response.json()['code'] == 'READ_ONLY_DEMO'
        assert snapshot(settings.database_path) == before


def test_public_lookup_preview_report_export_are_read_only_and_survive_restart(settings, monkeypatch):
    public_settings = replace(settings, read_only_demo=True)
    prepared = prepare_report(public_settings)
    before = snapshot(settings.database_path)
    assert prepare_report(public_settings) == prepared
    assert snapshot(settings.database_path) == before
    with TestClient(create_app(public_settings)) as client:
        def forbidden_write(*args, **kwargs):
            pytest.fail('Public request attempted a database write')
        monkeypatch.setattr(client.app.state.store, 'save_upload', forbidden_write)
        monkeypatch.setattr(client.app.state.plan_snapshots, 'save', forbidden_write)
        for _ in range(2):
            demo = client.post('/api/datasets/demo')
            assert demo.status_code == 200 and demo.json()['created'] is False
            assert demo.json()['dataset_id'] == prepared['dataset_id']
        preview = client.post(f"/api/datasets/{prepared['dataset_id']}/plans/preview", json={'class_id': '7A'})
        assert preview.status_code == 200 and preview.json()['total_hours'] == 24
        report = client.get(prepared['report_url'])
        exported = client.get(prepared['csv_url'])
        assert report.status_code == 200 and report.json()['is_demo'] is True
        assert exported.status_code == 200 and exported.content.startswith(b'\xef\xbb\xbf')
        caps = client.get('/api/capabilities').json()
        assert caps['features']['plan_save'] is False
        assert caps['features']['csv_import'] is False
        assert caps['features']['plan_preview'] is True
        assert snapshot(settings.database_path) == before
    with TestClient(create_app(public_settings)) as restarted:
        assert restarted.get(prepared['report_url']).json() == report.json()
        assert restarted.get(prepared['csv_url']).content == exported.content
        assert snapshot(settings.database_path) == before


@pytest.mark.parametrize('path', [
    '/api/plans/..%2f..%2fdata%2fcurriculum.sqlite3/export.csv',
    '/api/plans/%2e%2e%5c%2e%2e%5cprivate.txt/export.csv',
    '/api/plans/%27%20OR%201=1--/export.csv',
    '/api/plans/missing%0d%0aX-Injected:yes/export.csv',
])
def test_export_ids_cannot_read_files_or_inject_headers(settings, path):
    with TestClient(create_app(replace(settings, read_only_demo=True))) as client:
        response = client.get(path)
        assert response.status_code == 404
        assert 'x-injected' not in response.headers
        assert not response.content.startswith(b'SQLite format')


def test_public_entrypoint_refuses_write_configuration(monkeypatch):
    from deploy.run_server import preflight
    monkeypatch.setenv('PUBLIC_DEMO', 'true')
    monkeypatch.setenv('READ_ONLY_DEMO', 'false')
    with pytest.raises(ValueError, match='refusing public writes'):
        preflight()
