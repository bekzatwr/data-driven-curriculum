import { useId, type ReactNode } from 'react';

/**
 * Кольцо-индикатор для KPI: доля max, с анимацией «прорисовки» и меткой порога.
 * Декоративно (aria-hidden): само число всегда показано текстом рядом.
 */
export function Ring({
  value,
  max = 100,
  size = 54,
  stroke = 5,
  tone = 'accent',
  marker,
  children,
}: {
  value: number;
  max?: number;
  size?: number;
  stroke?: number;
  tone?: 'accent' | 'critical' | 'good';
  marker?: number;
  children?: ReactNode;
}) {
  const id = useId().replace(/:/g, '');
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const p = Math.max(0, Math.min(1, max > 0 ? value / max : 0));
  const stops =
    tone === 'critical'
      ? ['#ff8a7a', '#e5484d']
      : tone === 'good'
        ? ['#5fe0a5', '#1f9d63']
        : ['#22d3ee', '#8b7cff'];
  const m = marker === undefined ? null : Math.max(0, Math.min(1, marker / max));
  return (
    <span className="ring" style={{ width: size, height: size }} aria-hidden>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <defs>
          <linearGradient id={`rg-${id}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor={stops[0]} />
            <stop offset="1" stopColor={stops[1]} />
          </linearGradient>
        </defs>
        <circle className="ring-track" cx={size / 2} cy={size / 2} r={r} strokeWidth={stroke} fill="none" />
        <circle
          className="ring-bar"
          cx={size / 2}
          cy={size / 2}
          r={r}
          strokeWidth={stroke}
          fill="none"
          stroke={`url(#rg-${id})`}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - p)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ ['--c' as string]: c, filter: `drop-shadow(0 0 4px ${stops[1]}88)` }}
        />
        {m !== null && (
          <line
            className="ring-marker"
            x1={size / 2}
            y1={stroke / 2 - 2}
            x2={size / 2}
            y2={stroke * 1.5 + 2}
            transform={`rotate(${m * 360} ${size / 2} ${size / 2})`}
          />
        )}
      </svg>
      {children && <span className="ring-center">{children}</span>}
    </span>
  );
}
