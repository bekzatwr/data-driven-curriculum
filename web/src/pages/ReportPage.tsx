import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Braces, Check, Download, FileText, Link2, Lock, MessageSquare, Printer } from 'lucide-react';
import { api } from '../api/client';
import type { SavedPlan } from '../api/types';
import { Badge, Banner, Button, CloseButton, Drawer, ErrorState, LoadingBlock, WarningsList, errorText, useToast } from '../components/ui';
import { AiExplain } from '../components/AiExplain';
import { CommentsPanel } from '../components/Comments';
import { Brand } from '../components/Logo';
import { fmtDate, fmtDateTimeUtc5, fmtNum, fmtPct, fmtSigned, hours as hoursLabel, shortId } from '../lib/format';
import { rememberPlan } from '../lib/storage';
import { useAsync } from '../lib/useAsync';
import { useApp } from '../state/app';

export function ReportPage() {
  const { planId = '' } = useParams();
  const state = useAsync((s) => api.getPlan(planId, s), planId);
  const { setLastPlanId, setCurrent } = useApp();

  useEffect(() => {
    const p = state.data;
    if (!p) return;
    setLastPlanId(p.plan_id);
    setCurrent({ id: p.dataset_id, name: p.source.metadata.name, isDemo: p.is_demo });
    rememberPlan({
      plan_id: p.plan_id,
      dataset_id: p.dataset_id,
      dataset_name: p.source.metadata.name,
      class_id: p.class_id,
      created_at: p.created_at,
      total_hours: p.total_hours,
      is_demo: p.is_demo,
      manually_modified: p.manually_modified,
    });
  }, [state.data, setLastPlanId, setCurrent]);

  if (state.error != null) {
    return (
      <div className="card report">
        <ErrorState error={state.error} onRetry={state.reload} />
        <div style={{ textAlign: 'center', paddingBottom: 24 }}>
          <Link to="/reports">Все отчёты</Link>
        </div>
      </div>
    );
  }
  if (!state.data) {
    return (
      <div className="card report">
        <LoadingBlock rows={8} label="Открываем сохранённый план…" />
      </div>
    );
  }
  return <Report plan={state.data} />;
}

