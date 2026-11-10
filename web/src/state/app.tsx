import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api } from '../api/client';
import type { Capabilities, Dataset } from '../api/types';
import { readJson, writeJson } from '../lib/storage';

export interface CurrentDataset {
  id: string;
  name: string;
  isDemo: boolean;
}

interface AppState {
  current: CurrentDataset | null;
  setCurrent: (d: CurrentDataset | null) => void;
  lastPlanId: string | null;
  setLastPlanId: (id: string | null) => void;
  capabilities: Capabilities | null;
  apiOnline: boolean | null;
  recheckApi: () => void;
}

const Ctx = createContext<AppState | null>(null);

export function datasetToCurrent(d: Dataset): CurrentDataset {
  return { id: d.id, name: d.metadata.name, isDemo: d.source_type === 'demo' };
}

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [current, setCurrentState] = useState<CurrentDataset | null>(() => readJson('ddc.current', null));
  const [lastPlanId, setLastPlanIdState] = useState<string | null>(() => readJson('ddc.lastPlan', null));
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [nonce, setNonce] = useState(0);

  const setCurrent = useCallback((d: CurrentDataset | null) => {
    setCurrentState((prev) => (prev?.id === d?.id && prev?.name === d?.name && prev?.isDemo === d?.isDemo ? prev : d));
    writeJson('ddc.current', d);
  }, []);
  const setLastPlanId = useCallback((id: string | null) => {
    setLastPlanIdState(id);
    writeJson('ddc.lastPlan', id);
  }, []);

  useEffect(() => {
    let alive = true;
    const check = () =>
      api
        .health()
        .then(() => alive && setApiOnline(true))
        .catch(() => alive && setApiOnline(false));
    check();
    api
      .capabilities()
      .then((c) => alive && setCapabilities(c))
      .catch(() => {});
    const t = window.setInterval(check, 30000);
    return () => {
      alive = false;
      window.clearInterval(t);
    };
  }, [nonce]);

  const value = useMemo(
    () => ({
      current,
      setCurrent,
      lastPlanId,
      setLastPlanId,
      capabilities,
      apiOnline,
      recheckApi: () => setNonce((n) => n + 1),
    }),
    [current, setCurrent, lastPlanId, setLastPlanId, capabilities, apiOnline],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp() {
  const v = useContext(Ctx);
  if (!v) throw new Error('useApp outside provider');
  return v;
}
