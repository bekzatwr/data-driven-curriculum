"""Real localhost HTTP acceptance against a combined checkout, with process restart.

Usage: python qa/check_http_e2e.py ../aidana-p1-e2e
The checkout must contain collab, this planner, and built web/dist.
"""
import csv
import io
import os
from pathlib import Path
import socket
import subprocess
import sys
import sysconfig
import tempfile
import time

import httpx


def main():
    root = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(root))
    from backend.app.demo import demo_files
    with tempfile.TemporaryDirectory(prefix='aidana-http-') as temporary:
        database = Path(temporary) / 'test.sqlite3'
        env = {**os.environ, 'DATABASE_PATH': str(database), 'READ_ONLY_DEMO': 'false',
               'WEB_DIST_DIR': str(root / 'web/dist'), 'AI_ENABLED': 'false',
               'AI_ACCOUNT_VERIFIED': 'false', 'P1_COMMENTS_ENABLED': 'true'}
        # Windows venv python.exe is a redirector; terminating it may orphan the
        # real server. Launch the base executable with this venv's dependencies.
        env['PYTHONPATH'] = str(root) + os.pathsep + sysconfig.get_path('purelib')
        for key in ('GROQ_API_KEY', 'GEMINI_API_KEY'):
            env.pop(key, None)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        log = open(Path(temporary) / 'server.log', 'w', encoding='utf-8')
        process = None
        client = httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=20, trust_env=False)

        def stop():
            nonlocal process
            if process is not None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                process = None

        def start():
            nonlocal process
            process = subprocess.Popen([getattr(sys, '_base_executable', sys.executable), '-m', 'uvicorn', 'backend.app.main:app',
                '--host', '127.0.0.1', '--port', str(port), '--no-proxy-headers'], cwd=root, env=env,
                stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError('Server failed to start')
                try:
                    if client.get('/api/health').status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                time.sleep(.1)
            raise RuntimeError('Server did not become healthy')

        try:
            start()
            assert 'text/html' in client.get('/').headers['content-type']
            results, curriculum, metadata = demo_files()
            files = {'results_file': ('results.csv', results), 'curriculum_file': ('curriculum.csv', curriculum)}
            assert client.post('/api/datasets/import?dry_run=true', files=files, data={'metadata': metadata}).status_code == 200
            imported = client.post('/api/datasets/import?dry_run=false', files=files, data={'metadata': metadata})
            assert imported.status_code == 201, imported.text
            dataset = imported.json()['dataset_id']
            path = f'/api/datasets/{dataset}'
            assert client.get(path + '/overview').status_code == 200
            assert client.get(path + '/topics/equations').status_code == 200
            assert client.get(path + '/comparison', params={'topic_id': 'equations', 'textbook_a': 'Учебник A', 'textbook_b': 'Учебник B'}).status_code == 200
            payload = {'class_id': '7A', 'settings': {'mode': 'period'}}
            preview = client.post(path + '/plans/preview', json=payload)
            assert preview.status_code == 200, preview.text
            items = preview.json()['items']
            hours = {i['topic_id']: i['proposed_hours'] for i in items}
            donor = next(i for i in items if not i['is_locked'] and i['proposed_hours'] > i['min_hours'])
            recipient = next(i for i in items if i != donor and not i['is_locked'] and i['proposed_hours'] < i['max_hours'])
            hours[donor['topic_id']] -= 1
            hours[recipient['topic_id']] += 1
            response = client.post(path + '/plans', json={**payload, 'hours_by_topic': hours})
            assert response.status_code == 201, response.text
            saved = response.json()
            assert saved['settings']['mode'] == 'period' and saved['manually_modified']
            report = '/api/plans/' + saved['plan_id']
            assert client.get(report).json() == saved
            exported = client.get(report + '/export.csv').content
            rows = list(csv.DictReader(io.StringIO(exported.decode('utf-8-sig'))))
            assert {r['topic_id']: int(r['proposed_hours']) for r in rows} == hours
            comment = client.post(path + '/comments', json={'target_type': 'plan_topic',
                'target_id': saved['plan_id'] + ':fractions', 'author_name': 'Synthetic QA',
                'author_role': 'methodist', 'text': 'HTTP E2E проверка'})
            assert comment.status_code == 201, comment.text
            assert client.get('/api/ai/status').json()['configured'] is False
            offline = client.post(path + '/ai/explain', json={'kind': 'plan', 'context': {'plan_id': saved['plan_id']}})
            assert offline.status_code == 503 and offline.json()['code'] == 'AI_NOT_CONFIGURED'
            stop()
            start()
            assert client.get(report).json() == saved
            assert client.get(report + '/export.csv').content == exported
            assert client.get(path + '/comments').json()['items'][0] == comment.json()
            print('PASS: two CSV imports, overview, topic, comparison, period, manual edit, save, JSON/CSV, comments, offline AI, real process restart; frontend HTML served.')
            print('Browser interaction is NOT covered by this HTTP check.')
        finally:
            stop()
            client.close()
            log.close()


if __name__ == '__main__':
    main()
