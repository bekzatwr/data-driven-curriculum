# Final E2E / backend bugfix — 10 ноября 2026

**Изолированная интеграционная сборка для review, не Release Candidate.** Deployment выполняет Дамир. `main` и ветки участников не изменялись; production deploy и платные ресурсы не создавались. Все проверки использовали синтетические данные и отдельные локальные SQLite/volumes. Внешних AI-вызовов — 0.

## A. Интеграция

Ветка: `integration/final-e2e-stabilization`, создана от `integration/p0-server:b25891c332a1e0020e8ac8bdb72b1c5ce5789f27`.

Проверяемый SHA исходников и QA: **`2e4bb964b974292a669f85fe1072e0153e9c62d7`**. Последующие изменения этого PR — отчёт, evidence, README и handoff; актуальный HEAD документации доступен в PR. Выбирать SHA для deployment можно только после закрытия описанных ниже блокеров и review.

[Машиночитаемый аудит](final-e2e-pr-audit.json) содержит полные base/head SHA, списки файлов, reviews, CI runs и ancestry для каждого PR. Все PR #1–#13 на проверенном срезе открыты и не merged. GitHub допускает merge каждого в его заявленную базу; это не гарантирует отсутствия конфликтов между PR.

| PR | Head / SHA | Base | Решение |
| --- | --- | --- | --- |
| #1 | backend/bekzat · d83ce287 | main | Включён через #3; APPROVED Айданой именно для floating-point/atomic plan save |
| #2 | analytics/toni · b25cfaf7 | main | Тот же head, что #12; включён один раз |
| #3 | integration/p0-server · b25891c3 | main | Основа отдельной ветки |
| #4 | frontend/damir · 03395ef5 | integration/p0-server | Уже в истории #9; заменён авторскими обновлениями #9 |
| #5 | deployment/mobile-public · 2e6f3751 | integration/p0-server | Уже включён транзитивно; Docker/persistence/health сохранены |
| #6 | feature/bekzat-p1-infrastructure · cfce13d2 | integration/p0-server | Comments/anti-spam/AI-offline и инфраструктура включены через #9/#13 |
| #7 | docs/github-readme · af1bdc03 | main | Не merged: это устаревшая редакция README. Баннер совпадает с включённым; README интеграции актуализирован отдельно |
| #8 | deployment/bekzat-cloud-readiness · 024d422c | feature/bekzat-p1-infrastructure | Уже включён; необязательный Render example оставлен |
| #9 | fix/damir-final-integration · **de7c5859** | integration/p0-server | Включён опубликованный frontend, включая серверные Teachers и period |
| #10 | feature/aidana-period-planner · 62ad936e | integration/p0-server | Реально опубликован и включён; GitHub 403 больше не является блокером получения period |
| #11 | chore/bekzat-pre-integration · 64cba3f5 | deployment/bekzat-cloud-readiness | Включён через #13 |
| #12 | analytics/toni · b25cfaf7 | integration/p0-server | Включены серверные Teachers, уточнения методологии и тесты Тони |
| #13 | docs/bekzat-deployment-handoff · 0b77889b | chore/bekzat-pre-integration | Сохранена передача deployment Дамиру |

Для #7 CI runs не найдены; это не «успешный CI». У остальных проверенных heads имеющиеся workflow runs успешны. Формальное APPROVE найдено только у #1; остальные изменения включены исключительно в тестовую ветку. Review #1 не подтверждает browser E2E и не разрешает автоматически объединить остальные PR.

Разрешены конфликты `.github/workflows/backend.yml`, `README.md`, `backend/app/main.py`, `scripts/smoke_container.py`, `contracts/capabilities.response.json`, `contracts/openapi.json`. Сохранены read-only запреты, Comments/AI/period flags, CI gates и новые Teachers checks. Машинные контракты сгенерированы из объединённого приложения. При обновлении #9 возник ещё один конфликт README; сохранены текущие сведения об API и авторском UI.

Авторство сохранено обычными merge-коммитами. `web/` совпадает с `de7c585`, `analytics/` — с `b25cfaf`. Алгоритмы `planner/` совпадают с #10; единственное отличие от его дерева — существующее описание HTTP 403 в декораторе `planner/api.py`, без изменения вычислений. Backend ABI/API endpoints не дублируются. P0 остаётся `rules_v1`, period включается явным `settings.mode="period"`.