function Report({ plan }: { plan: SavedPlan }) {
  const navigate = useNavigate();
  const toast = useToast();
  const [downloading, setDownloading] = useState(false);
  const [copied, setCopied] = useState(false);
  const src = plan.source;
  const items = [...plan.items].sort((a, b) => a.topic_order - b.topic_order);
  const changed = items.filter((i) => i.proposed_hours !== i.current_hours);
  const moved = items.reduce((s, i) => s + Math.max(0, i.proposed_hours - i.current_hours), 0);
  const manual = items.filter((i) => i.manually_modified);
  const name = (tid: string) => items.find((i) => i.topic_id === tid)?.topic_name || tid;
  const isPeriod = plan.comment.startsWith('[План на весь период]');
  const comment = isPeriod ? plan.comment.replace('[План на весь период]', '').trim() : plan.comment;
  const [openTopic, setOpenTopic] = useState<string | null>(null);
  const counts = useAsync((sig) => api.comments(plan.dataset_id, { type: 'plan_topic' }, sig), `pt|${plan.plan_id}|${openTopic ?? ''}`);
  const countFor = (tid: string) => counts.data?.items.filter((c) => c.target_id === `${plan.plan_id}:${tid}`).length ?? 0;
  const openItem = openTopic ? items.find((x) => x.topic_id === openTopic) : undefined;

  const downloadCsv = async () => {
    setDownloading(true);
    try {
      const file = await api.downloadPlanCsv(plan.plan_id, `plan-${plan.class_id}-${plan.plan_id.slice(0, 8)}.csv`.replace(/[^\w.\-А-Яа-яЁё]/g, '_'));
      toast({ tone: 'good', title: 'CSV скачан', message: file });
    } catch (e) {
      toast({ tone: 'critical', title: 'Не удалось скачать CSV', message: errorText(e).message });
    } finally {
      setDownloading(false);
    }
  };

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      toast({ tone: 'info', title: 'Скопируйте адрес из строки браузера' });
    }
  };

  return (
    <div className="report stack">
      <div className="row-wrap no-print fade-up">
        <Button
          variant="ghost"
          icon={<ArrowLeft size={16} />}
          onClick={() => navigate(`/datasets/${encodeURIComponent(plan.dataset_id)}/plan?class=${encodeURIComponent(plan.class_id)}`)}
        >
          К плану класса {plan.class_id}
        </Button>
        <span className="spacer" />
        <Button icon={copied ? <Check size={16} /> : <Link2 size={16} />} onClick={copyLink}>
          {copied ? 'Скопировано' : 'Ссылка'}
        </Button>
        <a className="btn" href={api.planJsonUrl(plan.plan_id)} target="_blank" rel="noreferrer">
          <Braces size={16} /> JSON
        </a>
        <Button icon={<Download size={16} />} onClick={downloadCsv} loading={downloading}>
          Скачать CSV
        </Button>
        <Button variant="primary" icon={<Printer size={16} />} onClick={() => window.print()}>
          Печать
        </Button>
      </div>

      <article className="card report-sheet fade-up-2">
        <header className="report-head">
          <div style={{ flex: 1, minWidth: 260 }}>
            <Brand size={26} tagline="Отчёт по плану учебных часов" />
            <h1 style={{ marginTop: 6 }}>План учебных часов · класс {plan.class_id}</h1>
            <div className="text-2" style={{ marginTop: 6 }}>
              {src.metadata.subject}, {src.metadata.grade} класс · период {fmtDate(src.metadata.period_start)}–{fmtDate(src.metadata.period_end)}
            </div>
          </div>
          <div className="stack-sm" style={{ alignItems: 'flex-end' }}>
            {plan.is_demo && <span className="demo-stamp">🧪 Искусственные данные</span>}
            {isPeriod ? (
              <Badge tone="accent">План на весь период</Badge>
            ) : (
              <Badge tone={plan.manually_modified ? 'warning' : 'good'}>{plan.manually_modified ? 'С ручными правками' : 'По рекомендации'}</Badge>
            )}
          </div>
        </header>

        <div className="report-meta">
          <Meta k="Дата формирования" v={fmtDateTimeUtc5(plan.created_at)} />
          <Meta k="ID плана" v={<span className="mono">{plan.plan_id}</span>} />
          <Meta k="Набор данных" v={src.metadata.name} />
          <Meta k="ID набора" v={<span className="mono">{plan.dataset_id}</span>} />
          <Meta
            k="Источник"
            v={`${src.source_type === 'demo' ? 'Демонабор (искусственный)' : 'Импорт CSV'} · загружен ${fmtDateTimeUtc5(src.created_at)}`}
          />
          <Meta k="Контрольная сумма" v={<span className="mono" title={src.content_hash}>{shortId(src.content_hash, 16)}</span>} />
          <Meta
            k="Выборка набора"
            v={`${fmtNum(src.counts.students)} учеников · ${fmtNum(src.counts.classes)} кл. · ${fmtNum(src.counts.topics)} тем · ${fmtNum(src.counts.results)} записей`}
          />
          <Meta
            k="Настройки порогов"
            v={`цель ${plan.settings.target_pct}% · донор от ${plan.settings.donor_pct}% · мин. ${plan.settings.min_students} учеников · лимит ±${plan.settings.max_change} ч`}
          />
          <Meta k="Алгоритм" v={plan.algorithm_version} />
          <Meta
            k="Версии тестов"
            v={Object.keys(plan.applied_filters.test_versions || {}).length ? Object.entries(plan.applied_filters.test_versions).map(([t, v]) => `${name(t)}: ${v}`).join(', ') : 'единственные доступные'}
          />
        </div>

        <div className="counts-strip" style={{ marginBottom: 8 }}>
          <div className="stat">
            <div className="k">Всего часов</div>
            <div className="v">{plan.total_hours}</div>
          </div>
          <div className="stat">
            <div className="k">Изменено тем</div>
            <div className="v">
              {changed.length} / {items.length}
            </div>
          </div>
          <div className="stat">
            <div className="k">Перенесено</div>
            <div className="v">{hoursLabel(moved)}</div>
          </div>
          <div className="stat">
            <div className="k">{isPeriod ? 'Отличий от rules_v1' : 'Ручные правки'}</div>
            <div className="v">{manual.length}</div>
          </div>
        </div>

        <h2>Таблица часов</h2>
        <div className="table-wrap">
          <table className="table table-compact">
            <thead>
              <tr>
                <th>Тема</th>
                <th className="r">Средний</th>
                <th className="r">n</th>
                <th className="r">Текущие</th>
                <th className="c">Границы</th>
                <th className="c">Важн.</th>
                <th className="c">Блок</th>
                <th className="r">Рекоменд.</th>
                <th className="r">Итог</th>
                <th className="c">Изм.</th>
                <th>Объяснение</th>
                <th className="no-print">Обсуждение</th>
              </tr>
            </thead>
            <tbody>
              {items.map((i) => {
                const d = i.proposed_hours - i.current_hours;
                return (
                  <tr key={i.topic_id}>
                    <td>
                      <div className="cell-topic">
                        <span className="t">{i.topic_name}</span>
                        <span className="s">
                          {i.topic_id}
                          {i.test_version ? ` · ${i.test_version}` : ''}
                        </span>
                      </div>
                    </td>
                    <td className="r num">{fmtPct(i.mean_post_pct)}</td>
                    <td className="r num">{fmtNum(i.n_post)}</td>
                    <td className="r num">{i.current_hours}</td>
                    <td className="c num">
                      {i.min_hours}–{i.max_hours}
                    </td>
                    <td className="c num">{i.importance}</td>
                    <td className="c">{i.is_locked ? <Lock size={13} aria-label="да" /> : '—'}</td>
                    <td className="r num">{i.recommended_hours}</td>
                    <td className="r num strong">
                      {i.proposed_hours}
                      {i.manually_modified && (
                        <div className="tiny" style={{ color: 'var(--warning-text)', fontWeight: 600 }}>
                          вручную
                        </div>
                      )}
                    </td>
                    <td className="c">
                      <span className={`delta ${d > 0 ? 'up' : d < 0 ? 'down' : ''}`}>{fmtSigned(d)}</span>
                    </td>
                    <td className="reason" style={{ maxWidth: 320 }}>
                      {i.recommendation_reason}
                    </td>
                    <td className="no-print">
                      <button
                        type="button"
                        className={`comment-chip ${countFor(i.topic_id) ? 'has' : ''}`}
                        onClick={() => setOpenTopic(i.topic_id)}
                        aria-label={`Обсуждение темы ${i.topic_name}`}
                      >
                        <MessageSquare size={13} /> {countFor(i.topic_id) || 'Обсудить'}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr>
                <td className="strong">Итого</td>
                <td colSpan={2} />
                <td className="r num strong">{items.reduce((s, i) => s + i.current_hours, 0)}</td>
                <td colSpan={3} />
                <td className="r num">{items.reduce((s, i) => s + i.recommended_hours, 0)}</td>
                <td className="r num strong">{items.reduce((s, i) => s + i.proposed_hours, 0)}</td>
                <td colSpan={2} />
                <td className="no-print" />
              </tr>
            </tfoot>
          </table>
        </div>

        <div className="grid-2" style={{ marginTop: 8, alignItems: 'start' }}>
          <div>
            <h2>Переносы по рекомендации</h2>
            {plan.recommendation_transfers.length === 0 ? (
              <p className="text-2">Переносов нет: свободных часов в рамках ограничений не было.</p>
            ) : (
              <div className="transfers">
                {plan.recommendation_transfers.map((t, idx) => (
                  <div className="transfer" key={idx}>
                    <span className="from">{name(t.from_topic_id)}</span>
                    <ArrowRight size={14} className="muted" />
                    <span className="to">{name(t.to_topic_id)}</span>
                    <span className="h">{hoursLabel(t.hours)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div>
            <h2>Комментарий методиста</h2>
            {comment ? <p style={{ whiteSpace: 'pre-wrap' }}>{comment}</p> : <p className="muted">Без комментария.</p>}
            {manual.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <Banner tone={isPeriod ? 'info' : 'warning'} title={isPeriod ? 'План на период против правила rules_v1' : 'Ручные изменения'}>
                  {manual.map((i) => `${i.topic_name}: ${i.recommended_hours} → ${i.proposed_hours} ч`).join('; ')}
                </Banner>
              </div>
            )}
          </div>
        </div>

        <div style={{ marginTop: 20 }}>
          <WarningsList warnings={plan.warnings} tone="neutral" />
        </div>

        <p className="tiny muted" style={{ marginTop: 18 }}>
          <FileText size={12} style={{ verticalAlign: '-2px' }} /> Отчёт построен из неизменяемого снимка плана (GET /api/plans/{shortId(plan.plan_id)}), а не из текущих
          фильтров интерфейса. Рекомендации объяснимы и не прогнозируют рост баллов; решение принимает методист. Даты указаны в UTC+5.
        </p>
      </article>

      <div className="grid-2 no-print" style={{ alignItems: 'start' }}>
        <section className="card card-pad">
          <CommentsPanel
            datasetId={plan.dataset_id}
            target={{ type: 'plan', id: plan.plan_id }}
            title="Обсуждение плана"
            placeholder="Согласны с распределением часов? Что изменить и почему?"
          />
        </section>
        <AiExplain
          datasetId={plan.dataset_id}
          kind="plan"
          title="ИИ: объясни план учителям"
          hint="Короткое объяснение сохранённого плана для рассылки учителям."
          context={() => ({
            is_demo: plan.is_demo,
            class_id: plan.class_id,
            mode: isPeriod ? 'план на весь период' : 'перераспределение с лимитом',
            total_hours: plan.total_hours,
            settings: plan.settings,
            topics: items.map((i) => ({
              topic: i.topic_name,
              mean_post_pct: i.mean_post_pct,
              n_post: i.n_post,
              current_hours: i.current_hours,
              planned_hours: i.proposed_hours,
              recommended_hours: i.recommended_hours,
              manually_modified: i.manually_modified,
            })),
            transfers: plan.recommendation_transfers.map((t) => ({ from: name(t.from_topic_id), to: name(t.to_topic_id), hours: t.hours })),
            comment,
          })}
          saveTo={{ type: 'plan', id: plan.plan_id }}
        />
      </div>

      <Drawer open={openTopic != null} onClose={() => setOpenTopic(null)} labelledBy="plan-topic-title">
        <div className="drawer-head">
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="small muted">Тема плана · класс {plan.class_id}</div>
            <h2 id="plan-topic-title">{openTopic ? name(openTopic) : ''}</h2>
            {openItem && (
              <div className="small muted" style={{ marginTop: 6 }}>
                {openItem.current_hours} → {openItem.proposed_hours} ч · средний {fmtPct(openItem.mean_post_pct)}
              </div>
            )}
          </div>
          <CloseButton onClick={() => setOpenTopic(null)} />
        </div>
        <div className="drawer-body">
          {openTopic && (
            <CommentsPanel
              datasetId={plan.dataset_id}
              target={{ type: 'plan_topic', id: `${plan.plan_id}:${openTopic}` }}
              title="Комментарии к теме"
              placeholder="Хватит ли часов на эту тему? Что предлагаете?"
            />
          )}
        </div>
      </Drawer>
    </div>
  );
}

function Meta({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div>
      <div className="k">{k}</div>
      <div className="v">{v}</div>
    </div>
  );
}
