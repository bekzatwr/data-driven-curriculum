"""Reproducible artificial records; no personal data or external services."""
import csv
import io
import json
from copy import deepcopy

RESULT_FIELDS = ['student_id', 'school_id', 'class_id', 'teacher_id', 'textbook_id',
                 'topic_id', 'test_version', 'stage', 'score', 'max_score', 'tested_at']
TOPIC_FIELDS = ['topic_id', 'topic_name', 'topic_order', 'current_hours', 'min_hours',
                'max_hours', 'importance', 'is_locked']
DATASET_ID = 'toni-demo'
METADATA = {'name': 'Искусственные данные Тони: математика, 7 класс',
            'subject': 'Математика', 'grade': 7,
            'period_start': '2026-09-01', 'period_end': '2026-10-31'}


def demo_records():
    specs = [
        ('fractions', 'Дроби', 6, 3, 8, 3, False, 35, 48),
        ('equations', 'Уравнения', 5, 3, 8, 3, False, 52, 68),
        ('proportions', 'Пропорции', 4, 2, 6, 2, False, 56, 64),
        ('geometry', 'Геометрия', 3, 2, 5, 2, True, 60, 74),
        ('statistics', 'Статистика', 4, 2, 5, 1, False, 78, 88),
        ('revision', 'Повторение', 2, 1, 4, 1, False, 80, 92),
    ]
    topics, records = [], []
    for order, (tid, name, hours, lower, upper, weight, locked, pre_base, post_base) in enumerate(specs, 1):
        topics.append(dict(zip(TOPIC_FIELDS, [tid, name, order, hours, lower, upper, weight, locked])))
        for index in range(120):
            group, position = divmod(index, 30)
            offset = position % 15 - 7  # Exactly zero mean within every class.
            pre, post = pre_base + offset, post_base + offset
            if tid == 'equations' and group >= 2:
                pre, post = 53 + offset, 61 + offset
            if tid == 'proportions':
                # Mean=64, but 40% below 60: the separate problem flag matters.
                post = 40 if position < 12 else 80
                pre = post - 8
            for stage, score, date in [('pre', pre, '2026-09-01'), ('post', post, '2026-10-01')]:
                records.append(dict(zip(RESULT_FIELDS, [
                    f'S{index+1:03d}', 'DEMO-SCHOOL', f'7{chr(65+group)}', f'T{group+1}',
                    'Учебник A' if group < 2 else 'Учебник B', tid, 'v1', stage, score, 100, date,
                ])))
    return topics, records


def _csv(fields, rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({key: str(value).lower() if isinstance(value, bool) else value
                         for key, value in row.items()})
    return stream.getvalue().encode('utf-8')


def demo_files():
    topics, records = demo_records()
    return _csv(RESULT_FIELDS, records), _csv(TOPIC_FIELDS, topics), json.dumps(METADATA, ensure_ascii=False)


class DemoStore:
    demo_only = True

    def __init__(self):
        self.topics, self.records = demo_records()

    def get_dataset(self, dataset_id):
        if dataset_id != DATASET_ID:
            from fastapi import HTTPException
            raise HTTPException(404, 'Набор данных не найден')
        return {'id': DATASET_ID, 'source_type': 'demo', 'metadata': deepcopy(METADATA),
                'counts': {'students': 120, 'classes': 4, 'topics': 6, 'results': 1440}}

    def get_topics(self, dataset_id):
        self.get_dataset(dataset_id)
        return deepcopy(self.topics)

    def load_results(self, dataset_id, **filters):
        from .common import select_records
        self.get_dataset(dataset_id)
        return deepcopy(select_records(self.records, filters))
