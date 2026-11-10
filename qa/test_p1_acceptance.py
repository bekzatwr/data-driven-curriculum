"""Run explicitly on the combined P1 checkout: python -m pytest -q qa.

Requires Bekzat's collab module; intentionally fails collection if it is absent.
Only provider transport is mocked. SQLite, analytics and planning are real.
"""
import asyncio
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from collab import ai


@pytest.fixture
def settings(tmp_path):
    return Settings(database_path=tmp_path / 'acceptance.sqlite3')


@pytest.fixture
def client(settings, monkeypatch):
    monkeypatch.setenv('AI_ENABLED', 'true')
    monkeypatch.setenv('AI_ACCOUNT_VERIFIED', 'true')
    monkeypatch.setenv('AI_PROVIDERS', 'groq')
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    async def prohibit_network(*args, **kwargs):
        pytest.fail('Live AI provider calls are prohibited')
    monkeypatch.setattr(ai, '_post_json', prohibit_network)
    with TestClient(create_app(settings)) as session:
        yield session


def setup_plan(client):
    response = client.post('/api/datasets/demo')
    assert response.status_code in (200, 201)
    dataset = response.json()['dataset_id']
    result = client.post(f'/api/datasets/{dataset}/plans', json={'class_id': '7A', 'settings': {'mode': 'period'}})
    assert result.status_code == 201, result.text
    return dataset, result.json()


def academic_state(path):
    # AI requests intentionally update technical rate counters, not academic data.
    with sqlite3.connect(path) as db:
        names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {name: db.execute('SELECT * FROM "' + name.replace('"', '""') + '" ORDER BY rowid').fetchall()
                for name in names if name not in ('collab_rate_events', 'sqlite_sequence')}


def test_period_comments_targets_validation_and_restart(client, settings):
    dataset, plan = setup_plan(client)
    path = f'/api/datasets/{dataset}/comments'
    defaults = dict(author_name='Synthetic QA', author_role='methodist', text='Проверка периода')
    created = []
    for kind, target in [('dataset', dataset), ('topic', 'fractions'), ('plan', plan['plan_id']),
                         ('plan_topic', plan['plan_id'] + ':fractions')]:
        response = client.post(path, json={**defaults, 'target_type': kind, 'target_id': target})
        assert response.status_code == 201, response.text
        created.append(response.json())
    for text in ('', '   ', 'x' * 4001):
        assert client.post(path, json={**defaults, 'target_type': 'topic', 'target_id': 'fractions', 'text': text}).status_code == 422
    assert client.post('/api/datasets/missing/comments', json={**defaults, 'target_type': 'topic', 'target_id': 'fractions'}).status_code == 404
    assert client.get('/api/datasets/missing/comments').status_code == 404
    assert client.get(path).json()['total'] == 4
    with TestClient(create_app(settings)) as restarted:
        actual = restarted.get(path).json()
        assert {i['id'] for i in actual['items']} == {i['id'] for i in created}
        assert restarted.get('/api/plans/' + plan['plan_id']).json() == plan


def test_offline_ai_preserves_academic_data(client, settings):
    dataset, _ = setup_plan(client)
    before = academic_state(settings.database_path)
    assert client.get('/api/ai/status').json()['configured'] is False
    response = client.post(f'/api/datasets/{dataset}/ai/explain', json={'kind': 'overview', 'context': {}})
    assert response.status_code == 503 and response.json()['code'] == 'AI_NOT_CONFIGURED'
    assert 'ИИ не подключён' in response.json()['message']
    assert academic_state(settings.database_path) == before


@pytest.mark.parametrize('scenario', ['success', 'provider_error', 'timeout', 'invalid_context'])
def test_mock_ai_no_secrets_or_academic_writes(client, settings, monkeypatch, caplog, scenario):
    dataset, plan = setup_plan(client)
    secret = 'synthetic-key-never-a-real-credential'
    monkeypatch.setenv('GROQ_API_KEY', secret)
    calls = []
    async def provider(url, payload, headers):
        calls.append(payload)
        if scenario == 'provider_error':
            raise httpx.ConnectError(secret)
        if scenario == 'timeout':
            await asyncio.sleep(1)
        return {'choices': [{'message': {'content': 'Объяснение ' + secret}}]}
    monkeypatch.setattr(ai, '_post_json', provider)
    monkeypatch.setattr(ai, 'TIMEOUT_SECONDS', .01 if scenario == 'timeout' else 20)
    before = academic_state(settings.database_path)
    context = {'not_a_selector': 10} if scenario == 'invalid_context' else {'plan_id': plan['plan_id']}
    response = client.post(f'/api/datasets/{dataset}/ai/explain', json={'kind': 'plan', 'context': context})
    expected = {'success': 200, 'provider_error': 502, 'timeout': 502, 'invalid_context': 422}[scenario]
    assert response.status_code == expected, response.text
    assert secret not in response.text and secret not in caplog.text
    assert bool(calls) == (scenario != 'invalid_context')
    assert academic_state(settings.database_path) == before
