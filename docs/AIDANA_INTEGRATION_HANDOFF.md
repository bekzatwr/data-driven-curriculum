# Period Planner: передача Бекзату и Дамиру

PR Айданы: https://github.com/bekzatwr/data-driven-curriculum/pull/10
Назначение: `integration/p0-server`. Merge выполняет команда после review.

## Дамиру: точный контракт

Проверены `frontend/damir` (`03395ef5db68ac9fab379f622ddf6fbe09112327`) и `fix/damir-final-integration` (`f6eb7d3408ece65fdb571b0356c5584cd275c9f8`): period всё ещё считается через `buildPeriodPlan`, запрос поднимает `max_change`, но не передаёт `settings.mode`. Эти ветки нами не менялись.

1. В `PlanSettings` добавить `mode?: 'rules_v1' | 'period'`. Для старых снимков отсутствие mode означает `rules_v1`.
2. В period preview и save отправлять `mode: 'period'`. Снимать ±N валидацию в UI только для этого режима; не заменять mode большим max_change.
3. Часы и причины брать из **серверного** preview: `items[].proposed_hours`, `items[].reason`. `buildPeriodPlan` оставить только как независимый тестовый эталон, а не источник сохраняемой рекомендации.
4. При ручной правке хранить редактируемую копию часов. Save получает `hours_by_topic` для всех тем. Если правок нет, поле можно опустить: сервер сохранит свою рекомендацию.
5. В SavedPlan `recommended_hours` — серверная рекомендация; `proposed_hours` — фактическое решение. `manually_modified` на item и на плане вычисляет сервер. Не определять ручную правку только по `delta`: он сравнивает итог с исходным curriculum.
6. Для locked темы часы равны current_hours; min/max и сохранение общей суммы обязательны. В period min/max незаблокированной темы могут не включать её прежние current_hours. Невыполнимый бюджет — 422 `INVALID_PLAN`, сообщение показать без пересчёта в браузере.
7. Открывать сохранённый план через GET, без повторного preview: настройки и метрики снимка неизменны. Режим показывать по `settings.mode` / `algorithm_version`, не по префиксу comment. Экспорт брать с сервера.

### Preview

`POST /api/datasets/{dataset_id}/plans/preview`

```json
{"class_id":"7A","settings":{"mode":"period","target_pct":70,"donor_pct":80,"min_students":10,"max_change":2}}
```

Полный реальный ответ: [period-plan-preview.response.json](../contracts/period-plan-preview.response.json).
Ключевые признаки: `algorithm_version="period_v1"`, `settings.mode="period"`, `total_hours=24` на встроенном demo. `transfers=[]`: period распределяет бюджет с минимумов, а не моделирует P0-переносы.

### Ручное сохранение на demo 7A

`POST /api/datasets/{dataset_id}/plans`

```json
{
  "class_id":"7A",
  "settings":{"mode":"period","target_pct":70,"donor_pct":80,"min_students":10,"max_change":2},
  "hours_by_topic":{"fractions":7,"equations":7,"proportions":4,"geometry":3,"statistics":2,"revision":1},
  "comment":"Решение методиста после проверки ограничений"
}
```

Пример содержит все шесть тем, сумму 24 и locked geometry=3. Для другого dataset использовать его topic_id и ограничения, не копировать эти часы.
Полный реальный ответ без ручных правок: [period-plan-saved.response.json](../contracts/period-plan-saved.response.json).
После ручной правки сервер возвращает те же поля, а `manually_modified` отражает отличие от серверной рекомендации.

Фрагмент ответа для указанной правки встроенного demo (остальные поля опущены):

```json
{"algorithm_version":"period_v1","manually_modified":true,"items":[
  {"topic_id":"fractions","recommended_hours":8,"proposed_hours":7,"manually_modified":true},
  {"topic_id":"equations","recommended_hours":6,"proposed_hours":7,"manually_modified":true}
]}
```

```text
GET /api/plans/{plan_id}
GET /api/plans/{plan_id}/export.csv
```

JSON для скачивания — тело первого GET; CSV — ответ второго GET. Не генерировать новый план при Reload.

## Бекзату: минимальная интеграция с PR #6

- После review подключить PR #10 и PR #6 к общей integration-ветке. Planner storage/API контракты сохранили atomic save; collab и backend Бекзата не переписаны.
- В общей P1 capabilities выставить `period_planner_api: true` только при наличии работающего нового planner. В PR #6 сейчас false; это известная точка подключения, не подтверждённая готовность UI.
- Сохранить поддержку `settings.mode` в единственном planner router и общую `DATABASE_PATH` для datasets, snapshots, comments.
- При объединении `scripts/export_contracts.py` сохранить генерацию и P1 collab-примеров, и новых period-примеров. Перегенерировать OpenAPI; не выбирать целиком одну из конфликтующих версий contracts.
- Проверить `GET /openapi.json`: enum mode содержит rules_v1/period, default rules_v1; preview/save возвращают period_v1, старые планы читаются.
- Запустить полный pytest, `python -m pytest -q qa`, exporters, parity, Docker smoke и браузерный маршрут ниже. `qa` требует collab, поэтому он запускается после подключения PR #6.

## Сценарий настоящего browser E2E для Дамира и Бекзата

Использовать отдельную локальную SQLite с синтетическим demo, `READ_ONLY_DEMO=false`, `AI_ENABLED=false`, без внешних AI-ключей.

1. Открыть UI, загрузить demo, выбрать 7A. Проверить обзор, проблемную тему и сравнение учебников.
2. Выбрать Period Planner, нажать расчёт. В Network подтвердить POST preview с `settings.mode=period`; ответ содержит `period_v1`.
3. Сравнить таблицу UI с `items[].proposed_hours` ответа. Сумма 24, locked geometry=3, min/max соблюдены.
4. Перенести один допустимый час между двумя незаблокированными темами. Ошибочный бюджет должен блокировать сохранение или возвращать 422 без новой записи.
5. Сохранить. В Network проверить mode и все `hours_by_topic`; сервер возвращает 201, `period_v1`, корректные `recommended_hours` и `manually_modified`.
6. Открыть отчёт по plan_id, скачать JSON/CSV, сверить часы, сумму и ручные отметки. Добавить комментарий к плану/теме плана.
7. Reload и прямое открытие URL отчёта: тот же snapshot и comments, без повторного расчёта.
8. Остановить API, снова запустить с той же SQLite. Повторить GET отчёта/CSV/comments: содержимое совпадает.
9. Создать backup, восстановить в новый файл, запустить API с восстановленной БД. Проверить тот же отчёт и комментарии.
10. AI без ключей показывает «ИИ не подключён», основной маршрут работает. Повторить P0 rules_v1 и открытие старого отчёта.

Сохранить SHA backend/frontend, браузер, время, plan_id и результаты каждого шага. HTTP QA и сборка React сами по себе не заменяют этот прогон.
