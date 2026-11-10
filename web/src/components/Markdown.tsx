import type { ReactNode } from 'react';

/** Сколько видимых символов ещё можно показать (для эффекта печати). */
interface Budget {
  left: number;
}

function take(text: string, budget?: Budget): string {
  if (!budget) return text;
  const part = text.slice(0, Math.max(0, budget.left));
  budget.left -= part.length;
  return part;
}

/** Минимальный безопасный Markdown для ответов ИИ: заголовки, списки, **жирный**, `код`. Без HTML. */
function inline(text: string, key: string, budget?: Budget): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  const plain = (s: string) => {
    const t = take(s, budget);
    if (t) out.push(t);
  };
  while ((m = re.exec(text))) {
    if (budget && budget.left <= 0) return out;
    if (m.index > last) plain(text.slice(last, m.index));
    const token = m[0];
    const inner = take(token.startsWith('**') ? token.slice(2, -2) : token.slice(1, -1), budget);
    if (inner) {
      if (token.startsWith('**')) out.push(<strong key={`${key}-${i++}`}>{inner}</strong>);
      else if (token.startsWith('`')) out.push(<code key={`${key}-${i++}`}>{inner}</code>);
      else out.push(<em key={`${key}-${i++}`}>{inner}</em>);
    }
    last = m.index + token.length;
  }
  if (last < text.length) plain(text.slice(last));
  return out;
}

/**
 * `limit` — сколько видимых символов показать (эффект печати). Разметка при этом
 * не ломается: жирный, списки и заголовки появляются уже оформленными.
 */
export function Markdown({ text, limit }: { text: string; limit?: number }) {
  const budget: Budget | undefined = limit === undefined ? undefined : { left: limit };
  const lines = text.replace(/\r/g, '').split('\n');
  const blocks: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  let para: string[] = [];
  const spent = () => !!budget && budget.left <= 0;

  const flushPara = () => {
    if (para.length) {
      const k = `p${blocks.length}`;
      if (!spent()) blocks.push(<p key={k}>{inline(para.join(' '), k, budget)}</p>);
      para = [];
    }
  };
  const flushList = () => {
    if (list) {
      const k = `l${blocks.length}`;
      const items: ReactNode[] = [];
      list.items.forEach((it, i) => {
        if (!spent()) items.push(<li key={i}>{inline(it, `${k}-${i}`, budget)}</li>);
      });
      if (items.length) blocks.push(list.ordered ? <ol key={k}>{items}</ol> : <ul key={k}>{items}</ul>);
      list = null;
    }
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    const heading = /^#{1,6}\s+(.*)$/.exec(line);
    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    if (!line.trim()) {
      flushPara();
      flushList();
    } else if (heading) {
      flushPara();
      flushList();
      const k = `h${blocks.length}`;
      if (!spent()) blocks.push(<h4 key={k}>{inline(heading[1], k, budget)}</h4>);
    } else if (bullet || numbered) {
      flushPara();
      const ordered = !!numbered;
      if (!list || list.ordered !== ordered) {
        flushList();
        list = { ordered, items: [] };
      }
      list.items.push((bullet || numbered)![1]);
    } else {
      flushList();
      para.push(line.trim());
    }
  }
  flushPara();
  flushList();
  return <div className="md">{blocks}</div>;
}
