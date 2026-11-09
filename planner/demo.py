"""Isolated synthetic fixture; not a replacement for Toni's final dataset."""
from copy import deepcopy


class DemoStore:
    demo_only = True

    def __init__(self):
        names = ['Дроби', 'Уравнения', 'Геометрия', 'Проценты', 'Функции', 'Статистика']
        self.topics = [{'topic_id': f't{i+1}', 'topic_name': name, 'topic_order': i+1,
                        'current_hours': 4, 'min_hours': 2, 'max_hours': 6,
                        'importance': 2, 'is_locked': False} for i, name in enumerate(names)]
        self.results = []
        for classroom in ('7A', '7B', '7C', '7D'):
            for student in range(30):
                for topic, score in zip(self.topics, (46, 58, 72, 65, 84, 92)):
                    for stage in ('pre', 'post'):
                        self.results.append({'student_id': f'{classroom}-{student+1:02}', 'school_id': 'demo-school',
                                             'class_id': classroom, 'teacher_id': f'teacher-{classroom}',
                                             'textbook_id': 'A' if classroom in ('7A', '7B') else 'B',
                                             'topic_id': topic['topic_id'], 'test_version': 'v1', 'stage': stage,
                                             'score': score if stage == 'post' else score-10,
                                             'max_score': 100, 'tested_at': '2026-10-20' if stage == 'post' else '2026-09-01'})

    def get_dataset(self, dataset_id):
        if dataset_id != 'aidana-demo':
            from fastapi import HTTPException
            raise HTTPException(404, 'Набор данных не найден')
        return {'id': dataset_id, 'source_type': 'demo', 'metadata': {'name': 'Искусственный пример Айданы',
                'subject': 'Математика', 'grade': 7, 'period_start': '2026-09-01', 'period_end': '2026-10-31'},
                'counts': {'students': 120, 'classes': 4, 'topics': 6, 'results': 1440}}

    def get_topics(self, dataset_id):
        self.get_dataset(dataset_id)
        return deepcopy(self.topics)

    def load_results(self, dataset_id, class_ids):
        self.get_dataset(dataset_id)
        return [dict(r) for r in self.results if r['class_id'] in class_ids]
