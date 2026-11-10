import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BarChart3,
  BookOpen,
  CircleHelp,
  ClipboardList,
  CornerDownLeft,
  Database,
  FileText,
  FlaskConical,
  GitCompareArrows,
  GraduationCap,
  Moon,
  ScrollText,
  Search,
  Upload,
  Users,
} from 'lucide-react';
import { api } from '../api/client';
import type { Dataset, Filters } from '../api/types';
import { getRecentPlans } from '../lib/storage';
import { teachersModuleReady, useFeatures } from '../lib/features';
import { datasetToCurrent, useApp } from '../state/app';
import { errorText, useToast } from './ui';

interface Cmd {
  id: string;
  group: string;
  label: string;
  hint?: string;
  icon: ReactNode;
  keywords?: string;
  run: () => void | Promise<void>;
}

export const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

export function CommandPalette({ open, onClose, onToggleTheme }: { open: boolean; onClose: () => void; onToggleTheme: () => void }) {
  const navigate = useNavigate();
  const toast = useToast();
  const { current, setCurrent } = useApp();
  const features = useFeatures();
  const teachersVisible = teachersModuleReady(features);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [filters, setFilters] = useState<Filters | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setActive(0);
    const t = setTimeout(() => inputRef.current?.focus(), 10);
    const ctrl = new AbortController();
    api
      .listDatasets(ctrl.signal)
      .then((d) => setDatasets(d.items))
      .catch(() => {});
    if (current) {
      api
        .filters(current.id, ctrl.signal)
        .then(setFilters)
        .catch(() => setFilters(null));
    } else setFilters(null);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [open, current]);

  const go = (to: string) => {
    onClose();
    navigate(to);
  };

  const commands = useMemo<Cmd[]>(() => {
    const base = current ? `/datasets/${encodeURIComponent(current.id)}` : null;
    const list: Cmd[] = [
      { id: 'nav-data', group: 'Переходы', label: 'Данные и импорт', icon: <Upload size={16} />, hint: 'шаг 1', keywords: 'загрузка csv главная', run: () => go('/') },
    ];
    if (base) {
      list.push(
        { id: 'nav-overview', group: 'Переходы', label: 'Обзор результатов', icon: <BarChart3 size={16} />, hint: 'шаг 2', keywords: 'аналитика темы теплокарта', run: () => go(`${base}/overview`) },
        { id: 'nav-cmp', group: 'Переходы', label: 'Сравнение учебников', icon: <GitCompareArrows size={16} />, hint: 'шаг 3', keywords: 'учебник a b', run: () => go(`${base}/comparison`) },
        { id: 'nav-plan', group: 'Переходы', label: 'План часов', icon: <ClipboardList size={16} />, hint: 'шаг 4', keywords: 'часы планировщик период', run: () => go(`${base}/plan`) },
      );
      if (teachersVisible) {
        list.push({ id: 'nav-teachers', group: 'Переходы', label: 'Учителя и нагрузка', icon: <GraduationCap size={16} />, keywords: 'учитель нагрузка ученики на учителя школа', run: () => go(`${base}/teachers`) });
      }
    }
    list.push({ id: 'nav-reports', group: 'Переходы', label: 'Отчёты', icon: <FileText size={16} />, hint: 'шаг 5', keywords: 'план сохранённый', run: () => go('/reports') });
    if (base) {
      list.push({ id: 'nav-brief', group: 'Переходы', label: 'Справка для педсовета', icon: <ScrollText size={16} />, keywords: 'педсовет печать документ подпись итоги', run: () => go(`${base}/brief`) });
    }
    list.push({ id: 'tour', group: 'Помощь', label: 'Экскурсия по сайту', icon: <CircleHelp size={16} />, keywords: 'как это работает помощь обучение', run: () => { onClose(); window.dispatchEvent(new Event('ddc:tour')); } });

    list.push(
      {
        id: 'act-demo',
        group: 'Действия',
        label: 'Загрузить демоданные',
        icon: <FlaskConical size={16} />,
        keywords: 'демо пример искусственные',
        run: async () => {
          onClose();
          try {
            const res = await api.createDemo();
            if (res.dataset) setCurrent(datasetToCurrent(res.dataset));
            toast({ tone: 'good', title: 'Демонабор готов', message: `${res.counts.students} искусственных учеников` });
            if (res.dataset_id) navigate(`/datasets/${encodeURIComponent(res.dataset_id)}/overview`);
          } catch (e) {
            toast({ tone: 'critical', title: 'Не удалось загрузить демо', message: errorText(e).message });
          }
        },
      },
      { id: 'act-theme', group: 'Действия', label: 'Переключить тему', icon: <Moon size={16} />, keywords: 'тёмная светлая theme', run: () => (onClose(), onToggleTheme()) },
    );

    if (base && filters) {
      [...filters.topics]
        .sort((a, b) => a.topic_order - b.topic_order)
        .forEach((t) => {
          list.push({
            id: `topic-${t.topic_id}`,
            group: 'Темы',
            label: t.topic_name,
            hint: 'детали темы',
            icon: <BookOpen size={16} />,
            keywords: t.topic_id,
            run: () => go(`${base}/overview?topic=${encodeURIComponent(t.topic_id)}`),
          });
        });
      filters.classes.forEach((c) => {
        list.push({
          id: `class-${c.id}`,
          group: 'План для класса',
          label: `План часов: ${c.id}`,
          hint: `${c.student_count} уч.`,
          icon: <Users size={16} />,
          keywords: `класс ${c.id}`,
          run: () => go(`${base}/plan?class=${encodeURIComponent(c.id)}`),
        });
      });
    }

    getRecentPlans()
      .slice(0, 5)
      .forEach((p) => {
        list.push({
          id: `plan-${p.plan_id}`,
          group: 'Недавние отчёты',
          label: `Отчёт · класс ${p.class_id}`,
          hint: p.plan_id.slice(0, 8),
          icon: <FileText size={16} />,
          keywords: `${p.dataset_name} ${p.plan_id}`,
          run: () => go(`/plans/${encodeURIComponent(p.plan_id)}`),
        });
      });

    datasets.slice(0, 8).forEach((d) => {
      list.push({
        id: `ds-${d.id}`,
        group: 'Наборы данных',
        label: d.metadata.name,
        hint: d.source_type === 'demo' ? 'демо' : `${d.metadata.grade} кл.`,
        icon: <Database size={16} />,
        keywords: `${d.metadata.subject} ${d.id}`,
        run: () => {
          setCurrent(datasetToCurrent(d));
          go(`/datasets/${encodeURIComponent(d.id)}/overview`);
        },
      });
    });
    return list;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current, filters, datasets, teachersVisible]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter((c) => `${c.label} ${c.keywords || ''} ${c.group}`.toLowerCase().includes(q));
  }, [commands, query]);

  useEffect(() => setActive(0), [query]);
  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-idx="${active}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [active]);

  if (!open) return null;

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((a) => Math.min(filtered.length - 1, a + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((a) => Math.max(0, a - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      filtered[active]?.run();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    }
  };

  let lastGroup = '';
  return (
    <>
      <div className="cmdk-backdrop" onClick={onClose} />
      <div className="cmdk" role="dialog" aria-modal="true" aria-label="Команды и поиск" onKeyDown={onKey}>
        <div className="cmdk-input">
          <Search size={18} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Куда перейти или что сделать…"
            aria-label="Поиск команды"
            aria-activedescendant={filtered[active] ? `cmd-${filtered[active].id}` : undefined}
          />
          <span className="kbd">Esc</span>
        </div>
        <div className="cmdk-list" ref={listRef} role="listbox">
          {filtered.length === 0 && <div className="cmdk-empty">Ничего не найдено по «{query}»</div>}
          {filtered.map((c, i) => {
            const header = c.group !== lastGroup ? c.group : null;
            lastGroup = c.group;
            return (
              <div key={c.id}>
                {header && <div className="cmdk-group">{header}</div>}
                <button
                  type="button"
                  id={`cmd-${c.id}`}
                  data-idx={i}
                  role="option"
                  aria-selected={i === active}
                  className={`cmdk-item ${i === active ? 'active' : ''}`}
                  onMouseMove={() => setActive(i)}
                  onClick={() => c.run()}
                >
                  {c.icon}
                  <span>{c.label}</span>
                  {c.hint && <span className="hint">{c.hint}</span>}
                </button>
              </div>
            );
          })}
        </div>
        <div className="cmdk-foot">
          <span>
            <span className="kbd">↑</span>
            <span className="kbd">↓</span> выбрать
          </span>
          <span>
            <span className="kbd">
              <CornerDownLeft size={10} />
            </span>{' '}
            открыть
          </span>
          <span style={{ marginLeft: 'auto' }}>
            <span className="kbd">{isMac ? '⌘' : 'Ctrl'}</span>
            <span className="kbd">K</span> в любой момент
          </span>
        </div>
      </div>
    </>
  );
}
