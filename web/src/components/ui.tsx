import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
} from 'react';
import { createPortal } from 'react-dom';
import {
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  Info,
  Inbox,
  Minus,
  Plus,
  RefreshCw,
  WifiOff,
  X,
  XCircle,
} from 'lucide-react';
import { ApiError } from '../api/client';
import type { TopicStatus } from '../api/types';
import { TOPIC_STATUS, type Tone } from '../lib/status';

/* ---------- Button ---------- */
type BtnVariant = 'default' | 'primary' | 'ghost' | 'soft' | 'danger-soft';
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: BtnVariant;
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  icon?: ReactNode;
  iconOnly?: boolean;
}
export function Button({
  variant = 'default',
  size = 'md',
  loading,
  icon,
  iconOnly,
  className = '',
  children,
  disabled,
  ...rest
}: ButtonProps) {
  const cls = [
    'btn',
    variant !== 'default' ? `btn-${variant}` : '',
    size !== 'md' ? `btn-${size}` : '',
    iconOnly ? 'btn-icon' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');
  return (
    <button className={cls} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading ? <span className="spinner" aria-hidden /> : icon}
      {children}
    </button>
  );
}

/* ---------- Badges ---------- */
export function Badge({ tone = 'neutral', children, icon, title }: { tone?: Tone | 'accent' | 'demo' | 'outline'; children: ReactNode; icon?: ReactNode; title?: string }) {
  return (
    <span className={`badge badge-${tone}`} title={title}>
      {icon}
      {children}
    </span>
  );
}

export function StatusBadge({ status, label }: { status: TopicStatus; label?: string }) {
  const meta = TOPIC_STATUS[status] ?? TOPIC_STATUS.no_data;
  return (
    <span className={`badge badge-${meta.tone}`}>
      <span className="badge-ico" aria-hidden>
        {meta.icon}
      </span>
      {label || meta.label}
    </span>
  );
}

export function DemoBadge({ compact }: { compact?: boolean }) {
  return (
    <span className="badge badge-demo" title="Набор создан демомаршрутом сервера: все ученики искусственные">
      <span aria-hidden>🧪</span>
      {compact ? 'Демо' : 'Искусственные данные'}
    </span>
  );
}

/* ---------- Banner ---------- */
export function Banner({
  tone = 'info',
  title,
  children,
  action,
}: {
  tone?: 'info' | 'warning' | 'critical' | 'good' | 'neutral' | 'serious';
  title?: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
}) {
  const Icon =
    tone === 'critical' ? XCircle : tone === 'good' ? CheckCircle2 : tone === 'info' || tone === 'neutral' ? Info : AlertTriangle;
  return (
    <div className={`banner banner-${tone}`} role={tone === 'critical' ? 'alert' : 'status'}>
      <Icon size={18} />
      <div style={{ flex: 1, minWidth: 0 }}>
        {title && <div className="banner-title">{title}</div>}
        {children && <div className={title ? 'small text-2' : ''}>{children}</div>}
      </div>
      {action}
    </div>
  );
}

export function WarningsList({ warnings, tone = 'warning' }: { warnings?: string[]; tone?: 'warning' | 'info' | 'neutral' }) {
  const list = (warnings || []).filter(Boolean);
  if (!list.length) return null;
  if (list.length === 1) return <Banner tone={tone}>{list[0]}</Banner>;
  return (
    <Banner tone={tone} title="Обратите внимание">
      <ul>
        {list.map((w, i) => (
          <li key={i}>{w}</li>
        ))}
      </ul>
    </Banner>
  );
}

/* ---------- Skeleton & states ---------- */
export function Skeleton({ h = 16, w = '100%', r, style }: { h?: number | string; w?: number | string; r?: number; style?: React.CSSProperties }) {
  return <div className="skeleton" style={{ height: h, width: w, borderRadius: r, ...style }} aria-hidden />;
}

export function LoadingBlock({ rows = 4, label = 'Загрузка данных…' }: { rows?: number; label?: string }) {
  return (
    <div className="stack-sm" role="status" aria-live="polite" style={{ padding: 20 }}>
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} h={i === 0 ? 22 : 40} w={i === 0 ? '40%' : '100%'} />
      ))}
    </div>
  );
}

