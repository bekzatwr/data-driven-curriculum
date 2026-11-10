import { useCallback, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  AlertOctagon,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  CalendarRange,
  ChevronRight,
  ClipboardList,
  GitCompareArrows,
  Grid3X3,
  Percent,
  Scale,
  Sparkles,
  Table2,
  Users,
} from 'lucide-react';
import { api } from '../api/client';
import type { AnalyticsSettings, Overview, TopicMetrics } from '../api/types';
import { FilterBar } from '../components/FilterBar';
import { HeatLegend, Heatmap } from '../components/Heatmap';
import {
  Badge,
  Banner,
  Button,
  CloseButton,
  CountUp,
  DemoBadge,
  Drawer,
  EmptyState,
  ErrorState,
  InfoPopover,
  LoadingBlock,
  Meter,
  Refreshing,
  Skeleton,
  StatusBadge,
  StatusIcon,
  WarningsList,
} from '../components/ui';
import { fmtDate, fmtNum, fmtOne, fmtPct, fmtPp, fmtShare, isNum, plural } from '../lib/format';
import { STATUS_ORDER, TOPIC_STATUS } from '../lib/status';
import { useAsync } from '../lib/useAsync';
import { useDataset } from '../state/dataset';
import { AiExplain } from '../components/AiExplain';
import { Ring } from '../components/Ring';
import { CommentsPanel } from '../components/Comments';

type SortKey = 'order' | 'mean' | 'below' | 'status';

export function OverviewPage() {
  const { datasetId, dataset, shared, filters, resetShared } = useDataset();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const openTopic = params.get('topic');
  const [view, setView] = useState<'heatmap' | 'table'>('heatmap');

  const af = { class_ids: shared.classIds, textbook_ids: shared.textbookIds, test_version: shared.testVersion };
  const key = `${datasetId}|${JSON.stringify(af)}`;
  const state = useAsync((s) => api.overview(datasetId, af, s), key);
  const data = state.data;

  const setOpenTopic = useCallback(
    (id: string | null) => {
      const next = new URLSearchParams(params);
      if (id) next.set('topic', id);
      else next.delete('topic');
      setParams(next, { replace: true });
    },
    [params, setParams],
  );

  const filterSummary = useMemo(() => {
    const parts: string[] = [];
    parts.push(shared.classIds.length ? `классы ${shared.classIds.join(', ')}` : 'все классы');
    parts.push(shared.textbookIds.length ? `учебники: ${shared.textbookIds.join(', ')}` : 'все учебники');
    if (shared.testVersion) parts.push(`версия ${shared.testVersion}`);
    return parts.join(' · ');
  }, [shared]);

  return (
    <div className="stack" style={{ gap: 0 }}>
      <div className="page-head fade-up">
        <div style={{ flex: 1, minWidth: 280 }}>
          <div className="eyebrow">Шаг 2 · Обзор результатов</div>
          <h1>Где ученики испытывают трудности</h1>
          <p className="row-wrap" style={{ gap: 6 }}>
            <span className="strong" style={{ color: 'var(--text)' }}>
              {dataset.metadata.name}
            </span>
            <span>·</span>
            <span>
              {dataset.metadata.subject}, {dataset.metadata.grade} класс
            </span>
            <span className="row" style={{ gap: 4 }}>
              <CalendarRange size={14} /> {fmtDate(dataset.metadata.period_start)}–{fmtDate(dataset.metadata.period_end)}
            </span>
            {dataset.source_type === 'demo' && <DemoBadge />}
          </p>
        </div>
        <div className="row-wrap no-print">
          <Button icon={<GitCompareArrows size={16} />} onClick={() => navigate(`/datasets/${encodeURIComponent(datasetId)}/comparison`)}>
            Сравнить учебники
          </Button>
          <Button variant="primary" icon={<ClipboardList size={16} />} onClick={() => navigate(`/datasets/${encodeURIComponent(datasetId)}/plan`)}>
            Спланировать часы
          </Button>
        </div>
      </div>

      <FilterBar />

      {state.error != null && !data && (
        <div className="card">
          <ErrorState error={state.error} onRetry={state.reload} />
        </div>
      )}

      {state.error != null && data && (
        <div style={{ marginBottom: 16 }}>
          <Banner tone="critical" title="Не удалось применить фильтры" action={<Button size="sm" onClick={state.reload}>Повторить</Button>}>
            Ниже показаны данные для предыдущих фильтров.
          </Banner>
        </div>
      )}

      {state.loading && <OverviewSkeleton />}

      {data && (
        <Refreshing active={state.refreshing}>
          <OverviewBody
            data={data}
            filterSummary={filterSummary}
            view={view}
            setView={setView}
            onSelectTopic={setOpenTopic}
            classesTotal={filters.classes.length}
            onReset={resetShared}
          />
        </Refreshing>
      )}

      <TopicDrawer topicId={openTopic} onClose={() => setOpenTopic(null)} />
    </div>
  );
}

