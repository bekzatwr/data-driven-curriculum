import { useCallback, useEffect, useRef, useState } from 'react';

export interface AsyncState<T> {
  data: T | undefined;
  error: unknown;
  /** Первая загрузка: данных ещё нет. */
  loading: boolean;
  /** Идёт обновление поверх старых данных (их нужно показывать приглушёнными). */
  refreshing: boolean;
  reload: () => void;
  setData: (d: T) => void;
}

/**
 * Загрузка с отменой устаревших запросов. При смене ключа старые данные остаются на экране,
 * но помечаются флагом refreshing, чтобы не выглядеть как новый результат.
 */
export function useAsync<T>(
  fn: ((signal: AbortSignal) => Promise<T>) | null,
  key: string,
): AsyncState<T> {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState<boolean>(!!fn);
  const [nonce, setNonce] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    const current = fnRef.current;
    if (!current) {
      setPending(false);
      return;
    }
    const controller = new AbortController();
    setPending(true);
    setError(null);
    current(controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return;
        setData(result);
        setPending(false);
      })
      .catch((err) => {
        if (controller.signal.aborted || (err as Error)?.name === 'AbortError') return;
        setError(err);
        setPending(false);
      });
    return () => controller.abort();
  }, [key, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  return {
    data,
    error,
    loading: pending && data === undefined,
    refreshing: pending && data !== undefined,
    reload,
    setData,
  };
}
