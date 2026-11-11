"""Release gates against a real local HTTP server, including failure responses."""
from contextlib import contextmanager
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
from urllib.parse import urlsplit

import pytest

from scripts.check_release import check_release, compare_observations


@contextmanager
def service(overrides=None):
    html = b'<html><div id="root"></div><script type="module" src="/assets/app.js"></script></html>'
    def json_response(value):
        return (200, 'application/json', json.dumps(value).encode())
    routes = {
        '/api/health': json_response({'database': 'ok', 'read_only_demo': True}),
        '/api/capabilities': json_response({'mode': 'read_only_demo', 'features': {
            **dict.fromkeys(('csv_import', 'import_preview', 'package_restore', 'plan_save',
                             'comments_write', 'ai_explain'), False),
            **dict.fromkeys(('analytics', 'textbook_comparison', 'plan_preview', 'plan_report', 'plan_csv'), True)}}),
        '/api/ai/status': json_response({'configured': False}),
        '/openapi.json': json_response({'paths': {path: {'get': {}} for path in (
            '/api/datasets/{dataset_id}/overview', '/api/datasets/{dataset_id}/topics/{topic_id}',
            '/api/datasets/{dataset_id}/comparison')}}),
        '/': (200, 'text/html', html),
        '/assets/app.js': (200, 'text/javascript', b'// test fixture module'),
        '/plans/demo-plan': (200, 'text/html', html),
        '/api/plans/demo-plan': json_response({'plan_id': 'demo-plan', 'dataset_id': 'synthetic', 'is_demo': True}),
        '/api/plans/demo-plan/export.csv': (200, 'text/csv', b'\xef\xbb\xbftopic,hours\nfractions,6\n'),
    }
    routes.update(overrides or {})
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            requests.append(('GET', self.path))
            code, content_type, body = routes.get(self.path, (404, 'text/plain', b'missing'))
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            if code == 302:
                self.send_header('Location', body.decode())
            self.end_headers()
            self.wfile.write(body)

    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield 'http://127.0.0.1:' + str(server.server_port), requests
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_public_precheck_reads_real_http_without_claiming_https_or_full_e2e():
    with service() as (base, requests):
        result = check_release(base, plan_id='demo-plan')
    assert result['technical_precheck_passed'], result
    assert result['https_verified'] is False
    assert result['observed']['spa_deep_link'] is True
    assert result['observed']['report_sha256'] and result['observed']['csv_sha256']
    assert all(method == 'GET' for method, _ in requests)
    assert 'browser/mobile acceptance' in result['still_required']


@pytest.mark.parametrize('url', [
    'http://127.0.0.1:9', 'https://user:secret@example.test',
    'https://example.test?token=secret', 'https://example.test/path', 'file:///tmp/db',
    'https://user:secret@[',
])
def test_invalid_or_insecure_url_is_rejected_before_network(url):
    class NoNetwork:
        def open(self, *_args, **_kwargs):
            pytest.fail('Invalid URL must not be contacted')
    result = check_release(url, require_https=True, opener=NoNetwork())
    assert not result['technical_precheck_passed']
    assert not result['https_verified']
    assert 'secret' not in json.dumps(result)


@pytest.mark.parametrize('path,response,reason', [
    ('/api/health', (503, 'text/plain', b'private upstream body'), 'HTTPError'),
    ('/api/ai/status', (200, 'application/json', b'{"configured":true}'), 'AI must be offline'),
    ('/api/capabilities', (200, 'application/json', b'{"mode":"read_only_demo","features":{"comments_write":true}}'), 'public policy: comments_write'),
    ('/', (200, 'text/html', b'<h1>packaging probe only</h1>'), 'Real React build'),
    ('/assets/app.js', (200, 'text/html', b'<html>SPA fallback</html>'), 'Unexpected content type'),
    ('/plans/demo-plan', (302, 'text/plain', b'http://127.0.0.1:9/'), 'Unexpected redirect'),
    ('/api/plans/demo-plan', (200, 'application/json', b'{"plan_id":"demo-plan","is_demo":false}'), 'synthetic-data flag'),
    ('/api/plans/demo-plan/export.csv', (200, 'text/csv', b'no BOM'), 'CSV UTF-8 BOM'),
    ('/', (200, 'text/html', b'<div id="root"></div><script type="module" src="https://unrequested.test/x.js"></script>'), 'this service origin'),
])
def test_unready_service_is_not_reported_as_ready(path, response, reason):
    with service({path: response}) as (base, requests):
        result = check_release(base, plan_id='demo-plan')
    assert not result['technical_precheck_passed']
    assert any(reason in item for item in result['blockers']), result
    assert 'private upstream body' not in json.dumps(result)
    assert all(urlsplit(path).netloc == '' for _, path in requests)


def test_network_timeout_is_actionable_failure_not_success():
    class Timeout:
        def open(self, *_args, **_kwargs):
            raise TimeoutError('private connection details')
    result = check_release('https://example.test', require_https=True, opener=Timeout())
    assert not result['technical_precheck_passed'] and not result['https_verified']
    assert result['blockers'] == ['HTTP/precheck failure (TimeoutError)']


def test_baseline_comparison_detects_lost_or_changed_saved_data():
    with service() as (base, _):
        before = check_release(base, plan_id='demo-plan')
        after = check_release(base, plan_id='demo-plan')
    compare_observations(after, before)
    assert after['saved_report_matches_baseline']
    changed = deepcopy(after)
    changed['observed']['csv_sha256'] = 'different'
    compare_observations(changed, before)
    assert not changed['technical_precheck_passed']
    assert not changed['saved_report_matches_baseline']
    wrong = deepcopy(before)
    wrong['plan_id'] = 'another-plan'
    compare_observations(after, wrong)
    assert not after['technical_precheck_passed']


def test_public_ai_requires_explicit_operator_opt_in():
    ai_on = {
        '/api/ai/status': (200, 'application/json', json.dumps({'configured': True}).encode()),
        '/api/capabilities': (200, 'application/json', json.dumps({'mode': 'read_only_demo', 'features': {
            **dict.fromkeys(('csv_import', 'import_preview', 'package_restore', 'plan_save', 'comments_write'), False),
            'ai_explain': True,
            **dict.fromkeys(('analytics', 'textbook_comparison', 'plan_preview', 'plan_report', 'plan_csv'), True)}}).encode()),
    }
    with service(ai_on) as (base, _):
        strict = check_release(base)
        allowed = check_release(base, allow_public_ai=True)
    assert not strict['technical_precheck_passed']
    assert 'AI must be offline in public demo' in strict['blockers']
    assert allowed['technical_precheck_passed'], allowed
    assert allowed['observed']['public_ai_explain'] is True


def test_public_ai_opt_in_never_relaxes_write_policy():
    writes_open = {'/api/capabilities': (200, 'application/json', json.dumps({'mode': 'read_only_demo', 'features': {
        **dict.fromkeys(('csv_import', 'import_preview', 'package_restore', 'plan_save'), False),
        'comments_write': True, 'ai_explain': True,
        **dict.fromkeys(('analytics', 'textbook_comparison', 'plan_preview', 'plan_report', 'plan_csv'), True)}}).encode())}
    with service(writes_open) as (base, _):
        result = check_release(base, allow_public_ai=True)
    assert 'public policy: comments_write' in result['blockers']
