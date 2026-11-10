import { useEffect, useState } from 'react';
import { Check, Copy, MessageSquarePlus, RefreshCw, Sparkles } from 'lucide-react';
import { api, ApiError } from '../api/client';
import type { AiKind, CommentTarget, Explanation } from '../api/types';
import { fmtDateTimeUtc5 } from '../lib/format';
import { useApp } from '../state/app';
import { Markdown } from './Markdown';
import { Banner, Button, errorText, useToast } from './ui';

/**
 * Кнопка «Объяснить с ИИ» и карточка ответа. Сервер ходит в Groq/Gemini;
 * без ключей возвращает 503 AI_NOT_CONFIGURED — показываем понятную подсказку.
 */
export function AiExplain({
  datasetId,
  kind,
  context,
  title = 'ИИ-пояснение',
  hint,
  saveTo,
  compact,
}: {
  datasetId: string;
  kind: AiKind;
  context: () => unknown;
  title?: string;
  hint?: string;
  saveTo?: { type: CommentTarget; id: string };
  compact?: boolean;
}) {
  const { capabilities } = useApp();
  const toast = useToast();
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Explanation | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [copied, setCopied] = useState(false);
  const [saved, setSaved] = useState(false);
  // Эффект печати: ответ «набирается» ~2–3 секунды; клик по тексту показывает его сразу.
  const [shown, setShown] = useState(Infinity);
  const typing = result != null && shown < result.text.length;
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
  const notConfigured =
    capabilities?.features.ai_explain === false || (error instanceof ApiError && error.code === 'AI_NOT_CONFIGURED');

  const run = async () => {
    setLoading(true);
    setError(null);
    setSaved(false);
    try {
      const res = await api.aiExplain(datasetId, { kind, context: context(), question: question.trim() || null });
      setResult(res);
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

  const save = async () => {
    if (!result || !saveTo) return;
    try {
      await api.addComment(datasetId, {
        target_type: saveTo.type,
        target_id: saveTo.id,
        author_name: 'ИИ-помощник',
        author_role: 'ai',
        text: result.text,
      });
      setSaved(true);
      toast({ tone: 'good', title: 'Пояснение добавлено в обсуждение' });
    } catch (e) {
      toast({ tone: 'critical', title: 'Не удалось сохранить', message: errorText(e).message });
    }
  };

  return (
    <section className={`ai-card ${compact ? 'compact' : ''}`}>
      <div className="ai-head">
        <span className="ai-icon">
          <Sparkles size={15} />
        </span>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="strong">{title}</div>
          <div className="tiny muted">{hint || 'ИИ объясняет уже рассчитанные показатели простыми словами. Числа сверяйте с таблицами.'}</div>
        </div>
      </div>

      <div className="ai-ask">
        <input
          className="input"
          placeholder="Уточняющий вопрос (необязательно)"
          value={question}
          maxLength={500}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !loading && run()}
          aria-label="Вопрос для ИИ"
        />
        <Button variant="primary" icon={result ? <RefreshCw size={15} /> : <Sparkles size={15} />} loading={loading} onClick={run}>
          {result ? 'Ещё раз' : 'Объяснить с ИИ'}
        </Button>
      </div>

      {notConfigured && (
        <Banner tone="info" title="ИИ не подключён на сервере">
          Администратор задаёт бесплатные ключи <code>GROQ_API_KEY</code> или <code>GEMINI_API_KEY</code> в окружении сервера. Остальные функции работают без ИИ.
        </Banner>
      )}
      {error != null && !notConfigured && (
        <Banner tone="critical" title="ИИ не ответил">
          {errorText(error).message}
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
            {saveTo && (
              <Button size="sm" variant="ghost" icon={<MessageSquarePlus size={14} />} onClick={save} disabled={saved}>
                {saved ? 'В обсуждении' : 'В обсуждение'}
              </Button>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
