/** Знак продукта: открытая книга, на правой странице — растущие столбцы данных. */
export function LogoMark({ size = 28 }: { size?: number }) {
  // Цвета из темы: чернильный знак, страницы цвета бумаги, столбцы данных — акцент.
  const ink = { fill: 'var(--logo-bg, #17160f)' };
  const page = { fill: 'var(--logo-fg, #fbf9f4)' };
  const bar = { fill: 'var(--logo-bar, #7f97ff)' };
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" role="img" aria-label="Data-Driven Curriculum" style={{ flex: 'none', display: 'block' }}>
      <rect width="32" height="32" rx="8" style={ink} />
      <path d="M6.5 10.2c2.9-1.5 6-1.5 8.9.1v13.2c-2.9-1.5-6-1.5-8.9 0z" style={page} opacity=".55" />
      <path d="M25.5 10.2c-2.9-1.5-6-1.5-8.9.1v13.2c2.9-1.5 6-1.5 8.9 0z" style={page} />
      <rect x="18.3" y="17.6" width="1.7" height="3.6" rx=".85" style={bar} />
      <rect x="20.8" y="15.2" width="1.7" height="6" rx=".85" style={bar} />
      <rect x="23.3" y="12.6" width="1.7" height="8.6" rx=".85" style={bar} />
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
