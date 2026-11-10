"""Full-period allocation, matching web/src/lib/periodPlan.ts (frontend 326a75a)."""
from .models import PeriodConstraint, Settings
from .rules import PlanError, validate_hours


def allocate_period(topic_metrics, constraints, settings=None):
    settings = Settings.model_validate({'mode': 'period', **(settings or {})})
    if settings.mode != 'period':
        raise PlanError('Для полного периода нужен settings.mode=period')
    constraints = [PeriodConstraint.model_validate(c).model_dump() for c in constraints]
    if not constraints or len({c['topic_id'] for c in constraints}) != len(constraints):
        raise PlanError('Нужен непустой список уникальных тем')
    if len({c['topic_order'] for c in constraints}) != len(constraints):
        raise PlanError('Порядок тем должен быть уникальным')
    metrics = {m['topic_id']: m for m in topic_metrics}
    items, weights, added = [], {}, {}
    for c in sorted(constraints, key=lambda c: c['topic_order']):
        tid = c['topic_id']
        metric = metrics.get(tid, {})
        mean = metric.get('mean_post_pct')
        weight = c['importance'] * (1 + (0 if mean is None else max(0, settings.target_pct - mean) / 10))
        if mean is not None and mean >= settings.donor_pct:
            weight *= .5
        weights[tid], added[tid] = weight, 0
        items.append({**c, 'mean_post_pct': mean, 'n_post': metric.get('n_post', 0),
                      'test_version': metric.get('test_version'), 'max_score': metric.get('max_score'),
                      'automatic_eligible': not c['is_locked'],
                      'proposed_hours': c['current_hours'] if c['is_locked'] else c['min_hours']})
    total = sum(i['current_hours'] for i in items)
    remaining = total - sum(i['proposed_hours'] for i in items)
    capacity = sum(i['current_hours'] if i['is_locked'] else i['max_hours'] for i in items)
    if remaining < 0:
        raise PlanError(f'Недостаточный бюджет: минимумы и блокировки превышают {total} ч. на {-remaining} ч.')
    if capacity < total:
        raise PlanError(f'Избыточный бюджет: максимумы и блокировки позволяют разместить только {capacity} из {total} ч.')
    while remaining:
        best, best_score = None, float('-inf')
        for item in items:
            if item['is_locked'] or item['proposed_hours'] >= item['max_hours']:
                continue
            score = weights[item['topic_id']] / (1 + added[item['topic_id']])
            # Same tolerance and stable topic_order tie-breaking as the frontend.
            if score > best_score + 1e-9:
                best, best_score = item, score
        best['proposed_hours'] += 1
        added[best['topic_id']] += 1
        remaining -= 1
    for item in items:
        item['delta'] = item['proposed_hours'] - item['current_hours']
        mean = item['mean_post_pct']
        why = ('результатов нет — только по важности' if mean is None else
               f'{mean:g}% — освоена, половинный вес' if mean >= settings.donor_pct else
               f'{mean:g}% при цели {settings.target_pct:g}% — дефицит {settings.target_pct - mean:g} п.п.' if mean < settings.target_pct else
               f'{mean:g}% — цель достигнута')
        item['reason'] = (f"Тема заблокирована: остаётся {item['current_hours']} ч." if item['is_locked'] else
                          f"Минимум {item['min_hours']} ч + {added[item['topic_id']]} ч по приоритету "
                          f"(важность {item['importance']}; {why}). Было {item['current_hours']} ч → {item['proposed_hours']} ч.")
    validate_hours(items, {i['topic_id']: i['proposed_hours'] for i in items}, settings)
    warnings = ['Предложение не прогнозирует рост баллов; решение принимает методист.']
    if any(i['mean_post_pct'] is None for i in items):
        warnings.append('Для тем без сопоставимых итоговых результатов использована только важность.')
    return {'total_hours': total, 'items': items, 'transfers': [], 'warnings': warnings,
            'settings': settings.model_dump(), 'algorithm_version': 'period_v1'}
