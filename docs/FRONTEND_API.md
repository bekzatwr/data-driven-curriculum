# API для Дамира: серверная интеграция P0

Рабочая ветка: `integration/p0-server`. Запуск: Python 3.13, `python scripts/start.py --dev`; API и Swagger — `http://127.0.0.1:8000/docs`. В обычном локальном запуске импорт включён. `compose.yaml` запускает публичный деморежим с отключённым импортом; для двух пользовательских CSV нужен `READ_ONLY_DEMO=false`, как в `deploy/.env.example`.

В React используйте относительный `/api` с dev proxy на `http://127.0.0.1:8000` либо отдельный API base URL. Для прямых запросов разрешены Origins `http://localhost:5173` и `http://127.0.0.1:5173`; дополнительные задаются через `CORS_ORIGINS`. В production общий контейнер раздаёт React и API с одного origin. Frontend в этой ветке не создавался.

## Рабочие маршруты

`{dataset_id}` — UUID из ответа импорта/демо, `{plan_id}` — ID сохранённого плана. `toni-demo`/`aidana-demo` относятся к отдельным демоприложениям, не к общему серверу.

> **Публичный режим, deployment/mobile-public:** сначала читать `/api/capabilities`. При `mode=read_only_demo` функции `csv_import`, `import_preview`, `package_restore`, `plan_save` равны false; API отклоняет запись с 403 `READ_ONLY_DEMO`. `POST /api/datasets/demo` возвращает уже подготовленный при startup набор (200, created=false), без изменения БД. Preview, аналитика и чтение заранее сохранённого демоотчёта доступны. В локальном режиме импорт и save сохраняют прежние контракты. Ссылки подготовленного отчёта владелец получает командой `python deploy/seed_demo_report.py`. [Мобильная приёмка и Retry](MOBILE_ACCEPTANCE.md).

| Метод и путь | Вход | Успех |
| --- | --- | --- |
| GET `/api/health` | — | 200, состояние БД |
| GET `/api/capabilities` | — | 200, доступность модулей и импорта |
| POST `/api/datasets/import?dry_run=true` | FormData: два CSV и metadata | 200, только проверка |
| POST `/api/datasets/import?dry_run=false` | Та же FormData | 201 новый набор; 200 повторный импорт |
| POST `/api/datasets/demo` | Без тела | 201/200, доверенный синтетический набор |
| GET `/api/datasets/{dataset_id}/filters` | — | 200, реальные IDs и версии |
| GET `/api/datasets/{dataset_id}/overview` | `class_ids`, `textbook_ids`, `test_version` | 200, metrics, topics, heatmap |
| GET `/api/datasets/{dataset_id}/topics/{topic_id}` | Те же фильтры | 200, metrics, by_class, slices |
| GET `/api/datasets/{dataset_id}/comparison` | Обязательные `topic_id`, `textbook_a`, `textbook_b`; необязательные `class_ids`, `test_version` | 200, сравнение и причины ограничений |
| POST `/api/datasets/{dataset_id}/plans/preview` | JSON PlanRequest | 200, PlanPreview |
| POST `/api/datasets/{dataset_id}/plans` | JSON SaveRequest | 201, SavedPlan |
| GET `/api/plans/{plan_id}` | — | 200, сохранённый SavedPlan |
| GET `/api/plans/{plan_id}/export.csv` | — | 200, UTF-8 CSV с BOM |

## Импорт двух CSV

Воспроизводимые файлы: [results.csv](../examples/toni-demo/results.csv), [curriculum.csv](../examples/toni-demo/curriculum.csv), [metadata.json](../examples/toni-demo/metadata.json). Только искусственные ученики: 120, четыре класса, шесть тем, 1440 строк. Форматы столбцов: [шаблон результатов](../contracts/results.template.csv), [шаблон программы](../contracts/curriculum.template.csv).

`metadata` — JSON-строка внутри FormData, не третий загружаемый файл:

```json
{
  "name": "Демонстрационный импорт",
  "subject": "Математика",
  "grade": 7,
  "period_start": "2026-09-01",
  "period_end": "2026-10-31"
}
```

```javascript
const form = new FormData();
form.append('results_file', resultsFile);
form.append('curriculum_file', curriculumFile);
form.append('metadata', JSON.stringify(metadata));
const checked = await fetch('/api/datasets/import?dry_run=true', {method: 'POST', body: form});
// Проверить checked.ok; показать ошибки или preview. По действию пользователя:
const imported = await fetch('/api/datasets/import?dry_run=false', {method: 'POST', body: form});
const body = await imported.json();
if (!imported.ok) throw body;
const datasetId = body.dataset_id;
```

Не задавайте `Content-Type` вручную для FormData: браузер добавляет boundary. Дальнейшие запросы делайте после успешного сохранения набора. Импорт синтетического CSV имеет `is_demo=false`/`source_type=upload`; `is_demo=true` ставит только `/datasets/demo`.

## Аналитика и сравнение

Массивы передаются повторяемыми параметрами: `?class_ids=7A&class_ids=7B`, не строкой `7A,7B`. Кодируйте ID через `URLSearchParams`:

```javascript
const params = new URLSearchParams({
  topic_id: 'equations', textbook_a: 'Учебник A', textbook_b: 'Учебник B', test_version: 'v1'
});
const response = await fetch(`/api/datasets/${datasetId}/comparison?${params}`);
```

