import type { AiSelectors } from './types';

/**
 * Секунды из заголовка Retry-After (HTTP 429): целое число секунд или HTTP-дата.
 * null — заголовка нет или он некорректен.
 */
export function parseRetryAfter(value: string | null, now: number = Date.now()): number | null {
  if (value === null) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (/^\d+(\.\d+)?$/.test(trimmed)) return Math.ceil(Number(trimmed));
  const date = Date.parse(trimmed);
  return Number.isNaN(date) ? null : Math.max(1, Math.ceil((date - now) / 1000));
}

/** Убирает пустые селекторы: сервер принимает только применимые к kind поля. */
export function compactSelectors(s: AiSelectors): AiSelectors {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(s)) {
    if (v === undefined || v === null || v === '') continue;
    if (Array.isArray(v) && v.length === 0) continue;
    out[k] = v;
  }
  return out as AiSelectors;
}
