import { useEffect, useState } from 'react';
import { Lock, MessageSquare, Send, Sparkles } from 'lucide-react';
import { api, ApiError } from '../api/client';
import type { CommentItem, CommentTarget, HumanRole } from '../api/types';
import { fmtDateTimeUtc5 } from '../lib/format';
import { readOnlyReason, useFeatures } from '../lib/features';
import { readJson, writeJson } from '../lib/storage';
import { useAsync } from '../lib/useAsync';
import { Markdown } from './Markdown';
import { Button, ErrorState, LoadingBlock, errorText, useToast } from './ui';

const ROLES: Record<HumanRole, string> = {
  teacher: 'Учитель',
  methodist: 'Методист',
  admin: 'Администрация',
};

interface Author {
  name: string;
  school: string;
  role: HumanRole;
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('');
}

/**
 * Обсуждение по блоку: тема, учебник, план, тема плана. Хранится на сервере (модуль collab).
 * Чтение — если сервер не отключил comments; запись — только при features.comments_write.
 * Сервер проверяет, что цель существует в наборе, и ограничивает частоту (429 + Retry-After).
 */
export function CommentsPanel({
  datasetId,
  target,
  title = 'Обсуждение',
  placeholder = 'Ваш комментарий: что работает, что нет, что предложить…',
  onCount,
}: {
  datasetId: string;
  target: { type: CommentTarget; id: string };
  title?: string;
  placeholder?: string;
  onCount?: (n: number) => void;
}) {
  const features = useFeatures();
  if (features.off('comments')) return null;
  return <CommentsInner datasetId={datasetId} target={target} title={title} placeholder={placeholder} onCount={onCount} />;
}

