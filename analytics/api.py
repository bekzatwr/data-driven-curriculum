"""HTTP adapter; pure calculations never access the request or database."""
from typing import Annotated
from fastapi import APIRouter, Query, Request
from .common import AnalyticsError, normalize_settings, select_records
from .comparison import compare_textbooks
from .topics import compute_overview, compute_topics
from .models import Comparison, Error, Overview, TopicDetail

router = APIRouter(prefix='/api/datasets', tags=['Analytics'],
                   responses={404: {'model': Error}, 422: {'model': Error}})
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