## B. E2E и доказательства

### Независимый HTTP + настоящая SQLite

Команда: `python qa/check_http_e2e.py . data/final-http.json` после production build `web/`. Скрипт сам запускает Uvicorn на loopback с отдельной БД, выключает AI, удаляет provider keys из дочернего окружения, завершает только свои процессы.

Проверены два настоящих multipart CSV, dry-run, импорт 1 440 результатов / 120 учеников / 6 тем, повторный импорт без дубля, обзор, темы и сравнение. Для `equations`: paired gain A = 16 п.п., B = 8 п.п., разница = 8 п.п. Teachers API возвращает 4 учителя по 30 учеников и 24 часа.

Для обоих режимов выполнены preview, реальное ручное перераспределение двух тем, сохранение, JSON и CSV. `rules_v1` остаётся default; `period_v1` и settings сохраняются. Комментарий привязан к теме сохранённого плана. AI без ключей возвращает 503 `AI_NOT_CONFIGURED`.

На отдельной SQLite проверены неизменность количества snapshots при 422 и при искусственно вызванном серверном 500 после INSERT, `integrity_check=ok`, пустой `foreign_key_check`. Реальный stop процесса даёт connection failure; после start те же P0/period JSON, CSV, comments и Teachers снова доступны. Прямая `/plans/{id}` отдаёт SPA HTML. Это **HTTP E2E, не браузерный E2E**.

### Docker, restart и restore

`python scripts/verify_deployment.py` — 19 passed / 0 failed групп проверок. Проверка включает backend и настоящий React fullstack build, непривилегированный процесс, PORT=8765, health, CORS allow/deny, SPA/assets, запрет запуска без требуемого mount, запрет writable public mode, Teachers и оба snapshot-алгоритма.

Планы, аналитика, CSV и Comments совпадают после restart, удаления/создания только тестового контейнера с тем же volume, online backup и переноса backup в **новый volume**. Проверены SQLite integrity/FKs, Docker HEALTHCHECK, read-only demo lookup/preview/report, запрет import/restore/save/comments/AI POST и rate limit 429 с Retry-After. SQL dump публичного тестового стенда не изменился от запрещённых HTTP операций и после restart.

Доказательства: [HTTP](final-e2e-http.json), [Docker](final-e2e-docker.json), [сетевой probe](final-e2e-frontend-transport.json), [pytest summary](final-e2e-tests.json). Базы, резервные копии и большие локальные логи остаются в игнорируемом `data/`, не публикуются в Git.

### Browser / mobile — НЕ ПРОЙДЕНО

В этой задаче не получено ни одного успешного нового браузерного сценария. Создание новой вкладки локального приложения через доступный Browser Use дважды завершилось timeout подключения webview; существующая вкладка находилась на старой странице ошибки, доступ к которой отклонён URL policy. Ограничения не обходились. Приложение при этом отвечало на независимые HTTP-запросы.

Поэтому **CSV file picker, кнопки, графики, сохранение через React, download через браузер, Reload и UI Retry этой версии не подтверждены**. Исторический отчёт Дамира и screenshots предыдущих сборок не считаются новой приёмкой этого SHA.

| Проверка | Результат этого прогона |
| --- | --- |
| Browser CSV → Import → Overview → Topics → Comparison → Planner → Save → Report → Export | BLOCKED: браузерный инструмент недоступен |
| Teachers / period / Comments / AI-offline через UI | BLOCKED; backend и исходное подключение API проверены отдельно |
| 360 / 390 / 430 / 768 / 1366 / 1920 px | Не выполнено ни визуально, ни в эмуляции |
| Android Chrome / iPhone Safari / физические устройства | Не тестировались |
| Внешний HTTPS и сохранность опубликованного стенда | Не проверялись; deployment этой версии не выполнялся |

## C. Bug fix и открытые дефекты

### P0 — импорт оставлял данные при HTTP 500 — ИСПРАВЛЕНО (Бекзат)

**Reproduction:** вызвать ошибку валидации `ImportResponse` либо сериализации `JSONResponse` при CSV import, demo import или package restore. До исправления ответ 500 увеличивал datasets/topics/results: например, `(1,2,5) → (2,4,10)` при импортировании другого маленького набора.

