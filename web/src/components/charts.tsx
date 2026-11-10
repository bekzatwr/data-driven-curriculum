import { fmtOne, fmtPp, isNum } from '../lib/format';

/** Прямоугольник со скруглённым «концом данных» и плоским основанием на оси. */
function barPath(x: number, y0: number, w: number, y1: number, r = 4) {
  const up = y1 < y0;
  const h = Math.abs(y1 - y0);
  const rr = Math.min(r, h, w / 2);
  if (h < 0.5) return '';
  if (up) {
    return `M${x},${y0} V${y1 + rr} Q${x},${y1} ${x + rr},${y1} H${x + w - rr} Q${x + w},${y1} ${x + w},${y1 + rr} V${y0} Z`;
  }
  return `M${x},${y0} V${y1 - rr} Q${x},${y1} ${x + rr},${y1} H${x + w - rr} Q${x + w},${y1} ${x + w},${y1 - rr} V${y0} Z`;
}

export interface SeriesDef {
  key: string;
  label: string;
  color: string;
}

/** Сгруппированные столбцы 0–100%: категории (до/после) × серии (учебник A/B). */
export function GroupedBars({
  categories,
  series,
  values,
  height = 250,
  ariaLabel,
}: {
  categories: string[];
  series: SeriesDef[];
  values: (number | null)[][]; // [category][series]
  height?: number;
  ariaLabel: string;
}) {
  const W = 520;
  const H = height;
  const m = { t: 24, r: 8, b: 34, l: 40 };
  const iw = W - m.l - m.r;
  const ih = H - m.t - m.b;
  const y = (v: number) => m.t + ih - (Math.max(0, Math.min(100, v)) / 100) * ih;
  const groupW = iw / categories.length;
  const barW = Math.min(64, (groupW * 0.62) / series.length);
  const gap = 4;
  const ticks = [0, 25, 50, 75, 100];

  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={ariaLabel}>
        {ticks.map((t) => (
          <g key={t}>
            <line className={t === 0 ? 'zero-line' : 'grid-line'} x1={m.l} x2={W - m.r} y1={y(t)} y2={y(t)} />
            <text className="axis-text" x={m.l - 8} y={y(t) + 4} textAnchor="end">
              {t}%
            </text>
          </g>
        ))}
        {categories.map((cat, ci) => {
          const gx = m.l + ci * groupW + groupW / 2;
          const total = series.length * barW + (series.length - 1) * gap;
          return (
            <g key={cat}>
              {series.map((s, si) => {
                const v = values[ci]?.[si];
                const x = gx - total / 2 + si * (barW + gap);
                if (!isNum(v)) {
                  return (
                    <text key={s.key} className="axis-text" x={x + barW / 2} y={y(0) - 8} textAnchor="middle">
                      н/д
                    </text>
                  );
                }
                return (
                  <g key={s.key}>
                    <path
                      className="bar-rect"
                      d={barPath(x, y(0), barW, y(v))}
                      fill={s.color}
                      style={{ animationDelay: `${ci * 120 + si * 60}ms` }}
                    >
                      <title>{`${s.label} · ${cat}: ${fmtOne(v)}%`}</title>
                    </path>
                    <text className="value-text" x={x + barW / 2} y={y(v) - 7} textAnchor="middle">
                      {fmtOne(v)}%
                    </text>
                  </g>
                );
              })}
              <text className="cat-text" x={gx} y={H - 10} textAnchor="middle">
                {cat}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/** Горизонтальные столбцы прироста в п.п. от нуля (прирост может быть отрицательным). */
export function GainBars({ rows, ariaLabel }: { rows: { label: string; value: number | null; color: string }[]; ariaLabel: string }) {
  const W = 520;
  const rowH = 40;
  const m = { t: 8, r: 70, b: 24, l: 110 };
  const H = m.t + rows.length * rowH + m.b;
  const vals = rows.map((r) => r.value).filter(isNum);
  const lo = Math.min(0, ...vals);
  const hi = Math.max(0, ...vals, 1);
  const pad = (hi - lo) * 0.08;
  const d0 = lo < 0 ? lo - pad : 0;
  const d1 = hi + pad;
  const iw = W - m.l - m.r;
  const x = (v: number) => m.l + ((v - d0) / (d1 - d0)) * iw;
  const bh = 22;

  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={ariaLabel}>
        <line className="zero-line" x1={x(0)} x2={x(0)} y1={m.t - 2} y2={H - m.b + 4} />
        <text className="axis-text" x={x(0)} y={H - 6} textAnchor="middle">
          0 п.п.
        </text>
        {rows.map((r, i) => {
          const cy = m.t + i * rowH + rowH / 2;
          if (!isNum(r.value)) {
            return (
              <g key={r.label}>
                <text className="cat-text" x={m.l - 10} y={cy + 4} textAnchor="end">
                  {r.label}
                </text>
                <text className="axis-text" x={x(0) + 8} y={cy + 4}>
                  Нет данных
                </text>
              </g>
            );
          }
          const x0 = x(0);
          const x1 = x(r.value);
          const left = Math.min(x0, x1);
          const w = Math.abs(x1 - x0);
          const rr = Math.min(4, w / 2, bh / 2);
          const pos = r.value >= 0;
          const path =
            w < 0.5
              ? ''
              : pos
                ? `M${left},${cy - bh / 2} H${left + w - rr} Q${left + w},${cy - bh / 2} ${left + w},${cy - bh / 2 + rr} V${cy + bh / 2 - rr} Q${left + w},${cy + bh / 2} ${left + w - rr},${cy + bh / 2} H${left} Z`
                : `M${left + w},${cy - bh / 2} H${left + rr} Q${left},${cy - bh / 2} ${left},${cy - bh / 2 + rr} V${cy + bh / 2 - rr} Q${left},${cy + bh / 2} ${left + rr},${cy + bh / 2} H${left + w} Z`;
          return (
            <g key={r.label}>
              <text className="cat-text" x={m.l - 10} y={cy + 4} textAnchor="end">
                {r.label}
              </text>
              <path d={path} fill={r.color} className="bar-rect" style={{ transformOrigin: pos ? 'left' : 'right', animationName: 'growX', animationDelay: `${i * 80}ms` }}>
                <title>{`${r.label}: ${fmtPp(r.value)}`}</title>
              </path>
              <text className="value-text" x={pos ? x1 + 8 : x1 - 8} y={cy + 4} textAnchor={pos ? 'start' : 'end'}>
                {fmtPp(r.value)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="legend">
      {items.map((it) => (
        <span className="legend-item" key={it.label}>
          <span className="legend-swatch" style={{ background: it.color }} />
          {it.label}
        </span>
      ))}
    </div>
  );
}
