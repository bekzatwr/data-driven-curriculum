import { useEffect, useState } from 'react';
import { Check, Copy, RefreshCw, Sparkles } from 'lucide-react';
import { api, ApiError } from '../api/client';
import type { AiKind, AiSelectors, Explanation } from '../api/types';
import { fmtDateTimeUtc5 } from '../lib/format';
import { useFeatures } from '../lib/features';
import { useApp } from '../state/app';
import { Markdown } from './Markdown';
import { Banner, Button, errorText } from './ui';

/**
 * «Объяснить с ИИ». Контракт PR #6: браузер передаёт только селекторы (фильтры, тема,
 * учебники, plan_id), показатели сервер берёт из своей аналитики. Свободный вопрос и
 * сохранение ответа как комментария не поддерживаются: так ни данные учеников, ни текст
 * ИИ от имени пользователя не уходят.
 *
 * Кнопка показывается, только если сервер сообщил features.ai_explain = true и набор —
 * встроенный демо (для загруженных наборов сервер отвечает 403 AI_DEMO_ONLY).
 */
export function AiExplain({
  datasetId,
  kind,
  selectors,
  title = 'ИИ-пояснение',
  hint,
  compact,
}: {
  datasetId: string;
  kind: AiKind;
  selectors: () => AiSelectors;
  title?: string;
  hint?: string;
  compact?: boolean;
}) {
  const { current } = useApp();
  const features = useFeatures();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Explanation | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [copied, setCopied] = useState(false);
  // Эффект печати: ответ «набирается» ~2–3 секунды; клик по тексту показывает его сразу.
  const [shown, setShown] = useState(Infinity);
  const typing = result != null && shown < result.text.length;

  const isDemo = current?.id === datasetId ? current.isDemo : true;
  const code = error instanceof ApiError ? error.code : null;
  const enabled = features.on('ai_explain') && isDemo && code !== 'AI_NOT_CONFIGURED' && code !== 'AI_DEMO_ONLY';

  useEffect(() => {
    if (!result) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setShown(Infinity);
      return;
    }
    const step = Math.max(4, Math.ceil(result.text.length / 150));
    setShown(0);
    const t = window.setInterval(() => {
      setShown((s) => {
        const next = s + step;
        if (next >= result.text.length) window.clearInterval(t);
        return next;
      });
    }, 16);
    return () => window.clearInterval(t);
  }, [result]);

  const run = async () => {
    if (loading || !enabled) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await api.aiExplain(datasetId, { kind, context: selectors() }));
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  };

  const copy = async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  };

  // Сервер ещё не ответил, есть ли ИИ, — ничего не показываем, чтобы не мигать.
  // Если ИИ на сервере выключен или набор не демо, блок не занимает место на экране:
  // пустая карточка «ИИ не подключён» на каждой странице только перегружает интерфейс.
  if (!features.loaded || !features.on('ai_explain') || !isDemo) return null;

  const unavailable = code === 'AI_NOT_CONFIGURED';
  const demoOnly = code === 'AI_DEMO_ONLY';

  return (
    <section className={`ai-card ${compact ? 'compact' : ''}`}>
      <div className="ai-head">
        <span className="ai-icon">
          <Sparkles size={15} />
        </span>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="strong">{title}</div>
          <div className="tiny muted">{hint || 'ИИ объясняет уже рассчитанные сервером показатели простыми словами. Числа сверяйте с таблицами.'}</div>
        </div>
        {enabled && (
          <Button variant="primary" icon={result ? <RefreshCw size={15} /> : <Sparkles size={15} />} loading={loading} onClick={run}>
            {result ? 'Ещё раз' : 'Объяснить с ИИ'}
          </Button>
        )}
      </div>

      {unavailable ? (
        <div className="tiny muted ai-off">
          ИИ не подключён на сервере. Остальные функции работают без него.
        </div>
      ) : demoOnly ? (
        <div className="tiny muted ai-off">ИИ-пояснения доступны только для встроенного синтетического демонабора — данные загруженных наборов в ИИ не передаются.</div>
      ) : null}

      {error != null && !unavailable && !demoOnly && (
        <Banner tone="critical" title={code === 'TIMEOUT' ? 'ИИ не ответил вовремя' : 'ИИ не ответил'}>
          {errorText(error).message} Повторите попытку кнопкой выше.
        </Banner>
      )}
      {loading && !result && (
        <div className="ai-thinking">
          <span className="ai-orb" aria-hidden /> ИИ читает показатели
          <span className="ai-dots" aria-hidden>
            <i />
            <i />
            <i />
          </span>
        </div>
      )}
      {result && (
        <div className={`ai-result ${loading ? 'stale' : ''} ${typing ? 'typing' : ''}`} onClick={() => typing && setShown(Infinity)}>
          <Markdown text={result.text} limit={typing ? shown : undefined} />
          <div className="ai-foot">
            <span className="tiny faint">
              {result.provider} · {result.model} · {fmtDateTimeUtc5(result.created_at)}
            </span>
            <span className="spacer" />
            <Button size="sm" variant="ghost" icon={copied ? <Check size={14} /> : <Copy size={14} />} onClick={copy}>
              {copied ? 'Скопировано' : 'Копировать'}
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