function CommentsInner({
  datasetId,
  target,
  title,
  placeholder,
  onCount,
}: {
  datasetId: string;
  target: { type: CommentTarget; id: string };
  title: string;
  placeholder: string;
  onCount?: (n: number) => void;
}) {
  const toast = useToast();
  const features = useFeatures();
  const canWrite = !features.off('comments_write');
  const [author, setAuthor] = useState<Author>(() => {
    const saved = readJson<Author>('ddc.author', { name: '', school: '', role: 'teacher' });
    return { ...saved, role: saved.role in ROLES ? saved.role : 'teacher' };
  });
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [touched, setTouched] = useState(false);
  // 429: блокируем отправку на Retry-After секунд и показываем обратный отсчёт.
  const [waitUntil, setWaitUntil] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const waitLeft = Math.max(0, Math.ceil((waitUntil - now) / 1000));
  useEffect(() => {
    if (!waitUntil) return;
    const t = window.setInterval(() => {
      setNow(Date.now());
      if (Date.now() >= waitUntil) {
        setWaitUntil(0);
        window.clearInterval(t);
      }
    }, 500);
    return () => window.clearInterval(t);
  }, [waitUntil]);
  const state = useAsync(
    async (signal) => {
      const res = await api.comments(datasetId, target, signal);
      onCount?.(res.total);
      return res;
    },
    `${datasetId}|${target.type}|${target.id}`,
  );

  const send = async () => {
    setTouched(true);
    if (!canWrite || sending || waitLeft > 0 || !author.name.trim() || !text.trim()) return;
    setSending(true);
    try {
      const created = await api.addComment(datasetId, {
        target_type: target.type,
        target_id: target.id,
        author_name: author.name.trim(),
        author_school: author.school.trim(),
        author_role: author.role,
        text: text.trim(),
      });
      writeJson('ddc.author', author);
      setText('');
      setTouched(false);
      const list = state.data ? { items: [created, ...state.data.items], total: state.data.total + 1 } : { items: [created], total: 1 };
      state.setData(list);
      onCount?.(list.total);
    } catch (e) {
      if (e instanceof ApiError && e.status === 429) {
        const sec = e.retryAfter ?? 60;
        setNow(Date.now());
        setWaitUntil(Date.now() + sec * 1000);
      }
      const title =
        e instanceof ApiError && e.code === 'COMMENT_TARGET_NOT_FOUND'
          ? 'Объект обсуждения не найден'
          : e instanceof ApiError && e.code === 'COMMENT_QUOTA_EXCEEDED'
            ? 'Хранилище комментариев заполнено'
            : 'Комментарий не отправлен';
      toast({ tone: 'critical', title, message: errorText(e).message });
    } finally {
      setSending(false);
    }
  };

  const items = state.data?.items || [];

  return (
    <section className="comments">
      <div className="comments-head">
        <MessageSquare size={15} className="muted" />
        <span className="strong">{title}</span>
        {state.data && (
          <span className="badge badge-outline" style={{ height: 20 }}>
            {state.data.total}
          </span>
        )}
      </div>

      {!canWrite && (
        <div className="comment-readonly">
          <Lock size={13} /> {readOnlyReason(features.readOnly)} Комментарии доступны для чтения.
        </div>
      )}
      {canWrite && <div className="comment-form">
        <div className="comment-author">
          <input
            className={`input ${touched && !author.name.trim() ? 'invalid' : ''}`}
            placeholder="Имя и фамилия"
            value={author.name}
            maxLength={80}
            onChange={(e) => setAuthor({ ...author, name: e.target.value })}
            aria-label="Имя автора"
          />
          <input
            className="input"
            placeholder="Школа"
            value={author.school}
            maxLength={120}
            onChange={(e) => setAuthor({ ...author, school: e.target.value })}
            aria-label="Школа"
          />
          <select className="select" value={author.role} onChange={(e) => setAuthor({ ...author, role: e.target.value as Author['role'] })} aria-label="Роль">
            {Object.entries(ROLES).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </div>
        <textarea
          className="textarea"
          placeholder={placeholder}
          value={text}
          maxLength={4000}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => (e.ctrlKey || e.metaKey) && e.key === 'Enter' && send()}
          aria-label="Текст комментария"
        />
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <span className="tiny faint">
            {waitLeft > 0
              ? `Слишком часто: можно отправить через ${waitLeft} с`
              : touched && !author.name.trim()
                ? 'Укажите имя — оно видно коллегам'
                : 'Ctrl + Enter — отправить'}
          </span>
          <Button variant="primary" size="sm" icon={<Send size={14} />} loading={sending} onClick={send} disabled={!text.trim() || waitLeft > 0}>
            {waitLeft > 0 ? `Через ${waitLeft} с` : 'Отправить'}
          </Button>
        </div>
      </div>}

      {state.loading && <LoadingBlock rows={2} />}
      {state.error != null && <ErrorState error={state.error} onRetry={state.reload} compact />}
      {state.data && items.length === 0 && (
        <div className="comments-empty">{canWrite ? 'Пока нет комментариев — будьте первым.' : 'Пока нет комментариев.'}</div>
      )}
      <div className="comment-list">
        {items.map((c) => (
          <CommentRow key={c.id} c={c} />
        ))}
      </div>

    </section>
  );
}

function CommentRow({ c }: { c: CommentItem }) {
  const ai = c.kind === 'ai';
  return (
    <article className={`comment ${ai ? 'ai' : ''}`}>
      <span className="avatar" aria-hidden>
        {ai ? <Sparkles size={14} /> : initials(c.author_name) || '?'}
      </span>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div className="row-wrap" style={{ gap: 6 }}>
          <span className="strong small">{c.author_name}</span>
          <span className="tiny muted">
            {ai ? 'ИИ' : ROLES[c.author_role as keyof typeof ROLES] || c.author_role}
            {c.author_school ? ` · ${c.author_school}` : ''}
          </span>
          <span className="tiny faint">· {fmtDateTimeUtc5(c.created_at)}</span>
        </div>
        {ai ? <Markdown text={c.text} /> : <div className="comment-text">{c.text}</div>}
      </div>
    </article>
  );
}
