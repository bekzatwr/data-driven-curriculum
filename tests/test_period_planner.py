import random

import pytest
from pydantic import ValidationError

from planner.models import Settings
from planner.period import allocate_period
from planner.rules import PlanError, allocate_hours, validate_hours


def topic(tid, order, current=5, minimum=0, maximum=20, importance=1, locked=False):
    return dict(topic_id=tid, topic_name=tid, topic_order=order, current_hours=current,
                min_hours=minimum, max_hours=maximum, importance=importance, is_locked=locked)


def metric(tid, mean):
    return dict(topic_id=tid, mean_post_pct=mean, n_post=20 if mean is not None else 0,
                single_version=True, test_version='v1', max_score=100)


def hours(result):
    return {i['topic_id']: i['proposed_hours'] for i in result['items']}


def test_full_budget_exceeds_p0_delta():
    topics = [topic('weak', 1), topic('strong', 2)]
    metrics = [metric('weak', 0), metric('strong', 100)]
    result = allocate_period(metrics, topics)
    assert hours(result) == {'weak': 10, 'strong': 0}
    assert result['algorithm_version'] == 'period_v1'
    assert result['settings']['mode'] == 'period'
    p0 = allocate_hours(metrics, topics)
    assert hours(p0) == {'weak': 7, 'strong': 3}
    assert p0['algorithm_version'] == 'rules_v1'


@pytest.mark.parametrize(('metrics', 'topics', 'expected'), [
    ([], [topic('b', 2, current=1), topic('a', 1, current=0)], {'a': 1, 'b': 0}),
    ([], [topic('a', 1, current=2, importance=3), topic('b', 2, current=2)], {'a': 3, 'b': 1}),
    ([metric('a', 80), metric('b', 70)], [topic('a', 1, current=3), topic('b', 2, current=3)], {'a': 2, 'b': 4}),
    ([], [topic('a', 1, current=3, locked=True), topic('b', 2, current=7)], {'a': 3, 'b': 7}),
    ([metric('a', 0)], [topic('a', 1, maximum=6), topic('b', 2, minimum=3)], {'a': 6, 'b': 4}),
    ([], [topic('a', 1, current=0, maximum=0)], {'a': 0}),
    ([], [topic('a', 1, minimum=7), topic('b', 2)], {'a': 9, 'b': 1}),
])
def test_priority_bounds_locks_and_missing_data(metrics, topics, expected):
    assert hours(allocate_period(metrics, topics)) == expected


@pytest.mark.parametrize(('topics', 'message'), [
    ([topic('a', 1, minimum=6), topic('b', 2, minimum=6)], 'Недостаточный бюджет'),
    ([topic('a', 1, maximum=4), topic('b', 2, maximum=4)], 'Избыточный бюджет'),
    ([topic('a', 1), topic('a', 2)], 'уникальных тем'),
    ([topic('a', 1), topic('b', 1)], 'Порядок тем'),
    ([], 'непустой'),
])
def test_infeasible_and_ambiguous_constraints(topics, message):
    with pytest.raises(PlanError, match=message):
        allocate_period([], topics)


@pytest.mark.parametrize('change', [dict(min_hours=9, max_hours=8), dict(min_hours=6, is_locked=True)])
def test_invalid_bounds(change):
    with pytest.raises(ValidationError):
        allocate_period([], [{**topic('a', 1), **change}])


def test_period_manual_validation():
    topics = [topic('a', 1), topic('b', 2), topic('locked', 3, locked=True)]
    settings = Settings(mode='period')
    validate_hours(topics, {'a': 10, 'b': 0, 'locked': 5}, settings)
    for candidate in ({'a': 11, 'b': 0, 'locked': 5}, {'a': 10, 'b': 0, 'locked': 4},
                      {'a': 10, 'b': 0}, {'a': 10.0, 'b': 0, 'locked': 5},
                      {'a': 21, 'b': -11, 'locked': 5}):
        with pytest.raises(PlanError):
            validate_hours(topics, candidate, settings)
    with pytest.raises(PlanError):
        validate_hours(topics, {'a': 10, 'b': 0, 'locked': 5}, Settings())


def test_randomized_budget_bounds_order_and_locks():
    rng = random.Random(20261110)
    for _ in range(150):
        topics = [topic(str(i), i, current=rng.randint(1, 15), minimum=rng.randint(0, 1),
                        maximum=20, importance=rng.randint(1, 3), locked=rng.choice([True, False]))
                  for i in range(12)]
        metrics = [metric(t['topic_id'], rng.choice([None, 0, 50, 70, 80, 100])) for t in topics]
        result = allocate_period(metrics, topics)
        assert sum(hours(result).values()) == sum(t['current_hours'] for t in topics)
        validate_hours(topics, hours(result), Settings(mode='period'))
        rng.shuffle(topics)
        assert allocate_period(metrics, topics) == result
