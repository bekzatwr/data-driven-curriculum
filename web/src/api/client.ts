import type {
  AiKind,
  AuthorRole,
  Capabilities,
  CommentItem,
  CommentList,
  CommentTarget,
  Comparison,
  Explanation,
  RecordsPage,
  Dataset,
  DatasetList,
  DatasetMetadata,
  ErrorBody,
  ErrorDetail,
  Filters,
  ImportResponse,
  Overview,
  PlanPreview,
  PlanRequest,
  SavedPlan,
  SaveRequest,
  TopicDetail,
} from './types';

// Пусто = тот же origin (production-контейнер) или dev proxy Vite.
const BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ErrorDetail[];
  readonly totalErrors: number;

  constructor(status: number, body: Partial<ErrorBody>) {
    super(cleanMessage(body.message) || describeStatus(status));
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code || `HTTP_${status}`;
    this.details = Array.isArray(body.details) ? body.details : [];
    this.totalErrors = body.total_errors ?? this.details.length;
  }

  get isNetwork() {
    return this.status === 0;
  }
}

/** Убирает служебный текст pydantic («1 validation error… [type=…]»), оставляя понятную причину. */
export function cleanMessage(message?: string): string {
  if (!message) return '';
  const m = /Value error,\s*([^\[\n]+)/.exec(message);
  if (m) return m[1].trim();
  return message.split('\n')[0].replace(/\s*\[type=.*$/, '').trim();
}

function describeStatus(status: number): string {
  switch (status) {
    case 0:
      return 'Сервер недоступен. Проверьте, что API запущен, и повторите попытку.';
    case 403:
      return 'Действие недоступно в публичном деморежиме.';
    case 404:
      return 'Данные не найдены. Возможно, набор или план удалён.';
    case 422:
      return 'Проверьте введённые параметры.';
    case 503:
      return 'База данных временно недоступна. Повторите через несколько секунд.';
    default:
      return status >= 500 ? 'Внутренняя ошибка сервера.' : `Ошибка запроса (HTTP ${status}).`;
  }
}

type Query = Record<string, string | number | boolean | null | undefined | (string | number)[]>;

export function buildQuery(query?: Query): string {
  if (!query) return '';
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue;
    if (Array.isArray(value)) value.forEach((v) => params.append(key, String(v)));
    else params.append(key, String(value));
  }
  const s = params.toString();
  return s ? `?${s}` : '';
}

export function apiUrl(path: string, query?: Query) {
  return `${BASE}${path}${buildQuery(query)}`;
}

async function request<T>(
  path: string,
  init: RequestInit & { query?: Query; json?: unknown } = {},
): Promise<{ data: T; status: number; response: Response }> {
  const { query, json, headers, ...rest } = init;
  const finalInit: RequestInit = { ...rest, headers: { Accept: 'application/json', ...(headers || {}) } };
  if (json !== undefined) {
    finalInit.body = JSON.stringify(json);
    (finalInit.headers as Record<string, string>)['Content-Type'] = 'application/json';
  }
  let response: Response;
  try {
    response = await fetch(apiUrl(path, query), finalInit);
  } catch (err) {
    if ((err as Error)?.name === 'AbortError') throw err;
    throw new ApiError(0, {});
  }
  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
  }
  if (!response.ok) {
    throw new ApiError(response.status, (body as Partial<ErrorBody>) || {});
  }
  return { data: body as T, status: response.status, response };
}

const enc = encodeURIComponent;

export interface AnalyticsFilters {
  class_ids?: string[];
  textbook_ids?: string[];
  test_version?: string | null;
}

