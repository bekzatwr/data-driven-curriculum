"""HTTP adapter; pure calculations never access the request or database."""
from typing import Annotated
from fastapi import APIRouter, Query, Request
from .common import AnalyticsError, normalize_settings, select_records
from .comparison import compare_textbooks
from .topics import compute_overview, compute_topics
from .teachers import compute_teachers
from .models import Comparison, Error, Overview, Teachers, TopicDetail

router = APIRouter(prefix='/api/datasets', tags=['Analytics'],
                   responses={404: {'model': Error, 'description': 'Dataset or topic not found'},
                              422: {'model': Error, 'description': 'Invalid analytics request'}})
Ids = Annotated[list[str] | None, Query()]


def _load(request, dataset_id, class_ids, textbook_ids, test_version, topic_id=None):
    store = request.app.state.store
    dataset = store.get_dataset(dataset_id)  # Enforces public-demo visibility first.
    topics = store.get_topics(dataset_id)
    records = store.load_results(dataset_id)  # Internal method includes all 10k rows.
    if topic_id is not None and topic_id not in {t['topic_id'] for t in topics}:
        from fastapi import HTTPException
        raise HTTPException(404, 'Тема не найдена')
    for field, selected in [('class_id', class_ids), ('textbook_id', textbook_ids)]:
        unknown = set(selected or []) - {r[field] for r in records}
        if unknown:
            raise AnalyticsError('INVALID_FILTERS', f'Неизвестные значения {field}: {", ".join(sorted(unknown))}')
    eligible = [r for r in records if topic_id is None or r['topic_id'] == topic_id]
    if test_version is not None and test_version not in {r['test_version'] for r in eligible}:
        raise AnalyticsError('INVALID_FILTERS', 'Выбранная версия теста отсутствует в наборе или теме')
    filters = {'class_ids': sorted(set(class_ids or [])),
               'textbook_ids': sorted(set(textbook_ids or [])), 'test_version': test_version}
    selected = select_records(records, filters)
    classes = sorted({(r['school_id'], r['class_id']) for r in selected})
    return dataset, topics, selected, classes, filters


def _envelope(dataset, filters, settings, warnings=()):
    return {'dataset_id': dataset['id'], 'is_demo': dataset['source_type'] == 'demo',
            'source': dataset, 'applied_filters': filters, 'settings': settings,
            'warnings': list(warnings)}


def _topics(records, topics, settings):
    metrics = compute_topics(records, {'topic_ids': [t['topic_id'] for t in topics]}, settings)
    by_id = {m['topic_id']: m for m in metrics}
    return [{**by_id[t['topic_id']], 'topic_name': t['topic_name'], 'topic_order': t['topic_order']}
            for t in topics]


def _by_class(records, classes, topics, settings):
    return [{'school_id': school, 'class_id': classroom, 'metrics': metric}
            for school, classroom in classes
            for metric in _topics([r for r in records if (r['school_id'], r['class_id']) == (school, classroom)], topics, settings)]


@router.get('/{dataset_id}/overview', response_model=Overview)
def overview(dataset_id: str, request: Request, class_ids: Ids = None,
             textbook_ids: Ids = None, test_version: str | None = None):
    dataset, topics, records, classes, filters = _load(request, dataset_id, class_ids, textbook_ids, test_version)
    settings = normalize_settings(None)
    metrics = compute_overview(records, [t['topic_id'] for t in topics], settings=settings)
    return {**_envelope(dataset, filters, settings, metrics.get('warnings', [])),
            'metrics': metrics, 'topics': _topics(records, topics, settings),
            'heatmap': _by_class(records, classes, topics, settings)}


