// Запуск: npm test (встроенный раннер Node, без зависимостей). Файл исключён из сборки Vite/tsc.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { compactSelectors, parseRetryAfter } from './helpers.ts';

test('Retry-After: секунды и HTTP-дата', () => {
  assert.equal(parseRetryAfter('43'), 43);
  assert.equal(parseRetryAfter(' 7 '), 7);
  assert.equal(parseRetryAfter('1.2'), 2);
  const now = Date.parse('2026-11-10T12:00:00Z');
  assert.equal(parseRetryAfter('Tue, 10 Nov 2026 12:00:30 GMT', now), 30);
  assert.equal(parseRetryAfter('Tue, 10 Nov 2026 11:59:00 GMT', now), 1, 'прошедшая дата → минимум 1 с');
});

test('Retry-After: нет или мусор → null', () => {
  assert.equal(parseRetryAfter(null), null);
  assert.equal(parseRetryAfter(''), null);
  assert.equal(parseRetryAfter('скоро'), null);
});

test('ИИ-селекторы: пустые значения не уходят на сервер', () => {
  assert.deepEqual(compactSelectors({ class_ids: [], textbook_ids: ['Учебник A'], test_version: null, topic_id: '' }), {
    textbook_ids: ['Учебник A'],
  });
  assert.deepEqual(compactSelectors({}), {});
});

test('ИИ-селекторы: только разрешённые сервером поля, без показателей и текста', () => {
  const allowed = new Set(['class_ids', 'textbook_ids', 'test_version', 'topic_id', 'textbook_a', 'textbook_b', 'plan_id']);
  const sample = compactSelectors({ topic_id: 'equations', textbook_a: 'Учебник A', textbook_b: 'Учебник B', class_ids: ['7A'] });
  for (const key of Object.keys(sample)) assert.ok(allowed.has(key), `лишнее поле ${key}`);
  assert.deepEqual(sample, { topic_id: 'equations', textbook_a: 'Учебник A', textbook_b: 'Учебник B', class_ids: ['7A'] });
});
