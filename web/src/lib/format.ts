// Единые правила отображения чисел (ТЗ, раздел «Отображение чисел и статусов»):
// проценты и средние — один знак после запятой, разница — «п.п.», null — «Нет данных».

export const NO_DATA = 'Нет данных';

const one = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const int = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 });

export const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

export function fmtPct(v: number | null | undefined, fallback = NO_DATA): string {
  return isNum(v) ? `${one.format(v)}%` : fallback;
}

/** Доля 0…1 → проценты. */
export function fmtShare(v: number | null | undefined, fallback = NO_DATA): string {
  return isNum(v) ? `${one.format(v * 100)}%` : fallback;
}

export function fmtPp(v: number | null | undefined, opts: { sign?: boolean; fallback?: string } = {}): string {
  const { sign = true, fallback = NO_DATA } = opts;
  if (!isNum(v)) return fallback;
  const s = one.format(Math.abs(v));
  const prefix = v > 0 && sign ? '+' : v < 0 ? '−' : '';
  return `${prefix}${s} п.п.`;
}

export function fmtNum(v: number | null | undefined, fallback = NO_DATA): string {
  return isNum(v) ? int.format(v) : fallback;
}

export function fmtOne(v: number | null | undefined, fallback = NO_DATA): string {
  return isNum(v) ? one.format(v) : fallback;
}

export function fmtSigned(v: number): string {
  if (v > 0) return `+${v}`;
  if (v < 0) return `−${Math.abs(v)}`;
  return '0';
}

/** Русское склонение: plural(5, ['ученик','ученика','учеников']). */
export function plural(n: number, forms: [string, string, string]): string {
  const a = Math.abs(n) % 100;
  const b = a % 10;
  if (a > 10 && a < 20) return forms[2];
  if (b > 1 && b < 5) return forms[1];
  if (b === 1) return forms[0];
  return forms[2];
}

export const students = (n: number) => `${fmtNum(n)} ${plural(n, ['ученик', 'ученика', 'учеников'])}`;
export const hours = (n: number) => `${fmtNum(n)} ${plural(n, ['час', 'часа', 'часов'])}`;

const UTC5_OFFSET_MS = 5 * 60 * 60 * 1000;

/** Даты сервера в UTC; интерфейс показывает UTC+5 (фиксированное смещение, без зависимости от tzdata браузера). */
export function fmtDateTimeUtc5(iso: string | null | undefined): string {
  if (!iso) return NO_DATA;
  const normalized = /[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`;
  const t = Date.parse(normalized);
  if (Number.isNaN(t)) return iso;
  const d = new Date(t + UTC5_OFFSET_MS);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getUTCDate())}.${pad(d.getUTCMonth() + 1)}.${d.getUTCFullYear()}, ${pad(d.getUTCHours())}:${pad(
    d.getUTCMinutes(),
  )} (UTC+5)`;
}

export function fmtDate(isoDate: string | null | undefined): string {
  if (!isoDate) return NO_DATA;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoDate);
  return m ? `${m[3]}.${m[2]}.${m[1]}` : isoDate;
}

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n} Б`;
  if (n < 1024 * 1024) return `${one.format(n / 1024)} КБ`;
  return `${one.format(n / 1024 / 1024)} МБ`;
}

export function shortId(id: string, len = 8): string {
  return id.length > len ? `${id.slice(0, len)}…` : id;
}
