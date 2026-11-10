import type { CurriculumRow, ResultRow } from '../api/types';

export interface TeacherStat {
  teacher_id: string;
  school_id: string;
  class_ids: string[];
  students: number;
  textbooks: string[];
  n_post: number;
  mean_post_pct: number | null;
  n_pairs: number;
  mean_gain_pp: number | null;
  upcoming_hours: number;
}

export interface SchoolStat {
  school_id: string;
  teachers: number;
  students: number;
  classes: number;
  students_per_teacher: number | null;
  classes_per_teacher: number | null;
  hours_per_teacher: number | null;
}

export interface TeachersSummary {
  teachers: TeacherStat[];
  schools: SchoolStat[];
  total: SchoolStat;
  hours_per_class: number;
  missing_teacher_rows: number;
}

const NO_TEACHER = 'Не указан';
const pct = (r: ResultRow) => (r.score != null && r.max_score ? (r.score / r.max_score) * 100 : null);
const avg = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);

/**
 * Нагрузка по загруженному набору (один предмет, одна параллель):
 * предстоящие часы учителя = число его классов × сумма current_hours учебного плана.
 */
export function computeTeachers(rows: ResultRow[], topics: CurriculumRow[]): TeachersSummary {
  const hoursPerClass = topics.reduce((s, t) => s + (t.current_hours || 0), 0);
  type Acc = {
    school: string;
    classes: Set<string>;
    students: Set<string>;
    books: Set<string>;
    post: number[];
    pre: Map<string, number>;
    postByKey: Map<string, number>;
  };
  const map = new Map<string, Acc>();
  let missing = 0;
  for (const r of rows) {
    const tid = (r.teacher_id || '').trim() || NO_TEACHER;
    if (tid === NO_TEACHER) missing++;
    let a = map.get(tid);
    if (!a) {
      a = { school: r.school_id, classes: new Set(), students: new Set(), books: new Set(), post: [], pre: new Map(), postByKey: new Map() };
      map.set(tid, a);
    }
    a.classes.add(r.class_id);
    a.students.add(r.student_id);
    if (r.textbook_id) a.books.add(r.textbook_id);
    const p = pct(r);
    if (p == null) continue;
    const key = `${r.student_id}|${r.topic_id}|${r.test_version}`;
    if (r.stage === 'post') {
      a.post.push(p);
      a.postByKey.set(key, p);
    } else if (r.stage === 'pre') a.pre.set(key, p);
  }

  const teachers: TeacherStat[] = [...map.entries()]
    .map(([tid, a]) => {
      const gains: number[] = [];
      a.postByKey.forEach((post, key) => {
        const pre = a.pre.get(key);
        if (pre != null) gains.push(post - pre);
      });
      const classes = [...a.classes].sort((x, y) => x.localeCompare(y, 'ru', { numeric: true }));
      return {
        teacher_id: tid,
        school_id: a.school,
        class_ids: classes,
        students: a.students.size,
        textbooks: [...a.books].sort(),
        n_post: a.post.length,
        mean_post_pct: avg(a.post),
        n_pairs: gains.length,
        mean_gain_pp: avg(gains),
        upcoming_hours: classes.length * hoursPerClass,
      };
    })
    .sort((x, y) => x.teacher_id.localeCompare(y.teacher_id, 'ru', { numeric: true }));

  const bySchool = new Map<string, { teachers: Set<string>; students: Set<string>; classes: Set<string> }>();
  const all = { teachers: new Set<string>(), students: new Set<string>(), classes: new Set<string>() };
  for (const r of rows) {
    const tid = (r.teacher_id || '').trim() || NO_TEACHER;
    let s = bySchool.get(r.school_id);
    if (!s) {
      s = { teachers: new Set(), students: new Set(), classes: new Set() };
      bySchool.set(r.school_id, s);
    }
    for (const bucket of [s, all]) {
      if (tid !== NO_TEACHER) bucket.teachers.add(tid);
      bucket.students.add(r.student_id);
      bucket.classes.add(`${r.school_id}|${r.class_id}`);
    }
  }
  const stat = (school_id: string, s: { teachers: Set<string>; students: Set<string>; classes: Set<string> }): SchoolStat => {
    const t = s.teachers.size;
    const classLinks = teachers.filter((x) => x.teacher_id !== NO_TEACHER && s.teachers.has(x.teacher_id)).reduce((sum, x) => sum + x.class_ids.length, 0);
    return {
      school_id,
      teachers: t,
      students: s.students.size,
      classes: s.classes.size,
      students_per_teacher: t ? s.students.size / t : null,
      classes_per_teacher: t ? classLinks / t : null,
      hours_per_teacher: t ? (classLinks * hoursPerClass) / t : null,
    };
  };
  return {
    teachers,
    schools: [...bySchool.entries()].map(([id, s]) => stat(id, s)).sort((a, b) => a.school_id.localeCompare(b.school_id)),
    total: stat('Все школы', all),
    hours_per_class: hoursPerClass,
    missing_teacher_rows: missing,
  };
}
