import csv
import io
import json
import unittest
from copy import deepcopy
from fastapi.testclient import TestClient
from analytics.app import create_demo_app
from analytics.demo import DATASET_ID, demo_files


class AnalyticsApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_demo_app()
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.base = f'/api/datasets/{DATASET_ID}'

    def get(self, suffix, **params):
        response = self.client.get(self.base + suffix, params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_reproducible_csv_and_known_demo_numbers(self):
        self.assertEqual(demo_files(), demo_files())
        results, curriculum, metadata = demo_files()
        rows = list(csv.DictReader(io.StringIO(results.decode('utf-8'))))
        self.assertEqual(len(rows), 1440)
        self.assertEqual(len({r['student_id'] for r in rows}), 120)
        self.assertEqual(len({r['class_id'] for r in rows}), 4)
        self.assertEqual(len({r['textbook_id'] for r in rows}), 2)
        self.assertEqual(len(list(csv.DictReader(io.StringIO(curriculum.decode('utf-8'))))), 6)
        self.assertIn('Искусственные', json.loads(metadata)['name'])
        body = self.get('/overview')
        self.assertTrue(body['is_demo'])
        self.assertEqual(body['metrics']['n_post_results'], 720)
        self.assertEqual(body['metrics']['n_students'], 120)
        self.assertEqual(body['metrics']['n_complete_students'], 120)
        self.assertEqual(body['metrics']['pair_coverage'], 1)
        self.assertEqual(body['metrics']['n_paired_students'], 120)
        self.assertEqual(body['metrics']['paired_student_share'], 1)
        self.assertEqual(len(body['heatmap']), 24)
        proportions = next(t for t in body['topics'] if t['topic_id'] == 'proportions')
        self.assertEqual(proportions['mean_post_pct'], 64)
        self.assertEqual(proportions['below_threshold_share'], 0.4)
        self.assertTrue(proportions['problem_topic'])
        self.assertEqual(proportions['status'], 'needs_practice')

    def test_repeated_filters_change_entire_response(self):
        body = self.get('/overview', class_ids=['7A', '7B'], textbook_ids=['Учебник A'])
        self.assertEqual(body['metrics']['n_students'], 60)
        self.assertEqual(body['metrics']['n_post_results'], 360)
        self.assertEqual({t['n_post'] for t in body['topics']}, {60})
        self.assertEqual({c['class_id'] for c in body['heatmap']}, {'7A', '7B'})
        self.assertEqual(body['applied_filters']['class_ids'], ['7A', '7B'])
        by_book = self.get('/overview', textbook_ids=['Учебник A'])
        self.assertEqual({c['class_id'] for c in by_book['heatmap']}, {'7A', '7B'})

    def test_known_empty_filter_combination_returns_null(self):
        body = self.get('/overview', class_ids=['7A'], textbook_ids=['Учебник B'])
        self.assertEqual(body['metrics']['n_students'], 0)
        self.assertIsNone(body['metrics']['mean_post_pct'])
        self.assertEqual(len(body['topics']), 6)
        self.assertEqual(body['heatmap'], [])
        self.assertTrue(all(t['status'] == 'no_data' for t in body['topics']))

    def test_comparison_actual_fixture_matches_manual_example(self):
        body = self.get('/comparison', topic_id='equations', textbook_a='Учебник A', textbook_b='Учебник B')
        self.assertEqual(body['comparison_status'], 'comparable')
        self.assertEqual(body['difference_gain_pp'], 8)
        self.assertEqual(body['baseline_gap_pp'], 1)
        for key, pre, post in [('group_a', 52, 68), ('group_b', 53, 61)]:
            group = body[key]
            self.assertEqual(group['n_pairs'], 60)
            self.assertEqual(group['n_classes'], 2)
            self.assertEqual(group['n_teachers'], 2)
            self.assertEqual(group['mean_pre_paired_pct'], pre)
            self.assertEqual(group['mean_post_paired_pct'], post)
        self.assertIn('не доказывает', body['warnings'][0])

    def test_missing_pre_and_small_group_are_visible_over_http(self):
        self.app.state.store.records = [r for r in self.app.state.store.records
                                       if not (r['topic_id'] == 'equations' and r['textbook_id'] == 'Учебник B' and r['stage'] == 'pre')]
        body = self.get('/comparison', topic_id='equations', textbook_a='Учебник A', textbook_b='Учебник B')
        self.assertEqual(body['comparison_status'], 'insufficient_data')
        self.assertIsNone(body['difference_gain_pp'])
        self.assertIsNone(body['group_b']['mean_gain_pp'])
        self.assertEqual(body['group_b']['mean_post_pct'], 61)
        self.assertEqual(body['group_b']['pair_coverage'], 0)
        self.assertTrue(body['reasons'])

    def test_mixed_versions_show_slices_and_can_be_selected(self):
        for row in self.app.state.store.records:
            if row['topic_id'] == 'equations' and row['class_id'] == '7B':
                row['test_version'] = 'v2'
        body = self.get('/topics/equations')
        self.assertEqual(body['metrics']['status'], 'mixed_versions')
        self.assertIsNone(body['metrics']['mean_post_pct'])
        self.assertEqual(len(body['slices']), 2)
        self.assertEqual([s['n_post'] for s in body['slices']], [90, 30])
        selected = self.get('/topics/equations', test_version='v2')
        self.assertEqual(selected['metrics']['n_post'], 30)
        self.assertEqual(selected['metrics']['mean_post_pct'], 68)
        self.assertIsNone(self.get('/overview')['metrics']['mean_post_pct'])

    def test_unknown_filters_and_ids_have_structured_errors(self):
        for suffix, params, code in [
            ('/overview', {'class_ids': 'unknown'}, 422),
            ('/overview', {'textbook_ids': 'unknown'}, 422),
            ('/overview', {'test_version': 'unknown'}, 422),
            ('/topics/missing', {}, 404),
            ('/comparison', {}, 422),
            ('/comparison', {'topic_id': 'equations', 'textbook_a': 'Учебник A', 'textbook_b': 'Учебник A'}, 422),
        ]:
            with self.subTest(suffix=suffix, params=params):
                response = self.client.get(self.base + suffix, params=params)
                self.assertEqual(response.status_code, code, response.text)
                self.assertTrue({'code', 'message', 'details', 'total_errors'} <= response.json().keys())
        self.assertEqual(self.client.get('/api/datasets/missing/overview').status_code, 404)

    def test_duplicate_input_never_silently_changes_weights(self):
        self.app.state.store.records.append(deepcopy(self.app.state.store.records[0]))
        response = self.client.get(self.base + '/overview')
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['code'], 'DUPLICATE_RESULT')

    def test_openapi_exposes_response_models_and_array_filters(self):
        schema = self.client.get('/openapi.json').json()
        operation = schema['paths']['/api/datasets/{dataset_id}/overview']['get']
        self.assertEqual(operation['responses']['200']['content']['application/json']['schema']['$ref'], '#/components/schemas/Overview')
        self.assertIn('comparison_status', schema['components']['schemas']['Comparison']['properties'])
        self.assertIn('n_post_results', schema['components']['schemas']['OverviewMetrics']['properties'])
        self.assertIn('topic_name', schema['components']['schemas']['TopicMetrics']['properties'])
        self.assertEqual(schema['components']['schemas']['TopicMetrics']['properties']['status']['enum'][0], 'requires_attention')


if __name__ == '__main__':
    unittest.main()
