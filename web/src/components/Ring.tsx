import type { ReactNode } from 'react';

/**
 * Тонкое кольцо-индикатор для KPI: доля от max, с прорисовкой и меткой порога.
 * Декоративно (aria-hidden): само число всегда показано текстом рядом.
 */
export function Ring({
  value,
  max = 100,
  size = 50,
  stroke = 3.5,
  tone = 'ink',
  marker,
  children,
}: {
  value: number;
  max?: number;
  size?: number;
  stroke?: number;
  tone?: 'ink' | 'critical' | 'good';
  marker?: number;
  children?: ReactNode;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const p = Math.max(0, Math.min(1, max > 0 ? value / max : 0));
  const m = marker === undefined ? null : Math.max(0, Math.min(1, marker / max));
  const mid = size / 2;
  return (
    <span className="ring" style={{ width: size, height: size }} aria-hidden>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle className="ring-track" cx={mid} cy={mid} r={r} strokeWidth={stroke} fill="none" />
        <circle
          className={`ring-bar tone-${tone}`}
          cx={mid}
          cy={mid}
          r={r}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - p)}
          transform={`rotate(-90 ${mid} ${mid})`}
          style={{ ['--c' as string]: c }}
        />
        {m !== null && (
          <line
            className="ring-marker"
            x1={mid}
            y1={-1.5}
            x2={mid}
            y2={stroke + 2.5}
            transform={`rotate(${m * 360} ${mid} ${mid})`}
          />
        )}
      </svg>
      {children && <span className="ring-center">{children}</span>}
    </span>
  );
}
