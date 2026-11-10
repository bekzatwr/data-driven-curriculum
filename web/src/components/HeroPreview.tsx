import { divergingStyle } from './Heatmap';

/** «Рисунок» на главной: пример теплокарты и плана часов (иллюстрация, не реальные данные). */
const ROWS: { t: string; v: number[] }[] = [
  { t: 'Дроби', v: [44, 52, 47, 49] },
  { t: 'Уравнения', v: [68, 63, 58, 61] },
  { t: 'Пропорции', v: [64, 59, 66, 62] },
  { t: 'Геометрия', v: [74, 71, 77, 73] },
  { t: 'Статистика', v: [86, 90, 84, 88] },
];

const PLAN: { t: string; from: number; to: number }[] = [
  { t: 'Дроби', from: 6, to: 8 },
  { t: 'Уравнения', from: 5, to: 5 },
  { t: 'Статистика', from: 4, to: 3 },
  { t: 'Повторение', from: 2, to: 1 },
];
const MAX_H = 9;

export function HeroPreview() {
  return (
    <figure className="figure" aria-hidden style={{ margin: 0 }}>
      <div className="figure-cap">
        <b>Рис. 1</b>
        <span>Средний итоговый балл по темам и классам, %</span>
      </div>
      <div className="fig-heat">
        <span />
        {['7A', '7B', '7C', '7D'].map((c) => (
          <span className="fig-col" key={c}>
            {c}
          </span>
        ))}
        {ROWS.map((r, ri) => (
          <Row key={r.t} row={r} ri={ri} />
        ))}
      </div>
      <div className="fig-legend">
        ниже порога <i /> выше · порог 60%
      </div>

      <div className="fig-plan">
        <div className="fig-plan-title">План часов · 7A · сумма 24 ч не меняется</div>
        {PLAN.map((p, i) => (
          <div className="fig-plan-row" key={p.t}>
            <span>{p.t}</span>
            <span className="fig-track">
              <span className="fig-fill" style={{ width: `${(p.to / MAX_H) * 100}%`, animationDelay: `${600 + i * 90}ms` }} />
              <span className="fig-was" style={{ left: `${(p.from / MAX_H) * 100}%` }} />
            </span>
            <span className={`fig-delta ${p.to > p.from ? 'up' : p.to < p.from ? 'down' : ''}`}>
              {p.to > p.from ? `+${p.to - p.from}` : p.to < p.from ? `−${p.from - p.to}` : '0'}
            </span>
          </div>
        ))}
      </div>
      <div className="fig-note">Пример экрана на искусственных данных. Черта — часы до перераспределения.</div>
    </figure>
  );
}

function Row({ row, ri }: { row: { t: string; v: number[] }; ri: number }) {
  return (
    <>
      <span className="fig-row">{row.t}</span>
      {row.v.map((v, ci) => (
        <span className="fig-cell" key={ci} style={{ ...divergingStyle(v, 60), animationDelay: `${150 + ri * 60 + ci * 35}ms` }}>
          {v}
        </span>
      ))}
    </>
  );
}
