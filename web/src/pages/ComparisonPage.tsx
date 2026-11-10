import { useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeftRight, BarChart3, BookOpen, ClipboardList, GitCompareArrows, MessagesSquare } from 'lucide-react';
import { api } from '../api/client';
import type { BookGroup, Comparison } from '../api/types';
import { GroupedBars, Legend } from '../components/charts';
import { FilterBar } from '../components/FilterBar';
import {
  Banner,
  Button,
  DemoBadge,
  EmptyState,
  ErrorState,
  InfoPopover,
  LoadingBlock,
  Refreshing,
  WarningsList,
} from '../components/ui';
import { fmtNum, fmtOne, fmtPct, fmtPp, isNum } from '../lib/format';
import { COMPARISON_STATUS } from '../lib/status';
import { useAsync } from '../lib/useAsync';
import { useDataset } from '../state/dataset';
import { AiExplain } from '../components/AiExplain';
import { CommentsPanel } from '../components/Comments';
import { useState } from 'react';

export function ComparisonPage() {
  const { datasetId, dataset, filters, shared, comparison, setComparison, topicName } = useDataset();
  const navigate = useNavigate();
  const topics = useMemo(() => [...filters.topics].sort((a, b) => a.topic_order - b.topic_order), [filters.topics]);
  const books = filters.textbooks;

  const topicId = comparison.topicId && topics.some((t) => t.topic_id === comparison.topicId) ? comparison.topicId : topics[0]?.topic_id ?? null;
  const bookA = comparison.textbookA && books.some((b) => b.id === comparison.textbookA) ? comparison.textbookA : books[0]?.id ?? null;
  const bookB =
    comparison.textbookB && books.some((b) => b.id === comparison.textbookB) ? comparison.textbookB : books.find((b) => b.id !== bookA)?.id ?? null;

  useEffect(() => {
    if (topicId !== comparison.topicId || bookA !== comparison.textbookA || bookB !== comparison.textbookB) {
      setComparison({ topicId, textbookA: bookA, textbookB: bookB });
    }
  }, [topicId, bookA, bookB, comparison, setComparison]);

  const same = !!bookA && bookA === bookB;
  const ready = !!topicId && !!bookA && !!bookB && !same;
  const params = {
    topic_id: topicId || '',
    textbook_a: bookA || '',
    textbook_b: bookB || '',
    class_ids: shared.classIds,
    test_version: shared.testVersion,
  };
  const state = useAsync(ready ? (s) => api.comparison(datasetId, params, s) : null, `${datasetId}|${JSON.stringify(params)}|${ready}`);
  const data = ready ? state.data : undefined;
  const label = (id: string | null) => books.find((b) => b.id === id)?.label || id || '—';

  return (
    <div className="stack" style={{ gap: 0 }}>
      <div className="page-head fade-up">
        <div style={{ flex: 1, minWidth: 280 }}>
          <div className="eyebrow">Шаг 3 · Сравнение учебников</div>
          <h1>Как различаются наблюдаемые результаты</h1>
          <p>
            До и после — одни и те же ученики. Сравнение описательное и не доказывает влияния учебника.{' '}
            {dataset.source_type === 'demo' && <DemoBadge />}
          </p>
        </div>
        <div className="row-wrap no-print">
          <Button icon={<BarChart3 size={16} />} onClick={() => navigate(`/datasets/${encodeURIComponent(datasetId)}/overview`)}>
            К обзору
          </Button>
          <Button variant="primary" icon={<ClipboardList size={16} />} onClick={() => navigate(`/datasets/${encodeURIComponent(datasetId)}/plan`)}>
            Спланировать часы
          </Button>
        </div>
      </div>

      <FilterBar showTextbooks={false} />

      {books.length < 2 ? (
        <div className="card">
          <EmptyState title="Для сравнения нужно минимум два учебника" icon={<BookOpen size={26} />}>
            В этом наборе {books.length === 1 ? `один учебник: ${books[0].label}` : 'нет учебников'}.
          </EmptyState>
        </div>
      ) : (
        <div className="stack">
          <section className="card card-pad fade-up">
            <div className="grid-4" style={{ gridTemplateColumns: 'minmax(0, 1.3fr) minmax(0, 1fr) auto minmax(0, 1fr)', alignItems: 'end' }}>
              <div className="field">
                <label className="label" htmlFor="c-topic">
                  Тема
                </label>
                <select
                  id="c-topic"
                  className="select"
                  value={topicId || ''}
                  onChange={(e) => setComparison({ topicId: e.target.value, textbookA: bookA, textbookB: bookB })}
                >
                  {topics.map((t) => (
                    <option key={t.topic_id} value={t.topic_id}>
                      {t.topic_name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label className="label row" htmlFor="c-a" style={{ gap: 6 }}>
                  <span className="legend-swatch" style={{ background: 'var(--series-a)' }} /> Учебник A
                </label>
                <select
                  id="c-a"
                  className="select"
                  value={bookA || ''}
                  onChange={(e) => setComparison({ topicId, textbookA: e.target.value, textbookB: bookB })}
                >
                  {books.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.label}
                    </option>
                  ))}
                </select>
              </div>
              <Button
                variant="ghost"
                iconOnly
                aria-label="Поменять учебники местами"
                title="Поменять A и B местами"
                onClick={() => setComparison({ topicId, textbookA: bookB, textbookB: bookA })}
              >
                <ArrowLeftRight size={18} />
              </Button>
              <div className="field">
                <label className="label row" htmlFor="c-b" style={{ gap: 6 }}>
                  <span className="legend-swatch" style={{ background: 'var(--series-b)' }} /> Учебник B
                </label>
                <select
                  id="c-b"
                  className="select"
                  value={bookB || ''}
                  onChange={(e) => setComparison({ topicId, textbookA: bookA, textbookB: e.target.value })}
                >
                  {books.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </section>

          {same && (
            <Banner tone="warning" title="Выберите два разных учебника">
              Учебник A совпадает с учебником B — сравнивать нечего.
            </Banner>
          )}

          {ready && state.error != null && !data && (
            <div className="card">
              <ErrorState error={state.error} onRetry={state.reload} />
            </div>
          )}
          {ready && state.error != null && data && (
            <Banner tone="critical" title="Не удалось обновить сравнение" action={<Button size="sm" onClick={state.reload}>Повторить</Button>}>
              Ниже показан предыдущий результат.
            </Banner>
          )}
          {ready && state.loading && (
            <div className="card">
              <LoadingBlock rows={6} label="Сравниваем группы…" />
            </div>
          )}
          {data && (
            <Refreshing active={state.refreshing} label="Пересчитываем сравнение…">
              <ComparisonBody data={data} topicTitle={topicName(data.topic_id)} labelA={label(data.group_a.textbook_id)} labelB={label(data.group_b.textbook_id)} />
            </Refreshing>
          )}
        </div>
      )}
    </div>
  );
}

function ComparisonBody({ data, topicTitle, labelA, labelB }: { data: Comparison; topicTitle: string; labelA: string; labelB: string }) {
  const { datasetId } = useDataset();
  const [book, setBook] = useState<'a' | 'b'>('a');
  const st = COMPARISON_STATUS[data.comparison_status];
  const a = data.group_a;
  const b = data.group_b;
  const noPre = !isNum(a.mean_pre_paired_pct) && !isNum(b.mean_pre_paired_pct);
  const bannerTone = st.tone === 'good' ? 'good' : st.tone === 'serious' ? 'serious' : 'neutral';

  return (
    <div className="stack">
      <Banner
        tone={bannerTone}
        title={
          <span className="row-wrap" style={{ gap: 8 }}>
            Статус: {st.label}
            <span className="small muted" style={{ fontWeight: 500 }}>
              {topicTitle}
              {data.test_version ? ` · версия ${data.test_version}` : ''}
              {isNum(data.max_score) ? ` · шкала ${data.max_score}` : ''}
            </span>
          </span>
        }
      >
        {data.reasons.length > 0 ? (
          <ul>
            {data.reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        ) : (
          st.hint
        )}
      </Banner>

      {noPre && (
        <Banner tone="info" title="Нет входного теста">
          Показаны только итоговые результаты. Прирост и сопоставимое сравнение недоступны.
        </Banner>
      )}

      <div className="verdict fade-up">
        <div>
          <div className="small muted strong">Разница приростов (A − B)</div>
          <div className="verdict-num" style={{ marginTop: 6 }}>
            {data.comparison_status === 'comparable' && isNum(data.difference_gain_pp) ? fmtPp(data.difference_gain_pp) : '—'}
          </div>
          {data.comparison_status !== 'comparable' && <div className="tiny muted">скрыто: сравнение {st.label.toLowerCase()}</div>}
        </div>
        <div style={{ width: 1, alignSelf: 'stretch', background: 'var(--border)' }} />
        <div>
          <div className="small muted strong">Стартовый разрыв</div>
          <div className="verdict-num" style={{ marginTop: 6, fontSize: 26 }}>
            {fmtPp(data.baseline_gap_pp, { sign: false, fallback: '—' })}
          </div>
          <div className="tiny muted">допустимо ≤ {fmtOne(data.settings.max_baseline_gap_pp)} п.п.</div>
        </div>
        <div style={{ flex: 1, minWidth: 240 }}>
          <div className="strong" style={{ fontSize: 15 }}>
            {data.conclusion}
          </div>
          <div className="row-wrap" style={{ marginTop: 8 }}>
            <InfoPopover align="right">
              <ul>
                <li>Прирост = средний после − средний до, на одних и тех же учениках (парная выборка).</li>
                <li>Разница = прирост A − прирост B, в процентных пунктах.</li>
                <li>Нужно ≥ {data.settings.min_students} пар в каждой группе, одна версия/шкала теста и стартовый разрыв ≤ {fmtOne(data.settings.max_baseline_gap_pp)} п.п.</li>
                <li>Иначе разница не показывается — это корректный результат, а не ошибка.</li>
                <li>Сравнение описательное, не причинное: «лучший учебник» не определяется.</li>
              </ul>
            </InfoPopover>
          </div>
        </div>
      </div>

      <div className="vs-grid">
        <BookCard group={a} letter="A" label={labelA} color="var(--series-a)" />
        <div className="vs-badge">vs</div>
        <BookCard group={b} letter="B" label={labelB} color="var(--series-b)" />
      </div>

      <section className="card fade-up-2">
        <div className="card-head">
          <h3>
            <BarChart3 size={16} /> Средний балл до и после
          </h3>
          <span className="spacer" />
          <Legend
            items={[
              { label: `A · ${labelA}`, color: 'var(--series-a)' },
              { label: `B · ${labelB}`, color: 'var(--series-b)' },
            ]}
          />
        </div>
        <div className="card-body cmp-chart">
          <GroupedBars
            ariaLabel={`Средний балл до и после: ${labelA} и ${labelB}`}
            categories={['До', 'После']}
            series={[
              { key: 'a', label: labelA, color: 'var(--series-a)' },
              { key: 'b', label: labelB, color: 'var(--series-b)' },
            ]}
            values={[
              [a.mean_pre_paired_pct, b.mean_pre_paired_pct],
              [a.mean_post_paired_pct, b.mean_post_paired_pct],
            ]}
          />
        </div>
      </section>

      <WarningsList warnings={data.warnings} tone="info" />

      <AiExplain
        datasetId={datasetId}
        kind="comparison"
        title="ИИ: сравнение методик и учебников"
        hint="Что показывают данные, где ограничения и что проверить на уроках. Без вывода «лучший учебник»."
        selectors={() => ({
          topic_id: data.topic_id,
          textbook_a: data.group_a.textbook_id,
          textbook_b: data.group_b.textbook_id,
          class_ids: data.applied_filters.class_ids,
          test_version: data.applied_filters.test_version,
        })}
      />

      <details className="card card-pad fold no-print">
        <summary className="fold-summary">
          <MessagesSquare size={16} /> Отзывы учителей об учебниках
          <span className="tiny muted">— открыть обсуждение</span>
        </summary>
        <div className="row-wrap" style={{ margin: '12px 0' }}>
          <span className="spacer" />
          <div className="segmented" role="tablist" aria-label="Учебник">
            <button role="tab" aria-selected={book === 'a'} className={book === 'a' ? 'on' : ''} onClick={() => setBook('a')}>
              A · {labelA}
            </button>
            <button role="tab" aria-selected={book === 'b'} className={book === 'b' ? 'on' : ''} onClick={() => setBook('b')}>
              B · {labelB}
            </button>
          </div>
        </div>
        <CommentsPanel
          key={book}
          datasetId={datasetId}
          target={{ type: 'textbook', id: book === 'a' ? data.group_a.textbook_id : data.group_b.textbook_id }}
          title={`Обсуждение: ${book === 'a' ? labelA : labelB}`}
          placeholder="Чем удобен или неудобен учебник по этой теме? Задания, объяснения, методика…"
        />
      </details>
    </div>
  );
}

function BookCard({ group, letter, label, color }: { group: BookGroup; letter: string; label: string; color: string }) {
  return (
    <section className="card card-pad book-card fade-up" style={{ ['--book-color' as string]: color }}>
      <div className="book-head">
        <span className="book-letter">{letter}</span>
        <div style={{ minWidth: 0 }}>
          <div className="strong" style={{ fontSize: 16 }}>
            {label}
          </div>
          <div className="tiny muted">
            {fmtNum(group.n_classes)} кл. · {fmtNum(group.n_teachers)} учит.
          </div>
        </div>
        <span className="spacer" />
        <GitCompareArrows size={18} className="muted" />
      </div>
      <div className="book-stats">
        <div className="stat">
          <div className="k">Учеников с парой</div>
          <div className="v">{fmtNum(group.n_pairs)}</div>
        </div>
        <div className="stat">
          <div className="k">До</div>
          <div className="v">{fmtPct(group.mean_pre_paired_pct)}</div>
        </div>
        <div className="stat">
          <div className="k">После</div>
          <div className="v">{fmtPct(group.mean_post_paired_pct)}</div>
        </div>
        <div className="stat wide" style={{ background: 'color-mix(in srgb, var(--accent) 8%, var(--surface))' }}>
          <div className="k">Средний прирост</div>
          <div className="v big">{fmtPp(group.mean_gain_pp)}</div>
          <div className="tiny muted">итог по всем ученикам группы: {fmtPct(group.mean_post_pct)}</div>
        </div>
      </div>
    </section>
  );
}
