# Deployment handoff — Дамиру

**За весь deployment отвечает Дамир:** выбор платформы, её конфигурация, сборка frontend, HTTPS, публикация, эксплуатация, backups и rollback. **Бекзат отвечает за backend, SQLite, API и серверную интеграцию.** Новое распределение заменяет прежнее назначение Бекзата ответственным за облако.

Актуальная интеграция: `integration/final-e2e-stabilization`, [PR #14](https://github.com/bekzatwr/data-driven-curriculum/pull/14). Проверенный совместный код **`b641fd6aced15546648dd0e9e1c367f70d663c94`**, frontend **`2d554f0c3ecc67fa054e6c83a435eb82d5bdf766`**, дерево web идентично авторскому. Последующий commit меняет только QA/README/отчёт; точный SHA для handoff и CI указаны в PR #14.

**Оба frontend-блокера закрыты:** period stepper и ArrowUp/Down разрешают +3 в пределах min/max, P0 сохраняет ±2; timeout охватывает чтение response body. Настоящий React CSV→analytics→comparison→P0/period save→report→CSV, Teachers/Comments/AI disabled, Retry, Reload, restart и restore прошли. **451 pytest, 19 frontend tests, transport 10/10, HTTP 8 групп, Docker 19**, TypeScript/build/contracts — PASS. [Отчёт и границы проверки](FINAL_E2E_BUGFIX_REPORT.md), [машиночитаемый итог](release-accepted.json).

**GO для передачи проверенного backend и локального E2E на командный review. Публичный production пока NO-GO:** нужен approve Айданы/Тони, deployment Дамира и реальная внешняя HTTPS/persistence-проверка. На момент отчёта Айдана COMMENTED на старый SHA; review Тони в #14 отсутствует. AI остаётся выключенным. Физические устройства, отдельные Chrome/Safari и мобильная матрица в этом прогоне не принимались.

## 1. Запуск backend — выбрать подходящий вариант

| Вариант | Сборка / запуск | Условия |
| --- | --- | --- |
| API отдельно от frontend | `docker build --target backend -t ddc-api:handoff .` | Docker BuildKit; React не требуется. `REQUIRE_P0=false`, WEB_DIST_DIR не задавать |
| React + API вместе | `docker build --build-arg APP_TARGET=fullstack -t ddc-web:handoff .` | Собирает текущий `web/`, WEB_DIST_DIR=/app/web задан образом; `REQUIRE_P0=true` |
| Python без Docker | Python 3.13, `python -m pip install -r requirements.txt`, затем `python deploy/run_server.py` | Настроить env и реальное постоянное хранилище перед запуском; управление процессом и TLS — у Дамира |

Docker уже запускает `python deploy/run_server.py`: Uvicorn слушает `0.0.0.0:$PORT`, один worker, корректное завершение процесса. BuildKit собирает зависимости выбранного stage; [Docker `--target`](https://docs.docker.com/build/building/multi-stage/).

`REQUIRE_P0` — дополнительная проверка **единого fullstack-сервиса**, которая требует локальный React build. Для отдельного API значение false не отключает API, SQLite persistence, read-only или anti-spam. API и отдельно размещённый UI в таком варианте проверяются каждый по своему URL. Не копировать fullstack env целиком в API-only сервис.

Пример запуска отдельного API **локально**, после команды сборки из таблицы; это не публикация в интернет:

```bash
docker volume create ddc-api-data
docker run -d --name ddc-api -p 127.0.0.1:8080:8000 \
  -v ddc-api-data:/app/data -e PORT=8000 \
  -e DATABASE_PATH=/app/data/curriculum.sqlite3 -e DATA_MOUNT_PATH=/app/data \
  -e REQUIRE_PERSISTENT_STORAGE=true -e REQUIRE_P0=false \
  -e PUBLIC_DEMO=true -e READ_ONLY_DEMO=true \
  -e AI_ENABLED=false -e AI_ACCOUNT_VERIFIED=false \
  -e CORS_ORIGINS=https://frontend.example.org ddc-api:handoff
```

Origin заменить на адрес своего frontend. Проверить `http://127.0.0.1:8080/api/health`; volume сохранять при остановке/обновлении. Пример записан для bash, переносы строк для другой оболочки адаптирует запускающий.

## 2. Environment variables

| Переменная | Что задать |
| --- | --- |
| `PORT` | Порт, предоставленный платформой; default 8000. Healthcheck использует тот же порт |
| `DATABASE_PATH` | Абсолютный путь на постоянном диске, например `/app/data/curriculum.sqlite3` |
| `DATA_MOUNT_PATH` | Реальная точка монтирования диска, например `/app/data`; допускается другой путь |
| `REQUIRE_PERSISTENT_STORAGE` | `true`: запуск откажется без mount или если DATABASE_PATH вне него |
| `PUBLIC_DEMO`, `READ_ONLY_DEMO` | Для открытого synthetic demo оба `true`; публичная запись запрещена |
| `REQUIRE_P0` | `true` для fullstack; `false` для отдельного API, см. выше |
| `WEB_DIST_DIR` | Не задавать для API-only; fullstack image сам задаёт `/app/web` |
| `CORS_ORIGINS` | Пусто для одного origin; для отдельного UI — его точный HTTPS origin, несколько через запятую |
| `TRUSTED_PROXY_CIDRS` | Изначально пусто; заполнять только проверенными адресами ingress. Не использовать `0.0.0.0/0` или `::/0` |
| `P1_COMMENTS_ENABLED` | `true`; public read-only всё равно запрещает POST comments |
| `AI_ENABLED`, `AI_ACCOUNT_VERIFIED` | Оба `true`, чтобы включить ИИ-пояснения; иначе `false`, и ключи не нужны |
| `AI_PUBLIC_DEMO` | `true` — разрешить ИИ-пояснения встроенного демо в режиме `READ_ONLY_DEMO`. Запись (импорт, сохранение, комментарии) остаётся закрытой; лимит ИИ — 3 запроса в минуту на адрес, 10 в минуту и 100 в сутки на весь сервер. По умолчанию `false` |
| `GROQ_API_KEY`, `GEMINI_API_KEY` | Секреты только в env платформы; хотя бы один для ИИ |

`APP_TARGET`, `FRONTEND_DIR`, `VITE_API_BASE_URL` — параметры **сборки**, а не переключатели готового backend. Для отдельного UI Дамир задаёт при сборке React `VITE_API_BASE_URL=https://api.example.org` **без `/api` в конце**: клиент сам добавляет `/api/...`. Для одного origin оставить пусто. Изменение runtime env не пересобирает Vite. Секреты не должны попадать в VITE-переменные, build args или Git.

Read-only ограничивает HTTP, а не права процесса на SQLite: для startup, WAL и операторского seed нужен доступ на запись. Для полного сценария с импортом/save использовать существующий защищённый локальный профиль `deploy/compose.local.yaml`. Публичную запись нельзя открывать простым отключением флагов без согласованной защиты доступа.

## 3. SQLite, постоянство и backup

Хранятся datasets/results/curriculum, сохранённые snapshots, comments и технические rate counters в **одной DATABASE_PATH**. Монтируется весь каталог, включая `-wal` и `-shm`. Один экземпляр backend и постоянный локальный filesystem с SQLite locking; WAL не работает через сетевой filesystem — [документация SQLite](https://sqlite.org/wal.html). Эфемерный слой контейнера и object storage не заменяют этот диск.

В Docker процесс работает как `appuser`; при запуске без Docker используется назначенный Дамиром пользователь сервиса. Для нестандартного mount Дамир обеспечивает ему права на каталог средствами выбранной платформы. Наличие mount само по себе не доказывает сохранность после redeploy: проверить сохранённый plan_id/JSON/CSV после restart и замены контейнера. Если платформа не предоставляет подходящий диск, согласовать другое хранилище с Бекзатом до публикации.

Команды **в окружении backend** с его DATABASE_PATH; имена копий должны быть новыми:

```bash
python deploy/seed_demo_report.py
python -m backend.app.db.backup --output /app/data/backups/pre-release-UNIQUE.sqlite3
python -m backend.app.db.backup --source /app/data/backups/pre-release-UNIQUE.sqlite3 --output /app/data/recovered-UNIQUE.sqlite3
```

Seed создаёт только встроенный synthetic dataset и настоящий сохранённый отчёт; stdout содержит `dataset_id`, `plan_id`, `report_url`, `csv_url`. Пути примера заменить при другом mount. Готовый backup скопировать **за пределы сервиса**. Для restore переключить DATABASE_PATH на проверенный новый файл и перезапустить; исходную БД сохранить. JSON package одного dataset не заменяет backup SQLite. Не копировать только живой `.sqlite3` без WAL и не удалять volume при обновлении.

## 4. Рабочие API

Базовый контракт публикуется в `GET /openapi.json`, интерактивная документация — `/docs`. UI проверяет `GET /api/capabilities`, доступность БД — `GET /api/health` (200 либо 503).

| Назначение | Endpoint |
| --- | --- |
| Демо / наборы | `POST /api/datasets/demo`, `GET /api/datasets`, `GET /api/datasets/{id}` |
| CSV / проверка импорта | `POST /api/datasets/import?dry_run=true` или `false`; multipart: results_file, curriculum_file, metadata |
| Данные и фильтры | `GET /api/datasets/{id}/filters`, `/quality`, `/curriculum`, `/results` |
| Аналитика / сравнение | `GET /api/datasets/{id}/overview`, `/topics/{topic_id}`, `/comparison` |
| Teachers | `GET /api/datasets/{id}/teachers`; [фактический HTTP response](release-accepted-teachers.response.json) |
| План | `POST /api/datasets/{id}/plans/preview`, `POST /api/datasets/{id}/plans` |
| Сохранённый JSON / CSV | `GET /api/plans/{plan_id}`, `GET /api/plans/{plan_id}/export.csv` |
| Comments | `GET/POST /api/datasets/{id}/comments` |
| AI status | `GET /api/ai/status`: configured=false; AI-вызовы выключены |

В public read-only разрешены чтение, demo lookup и preview. Import, import dry-run, save, comments POST, AI POST и dataset restore возвращают 403. Teachers API подключён: `GET /api/datasets/{id}/teachers`, фильтры `class_ids`, `textbook_ids`, `test_version`. Проверенный frontend `2d554f0` использует этот endpoint. Period опубликован и подключён: `settings.mode="period"`, snapshot `algorithm_version="period_v1"`; без mode используется `rules_v1`. JSON/CSV обоих режимов проверены после restart и восстановления. Примеры: `contracts/integrated-analytics-teachers.response.json`, `contracts/period-plan-preview.response.json`, `contracts/period-plan-saved.response.json`.

## 5. Что нужно Дамиру для публикации

1. Выбрать платформу и **согласованный проверенный SHA** со всеми нужными модулями. В `deploy/render.yaml` записана прежняя cloud-ветка; это необязательный пример. Если Render выбран, актуальную ветку и параметры задаёт Дамир после review. Иначе этот файл не используется.
2. Настроить постоянный диск, env, права appuser, один экземпляр, HTTPS/ingress и health `/api/health`. Сохранить `/api/...` при проксировании. Для uploads учесть лимит API 10 MiB CSV + 64 KiB multipart и согласованный timeout.
3. При отдельном UI согласовать VITE_API_BASE_URL и CORS_ORIGINS; настроить SPA fallback на стороне frontend для прямых `/plans/{id}` и Reload. Не подменять API errors HTML-страницей.
4. Подготовить synthetic report, проверить UI → API → report/CSV, read-only, ошибки/Retry, мобильные размеры, restart и restore. `scripts/check_release.py` рассчитан на **единый origin с React**; для раздельной схемы дополнительно проверяются оба origin, нельзя объявить весь сайт готовым по одному health. Если на публичном стенде намеренно включён `AI_PUBLIC_DEMO=true`, добавьте `--allow-public-ai`: проверка допустит ИИ-пояснения, но по-прежнему потребует закрытую запись. Без флага ИИ на публичном стенде считается блокером.
5. Организовать off-service backup и rollback к проверенному image/commit + совместимой копии БД. Выбор и оплата ресурсов, запуск, URL и эксплуатация — ответственность Дамира/владельца аккаунта.

Бекзат предоставляет/исправляет серверные контракты, транзакции, persistence/backup API и интеграцию аналитики/planner. Он не выбирает и не меняет deployment Дамира без согласования.
