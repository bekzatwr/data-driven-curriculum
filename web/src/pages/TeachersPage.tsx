import { useMemo } from 'react';
import { BookOpen, Clock3, GraduationCap, School, Users } from 'lucide-react';
import { api } from '../api/client';
import { AiExplain } from '../components/AiExplain';
import { Badge, Banner, CountUp, DemoBadge, EmptyState, ErrorState, InfoPopover, LoadingBlock } from '../components/ui';
import { fmtNum, fmtOne, fmtPct, fmtPp, isNum, plural } from '../lib/format';
import { computeTeachers } from '../lib/teachers';
import { useAsync } from '../lib/useAsync';
import { useDataset } from '../state/dataset';

export function TeachersPage() {
  const { datasetId, dataset, filters } = useDataset();
  const state = useAsync((s) => api.allResults(datasetId, s), `teachers|${datasetId}`);
  const summary = useMemo(() => (state.data ? computeTeachers(state.data, filters.topics) : null), [state.data, filters.topics]);

  return (
    <div className="stack" style={{ gap: 0 }}>
      <div className="page-head fade-up">
        <div style={{ flex: 1, minWidth: 280 }}>
          <div className="eyebrow">Школа · Нагрузка учителей</div>
          <h1>Сколько учеников и часов на учителя</h1>
          <p>
            Считается по загруженному набору: {dataset.metadata.subject}, {dataset.metadata.grade} класс. Это нагрузка в рамках этого предмета и
            параллели, а не полная ставка учителя. {dataset.source_type === 'demo' && <DemoBadge />}
          </p>
        </div>
      </div>

      {state.error != null && (
        <div className="card">
          <ErrorState error={state.error} onRetry={state.reload} />
        </div>
      )}
      {state.loading && (
        <div className="card">
          <LoadingBlock rows={6} label="Считаем нагрузку…" />
        </div>
      )}
      {summary && summary.teachers.length === 0 && (
        <div className="card">
          <EmptyState title="В наборе нет записей об учителях" icon={<GraduationCap size={26} />} />
        </div>
      )}
      {summary && summary.teachers.length > 0 && <TeachersBody summary={summary} datasetId={datasetId} isDemo={dataset.source_type === 'demo'} />}
    </div>
  );
}