**Root cause:** `Store.save_upload()` завершал транзакцию, затем endpoint формировал ответ. Rollback уже не мог отменить успешно committed записи.

**Fix:** optional `response_factory` формирует и валидирует готовые байты ответа внутри той же транзакции. Исключение откатывает все таблицы. Даже если ответ подготовлен, ошибка COMMIT не возвращает клиенту успех. Старый внутренний контракт `(dataset, created)` сохранён для seed/аналитики. Конкурентная дедупликация под `BEGIN IMMEDIATE` сохранена.

**Файлы:** `backend/app/db/store.py`, `backend/app/api/datasets.py`. **Regression:** `backend/tests/test_import_atomic_response.py`: 8 сочетаний operation × failure, плюс ошибка отложенного FK при commit. До исправления — **6 failed / 3 passed**; после — 9 passed. Дополнительно targeted import/storage/package suite — 89 passed (входит в полный прогон, не складывать).

### Существующие P0 исправления — СОХРАНЕНЫ

`100 * (score / max_score)`, дробные/полные/крайние баллы, строгие 0..100, failure-atomic P0/period save, сериализация до commit, min/max/locked/сумма/±2 для P0 и серверная валидация manual edits — проверены существующими regression-тестами. Эти исправления из PR #1 не приписываются новому коммиту.

### P1 critical — таймаут frontend не охватывает тело ответа — ОТКРЫТО (Дамир)

**Reproduction:** `npm ci --prefix web`, затем `node qa/check_frontend_transport.mjs`. Этот probe исполняет неизменённый `web/src/api/client.ts` через esbuild в Node против синтетического loopback HTTP server. Server возвращает 200 и начало JSON, затем не завершает body. Это отдельный сетевой тест клиентского модуля, не browser E2E и не замена реальных backend вычислений.

**Actual:** request остаётся pending после 21,2 с при обычном deadline 20 с. **Expected:** понятная ошибка timeout и возможность ручного Retry; отмена при смене фильтра также должна действовать до окончания чтения body.

**Root cause:** `fetchWithDeadline()` очищает timer и abort listener в `finally` после `fetch()`; `request()` затем отдельно ожидает `response.text()`. Пути: `web/src/api/client.ts:116`, `:136`, `:153`. Проблема сохраняется в опубликованном `de7c585`.

**Required fix:** Дамир переносит чтение body под тот же deadline/abort и добавляет regression в свой набор. В этой ветке frontend не изменялся. Probe возвращает ненулевой код: **9 passed / 1 failed**; этот failure не скрыт и не входит в текущий `npm test`/CI. После авторского исправления этот же probe должен стать 10/10 и пройти браузерная проверка Retry.

### Остальные наблюдения

- Teachers UI blocker из раннего `a8f6452` устранён самим Дамиром в `de7c585`: используется `api.teachers`, клиентский `computeTeachers` удалён. Не требуется повторно реализовывать модуль.
- `pytest.ini` теперь включает `qa`, поэтому 7 существующих приёмочных тестов Айданы входят в обычный полный pytest/CI. Их результаты не прибавляются второй раз.
- `npm audit` сообщает 2 moderate записи для react-router/react-router-dom; high/critical = 0. Это вывод npm, не подтверждение эксплуатации. Триаж и совместимое обновление — Дамир; автоматический breaking `audit fix --force` не выполнялся.
- Lint script в `web/package.json` отсутствует. Не выдан за успешный lint.

## D. Testing

| Набор | Passed | Failed | Skipped / ограничение |
| --- | ---: | ---: | --- |
| Полный pytest: backend/tests + tests + qa | 436 | 0 | 0; один известный deprecation warning Starlette/httpx |
| Вложенные unittest subtests | 102 | 0 | Отдельно, не добавлены к 436 |
| npm test | 8 | 0 | 0 |
| Node transport probe | 9 | **1** | Открытый frontend body-timeout |
| TypeScript check / React production build | 2 команды | 0 | Не являются дополнительными unit tests |
| Общий и analytics OpenAPI/examples | Повторная генерация без diff | 0 | Сохранены Comments/period/Teachers |
| Offline AI methodology / Teachers legacy parity | 5 offline requests; 56 parity values, max diff=0 | 0 | Без provider network; parity — отдельная сверка, не UI |
| Native HTTP + SQLite | 8 групп assertions, exit 0 | 0 | Browser не покрыт |
| Docker rehearsal | 19 passed / 0 failed групп проверок | 0 | Только localhost, не production |
| Browser / mobile / внешний HTTPS | 0 | — | BLOCKED / не запускались; не входят в pytest skipped |

