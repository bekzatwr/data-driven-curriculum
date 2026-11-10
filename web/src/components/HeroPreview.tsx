import { useRef } from 'react';
import { CheckCircle2, Sparkles, TrendingUp } from 'lucide-react';
import { divergingStyle } from './Heatmap';

/** Декоративное превью продукта на главной (пример экрана, не реальные данные). */
const ROWS: { t: string; v: number[] }[] = [
  { t: 'Дроби', v: [44, 52, 47, 49] },
  { t: 'Уравнения', v: [68, 63, 58, 61] },
  { t: 'Пропорции', v: [64, 59, 66, 62] },
  { t: 'Геометрия', v: [74, 71, 77, 73] },
  { t: 'Статистика', v: [86, 90, 84, 88] },
];

const PLAN: { t: string; from: number; to: number }[] = [
  { t: 'Дроби', from: 4, to: 6 },
  { t: 'Уравнения', from: 5, to: 5 },
  { t: 'Статистика', from: 5, to: 4 },
  { t: 'Повторение', from: 4, to: 3 },
];

export function HeroPreview() {
  const win = useRef<HTMLDivElement>(null);
  // Окно наклоняется за курсором (только мышь; на сенсорах — статичный наклон из CSS).
  const onMove = (e: React.PointerEvent) => {
    const el = win.current;
    if (!el || e.pointerType !== 'mouse') return;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    el.style.setProperty('--ry', `${(px * 16).toFixed(2)}deg`);
    el.style.setProperty('--rx', `${(-py * 12).toFixed(2)}deg`);
  };
  const onLeave = () => {
    win.current?.style.removeProperty('--ry');
    win.current?.style.removeProperty('--rx');
  };
  return (
    <div className="hero-preview" aria-hidden onPointerMove={onMove} onPointerLeave={onLeave}>
      <div className="hp-window" ref={win}>
        <div className="hp-bar">
          <i />
          <i />
          <i />
          <span>Обзор · Математика, 7 класс</span>
        </div>
        <div className="hp-body">
          <div className="hp-kpis">
            <div>
              <small>Ученики</small>
              <b>120</b>
            </div>
            <div>
              <small>Средний балл</small>
              <b>
                71,8<em>%</em>
              </b>
            </div>
            <div className="crit">
              <small>Проблемные темы</small>
              <b>
                2 <em>из 6</em>
              </b>
            </div>
          </div>

          <div className="hp-heat">
            <span />
            {['7A', '7B', '7C', '7D'].map((c) => (
              <span className="hp-col" key={c}>
                {c}
              </span>
            ))}
            {ROWS.map((r, ri) => (
              <Row key={r.t} row={r} ri={ri} />
            ))}
          </div>

          <div className="hp-plan">
            <div className="hp-plan-title">План часов · 7A · сумма 24 ч сохранена</div>
            {PLAN.map((p, i) => (
              <div className="hp-plan-row" key={p.t}>
                <span>{p.t}</span>
                <span className="hp-track">
                  <span className="hp-fill" style={{ width: `${(p.to / 7) * 100}%`, animationDelay: `${900 + i * 120}ms` }} />
                </span>
                <span className={`hp-delta ${p.to > p.from ? 'up' : p.to < p.from ? 'down' : ''}`}>
                  {p.to > p.from ? `+${p.to - p.from}` : p.to < p.from ? `−${p.from - p.to}` : '0'}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="hp-chip hp-chip-ai">
        <span className="hp-chip-icon">
          <Sparkles size={13} />
        </span>
        <span>
          <b>ИИ:</b> «Дроби» ниже порога на 12 п.п. — нужна практика
        </span>
      </div>
      <div className="hp-chip hp-chip-plan">
        <span className="hp-chip-icon good">
          <TrendingUp size={13} />
        </span>
        <span>
          <b>+2 ч</b> на «Дроби»
        </span>
      </div>
      <div className="hp-chip hp-chip-ok">
        <CheckCircle2 size={13} />
        <span>24 / 24 ч · блокировки соблюдены</span>
      </div>
    </div>
  );
}

function Row({ row, ri }: { row: { t: string; v: number[] }; ri: number }) {
  return (
    <>
      <span className="hp-row">{row.t}</span>
      {row.v.map((v, ci) => (
        <span
          className={`hp-cell ${v < 60 ? 'below' : ''}`}
          key={ci}
          style={{ ...divergingStyle(v, 60), animationDelay: `${300 + ri * 70 + ci * 45}ms` }}
        >
          {v}
        </span>
      ))}
    </>
  );
}
