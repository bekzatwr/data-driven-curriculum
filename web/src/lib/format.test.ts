// Запуск: npm test (встроенный раннер Node, без зависимостей). Файл исключён из сборки Vite/tsc.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { NO_DATA, fmtPct, fmtPp, fmtShare, fmtSigned, plural } from './format.ts';

// Intl ru-RU разделяет тысячи неразрывным пробелом и пишет запятую в дробях.
test('проценты и доли: один знак, запятая, null → «Нет данных»', () => {
  assert.equal(fmtPct(71.8), '71,8%');
  assert.equal(fmtPct(48), '48,0%');
  assert.equal(fmtShare(0.5), '50,0%');
  assert.equal(fmtPct(null), NO_DATA);
  assert.equal(fmtPct(Number.NaN, '—'), '—');
});

test('разница в п.п.: знак и типографский минус', () => {
  assert.equal(fmtPp(8), '+8,0 п.п.');
  assert.equal(fmtPp(-12), '−12,0 п.п.');
  assert.equal(fmtPp(0), '0,0 п.п.');
  assert.equal(fmtPp(3, { sign: false }), '3,0 п.п.');
});

test('изменение часов в плане', () => {
  assert.equal(fmtSigned(2), '+2');
  assert.equal(fmtSigned(-1), '−1');
  assert.equal(fmtSigned(0), '0');
});

test('склонение', () => {
  const f: [string, string, string] = ['тема', 'темы', 'тем'];
  assert.equal(plural(1, f), 'тема');
  assert.equal(plural(2, f), 'темы');
  assert.equal(plural(5, f), 'тем');
  assert.equal(plural(11, f), 'тем');
  assert.equal(plural(21, f), 'тема');
  assert.equal(plural(104, f), 'темы');
});
