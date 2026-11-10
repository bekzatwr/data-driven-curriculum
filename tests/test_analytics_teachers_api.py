"""The workload endpoint uses complete stored data and the existing access rules."""
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient
from analytics.demo import demo_files
from backend.app.config import Settings
from backend.app.main import create_app


class TeachersApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings = Settings(database_path=Path(self.directory.name) / 'teachers.sqlite3')
        self.client = TestClient(create_app(self.settings))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.dataset_id = self.client.post('/api/datasets/demo').json()['dataset_id']
        self.path = f'/api/datasets/{self.dataset_id}/teachers'

    def test_full_demo_not_first_page_and_response_schema(self):
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body['total']['teachers'], 4)
        self.assertEqual(body['total']['students'], 120)
        self.assertEqual(body['total']['students_per_teacher'], 30)
        self.assertEqual(body['total']['hours_per_teacher'], 24)
        self.assertEqual(sum(t['n_post'] for t in body['teachers']), 720)
        self.assertEqual(sum(t['n_pairs'] for t in body['teachers']), 720)
        self.assertTrue(body['is_demo'])
        self.assertTrue(body['warnings'])
        self.assertIn('mean_post_pct', body['definitions'])
        self.assertTrue(self.client.get('/api/capabilities').json()['features']['teachers_api'])
        schema = self.client.get('/openapi.json').json()
        operation = schema['paths']['/api/datasets/{dataset_id}/teachers']['get']
        self.assertEqual(operation['responses']['200']['content']['application/json']['schema']['$ref'], '#/components/schemas/Teachers')

    def test_class_book_and_version_filters_are_shared_by_totals(self):
        response = self.client.get(self.path, params=[('class_ids', '7A'), ('class_ids', '7B'), ('test_version', 'v1')])
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body['total']['teachers'], 2)
        self.assertEqual(body['total']['students'], 60)
        self.assertEqual(body['hours_per_class'], 24)
        self.assertEqual([t['teacher_id'] for t in body['teachers']], ['T1', 'T2'])
        empty = self.client.get(self.path, params={'class_ids': '7A', 'textbook_ids': 'Учебник B'}).json()
        self.assertEqual(empty['teachers'], [])
        self.assertEqual(empty['total']['teachers'], 0)
        self.assertIsNone(empty['total']['hours_per_teacher'])
        self.assertEqual(empty['hours_per_class'], 24)

    def test_unknown_dataset_and_filters_are_structured_errors(self):
        self.assertEqual(self.client.get('/api/datasets/unknown/teachers').status_code, 404)
        for key in ('class_ids', 'textbook_ids', 'test_version'):
            response = self.client.get(self.path, params={key: 'unknown'})
            self.assertEqual(response.status_code, 422, response.text)
            self.assertTrue({'code', 'message', 'details', 'total_errors'} <= response.json().keys())

    def test_uploaded_dataset_hidden_in_public_demo_and_readable_locally(self):
        results, topics, metadata = demo_files()
        response = self.client.post('/api/datasets/import?dry_run=false', data={'metadata': metadata}, files={
            'results_file': ('results.csv', results), 'curriculum_file': ('curriculum.csv', topics)})
        self.assertEqual(response.status_code, 201, response.text)
        path = f"/api/datasets/{response.json()['dataset_id']}/teachers"
        self.assertFalse(self.client.get(path).json()['is_demo'])
        with TestClient(create_app(replace(self.settings, read_only_demo=True))) as public:
            self.assertEqual(public.get(path).status_code, 404)
            self.assertEqual(public.get(self.path).status_code, 200)
        with TestClient(create_app(self.settings)) as restarted:
            self.assertEqual(restarted.get(self.path).json(), self.client.get(self.path).json())


if __name__ == '__main__':
    unittest.main()
