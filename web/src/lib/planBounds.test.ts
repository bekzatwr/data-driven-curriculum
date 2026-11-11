// Запуск: npm test. Регрессия: в режиме period кнопки «+»/«−» и стрелки упирались в ±2 ч от текущих часов.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { hourBounds, stepHours } from './planBounds.ts';

// Демо Тони, класс 7A: текущие часы и границы тем (как в ответе /plans/preview).
const topics = {
  fractions: { current_hours: 6, min_hours: 3, max_hours: 8, is_locked: false },
  equations: { current_hours: 5, min_hours: 3, max_hours: 8, is_locked: false },
  proportions: { current_hours: 4, min_hours: 2, max_hours: 6, is_locked: false },
  geometry: { current_hours: 3, min_hours: 2, max_hours: 5, is_locked: true },
  statistics: { current_hours: 4, min_hours: 2, max_hours: 5, is_locked: false },
  revision: { current_hours: 2, min_hours: 1, max_hours: 4, is_locked: false },
};
type Topic = keyof typeof topics;

/** Нажимает «+» или «−» (или стрелку), пока значение не станет target; бросает, если шаг запрещён. */
function press(value: number, target: number, topic: Topic, isPeriod: boolean): number {
  const bounds = hourBounds(topics[topic], isPeriod, 2);
  while (value !== target) {
    const next = stepHours(value, target > value ? 1 : -1, bounds);
    if (next === null) throw new Error(`${topic}: шаг ${value} → ${target} запрещён границами ${bounds.min}…${bounds.max}`);
    value = next;
  }
  return value;
}

test('period: границы — min/max темы, а не ±2 от текущих часов', () => {
  assert.deepEqual(hourBounds(topics.equations, true, 2), { min: 3, max: 8 });
  assert.deepEqual(hourBounds(topics.fractions, true, 2), { min: 3, max: 8 });
  assert.deepEqual(hourBounds(topics.revision, true, 2), { min: 1, max: 4 });
});

test('period, 7A: план 6/8/4/3/2/1 набирается только кнопками, сумма 24', () => {
  // Предложение period_v1 для 7A: 8/6/4/3/2/1.
  const proposed: Record<Topic, number> = { fractions: 8, equations: 6, proportions: 4, geometry: 3, statistics: 2, revision: 1 };
  const target: Record<Topic, number> = { fractions: 6, equations: 8, proportions: 4, geometry: 3, statistics: 2, revision: 1 };
  const result = Object.fromEntries(
    (Object.keys(topics) as Topic[]).map((t) => [t, proposed[t] === target[t] ? proposed[t] : press(proposed[t], target[t], t, true)]),
  ) as Record<Topic, number>;
  assert.deepEqual(result, target);
  assert.equal(Object.values(result).reduce((s, h) => s + h, 0), 24);
  // «Уравнения»: с текущих 5 до 8 — на 3 ч, больше прежнего лимита ±2.
  assert.equal(press(5, 8, 'equations', true), 8);
});

test('period: 9 при max=8 запрещено, ниже минимума — тоже', () => {
  const eq = hourBounds(topics.equations, true, 2);
  assert.equal(stepHours(8, 1, eq), null);
  assert.equal(stepHours(3, -1, eq), null);
  assert.equal(stepHours(7, 1, eq), 8);
});

test('заблокированная тема не меняется ни в одном режиме', () => {
  for (const isPeriod of [true, false]) {
    const b = hourBounds(topics.geometry, isPeriod, 2);
    assert.deepEqual(b, { min: 3, max: 3 });
    assert.equal(stepHours(3, 1, b), null);
    assert.equal(stepHours(3, -1, b), null);
  }
});

test('P0 (перераспределение): ограничение ±2 ч сохраняется', () => {
  assert.deepEqual(hourBounds(topics.equations, false, 2), { min: 3, max: 7 });
  assert.equal(press(5, 7, 'equations', false), 7);
  assert.throws(() => press(5, 8, 'equations', false), /запрещён/);
  // ±2 и границы темы действуют вместе: у «Повторения» минимум 1 ч.
  assert.deepEqual(hourBounds(topics.revision, false, 2), { min: 1, max: 4 });
  assert.deepEqual(hourBounds(topics.statistics, false, 2), { min: 2, max: 5 });
});

test('значение вне границ (прямой ввод) можно вернуть шагом назад, но не увести дальше', () => {
  const eq = hourBounds(topics.equations, true, 2);
  assert.equal(stepHours(9, -1, eq), 8);
  assert.equal(stepHours(9, 1, eq), null);
});