@router.get('/{dataset_id}/topics/{topic_id}', response_model=TopicDetail)
def topic_detail(dataset_id: str, topic_id: str, request: Request, class_ids: Ids = None,
                 textbook_ids: Ids = None, test_version: str | None = None):
    dataset, topics, records, classes, filters = _load(request, dataset_id, class_ids, textbook_ids, test_version, topic_id)
    topics = [t for t in topics if t['topic_id'] == topic_id]
    records = [r for r in records if r['topic_id'] == topic_id]
    settings = normalize_settings(None)
    metrics = _topics(records, topics, settings)[0]
    slices = [_topics([r for r in records if r['test_version'] == s['test_version'] and r['max_score'] == s['max_score']], topics, settings)[0]
              for s in metrics['available_slices']]
    return {**_envelope(dataset, filters, settings, metrics['warnings']), 'metrics': metrics,
            'by_class': _by_class(records, classes, topics, settings), 'slices': slices}


@router.get('/{dataset_id}/comparison', response_model=Comparison)
def comparison(dataset_id: str, request: Request, topic_id: str, textbook_a: str,
               textbook_b: str, class_ids: Ids = None, test_version: str | None = None):
    dataset, topics, records, classes, filters = _load(
        request, dataset_id, class_ids, [textbook_a, textbook_b], test_version, topic_id)
    settings = normalize_settings(None)
    result = compare_textbooks(records, topic_id, textbook_a, textbook_b, settings)
    return {**_envelope(dataset, filters, settings), **result}


@router.get('/{dataset_id}/teachers', response_model=Teachers)
def teachers(dataset_id: str, request: Request, class_ids: Ids = None,
             textbook_ids: Ids = None, test_version: str | None = None):
    dataset, topics, records, _, filters = _load(request, dataset_id, class_ids, textbook_ids, test_version)
    settings = normalize_settings(None)
    result = compute_teachers(records, topics, settings=settings)
    return {**_envelope(dataset, filters, settings), **result, 'definitions': {
        'scope': 'Наблюдаемая нагрузка по одному предмету, параллели и периоду набора; не полная ставка и не оценка качества учителя.',
        'teacher_key': 'school_id + teacher_id + is_missing_teacher; пропуск учителя не является отдельным известным учителем.',
        'upcoming_hours': 'Число наблюдаемых классов учителя × сумма current_hours всех тем. Это оценка, а не расписание.',
        'students_per_teacher': 'Уникальные ученики школы, включая записи без учителя, / число известных учителей. При неполных ID показатель требует осторожности.',
        'classes_per_teacher': 'Число наблюдаемых связей известный учитель–класс / число известных учителей.',
        'hours_per_teacher': 'Число связей известный учитель–класс × hours_per_class / число известных учителей.',
        'mean_post_pct': 'Среднее процентов по итоговым записям ученик–тема, как в прототипе страницы учителей; отличается от взвешивания учеников в overview.',
        'mean_pre_paired_pct': 'Средний входной процент только по тем же совместимым парам, что mean_gain_pp; без пар или при смешанных версиях — null.',
        'mean_post_paired_pct': 'Средний итоговый процент по той же парной выборке; может отличаться от mean_post_pct всех итоговых записей.',
        'n_post': 'Число итоговых записей ученик–тема; число уникальных учеников с итогом — n_post_students.',
        'n_pairs': 'Совместимые пары ученик–тема в одной группе school_id/teacher_id с одинаковым классом, учебником, версией и шкалой. Пары без teacher_id описывают учеников и не подтверждают одного преподавателя.',
        'n_paired_students': 'Уникальные ученики хотя бы с одной совместимой парой; число тем одного ученика не увеличивает это значение.',
        'paired_student_share': 'n_paired_students / n_post_students, доля от 0 до 1; без итоговых результатов — null. Малое число учеников с парой отмечается предупреждением.',
        'mean_gain_pp': 'Среднее индивидуальных приростов по совместимым парам, в п.п.; не причинный эффект работы учителя.',
        'missing_teacher_rows': 'Количество записей без teacher_id; сгруппированы отдельно по школам и исключены из числа известных учителей.',
    }}
