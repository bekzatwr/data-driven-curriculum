import { useMemo, useState } from 'react';
import type { ClassMetrics, TopicMetrics } from '../api/types';
import { fmtNum, fmtOne, fmtPct, fmtPp, fmtShare, isNum } from '../lib/format';
import { TOPIC_STATUS } from '../lib/status';

/** Дивергентная шкала: ниже порога — красный, выше — синий, у порога — нейтральный серый. */
export function divergingStyle(value: number | null | undefined, center: number, span = 25): React.CSSProperties {
  if (!isNum(value)) return {};
  const t = Math.max(-1, Math.min(1, (value - center) / span));
  const p = Math.round(Math.abs(t) * 100);
  const pole = t < 0 ? 'var(--div-neg)' : 'var(--div-pos)';
  return {
    background: `color-mix(in oklab, rgb(${pole}) ${p}%, rgb(var(--div-mid)))`,
    color: p > 52 ? '#fff' : 'var(--text)',
  };
}

interface Tip {
  x: number;
  y: number;
  topic: TopicMetrics;
  classId: string;
}

export function Heatmap({
  topics,
  cells,
  threshold,
  onSelectTopic,
}: {
  topics: TopicMetrics[];
  cells: ClassMetrics[];
  threshold: number;
  onSelectTopic: (topicId: string) => void;
}) {
  const [tip, setTip] = useState<Tip | null>(null);

  const { classes, lookup } = useMemo(() => {
    const cls = Array.from(new Set(cells.map((c) => c.class_id))).sort((a, b) => a.localeCompare(b, 'ru', { numeric: true }));
    const map = new Map<string, TopicMetrics>();
    cells.forEach((c) => map.set(`${c.metrics.topic_id}|${c.class_id}`, c.metrics));
    return { classes: cls, lookup: map };
  }, [cells]);

  const rows = useMemo(() => [...topics].sort((a, b) => a.topic_order - b.topic_order), [topics]);

  return (
    <div className="heatmap-wrap">
      <div
        className="heatmap"
        style={{ gridTemplateColumns: `minmax(150px, 1.3fr) repeat(${classes.length}, minmax(76px, 1fr)) minmax(84px, 0.9fr)` }}
        role="table"
        aria-label="Средний итоговый результат: тема × класс"
        onMouseLeave={() => setTip(null)}
      >
        <div role="columnheader" />
        {classes.map((c) => (
          <div className="hm-colhead" key={c} role="columnheader">
            {c}
          </div>
        ))}
        <div className="hm-colhead" role="columnheader">
          Все
          <small>выбранные</small>
        </div>

        {rows.map((t, ri) => (
          <HeatRow
            key={t.topic_id}
            topic={t}
            rowIndex={ri}
            classes={classes}
            lookup={lookup}
            threshold={threshold}
            onSelect={() => onSelectTopic(t.topic_id)}
            onHover={setTip}
          />
        ))}
      </div>

      {tip && <HeatTooltip tip={tip} threshold={threshold} />}
    </div>
  );
}

function HeatRow({
  topic,
  rowIndex,
  classes,
  lookup,
  threshold,
  onSelect,
  onHover,
}: {
  topic: TopicMetrics;
  rowIndex: number;
  classes: string[];
  lookup: Map<string, TopicMetrics>;
  threshold: number;
  onSelect: () => void;
  onHover: (t: Tip | null) => void;
}) {
  const cell = (m: TopicMetrics | undefined, classId: string, ci: number) => {
    const empty = !m || !isNum(m.mean_post_pct);
    const few = m?.status === 'insufficient_data';
    const label = `${topic.topic_name}, ${classId}: ${m ? fmtPct(m.mean_post_pct) : 'Нет данных'}${m ? `, ${TOPIC_STATUS[m.status]?.label}` : ''}`;
    return (
      <button
        type="button"
        role="cell"
        key={classId}
        className={`hm-cell ${empty ? 'empty' : ''}`}
        style={{ ...(empty ? {} : divergingStyle(m!.mean_post_pct, threshold)), animationDelay: `${rowIndex * 40 + ci * 25}ms` }}
        aria-label={label}
        onClick={onSelect}
        onMouseMove={(e) => m && onHover({ x: e.clientX, y: e.clientY, topic: m, classId })}
        onFocus={(e) => {
          if (!m) return;
          const r = e.currentTarget.getBoundingClientRect();
          onHover({ x: r.right, y: r.top + r.height / 2, topic: m, classId });
        }}
        onBlur={() => onHover(null)}
      >
        {empty ? (
          <span className="n">Нет данных</span>
        ) : (
          <>
            <span className="v">{fmtOne(m!.mean_post_pct)}</span>
            <span className="n">
              n={fmtNum(m!.n_post)}
              {few ? ' · мало' : ''}
            </span>
            {m!.problem_topic && (
              <span className="flag" aria-hidden title="Проблемная тема">
                ▲
              </span>
            )}
          </>
        )}
      </button>
    );
  };

  return (
    <>
      <button type="button" className="hm-rowhead" role="rowheader" onClick={onSelect} title="Открыть детали темы">
        <span className="t">{topic.topic_name}</span>
        <span className="s">{topic.status_label || TOPIC_STATUS[topic.status]?.label}</span>
      </button>
      {classes.map((c, ci) => cell(lookup.get(`${topic.topic_id}|${c}`), c, ci))}
      {cell(topic, 'Все выбранные', classes.length)}
    </>
  );
}

function HeatTooltip({ tip, threshold }: { tip: Tip; threshold: number }) {
  const m = tip.topic;
  const left = Math.min(tip.x + 16, window.innerWidth - 300);
  const top = Math.min(tip.y + 16, window.innerHeight - 220);
  return (
    <div className="viz-tooltip" style={{ left, top }} role="tooltip">
      <div className="tt-title">
        {m.topic_name} · {tip.classId}
      </div>
      <div className="tt-row">
        Средний итоговый <b>{fmtPct(m.mean_post_pct)}</b>
      </div>
      <div className="tt-row">
        Ниже {fmtOne(threshold)}% <b>{fmtShare(m.below_threshold_share)}</b>
      </div>
      <div className="tt-row">
        Итоговых результатов <b>{fmtNum(m.n_post)}</b>
      </div>
      <div className="tt-row">
        Пар до/после <b>{fmtNum(m.n_pairs)}</b>
      </div>
      <div className="tt-row">
        Прирост (парная) <b>{fmtPp(m.mean_gain_pp)}</b>
      </div>
      <div className="tt-row">
        Статус <b>{m.status_label || TOPIC_STATUS[m.status]?.label}</b>
      </div>
      {m.test_version && (
        <div className="tt-row">
          Версия теста <b>{m.test_version}</b>
        </div>
      )}
    </div>
  );
}

export function HeatLegend({ threshold }: { threshold: number }) {
  return (
    <div className="hm-legend">
      <span>ниже порога</span>
      <span className="hm-legend-bar" aria-hidden />
      <span>выше порога</span>
      <span className="muted">· центр шкалы — порог {fmtOne(threshold)}%</span>
      <span className="muted">· ▲ проблемная тема</span>
    </div>
  );
}
