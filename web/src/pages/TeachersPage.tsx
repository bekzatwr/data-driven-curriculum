import { AlertTriangle, BookOpen, Clock3, GraduationCap, School, Users } from 'lucide-react';
import { api } from '../api/client';
import type { TeachersResponse } from '../api/types';
import { FilterBar } from '../components/FilterBar';
import { Badge, Banner, Button, CountUp, DemoBadge, EmptyState, ErrorState, InfoPopover, LoadingBlock, Refreshing } from '../components/ui';
import { fmtNum, fmtOne, fmtPct, fmtPp, fmtShare, isNum, plural } from '../lib/format';
import { teachersModuleReady, useFeatures } from '../lib/features';
import { useAsync } from '../lib/useAsync';
import { useDataset } from '../state/dataset';

/**
 * Нагрузка учителей. Всё считает сервер (модуль Тони, GET /api/datasets/{id}/teachers)
 * по всем записям набора; страница только показывает готовые числа.
 * Баллы и прирост — контекст для планирования поддержки, не рейтинг учителей.
 */
export function TeachersPage() {
  const features = useFeatures();
  const { datasetId, dataset, shared, resetShared } = useDataset();
  const ready = teachersModuleReady(features);
  const af = { class_ids: shared.classIds, textbook_ids: shared.textbookIds, test_version: shared.testVersion };
  const state = useAsync(ready ? (s) => api.teachers(datasetId, af, s) : null, `teachers|${datasetId}|${JSON.stringify(af)}|${ready}`);
  const data = state.data;

  return (
    <div className="stack" style={{ gap: 0 }}>
      <div className="page-head fade-up">
        <div style={{ flex: 1, minWidth: 280 }}>
          <div className="eyebrow">Школа · Нагрузка учителей</div>
          <h1>Сколько учеников и часов на учителя</h1>
          <p>
            {dataset.metadata.subject}, {dataset.metadata.grade} класс. Это наблюдаемая нагрузка по одному предмету — не полная ставка и не оценка работы
            учителя. {dataset.source_type === 'demo' && <DemoBadge />}
          </p>
        </div>
      </div>

      {!ready ? (
        <div className="card">
          <EmptyState title="Раздел не подключён на этом сервере" icon={<GraduationCap size={26} />}>
            Сервер не сообщил о модуле нагрузки учителей. Остальные разделы работают как обычно.
          </EmptyState>
        </div>
      ) : (
        <>
          <FilterBar />
          {state.error != null && !data && (
            <div className="card">
              <ErrorState error={state.error} onRetry={state.reload} />
            </div>
          )}
          {state.error != null && data && (
            <div style={{ marginBottom: 16 }}>
              <Banner tone="critical" title="Не удалось применить фильтры" action={<Button size="sm" onClick={state.reload}>Повторить</Button>}>
                Ниже показаны данные для предыдущих фильтров.
              </Banner>
            </div>
          )}
          {state.loading && (
            <div className="card">
              <LoadingBlock rows={6} label="Считаем нагрузку…" />
            </div>
          )}
          {data && (
            <Refreshing active={state.refreshing}>
              {data.teachers.length === 0 ? (
                <div className="card">
                  <EmptyState
                    title="В выбранной выборке нет записей"
                    icon={<GraduationCap size={26} />}
                    action={
                      <Button variant="primary" onClick={resetShared}>
                        Сбросить фильтры
                      </Button>
                    }
                  />
                </div>
              ) : (
                <TeachersBody data={data} />
              )}
            </Refreshing>
          )}
        </>
      )}
    </div>
  );
}

