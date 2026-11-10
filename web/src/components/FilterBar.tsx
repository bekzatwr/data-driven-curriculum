import { RotateCcw, SlidersHorizontal } from 'lucide-react';
import { useDataset } from '../state/dataset';
import { Button } from './ui';

export function FilterBar({ showTextbooks = true, extra }: { showTextbooks?: boolean; extra?: React.ReactNode }) {
  const { filters, shared, setShared, resetShared, hasMultipleVersions, allVersions } = useDataset();
  const active = shared.classIds.length + (showTextbooks ? shared.textbookIds.length : 0) + (shared.testVersion ? 1 : 0);

  const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  return (
    <div className="filterbar no-print" role="region" aria-label="Фильтры">
      <span className="row strong" style={{ gap: 6 }}>
        <SlidersHorizontal size={16} className="muted" />
      </span>
      <div className="filter-group">
        <span className="filter-label">Классы</span>
        <div className="chips" role="group" aria-label="Классы">
          <button
            type="button"
            className={`chip ${shared.classIds.length === 0 ? 'on' : ''}`}
            aria-pressed={shared.classIds.length === 0}
            onClick={() => setShared({ ...shared, classIds: [] })}
          >
            Все
          </button>
          {filters.classes.map((c) => {
            const on = shared.classIds.includes(c.id);
            return (
              <button
                key={c.id}
                type="button"
                className={`chip ${on ? 'on' : ''}`}
                aria-pressed={on}
                onClick={() => setShared({ ...shared, classIds: toggle(shared.classIds, c.id) })}
                title={`${c.id}: ${c.student_count} учеников`}
              >
                {c.id}
                <span className="chip-count">{c.student_count}</span>
              </button>
            );
          })}
        </div>
      </div>

      {showTextbooks && filters.textbooks.length > 0 && (
        <>
          <span className="filter-sep" />
          <div className="filter-group">
            <span className="filter-label">Учебники</span>
            <div className="chips" role="group" aria-label="Учебники">
              <button
                type="button"
                className={`chip ${shared.textbookIds.length === 0 ? 'on' : ''}`}
                aria-pressed={shared.textbookIds.length === 0}
                onClick={() => setShared({ ...shared, textbookIds: [] })}
              >
                Все
              </button>
              {filters.textbooks.map((t) => {
                const on = shared.textbookIds.includes(t.id);
                return (
                  <button
                    key={t.id}
                    type="button"
                    className={`chip ${on ? 'on' : ''}`}
                    aria-pressed={on}
                    onClick={() => setShared({ ...shared, textbookIds: toggle(shared.textbookIds, t.id) })}
                  >
                    {t.label}
                  </button>
                );
              })}
            </div>
          </div>
        </>
      )}

      {hasMultipleVersions && (
        <>
          <span className="filter-sep" />
          <div className="filter-group">
            <label className="filter-label" htmlFor="f-version">
              Версия теста
            </label>
            <select
              id="f-version"
              className="select"
              style={{ height: 32, width: 'auto' }}
              value={shared.testVersion || ''}
              onChange={(e) => setShared({ ...shared, testVersion: e.target.value || null })}
            >
              <option value="">Все версии</option>
              {allVersions.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </div>
        </>
      )}

      {extra}
      <span className="spacer" />
      <Button size="sm" variant="ghost" icon={<RotateCcw size={14} />} disabled={active === 0} onClick={resetShared}>
        Сбросить{active > 0 ? ` (${active})` : ''}
      </Button>
    </div>
  );
}
