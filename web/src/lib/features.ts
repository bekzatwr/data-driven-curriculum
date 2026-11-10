import type { FeatureFlag } from '../api/types';
import { useApp } from '../state/app';

/**
 * Флаги возможностей сервера (GET /api/capabilities). Сервер — источник истины:
 * интерфейс ничего не разрешает сам.
 *
 * - `off(f)` — функция явно запрещена сервером (например, публичный read-only режим).
 *   Для P0-функций старых серверов без флага считаем «не запрещено».
 * - `on(f)` — функция явно включена. P1-модули (ИИ, учителя, план на период)
 *   показываем только при явном true.
 */
export function useFeatures() {
  const { capabilities } = useApp();
  const f = capabilities?.features;
  const on = (name: FeatureFlag) => f?.[name] === true;
  const off = (name: FeatureFlag) => f?.[name] === false;
  return {
    loaded: !!capabilities,
    readOnly: capabilities?.mode === 'read_only_demo',
    on,
    off,
  };
}

/**
 * Серверный модуль нагрузки учителей (GET /api/datasets/{id}/teachers, владелец — Тони)
 * ещё не подключён. Расчёт в браузере (lib/teachers.ts) — прототип и не показывается.
 * Включить вместе с серверным контрактом.
 */
export const TEACHERS_SERVER_CONNECTED = false;

export function teachersModuleReady(features: ReturnType<typeof useFeatures>) {
  return TEACHERS_SERVER_CONNECTED && features.on('teachers_api');
}

/** Короткое объяснение, почему действие недоступно. */
export function readOnlyReason(readOnly: boolean) {
  return readOnly
    ? 'Публичный демо-режим: сервер разрешает только просмотр. Сохранение доступно в локальном режиме.'
    : 'Сервер отключил это действие.';
}
