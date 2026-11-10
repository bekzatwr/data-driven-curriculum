import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Outlet, useParams } from 'react-router-dom';
import { api } from '../api/client';
import type { Dataset, Filters } from '../api/types';
import { isNotFound, MissingData } from '../components/MissingData';
import { ErrorState, LoadingBlock } from '../components/ui';
import { readJson, writeJson } from '../lib/storage';
import { useAsync } from '../lib/useAsync';
import { datasetToCurrent, useApp } from './app';

/** Фильтры аналитики общие для обзора и сравнения (ТЗ: сохраняются при переходе). */
export interface SharedFilters {
  classIds: string[];
  textbookIds: string[];
  testVersion: string | null;
}

export interface ComparisonSelection {
  topicId: string | null;
  textbookA: string | null;
  textbookB: string | null;
}

interface DatasetCtx {
  datasetId: string;
  dataset: Dataset;
  filters: Filters;
  shared: SharedFilters;
  setShared: (f: SharedFilters) => void;
  resetShared: () => void;
  comparison: ComparisonSelection;
  setComparison: (c: ComparisonSelection) => void;
  topicName: (id: string) => string;
  /** Есть ли у какой-либо темы больше одной версии теста. */
  hasMultipleVersions: boolean;
  allVersions: string[];
}

const Ctx = createContext<DatasetCtx | null>(null);

const EMPTY: SharedFilters = { classIds: [], textbookIds: [], testVersion: null };

export function DatasetScope() {
  const { datasetId = '' } = useParams();
  const { setCurrent } = useApp();
  const state = useAsync(
    (signal) => Promise.all([api.getDataset(datasetId, signal), api.filters(datasetId, signal)]),
    datasetId,
  );

  useEffect(() => {
    if (state.data) setCurrent(datasetToCurrent(state.data[0]));
  }, [state.data, setCurrent]);

  if (state.error) {
    return (
      <div className="card">
        {isNotFound(state.error) ? (
          <MissingData kind="dataset" staleId={datasetId} />
        ) : (
          <ErrorState error={state.error} onRetry={state.reload} />
        )}
      </div>
    );
  }
  if (!state.data || state.data[0].id !== datasetId) {
    return (
      <div className="card">
        <LoadingBlock rows={6} label="Загружаем набор данных…" />
      </div>
    );
  }
  return (
    <DatasetProvider dataset={state.data[0]} filters={state.data[1]}>
      <Outlet />
    </DatasetProvider>
  );
}

function DatasetProvider({ dataset, filters, children }: { dataset: Dataset; filters: Filters; children: ReactNode }) {
  const id = dataset.id;
  const [shared, setSharedState] = useState<SharedFilters>(() => sanitize(readJson(`ddc.filters.${id}`, EMPTY, 'session'), filters));
  const [comparison, setComparisonState] = useState<ComparisonSelection>(() =>
    readJson(`ddc.cmp.${id}`, { topicId: null, textbookA: null, textbookB: null }, 'session'),
  );

  const setShared = useCallback(
    (f: SharedFilters) => {
      setSharedState(f);
      writeJson(`ddc.filters.${id}`, f, 'session');
    },
    [id],
  );
  const setComparison = useCallback(
    (c: ComparisonSelection) => {
      setComparisonState(c);
      writeJson(`ddc.cmp.${id}`, c, 'session');
    },
    [id],
  );

  const value = useMemo<DatasetCtx>(() => {
    const names = new Map(filters.topics.map((t) => [t.topic_id, t.topic_name]));
    const versions = Array.from(new Set(filters.test_versions.map((v) => v.test_version))).sort();
    const perTopic = new Map<string, number>();
    filters.test_versions.forEach((v) => perTopic.set(v.topic_id, (perTopic.get(v.topic_id) || 0) + 1));
    return {
      datasetId: id,
      dataset,
      filters,
      shared,
      setShared,
      resetShared: () => setShared(EMPTY),
      comparison,
      setComparison,
      topicName: (tid: string) => names.get(tid) || tid,
      hasMultipleVersions: versions.length > 1 || Array.from(perTopic.values()).some((n) => n > 1),
      allVersions: versions,
    };
  }, [id, dataset, filters, shared, setShared, comparison, setComparison]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

function sanitize(f: SharedFilters, filters: Filters): SharedFilters {
  const classes = new Set(filters.classes.map((c) => c.id));
  const books = new Set(filters.textbooks.map((t) => t.id));
  const versions = new Set(filters.test_versions.map((v) => v.test_version));
  return {
    classIds: (f.classIds || []).filter((c) => classes.has(c)),
    textbookIds: (f.textbookIds || []).filter((t) => books.has(t)),
    testVersion: f.testVersion && versions.has(f.testVersion) ? f.testVersion : null,
  };
}

export function useDataset() {
  const v = useContext(Ctx);
  if (!v) throw new Error('useDataset outside DatasetScope');
  return v;
}
