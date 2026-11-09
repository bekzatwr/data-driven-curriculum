import csv
import io
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from planner.app import create_demo_app
from planner.demo import DemoStore
from planner.models import PlanRequest, Settings
from planner.rules import allocate_hours, validate_hours, PlanError
from planner.service import preview


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'plans.db'
        self.app = create_demo_app(self.path)
        self.client = TestClient(self.app)
        self.url = '/api/datasets/aidana-demo/plans'

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_expected_allocation_and_conservation(self):
        result = self.client.post(self.url+'/preview', json={'class_id': '7A'}).json()
        self.assertEqual([i['proposed_hours'] for i in result['items']], [6, 6, 4, 4, 2, 2])
        self.assertEqual(result['total_hours'], 24)
        self.assertEqual(result['transfers'][0], {'from_topic_id': 't6', 'to_topic_id': 't1', 'hours': 1})
        self.assertTrue(all(t['hours'] == 1 for t in result['transfers']))

    def test_constraints_no_donors_locks_small_sample_and_versions(self):
        source = DemoStore()
        for topic in source.topics:
            topic['is_locked'] = True
        result = preview(source, 'aidana-demo', PlanRequest(class_id='7A'))
        self.assertFalse(result['transfers'])
        self.assertTrue(all(i['delta'] == 0 for i in result['items']))
        source = DemoStore()
        source.results = [r for r in source.results if int(r['student_id'].split('-')[1]) < 10]
        self.assertFalse(preview(source, 'aidana-demo', PlanRequest(class_id='7A'))['transfers'])
        source = DemoStore()
        for row in source.results:
            if row['topic_id'] == 't1' and row['student_id'].endswith('01'):
                row['test_version'] = 'v2'
        result = preview(source, 'aidana-demo', PlanRequest(class_id='7A'))
        self.assertIsNone(result['items'][0]['mean_post_pct'])
        self.assertEqual(result['items'][0]['delta'], 0)
        chosen = preview(source, 'aidana-demo', PlanRequest(class_id='7A', test_versions={'t1':'v1'}))
        self.assertEqual(chosen['items'][0]['n_post'], 29)

    def test_threshold_tie_and_zero_change(self):
        topics = DemoStore().topics[:3]
        metrics = [{'topic_id': t['topic_id'], 'n_post': 30, 'mean_post_pct': score, 'single_version': True}
                   for t, score in zip(topics, (60,60,80))]
        result = allocate_hours(metrics, topics)
        self.assertEqual([i['proposed_hours'] for i in result['items']], [5,5,2])
        self.assertEqual(result['transfers'][0]['to_topic_id'], 't1')
        self.assertFalse(allocate_hours(metrics, topics, {'max_change': 0})['transfers'])

    def test_manual_validation_and_restart_csv(self):
        hours = {f't{i}': 4 for i in range(1,7)}
        payload = {'class_id':'7A', 'hours_by_topic':hours}
        saved = self.client.post(self.url, json=payload)
        self.assertEqual(saved.status_code, 201)
        plan = saved.json()
        self.assertTrue(plan['manually_modified'])
        self.app.state.store.topics[0]['topic_name'] = 'Changed after saving'
        with TestClient(create_demo_app(self.path)) as restarted:
            self.assertEqual(restarted.get('/api/plans/'+plan['plan_id']).json(), plan)
            response = restarted.get('/api/plans/'+plan['plan_id']+'/export.csv')
            rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
            self.assertEqual(sum(int(r['proposed_hours']) for r in rows), 24)
            self.assertEqual(rows[0]['topic_name'], 'Дроби')
        for bad in ({**hours, 't1': 5}, {**hours, 't1': True}, {**hours, 't1': 1, 't2':7}, {'t1':4}):
            self.assertEqual(self.client.post(self.url, json={**payload, 'hours_by_topic':bad}).status_code,422)
        locked = {**payload, 'constraints':{'t1':{'is_locked':True}}, 'hours_by_topic':{**hours,'t1':5,'t2':3}}
        self.assertEqual(self.client.post(self.url, json=locked).status_code,422)

    def test_invalid_and_missing_objects(self):
        for payload in ({'class_id':'missing'}, {'class_id':'7A','constraints':{'unknown':{}}},
                        {'class_id':'7A','constraints':{'t1':{'min_hours':9}}},
                        {'class_id':'7A','settings':{'target_pct':90,'donor_pct':80}},
                        {'class_id':'7A','test_versions':{'t1':'absent'}}):
            self.assertEqual(self.client.post(self.url+'/preview',json=payload).status_code,422)
        self.assertEqual(self.client.get('/api/plans/absent').status_code,404)
        self.assertEqual(self.client.post('/api/datasets/missing/plans/preview',json={'class_id':'7A'}).status_code,404)

    def test_many_constraint_combinations(self):
        import random
        rng = random.Random(42)
        for _ in range(200):
            topics = DemoStore().topics
            for t in topics:
                t['importance'] = rng.randint(1,3)
                t['is_locked'] = rng.choice([True,False])
            metrics = [{'topic_id': t['topic_id'], 'n_post':rng.choice([0,9,10,30]),
                        'mean_post_pct':rng.randint(0,100), 'single_version':True} for t in topics]
            result = allocate_hours(metrics, topics)
            validate_hours(result['items'], {i['topic_id']:i['proposed_hours'] for i in result['items']}, Settings())

    def test_csv_formula_protection(self):
        self.app.state.store.topics[0]['topic_name'] = '=SUM(1,2)'
        plan = self.client.post(self.url,json={'class_id':'7A'}).json()
        response = self.client.get('/api/plans/'+plan['plan_id']+'/export.csv')
        rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(rows[0]['topic_name'], "'=SUM(1,2)")


if __name__ == '__main__':
    unittest.main()