/** «Главный вывод» над KPI: сколько тем проблемные и где результат ниже всего (описательно, без причин). */
function Insight({ data, onSelectTopic }: { data: Overview; onSelectTopic: (id: string) => void }) {
  const thr = data.settings.threshold_pct;
  const ranked = data.topics
    .filter((t) => isNum(t.mean_post_pct))
    .sort((a, b) => (a.mean_post_pct as number) - (b.mean_post_pct as number));
  const worst = ranked[0];
  const problems = ranked.filter((t) => t.problem_topic);
  const n = data.metrics.n_problem_topics;
  const total = data.metrics.topic_count;
  const below = worst && (worst.mean_post_pct as number) < thr;
  return (
    <section className={`insight fade-up ${n > 0 ? 'bad' : 'ok'}`}>
      <span className="insight-icon">
        <Sparkles size={18} />
      </span>
      <div className="insight-body">
        <div className="insight-kicker">Главный вывод</div>
        <div className="insight-title">
          {n > 0 ? (
            <>
              <span className="grad-text">
                {n} {plural(n, ['тема', 'темы', 'тем'])} из {total}
              </span>{' '}
              — {plural(n, ['проблемная', 'проблемные', 'проблемные'])}
            </>
          ) : (
            'Проблемных тем нет'
          )}
        </div>
        <div className="insight-text">
          {below
            ? `Ниже всего «${worst.topic_name}»: ${fmtPct(worst.mean_post_pct)} при пороге ${fmtPct(thr)} — на ${fmtOne(thr - (worst.mean_post_pct as number))} п.п. ниже.`
            : `Все темы на уровне порога ${fmtPct(thr)} или выше.`}
        </div>
      </div>
      {problems.length > 0 && (
        <div className="insight-chips">
          {problems.slice(0, 3).map((t) => (
            <button type="button" key={t.topic_id} className="insight-chip" onClick={() => onSelectTopic(t.topic_id)}>
              <span>{t.topic_name}</span>
              <b>{fmtPct(t.mean_post_pct)}</b>
              <ChevronRight size={14} />
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

function OverviewSkeleton() {
  return (
    <div className="stack">
      <div className="grid-4">
        {[0, 1, 2, 3].map((i) => (
          <div className="card kpi" key={i}>
            <Skeleton h={14} w="50%" />
            <Skeleton h={30} w="60%" style={{ marginTop: 12 }} />
            <Skeleton h={12} w="80%" style={{ marginTop: 10 }} />
          </div>
        ))}
      </div>
      <div className="card">
        <LoadingBlock rows={7} />
      </div>
    </div>
  );
}

function OverviewBody({
  data,
  filterSummary,
  view,
  setView,
  onSelectTopic,
  classesTotal,
  onReset,
}: {
  onReset: () => void;
  data: Overview;
  filterSummary: string;
  view: 'heatmap' | 'table';
  setView: (v: 'heatmap' | 'table') => void;
  onSelectTopic: (id: string) => void;
  classesTotal: number;
}) {
  const { datasetId } = useDataset();
  const m = data.metrics;
  const s = data.settings;
  const empty = m.n_students === 0 || data.topics.every((t) => t.n_post === 0);
  const statusCounts = useMemo(() => {
    const map = new Map<string, number>();
    data.topics.forEach((t) => map.set(t.status, (map.get(t.status) || 0) + 1));
    return STATUS_ORDER.filter((st) => map.get(st)).map((st) => ({ st, n: map.get(st)! }));
  }, [data.topics]);
  const heatClasses = new Set(data.heatmap.map((h) => h.class_id)).size;

  if (empty) {
    return (
      <div className="card fade-up">
        <EmptyState
          title="В выбранной выборке нет результатов"
          icon={<Users size={26} />}
          action={
            <Button variant="primary" onClick={onReset}>
              Сбросить фильтры
            </Button>
          }
        >
          Для комбинации «{filterSummary}» данных нет. Это пустая выборка, а не нулевой балл — измените или сбросьте фильтры.
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="stack">
      <WarningsList warnings={[...data.warnings, ...m.warnings]} />

      <Insight data={data} onSelectTopic={onSelectTopic} />

      <div className="kpi-strip fade-up">
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Ученики</span>
            <span className="kpi-icon">
              <Users size={15} />
            </span>
          </div>
          <div className="kpi-value">
            <CountUp value={m.n_students} format={(v) => fmtNum(Math.round(v))} />
          </div>
          <div className="kpi-sub">
            с итоговым результатом: {fmtNum(m.n_post_students)} · с парой до/после: {fmtShare(m.paired_student_share)}
          </div>
        </div>

        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Итоговые результаты</span>
            <span className="kpi-icon">
              <ClipboardList size={15} />
            </span>
          </div>
          <div className="kpi-value">
            <CountUp value={m.n_post_results} format={(v) => fmtNum(Math.round(v))} />
          </div>
          <div className="kpi-sub">
            пар «ученик–тема» до/после: {fmtNum(m.n_pairs)} · покрытие {fmtShare(m.pair_coverage)}
          </div>
        </div>

        <div className={`kpi ${isNum(m.mean_post_pct) ? 'has-ring' : ''}`}>
          {isNum(m.mean_post_pct) && (
            <Ring value={m.mean_post_pct} marker={s.threshold_pct} tone={m.mean_post_pct < s.threshold_pct ? 'critical' : 'accent'}>
              <Percent size={14} />
            </Ring>
          )}
          <div className="kpi-top">
            <span className="kpi-label row" style={{ gap: 4 }}>
              Средний итоговый балл
              <InfoPopover iconOnly label="Как рассчитано: средний балл">
                <p>Сначала считается средний процент по доступным темам каждого ученика, затем — среднее этих индивидуальных средних. Ученик с большим числом результатов не получает больший вес.</p>
                <ul>
                  <li>Итоговая выборка: этап post, {fmtNum(m.n_post_students)} учеников.</li>
                  <li>Все темы есть у {fmtNum(m.n_complete_students)} из {fmtNum(m.n_post_students)}.</li>
                </ul>
              </InfoPopover>
            </span>
            <span className="kpi-icon">
              <Percent size={15} />
            </span>
          </div>
          <div className="kpi-value">
            {isNum(m.mean_post_pct) ? (
              <>
                <CountUp value={m.mean_post_pct} format={(v) => fmtOne(v)} />
                <span className="unit">%</span>
              </>
            ) : (
              <span style={{ fontSize: 20 }}>Нет данных</span>
            )}
          </div>
          <div className="kpi-sub">
            итоговая выборка, {fmtNum(m.n_post_students)} {plural(m.n_post_students, ['ученик', 'ученика', 'учеников'])}
            {m.n_complete_students < m.n_post_students ? ` · неполное покрытие тем (${fmtNum(m.n_complete_students)} с полным набором)` : ''}
          </div>
        </div>

        <div className={`kpi has-ring ${m.n_problem_topics > 0 ? 'tone-critical' : 'tone-good'}`}>
          <Ring value={m.n_problem_topics} max={Math.max(1, m.topic_count)} tone={m.n_problem_topics > 0 ? 'critical' : 'good'}>
            <AlertOctagon size={14} />
          </Ring>
          <div className="kpi-top">
            <span className="kpi-label row" style={{ gap: 4 }}>
              Проблемные темы
              <InfoPopover iconOnly label="Как рассчитано: проблемные темы" align="right">
                <ProblemRules s={s} />
              </InfoPopover>
            </span>
            <span className="kpi-icon">
              <AlertOctagon size={15} />
            </span>
          </div>
          <div className="kpi-value">
            <CountUp value={m.n_problem_topics} format={(v) => fmtNum(Math.round(v))} />
            <span className="unit"> из {m.topic_count}</span>
          </div>
          <div className="kpi-sub row-wrap" style={{ gap: 4 }}>
            {statusCounts.map(({ st, n }) => {
              const meta = TOPIC_STATUS[st as keyof typeof TOPIC_STATUS];
              return (
                <span key={st} className={`status tone-${meta.tone}`} style={{ fontSize: 12, marginRight: 6 }} title={meta.label}>
                  <StatusIcon tone={meta.tone} size={12} />
                  {n} {meta.label.toLowerCase()}
                </span>
              );
            })}
          </div>
        </div>
      </div>

      <section className="card fade-up-2">
        <div className="card-head">
          <h2>{view === 'heatmap' ? <Grid3X3 size={18} /> : <Table2 size={18} />} Темы</h2>
          <span className="small muted">{filterSummary}</span>
          <span className="spacer" />
          <InfoPopover align="right">
            <ProblemRules s={s} />
          </InfoPopover>
          <div className="segmented" role="tablist" aria-label="Вид">
            <button role="tab" aria-selected={view === 'heatmap'} className={view === 'heatmap' ? 'on' : ''} onClick={() => setView('heatmap')}>
              Теплокарта
            </button>
            <button role="tab" aria-selected={view === 'table'} className={view === 'table' ? 'on' : ''} onClick={() => setView('table')}>
              Таблица
            </button>
          </div>
        </div>
        {view === 'heatmap' ? (
          <>
            <div style={{ padding: '14px 20px 6px' }} className="row-wrap">
              <HeatLegend threshold={s.threshold_pct} />
              <span className="spacer" />
              <span className="small muted">
                Классов в карте: {heatClasses} из {classesTotal} · нажмите на тему или ячейку, чтобы открыть детали
              </span>
            </div>
            {data.heatmap.length === 0 ? (
              <EmptyState title="Нет данных для теплокарты">Для выбранных фильтров нет результатов по классам.</EmptyState>
            ) : (
              <Heatmap topics={data.topics} cells={data.heatmap} threshold={s.threshold_pct} onSelectTopic={onSelectTopic} />
            )}
          </>
        ) : (
          <TopicsTable topics={data.topics} settings={s} onSelect={onSelectTopic} />
        )}
      </section>

      <AiExplain
        datasetId={datasetId}
        kind="overview"
        title="ИИ: где трудности и что делать"
        context={() => ({
          is_demo: data.is_demo,
          filters: filterSummary,
          settings: s,
          metrics: {
            n_students: m.n_students,
            mean_post_pct: m.mean_post_pct,
            pair_coverage: m.pair_coverage,
            n_problem_topics: m.n_problem_topics,
            topic_count: m.topic_count,
          },
          topics: data.topics.map((t) => ({
            topic: t.topic_name,
            status: t.status_label,
            problem_topic: t.problem_topic,
            mean_post_pct: t.mean_post_pct,
            below_threshold_share: t.below_threshold_share,
            n_post: t.n_post,
            mean_gain_pp: t.mean_gain_pp,
          })),
        })}
        saveTo={{ type: 'dataset', id: 'overview' }}
      />
    </div>
  );
}

function ProblemRules({ s }: { s: AnalyticsSettings }) {
  return (
    <>
      <p>Статус темы строится по итоговым результатам (этап post) выбранной выборки.</p>
      <ul>
        <li>«Требует внимания» — средний ниже {fmtOne(s.threshold_pct)}%.</li>
        <li>«Нужно закрепление» — от {fmtOne(s.threshold_pct)}% до {fmtOne(s.mastered_pct)}%.</li>
        <li>«Освоено» — {fmtOne(s.mastered_pct)}% и выше.</li>
        <li>«Мало данных» — меньше {s.min_students} результатов: показатель виден, рекомендация не строится.</li>
        <li>«Разные версии» — тесты разных версий/шкал не объединяются.</li>
        <li>
          ▲ Проблемная тема — отдельный флаг: средний ниже {fmtOne(s.threshold_pct)}% или доля учеников ниже порога не меньше{' '}
          {fmtShare(s.problem_share)} (даже при приемлемом среднем).
        </li>
      </ul>
    </>
  );
}

function TopicsTable({ topics, settings, onSelect }: { topics: TopicMetrics[]; settings: AnalyticsSettings; onSelect: (id: string) => void }) {
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: 'order', dir: 1 });
  const sorted = useMemo(() => {
    const val = (t: TopicMetrics): number => {
      switch (sort.key) {
        case 'mean':
          return t.mean_post_pct ?? Number.POSITIVE_INFINITY;
        case 'below':
          return t.below_threshold_share ?? Number.NEGATIVE_INFINITY;
        case 'status':
          return STATUS_ORDER.indexOf(t.status);
        default:
          return t.topic_order;
      }
    };
    return [...topics].sort((a, b) => (val(a) - val(b)) * sort.dir || a.topic_order - b.topic_order);
  }, [topics, sort]);

  const SortTh = ({ k, children, className, defaultDir = 1 }: { k: SortKey; children: React.ReactNode; className?: string; defaultDir?: 1 | -1 }) => {
    const on = sort.key === k;
    const Icon = !on ? ArrowUpDown : sort.dir === 1 ? ArrowUp : ArrowDown;
    return (
      <th className={className} aria-sort={on ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none'}>
        <button type="button" className={`th-sort ${on ? 'on' : ''}`} onClick={() => setSort(on ? { key: k, dir: (sort.dir * -1) as 1 | -1 } : { key: k, dir: defaultDir })}>
          {children}
          <Icon size={12} />
        </button>
      </th>
    );
  };

  return (
    <div className="table-wrap">
      <table className="table hover clickable">
        <thead>
          <tr>
            <SortTh k="order">Тема</SortTh>
            <SortTh k="mean">Средний итоговый</SortTh>
            <SortTh k="below" className="r" defaultDir={-1}>
              Ниже {fmtOne(settings.threshold_pct)}%
            </SortTh>
            <th className="r">Учеников (итог)</th>
            <th className="r">Пары до/после</th>
            <th className="r">Прирост</th>
            <SortTh k="status">Статус</SortTh>
          </tr>
        </thead>
        <tbody>
          {sorted.map((t) => (
            <tr
              key={t.topic_id}
              onClick={() => onSelect(t.topic_id)}
              tabIndex={0}
              onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onSelect(t.topic_id))}
              aria-label={`Открыть тему ${t.topic_name}`}
            >
              <td>
                <div className="cell-topic">
                  <span className="t row" style={{ gap: 6 }}>
                    {t.topic_name}
                    {t.problem_topic && (
                      <span title="Проблемная тема" style={{ color: 'var(--critical-text)', fontSize: 11 }}>
                        ▲
                      </span>
                    )}
                  </span>
                  <span className="s">
                    {t.topic_id}
                    {t.test_version ? ` · ${t.test_version}` : ''}
                    {!t.single_version ? ' · несколько версий' : ''}
                  </span>
                </div>
              </td>
              <td>
                <div className="metric-cell">
                  <span className="v">{fmtPct(t.mean_post_pct)}</span>
                  <Meter
                    value={t.mean_post_pct}
                    mark={settings.threshold_pct}
                    color={
                      !isNum(t.mean_post_pct)
                        ? undefined
                        : t.mean_post_pct < settings.threshold_pct
                          ? 'var(--critical)'
                          : t.mean_post_pct < settings.mastered_pct
                            ? 'var(--warning)'
                            : 'var(--good)'
                    }
                  />
                </div>
              </td>
              <td className="r num strong">{fmtShare(t.below_threshold_share)}</td>
              <td className="r num">{fmtNum(t.n_post)}</td>
              <td className="r num">
                {fmtNum(t.n_pairs)} <span className="muted small">({fmtShare(t.pair_coverage, '—')})</span>
              </td>
              <td className="r num">{fmtPp(t.mean_gain_pp)}</td>
              <td>
                <StatusBadge status={t.status} label={t.status_label} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ================= Детали темы ================= */

function TopicDrawer({ topicId, onClose }: { topicId: string | null; onClose: () => void }) {
  const { datasetId, shared, topicName, comparison, setComparison } = useDataset();
  const navigate = useNavigate();
  const af = { class_ids: shared.classIds, textbook_ids: shared.textbookIds, test_version: shared.testVersion };
  const state = useAsync(topicId ? (s) => api.topic(datasetId, topicId, af, s) : null, `${topicId}|${JSON.stringify(af)}`);
  const d = state.data && state.data.metrics.topic_id === topicId ? state.data : undefined;

  const goCompare = () => {
    if (!topicId) return;
    setComparison({ ...comparison, topicId });
    navigate(`/datasets/${encodeURIComponent(datasetId)}/comparison`);
  };

  return (
    <Drawer open={!!topicId} onClose={onClose} labelledBy="topic-drawer-title">
      <div className="drawer-head">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="small muted">Тема</div>
          <h2 id="topic-drawer-title">{topicId ? topicName(topicId) : ''}</h2>
          {d && (
            <div className="row-wrap" style={{ marginTop: 8 }}>
              <StatusBadge status={d.metrics.status} label={d.metrics.status_label} />
              {d.metrics.problem_topic && <Badge tone="critical">▲ Проблемная тема</Badge>}
              {d.metrics.test_version && <Badge tone="outline">Версия {d.metrics.test_version}</Badge>}
            </div>
          )}
        </div>
        <CloseButton onClick={onClose} />
      </div>
      <div className="drawer-body">
        {state.error != null && <ErrorState error={state.error} onRetry={state.reload} compact />}
        {!d && state.error == null && <LoadingBlock rows={6} />}
        {d && (
          <div className="stack">
            <WarningsList warnings={[...d.warnings, ...d.metrics.warnings]} />
            <div className="book-stats" style={{ marginTop: 0 }}>
              <div className="stat">
                <div className="k">Средний итоговый · итоговая выборка</div>
                <div className="v big">{fmtPct(d.metrics.mean_post_pct)}</div>
                <div className="tiny muted">{fmtNum(d.metrics.n_post)} результатов</div>
              </div>
              <div className="stat">
                <div className="k">Ниже порога {fmtOne(d.settings.threshold_pct)}%</div>
                <div className="v big">{fmtShare(d.metrics.below_threshold_share)}</div>
                <div className="tiny muted">доля учеников с итогом</div>
              </div>
              <div className="stat">
                <div className="k">До → после · парная выборка</div>
                <div className="v">
                  {fmtPct(d.metrics.mean_pre_paired_pct, '—')} → {fmtPct(d.metrics.mean_post_paired_pct, '—')}
                </div>
                <div className="tiny muted">
                  {fmtNum(d.metrics.n_pairs)} пар · покрытие {fmtShare(d.metrics.pair_coverage)}
                </div>
              </div>
              <div className="stat">
                <div className="k">Прирост · парная выборка</div>
                <div className="v">{fmtPp(d.metrics.mean_gain_pp)}</div>
                <div className="tiny muted">{isNum(d.metrics.mean_pre_paired_pct) ? 'одни и те же ученики' : 'нет входного теста — прирост недоступен'}</div>
              </div>
            </div>

            <div>
              <div className="section-title" style={{ marginBottom: 10 }}>
                По классам
                <span className="small muted" style={{ fontWeight: 500 }}>
                  · средний итоговый, черта — порог {fmtOne(d.settings.threshold_pct)}%
                </span>
              </div>
              {d.by_class.length === 0 ? (
                <EmptyState title="Нет данных по классам" />
              ) : (
                <div className="bars">
                  {d.by_class.map((c, i) => (
                    <div className="bar-row" key={c.class_id} title={`${c.class_id}: ${fmtPct(c.metrics.mean_post_pct)}, n=${c.metrics.n_post}`}>
                      <span className="strong">{c.class_id}</span>
                      <div className="bar-track">
                        {isNum(c.metrics.mean_post_pct) && (
                          <div
                            className="bar-fill"
                            style={{
                              width: `${Math.min(100, c.metrics.mean_post_pct)}%`,
                              background: c.metrics.mean_post_pct < d.settings.threshold_pct ? 'var(--critical)' : 'var(--series-a)',
                              animationDelay: `${i * 60}ms`,
                            }}
                          />
                        )}
                        <div className="bar-mark" style={{ left: `${d.settings.threshold_pct}%` }} />
                      </div>
                      <span className="num r strong" style={{ textAlign: 'right' }}>
                        {fmtPct(c.metrics.mean_post_pct, '—')}
                        <span className="tiny muted" style={{ display: 'block', fontWeight: 400 }}>
                          n={fmtNum(c.metrics.n_post)}
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
              )}
              <div className="table-wrap" style={{ marginTop: 14 }}>
                <table className="table table-compact">
                  <thead>
                    <tr>
                      <th>Класс</th>
                      <th className="r">До</th>
                      <th className="r">После</th>
                      <th className="r">Прирост</th>
                      <th className="r">Пары</th>
                      <th>Статус</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.by_class.map((c) => (
                      <tr key={c.class_id}>
                        <td className="strong">{c.class_id}</td>
                        <td className="r num">{fmtPct(c.metrics.mean_pre_paired_pct, '—')}</td>
                        <td className="r num">{fmtPct(c.metrics.mean_post_paired_pct, '—')}</td>
                        <td className="r num">{fmtPp(c.metrics.mean_gain_pp, { fallback: '—' })}</td>
                        <td className="r num">{fmtNum(c.metrics.n_pairs)}</td>
                        <td>
                          <StatusBadge status={c.metrics.status} label={c.metrics.status_label} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <AiExplain
              compact
              datasetId={datasetId}
              kind="topic"
              title="ИИ: разбор темы"
              context={() => ({ is_demo: d.is_demo, settings: d.settings, metrics: d.metrics, by_class: d.by_class.map((c) => ({ class_id: c.class_id, ...c.metrics })) })}
              saveTo={{ type: 'topic', id: d.metrics.topic_id }}
            />
            <CommentsPanel
              datasetId={datasetId}
              target={{ type: 'topic', id: d.metrics.topic_id }}
              title="Обсуждение темы"
              placeholder="Что мешает ученикам в этой теме? Какие задания и методы помогают?"
            />

            {d.slices.length > 1 && (
              <div>
                <div className="section-title" style={{ marginBottom: 8 }}>
                  Версии теста
                </div>
                <Banner tone="info">Версии с разными шкалами не объединяются — смотрите каждую отдельно.</Banner>
                <div className="table-wrap" style={{ marginTop: 10 }}>
                  <table className="table table-compact">
                    <thead>
                      <tr>
                        <th>Версия</th>
                        <th className="r">Макс. балл</th>
                        <th className="r">Средний</th>
                        <th className="r">n</th>
                        <th>Статус</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.slices.map((sl) => (
                        <tr key={sl.test_version || 'none'}>
                          <td>{sl.test_version}</td>
                          <td className="r num">{sl.max_score ?? '—'}</td>
                          <td className="r num">{fmtPct(sl.mean_post_pct)}</td>
                          <td className="r num">{fmtNum(sl.n_post)}</td>
                          <td>
                            <StatusBadge status={sl.status} label={sl.status_label} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      <div className="drawer-foot">
        <Button variant="primary" icon={<GitCompareArrows size={16} />} onClick={goCompare} disabled={!topicId}>
          Сравнить учебники по теме
        </Button>
        <Button icon={<Scale size={16} />} onClick={() => navigate(`/datasets/${encodeURIComponent(datasetId)}/plan`)}>
          К плану часов
        </Button>
      </div>
    </Drawer>
  );
}
