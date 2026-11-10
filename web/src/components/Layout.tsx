import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { BarChart3, Database, Moon, Sun } from 'lucide-react';
import { useApp } from '../state/app';

type Theme = 'light' | 'dark';

function initialTheme(): Theme {
  const t = document.documentElement.dataset.theme;
  if (t === 'dark' || t === 'light') return t;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function Layout() {
  const { current, lastPlanId, apiOnline, recheckApi } = useApp();
  const location = useLocation();
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem('ddc.theme', theme);
    } catch {
      /* ignore */
    }
  }, [theme]);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  const path = location.pathname;
  const base = current ? `/datasets/${encodeURIComponent(current.id)}` : null;
  const steps = [
    { key: 'data', label: 'Данные', to: '/', active: path === '/', enabled: true },
    { key: 'overview', label: 'Обзор', to: base ? `${base}/overview` : '#', active: path.endsWith('/overview'), enabled: !!base },
    { key: 'comparison', label: 'Сравнение', to: base ? `${base}/comparison` : '#', active: path.endsWith('/comparison'), enabled: !!base },
    { key: 'plan', label: 'План часов', to: base ? `${base}/plan` : '#', active: path.endsWith('/plan'), enabled: !!base },
    {
      key: 'report',
      label: 'Отчёт',
      to: lastPlanId ? `/plans/${encodeURIComponent(lastPlanId)}` : '/reports',
      active: path.startsWith('/plans') || path.startsWith('/reports'),
      enabled: true,
    },
  ];
  const activeIndex = steps.findIndex((s) => s.active);

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <Link to="/" className="brand" aria-label="Data-Driven Curriculum — на главную">
            <span className="brand-mark">
              <BarChart3 size={18} />
            </span>
            <span className="brand-text">
              Data-Driven Curriculum
              <small>Аналитика для методиста</small>
            </span>
          </Link>

          <nav className="stepper" aria-label="Шаги сценария">
            {steps.map((s, i) => (
              <NavLink
                key={s.key}
                to={s.to}
                className={`step ${s.active ? 'active' : ''} ${activeIndex > i ? 'done' : ''} ${s.enabled ? '' : 'disabled'}`}
                aria-current={s.active ? 'page' : undefined}
                aria-disabled={!s.enabled || undefined}
                tabIndex={s.enabled ? undefined : -1}
                title={s.enabled ? s.label : 'Сначала выберите или загрузите набор данных'}
              >
                <span className="step-num">{i + 1}</span>
                <span className="step-label">{s.label}</span>
              </NavLink>
            ))}
          </nav>

          <div className="header-right">
            {current && (
              <Link to="/" className="dataset-chip" title={`Текущий набор: ${current.name}. Нажмите, чтобы сменить.`}>
                <Database size={15} className="muted" />
                <span className="dataset-chip-text">{current.name}</span>
                {current.isDemo && (
                  <span className="badge badge-demo" style={{ height: 20, padding: '0 6px', fontSize: 11 }}>
                    Демо
                  </span>
                )}
              </Link>
            )}
            <button
              type="button"
              className="btn btn-ghost btn-icon btn-sm"
              onClick={recheckApi}
              title={apiOnline === false ? 'API недоступен — нажмите, чтобы проверить снова' : apiOnline ? 'API подключён' : 'Проверяем API…'}
              aria-label="Состояние API"
            >
              <span className={`dot ${apiOnline === false ? 'off' : apiOnline ? '' : 'wait'}`} />
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-icon btn-sm"
              onClick={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
              aria-label={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
              title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
            >
              {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
            </button>
          </div>
        </div>
      </header>

      <main className="main" id="main">
        <Outlet />
      </main>

      <footer className="footer no-print">
        Data-Driven Curriculum · рекомендации объяснимы и не прогнозируют рост баллов · решение принимает методист · время UTC+5
      </footer>
    </div>
  );
}
