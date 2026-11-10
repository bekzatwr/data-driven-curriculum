# Готовность публичного демостенда · 10 ноября 2026

**Сервер и конфигурация подготовлены. Публикация полного сайта заблокирована frontend и review.** Рабочая ветка `deployment/mobile-public`, база `integration/p0-server:b25891c`. Deployment, платные ресурсы и merge в main не выполнялись. [Публикация и env](../deploy/README.md) · [Мобильная приёмка](MOBILE_ACCEPTANCE.md).

## Проверенные ветки и review

| Компонент | Проверенный head | Состояние |
| --- | --- | --- |
| main | 3ebe857 | React отсутствует |
| PR #1, backend/bekzat | d83ce28 | Open, не merged; CI успешен; submitted reviews нет, approve Айданы отсутствует |
| PR #2, analytics/toni | a2a89fa | Open, не merged; CI успешен; submitted reviews нет |
| PR #3, integration/p0-server | b25891c | Draft, не merged; CI успешен; submitted reviews нет |
| frontend/damir | 7660b17 | Только README.md и ТЗ .docx; package.json/lockfile/src отсутствуют |

Ветки участников не изменялись. Алгоритмы в `analytics/*`, `planner/service.py`, `planner/rules.py`, `planner/storage.py`, модели и исходные planner tests сохранены. В `planner/api.py` добавлено только описание ответа 403 в OpenAPI.

## Найденные проблемы и изменения

1. Render Blueprint указывал старую backend-ветку и `READ_ONLY_DEMO=false`. Исправлено: новая deployment-ветка, `READ_ONLY_DEMO=true`, `PUBLIC_DEMO=true`; persistent disk 1 GB и auto-deploy off сохранены. Удалён maxShutdownDelaySeconds: Render не позволяет менять shutdown delay при attached disk.
2. Старый read-only режим разрешал HTTP save плана и создание demo по запросу. Добавлен ASGI guard до разбора тела: запись запрещена, preview остаётся доступен. Demo готовится из встроенных CSV при startup; публичный POST demo только читает, возвращает 200/created=false. Capabilities сообщает plan_save=false. Это намеренное изменение публичного контракта, не отключение валидации.
3. Добавлена служебная команда владельца `deploy/seed_demo_report.py`: синтетический сохранённый отчёт создаётся без открытия публичной записи; повторный запуск переиспользует snapshot. Ссылки выводятся в Shell, а не через публичный admin endpoint.
4. Release precheck различает public/local. Compose override предоставляет отдельный локальный writable проект/volume, привязанный к loopback. Frontend handoff check сообщает отсутствие файлов и не выдаёт это за успешный build.
5. CI и Docker smoke проверяют запрет публичной записи, реальный сохранённый отчёт и неизменность SQLite. `.dockerignore` исключает вложенные env, ключи и базы из build context. README обновлён для GitHub.

Изменены ожидания трёх существующих integration tests в связи с новым требованием публичной безопасности: 201 → 200 для заранее подготовленного demo и 201/404 → 403 для запрещённого save. Проверки приватности, расчётов и atomic save не ослаблены. Добавлены 15 отдельных regression cases.

## Результаты локальных проверок

| Проверка | Фактический результат |
| --- | --- |
| Полный pytest, Python 3.13.3 | **224 passed, 26 subtests passed; 0 failed, 0 skipped**, 157,60 с |
| Новые public-deployment regression cases | **15 passed**, входят в общий прогон |
| Исходные 7 planner tests, 28 atomic-save, 8 boundary regressions | Прошли в полном pytest |
| API contracts | Экспорты общего и analytics OpenAPI успешны; единственное намеренное изменение — 403 для save |
| Docker 29.1.5 | **13 групп проверок успешно**, run `ddc-check-0dc0e60b28` |
| Render Blueprint | Официальная JSON Schema: **0 ошибок**; Compose local override проверен — отдельный volume и loopback |
| Реальная fullstack Docker-сборка | Ожидаемо заблокирована: `web/package.json` и `web/` отсутствуют |
| Frontend tests / TypeScript / lint / build | **BLOCKED**, нет React/package.json |
| Browser E2E / responsive / Android / iPhone / macOS | **NOT RUN**, нет React и внешнего стенда |
| HTTPS / другой ноутбук или физический телефон | **NOT RUN**, deploy не выполнялся |

Сохраняется одно известное Starlette/TestClient deprecation warning. Первый полный прогон обнаружил устаревшее ожидание 201 в analytics integration test; оно обновлено согласно описанному контракту. Первый Docker-прогон превысил существующий startup timeout; повторный полный прогон прошёл без увеличения таймаута. Итоговые результаты приведены выше.

## Реальный серверный E2E и ограничения

Два синтетических CSV → preview/import → overview/heatmap/topics → comparison → planner → сохранённый план → JSON/CSV. Настоящий Uvicorn HTTP и SQLite: 120 учеников, 1440 строк, 720 пар; сравнение уравнений 16−8=8 п.п.; план 24 часа. Dataset, аналитика, snapshot и CSV совпадают после restart, пересоздания контейнера с тем же volume и восстановления off-volume backup в новый volume.

В отдельном public-контейнере проверены startup guard, 403 import/restore/save, отсутствие логических изменений SQLite при demo/preview/report/export, совпадение подготовленного отчёта после restart и защита export от traversal. Чтение заранее созданного synthetic snapshot работает с запрещённым HTTP save.

[Машинный Docker-протокол](public-deployment-check.local.json) содержит `server_p0_verified=true`, `public_read_only_verified=true`, **`full_p0_verified=false`**. React build stage тестировался на явно обозначенном временном packaging probe. Это не UI и не доказательство мобильной готовности. Секреты React, Retry, графики, file picker и мобильный CSV export пока проверить невозможно.

## Блокеры до публикации

1. Дамир публикует настоящий frontend и согласовывает интеграцию. Нужны исходники, lockfile, команды тестов/TS/lint/build, работа с capabilities и все P0 API.
2. Команда выполняет browser E2E и матрицу 360/390/430/768/1366/1920; фиксирует реальные среды и ограничения эмуляции.
3. Айдана review/approve серверной интеграции; команда согласовывает изменение read-only контракта. PR остаются открытыми до согласования.
4. Владелец отдельно разрешает Render compute + disk (ориентир $7,25/месяц до дополнительных начислений) и public deployment. Ресурсы сейчас не создаются.
5. После разрешённой публикации проверить HTTPS, доступ с другого устройства, реальные disk permissions, restart/restore и off-service backup. Домен и стоимость подтверждаются кабинетом.

Точные шаги, environment variables, создание синтетического отчёта и backup/restore находятся в [deploy/README.md](../deploy/README.md). До устранения блокеров репозиторий содержит подготовку публикации, а не готовый публичный мобильный сайт.