export function EmptyState({ title, children, action, icon }: { title: string; children?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="state">
      <div className="state-icon">{icon || <Inbox size={26} />}</div>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

export function errorText(err: unknown): { title: string; message: string; network: boolean } {
  if (err instanceof ApiError) {
    if (err.isNetwork) return { title: 'Нет связи с сервером', message: err.message, network: true };
    const title =
      err.status === 404
        ? 'Не найдено'
        : err.status === 422
          ? 'Запрос отклонён сервером'
          : err.status === 403
            ? 'Недоступно в деморежиме'
            : err.status === 503
              ? 'Сервер временно недоступен'
              : 'Ошибка сервера';
    return { title, message: err.message, network: false };
  }
  return { title: 'Что-то пошло не так', message: (err as Error)?.message || 'Неизвестная ошибка', network: false };
}

export function ErrorState({ error, onRetry, compact }: { error: unknown; onRetry?: () => void; compact?: boolean }) {
  const { title, message, network } = errorText(error);
  const details = error instanceof ApiError ? error.details : [];
  return (
    <div className="state error" role="alert" style={compact ? { padding: 24 } : undefined}>
      <div className="state-icon">{network ? <WifiOff size={26} /> : <AlertTriangle size={26} />}</div>
      <h3>{title}</h3>
      <p>{message}</p>
      {details.length > 0 && (
        <ul className="small text-2" style={{ textAlign: 'left', margin: 0 }}>
          {details.slice(0, 5).map((d, i) => (
            <li key={i}>{[d.field, d.reason].filter(Boolean).join(': ')}</li>
          ))}
        </ul>
      )}
      {onRetry && (
        <Button variant="primary" icon={<RefreshCw size={16} />} onClick={onRetry} style={{ marginTop: 6 }}>
          Повторить
        </Button>
      )}
    </div>
  );
}

/** Обёртка, которая приглушает устаревшие данные во время обновления. */
export function Refreshing({ active, children, label = 'Обновляем по новым фильтрам…' }: { active: boolean; children: ReactNode; label?: string }) {
  return (
    <div className={active ? 'refreshing' : ''} aria-busy={active || undefined}>
      {children}
      {active && (
        <div className="refresh-veil">
          <span className="refresh-pill">
            <span className="spinner" /> {label}
          </span>
        </div>
      )}
    </div>
  );
}

/* ---------- Info popover «Как рассчитано» ---------- */
export function InfoPopover({
  title = 'Как рассчитано',
  children,
  label = 'Как рассчитано',
  align = 'center',
  iconOnly,
}: {
  title?: string;
  children: ReactNode;
  label?: string;
  align?: 'center' | 'left' | 'right';
  iconOnly?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const id = useId();
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);
  return (
    <span className="info-wrap" ref={ref}>
      <button
        type="button"
        className="info-btn"
        aria-expanded={open}
        aria-controls={id}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
        title={label}
      >
        <CircleHelp size={14} />
        {!iconOnly && label}
      </button>
      {open && (
        <div className={`popover ${align !== 'center' ? `align-${align}` : ''}`} id={id} role="dialog" onClick={(e) => e.stopPropagation()}>
          <h4>{title}</h4>
          <div className="text-2">{children}</div>
        </div>
      )}
    </span>
  );
}

/* ---------- Drawer ---------- */
export function Drawer({ open, onClose, children, labelledBy }: { open: boolean; onClose: () => void; children: ReactNode; labelledBy?: string }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);
  if (!open) return null;
  return createPortal(
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby={labelledBy}>
        {children}
      </aside>
    </>,
    document.body,
  );
}

export function CloseButton({ onClick }: { onClick: () => void }) {
  return (
    <Button variant="ghost" iconOnly size="sm" onClick={onClick} aria-label="Закрыть" title="Закрыть (Esc)">
      <X size={18} />
    </Button>
  );
}

/* ---------- Toasts ---------- */
type ToastTone = 'good' | 'critical' | 'info';
interface ToastItem {
  id: number;
  tone: ToastTone;
  title: string;
  message?: string;
}
const ToastCtx = createContext<(t: Omit<ToastItem, 'id'>) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((t: Omit<ToastItem, 'id'>) => {
    const id = Date.now() + Math.random();
    setItems((list) => [...list.slice(-3), { ...t, id }]);
    setTimeout(() => setItems((list) => list.filter((x) => x.id !== id)), t.tone === 'critical' ? 7000 : 4200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite">
        {items.map((t) => {
          const Icon = t.tone === 'good' ? CheckCircle2 : t.tone === 'critical' ? XCircle : Info;
          return (
            <div key={t.id} className={`toast toast-${t.tone}`} role={t.tone === 'critical' ? 'alert' : 'status'}>
              <Icon size={18} />
              <div style={{ flex: 1 }}>
                <div className="toast-title">{t.title}</div>
                {t.message && <div className="toast-msg">{t.message}</div>}
              </div>
              <button
                className="btn btn-ghost btn-sm btn-icon"
                aria-label="Закрыть уведомление"
                onClick={() => setItems((list) => list.filter((x) => x.id !== t.id))}
              >
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastCtx.Provider>
  );
}

/* ---------- Count-up number ---------- */
export function CountUp({ value, format, duration = 700 }: { value: number; format: (n: number) => string; duration?: number }) {
  const [shown, setShown] = useState(value);
  const from = useRef(0);
  useEffect(() => {
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if (reduce) {
      setShown(value);
      from.current = value;
      return;
    }
    const start = performance.now();
    const a = from.current;
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / duration);
      const e = 1 - Math.pow(1 - p, 3);
      setShown(a + (value - a) * e);
      if (p < 1) raf = requestAnimationFrame(tick);
      else from.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);
  return <>{format(shown)}</>;
}

/* ---------- Meter ---------- */
export function Meter({ value, max = 100, color, mark }: { value: number | null; max?: number; color?: string; mark?: number }) {
  const pct = value == null ? 0 : Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="meter" aria-hidden>
      {value != null && <div className="meter-fill" style={{ width: `${pct}%`, background: color || 'var(--accent)' }} />}
      {mark != null && <div className="meter-mark" style={{ left: `calc(${(mark / max) * 100}% - 1px)` }} />}
    </div>
  );
}

/* ---------- Switch ---------- */
export function Switch({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <label className="switch" title={label}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} aria-label={label} />
      <span />
    </label>
  );
}

/* ---------- Hours stepper ---------- */
export function HoursStepper({
  value,
  onChange,
  min = 0,
  max = 10000,
  disabled,
  invalid,
  changed,
  label,
}: {
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  disabled?: boolean;
  invalid?: boolean;
  changed?: boolean;
  label: string;
}) {
  const [draft, setDraft] = useState(String(value));
  useEffect(() => setDraft(String(value)), [value]);
  const commit = (raw: string) => {
    const n = Number(raw);
    if (raw.trim() === '' || !Number.isFinite(n)) {
      setDraft(String(value));
      return;
    }
    const v = Math.max(0, Math.min(10000, Math.round(n)));
    onChange(v);
    setDraft(String(v));
  };
  return (
    <div className={`hours-stepper ${invalid ? 'invalid' : ''} ${changed && !invalid ? 'changed' : ''}`}>
      <button type="button" onClick={() => onChange(value - 1)} disabled={disabled || value <= min} aria-label={`${label}: уменьшить`}>
        <Minus size={14} />
      </button>
      <input
        type="number"
        inputMode="numeric"
        value={draft}
        disabled={disabled}
        aria-label={label}
        aria-invalid={invalid || undefined}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={(e) => commit(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit((e.target as HTMLInputElement).value);
          if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (value < max) onChange(value + 1);
          }
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (value > min) onChange(value - 1);
          }
        }}
      />
      <button type="button" onClick={() => onChange(value + 1)} disabled={disabled || value >= max} aria-label={`${label}: увеличить`}>
        <Plus size={14} />
      </button>
    </div>
  );
}
