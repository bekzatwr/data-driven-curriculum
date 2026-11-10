import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { FlaskConical, SearchX, Upload } from 'lucide-react';
import { api, ApiError } from '../api/client';
import { datasetToCurrent, useApp } from '../state/app';
import { Button, errorText } from './ui';

export function isNotFound(error: unknown) {
  return error instanceof ApiError && error.status === 404;
}

/**
 * 404 на наборе или плане. На бесплатном хостинге без диска база живёт до перезапуска сервера,
 * поэтому старые ссылки «теряются»: объясняем это и даём за один клик пересоздать демонабор.
 */
export function MissingData({ kind, staleId }: { kind: 'dataset' | 'plan'; staleId: string }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { current, setCurrent, lastPlanId, setLastPlanId } = useApp();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Не держим в боковой панели ссылки на то, чего больше нет.
  useEffect(() => {
    if (kind === 'dataset' && current?.id === staleId) setCurrent(null);
    if (kind === 'plan' && lastPlanId === staleId) setLastPlanId(null);
  }, [kind, staleId, current?.id, lastPlanId, setCurrent, setLastPlanId]);

  const recreate = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.createDemo();
      if (!res.dataset_id) throw new Error('Сервер не вернул ID набора');
      if (res.dataset) setCurrent(datasetToCurrent(res.dataset));
      // Остаёмся на том же экране (обзор, сравнение, план, учителя), но уже с новым набором.
      const sub = kind === 'dataset' ? pathname.split('/').slice(3).join('/') : 'plan';
      navigate(`/datasets/${encodeURIComponent(res.dataset_id)}/${sub || 'overview'}`, { replace: true });
    } catch (e) {
      setError(errorText(e).message);
      setBusy(false);
    }
  };

  return (
    <div className="state" role="alert">
      <div className="state-icon">
        <SearchX size={26} />
      </div>
      <h3>{kind === 'dataset' ? 'Набор данных не найден' : 'План не найден'}</h3>
      <p>
        Скорее всего, сервер перезапускался: на бесплатном хостинге данные хранятся только до перезапуска.
        {kind === 'dataset'
          ? ' Демонабор можно создать заново за пару секунд, свои CSV — загрузить ещё раз.'
          : ' Создайте демонабор заново и пересчитайте план — это займёт меньше минуты.'}
      </p>
      {error && <p className="small text-2">{error}</p>}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center', marginTop: 6 }}>
        <Button variant="primary" icon={<FlaskConical size={16} />} loading={busy} onClick={recreate}>
          Создать демо заново
        </Button>
        <Button icon={<Upload size={16} />} onClick={() => navigate('/')} disabled={busy}>
          Загрузить CSV
        </Button>
      </div>
    </div>
  );
}
