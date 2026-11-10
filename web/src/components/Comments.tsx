import { useState } from 'react';
import { MessageSquare, Send, Sparkles } from 'lucide-react';
import { api } from '../api/client';
import type { AuthorRole, CommentItem, CommentTarget } from '../api/types';
import { fmtDateTimeUtc5, plural } from '../lib/format';
import { readJson, writeJson } from '../lib/storage';
import { useAsync } from '../lib/useAsync';
import { AiExplain } from './AiExplain';
import { Markdown } from './Markdown';
import { Button, ErrorState, LoadingBlock, errorText, useToast } from './ui';

const ROLES: Record<Exclude<AuthorRole, 'ai'>, string> = {
  teacher: 'Учитель',
  methodist: 'Методист',
  admin: 'Администрация',
};

interface Author {
  name: string;
  school: string;
  role: Exclude<AuthorRole, 'ai'>;
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('');
}

/** Обсуждение по блоку: тема, учебник, план, тема плана. Хранится на сервере (модуль collab). */
export function CommentsPanel({
  datasetId,
  target,
  title = 'Обсуждение',
  placeholder = 'Ваш комментарий: что работает, что нет, что предложить…',
  aiSummary = true,
  onCount,
}: {
  datasetId: string;
  target: { type: CommentTarget; id: string };
  title?: string;
  placeholder?: string;
  aiSummary?: boolean;
  onCount?: (n: number) => void;
}) {
  const toast = useToast();
  const [author, setAuthor] = useState<Author>(() => readJson('ddc.author', { name: '', school: '', role: 'teacher' }));
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [touched, setTouched] = useState(false);
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
    if (!author.name.trim() || !text.trim()) return;
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
      toast({ tone: 'critical', title: 'Комментарий не отправлен', message: errorText(e).message });
    } finally {
      setSending(false);
    }
  };

  const items = state.data?.items || [];
  const humans = items.filter((c) => c.kind === 'human');

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

      <div className="comment-form">
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
          <span className="tiny faint">{touched && !author.name.trim() ? 'Укажите имя — оно видно коллегам' : 'Ctrl + Enter — отправить'}</span>
          <Button variant="primary" size="sm" icon={<Send size={14} />} loading={sending} onClick={send} disabled={!text.trim()}>
            Отправить
          </Button>
        </div>
      </div>

      {state.loading && <LoadingBlock rows={2} />}
      {state.error != null && <ErrorState error={state.error} onRetry={state.reload} compact />}
      {state.data && items.length === 0 && <div className="comments-empty">Пока нет комментариев — будьте первым.</div>}
      <div className="comment-list">
        {items.map((c) => (
          <CommentRow key={c.id} c={c} />
        ))}
      </div>

      {aiSummary && humans.length >= 2 && (
        <AiExplain
          compact
          datasetId={datasetId}
          kind="comments"
          title="Сводка обсуждения от ИИ"
          hint={`${humans.length} ${plural(humans.length, ['комментарий', 'комментария', 'комментариев'])}: главные темы, согласия и разногласия`}
          context={() => ({
            target: target,
            comments: humans.slice(0, 60).map((c) => ({ role: ROLES[c.author_role as keyof typeof ROLES] || c.author_role, text: c.text })),
          })}
          saveTo={target}
        />
      )}
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