function TeachersBody({ summary, datasetId, isDemo }: { summary: ReturnType<typeof computeTeachers>; datasetId: string; isDemo: boolean }) {
  const t = summary.total;
  const real = summary.teachers.filter((x) => x.teacher_id !== 'Не указан');
  const avgStudents = t.students_per_teacher ?? 0;
  const maxStudents = Math.max(1, ...summary.teachers.map((x) => x.students));
  const range = real.length ? [Math.min(...real.map((x) => x.students)), Math.max(...real.map((x) => x.students))] : null;

  return (
    <div className="stack">
      {summary.missing_teacher_rows > 0 && (
        <Banner tone="warning" title="Не у всех записей указан учитель">
          {fmtNum(summary.missing_teacher_rows)} строк без teacher_id собраны в группу «Не указан» и не входят в средние по школе.
        </Banner>
      )}

      <div className="kpi-strip fade-up">
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
                <p>Уникальные ученики набора ÷ уникальные учителя (teacher_id). Ученик одного учителя по предмету считается один раз.</p>
              </InfoPopover>
            </span>
            <span className="kpi-icon">
              <Users size={15} />
            </span>
          </div>
          <div className="kpi-value">{isNum(t.students_per_teacher) ? <CountUp value={t.students_per_teacher} format={fmtOne} /> : '—'}</div>
          <div className="kpi-sub">{range ? `от ${range[0]} до ${range[1]} у разных учителей` : 'нет данных'}</div>
        </div>
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label">Классов на учителя</span>
            <span className="kpi-icon">
              <School size={15} />
            </span>
          </div>
          <div className="kpi-value">{isNum(t.classes_per_teacher) ? <CountUp value={t.classes_per_teacher} format={fmtOne} /> : '—'}</div>
          <div className="kpi-sub">в среднем по набору</div>
        </div>
        <div className="kpi">
          <div className="kpi-top">
            <span className="kpi-label row" style={{ gap: 4 }}>
              Часов на учителя
              <InfoPopover iconOnly label="Как рассчитано: часы" align="right">
                <p>
                  Предстоящие часы по учебному плану: число классов учителя × {summary.hours_per_class} ч (сумма current_hours всех тем плана на один
                  класс).
                </p>
              </InfoPopover>
            </span>
            <span className="kpi-icon">
              <Clock3 size={15} />
            </span>
          </div>
          <div className="kpi-value">
            {isNum(t.hours_per_teacher) ? <CountUp value={t.hours_per_teacher} format={fmtOne} /> : '—'}
            <span className="unit"> ч</span>
          </div>
          <div className="kpi-sub">{summary.hours_per_class} ч на один класс по плану</div>
        </div>
      </div>

      {summary.schools.length > 1 && (
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
                  <th className="r">Классов</th>
                  <th className="r">Учеников на учителя</th>
                  <th className="r">Часов на учителя</th>
                </tr>
              </thead>
              <tbody>
                {summary.schools.map((s) => (
                  <tr key={s.school_id}>
                    <td className="strong">{s.school_id}</td>
                    <td className="r num">{s.teachers}</td>
                    <td className="r num">{s.students}</td>
                    <td className="r num">{s.classes}</td>
                    <td className="r num strong">{s.students_per_teacher != null ? fmtOne(s.students_per_teacher) : '—'}</td>
                    <td className="r num">{s.hours_per_teacher != null ? fmtOne(s.hours_per_teacher) : '—'}</td>
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
          <span className="small muted">черта на шкале — среднее по набору ({fmtOne(avgStudents)} уч.)</span>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Учитель</th>
                <th>Классы</th>
                <th>Ученики</th>
                <th className="r">Часов (план)</th>
                <th>Учебники</th>
                <th className="r">Итоговый средний</th>
                <th className="r">Прирост</th>
              </tr>
            </thead>
            <tbody>
              {summary.teachers.map((x) => {
                const high = avgStudents > 0 && x.students > avgStudents * 1.2;
                return (
                  <tr key={x.teacher_id}>
                    <td>
                      <div className="cell-topic">
                        <span className="t">{x.teacher_id}</span>
                        <span className="s">{x.school_id}</span>
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
                          {x.students}
                        </span>
                        <div className={`load-bar ${high ? 'high' : ''}`} style={{ flex: 1 }}>
                          <span style={{ width: `${(x.students / maxStudents) * 100}%` }} />
                          {avgStudents > 0 && <i className="avg" style={{ left: `${(avgStudents / maxStudents) * 100}%` }} />}
                        </div>
                      </div>
                      {high && (
                        <div style={{ marginTop: 4 }}>
                          <Badge tone="serious">выше среднего на {Math.round((x.students / avgStudents - 1) * 100)}%</Badge>
                        </div>
                      )}
                    </td>
                    <td className="r num strong">{x.upcoming_hours}</td>
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
                    <td className="r num">{fmtPp(x.mean_gain_pp)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="card-foot">
          <span className="tiny muted">
            Результаты учеников — для планирования поддержки, а не оценка работы учителя: на них влияют состав класса, учебник и условия.
          </span>
        </div>
      </section>

      <AiExplain
        datasetId={datasetId}
        kind="teachers"
        title="ИИ: где перекос нагрузки"
        context={() => ({
          is_demo: isDemo,
          hours_per_class: summary.hours_per_class,
          total: summary.total,
          schools: summary.schools,
          teachers: summary.teachers.map((x) => ({
            teacher_id: x.teacher_id,
            classes: x.class_ids,
            students: x.students,
            upcoming_hours: x.upcoming_hours,
            textbooks: x.textbooks,
          })),
        })}
        saveTo={{ type: 'dataset', id: 'teachers' }}
      />
    </div>
  );
}
