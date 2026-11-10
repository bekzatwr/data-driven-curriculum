import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowRight,
  BarChart3,
  Calculator,
  CheckCircle2,
  FileText,
  Lock,
  RotateCcw,
  Save,
  Settings2,
  Sparkles,
  Undo2,
  Users,
  XCircle,
} from 'lucide-react';
import { api } from '../api/client';
import type { ConstraintOverride, PlanItem, PlanPreview, PlanRequest, PlanSettings, SavedPlan } from '../api/types';
import {
  Badge,
  Banner,
  Button,
  DemoBadge,
  EmptyState,
  ErrorState,
  HoursStepper,
  InfoPopover,
  LoadingBlock,
  Refreshing,
  Switch,
  WarningsList,
  errorText,
  useToast,
} from '../components/ui';
import { fmtNum, fmtPct, fmtSigned, hours as hoursLabel, plural } from '../lib/format';
import { rememberPlan } from '../lib/storage';
import { buildPeriodPlan } from '../lib/periodPlan';
import { AiExplain } from '../components/AiExplain';
import { readOnlyReason, useFeatures } from '../lib/features';
import { useApp } from '../state/app';
import { useDataset } from '../state/dataset';

type PlanMode = 'shift' | 'period';

/**
 * «План на весь период» — клиентский прототип (распределение в браузере + сохранение через
 * rules_v1 с max_change = сумме часов). Серверного режима settings.mode = "period" пока нет
 * (capabilities.period_planner_api = false), поэтому режим скрыт: иначе сохранялся бы план,
 * который сервер не считает периодным. Включать только вместе с серверным контрактом Айданы.
 */
const PERIOD_PROTOTYPE_ENABLED = false;

const DEFAULT_SETTINGS: PlanSettings = { target_pct: 70, donor_pct: 80, min_students: 10, max_change: 2 };

interface Constraint {
  min_hours: number;
  max_hours: number;
  importance: number;
  is_locked: boolean;
}

