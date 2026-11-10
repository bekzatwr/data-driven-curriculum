"""The workload endpoint uses complete stored data and the existing access rules."""
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient
from analytics.demo import METADATA, RESULT_FIELDS, TOPIC_FIELDS, _csv, demo_files, demo_records
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
        self.assertEqual([t['n_paired_students'] for t in body['teachers']], [30] * 4)
        self.assertTrue(all(t['paired_student_share'] == 1 for t in body['teachers']))
        self.assertTrue(all(t['topic_count'] == 6 and t['post_topic_count'] == 6 for t in body['teachers']))
        self.assertTrue(all(t['n_complete_students'] == 30 and t['complete_student_share'] == 1 for t in body['teachers']))
        self.assertTrue(body['is_demo'])
        self.assertTrue(body['warnings'])
        self.assertIn('mean_post_pct', body['definitions'])
        self.assertTrue(self.client.get('/api/capabilities').json()['features']['teachers_api'])
        schema = self.client.get('/openapi.json').json()
        operation = schema['paths']['/api/datasets/{dataset_id}/teachers']['get']
        self.assertEqual(operation['responses']['200']['content']['application/json']['schema']['$ref'], '#/components/schemas/Teachers')
        fields = schema['components']['schemas']['TeacherMetrics']
        self.assertIn('n_paired_students', fields['required'])
        self.assertIn('paired_student_share', fields['required'])
        self.assertIn('mean_pre_paired_pct', fields['required'])
        self.assertIn('mean_post_paired_pct', fields['required'])
        for field in ('topic_count', 'post_topic_count', 'n_complete_students', 'complete_student_share'):
            self.assertIn(field, fields['required'])

    def test_valid_csv_exposes_one_tested_topic_in_hundred_topic_curriculum(self):
        topics = [{'topic_id': f't{i:03d}', 'topic_name': f'Topic {i}', 'topic_order': i,
                   'current_hours': 1, 'min_hours': 0, 'max_hours': 3, 'importance': 1,
                   'is_locked': False} for i in range(100)]
        records = [{'student_id': f's{i}', 'school_id': 'S1', 'class_id': '7A', 'teacher_id': 'T1',
                    'textbook_id': 'A', 'topic_id': 't000', 'test_version': 'v1', 'stage': stage,
                    'score': score, 'max_score': 100, 'tested_at': date}
                   for i in range(30)
                   for stage, score, date in (('pre', 80, '2026-09-01'), ('post', 100, '2026-10-01'))]
        response = self.client.post('/api/datasets/import?dry_run=false',
            data={'metadata': json.dumps(METADATA)}, files={
                'results_file': ('results.csv', _csv(RESULT_FIELDS, records)),
                'curriculum_file': ('curriculum.csv', _csv(TOPIC_FIELDS, topics)),
            })
        self.assertEqual(response.status_code, 201, response.text)
        response = self.client.get(f"/api/datasets/{response.json()['dataset_id']}/teachers",
                                   params={'class_ids': '7A', 'test_version': 'v1'})
        self.assertEqual(response.status_code, 200, response.text)
        teacher = response.json()['teachers'][0]
        self.assertEqual(teacher['mean_post_pct'], 100)
        self.assertEqual(teacher['mean_pre_paired_pct'], 80)
        self.assertEqual(teacher['mean_post_paired_pct'], 100)
        self.assertEqual(teacher['mean_gain_pp'], 20)
        self.assertEqual(teacher['pair_coverage'], 1)
        self.assertEqual(teacher['paired_student_share'], 1)
        self.assertEqual(teacher['topic_count'], 100)
        self.assertEqual(teacher['post_topic_count'], 1)
        self.assertEqual(teacher['n_complete_students'], 0)
        self.assertEqual(teacher['complete_student_share'], 0)
        self.assertTrue(any('Неполное покрытие учебного плана' in warning for warning in teacher['warnings']))

    def test_valid_csv_keeps_paired_means_separate_from_all_post_mean(self):
        topics, records = demo_records()
        paired = [record for record in records if record['student_id'] == 'S001'
                  and record['topic_id'] == 'fractions']
        paired = [{**record, 'score': 40 if record['stage'] == 'pre' else 60} for record in paired]
        unpaired = next(record for record in records if record['student_id'] == 'S002'
                        and record['topic_id'] == 'fractions' and record['stage'] == 'post')
        sample = [*paired, {**unpaired, 'score': 100}]
        response = self.client.post('/api/datasets/import?dry_run=false',
            data={'metadata': json.dumps(METADATA)}, files={
                'results_file': ('results.csv', _csv(RESULT_FIELDS, sample)),
                'curriculum_file': ('curriculum.csv', _csv(TOPIC_FIELDS, topics)),
            })
        self.assertEqual(response.status_code, 201, response.text)
        response = self.client.get(f"/api/datasets/{response.json()['dataset_id']}/teachers",
                                   params={'class_ids': '7A'})
        self.assertEqual(response.status_code, 200, response.text)
        teacher = response.json()['teachers'][0]
        self.assertEqual(teacher['n_post'], 2)
        self.assertEqual(teacher['n_pairs'], 1)
        self.assertEqual(teacher['mean_post_pct'], 80)
        self.assertEqual(teacher['mean_pre_paired_pct'], 40)
        self.assertEqual(teacher['mean_post_paired_pct'], 60)
        self.assertEqual(teacher['mean_gain_pp'], 20)

    def test_valid_csv_reports_one_paired_pupil_across_six_topics(self):
        topics, records = demo_records()
        # All 120 pupils keep their post tests; only S001 has pre for six topics.
        records = [record for record in records if record['stage'] == 'post' or record['student_id'] == 'S001']
        response = self.client.post('/api/datasets/import?dry_run=false',
            data={'metadata': json.dumps(METADATA)}, files={
                'results_file': ('results.csv', _csv(RESULT_FIELDS, records)),
                'curriculum_file': ('curriculum.csv', _csv(TOPIC_FIELDS, topics)),
            })
        self.assertEqual(response.status_code, 201, response.text)
        path = f"/api/datasets/{response.json()['dataset_id']}/teachers"
        response = self.client.get(path, params={'class_ids': '7A'})
        self.assertEqual(response.status_code, 200, response.text)
        teacher = response.json()['teachers'][0]
        self.assertEqual(teacher['n_post'], 180)
        self.assertEqual(teacher['n_post_students'], 30)
        self.assertEqual(teacher['n_pairs'], 6)
        self.assertEqual(teacher['n_paired_students'], 1)
        self.assertAlmostEqual(teacher['paired_student_share'], 1 / 30)
        self.assertAlmostEqual(teacher['mean_gain_pp'], 73 / 6)
        self.assertTrue(any('Мало учеников в парной выборке' in warning for warning in teacher['warnings']))
        other = self.client.get(path, params={'class_ids': '7B'}).json()['teachers'][0]
        self.assertEqual(other['n_paired_students'], 0)
        self.assertEqual(other['paired_student_share'], 0)
        self.assertIsNone(other['mean_gain_pp'])

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
