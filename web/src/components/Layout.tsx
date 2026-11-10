import { useCallback, useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { BarChart3, ChevronRight, ClipboardList, FileText, GitCompareArrows, GraduationCap, Menu, Moon, Search, Sun, Upload } from 'lucide-react';
import { useApp } from '../state/app';
import { CommandPalette, isMac } from './CommandPalette';
import { Brand } from './Logo';

type Theme = 'light' | 'dark';

export function Layout() {
  const { current, lastPlanId, apiOnline, recheckApi } = useApp();
  const location = useLocation();
  const [theme, setTheme] = useState<Theme>(() => (document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'));
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#08090a' : '#fbfbfc');
    try {
      localStorage.setItem('ddc.theme2', theme);
    } catch {
      /* ignore */
    }
  }, [theme]);

  const toggleTheme = useCallback(() => setTheme((t) => (t === 'dark' ? 'light' : 'dark')), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0 });
    setNavOpen(false);
  }, [location.pathname]);

  const path = location.pathname;
  const base = current ? `/datasets/${encodeURIComponent(current.id)}` : null;
  const steps = [
    { key: 'data', label: 'Данные', icon: Upload, to: '/', active: path === '/', enabled: true },
    { key: 'overview', label: 'Обзор', icon: BarChart3, to: base ? `${base}/overview` : '#', active: path.endsWith('/overview'), enabled: !!base },
    { key: 'comparison', label: 'Сравнение', icon: GitCompareArrows, to: base ? `${base}/comparison` : '#', active: path.endsWith('/comparison'), enabled: !!base },
    { key: 'plan', label: 'План часов', icon: ClipboardList, to: base ? `${base}/plan` : '#', active: path.endsWith('/plan'), enabled: !!base },
    {
      key: 'report',
      label: 'Отчёт',
      icon: FileText,
      to: lastPlanId ? `/plans/${encodeURIComponent(lastPlanId)}` : '/reports',
      active: path.startsWith('/plans') || path.startsWith('/reports'),
      enabled: true,
    },
  ];
  const activeIndex = steps.findIndex((s) => s.active);
  const teachersActive = path.endsWith('/teachers');
  const pageTitle = teachersActive ? 'Учителя и нагрузка' : steps[activeIndex]?.label ?? 'Страница';
  const inDataset = path.startsWith('/datasets/') || path.startsWith('/plans/');

  return (
    <div className={`shell ${navOpen ? 'nav-open' : ''}`}>
      <aside className="sidebar" aria-label="Навигация">
        <Link to="/" className="sb-brand" aria-label="Data-Driven Curriculum — на главную">
          <Brand size={28} />
        </Link>

        <button type="button" className="sb-search" onClick={() => setPaletteOpen(true)}>
          <Search size={14} />
          Поиск и команды
          <span className="kbds">
            <span className="kbd">{isMac ? '⌘' : 'Ctrl'}</span>
            <span className="kbd">K</span>
          </span>
        </button>

        <div className="sb-label">Сценарий методиста</div>
        <nav aria-label="Шаги сценария" className="stack-sm" style={{ gap: 2 }}>
          {steps.map((s, i) => {
            const Icon = s.icon;
            return (
              <NavLink
                key={s.key}
                to={s.to}
                className={`sb-item ${s.active ? 'active' : ''} ${activeIndex > i && s.enabled ? 'done' : ''} ${s.enabled ? '' : 'disabled'}`}
                aria-current={s.active ? 'page' : undefined}
                aria-disabled={!s.enabled || undefined}
                tabIndex={s.enabled ? undefined : -1}
                title={s.enabled ? undefined : 'Сначала выберите или загрузите набор данных'}
              >
                <Icon size={16} />
                {s.label}
                <span className="sb-step">{i + 1}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="sb-label">Школа</div>
        <NavLink
          to={base ? `${base}/teachers` : '#'}
          className={`sb-item ${teachersActive ? 'active' : ''} ${base ? '' : 'disabled'}`}
          aria-current={teachersActive ? 'page' : undefined}
          tabIndex={base ? undefined : -1}
        >
          <GraduationCap size={16} />
          Учителя и нагрузка
        </NavLink>

        {current && (
          <div className="sb-dataset">
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <span className="tiny faint">Текущий набор</span>
              {current.isDemo && (
                <span className="badge badge-demo" style={{ height: 18, padding: '0 6px', fontSize: 10.5 }}>
                  демо
                </span>
              )}
            </div>
            <div className="name" title={current.name}>
              {current.name}
            </div>
            <Link to="/" className="tiny" style={{ display: 'inline-block', marginTop: 6 }}>
              Сменить набор
            </Link>
          </div>
        )}

        <div className="sb-footer">
          <button
            type="button"
            className="sb-status"
            onClick={recheckApi}
            title={apiOnline === false ? 'API недоступен — нажмите, чтобы проверить снова' : 'Проверить соединение'}
          >
            <span className={`dot ${apiOnline === false ? 'off' : apiOnline ? '' : 'wait'}`} />
            {apiOnline === false ? 'API недоступен' : apiOnline ? 'API подключён' : 'Проверяем…'}
          </button>
          <span className="spacer" />
          <button
            type="button"
            className="btn btn-ghost btn-icon btn-sm"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
            title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
          >
            {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
          </button>
        </div>
      </aside>
      <div className="sidebar-backdrop" onClick={() => setNavOpen(false)} />

      <div className="main-col">
        <header className="topbar">
          <button type="button" className="btn btn-ghost btn-icon btn-sm menu-btn" aria-label="Открыть меню" onClick={() => setNavOpen(true)}>
            <Menu size={17} />
          </button>
          <nav className="crumbs" aria-label="Путь">
            {inDataset && current ? (
              <>
                <Link to={`/datasets/${encodeURIComponent(current.id)}/overview`} className="crumb-ds" title={current.name}>
                  {current.name}
                </Link>
                <ChevronRight size={14} className="sep crumb-ds" />
              </>
            ) : null}
            <span className="cur">{pageTitle}</span>
          </nav>
          <span className="spacer" />
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPaletteOpen(true)} aria-label="Открыть поиск и команды">
            <Search size={14} />
            <span className="top-search-text">Поиск</span>
            <span className="kbd">{isMac ? '⌘K' : 'Ctrl K'}</span>
          </button>
        </header>

        <main className="content" id="main">
          <Outlet />
        </main>

        <footer className="footer no-print">
          Рекомендации объяснимы и не прогнозируют рост баллов · решение принимает методист · время UTC+5
        </footer>
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} onToggleTheme={toggleTheme} />
    </div>
  );
}