export function PlannerPage() {
  const { datasetId, dataset, filters } = useDataset();
  const [params, setParams] = useSearchParams();
  const classId = params.get('class');
  const validClass = filters.classes.some((c) => c.id === classId) ? classId : null;

  const chooseClass = (id: string) => {
    const next = new URLSearchParams(params);
    next.set('class', id);
    setParams(next, { replace: false });
  };

  return (
    <div className="stack" style={{ gap: 0 }}>
      <div className="page-head fade-up">
        <div style={{ flex: 1, minWidth: 280 }}>
          <div className="eyebrow">Шаг 4 · План учебных часов</div>
          <h1>Перераспределение оставшихся часов</h1>
          <p>
            План строится для одного класса. Общая сумма, границы, блокировки и лимит изменения соблюдаются; каждое изменение
            объяснено правилом. Предложение не прогнозирует рост баллов — решение за методистом.{' '}
            {dataset.source_type === 'demo' && <DemoBadge />}
          </p>
        </div>
        {validClass && (
          <div className="row-wrap no-print">
            <label className="label" htmlFor="p-class">
              Класс
            </label>
            <select id="p-class" className="select" style={{ width: 'auto', fontWeight: 700 }} value={validClass} onChange={(e) => chooseClass(e.target.value)}>
              {filters.classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.id} · {c.student_count} уч.
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {!validClass ? (
        <section className="card card-pad fade-up">
          <div className="section-title" style={{ marginBottom: 6 }}>
            <Users size={18} /> Выберите один класс для планирования
          </div>
          <p className="text-2 small" style={{ marginBottom: 16 }}>
            Рекомендации строятся по итоговым результатам выбранного класса. После выбора сразу появится расчёт.
          </p>
          <div className="class-picker">
            {filters.classes.map((c) => (
              <button key={c.id} type="button" className="class-card" onClick={() => chooseClass(c.id)}>
                <span className="cid">{c.id}</span>
                <span className="cmeta">
                  {c.student_count} {plural(c.student_count, ['ученик', 'ученика', 'учеников'])}
                </span>
                <span className="small row" style={{ color: 'var(--accent-text)', fontWeight: 600, gap: 4 }}>
                  Рассчитать <ArrowRight size={14} />
                </span>
              </button>
            ))}
          </div>
        </section>
      ) : (
        <PlanEditor key={`${datasetId}|${validClass}`} classId={validClass} />
      )}
    </div>
  );
}

/* ================================================================= */

function PlanEditor({ classId }: { classId: string }) {
  const { datasetId, filters, topicName, shared, setShared } = useDataset();
  const { setLastPlanId } = useApp();
  const navigate = useNavigate();
  const toast = useToast();

  const baseConstraints = useMemo(() => {
    const m: Record<string, Constraint> = {};
    filters.topics.forEach((t) => {
      m[t.topic_id] = { min_hours: t.min_hours, max_hours: t.max_hours, importance: t.importance, is_locked: t.is_locked };
    });
    return m;
  }, [filters.topics]);
  const currentHours = useMemo(() => Object.fromEntries(filters.topics.map((t) => [t.topic_id, t.current_hours])), [filters.topics]);

  const versionChoices = useMemo(() => {
    const m: Record<string, string[]> = {};
    filters.test_versions.forEach((v) => (m[v.topic_id] = [...(m[v.topic_id] || []), v.test_version]));
    return Object.fromEntries(Object.entries(m).filter(([, list]) => list.length > 1));
  }, [filters.test_versions]);

  const [constraints, setConstraints] = useState<Record<string, Constraint>>(baseConstraints);
  const [settings, setSettings] = useState<PlanSettings>(DEFAULT_SETTINGS);
  const [testVersions, setTestVersions] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    Object.entries(versionChoices).forEach(([tid, list]) => {
      if (shared.testVersion && list.includes(shared.testVersion)) init[tid] = shared.testVersion;
    });
    return init;
  });

  const [preview, setPreview] = useState<PlanPreview | null>(null);
  const [previewSig, setPreviewSig] = useState<string | null>(null);
  const [previewReq, setPreviewReq] = useState<{ constraints: Record<string, Constraint>; settings: PlanSettings; testVersions: Record<string, string> } | null>(null);
  const [loading, setLoading] = useState(false);
  const [previewError, setPreviewError] = useState<unknown>(null);
  const [hours, setHours] = useState<Record<string, number>>({});
  const [comment, setComment] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [saved, setSaved] = useState<SavedPlan | null>(null);
  const reqId = useRef(0);
  const features = useFeatures();
  const saveAllowed = !features.off('plan_save');
  const periodAllowed = PERIOD_PROTOTYPE_ENABLED && features.on('period_planner_api');
  const [mode, setMode] = useState<PlanMode>('shift');
  const totalCurrent = useMemo(() => filters.topics.reduce((sum, t) => sum + t.current_hours, 0), [filters.topics]);
  // План на период: снимаем лимит ±N (сервер разрешает max_change до 10000), распределение строит buildPeriodPlan.
  const settingsFor = useCallback(
    (m: PlanMode): PlanSettings => (m === 'period' ? { ...settings, max_change: Math.max(settings.max_change, totalCurrent) } : settings),
    [settings, totalCurrent],
  );

  const buildRequest = useCallback((m: PlanMode = mode): PlanRequest => {
    const overrides: Record<string, ConstraintOverride> = {};
    Object.entries(constraints).forEach(([tid, c]) => {
      const b = baseConstraints[tid];
      const o: ConstraintOverride = {};
      if (!b || c.min_hours !== b.min_hours) o.min_hours = c.min_hours;
      if (!b || c.max_hours !== b.max_hours) o.max_hours = c.max_hours;
      if (!b || c.importance !== b.importance) o.importance = c.importance;
      if (!b || c.is_locked !== b.is_locked) o.is_locked = c.is_locked;
      if (Object.keys(o).length) overrides[tid] = o;
    });
    const req: PlanRequest = { class_id: classId, settings: settingsFor(m) };
    if (Object.keys(overrides).length) req.constraints = overrides;
    if (Object.keys(testVersions).length) req.test_versions = testVersions;
    return req;
  }, [constraints, baseConstraints, classId, settingsFor, testVersions, mode]);

  const request = buildRequest();
  const sig = JSON.stringify(request);
  const stale = !!preview && previewSig !== sig;

  // Клиентская проверка ограничений (сервер требует min ≤ текущие ≤ max).
  const constraintErrors = useMemo(() => {
    const e: Record<string, string> = {};
    Object.entries(constraints).forEach(([tid, c]) => {
      const cur = currentHours[tid];
      if (!Number.isInteger(c.min_hours) || !Number.isInteger(c.max_hours) || c.min_hours < 0 || c.max_hours > 10000) e[tid] = 'Целые часы от 0 до 10000';
      else if (c.min_hours > c.max_hours) e[tid] = 'Минимум больше максимума';
      else if (cur < c.min_hours || cur > c.max_hours) e[tid] = `Текущие ${cur} ч должны быть в границах`;
    });
    return e;
  }, [constraints, currentHours]);
  const settingsError =
    settings.target_pct < 0 || settings.target_pct > 100 || settings.donor_pct < 0 || settings.donor_pct > 100
      ? 'Пороги — от 0 до 100%'
      : settings.min_students < 10
        ? 'Минимум учеников — не меньше 10'
        : !Number.isInteger(settings.max_change) || settings.max_change < 0
          ? 'Лимит изменения — целое ≥ 0'
          : null;
  const canCalculate = Object.keys(constraintErrors).length === 0 && !settingsError && !loading;

  const calculate = useCallback(
    async (
      req: PlanRequest,
      snapshot: { constraints: Record<string, Constraint>; settings: PlanSettings; testVersions: Record<string, string> },
      periodMode = false,
    ) => {
      const id = ++reqId.current;
      setLoading(true);
      setPreviewError(null);
      setSaveError(null);
      try {
        const res = await api.previewPlan(datasetId, req);
        if (id !== reqId.current) return;
        setPreview(res);
        setPreviewSig(JSON.stringify(req));
        setPreviewReq(snapshot);
        setHours(
          periodMode
            ? buildPeriodPlan(res.items, res.total_hours, res.settings.target_pct, res.settings.donor_pct).hours
            : Object.fromEntries(res.items.map((i) => [i.topic_id, i.proposed_hours])),
        );
      } catch (e) {
        if (id !== reqId.current) return;
        setPreviewError(e);
      } finally {
        if (id === reqId.current) setLoading(false);
      }
    },
    [datasetId],
  );

  // Автоматический расчёт при открытии класса.
  useEffect(() => {
    calculate(buildRequest(), { constraints, settings, testVersions });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runCalculate = () => canCalculate && calculate(request, { constraints, settings, testVersions }, mode === 'period');

  const switchMode = (m: PlanMode) => {
    if (m === mode || !canCalculate || (m === 'period' && !periodAllowed)) return;
    setMode(m);
    setSaved(null);
    calculate(buildRequest(m), { constraints, settings, testVersions }, m === 'period');
  };

  const resetChanges = () => {
    if (previewReq) {
      setConstraints(previewReq.constraints);
      setSettings(previewReq.settings);
      setTestVersions(previewReq.testVersions);
    }
    if (preview) setHours(Object.fromEntries(preview.items.map((i) => [i.topic_id, baselineOf(i)])));
    setSaveError(null);
  };

  /* ---------- Проверка ручных часов ---------- */
  const items = preview?.items || [];
  const period = useMemo(
    () =>
      preview && mode === 'period'
        ? buildPeriodPlan(preview.items, preview.total_hours, preview.settings.target_pct, preview.settings.donor_pct)
        : null,
    [preview, mode],
  );
  function baselineOf(it: PlanItem) {
    return period ? period.hours[it.topic_id] ?? it.proposed_hours : it.proposed_hours;
  }
  const maxChange = preview?.settings.max_change ?? settings.max_change;
  const rowErrors = useMemo(() => {
    const e: Record<string, string> = {};
    items.forEach((it) => {
      const h = hours[it.topic_id];
      if (h == null || !Number.isInteger(h) || h < 0) e[it.topic_id] = 'Нужны целые часы ≥ 0';
      else if (it.is_locked && h !== it.current_hours) e[it.topic_id] = `Тема заблокирована: должно остаться ${it.current_hours} ч`;
      else if (h < it.min_hours) e[it.topic_id] = `Меньше минимума ${it.min_hours} ч`;
      else if (h > it.max_hours) e[it.topic_id] = `Больше максимума ${it.max_hours} ч`;
      else if (Math.abs(h - it.current_hours) > maxChange) e[it.topic_id] = `Изменение больше лимита ±${maxChange} ч`;
    });
    return e;
  }, [items, hours, maxChange]);

  const sum = items.reduce((s, it) => s + (hours[it.topic_id] ?? 0), 0);
  const total = preview?.total_hours ?? 0;
  const sumDiff = sum - total;
  const manualCount = items.filter((it) => hours[it.topic_id] !== baselineOf(it)).length;
  const changedCount = items.filter((it) => hours[it.topic_id] !== it.current_hours).length;
  const moved = items.reduce((s, it) => s + Math.max(0, (hours[it.topic_id] ?? 0) - it.current_hours), 0);
  const errorCount = Object.keys(rowErrors).length + (sumDiff !== 0 ? 1 : 0);
  const valid = !!preview && errorCount === 0;
  const canSave = saveAllowed && valid && !stale && !loading && !saving;

  const savePlan = async () => {
    if (!canSave || !preview) return;
    setSaving(true);
    setSaveError(null);
    try {
      const note = mode === 'period' ? `[План на весь период] ${comment.trim()}`.trim() : comment.trim();
      const body = { ...request, hours_by_topic: Object.fromEntries(items.map((it) => [it.topic_id, hours[it.topic_id]])), comment: note };
      const res = await api.savePlan(datasetId, body);
      setSaved(res);
      setLastPlanId(res.plan_id);
      rememberPlan({
        plan_id: res.plan_id,
        dataset_id: res.dataset_id,
        dataset_name: res.source.metadata.name,
        class_id: res.class_id,
        created_at: res.created_at,
        total_hours: res.total_hours,
        is_demo: res.is_demo,
        manually_modified: res.manually_modified,
      });
      toast({ tone: 'good', title: 'План сохранён', message: `Снимок ${res.plan_id.slice(0, 8)}… · класс ${res.class_id}` });
    } catch (e) {
      setSaveError(e);
      toast({ tone: 'critical', title: 'План не сохранён', message: errorText(e).message });
    } finally {
      setSaving(false);
    }
  };

  const setConstraint = (tid: string, patch: Partial<Constraint>) => setConstraints((c) => ({ ...c, [tid]: { ...c[tid], ...patch } }));

  const openAnalytics = () => {
    setShared({ ...shared, classIds: [classId] });
    navigate(`/datasets/${encodeURIComponent(datasetId)}/overview`);
  };

  if (!preview && loading) {
    return (
      <div className="card">
        <LoadingBlock rows={8} label="Рассчитываем предложение…" />
      </div>
    );
  }
  if (!preview && previewError != null) {
    return (
      <div className="card">
        <ErrorState error={previewError} onRetry={() => calculate(request, { constraints, settings, testVersions }, mode === 'period')} />
      </div>
    );
  }
  if (!preview) return null;

  const sumOk = sumDiff === 0;

  return (
    <div className="stack">
      {/* ---------- Режим ---------- */}
      {periodAllowed && <div className="mode-switch fade-up">
        <div className="segmented" role="tablist" aria-label="Режим планирования">
          <button role="tab" aria-selected={mode === 'shift'} className={mode === 'shift' ? 'on' : ''} onClick={() => switchMode('shift')}>
            Перераспределение ±{settings.max_change} ч
          </button>
          <button role="tab" aria-selected={mode === 'period'} className={mode === 'period' ? 'on' : ''} onClick={() => switchMode('period')}>
            План на весь период
          </button>
        </div>
        <span className="small muted" style={{ flex: 1, minWidth: 240 }}>
          {mode === 'period'
            ? `Все ${preview.total_hours} ч распределяются по темам с нуля: минимум каждой теме, остаток — по приоритету трудных и важных тем.`
            : 'Небольшие переносы часов между темами по правилу rules_v1 с лимитом изменения на тему.'}
        </span>
      </div>}
      {!saveAllowed && (
        <Banner tone="info" title="Сохранение отключено сервером">
          {readOnlyReason(features.readOnly)} Расчёт, ручные правки и проверка ограничений работают.
        </Banner>
      )}
      {period && period.overflow > 0 && (
        <Banner tone="critical" title="Минимумы больше общего лимита">
          Сумма минимумов и заблокированных часов превышает {preview.total_hours} ч на {period.overflow} ч. Уменьшите минимумы или снимите блокировку.
        </Banner>
      )}
      {period && period.leftover > 0 && (
        <Banner tone="warning" title="Не все часы удалось распределить">
          {period.leftover} ч не помещаются из-за максимумов тем. Увеличьте максимум у важных тем и нажмите «Рассчитать».
        </Banner>
      )}

      {/* ---------- Сводка ---------- */}
      <div className="kpi-strip wide-first fade-up">
        <div className={`kpi ${sumOk ? '' : 'tone-critical'}`}>
          <div className="row">
            <span className="kpi-label">Сумма часов / лимит</span>
            <span className="spacer" />
            {sumOk ? (
              <Badge tone="good" icon={<CheckCircle2 size={13} />}>
                Сумма сохранена
              </Badge>
            ) : (
              <Badge tone="critical" icon={<XCircle size={13} />}>
                {sumDiff > 0 ? `Лишних ${hoursLabel(sumDiff)}` : `Не хватает ${hoursLabel(-sumDiff)}`}
              </Badge>
            )}
          </div>
          <div className="kpi-value" style={{ marginTop: 6 }}>
            {sum}
            <span className="unit"> / {total} ч</span>
          </div>
          <div className="budget-bar" aria-hidden>
            {items.map((it, i) => (
              <div
                key={it.topic_id}
                className="budget-seg"
                title={`${it.topic_name}: ${hours[it.topic_id]} ч`}
                style={{
                  flexGrow: Math.max(0, hours[it.topic_id] ?? 0),
                  background: `color-mix(in oklab, var(--accent) ${100 - i * 14}%, var(--accent-2))`,
                }}
              />
            ))}
            {sumDiff < 0 && <div className="budget-seg" style={{ flexGrow: -sumDiff, background: 'var(--critical-bg)', outline: '1px dashed var(--critical)' }} />}
          </div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Изменено тем</div>
          <div className="kpi-value">
            {changedCount}
            <span className="unit"> из {items.length}</span>
          </div>
          <div className="kpi-sub">перенесено {hoursLabel(moved)}</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Ручные правки</div>
          <div className="kpi-value">{manualCount}</div>
          <div className="kpi-sub">{manualCount ? 'отклонение от рекомендации сохранится в плане' : 'вариант совпадает с рекомендацией'}</div>
        </div>
        <div className={`kpi ${errorCount ? 'tone-critical' : ''}`}>
          <div className="kpi-label">Проверки ограничений</div>
          <div className="kpi-value" style={{ fontSize: 20, marginTop: 12, letterSpacing: '-0.02em' }}>
            {errorCount === 0 ? (
              <span className="row" style={{ color: 'var(--good-text)', gap: 6 }}>
                <CheckCircle2 size={22} /> Пройдены
              </span>
            ) : (
              <span className="row" style={{ color: 'var(--critical-text)', gap: 6 }}>
                <XCircle size={22} /> {errorCount} {plural(errorCount, ['нарушение', 'нарушения', 'нарушений'])}
              </span>
            )}
          </div>
          <div className="kpi-sub">сумма · границы · блокировки · ±{maxChange} ч</div>
        </div>
      </div>

      {stale && (
        <div className="stale-bar no-print" role="status">
          <RotateCcw size={18} style={{ color: 'var(--warning-text)' }} />
          <div style={{ flex: 1 }}>
            <div className="strong">Расчёт устарел</div>
            <div className="small text-2">Ограничения или параметры изменились. Пересчитайте, чтобы рекомендации учли новые значения.</div>
          </div>
          <Button variant="primary" size="sm" icon={<Calculator size={15} />} onClick={runCalculate} disabled={!canCalculate} loading={loading}>
            Рассчитать
          </Button>
        </div>
      )}
      {previewError != null && (
        <Banner tone="critical" title="Расчёт не выполнен">
          {errorText(previewError).message}
        </Banner>
      )}
      {settingsError && <Banner tone="critical">{settingsError}</Banner>}

      <WarningsList warnings={preview.warnings} tone="info" />

      {/* ---------- Таблица ---------- */}
      <Refreshing active={loading} label="Пересчитываем…">
        <section className="card">
          <div className="card-head">
            <h2>
              <Sparkles size={18} /> Предложение для класса {preview.class_id}
            </h2>
            <Badge tone="outline">алгоритм {preview.algorithm_version}</Badge>
            <span className="spacer" />
            <InfoPopover align="right" title="Как строится предложение">
              <ul>
                <li>
                  Получатели — темы со средним ниже цели {preview.settings.target_pct}%: приоритет = важность × (цель − средний) / (1 + уже добавленные часы).
                </li>
                <li>Доноры — темы со средним от {preview.settings.donor_pct}%: часы снимаются у наиболее освоенных.</li>
                <li>Каждый перенос — ровно 1 час; изменение темы не больше ±{preview.settings.max_change} ч; границы и блокировки соблюдаются.</li>
                <li>Темы с выборкой меньше {preview.settings.min_students} учеников не получают автоматической рекомендации.</li>
                <li>Сумма часов не меняется. Рост баллов не прогнозируется.</li>
              </ul>
            </InfoPopover>
            <Button size="sm" variant="ghost" icon={<BarChart3 size={14} />} onClick={openAnalytics}>
              Аналитика класса
            </Button>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Тема</th>
                  <th className="r">Средний балл</th>
                  <th className="r">Текущие</th>
                  <th className="c">Мин</th>
                  <th className="c">Макс</th>
                  <th className="c">Важность</th>
                  <th className="c">Блок</th>
                  <th className="c">Предложено, ч</th>
                  <th className="c">Изменение</th>
                  <th>Объяснение</th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => {
                  const c = constraints[it.topic_id] || { min_hours: it.min_hours, max_hours: it.max_hours, importance: it.importance, is_locked: it.is_locked };
                  const base = baseConstraints[it.topic_id];
                  const h = hours[it.topic_id] ?? it.proposed_hours;
                  const delta = h - it.current_hours;
                  const err = rowErrors[it.topic_id];
                  const cErr = constraintErrors[it.topic_id];
                  const base0 = baselineOf(it);
                  const manual = h !== base0;
                  const lo = Math.max(it.min_hours, it.current_hours - maxChange);
                  const hi = Math.min(it.max_hours, it.current_hours + maxChange);
                  return (
                    <tr key={it.topic_id} className={err ? 'row-invalid' : it.is_locked ? 'row-locked' : ''}>
                      <td>
                        <div className="cell-topic">
                          <span className="t row" style={{ gap: 6 }}>
                            {it.is_locked && <Lock size={13} className="muted" aria-label="заблокирована" />}
                            {it.topic_name}
                          </span>
                          <span className="s">
                            {it.topic_id}
                            {it.test_version ? ` · ${it.test_version}` : ''}
                            {versionChoices[it.topic_id] && (
                              <select
                                className="select"
                                style={{ height: 24, width: 'auto', fontSize: 11, marginLeft: 6, padding: '0 22px 0 6px', backgroundPosition: 'right 6px center' }}
                                value={testVersions[it.topic_id] || ''}
                                onChange={(e) => {
                                  const v = e.target.value;
                                  setTestVersions((tv) => {
                                    const n = { ...tv };
                                    if (v) n[it.topic_id] = v;
                                    else delete n[it.topic_id];
                                    return n;
                                  });
                                }}
                                aria-label={`Версия теста для ${it.topic_name}`}
                              >
                                <option value="">версия?</option>
                                {versionChoices[it.topic_id].map((v) => (
                                  <option key={v} value={v}>
                                    {v}
                                  </option>
                                ))}
                              </select>
                            )}
                          </span>
                        </div>
                      </td>
                      <td className="r num">
                        <span className="strong">{fmtPct(it.mean_post_pct)}</span>
                        <div className="tiny muted">
                          n={fmtNum(it.n_post)}
                          {!it.automatic_eligible && !it.is_locked ? ' · без авто' : ''}
                        </div>
                      </td>
                      <td className="r num strong">{it.current_hours}</td>
                      <td className="c">
                        <input
                          className={`mini-input ${base && c.min_hours !== base.min_hours ? 'edited' : ''}`}
                          type="number"
                          min={0}
                          value={c.min_hours}
                          aria-label={`Минимум часов: ${it.topic_name}`}
                          onChange={(e) => setConstraint(it.topic_id, { min_hours: Math.round(Number(e.target.value || 0)) })}
                        />
                      </td>
                      <td className="c">
                        <input
                          className={`mini-input ${base && c.max_hours !== base.max_hours ? 'edited' : ''}`}
                          type="number"
                          min={0}
                          value={c.max_hours}
                          aria-label={`Максимум часов: ${it.topic_name}`}
                          onChange={(e) => setConstraint(it.topic_id, { max_hours: Math.round(Number(e.target.value || 0)) })}
                        />
                      </td>
                      <td className="c">
                        <select
                          className={`mini-input ${base && c.importance !== base.importance ? 'edited' : ''}`}
                          style={{ width: 52 }}
                          value={c.importance}
                          aria-label={`Важность: ${it.topic_name}`}
                          onChange={(e) => setConstraint(it.topic_id, { importance: Number(e.target.value) })}
                        >
                          {[1, 2, 3].map((v) => (
                            <option key={v} value={v}>
                              {v}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="c">
                        <Switch checked={c.is_locked} onChange={(v) => setConstraint(it.topic_id, { is_locked: v })} label={`Блокировка: ${it.topic_name}`} />
                      </td>
                      <td className="c">
                        <div className="stack-sm" style={{ alignItems: 'center', gap: 4 }}>
                          <HoursStepper
                            value={h}
                            min={lo}
                            max={hi}
                            disabled={it.is_locked || stale}
                            invalid={!!err}
                            changed={manual}
                            label={`Часы: ${it.topic_name}`}
                            onChange={(v) => setHours((hs) => ({ ...hs, [it.topic_id]: v }))}
                          />
                          {manual && (
                            <button
                              type="button"
                              className="reason-toggle tiny row"
                              style={{ gap: 3 }}
                              onClick={() => setHours((hs) => ({ ...hs, [it.topic_id]: base0 }))}
                              title="Вернуть рекомендацию"
                            >
                              <Undo2 size={11} /> рекоменд. {base0}
                            </button>
                          )}
                        </div>
                      </td>
                      <td className="c">
                        <span className={`delta ${delta > 0 ? 'up' : delta < 0 ? 'down' : ''}`}>{fmtSigned(delta)}</span>
                      </td>
                      <td>
                        {err && <div className="field-error strong" style={{ marginBottom: 4 }}>{err}</div>}
                        {cErr && <div className="field-error strong" style={{ marginBottom: 4 }}>Ограничения: {cErr}</div>}
                        {manual && <Badge tone="warning">ручная правка: {fmtSigned(h - it.proposed_hours)} к рекомендации</Badge>}
                        <Reason text={period ? period.reasons[it.topic_id] ?? it.reason : it.reason} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr>
                  <td className="strong" style={{ paddingLeft: 20 }}>
                    Итого
                  </td>
                  <td />
                  <td className="r num strong">{items.reduce((s, it) => s + it.current_hours, 0)}</td>
                  <td colSpan={4} />
                  <td className="c num strong" style={{ color: sumOk ? 'var(--good-text)' : 'var(--critical-text)' }}>
                    {sum} / {total}
                  </td>
                  <td className="c">
                    <span className={`delta ${sumDiff ? 'down' : ''}`}>{fmtSigned(sumDiff)}</span>
                  </td>
                  <td className="small muted">{sumOk ? 'Сумма сохранена' : 'Верните общую сумму, чтобы сохранить план'}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </section>
      </Refreshing>

      <div className="grid-2" style={{ alignItems: 'start' }}>
        <section className="card">
          <div className="card-head">
            <h3>
              <ArrowRight size={16} /> {period ? 'Как распределены часы' : 'Переносы по рекомендации'}
            </h3>
            <span className="spacer" />
            <Badge>{period ? items.length : preview.transfers.length}</Badge>
          </div>
          <div className="card-body">
            {period ? (
              <div className="transfers">
                {[...items]
                  .sort((a, b) => a.topic_order - b.topic_order)
                  .map((it) => (
                    <div className="transfer" key={it.topic_id}>
                      <span className="strong">{it.topic_name}</span>
                      <span className="tiny muted">
                        {it.is_locked ? 'заблокирована' : `мин ${it.min_hours} + ${period.added[it.topic_id] ?? 0} по приоритету`}
                      </span>
                      <span className="h">{hoursLabel(period.hours[it.topic_id] ?? 0)}</span>
                    </div>
                  ))}
              </div>
            ) : preview.transfers.length === 0 ? (
              <EmptyState title="Переносов нет">Свободных часов в рамках ограничений нет; требуется решение методиста.</EmptyState>
            ) : (
              <div className="transfers">
                {preview.transfers.map((t, i) => (
                  <div className="transfer" key={i}>
                    <span className="from">{topicName(t.from_topic_id)}</span>
                    <ArrowRight size={15} className="muted" />
                    <span className="to">{topicName(t.to_topic_id)}</span>
                    <span className="h">{hoursLabel(t.hours)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <h3>
              <Settings2 size={16} /> Параметры алгоритма
            </h3>
            <span className="spacer" />
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setSettings(DEFAULT_SETTINGS);
                setConstraints(baseConstraints);
              }}
            >
              По умолчанию
            </Button>
          </div>
          <div className="card-body">
            <div className="grid-2" style={{ gap: 12 }}>
              <NumField label="Цель, %" value={settings.target_pct} onChange={(v) => setSettings({ ...settings, target_pct: v })} hint="ниже — получатель часов" />
              <NumField label="Порог донора, %" value={settings.donor_pct} onChange={(v) => setSettings({ ...settings, donor_pct: v })} hint="от него — можно снять часы" />
              <NumField label="Мин. учеников" value={settings.min_students} onChange={(v) => setSettings({ ...settings, min_students: v })} hint="меньше — без авто-рекомендации" />
              <NumField label="Лимит изменения, ±ч" value={settings.max_change} onChange={(v) => setSettings({ ...settings, max_change: v })} hint="на одну тему" />
            </div>
            <p className="tiny muted" style={{ marginTop: 10 }}>
              У аналитики порог внимания {60}%, у планировщика цель {preview.settings.target_pct}% — это разные параметры. Изменения отмечают расчёт как устаревший.
            </p>
          </div>
        </section>
      </div>

      <section className="card">
        <div className="card-body">
          <div className="field">
            <label className="label" htmlFor="p-comment">
              Комментарий к плану
            </label>
            <textarea
              id="p-comment"
              className="textarea"
              maxLength={2000}
              placeholder="Например: согласовано с учителем, усилить дроби перед контрольной"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
          </div>
        </div>
      </section>


      {saveError != null && (
        <Banner tone="critical" title="Сервер отклонил план">
          {errorText(saveError).message}
        </Banner>
      )}

      {saved && (
        <AiExplain
          datasetId={datasetId}
          kind="plan"
          title="ИИ: объясни план учителю"
          hint="Простыми словами: откуда и куда идут часы, почему, какие риски. Сервер берёт данные из сохранённого снимка."
          selectors={() => ({ plan_id: saved.plan_id })}
        />
      )}

      {saved && (
        <div className="banner banner-good fade-up" role="status" style={{ alignItems: 'center' }}>
          <CheckCircle2 size={22} />
          <div style={{ flex: 1 }}>
            <div className="banner-title">План сохранён</div>
            <div className="small text-2">
              ID снимка: <span className="mono">{saved.plan_id}</span> · класс {saved.class_id}
              {saved.manually_modified ? ' · с ручными правками' : ''}. Каждое сохранение создаёт новый снимок.
            </div>
          </div>
          <Button variant="primary" icon={<FileText size={16} />} onClick={() => navigate(`/plans/${encodeURIComponent(saved.plan_id)}`)}>
            Открыть отчёт
          </Button>
        </div>
      )}

      <div className="action-bar no-print">
        <Button icon={<Calculator size={16} />} onClick={runCalculate} disabled={!canCalculate} loading={loading} variant={stale ? 'primary' : 'default'}>
          Рассчитать
        </Button>
        <Button icon={<RotateCcw size={16} />} variant="ghost" onClick={resetChanges} disabled={loading || (!stale && manualCount === 0)}>
          Сбросить изменения
        </Button>
        <span className="spacer" />
        <span className="small action-hint" style={{ color: canSave ? 'var(--good-text)' : 'var(--muted)', fontWeight: 600 }}>
          {!saveAllowed
            ? 'Сохранение отключено сервером'
            : stale
            ? 'Сначала пересчитайте'
            : !sumOk
              ? `Сумма ${sum} из ${total} ч`
              : errorCount
                ? 'Исправьте нарушения'
                : 'Можно сохранять'}
        </span>
        <Button
          variant={saved ? 'default' : 'primary'}
          icon={<Save size={16} />}
          onClick={savePlan}
          disabled={!canSave}
          loading={saving}
          title={saveAllowed ? undefined : readOnlyReason(features.readOnly)}
        >
          Сохранить план
        </Button>
        <Button
          variant={saved ? 'primary' : 'default'}
          icon={<FileText size={16} />}
          disabled={!saved}
          onClick={() => saved && navigate(`/plans/${encodeURIComponent(saved.plan_id)}`)}
          title={saved ? 'Открыть сохранённый отчёт' : 'Доступно после сохранения'}
        >
          Открыть отчёт
        </Button>
      </div>
    </div>
  );
}

function Reason({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > 90;
  return (
    <div className="reason" style={{ marginTop: 4 }}>
      {long && !open ? `${text.slice(0, 88)}…` : text}{' '}
      {long && (
        <button type="button" className="reason-toggle" onClick={() => setOpen((o) => !o)}>
          {open ? 'свернуть' : 'подробнее'}
        </button>
      )}
    </div>
  );
}

function NumField({ label, value, onChange, hint }: { label: string; value: number; onChange: (v: number) => void; hint?: string }) {
  return (
    <div className="field">
      <label className="label">{label}</label>
      <input className="input" type="number" value={value} onChange={(e) => onChange(Number(e.target.value))} />
      {hint && <span className="field-hint">{hint}</span>}
    </div>
  );
}