CI общей ветки: [Backend](https://github.com/bekzatwr/data-driven-curriculum/actions/workflows/backend.yml?query=branch%3Aintegration%2Ffinal-e2e-stabilization), [Frontend](https://github.com/bekzatwr/data-driven-curriculum/actions/workflows/web.yml?query=branch%3Aintegration%2Ffinal-e2e-stabilization), [Analytics](https://github.com/bekzatwr/data-driven-curriculum/actions/workflows/analytics.yml?query=branch%3Aintegration%2Ffinal-e2e-stabilization), [Planner](https://github.com/bekzatwr/data-driven-curriculum/actions/workflows/planner.yml?query=branch%3Aintegration%2Ffinal-e2e-stabilization). Финальные ссылки на runs и их проверенные conclusion записываются в описании Draft PR. В workflows 8 jobs на событие; повторные push/PR runs не считаются дополнительными тестами. Сетевой probe с известным frontend failure запускается отдельно и явно остаётся блокером, даже при зелёном CI.

Предварительные неуспешные запуски не скрываются: Docker daemon первоначально был выключен и был штатно запущен; HTTP harness сначала выбрал глобальные зависимости вместо окружения проекта, затем при собственном SQL-inspection оставлял соединения открытыми на Windows. Исправлены выбор PYTHONPATH и закрытие test connections; окончательный HTTP запуск завершился кодом 0. Это ошибки/ограничения тестового окружения, не новые production-дефекты.

Воспроизведение:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/export_contracts.py
python -m scripts.export_analytics_contracts
git diff --exit-code -- contracts
npm ci --prefix web
npm test --prefix web
npm run typecheck --prefix web
npm run build --prefix web
python qa/check_http_e2e.py . data/final-http.json
python scripts/verify_deployment.py
node qa/check_frontend_transport.mjs
```

Последняя команда сейчас намеренно сообщает реальный незакрытый defect ненулевым exit code. На Windows при проблеме общего `%TEMP%` задавать новый `--basetemp data/<unique>`; не переиспользовать каталог чужого прогона. Python 3.13, Node 24 локально; Docker build использует Node 22.

## E. Handoff Дамиру

Техническая основа: ветка и полный SHA из раздела A. [Подробный запуск, env и rollback](DAMIR_DEPLOYMENT_HANDOFF.md). Dockerfile и deployment-конфигурации оставлены совместимыми; frontend/hosting-конфигурация Дамира не переписана. `deploy/render.yaml` по-прежнему пример со старой cloud-веткой, auto-deploy off; Дамир сам выбирает платформу и согласованный SHA после review.

```bash
docker build --build-arg APP_TARGET=fullstack -t ddc:<reviewed-sha> .
# Защищённое локальное демо с записью:
docker compose -f deploy/compose.yaml -f deploy/compose.local.yaml up --build --detach --wait
# Backend без Docker, после установки requirements:
python deploy/run_server.py
```

| Параметр | Значение / требование |
| --- | --- |
| APP_TARGET | **Build arg** fullstack; React и API в одном origin |
| PORT | Порт платформы; health использует его же |
| DATABASE_PATH | `/app/data/curriculum.sqlite3` на реальном persistent disk |
| DATA_MOUNT_PATH | `/app/data`, весь каталог вместе с WAL/SHM |
| REQUIRE_PERSISTENT_STORAGE | true |
| REQUIRE_P0 | true для fullstack; API-only — false по handoff |
| WEB_DIST_DIR | `/app/web`, уже задан fullstack image |
| PUBLIC_DEMO / READ_ONLY_DEMO | true / true для открытого synthetic demo |
| AI_ENABLED / AI_ACCOUNT_VERIFIED | false / false; ключи не нужны |
| P1_COMMENTS_ENABLED | true; public POST всё равно запрещён |
| CORS_ORIGINS | Пусто при одном origin; иначе точный HTTPS origin frontend |
| VITE_API_BASE_URL | Build-time пусто для одного origin; никаких секретов |
| TRUSTED_PROXY_CIDRS | Пусто до проверки доверенного ingress |

Один backend instance, filesystem с корректным SQLite locking и права appuser на mount. Операторский synthetic seed: `python deploy/seed_demo_report.py`; выводит report/CSV URLs. Online backup: `python -m backend.app.db.backup --output /app/data/backups/<new-name>.sqlite3`; копию вынести за пределы сервиса. Restore — в новый файл/volume, проверить integrity/FKs и snapshot/CSV, затем переключить DATABASE_PATH. Rollback — согласованный предыдущий image и совместимая проверенная копия; не перезаписывать единственную БД и не удалять volume.

Рабочие endpoints: `/api/health`, `/api/capabilities`, `/openapi.json`; `/api/datasets/import?dry_run=true|false`; `/api/datasets/{id}/overview`, `/topics/{topic_id}`, `/comparison`, `/teachers`, `/plans/preview`, `/plans`, `/comments`; `/api/plans/{id}`, `/api/plans/{id}/export.csv`; `/api/ai/status`. P0 запрос `{"class_id":"7A"}`, period `{"class_id":"7A","settings":{"mode":"period"}}`; manual — `hours_by_topic` всех тем. Точные request/response schemas и реальные JSON — в `contracts/` и [FRONTEND_API](FRONTEND_API.md).

До публикации Дамиру: исправить timeout; провести полный React CSV/file-picker/E2E и шесть размеров; проверить HTTP/Retry/public flags, health, прямые ссылки и download; получить review; затем самостоятельно выполнить разрешённый deployment, HTTPS и persistence/backup acceptance на выбранной площадке. Серверный handoff можно принимать уже сейчас; разрешения публиковать он не заменяет.

## F. Итоговый статус

| Зона | Статус | Условие |
| --- | --- | --- |
| P0 backend / SQLite | **GO для review и серверной интеграции** | HTTP/pytest/Docker прошли; floating-point и atomic save сохранены, atomic import исправлен |
| Полный P0 через React | **NO-GO для окончательной приёмки** | Browser/file upload/сохранение через UI не подтверждены; timeout открыт |
| P1 server: Teachers / period / Comments / AI-offline | **GO для review** | Реальные опубликованные модули; UI P1 ещё нуждается в приёмке |
| Полное локальное демо | **NO-GO как окончательно принятое** | Локально запускается и серверный сценарий проходит; оператор должен закрыть browser QA |
| Public deployment | **NO-GO** | Нет team review всей интеграции, browser/mobile acceptance и проверенного внешнего HTTPS/persistence этой версии |

| Задача | Сделано | Осталось | Блокер | Кто отвечает |
| --- | --- | --- | --- | --- |
| Серверная интеграция | Реальные модули, контракты, 436 pytest | Review и приёмка финального SHA | Нет командного approve общей ветки | Бекзат + команда |
| Импорт / plans / Comments | Атомарность, rollback, restart, backup | Review изменения import transaction | — | Бекзат, Айдана |
| Frontend | Авторский de7c585, Teachers/period подключены, build | Исправить body-timeout; browser/mobile/Retry | 1 воспроизводимый frontend defect + недоступность браузера здесь | Дамир |
| Analytics | Формулы и Teachers из b25cfaf сохранены | Review корректности отображения методологии в UI | Browser QA | Тони + Дамир |
| Period | Опубликован, mode/version, manual/CSV/restart проверены | Review и общий UI acceptance | Browser QA | Айдана + Дамир |
| Публикация | Docker, persistent storage, seed/backup/restore | Площадка, одобрение, HTTPS, внешний restart/restore | До закрытия gates не публиковать | Дамир / владелец аккаунта |

Заморозка функций — **11 ноября 18:00**, внутренняя сдача — **22:00**, дедлайн — **11 ноября 2026, 23:59 UTC+5**. До freeze закрыть timeout и отзывы; затем только интеграция/исправления, полный UI/mobile сценарий и операторская проверка разрешённой публикации. Новые P1/P2 функции не добавлять.
