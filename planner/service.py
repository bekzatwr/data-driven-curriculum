from analytics.topics import compute_topics
from pydantic import ValidationError
from .models import Constraint, PeriodConstraint
from .period import allocate_period
from .rules import allocate_hours, validate_hours, PlanError


def preview(store, dataset_id, request):
    dataset = store.get_dataset(dataset_id)
    topics = store.get_topics(dataset_id)
    records = store.load_results(dataset_id, class_ids=[request.class_id])
    if not records:
        raise PlanError('Класс отсутствует в наборе')
    if len({r['school_id'] for r in records}) != 1:
        raise PlanError('Идентификатор класса неоднозначен между школами')
    ids = {t['topic_id'] for t in topics}
    if (set(request.constraints) | set(request.test_versions)) - ids:
        raise PlanError('Настройки содержат неизвестную тему')
    constraints, metrics = [], []
    for topic in topics:
        tid = topic['topic_id']
        override = request.constraints.get(tid)
        constraint_model = PeriodConstraint if request.settings.mode == 'period' else Constraint
        try:
            constraints.append(constraint_model.model_validate({**topic, **(override.model_dump(exclude_none=True) if override else {})}).model_dump())
        except ValidationError as exc:
            messages = [e['msg'].removeprefix('Value error, ') for e in exc.errors(include_url=False)]
            raise PlanError('; '.join(messages)) from exc
        rows = [r for r in records if r['topic_id'] == tid]
        if tid in request.test_versions:
            rows = [r for r in rows if r['test_version'] == request.test_versions[tid]]
            if not any(r['stage'] == 'post' for r in rows):
                raise PlanError(f'{tid}: выбранная версия не содержит итоговых результатов')
        # Use exactly the analytics cohort/version rule, including pre-only
        # observations. Otherwise the overview could prohibit aggregation while
        # the planner silently proposes hours from a different population.
        metric = compute_topics(rows, {'topic_ids': [tid]})[0]
        metrics.append({key: metric[key] for key in (
            'topic_id', 'mean_post_pct', 'n_post', 'single_version', 'test_version', 'max_score')})
    allocator = allocate_period if request.settings.mode == 'period' else allocate_hours
    result = allocator(metrics, constraints, request.settings.model_dump())
    return {**result, 'dataset_id': dataset_id, 'class_id': request.class_id,
            'applied_filters': {'class_ids': [request.class_id], 'test_versions': request.test_versions},
            'source': dataset, 'is_demo': dataset['source_type'] == 'demo', 'metrics': metrics}


def save_plan(source, snapshots, dataset_id, request, *, response_factory=None):
    result = preview(source, dataset_id, request)
    recommended = {i['topic_id']: i['proposed_hours'] for i in result['items']}
    hours = request.hours_by_topic if request.hours_by_topic is not None else recommended
    validate_hours(result['items'], hours, request.settings)
    for i in result['items']:
        i['recommended_hours'] = i['proposed_hours']
        i['recommendation_reason'] = i['reason']
        i['proposed_hours'] = hours[i['topic_id']]
        i['delta'] = i['proposed_hours'] - i['current_hours']
        i['manually_modified'] = i['proposed_hours'] != i['recommended_hours']
        if i['manually_modified']:
            i['reason'] = f"Ручное решение методиста: {i['current_hours']} → {i['proposed_hours']} ч.; рекомендация {i['recommended_hours']} ч. Ограничения проверены."
    result['manually_modified'] = hours != recommended
    result['comment'] = request.comment
    result['recommendation_transfers'] = result.pop('transfers')
    return snapshots.save(result, response_factory=response_factory)
