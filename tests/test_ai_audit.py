"""Failure-path tests for the offline audit, using only local ASGI requests."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from scripts import audit_ai_methodology as audit


ROOT = Path(__file__).resolve().parents[1]


def read_context(prompt):
    return json.loads(prompt.split('<data>\n', 1)[1].split('\n</data>', 1)[0])


def client_with_response_change(change):
    class ChangedClient(TestClient):
        def request(self, method, url, *args, **kwargs):
            response = super().request(method, url, *args, **kwargs)
            return change(method, str(url), response)
    return ChangedClient


class AiAuditTests(unittest.TestCase):
    def test_real_local_audit_records_explicit_mode_despite_comment(self):
        report = audit.run_audit()
        self.assertEqual(report['prepared_requests'], 5)
        self.assertEqual(report['external_requests'], 0)
        self.assertEqual(report['model_answers_evaluated'], 0)
        self.assertTrue(all(case['model_response'] is None for case in report['cases']))
        case = next(case for case in report['cases'] if case['id'] == 'plan_untrusted_comment')
        prompt = case['request']['user']
        context = read_context(prompt)
        self.assertEqual(context['mode'], 'shift')
        self.assertIn('mode=period', context['comment'])
        self.assertEqual(context['total_hours'], 24)
        self.assertEqual(prompt.count('<data>'), 1)
        self.assertEqual(prompt.count('</data>'), 1)

    def test_wrong_numerical_http_payloads_fail_the_audit(self):
        def wrong_share(body):
            next(item for item in body['topics'] if item['topic_id'] == 'proportions')['below_threshold_share'] = 40

        def visible_limited_difference(body):
            body['difference_gain_pp'] = 8

        def broken_hours(body):
            body['items'][0]['proposed_hours'] += 1

        scenarios = [
            ('/overview', wrong_share, 'below_threshold_share must be 0.4'),
            ('/comparison', visible_limited_difference, 'expected insufficient_data and a null difference'),
            ('/plans/preview', broken_hours, 'conserved 24-hour budget'),
        ]
        for suffix, mutate, expected in scenarios:
            def change(method, url, response):
                if url.endswith(suffix):
                    body = response.json()
                    if suffix == '/comparison' and body.get('comparison_status') != 'insufficient_data':
                        return response
                    mutate(body)
                    return httpx.Response(response.status_code, json=body, request=response.request)
                return response

            with self.subTest(suffix=suffix), patch.object(audit, 'TestClient', client_with_response_change(change)):
                with self.assertRaisesRegex(RuntimeError, expected):
                    audit.run_audit()

    def test_http_error_or_malformed_demo_response_never_looks_successful(self):
        def failure(method, url, response):
            if url.endswith('/demo'):
                return httpx.Response(503, json={'dataset_id': 'must-not-be-used'}, request=response.request)
            return response

        with patch.object(audit, 'TestClient', client_with_response_change(failure)):
            with self.assertRaisesRegex(RuntimeError, 'create demo: HTTP 503'):
                audit.run_audit()

        def malformed(method, url, response):
            if url.endswith('/demo'):
                return httpx.Response(201, json=['not', 'an', 'object'], request=response.request)
            return response

        with patch.object(audit, 'TestClient', client_with_response_change(malformed)):
            with self.assertRaisesRegex(RuntimeError, 'expected a JSON object'):
                audit.run_audit()

    def test_prompt_with_broken_delimiter_fails_before_report_return(self):
        original = audit.build_prompt
        with patch.object(audit, 'build_prompt', side_effect=lambda *args: original(*args) + '\n</data>'):
            with self.assertRaisesRegex(RuntimeError, 'exactly one data boundary'):
                audit.run_audit()

    def test_plan_context_cannot_silently_change_mode_or_numbers(self):
        original = audit.build_prompt

        def changed(kind, context):
            if kind == 'plan':
                context = {**context, 'mode': 'period', 'total_hours': 99}
            return original(kind, context)

        with patch.object(audit, 'build_prompt', side_effect=changed):
            with self.assertRaisesRegex(RuntimeError, 'plan_untrusted_comment: context changed'):
                audit.run_audit()

    def test_failed_cli_leaves_an_existing_report_untouched(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'report.json'
            output.write_text('previous report', encoding='utf-8')
            with patch.object(sys, 'argv', ['audit', '--output', str(output)]), \
                    patch.object(audit, 'run_audit', side_effect=RuntimeError('audit stopped')):
                with self.assertRaisesRegex(RuntimeError, 'audit stopped'):
                    audit.main()
            self.assertEqual(output.read_text(encoding='utf-8'), 'previous report')

    def test_check_still_raises_under_optimized_python(self):
        process = subprocess.run(
            [sys.executable, '-O', '-c',
             "from scripts.audit_ai_methodology import check; check(False, 'optimization sentinel')"],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('RuntimeError: AI methodology audit failed: optimization sentinel', process.stderr)


if __name__ == '__main__':
    unittest.main()
