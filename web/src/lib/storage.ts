// Только удобства для этого браузера; при недоступном хранилище всё продолжает работать.

export function readJson<T>(key: string, fallback: T, store: 'local' | 'session' = 'local'): T {
  try {
    const s = store === 'local' ? window.localStorage : window.sessionStorage;
    const raw = s.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function writeJson(key: string, value: unknown, store: 'local' | 'session' = 'local') {
  try {
    const s = store === 'local' ? window.localStorage : window.sessionStorage;
    s.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore */
  }
}

export interface RecentPlan {
  plan_id: string;
  dataset_id: string;
  dataset_name: string;
  class_id: string;
  created_at: string;
  total_hours: number;
  is_demo: boolean;
  manually_modified: boolean;
}

const PLANS_KEY = 'ddc.recentPlans';

export function getRecentPlans(): RecentPlan[] {
  return readJson<RecentPlan[]>(PLANS_KEY, []);
}

export function rememberPlan(p: RecentPlan) {
  const list = getRecentPlans().filter((x) => x.plan_id !== p.plan_id);
  list.unshift(p);
  writeJson(PLANS_KEY, list.slice(0, 20));
}