function TeachersBody({ data }: { data: TeachersResponse }) {
  const t = data.total;
  const known = data.teachers.filter((x) => !x.is_missing_teacher);
  const avgStudents = t.students_per_teacher;
  const maxStudents = Math.max(1, ...data.teachers.map((x) => x.students));
  const range = known.length ? [Math.min(...known.map((x) => x.students)), Math.max(...known.map((x) => x.students))] : null;
  const attr = t.teacher_attribution;
  const partial = isNum(attr.fully_attributed_student_share) && attr.fully_attributed_student_share < 1;

  return (
    <div className="stack">
      {partial && (
        <Banner tone="warning" title="Не у всех учеников указан учитель">
          Учитель указан во всех записях у {fmtNum(attr.fully_attributed_students)} из {fmtNum(t.students)}{' '}
          {plural(t.students, ['ученика', 'учеников', 'учеников'])} ({fmtShare(attr.fully_attributed_student_share)}). Записи без учителя (
          {fmtNum(data.missing_teacher_rows)}) собраны в строку «Учитель не указан» и не считаются отдельным учителем.
        </Banner>
      )}

      <div className="kpi-strip three fade-up">
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Учителей</span>
            <span className="kpi-icon">
              <GraduationCap size={15} />
            </span>
          </div>
          <div className="kpi-value">
            <CountUp value={t.teachers} format={(v) => fmtNum(Math.round(v))} />
          </div>
          <div className="kpi-sub">
            {fmtNum(t.students)} {plural(t.students, ['ученик', 'ученика', 'учеников'])} · {fmtNum(t.classes)} кл.
          </div>
        </div>
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label row" style={{ gap: 4 }}>
              Учеников на учителя
              <InfoPopover iconOnly label="Как рассчитано: учеников на учителя">
                <p>{data.definitions.students_per_teacher || 'Уникальные ученики ÷ число известных учителей.'}</p>
              </InfoPopover>
            </span>
            <span className="kpi-icon">
              <Users size={15} />
            </span>
          </div>
          <div className="kpi-value">{isNum(t.students_per_teacher) ? <CountUp value={t.students_per_teacher} format={fmtOne} /> : '—'}</div>
          <div className="kpi-sub">{range ? (range[0] === range[1] ? `у каждого учителя ${range[0]}` : `от ${range[0]} до ${range[1]} у разных учителей`) : 'нет известных учителей'}</div>
        </div>
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label row" style={{ gap: 4 }}>
              Часов на учителя
              <InfoPopover iconOnly label="Как рассчитано: часы" align="right">
                <p>{data.definitions.hours_per_teacher || 'Связи учитель–класс × часы плана на класс ÷ число учителей.'}</p>
              </InfoPopover>
            </span>
            <span className="kpi-icon">
              <Clock3 size={15} />
            </span>
          </div>
          <div className="kpi-value">
            {isNum(t.hours_per_teacher) ? <CountUp value={t.hours_per_teacher} format={fmtOne} /> : '—'}
            {isNum(t.hours_per_teacher) && <span className="unit"> ч</span>}
          </div>
          <div className="kpi-sub">{fmtNum(data.hours_per_class)} ч на один класс по учебному плану</div>
        </div>
      </div>

      {data.schools.length > 1 && (
        <section className="card">
          <div className="card-head">
            <h2>
              <School size={16} /> По школам
            </h2>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Школа</th>
                  <th className="r">Учителей</th>
                  <th className="r">Учеников</th>
                  <th className="r">Учеников на учителя</th>
                  <th className="r">Часов на учителя</th>
                </tr>
              </thead>
              <tbody>
                {data.schools.map((s) => (
                  <tr key={s.school_id}>
                    <td className="strong">{s.school_id}</td>
                    <td className="r num">{fmtNum(s.teachers)}</td>
                    <td className="r num">{fmtNum(s.students)}</td>
                    <td className="r num strong">{isNum(s.students_per_teacher) ? fmtOne(s.students_per_teacher) : '—'}</td>
                    <td className="r num">{isNum(s.hours_per_teacher) ? fmtOne(s.hours_per_teacher) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="card fade-up-2">
        <div className="card-head">
          <h2>
            <GraduationCap size={16} /> Учителя
          </h2>
          {isNum(avgStudents) && <span className="small muted">черта на шкале — среднее ({fmtOne(avgStudents)} уч.)</span>}
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Учитель</th>
                <th>Классы</th>
                <th>Ученики</th>
                <th className="r">Часов</th>
                <th>Учебники</th>
                <th className="r">Итоговый средний</th>
                <th className="r">Прирост</th>
              </tr>
            </thead>
            <tbody>
              {data.teachers.map((x) => {
                // Флаг перегрузки — только для известных учителей и только по числу учеников.
                const high = !x.is_missing_teacher && isNum(avgStudents) && avgStudents > 0 && x.students > avgStudents * 1.2;
                return (
                  <tr key={JSON.stringify([x.school_id, x.teacher_id, x.is_missing_teacher])} className={x.is_missing_teacher ? 'row-locked' : undefined}>
                    <td>
                      <div className="cell-topic">
                        <span className="t">{x.is_missing_teacher ? 'Учитель не указан' : x.teacher_id}</span>
                        <span className="s">
                          {x.school_id}
                          {x.warnings.length > 0 && (
                            <span className="row" style={{ gap: 3, display: 'inline-flex', marginLeft: 6 }} title={x.warnings.join('\n')}>
                              <AlertTriangle size={11} /> {x.warnings.length} {plural(x.warnings.length, ['оговорка', 'оговорки', 'оговорок'])}
                            </span>
                          )}
                        </span>
                      </div>
                    </td>
                    <td>
                      <div className="class-tags">
                        {x.class_ids.map((c) => (
                          <span key={c}>{c}</span>
                        ))}
                      </div>
                    </td>
                    <td style={{ minWidth: 170 }}>
                      <div className="row" style={{ gap: 10 }}>
                        <span className="num strong" style={{ width: 28, textAlign: 'right' }}>
                          {fmtNum(x.students)}
                        </span>
                        <div className={`load-bar ${high ? 'high' : ''}`} style={{ flex: 1 }}>
                          <span style={{ width: `${(x.students / maxStudents) * 100}%` }} />
                          {isNum(avgStudents) && avgStudents > 0 && <i className="avg" style={{ left: `${(avgStudents / maxStudents) * 100}%` }} />}
                        </div>
                      </div>
                      {high && (
                        <div style={{ marginTop: 4 }}>
                          <Badge tone="serious">более чем на 20% выше средней нагрузки</Badge>
                        </div>
                      )}
                    </td>
                    <td className="r num strong">{x.is_missing_teacher ? '—' : fmtNum(x.upcoming_hours)}</td>
                    <td>
                      <div className="class-tags">
                        {x.textbooks.map((b) => (
                          <span key={b}>
                            <BookOpen size={11} style={{ marginRight: 4 }} />
                            {b}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="r num">{fmtPct(x.mean_post_pct)}</td>
                    <td className="r num" title={isNum(x.mean_gain_pp) ? `${fmtPct(x.mean_pre_paired_pct)} → ${fmtPct(x.mean_post_paired_pct)}, пар: ${fmtNum(x.n_pairs)}` : undefined}>
                      {fmtPp(x.mean_gain_pp)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="card-foot stack-sm" style={{ alignItems: 'flex-start' }}>
          <span className="tiny muted">
            Результаты учеников — для планирования поддержки, а не оценка работы учителя: на них влияют состав класса, учебник и условия.
          </span>
          {data.warnings.map((w, i) => (
            <span key={i} className="tiny muted">
              {w}
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}
