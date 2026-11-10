"""Real localhost HTTP acceptance against a combined checkout, with process restart.

Usage: python qa/check_http_e2e.py ../aidana-p1-e2e
The checkout must contain collab, this planner, and built web/dist.
"""
import csv
from contextlib import closing
import io
import json
import os
from pathlib import Path
import socket
import sqlite3
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
               'AI_ACCOUNT_VERIFIED': 'false', 'P1_COMMENTS_ENABLED': 'true', 'PUBLIC_DEMO': 'false'}
        # Windows venv python.exe is a redirector; terminating it may orphan the
        # real server. Launch the base executable with this venv's dependencies.
        env['PYTHONPATH'] = os.pathsep.join(filter(None, [str(root), os.environ.get('PYTHONPATH'), sysconfig.get_path('purelib')]))
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
                    raise RuntimeError('Server failed to start: ' + (Path(temporary) / 'server.log').read_text(encoding='utf-8')[-4000:])
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
            assert client.get('/api/datasets').json()['total'] == 0
            assert client.post('/api/datasets/import', content=b'invalid', headers={'Content-Type': 'multipart/form-data'}).status_code == 400
            assert client.get('/api/datasets/missing').status_code == 404
            results, curriculum, metadata = demo_files()
            files = {'results_file': ('results.csv', results), 'curriculum_file': ('curriculum.csv', curriculum)}
            assert client.post('/api/datasets/import?dry_run=true', files=files, data={'metadata': metadata}).status_code == 200
            imported = client.post('/api/datasets/import?dry_run=false', files=files, data={'metadata': metadata})
            assert imported.status_code == 201, imported.text
            dataset = imported.json()['dataset_id']
            duplicate = client.post('/api/datasets/import?dry_run=false', files=files, data={'metadata': metadata})
            assert duplicate.status_code == 200 and duplicate.json()['dataset_id'] == dataset
            assert client.get('/api/datasets').json()['total'] == 1
            path = f'/api/datasets/{dataset}'
            overview = client.get(path + '/overview')
            assert overview.status_code == 200 and overview.json()['metrics']['n_students'] == 120
            assert client.get(path + '/topics/equations').status_code == 200
            comparison = client.get(path + '/comparison', params={'topic_id': 'equations', 'textbook_a': 'Учебник A', 'textbook_b': 'Учебник B'})
            assert comparison.status_code == 200 and comparison.json()['difference_gain_pp'] == 8
            teachers = client.get(path + '/teachers')
            assert teachers.status_code == 200
            assert len(teachers.json()['teachers']) == 4
            assert all(t['students'] == 30 and t['upcoming_hours'] == 24 for t in teachers.json()['teachers'])
            p0 = client.post(path + '/plans/preview', json={'class_id': '7A'})
            assert p0.status_code == 200 and p0.json()['algorithm_version'] == 'rules_v1'
            p0_items = p0.json()['items']
            p0_hours = {i['topic_id']: i['proposed_hours'] for i in p0_items}
            p0_donor = next(i for i in p0_items if not i['is_locked'] and i['proposed_hours'] > max(i['min_hours'], i['current_hours'] - 2))
            p0_recipient = next(i for i in p0_items if i != p0_donor and not i['is_locked'] and i['proposed_hours'] < min(i['max_hours'], i['current_hours'] + 2))
            p0_hours[p0_donor['topic_id']] -= 1
            p0_hours[p0_recipient['topic_id']] += 1
            p0_saved_response = client.post(path + '/plans', json={'class_id': '7A', 'hours_by_topic': p0_hours})
            assert p0_saved_response.status_code == 201, p0_saved_response.text
            p0_saved = p0_saved_response.json()
            assert p0_saved['algorithm_version'] == 'rules_v1' and p0_saved['manually_modified']
            p0_report = '/api/plans/' + p0_saved['plan_id']
            p0_exported = client.get(p0_report + '/export.csv').content
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
            assert saved['algorithm_version'] == 'period_v1'
            report = '/api/plans/' + saved['plan_id']
            assert client.get(report).json() == saved
            exported = client.get(report + '/export.csv').content
            rows = list(csv.DictReader(io.StringIO(exported.decode('utf-8-sig'))))
            assert {r['topic_id']: int(r['proposed_hours']) for r in rows} == hours
            comment = client.post(path + '/comments', json={'target_type': 'plan_topic',
                'target_id': saved['plan_id'] + ':fractions', 'author_name': 'Synthetic QA',
                'author_role': 'methodist', 'text': 'HTTP E2E проверка'})
            assert comment.status_code == 201, comment.text
            with closing(sqlite3.connect(database)) as db, db:
                before = db.execute('SELECT COUNT(*) FROM aidana_plan_snapshots').fetchone()[0]
                assert before == 2
            assert client.post(path + '/plans', json={'class_id': '7A', 'hours_by_topic': {}}).status_code == 422
            with closing(sqlite3.connect(database)) as db, db:
                assert db.execute('SELECT COUNT(*) FROM aidana_plan_snapshots').fetchone()[0] == before
                db.execute("CREATE TRIGGER final_http_reject_plan AFTER INSERT ON aidana_plan_snapshots BEGIN SELECT RAISE(FAIL, 'synthetic HTTP failure'); END")
            assert client.post(path + '/plans', json={'class_id': '7A'}).status_code == 500
            with closing(sqlite3.connect(database)) as db, db:
                assert db.execute('SELECT COUNT(*) FROM aidana_plan_snapshots').fetchone()[0] == before
                db.execute('DROP TRIGGER final_http_reject_plan')
                assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
                assert db.execute('PRAGMA foreign_key_check').fetchall() == []
            assert client.get('/api/ai/status').json()['configured'] is False
            offline = client.post(path + '/ai/explain', json={'kind': 'plan', 'context': {'plan_id': saved['plan_id']}})
            assert offline.status_code == 503 and offline.json()['code'] == 'AI_NOT_CONFIGURED'
            stop()
            try:
                client.get('/api/health')
                raise AssertionError('A stopped server must not return success')
            except httpx.ConnectError:
                pass
            start()
            assert client.get(report).json() == saved
            assert client.get(report + '/export.csv').content == exported
            assert client.get(path + '/comments').json()['items'][0] == comment.json()
            assert client.get(p0_report).json() == p0_saved
            assert client.get(p0_report + '/export.csv').content == p0_exported
            assert client.get(path + '/teachers').json() == teachers.json()
            assert 'text/html' in client.get('/plans/' + saved['plan_id']).headers['content-type']
            observation = {'passed': True, 'browser_e2e': False, 'synthetic_data_only': True,
                'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                'source_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip()),
                'dataset_id': dataset, 'rules_plan_id': p0_saved['plan_id'], 'period_plan_id': saved['plan_id'],
                'students': 120, 'comparison_gain_pp': 8, 'teachers': 4, 'hours': 24,
                'checks': ['CSV dry-run/import/dedup', 'overview/topics/comparison/Teachers',
                    'rules_v1 and period_v1 preview/manual/save/JSON/CSV', 'comments and AI offline',
                    '400/404/422/500/503', 'real SQLite rollback/integrity/FKs',
                    'stopped server connection failure and retry after restart', 'SPA HTML for saved plan'],
                'ai_provider_calls': 0}
            if len(sys.argv) > 2:
                output = Path(sys.argv[2]); output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(observation, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            print(json.dumps(observation, ensure_ascii=False, indent=2))
            print('PASS: real HTTP, SQLite, restart and actual frontend HTML; browser interaction NOT covered.')
        finally:
            stop()
            client.close()
            log.close()


if __name__ == '__main__':
    main()
