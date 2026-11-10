# Deployment handoff audit — Бекзат → Дамир

Проверено **10 ноября 2026**. Deployment целиком передан Дамиру. Этот отчёт проверяет совместимость прежних изменений Бекзата; он не назначает платформу, не разрешает deploy и не объявляет Release Candidate.

Рабочая ветка `docs/bekzat-deployment-handoff` создана от собственной `chore/bekzat-pre-integration:64cba3f`. Актуальная изученная ветка Дамира — `fix/damir-final-integration:a8f645295e44a1d294429b4894279e4a9a8e4be9`. Его исходники, конфигурация и ветка не менялись. [Короткий handoff](DAMIR_DEPLOYMENT_HANDOFF.md) · [Машиночитаемые результаты](deployment-handoff-check.local.json).

## Что проверено и оставлено

| Изменение Бекзата | Зависимость / влияние | Решение |
| --- | --- | --- |
| [PR #5](https://github.com/bekzatwr/data-driven-curriculum/pull/5), `2e6f375` | PublicDemoGuard, операторский synthetic report, local/public Compose и health/persistence; уже предок #6/#8 и ветки Дамира | Оставить: ограничивает публичную запись, не выбор хостинга |
| [PR #6](https://github.com/bekzatwr/data-driven-curriculum/pull/6), `cfce13d` | Comments, anti-spam, AI-off, общий SQLite backup, fullstack; уже включён Дамиром | Оставить: отмена потеряет серверные гарантии и зависимости UI/API |
| [PR #8](https://github.com/bekzatwr/data-driven-curriculum/pull/8), `024d422` | Дополнительные проверки выпуска, cloud-инструкция, ручной Render Blueprint; уже включён Дамиром | Оставить: проверки используют HTTP/SQLite/Docker и не создают облако |
| Dockerfile / .dockerignore | Backend stage работает без React; fullstack — выбираемый build target; env/DB/ключи исключаются из build context | Оставить: оба варианта переносимы, defaults не требуют Render |
| deploy/run_server.py | PORT из env, 0.0.0.0, один worker, mount/writeability, public-mode guard, опциональный fullstack gate | Оставить: нет Render SDK, RENDER_* env или домена в runtime |
| deploy/render.yaml | Самостоятельный необязательный пример с прежней cloud-веткой, persistent disk и auto-deploy off | Оставить: FastAPI и Actions его не применяют; при выборе Render Дамир задаёт согласованный release ref |
| compose.yaml / deploy/compose.yaml / local override | Разные профили: API dev, public fullstack rehearsal, отдельное writable loopback demo | Оставить: это альтернативы, не три одновременно обязательных сервиса; профили имеют своё назначение |
| Environment variables | DATABASE_PATH/PORT/mount/CORS настраиваются; VITE_API_BASE_URL нужен только при сборке UI; REQUIRE_P0 относится к единому fullstack | Оставить значения и шаблоны; разъяснить выбор профиля, чтобы не скопировать fullstack guard в отдельный API |
| GitHub Actions | Pytest, contracts, benchmarks, React build, Docker smoke/rehearsal. Нет deploy hook, provider CLI, docker push или применения Blueprint | Оставить: это CI, не автоматическая публикация |
| SQLite / backup / health / public protection | Общая БД и WAL, согласованный backup, восстановление нового файла, health с проверкой БД, readonly/anti-spam | Оставить полностью: обязательные требования backend независимо от платформы |

Проверено Git ancestry: **#5, #6, #8 уже входят в `dd3d043`**. Не нужно применять эти PR повторно или отменять их группой. Все PR сохранены открытыми и не объединялись нами.

## Совместимость с работой Дамира

Сравнены Git blobs **13 файлов**: Dockerfile, .dockerignore, root Compose, Render YAML, env example, оба deploy Compose, entrypoint, seed, backend Settings, backup, release checker и Docker rehearsal. В проверенных SHA Бекзата и Дамира они **полностью идентичны**. Отличия GitHub workflows Дамира расширяют branch filters и запускают его npm/AI-contract tests; эти изменения сохранены, не заменены старыми файлами Бекзата.

На новом `dd3d043` Дамир самостоятельно включил period из PR #10 и разрешил прежние конфликты exporter/CI. Это установлено по Git history/diff и успешным четырём CI workflows актуального `a8f6452`; общий browser E2E здесь не повторялся. Дополнительный `dd3d043 → a8f6452` меняет только UI/его отчёт, deployment/runtime-файлы одинаковы. Отдельный provider-specific deploy Дамира в просмотренных refs не опубликован. Когда он выберет другую платформу, backend требует подходящее хранилище и origin-настройки, а не Render.

Тони во время аудита опубликовал Teachers API (`analytics/toni:59ba47b`) на серверной базе `b25891c`. Это следующая серверная интеграция Бекзата с Тони; старые deployment-файлы из базы этой ветки не должны заменять актуальную конфигурацию Дамира. В этой задаче модуль не объединялся и не тестировался как часть общего приложения.

**Мешающего runtime-изменения не найдено. Отменено: ничего.** Mass revert/reset, изменения чужих веток и замена algorithms не выполнялись.

Обнаружены только неточности прежней документации:

- Назначение Бекзата ответственным за cloud больше не актуально — передано Дамиру явно в README и handoff.
- Fullstack-команды и REQUIRE_P0=true могли выглядеть обязательными для любой архитектуры. Уточнён отдельный API без локального React с сохранением persistence/public guards.
- `npm test -- --run` не соответствует опубликованному node:test script Дамира; инструкция исправлена на `npm test`. Lint script по-прежнему отсутствует и не объявляется пройденным.
- Render-шаблон содержит прежнюю подготовительную ветку. Уточнено, что это пример; согласованный ref выбирает Дамир, конфигурацию за него не переключали.

Изменения этой ветки — **только документация и evidence**. Dockerfile, YAML, env values, workflows, backend/API и frontend не изменены. Git-конфликты окончательного объединения зависят от будущих HEAD; текущая совместимость не означает готовый release.

## Проверки в этой задаче

| Проверка | Реальный результат / границы |
| --- | --- |
| Профильный pytest | **147 passed, 0 failed, 0 skipped**, 91.38 s; backup/storage/API/public mode/release precheck/anti-spam/atomic save; 1 известный Starlette warning |
| Docker BuildKit API-only | Backend target собран без компиляции React |
| Переносимость env/storage | Непривилегированный backend, **PORT=8765**, mount **/srv/curriculum**; настоящий persistent guard включён |
| Другой frontend origin | CORS GET и preflight разрешены для одного заданного origin; чужому origin разрешение не выдано. Это HTTP headers, не браузерный E2E |
| Реальные вычисления | Synthetic 120 учеников; comparison +8 п.п.; preview/сохранённый оператором report 24 ч; JSON/CSV |
| Public restrictions / AI | Import/restore/save/comments/AI POST дают 403 без изменений БД; AI configured=false, внешних provider calls 0 |
| Persistence / backup | После restart те же report/CSV; backup скопирован за пределы контейнера и восстановлен в **новый volume**, содержимое совпадает |
| Docker итог | **7 групп passed, 0 failed**; source `64cba3f`, source_dirty=false. Созданные только для теста containers/volumes удалены |
| OpenAPI / analytics contracts | Оба exporter exit 0, diff contracts пустой |
| Compose | Root, fullstack и local override — config valid |
| Внешний deploy / HTTPS / устройства | **NOT RUN**: публикует Дамир; сервер доступен был только локально |

Команды pytest и метаданные Docker находятся в evidence. Полный 319-test / 16-group fullstack прогон из предыдущего PRE-INTEGRATION отчёта **не выдаётся за повторный прогон здесь**. Runtime с того времени в собственной базе не менялся; текущая проверка дополнительно проверила API-only вариант. Код Дамира не пересобирался и не редактировался.

## Ответственность после передачи

| Задача | Кто отвечает |
| --- | --- |
| Платформа, аккаунт/бюджет, deployment-конфигурация, release ref, сборка UI, HTTPS/ingress, публикация | **Дамир**, платные действия — с владельцем аккаунта |
| Persistent disk и права, off-service backups, restore/rollback в выбранном хостинге, мониторинг доступности | **Дамир**; Бекзат поддерживает серверные инструменты |
| Backend/FastAPI, SQLite schema/transactions, atomic save, import limits, API contracts, server health/security | **Бекзат** |
| Согласованное подключение аналитики Тони и planner Айданы, серверные regression tests и совместимость snapshot | **Бекзат вместе с владельцами модулей** |
| Frontend API wiring, браузерные/mobile E2E, внешний HTTPS + сохранность после redeploy | **Дамир**, Бекзат помогает диагностировать API |
| Разрешение финального объединения / публикации | **Командный review и капитан/владелец** |

Backend совместим с размещением единым контейнером либо отдельным API при соблюдении требований SQLite. Ни подготовленный Render-шаблон, ни этот отчёт не требуют от Дамира выбирать конкретного провайдера. Необходимость иной СУБД обсуждается с Бекзатом только если выбранная инфраструктура не поддерживает нужное постоянное хранилище.
