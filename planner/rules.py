from .models import Constraint, Settings


class PlanError(ValueError):
    pass


def validate_hours(items, hours, settings):
    if set(hours) != {i["topic_id"] for i in items}:
        raise PlanError("Укажите часы для всех тем и только для них")
    for item in items:
        value = hours[item["topic_id"]]
        if type(value) is not int or not item["min_hours"] <= value <= item["max_hours"]:
            raise PlanError(f'{item["topic_id"]}: нужны целые часы в заданных границах')
        delta = value - item["current_hours"]
        if (settings.mode != 'period' and abs(delta) > settings.max_change) or (item["is_locked"] and delta):
            raise PlanError(f'{item["topic_id"]}: нарушена блокировка или лимит изменения')
    if sum(hours.values()) != sum(i["current_hours"] for i in items):
        raise PlanError("Общая сумма часов должна сохраняться")


def allocate_hours(topic_metrics, constraints, settings=None):
    """Pure rules_v1; metrics must describe one class and one test scale per topic."""
    settings = Settings.model_validate(settings or {})
    constraints = [Constraint.model_validate(c).model_dump() for c in constraints]
    if not constraints or len({c['topic_id'] for c in constraints}) != len(constraints):
        raise PlanError("Нужен непустой список уникальных тем")
    if len({c['topic_order'] for c in constraints}) != len(constraints):
        raise PlanError("Порядок тем должен быть уникальным")
    metrics = {m['topic_id']: m for m in topic_metrics}
    items = []
    for c in sorted(constraints, key=lambda c: c['topic_order']):
        m = metrics.get(c['topic_id'], {})
        mean, n = m.get('mean_post_pct'), m.get('n_post', 0)
        eligible = mean is not None and n >= settings.min_students and m.get('single_version', False)
        reason = ('Тема заблокирована' if c['is_locked'] else
                  'Нужна одна версия теста и шкала' if not m.get('single_version', False) else
                  'Нет данных' if mean is None else
                  'Мало данных для автоматического изменения' if n < settings.min_students else
                  'Перенос не требуется или ограничен доступными часами')
        items.append({**c, 'mean_post_pct': mean, 'n_post': n,
                      'test_version': m.get('test_version'), 'max_score': m.get('max_score'),
                      'automatic_eligible': eligible and not c['is_locked'],
                      'proposed_hours': c['current_hours'], 'delta': 0, 'reason': reason})
    transfers = []
    while True:
        recipients = [i for i in items if i['automatic_eligible'] and i['mean_post_pct'] < settings.target_pct
                      and i['proposed_hours'] < i['max_hours'] and i['delta'] < settings.max_change]
        donors = [i for i in items if i['automatic_eligible'] and i['mean_post_pct'] >= settings.donor_pct
                  and i['proposed_hours'] > i['min_hours'] and -i['delta'] < settings.max_change]
        if not recipients or not donors:
            break
        recipient = min(recipients, key=lambda i: (-i['importance'] * (settings.target_pct-i['mean_post_pct']) / (1+i['delta']), i['topic_order']))
        donor = min(donors, key=lambda i: (-(i['mean_post_pct']-settings.donor_pct) / (i['importance']*(1-i['delta'])), i['topic_order']))
        recipient['proposed_hours'] += 1
        recipient['delta'] += 1
        donor['proposed_hours'] -= 1
        donor['delta'] -= 1
        transfers.append({'from_topic_id': donor['topic_id'], 'to_topic_id': recipient['topic_id'], 'hours': 1})
    for i in items:
        if i['delta']:
            related = [t for t in transfers if i['topic_id'] in (t['from_topic_id'], t['to_topic_id'])]
            peers = ', '.join(sorted({t['from_topic_id'] if i['delta'] > 0 else t['to_topic_id'] for t in related}))
            i['reason'] = (f"{i['topic_name']}: {i['mean_post_pct']:.1f}%, {i['n_post']} учеников; "
                           f"цель {settings.target_pct:g}%, порог донора {settings.donor_pct:g}%. "
                           f"{i['current_hours']} → {i['proposed_hours']} ч.; связанные темы: {peers}. "
                           f"Границы {i['min_hours']}–{i['max_hours']} и лимит ±{settings.max_change} соблюдены.")
    validate_hours(items, {i['topic_id']: i['proposed_hours'] for i in items}, settings)
    warnings = ['Предложение не прогнозирует рост баллов; решение принимает методист.']
    if not transfers:
        warnings.append('Нет допустимой пары донора и получателя: проверьте результаты, выборку, версии тестов, границы и блокировки.')
    return {'total_hours': sum(i['current_hours'] for i in items), 'items': items,
            'transfers': transfers, 'warnings': warnings, 'settings': settings.model_dump(), 'algorithm_version': 'rules_v1'}
