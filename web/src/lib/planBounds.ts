import type { PlanItem } from '../api/types';

export interface HourBounds {
  min: number;
  max: number;
}

/**
 * Границы ручной правки часов темы для кнопок «+»/«−» и стрелок клавиатуры.
 * - Заблокированная тема остаётся с текущими часами.
 * - План на период (period_v1) распределяет весь бюджет заново: предел — min_hours…max_hours темы.
 * - Перераспределение (rules_v1, P0) дополнительно ограничено ±max_change ч от текущих часов.
 * Сервер проверяет те же правила при сохранении.
 */
export function hourBounds(
  item: Pick<PlanItem, 'current_hours' | 'min_hours' | 'max_hours' | 'is_locked'>,
  isPeriod: boolean,
  maxChange: number,
): HourBounds {
  if (item.is_locked) return { min: item.current_hours, max: item.current_hours };
  if (isPeriod) return { min: item.min_hours, max: item.max_hours };
  return {
    min: Math.max(item.min_hours, item.current_hours - maxChange),
    max: Math.min(item.max_hours, item.current_hours + maxChange),
  };
}

/** Шаг на 1 ч кнопкой или стрелкой; null — шаг за границу запрещён. */
export function stepHours(value: number, direction: 1 | -1, bounds: HourBounds): number | null {
  if (direction > 0 ? value >= bounds.max : value <= bounds.min) return null;
  return value + direction;
}
