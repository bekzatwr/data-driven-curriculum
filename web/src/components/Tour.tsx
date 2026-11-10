import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, FlaskConical, X } from 'lucide-react';
import { api } from '../api/client';
import { datasetToCurrent, useApp } from '../state/app';
import { Button, errorText, useToast } from './ui';

interface Step {
  title: string;
  text: string;
  /** Путь страницы шага; base — /datasets/{id} текущего набора. */
  path: (base: string | null) => string | null;
  /** Блок, который подсвечиваем (если найден). */
  focus: string;
  needsDataset?: boolean;
}

const STEPS: Step[] = [
  {
    title: 'Данные',
    text: 'Загрузите два CSV — результаты тестов и учебный план — или откройте демонабор. Ошибки в файлах показываются построчно ещё до сохранения.',
    path: () => '/',
    focus: '.tiles',
  },
  {
    title: 'Обзор результатов',
    text: 'Главные показатели и теплокарта «тема × класс»: красное — ниже порога освоения. Нажмите на тему, чтобы увидеть разбор по классам и обсуждение коллег.',
    path: (b) => (b ? `${b}/overview` : null),
    focus: '.kpi-strip',
    needsDataset: true,
  },
  {
    title: 'Сравнение учебников',
    text: 'Прирост «до → после» на одних и тех же учениках. Если группы несопоставимы, разница не показывается — сравнение описательное, без «лучшего учебника».',
    path: (b) => (b ? `${b}/comparison` : null),
    focus: '.verdict, .vs-grid',
    needsDataset: true,
  },
  {
    title: 'План учебных часов',
    text: 'Выберите класс — система предложит перераспределение часов (±N или на весь период) с обоснованием по каждой теме. Общая сумма, минимумы, максимумы и блокировки соблюдаются; решение за методистом.',
    path: (b) => (b ? `${b}/plan` : null),
    focus: '.class-picker, .action-bar',
    needsDataset: true,
  },
  {
    title: 'Отчёт и справка для педсовета',
    text: 'Сохранённый план — это отчёт с печатью и CSV. «Справка для педсовета» собирает итоги, сравнение и план на одну страницу с местом для подписей.',
    path: (b) => (b ? `${b}/brief` : '/reports'),
    focus: '.brief-sheet, .card',
    needsDataset: true,
  },
];

/** Экскурсия по сайту: карточка внизу экрана, переходы по шагам и подсветка главного блока страницы. */
export function Tour({ onClose }: { onClose: () => void }) {
  const { current, setCurrent } = useApp();
  const navigate = useNavigate();
  const toast = useToast();
  const [i, setI] = useState(0);
  const [loadingDemo, setLoadingDemo] = useState(false);
  const step = STEPS[i];
  const base = current ? `/datasets/${encodeURIComponent(current.id)}` : null;
  const target = step.path(base);
  const blocked = step.needsDataset && !base;

  // Переход на страницу шага и подсветка блока (ждём, пока он появится).
  useEffect(() => {
    if (!target) return;
    navigate(target);
    let tries = 0;
    let el: Element | null = null;
    const t = window.setInterval(() => {
      tries += 1;
      el = document.querySelector(step.focus);
      if (el || tries > 30) {
        window.clearInterval(t);
        if (el) {
          el.classList.add('tour-focus');
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }
    }, 120);
    return () => {
      window.clearInterval(t);
      document.querySelectorAll('.tour-focus').forEach((n) => n.classList.remove('tour-focus'));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [i, target]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowRight' && i < STEPS.length - 1 && !blocked) setI(i + 1);
      if (e.key === 'ArrowLeft' && i > 0) setI(i - 1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [i, blocked, onClose]);

  const openDemo = async () => {
    setLoadingDemo(true);
    try {
      const res = await api.createDemo();
      if (res.dataset) setCurrent(datasetToCurrent(res.dataset));
    } catch (e) {
      toast({ tone: 'critical', title: 'Не удалось открыть демо', message: errorText(e).message });
    } finally {
      setLoadingDemo(false);
    }
  };

  return (
    <aside className="tour" role="dialog" aria-label="Экскурсия по сайту" aria-live="polite">
      <div className="tour-top">
        <span className="tour-count">
          Шаг {i + 1} из {STEPS.length}
        </span>
        <span className="tour-dots" aria-hidden>
          {STEPS.map((_, k) => (
            <i key={k} className={k === i ? 'on' : k < i ? 'done' : ''} />
          ))}
        </span>
        <button type="button" className="btn btn-ghost btn-icon btn-sm" aria-label="Закрыть экскурсию" onClick={onClose}>
          <X size={15} />
        </button>
      </div>
      <div className="tour-title">{step.title}</div>
      <p className="tour-text">{step.text}</p>
      {blocked && (
        <div className="tour-need">
          Для этого шага нужен набор данных.
          <Button size="sm" variant="primary" icon={<FlaskConical size={14} />} loading={loadingDemo} onClick={openDemo}>
            Открыть демо
          </Button>
        </div>
      )}
      <div className="tour-actions">
        <Button size="sm" variant="ghost" icon={<ArrowLeft size={14} />} disabled={i === 0} onClick={() => setI(i - 1)}>
          Назад
        </Button>
        <span className="spacer" />
        {i < STEPS.length - 1 ? (
          <Button size="sm" variant="primary" disabled={blocked} onClick={() => setI(i + 1)}>
            Далее <ArrowRight size={14} />
          </Button>
        ) : (
          <Button size="sm" variant="primary" onClick={onClose}>
            Готово
          </Button>
        )}
      </div>
    </aside>
  );
}
