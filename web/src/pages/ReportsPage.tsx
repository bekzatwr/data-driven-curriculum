import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ChevronRight, FileText, Search } from 'lucide-react';
import { Button, DemoBadge, EmptyState } from '../components/ui';
import { fmtDateTimeUtc5, hours as hoursLabel } from '../lib/format';
import { getRecentPlans } from '../lib/storage';

export function ReportsPage() {
  const navigate = useNavigate();
  const [id, setId] = useState('');
  const plans = getRecentPlans();

  return (
    <div className="stack" style={{ maxWidth: 900, margin: '0 auto' }}>
      <div className="page-head fade-up">
        <div>
          <div className="eyebrow">Шаг 5 · Отчёты</div>
          <h1>Сохранённые планы</h1>
          <p>Откройте план по ID или выберите недавний. Отчёт всегда строится из сохранённого снимка.</p>
        </div>
      </div>

      <form
        className="card card-pad row-wrap fade-up"
        onSubmit={(e) => {
          e.preventDefault();
          if (id.trim()) navigate(`/plans/${encodeURIComponent(id.trim())}`);
        }}
      >
        <div className="field" style={{ flex: 1, minWidth: 240 }}>
          <label className="label" htmlFor="plan-id">
            ID плана
          </label>
          <input id="plan-id" className="input mono" placeholder="например, 3f2c…" value={id} onChange={(e) => setId(e.target.value)} />
        </div>
        <Button variant="primary" type="submit" icon={<Search size={16} />} disabled={!id.trim()} style={{ alignSelf: 'flex-end' }}>
          Открыть
        </Button>
      </form>

      <section className="card fade-up-2">
        <div className="card-head">
          <h2>
            <FileText size={18} /> Недавние в этом браузере
          </h2>
        </div>
        {plans.length === 0 ? (
          <EmptyState title="Пока нет сохранённых планов" action={<Link className="btn btn-primary" to="/">Начать с данных</Link>}>
            Рассчитайте и сохраните план на шаге «План часов» — он появится здесь.
          </EmptyState>
        ) : (
          plans.map((p) => (
            <Link key={p.plan_id} to={`/plans/${encodeURIComponent(p.plan_id)}`} className="dataset-item">
              <span className="dataset-icon">
                <FileText size={18} />
              </span>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div className="row" style={{ gap: 6 }}>
                  <span className="name">Класс {p.class_id}</span>
                  {p.is_demo && <DemoBadge compact />}
                  {p.manually_modified && <span className="badge badge-warning">ручные правки</span>}
                </div>
                <div className="small muted">
                  {p.dataset_name} · {hoursLabel(p.total_hours)}
                </div>
                <div className="tiny muted">
                  {fmtDateTimeUtc5(p.created_at)} · <span className="mono">{p.plan_id}</span>
                </div>
              </div>
              <ChevronRight size={18} className="muted" />
            </Link>
          ))
        )}
      </section>
    </div>
  );
}
