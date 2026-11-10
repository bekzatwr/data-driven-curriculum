"""Validated CSV imports must produce the same metrics in analytics and plans."""
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from analytics.demo import METADATA, RESULT_FIELDS, TOPIC_FIELDS, demo_records
from analytics.topics import compute_topics
from backend.app.config import Settings
from backend.app.db import Store
from backend.app.validation import validate_upload
from planner.contracts import PlanPreview
from planner.models import PlanRequest
from planner.rules import PlanError
from planner.service import preview


def csv_bytes(fields, rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows({key: str(value).lower() if isinstance(value, bool) else value
                      for key, value in row.items()} for row in rows)
    return stream.getvalue().encode('utf-8')


class AnalyticsPlannerConsistencyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.settings = Settings(database_path=Path(temporary.name) / 'data.sqlite3')
        self.store = Store(self.settings.database_path)
        self.store.initialize()

    def imported(self, topics, records):
        upload = validate_upload(
            csv_bytes(RESULT_FIELDS, records), csv_bytes(TOPIC_FIELDS, topics),
            json.dumps(METADATA), self.settings,
        )
        dataset, _ = self.store.save_upload(upload)
        return dataset['id']

    def metric_and_item(self, dataset_id, topic_id, version=None):
        filters = {'class_ids': ['7A'], 'topic_ids': [topic_id]}
        versions = {}
        if version is not None:
            filters['test_version'] = version
            versions[topic_id] = version
        analytics = compute_topics(self.store.load_results(dataset_id), filters)[0]
        plan = preview(self.store, dataset_id, PlanRequest(class_id='7A', test_versions=versions))
        # The public planner contract must keep accepting its existing fields.
        PlanPreview.model_validate(plan)
        planned = next(metric for metric in plan['metrics'] if metric['topic_id'] == topic_id)
        for field in ('mean_post_pct', 'n_post', 'single_version', 'test_version', 'max_score'):
            self.assertEqual(analytics[field], planned[field], field)
        item = next(item for item in plan['items'] if item['topic_id'] == topic_id)
        return analytics, item

    def test_pre_only_other_version_blocks_transfer_until_version_selected(self):
        topics, records = demo_records()
        extra = dict(next(row for row in records if row['topic_id'] == 'fractions' and row['stage'] == 'pre'))
        extra.update(student_id='PRE-ONLY-V2', test_version='v2')
        dataset_id = self.imported(topics, records + [extra])
        metric, item = self.metric_and_item(dataset_id, 'fractions')
        self.assertEqual(metric['n_post'], 30)
        self.assertEqual(metric['status'], 'mixed_versions')
        self.assertIsNone(item['mean_post_pct'])
        self.assertFalse(item['automatic_eligible'])
        self.assertEqual(item['delta'], 0)
        selected, item = self.metric_and_item(dataset_id, 'fractions', 'v1')
        self.assertEqual(selected['mean_post_pct'], 48)
        self.assertTrue(item['automatic_eligible'])
        self.assertEqual(item['delta'], 2)
        for version in ('v2', 'unknown'):
            with self.subTest(version=version), self.assertRaises(PlanError):
                preview(self.store, dataset_id, PlanRequest(class_id='7A', test_versions={'fractions': version}))

    def test_pre_only_and_empty_topics_keep_missing_mean_and_zero_transfers(self):
        topics, records = demo_records()
        records = [row for row in records if row['topic_id'] != 'equations'
                   and not (row['topic_id'] == 'fractions' and row['stage'] == 'post')]
        dataset_id = self.imported(topics, records)
        for topic in ('fractions', 'equations'):
            with self.subTest(topic=topic):
                metric, item = self.metric_and_item(dataset_id, topic)
                self.assertEqual(metric['status'], 'no_data')
                self.assertEqual(metric['n_post'], 0)
                self.assertIsNone(item['mean_post_pct'])
                self.assertFalse(item['automatic_eligible'])
                self.assertEqual(item['delta'], 0)

    def test_hand_calculated_small_sample_matches_and_is_ineligible(self):
        topics, original = demo_records()
        records = []
        for student, score in enumerate((40, 60, 80), 1):
            record = dict(original[0])
            record.update(student_id=f'HAND-{student}', stage='post', score=score, tested_at='2026-10-01')
            records.append(record)
        dataset_id = self.imported(topics, records)
        metric, item = self.metric_and_item(dataset_id, 'fractions')
        self.assertEqual(metric['mean_post_pct'], 60)
        self.assertEqual(metric['n_post'], 3)
        self.assertAlmostEqual(metric['below_threshold_share'], 1 / 3)
        self.assertEqual(metric['status'], 'insufficient_data')
        self.assertFalse(item['automatic_eligible'])
        self.assertEqual(item['delta'], 0)

    def test_unknown_class_keeps_existing_plan_error(self):
        dataset_id = self.imported(*demo_records())
        with self.assertRaises(PlanError):
            preview(self.store, dataset_id, PlanRequest(class_id='missing'))


if __name__ == '__main__':
    unittest.main()
