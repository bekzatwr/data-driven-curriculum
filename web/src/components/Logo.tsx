import { useId } from 'react';

/** Знак продукта: открытая книга, на правой странице — растущие столбцы данных. */
export function LogoMark({ size = 28 }: { size?: number }) {
  const id = useId().replace(/:/g, '');
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" role="img" aria-label="Data-Driven Curriculum" style={{ flex: 'none', display: 'block' }}>
      <defs>
        <linearGradient id={`lg-${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#8b8aff" />
          <stop offset=".55" stopColor="#6260f2" />
          <stop offset="1" stopColor="#3d3bc6" />
        </linearGradient>
        <linearGradient id={`lb-${id}`} x1="0" y1="1" x2="0" y2="0">
          <stop offset="0" stopColor="#6260f2" />
          <stop offset="1" stopColor="#22b8f0" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill={`url(#lg-${id})`} />
      <rect x=".5" y=".5" width="31" height="31" rx="8.5" fill="none" stroke="#fff" strokeOpacity=".22" />
      <path d="M6.5 10.2c2.9-1.5 6-1.5 8.9.1v13.2c-2.9-1.5-6-1.5-8.9 0z" fill="#fff" opacity=".55" />
      <path d="M25.5 10.2c-2.9-1.5-6-1.5-8.9.1v13.2c2.9-1.5 6-1.5 8.9 0z" fill="#fff" />
      <rect x="18.3" y="17.6" width="1.7" height="3.6" rx=".85" fill={`url(#lb-${id})`} />
      <rect x="20.8" y="15.2" width="1.7" height="6" rx=".85" fill={`url(#lb-${id})`} />
      <rect x="23.3" y="12.6" width="1.7" height="8.6" rx=".85" fill={`url(#lb-${id})`} />
    </svg>
  );
}

export function Brand({ size = 28, tagline = 'Учебный план на данных' }: { size?: number; tagline?: string | null }) {
  return (
    <span className="brand-lockup">
      <LogoMark size={size} />
      <span className="brand-words">
        <span className="brand-name">
          Data-Driven <b>Curriculum</b>
        </span>
        {tagline && <small>{tagline}</small>}
      </span>
    </span>
  );
}