export const api = {
  health: (signal?: AbortSignal) =>
    request<{ status: string; database: string; read_only_demo: boolean; version: string }>('/api/health', {
      signal,
    }).then((r) => r.data),

  capabilities: (signal?: AbortSignal) =>
    request<Capabilities>('/api/capabilities', { signal }).then((r) => r.data),

  listDatasets: (signal?: AbortSignal) =>
    request<DatasetList>('/api/datasets', { signal, query: { limit: 50 } }).then((r) => r.data),

  getDataset: (id: string, signal?: AbortSignal) =>
    request<Dataset>(`/api/datasets/${enc(id)}`, { signal }).then((r) => r.data),

  createDemo: () =>
    request<ImportResponse>('/api/datasets/demo', { method: 'POST' }).then((r) => ({ ...r.data, httpStatus: r.status })),

  importDataset: (
    files: { results: File; curriculum: File },
    metadata: DatasetMetadata,
    dryRun: boolean,
    signal?: AbortSignal,
  ) => {
    const form = new FormData();
    form.append('results_file', files.results);
    form.append('curriculum_file', files.curriculum);
    form.append('metadata', JSON.stringify(metadata));
    // Content-Type не задаём: boundary добавит браузер.
    return request<ImportResponse>('/api/datasets/import', {
      method: 'POST',
      body: form,
      signal,
      query: { dry_run: dryRun },
    }).then((r) => ({ ...r.data, httpStatus: r.status }));
  },

  filters: (id: string, signal?: AbortSignal) =>
    request<Filters>(`/api/datasets/${enc(id)}/filters`, { signal }).then((r) => r.data),

  overview: (id: string, f: AnalyticsFilters, signal?: AbortSignal) =>
    request<Overview>(`/api/datasets/${enc(id)}/overview`, {
      signal,
      query: { class_ids: f.class_ids, textbook_ids: f.textbook_ids, test_version: f.test_version },
    }).then((r) => r.data),

  topic: (id: string, topicId: string, f: AnalyticsFilters, signal?: AbortSignal) =>
    request<TopicDetail>(`/api/datasets/${enc(id)}/topics/${enc(topicId)}`, {
      signal,
      query: { class_ids: f.class_ids, textbook_ids: f.textbook_ids, test_version: f.test_version },
    }).then((r) => r.data),

  comparison: (
    id: string,
    p: { topic_id: string; textbook_a: string; textbook_b: string; class_ids?: string[]; test_version?: string | null },
    signal?: AbortSignal,
  ) =>
    request<Comparison>(`/api/datasets/${enc(id)}/comparison`, { signal, query: { ...p } }).then((r) => r.data),

  previewPlan: (id: string, body: PlanRequest, signal?: AbortSignal) =>
    request<PlanPreview>(`/api/datasets/${enc(id)}/plans/preview`, { method: 'POST', json: body, signal }).then(
      (r) => r.data,
    ),

  savePlan: (id: string, body: SaveRequest) =>
    request<SavedPlan>(`/api/datasets/${enc(id)}/plans`, { method: 'POST', json: body }).then((r) => r.data),

  getPlan: (planId: string, signal?: AbortSignal) =>
    request<SavedPlan>(`/api/plans/${enc(planId)}`, { signal }).then((r) => r.data),

  results: (id: string, offset: number, limit = 1000, signal?: AbortSignal) =>
    request<RecordsPage>(`/api/datasets/${enc(id)}/results`, { signal, query: { offset, limit } }).then((r) => r.data),

  /** Все записи набора (до 10 000 строк) — для расчёта нагрузки учителей на клиенте. */
  async allResults(id: string, signal?: AbortSignal) {
    const first = await api.results(id, 0, 1000, signal);
    const items = [...first.items];
    for (let offset = first.items.length; offset < first.total; offset += 1000) {
      const page = await api.results(id, offset, 1000, signal);
      items.push(...page.items);
      if (!page.items.length) break;
    }
    return items;
  },

  comments: (id: string, target?: { type?: CommentTarget; id?: string }, signal?: AbortSignal) =>
    request<CommentList>(`/api/datasets/${enc(id)}/comments`, {
      signal,
      query: { target_type: target?.type, target_id: target?.id },
    }).then((r) => r.data),

  addComment: (
    id: string,
    body: { target_type: CommentTarget; target_id: string; author_name: string; author_school?: string; author_role: AuthorRole; text: string },
  ) => request<CommentItem>(`/api/datasets/${enc(id)}/comments`, { method: 'POST', json: body }).then((r) => r.data),

  aiStatus: (signal?: AbortSignal) =>
    request<{ configured: boolean; providers: string[]; models: Record<string, string> }>('/api/ai/status', { signal }).then(
      (r) => r.data,
    ),

  aiExplain: (id: string, body: { kind: AiKind; context: unknown; question?: string | null }) =>
    request<Explanation>(`/api/datasets/${enc(id)}/ai/explain`, { method: 'POST', json: body }).then((r) => r.data),

  planCsvUrl: (planId: string) => apiUrl(`/api/plans/${enc(planId)}/export.csv`),
  planJsonUrl: (planId: string) => apiUrl(`/api/plans/${enc(planId)}`),
  templateUrl: (name: 'results' | 'curriculum') => apiUrl(`/api/templates/${name}.csv`),

  async downloadPlanCsv(planId: string, preferredName?: string) {
    let response: Response;
    try {
      response = await fetch(api.planCsvUrl(planId));
    } catch {
      throw new ApiError(0, {});
    }
    if (!response.ok) {
      let body: Partial<ErrorBody> = {};
      try {
        body = await response.json();
      } catch {
        /* ignore */
      }
      throw new ApiError(response.status, body);
    }
    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i.exec(disposition);
    const filename = preferredName || (match ? decodeURIComponent(match[1] || match[2]) : `plan-${planId}.csv`);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return filename;
  },
};
