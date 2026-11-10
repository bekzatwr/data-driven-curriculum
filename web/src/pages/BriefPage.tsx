import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Printer, ScrollText } from 'lucide-react';
import { api, ApiError } from '../api/client';
import type { Comparison, Overview, SavedPlan } from '../api/types';
import { Brand } from '../components/Logo';
import { Badge, Button, DemoBadge, ErrorState, LoadingBlock, StatusBadge } from '../components/ui';
import { fmtDate, fmtDateTimeUtc5, fmtNum, fmtPct, fmtPp, fmtShare, fmtSigned, isNum, plural } from '../lib/format';
import { COMPARISON_STATUS } from '../lib/status';
import { readOnlyReason, useFeatures } from '../lib/features';
import { getRecentPlans } from '../lib/storage';
import { useAsync } from '../lib/useAsync';
import { useApp } from '../state/app';
import { useDataset } from '../state/dataset';

/**
 * «Справка для педсовета» — служебный документ на 1–2 листа A4 из уже рассчитанных сервером
 * показателей: итоги по темам, описательное сравнение учебников и сохранённый план часов.
 * Ничего не пересчитывает и не прогнозирует; формулировки — описательные.
 */
export function BriefPage() {
  const { datasetId, dataset, filters } = useDataset();
  const { lastPlanId } = useApp();
  const features = useFeatures();
  const saveAllowed = !features.off('plan_save');
  const books = filters.textbooks;
  const bookA = books[0]?.id ?? null;
  const bookB = books[1]?.id ?? null;

  const overview = useAsync((s) => api.overview(datasetId, {}, s), `brief-ov|${datasetId}`);
  const comparisons = useAsync(
    async (s) => {
      if (!bookA || !bookB) return [] as Comparison[];
      return Promise.all(filters.topics.map((t) => api.comparison(datasetId, { topic_id: t.topic_id, textbook_a: bookA, textbook_b: bookB }, s)));
    },
    `brief-cmp|${datasetId}|${bookA}|${bookB}`,
  );

  // План: последние сохранённые снимки этого набора (история этого браузера).
  const plans = useMemo(() => getRecentPlans().filter((p) => p.dataset_id === datasetId), [datasetId, lastPlanId]);
  // ?plan=<id> — конкретный снимок (кнопка из отчёта, ссылка для коллег); иначе последний сохранённый.
  const [params] = useSearchParams();
  const [planId, setPlanId] = useState<string | null>(() => params.get('plan') || plans[0]?.plan_id || null);
  const plan = useAsync(
    async (s): Promise<SavedPlan | null> => {
      if (!planId) return null;
      try {
        return await api.getPlan(planId, s);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
    `brief-plan|${planId}`,
  );

  const now = new Date().toISOString();

  return (
    <div className="stack" style={{ gap: 16 }}>
      <div className="row-wrap no-print brief-toolbar">
        <Link to={`/datasets/${encodeURIComponent(datasetId)}/overview`} className="btn btn-ghost btn-sm">
          <ArrowLeft size={15} /> К обзору
        </Link>
        <span className="spacer" />
        {plans.length > 1 && planId && plans.some((p) => p.plan_id === planId) && (
          <label className="row small muted" style={{ gap: 8 }}>
            План в справке
            <select className="select" style={{ width: 'auto' }} value={planId ?? ''} onChange={(e) => setPlanId(e.target.value || null)}>
              {plans.map((p) => (
                <option key={p.plan_id} value={p.plan_id}>
                  {p.class_id} · {fmtDateTimeUtc5(p.created_at)}
                </option>
              ))}
            </select>
          </label>
        )}
        <Button variant="primary" icon={<Printer size={16} />} onClick={() => window.print()}>
          Печать / PDF
        </Button>
      </div>

      <article className="card brief-sheet">
        <header className="brief-head">
          <Brand size={30} tagline="Справка для педагогического совета" />
          <div className="brief-meta">
            <div>{fmtDateTimeUtc5(now)}</div>
            <div className="tiny muted mono">набор {dataset.id.slice(0, 8)}</div>
          </div>
        </header>

        <h1 className="brief-title">
          <ScrollText size={22} className="no-print" /> Результаты по темам и предложения по учебным часам
        </h1>
        <p className="brief-sub">
          {dataset.metadata.subject}, {dataset.metadata.grade} класс · период {fmtDate(dataset.metadata.period_start)}–
          {fmtDate(dataset.metadata.period_end)} · {dataset.metadata.name} {dataset.source_type === 'demo' && <DemoBadge />}
        </p>

        {overview.error != null && <ErrorState error={overview.error} onRetry={overview.reload} compact />}
        {overview.loading && <LoadingBlock rows={4} />}
        {overview.data && <OverviewSection data={overview.data} />}

        <section className="brief-section">
          <h2>2. Сравнение учебников</h2>
          {!bookA || !bookB ? (
            <p className="muted">В наборе меньше двух учебников — сравнение не проводится.</p>
          ) : comparisons.error != null ? (
            <ErrorState error={comparisons.error} onRetry={comparisons.reload} compact />
          ) : !comparisons.data ? (
            <LoadingBlock rows={3} />
          ) : (
            <ComparisonSection data={comparisons.data} labelA={books[0].label} labelB={books[1].label} topicName={(id) => filters.topics.find((t) => t.topic_id === id)?.topic_name ?? id} />
          )}
        </section>

        <section className="brief-section">
          <h2>3. План учебных часов</h2>
          {!planId ? (
            <p className="muted">
              {saveAllowed
                ? 'Сохранённого плана для этого набора нет. Составьте и сохраните план на шаге «План часов» — он появится в справке.'
                : `${readOnlyReason(features.readOnly)} Поэтому справка здесь без раздела плана; расчёт плана можно посмотреть на шаге «План часов».`}
            </p>
          ) : plan.error != null ? (
            <ErrorState error={plan.error} onRetry={plan.reload} compact />
          ) : plan.loading && !plan.data ? (
            <LoadingBlock rows={3} />
          ) : plan.data ? (
            <PlanSection plan={plan.data} />
          ) : (
            <p className="muted">Сохранённый план не найден на сервере (возможно, данные стенда сброшены). Сохраните план заново.</p>
          )}
        </section>

        <section className="brief-section brief-notes">
          <h2>4. Оговорки</h2>
          <ul>
            <li>Показатели рассчитаны сервером по загруженным результатам; справка их не пересчитывает.</li>
            <li>Сравнение учебников описательное и не доказывает причинного влияния; «лучший учебник» не определяется.</li>
            <li>Предложение по часам не прогнозирует рост баллов. Решение принимает методист и педагогический совет.</li>
            {dataset.source_type === 'demo' && <li>Данные набора искусственные (синтетические), не относятся к реальным ученикам.</li>}
          </ul>
        </section>

        <footer className="brief-sign">
          <div>
            <span>Методист</span>
            <i />
            <small>подпись / ФИО</small>
          </div>
          <div>
            <span>Заместитель директора по УР</span>
            <i />
            <small>подпись / ФИО</small>
          </div>
          <div>
            <span>Дата рассмотрения</span>
            <i />
            <small>«___» __________ 20__ г.</small>
          </div>
        </footer>
      </article>
    </div>
  );
}

function OverviewSection({ data }: { data: Overview }) {
  const m = data.metrics;
  const thr = data.settings.threshold_pct;
  const ranked = [...data.topics].filter((t) => isNum(t.mean_post_pct)).sort((a, b) => (a.mean_post_pct as number) - (b.mean_post_pct as number));
  const worst = ranked[0];
  return (
    <section className="brief-section">
      <h2>1. Итоги по темам</h2>
      <div className="brief-kpis">
        <div>
          <b>{fmtNum(m.n_students)}</b>
          <span>{plural(m.n_students, ['ученик', 'ученика', 'учеников'])}</span>
        </div>
        <div>
          <b>{fmtPct(m.mean_post_pct)}</b>
          <span>средний итоговый балл</span>
        </div>
        <div className={m.n_problem_topics > 0 ? 'bad' : ''}>
          <b>
            {m.n_problem_topics} из {m.topic_count}
          </b>
          <span>проблемных тем</span>
        </div>
        <div>
          <b>{fmtPct(thr)}</b>
          <span>порог освоения</span>
        </div>
      </div>
      {worst && (
        <p className="brief-lead">
          {(worst.mean_post_pct as number) < thr
            ? `Ниже всего результат по теме «${worst.topic_name}»: ${fmtPct(worst.mean_post_pct)} при пороге ${fmtPct(thr)}, ниже порога — ${fmtShare(worst.below_threshold_share)} учеников.`
            : `Все темы на уровне порога ${fmtPct(thr)} или выше.`}
        </p>
      )}
      <table className="table brief-table">
        <thead>
          <tr>
            <th>Тема</th>
            <th className="r">Средний итог</th>
            <th className="r">Ниже порога</th>
            <th className="r">Прирост</th>
            <th>Статус</th>
          </tr>
        </thead>
        <tbody>
          {data.topics.map((t) => (
            <tr key={t.topic_id}>
              <td className="strong">{t.topic_name}</td>
              <td className="r num">{fmtPct(t.mean_post_pct)}</td>
              <td className="r num">{fmtShare(t.below_threshold_share)}</td>
              <td className="r num">{fmtPp(t.mean_gain_pp, { fallback: '—' })}</td>
              <td>
                <StatusBadge status={t.status} label={t.status_label} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function ComparisonSection({ data, labelA, labelB, topicName }: { data: Comparison[]; labelA: string; labelB: string; topicName: (id: string) => string }) {
  const comparable = data.filter((c) => c.comparison_status === 'comparable');
  return (
    <>
      <p className="brief-lead">
        Прирост «до → после» на одних и тех же учениках: {labelA} против {labelB}. Сопоставимых тем — {comparable.length} из {data.length}
        {comparable.length < data.length ? '; для остальных разница не показывается.' : '.'}
      </p>
      <table className="table brief-table">
        <thead>
          <tr>
            <th>Тема</th>
            <th className="r">Прирост A</th>
            <th className="r">Прирост B</th>
            <th className="r">Разница A − B</th>
            <th>Статус</th>
          </tr>
        </thead>
        <tbody>
          {data.map((c) => {
            const st = COMPARISON_STATUS[c.comparison_status];
            const ok = c.comparison_status === 'comparable';
            return (
              <tr key={c.topic_id}>
                <td className="strong">{topicName(c.topic_id)}</td>
                <td className="r num">{fmtPp(c.group_a.mean_gain_pp, { fallback: '—' })}</td>
                <td className="r num">{fmtPp(c.group_b.mean_gain_pp, { fallback: '—' })}</td>
                <td className="r num strong">{ok ? fmtPp(c.difference_gain_pp, { fallback: '—' }) : '—'}</td>
                <td>
                  <Badge tone={st.tone === 'good' ? 'good' : st.tone === 'serious' ? 'serious' : 'neutral'}>{st.label}</Badge>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}

function PlanSection({ plan }: { plan: SavedPlan }) {
  const isPeriod = plan.settings.mode === 'period' || plan.algorithm_version === 'period_v1';
  const changed = plan.items.filter((i) => i.proposed_hours !== i.current_hours);
  return (
    <>
      <p className="brief-lead">
        Класс {plan.class_id} · всего {plan.total_hours} ч (сумма не меняется) ·{' '}
        {isPeriod ? 'распределение на весь период' : `перераспределение ±${plan.settings.max_change} ч`} · снимок от {fmtDateTimeUtc5(plan.created_at)}
        {plan.manually_modified ? ' · с ручными правками методиста' : ''}. Изменено тем: {changed.length} из {plan.items.length}.
      </p>
      <table className="table brief-table">
        <thead>
          <tr>
            <th>Тема</th>
            <th className="r">Было</th>
            <th className="r">Станет</th>
            <th className="r">Изм.</th>
            <th>Обоснование рекомендации</th>
          </tr>
        </thead>
        <tbody>
          {plan.items.map((i) => (
            <tr key={i.topic_id}>
              <td className="strong">
                {i.topic_name}
                {i.manually_modified && <span className="tiny muted"> · вручную</span>}
              </td>
              <td className="r num">{i.current_hours}</td>
              <td className="r num strong">{i.proposed_hours}</td>
              <td className="r num">{fmtSigned(i.proposed_hours - i.current_hours)}</td>
              <td className="brief-reason">{i.recommendation_reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {plan.comment && <p className="small">Комментарий методиста: {plan.comment}</p>}
      <p className="tiny muted no-print">
        Полный отчёт по плану: <Link to={`/plans/${encodeURIComponent(plan.plan_id)}`}>открыть</Link>
      </p>
    </>
  );
}