На полном синтетическом наборе фрагмент `overview.metrics`:

```json
{
  "n_students": 120,
  "n_post_results": 720,
  "n_pairs": 720,
  "mean_post_pct": 71.75,
  "pair_coverage": 1.0,
  "n_problem_topics": 2
}
```

Фрагмент сравнения `equations`, без ограничения по классу:

```json
{
  "comparison_status": "comparable",
  "difference_gain_pp": 8.0,
  "baseline_gap_pp": 1.0,
  "group_a": {"textbook_id": "Учебник A", "n_pairs": 60, "mean_gain_pp": 16.0},
  "group_b": {"textbook_id": "Учебник B", "n_pairs": 60, "mean_gain_pp": 8.0}
}
```

Это фрагменты, не полный response. Полные проверяемые JSON: [overview](../contracts/integrated-analytics-overview.response.json), [topic](../contracts/integrated-analytics-topic.response.json), [comparison](../contracts/integrated-analytics-comparison.response.json). Эти contract fixtures получены через `/datasets/demo`; UUID/даты заменены маркерами `__DATASET_ID__`, `__CREATED_AT__`.

`mean_*_pct` — проценты 0…100; `*_share`, `pair_coverage` — доли 0…1; `mean_gain_pp`, `difference_gain_pp`, `baseline_gap_pp` — процентные пункты. `difference_gain_pp` = прирост A минус прирост B. Отрицательный прирост допустим. `null` означает отсутствие допустимого расчёта и не заменяется нулём.

Показывайте `comparison_status`, `reasons`, `warnings`, `conclusion`. При `insufficient_data` или `not_comparable` разность приростов — `null`; это корректный HTTP 200. Нужно ≥10 пар на группу, одна совместимая версия/шкала и входной разрыв ≤10 п.п. Сравнение описательное, не причинное доказательство.

Статусы тем: `requires_attention`, `needs_practice`, `mastered`, `insufficient_data`, `no_data`, `mixed_versions`. `problem_topic` — отдельный флаг: например, доля ниже порога может требовать внимания при приемлемом среднем. Для версий используйте `available_slices`/`slices`, а для объяснений — `status_label`/`warnings`.

## Preview, ручные часы, сохранённый отчёт

Минимальный запрос preview:

```json
{"class_id":"7A"}
```

При выбранных версиях:

```json
{
  "class_id": "7A",
  "test_versions": {"equations": "v1"},
  "settings": {"target_pct": 70, "donor_pct": 80, "min_students": 10, "max_change": 2}
}
```

План строится для **одного класса**. Он не принимает `textbook_ids` и массив `class_ids`. Для согласованного экрана запросите overview/topic того же класса и передайте версии как `test_versions: {topic_id: version}`. У аналитики дефолтный порог внимания 60%, у planner целевой уровень 70%: это разные назначенные параметры, не ошибка округления.

Для полного синтетического набора класса 7A получен следующий валидный запрос save:

```json
{
  "class_id": "7A",
  "hours_by_topic": {
    "fractions": 8,
    "equations": 5,
    "proportions": 5,
    "geometry": 3,
    "statistics": 2,
    "revision": 1
  },
  "comment": "Согласованный учебный план"
}
```

В рабочем UI собирайте эту карту из текущего preview/ручных правок; не хардкодьте пример. При отсутствии `hours_by_topic` сохраняются серверные рекомендации. Карта при ручной отправке должна содержать все темы и целые часы. Сумма, min/max, locked и ±2 при стандартных settings проверяются сервером; граница каждого поля Hours — 10000. Сохранение не идемпотентно: каждое успешное нажатие создаёт новый план. На время запроса блокируйте повторное нажатие.

Показывайте `plan_id` и открывайте отчёт через `GET /api/plans/{plan_id}`. Полные [preview](../contracts/integrated-plan-preview.response.json) и [SavedPlan](../contracts/integrated-plan-saved.response.json) опубликованы в contracts. CSV скачивайте отдельной ссылкой/Blob; `Content-Disposition` доступен через CORS. JSON-отчёт — тот же SavedPlan из GET; отдельного PDF endpoint нет.

Snapshot фиксирует источник, класс, версии, метрики planner, ограничения, часы, рекомендации, комментарий и дату. Полные overview/comparison не записываются в snapshot. Не заменяйте сохранённый отчёт пересчётом с текущих фильтров UI.

## Ошибки и контракт

Общий формат ошибки:

```json
{"code":"INVALID_FILTERS","message":"Описание причины","details":[],"total_errors":0}
```

403 — импорт запрещён в деморежиме; 404 — неизвестный/скрытый набор, тема или план; 422 — неверные параметры, CSV или часы; 503 — SQLite временно недоступна; 500 — внутренняя ошибка. Не переходите на экран успеха при `!response.ok`. Ошибки формирования snapshot/ответа до commit не оставляют план; ошибки записи/commit откатываются.

Источник истины: [OpenAPI общего сервера](../contracts/openapi.json) и live `/openapi.json`. Analytics имеет три GET-маршрута в общем приложении; все capabilities аналитики и planner включены. Даты snapshot — UTC; UI отображает UTC+5.

Приёмка Дамиром: реальные два CSV → проверка/импорт → фильтры → overview/темы → сравнение → preview → ручная правка/ошибка → save → повторное открытие JSON и скачивание CSV. Затем тот же сценарий со второго ноутбука после командного review и выбора стенда.
