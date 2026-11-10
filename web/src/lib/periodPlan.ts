import type { PlanItem } from '../api/types';
import { fmtOne } from './format';

export interface PeriodPlan {
  hours: Record<string, number>;
  reasons: Record<string, string>;
  added: Record<string, number>;
  /** Часы, которые не удалось разместить из-за максимумов (план невыполним без правки границ). */
  leftover: number;
  /** Сумма минимумов и заблокированных часов больше общего лимита. */
  overflow: number;
}

/**
 * План на весь период: распределить ВСЕ часы по темам с нуля (а не переносить ±2).
 * 1) Заблокированные темы — текущие часы, остальные — минимум.
 * 2) Остаток раздаётся по одному часу теме с наибольшим приоритетом
 *    важность × (1 + дефицит до цели / 10) / (1 + уже добавлено);
 *    освоенные темы (≥ порога донора) получают половинный вес; выше максимума — нельзя.
 * Детерминированно: при равенстве приоритетов — порядок тем.
 */
export function buildPeriodPlan(items: PlanItem[], total: number, targetPct: number, donorPct: number): PeriodPlan {
  const sorted = [...items].sort((a, b) => a.topic_order - b.topic_order);
  const hours: Record<string, number> = {};
  const added: Record<string, number> = {};
  const weight: Record<string, number> = {};
  for (const it of sorted) {
    hours[it.topic_id] = it.is_locked ? it.current_hours : it.min_hours;
    added[it.topic_id] = 0;
    const mean = it.mean_post_pct;
    let w = it.importance * (1 + (mean == null ? 0 : Math.max(0, targetPct - mean) / 10));
    if (mean != null && mean >= donorPct) w *= 0.5;
    weight[it.topic_id] = w;
  }
  const base = Object.values(hours).reduce((s, h) => s + h, 0);
  let remaining = total - base;
  const overflow = remaining < 0 ? -remaining : 0;
  while (remaining > 0) {
    let best: PlanItem | null = null;
    let bestScore = -Infinity;
    for (const it of sorted) {
      if (it.is_locked || hours[it.topic_id] >= it.max_hours) continue;
      const score = weight[it.topic_id] / (1 + added[it.topic_id]);
      if (score > bestScore + 1e-9) {
        best = it;
        bestScore = score;
      }
    }
    if (!best) break;
    hours[best.topic_id] += 1;
    added[best.topic_id] += 1;
    remaining -= 1;
  }

  const reasons: Record<string, string> = {};
  for (const it of sorted) {
    const h = hours[it.topic_id];
    if (it.is_locked) {
      reasons[it.topic_id] = `Тема заблокирована: остаётся ${it.current_hours} ч.`;
      continue;
    }
    const why =
      it.mean_post_pct == null
        ? 'результатов нет — только по важности'
        : it.mean_post_pct >= donorPct
          ? `${fmtOne(it.mean_post_pct)}% — освоена, половинный вес`
          : it.mean_post_pct < targetPct
            ? `${fmtOne(it.mean_post_pct)}% при цели ${fmtOne(targetPct)}% — дефицит ${fmtOne(targetPct - it.mean_post_pct)} п.п.`
            : `${fmtOne(it.mean_post_pct)}% — цель достигнута`;
    reasons[it.topic_id] =
      `Минимум ${it.min_hours} ч + ${added[it.topic_id]} ч по приоритету (важность ${it.importance}; ${why}).` +
      ` Было ${it.current_hours} ч → ${h} ч.${h >= it.max_hours ? ` Достигнут максимум ${it.max_hours} ч.` : ''}`;
  }
  return { hours, reasons, added, leftover: Math.max(0, remaining), overflow };
}
