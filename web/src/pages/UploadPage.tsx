import { useMemo, useRef, useState, type DragEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Download,
  FileSpreadsheet,
  FlaskConical,
  Layers,
  ListChecks,
  Lock,
  ShieldCheck,
  Sparkles,
  Upload,
  UploadCloud,
  X,
} from 'lucide-react';
import { api, ApiError } from '../api/client';
import type { DatasetMetadata, ImportResponse } from '../api/types';
import { Badge, Banner, Button, DemoBadge, EmptyState, ErrorState, LoadingBlock, useToast, errorText } from '../components/ui';
import { fmtBytes, fmtDate, fmtDateTimeUtc5, fmtNum, plural } from '../lib/format';
import { useAsync } from '../lib/useAsync';
import { datasetToCurrent, useApp } from '../state/app';

const DEFAULT_META: DatasetMetadata = {
  name: '',
  subject: 'Математика',
  grade: 7,
  period_start: '2026-09-01',
  period_end: '2026-10-31',
};

type CheckState =
  | { kind: 'idle' }
  | { kind: 'checking' }
  | { kind: 'valid'; result: ImportResponse; signature: string }
  | { kind: 'invalid'; error: unknown; signature: string };

export function UploadPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const { capabilities, setCurrent, current } = useApp();
  const datasets = useAsync((s) => api.listDatasets(s), 'list');
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoError, setDemoError] = useState<unknown>(null);
  const formRef = useRef<HTMLDivElement>(null);

  const importAllowed = capabilities ? capabilities.features.csv_import !== false : true;

  const loadDemo = async () => {
    setDemoLoading(true);
    setDemoError(null);
    try {
      const res = await api.createDemo();
      const ds = res.dataset;
      if (!res.dataset_id) throw new Error('Сервер не вернул ID набора');
      if (ds) setCurrent(datasetToCurrent(ds));
      toast({
        tone: 'good',
        title: res.httpStatus === 201 ? 'Демонабор создан' : 'Демонабор открыт',
        message: `${fmtNum(res.counts.students)} искусственных учеников, ${fmtNum(res.counts.results)} записей.`,
      });
      navigate(`/datasets/${encodeURIComponent(res.dataset_id)}/overview`);
    } catch (e) {
      setDemoError(e);
    } finally {
      setDemoLoading(false);
    }
  };

  return (
    <div className="stack" style={{ gap: 24 }}>
      <section className="hero fade-up">
        <Badge tone="outline">
          <Sparkles size={13} /> P0 · Импорт → Аналитика → Сравнение → План → Отчёт
        </Badge>
        <h1 style={{ marginTop: 14 }}>Где ученики испытывают трудности и как перераспределить часы</h1>
        <p>
          Загрузите результаты тестов и учебный план — увидите проблемные темы, честное сравнение учебников и объяснимое
          предложение по часам с сохранением общей суммы.
        </p>
        <div className="hero-actions">
          <Button size="lg" className="btn-white" onClick={loadDemo} loading={demoLoading} icon={<FlaskConical size={18} />}>
            Загрузить демоданные
          </Button>
          <Button
            size="lg"
            icon={<UploadCloud size={18} />}
            onClick={() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
          >
            Загрузить свои CSV
          </Button>
          {current && (
            <Button size="lg" icon={<ArrowRight size={18} />} onClick={() => navigate(`/datasets/${encodeURIComponent(current.id)}/overview`)}>
              Продолжить: {current.name.length > 26 ? `${current.name.slice(0, 26)}…` : current.name}
            </Button>
          )}
        </div>
        <div className="hero-flow" aria-hidden>
          <span>
            <ShieldCheck size={14} /> Проверка до сохранения
          </span>
          <span>
            <Layers size={14} /> Темы × классы
          </span>
          <span>
            <ListChecks size={14} /> Сравнение без «лучшего учебника»
          </span>
          <span>
            <Lock size={14} /> Сумма часов и блокировки соблюдаются
          </span>
        </div>
      </section>

      {demoError != null && (
        <Banner tone="critical" title="Не удалось загрузить демоданные" action={<Button size="sm" onClick={loadDemo}>Повторить</Button>}>
          {errorText(demoError).message}
        </Banner>
      )}

      <div className="grid-2" style={{ gridTemplateColumns: 'minmax(0, 1.55fr) minmax(0, 1fr)', alignItems: 'start' }}>
        <div ref={formRef} style={{ scrollMarginTop: 90 }}>
          <ImportForm allowed={importAllowed} limitBytes={capabilities?.limits.csv_files_bytes} onImported={() => datasets.reload()} />
        </div>

        <section className="card fade-up-2">
          <div className="card-head">
            <h2>
              <FileSpreadsheet size={18} /> Наборы данных
            </h2>
            <span className="spacer" />
            {datasets.data && <Badge>{datasets.data.total}</Badge>}
          </div>
          {datasets.loading && <LoadingBlock rows={4} />}
          {datasets.error != null && <ErrorState error={datasets.error} onRetry={datasets.reload} compact />}
          {datasets.data && datasets.data.items.length === 0 && (
            <EmptyState title="Пока нет наборов">Загрузите демо или свои CSV — набор появится здесь.</EmptyState>
          )}
          {datasets.data && datasets.data.items.length > 0 && (
            <div style={{ maxHeight: 560, overflowY: 'auto' }}>
              {datasets.data.items.map((d) => (
                <Link
                  key={d.id}
                  to={`/datasets/${encodeURIComponent(d.id)}/overview`}
                  className="dataset-item"
                  onClick={() => setCurrent(datasetToCurrent(d))}
                  style={current?.id === d.id ? { background: 'var(--accent-soft)' } : undefined}
                >
                  <span className="dataset-icon">{d.source_type === 'demo' ? <FlaskConical size={18} /> : <FileSpreadsheet size={18} />}</span>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div className="row" style={{ gap: 6 }}>
                      <span className="name">{d.metadata.name}</span>
                      {d.source_type === 'demo' && <DemoBadge compact />}
                    </div>
                    <div className="small muted">
                      {d.metadata.subject} · {d.metadata.grade} класс · {fmtDate(d.metadata.period_start)}–{fmtDate(d.metadata.period_end)}
                    </div>
                    <div className="tiny muted">
                      {fmtNum(d.counts.students)} {plural(d.counts.students, ['ученик', 'ученика', 'учеников'])} · {fmtNum(d.counts.results)}{' '}
                      записей · {fmtDateTimeUtc5(d.created_at)}
                    </div>
                  </div>
                  <ChevronRight size={18} className="muted" />
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

/* ================================================================= */

function ImportForm({ allowed, limitBytes, onImported }: { allowed: boolean; limitBytes?: number; onImported: () => void }) {
  const navigate = useNavigate();
  const toast = useToast();
  const { setCurrent } = useApp();
  const [meta, setMeta] = useState<DatasetMetadata>(DEFAULT_META);
  const [results, setResults] = useState<File | null>(null);
  const [curriculum, setCurriculum] = useState<File | null>(null);
  const [touched, setTouched] = useState(false);
  const [check, setCheck] = useState<CheckState>({ kind: 'idle' });
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<unknown>(null);

  const signature = `${JSON.stringify(meta)}|${fileSig(results)}|${fileSig(curriculum)}`;
  const limit = limitBytes ?? 10 * 1024 * 1024;

  const errors = useMemo(() => {
    const e: Partial<Record<keyof DatasetMetadata | 'results' | 'curriculum' | 'size', string>> = {};
    if (!meta.name.trim()) e.name = 'Укажите название набора';
    else if (meta.name.length > 120) e.name = 'Не длиннее 120 символов';
    if (!meta.subject.trim()) e.subject = 'Укажите предмет';
    if (!Number.isInteger(meta.grade) || meta.grade < 1 || meta.grade > 12) e.grade = 'Параллель от 1 до 12';
    if (!meta.period_start) e.period_start = 'Укажите дату начала';
    if (!meta.period_end) e.period_end = 'Укажите дату окончания';
    if (meta.period_start && meta.period_end && meta.period_end < meta.period_start) e.period_end = 'Конец периода раньше начала';
    if (!results) e.results = 'Выберите results.csv';
    else if (!/\.csv$/i.test(results.name)) e.results = 'Нужен файл .csv';
    if (!curriculum) e.curriculum = 'Выберите curriculum.csv';
    else if (!/\.csv$/i.test(curriculum.name)) e.curriculum = 'Нужен файл .csv';
    if ((results?.size || 0) + (curriculum?.size || 0) > limit) e.size = `Файлы больше лимита ${fmtBytes(limit)}`;
    return e;
  }, [meta, results, curriculum, limit]);
  const hasErrors = Object.keys(errors).length > 0;

  const checkFresh = (check.kind === 'valid' || check.kind === 'invalid') && check.signature === signature;
  const checkStale = (check.kind === 'valid' || check.kind === 'invalid') && check.signature !== signature;
  const canImport = allowed && check.kind === 'valid' && checkFresh && !importing;

  const runCheck = async () => {
    setTouched(true);
    setImportError(null);
    if (hasErrors || !results || !curriculum) return;
    setCheck({ kind: 'checking' });
    const sig = signature;
    try {
      const res = await api.importDataset({ results, curriculum }, cleanMeta(meta), true);
      setCheck({ kind: 'valid', result: res, signature: sig });
    } catch (e) {
      setCheck({ kind: 'invalid', error: e, signature: sig });
    }
  };

  const runImport = async () => {
    if (!canImport || !results || !curriculum) return;
    setImporting(true);
    setImportError(null);
    try {
      const res = await api.importDataset({ results, curriculum }, cleanMeta(meta), false);
      if (!res.dataset_id) throw new Error('Сервер не вернул ID набора');
      if (res.dataset) setCurrent(datasetToCurrent(res.dataset));
      toast({
        tone: 'good',
        title: res.httpStatus === 201 ? 'Набор импортирован' : 'Такой набор уже есть — открыли его',
        message: `${fmtNum(res.counts.results)} записей, ${fmtNum(res.counts.topics)} тем.`,
      });
      onImported();
      navigate(`/datasets/${encodeURIComponent(res.dataset_id)}/overview`);
    } catch (e) {
      setImportError(e);
    } finally {
      setImporting(false);
    }
  };

  const show = (k: keyof typeof errors) => (touched ? errors[k] : undefined);
  const stage = check.kind === 'valid' && checkFresh ? 2 : results && curriculum ? 1 : 0;

  return (
    <section className="card fade-up">
      <div className="card-head">
        <h2>
          <Upload size={18} /> Импорт двух CSV
        </h2>
        <span className="spacer" />
        <div className="check-steps" aria-label="Этапы импорта">
          <span className={`cs ${stage >= 1 ? 'ok' : 'on'}`}>{stage >= 1 ? <CheckCircle2 size={14} /> : '1'} Файлы</span>
          <ChevronRight size={14} />
          <span className={`cs ${stage >= 2 ? 'ok' : stage === 1 ? 'on' : ''}`}>{stage >= 2 ? <CheckCircle2 size={14} /> : '2'} Проверка</span>
          <ChevronRight size={14} />
          <span className={`cs ${stage === 2 ? 'on' : ''}`}>3 Импорт</span>
        </div>
      </div>

      <div className="card-body stack">
        {!allowed && (
          <Banner tone="warning" title="Импорт отключён на этом стенде">
            Сервер работает в публичном деморежиме. Используйте «Загрузить демоданные» или запустите сервер локально.
          </Banner>
        )}

        <div className="grid-2" style={{ gap: 12 }}>
          <div className="field" style={{ gridColumn: '1 / -1' }}>
            <label className="label" htmlFor="m-name">
              Название набора
            </label>
            <input
              id="m-name"
              className={`input ${show('name') ? 'invalid' : ''}`}
              placeholder="Например: Математика 7 — I четверть"
              value={meta.name}
              maxLength={120}
              onChange={(e) => setMeta({ ...meta, name: e.target.value })}
            />
            {show('name') && <span className="field-error">{show('name')}</span>}
          </div>
          <div className="field">
            <label className="label" htmlFor="m-subject">
              Предмет
            </label>
            <input
              id="m-subject"
              className={`input ${show('subject') ? 'invalid' : ''}`}
              value={meta.subject}
              maxLength={120}
              onChange={(e) => setMeta({ ...meta, subject: e.target.value })}
            />
            {show('subject') && <span className="field-error">{show('subject')}</span>}
          </div>
          <div className="field">
            <label className="label" htmlFor="m-grade">
              Параллель
            </label>
            <select id="m-grade" className="select" value={meta.grade} onChange={(e) => setMeta({ ...meta, grade: Number(e.target.value) })}>
              {Array.from({ length: 12 }, (_, i) => i + 1).map((g) => (
                <option key={g} value={g}>
                  {g} класс
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label className="label" htmlFor="m-start">
              Начало периода
            </label>
            <input
              id="m-start"
              type="date"
              className={`input ${show('period_start') ? 'invalid' : ''}`}
              value={meta.period_start}
              onChange={(e) => setMeta({ ...meta, period_start: e.target.value })}
            />
            {show('period_start') && <span className="field-error">{show('period_start')}</span>}
          </div>
          <div className="field">
            <label className="label" htmlFor="m-end">
              Конец периода
            </label>
            <input
              id="m-end"
              type="date"
              className={`input ${show('period_end') ? 'invalid' : ''}`}
              value={meta.period_end}
              onChange={(e) => setMeta({ ...meta, period_end: e.target.value })}
            />
            {show('period_end') && <span className="field-error">{show('period_end')}</span>}
          </div>
        </div>

        <div className="grid-2" style={{ gap: 12 }}>
          <DropZone
            title="results.csv"
            subtitle="Результаты тестов: ученик × тема × этап"
            file={results}
            onFile={setResults}
            error={show('results')}
            template={api.templateUrl('results')}
            disabled={!allowed}
          />
          <DropZone
            title="curriculum.csv"
            subtitle="Учебный план: часы, границы, важность"
            file={curriculum}
            onFile={setCurriculum}
            error={show('curriculum')}
            template={api.templateUrl('curriculum')}
            disabled={!allowed}
          />
        </div>
        {show('size') && <span className="field-error">{show('size')}</span>}
        <p className="tiny muted">
          UTF-8, разделитель — запятая, дробная часть — точка. ФИО и другие прямые идентификаторы не нужны: используйте условные ID.
        </p>

        {checkStale && (
          <Banner tone="warning" title="Параметры или файлы изменились">
            Результат проверки относится к прежним данным. Нажмите «Проверить» ещё раз.
          </Banner>
        )}

        {check.kind === 'invalid' && checkFresh && <ImportErrors error={check.error} />}
        {check.kind === 'valid' && checkFresh && <ImportPreview result={check.result} />}
        {importError != null && <ImportErrors error={importError} title="Сервер не сохранил набор" />}
      </div>

      <div className="card-foot">
        <Button
          variant={check.kind === 'valid' && checkFresh ? 'default' : 'primary'}
          icon={<ShieldCheck size={16} />}
          loading={check.kind === 'checking'}
          disabled={!allowed || importing}
          onClick={runCheck}
        >
          Проверить
        </Button>
        <Button
          variant="primary"
          icon={<UploadCloud size={16} />}
          disabled={!canImport}
          loading={importing}
          onClick={runImport}
          title={canImport ? 'Сохранить набор на сервере' : 'Доступно после успешной проверки'}
        >
          Импортировать
        </Button>
        <span className="small muted">
          {check.kind === 'valid' && checkFresh
            ? 'Проверка пройдена — можно импортировать. Сервер проверит файлы ещё раз.'
            : '«Импортировать» станет доступно после успешной проверки.'}
        </span>
      </div>
    </section>
  );
}

function cleanMeta(m: DatasetMetadata): DatasetMetadata {
  return { ...m, name: m.name.trim(), subject: m.subject.trim() };
}

function fileSig(f: File | null) {
  return f ? `${f.name}:${f.size}:${f.lastModified}` : '-';
}

function DropZone({
  title,
  subtitle,
  file,
  onFile,
  error,
  template,
  disabled,
}: {
  title: string;
  subtitle: string;
  file: File | null;
  onFile: (f: File | null) => void;
  error?: string;
  template: string;
  disabled?: boolean;
}) {
  const [drag, setDrag] = useState(false);
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    if (disabled) return;
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  };
  return (
    <div className="stack-sm">
      <div
        className={`dropzone ${drag ? 'drag' : ''} ${file ? 'filled' : ''} ${error ? 'bad' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        aria-disabled={disabled}
      >
        <input
          type="file"
          accept=".csv,text/csv"
          disabled={disabled}
          aria-label={`Выбрать ${title}`}
          onChange={(e) => {
            onFile(e.target.files?.[0] || null);
            e.target.value = '';
          }}
        />
        <span className="dz-icon">{file ? <CheckCircle2 size={22} /> : <FileSpreadsheet size={22} />}</span>
        <span className="dz-title">{file ? file.name : title}</span>
        <span className="dz-sub">{file ? `${fmtBytes(file.size)} · нажмите, чтобы заменить` : `${subtitle} · перетащите или выберите`}</span>
        {file && (
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            style={{ position: 'relative', zIndex: 2 }}
            onClick={(e) => {
              e.stopPropagation();
              onFile(null);
            }}
          >
            <X size={14} /> Убрать
          </button>
        )}
      </div>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        {error ? <span className="field-error">{error}</span> : <span />}
        <a className="small row" href={template} download>
          <Download size={13} /> Шаблон {title}
        </a>
      </div>
    </div>
  );
}

function ImportErrors({ error, title }: { error: unknown; title?: string }) {
  if (!(error instanceof ApiError) || error.isNetwork) {
    const t = errorText(error);
    return (
      <Banner tone="critical" title={title || t.title}>
        {t.message}
      </Banner>
    );
  }
  const details = error.details;
  return (
    <div className="card fade-up" style={{ borderColor: 'var(--critical)', boxShadow: 'none' }}>
      <div className="card-head" style={{ background: 'var(--critical-bg)', borderRadius: '18px 18px 0 0' }}>
        <h3 style={{ color: 'var(--critical-text)' }}>{title || 'Проверка не пройдена'}</h3>
        <span className="spacer" />
        <Badge tone="critical">
          {fmtNum(error.totalErrors || details.length)} {plural(error.totalErrors || details.length, ['ошибка', 'ошибки', 'ошибок'])}
        </Badge>
      </div>
      <div style={{ padding: '12px 20px 4px' }} className="small">
        {error.message}
        {/не сохран/i.test(error.message) ? '' : ' Набор не сохранён.'}
      </div>
      {details.length > 0 && (
        <div className="table-wrap" style={{ maxHeight: 300 }}>
          <table className="table table-compact">
            <thead>
              <tr>
                <th>Файл</th>
                <th className="r">Строка</th>
                <th>Поле</th>
                <th>Причина</th>
              </tr>
            </thead>
            <tbody>
              {details.map((d, i) => (
                <tr key={i}>
                  <td className="mono">{d.file || '—'}</td>
                  <td className="r num">{d.row ?? '—'}</td>
                  <td className="mono">{d.field || '—'}</td>
                  <td>{d.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {error.totalErrors > details.length && (
        <div className="small muted" style={{ padding: '8px 20px 14px' }}>
          Показаны первые {details.length} из {error.totalErrors}. Исправьте их и проверьте снова.
        </div>
      )}
    </div>
  );
}

function ImportPreview({ result }: { result: ImportResponse }) {
  const [tab, setTab] = useState<'results' | 'curriculum'>('results');
  const c = result.counts;
  const items: [string, number][] = [
    ['Ученики', c.students],
    ['Классы', c.classes],
    ['Темы', c.topics],
    ['Учебники', c.textbooks],
    ['Записи', c.results],
    ['До (pre)', c.pre],
    ['После (post)', c.post],
    ['Пары до/после', c.pairs],
  ];
  return (
    <div className="stack-sm fade-up">
      <Banner tone="good" title="Проверка пройдена">
        Файлы корректны. Ниже — сводка и первые строки. Если всё верно, нажмите «Импортировать».
      </Banner>
      <div className="counts-strip">
        {items.map(([k, v]) => (
          <div className="stat" key={k}>
            <div className="k">{k}</div>
            <div className="v">{fmtNum(v)}</div>
          </div>
        ))}
      </div>
      {result.warnings.length > 0 && (
        <Banner tone="warning" title="Предупреждения">
          <ul>
            {result.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </Banner>
      )}
      <div className="card" style={{ boxShadow: 'none' }}>
        <div className="card-head" style={{ padding: '10px 16px' }}>
          <div className="segmented" role="tablist">
            <button role="tab" aria-selected={tab === 'results'} className={tab === 'results' ? 'on' : ''} onClick={() => setTab('results')}>
              results.csv · первые {Math.min(10, result.preview.results.length)}
            </button>
            <button
              role="tab"
              aria-selected={tab === 'curriculum'}
              className={tab === 'curriculum' ? 'on' : ''}
              onClick={() => setTab('curriculum')}
            >
              curriculum.csv · {Math.min(10, result.preview.curriculum.length)}
            </button>
          </div>
        </div>
        <div className="table-wrap" style={{ maxHeight: 340 }}>
          {tab === 'results' ? (
            <table className="table table-compact">
              <thead>
                <tr>
                  <th>student_id</th>
                  <th>class_id</th>
                  <th>textbook_id</th>
                  <th>topic_id</th>
                  <th>version</th>
                  <th>stage</th>
                  <th className="r">score</th>
                  <th className="r">max</th>
                  <th>tested_at</th>
                </tr>
              </thead>
              <tbody>
                {result.preview.results.slice(0, 10).map((r, i) => (
                  <tr key={i}>
                    <td className="mono">{r.student_id}</td>
                    <td>{r.class_id}</td>
                    <td>{r.textbook_id}</td>
                    <td className="mono">{r.topic_id}</td>
                    <td>{r.test_version}</td>
                    <td>
                      <Badge tone={r.stage === 'pre' ? 'info' : 'accent'}>{r.stage}</Badge>
                    </td>
                    <td className="r num">{r.score ?? '—'}</td>
                    <td className="r num">{r.max_score ?? '—'}</td>
                    <td className="num">{r.tested_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <table className="table table-compact">
              <thead>
                <tr>
                  <th className="r">#</th>
                  <th>topic_id</th>
                  <th>Тема</th>
                  <th className="r">Часы</th>
                  <th className="r">Мин</th>
                  <th className="r">Макс</th>
                  <th className="r">Важность</th>
                  <th>Блок</th>
                </tr>
              </thead>
              <tbody>
                {result.preview.curriculum.slice(0, 10).map((r) => (
                  <tr key={r.topic_id}>
                    <td className="r num">{r.topic_order}</td>
                    <td className="mono">{r.topic_id}</td>
                    <td>{r.topic_name}</td>
                    <td className="r num">{r.current_hours}</td>
                    <td className="r num">{r.min_hours}</td>
                    <td className="r num">{r.max_hours}</td>
                    <td className="r num">{r.importance}</td>
                    <td>{r.is_locked ? <Lock size={14} aria-label="заблокирована" /> : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
