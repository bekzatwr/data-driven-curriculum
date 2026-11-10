"""Teacher-ID completeness is scoped by real imported data and HTTP filters."""
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from analytics.demo import METADATA, RESULT_FIELDS, TOPIC_FIELDS, _csv
from backend.app.config import Settings
from backend.app.main import create_app


class TeacherAttributionApiTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.client = TestClient(create_app(Settings(database_path=Path(temporary.name) / 'attribution.sqlite3')))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        cases = [
            ('A', 'S1', 'C1', 'T1', 'Book A', 't1', 'pre'),
            ('A', 'S1', 'C1', 'T1', 'Book A', 't1', 'post'),
            ('B', 'S1', 'C1', 'T1', 'Book A', 't1', 'pre'),
            ('B', 'S1', 'C1', None, 'Book B', 't2', 'post'),
            ('C', 'S1', 'C1', None, 'Book A', 't1', 'pre'),
            ('C', 'S1', 'C1', None, 'Book A', 't1', 'post'),
            ('D', 'S2', 'C2', 'Не указан', 'Book A', 't1', 'post'),
            ('E', 'S2', 'C2', None, 'Book A', 't1', 'post'),
        ]
        rows = [dict(student_id=student, school_id=school, class_id=classroom, teacher_id=teacher,
                     textbook_id=book, topic_id=topic, stage=stage, test_version='v1', max_score=100,
                     score=30 if stage == 'pre' else 60,
                     tested_at='2026-09-01' if stage == 'pre' else '2026-10-01')
                for student, school, classroom, teacher, book, topic, stage in cases]
        topics = [dict(topic_id=f't{i}', topic_name=f'Topic {i}', topic_order=i,
                       current_hours=2, min_hours=0, max_hours=4, importance=1, is_locked=False)
                  for i in (1, 2)]
        response = self.client.post('/api/datasets/import?dry_run=false',
            data={'metadata': json.dumps(METADATA)}, files={
                'results_file': ('results.csv', _csv(RESULT_FIELDS, rows)),
                'curriculum_file': ('curriculum.csv', _csv(TOPIC_FIELDS, topics)),
            })
        self.assertEqual(response.status_code, 201, response.text)
        self.path = f"/api/datasets/{response.json()['dataset_id']}/teachers"

    def get(self, **params):
        response = self.client.get(self.path, params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_school_and_total_categories_conserve_unique_students(self):
        body = self.get()
        attribution = body['total']['teacher_attribution']
        self.assertEqual(attribution, {
            'fully_attributed_students': 2, 'partially_attributed_students': 1,
            'unattributed_students': 2, 'fully_attributed_student_share': 0.4, 'missing_teacher_rows': 4,
        })
        self.assertEqual(body['total']['students'], 5)
        self.assertEqual(body['total']['students_per_teacher'], 2.5)
        self.assertEqual(attribution['missing_teacher_rows'], body['missing_teacher_rows'])
        schools = {school['school_id']: school for school in body['schools']}
        self.assertEqual(schools['S1']['teacher_attribution'], {
            'fully_attributed_students': 1, 'partially_attributed_students': 1,
            'unattributed_students': 1, 'fully_attributed_student_share': 1 / 3, 'missing_teacher_rows': 3,
        })
        self.assertEqual(schools['S2']['teacher_attribution'], {
            'fully_attributed_students': 1, 'partially_attributed_students': 0,
            'unattributed_students': 1, 'fully_attributed_student_share': 0.5, 'missing_teacher_rows': 1,
        })
        for key in ('fully_attributed_students', 'partially_attributed_students', 'unattributed_students', 'missing_teacher_rows'):
            self.assertEqual(sum(school['teacher_attribution'][key] for school in body['schools']), attribution[key])
        self.assertTrue(any(teacher['teacher_id'] == 'Не указан' and not teacher['is_missing_teacher']
                            for teacher in body['teachers']))
        schema = self.client.get('/openapi.json').json()['components']['schemas']
        self.assertEqual(schema['SchoolWorkload']['properties']['teacher_attribution']['$ref'],
                         '#/components/schemas/TeacherAttribution')

    def test_filters_reclassify_partial_pupils_and_preserve_empty_null(self):
        known = self.get(textbook_ids='Book A')['total']['teacher_attribution']
        self.assertEqual(known, {
            'fully_attributed_students': 3, 'partially_attributed_students': 0,
            'unattributed_students': 2, 'fully_attributed_student_share': 0.6, 'missing_teacher_rows': 3,
        })
        missing = self.get(textbook_ids='Book B')['total']
        self.assertEqual(missing['teacher_attribution'], {
            'fully_attributed_students': 0, 'partially_attributed_students': 0,
            'unattributed_students': 1, 'fully_attributed_student_share': 0, 'missing_teacher_rows': 1,
        })
        self.assertEqual(missing['teachers'], 0)
        self.assertIsNone(missing['students_per_teacher'])
        empty = self.get(class_ids='C2', textbook_ids='Book B')
        self.assertEqual(empty['schools'], [])
        self.assertEqual(empty['total']['teacher_attribution'], {
            'fully_attributed_students': 0, 'partially_attributed_students': 0,
            'unattributed_students': 0, 'fully_attributed_student_share': None, 'missing_teacher_rows': 0,
        })


if __name__ == '__main__':
    unittest.main()
