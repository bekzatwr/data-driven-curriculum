# Бекзат — P1 backend, AI config и deployment

Проверка: **10 ноября 2026**. Дедлайн 11 ноября 23:59 UTC+5; freeze 18:00, внутренняя сдача 22:00. Ветка `feature/bekzat-p1-infrastructure`, база `integration/p0-server:b25891c`. Только синтетические данные. Production, paid resources и merge в main не выполнялись.

## A. Что сделано

| Задача | Результат | Файлы / проверенные API | Evidence / commit |
| --- | --- | --- | --- |
| Audit и безопасная интеграция | Выполнено; PR #1–4 открыты, submitted reviews/approve отсутствуют | main `3ebe857`, backend `d83ce28`, analytics `a2a89fa`, integration `b25891c`, frontend `68f5a56` | История сохранена; merge frontend `9967e3c` + `a8c889d` |
| Comments storage | Готово к review: общая SQLite, индексы, 500 max, стабильная сортировка, проверка принадлежности всех 7 типов целей | `collab/storage.py`, `collab/api.py`; GET/POST `/api/datasets/{id}/comments` | `ef4baaf`; реальные SQLite ownership/transaction/response tests |
| Атомарность comments | Полный response валидируется/сериализуется до INSERT; write transaction проверяет цель и квоту | `BEGIN IMMEDIATE`, rollback на ошибке; существующие данные не удаляются | Ошибки render/INSERT не оставляют comments; P0 atomic-save сохранён |
| Persistence и backup | Dataset, plan JSON/CSV и comments совпадают после restart, replacement и restore в новый volume | `scripts/verify_deployment.py`, `deploy/seed_demo_report.py`, существующий SQLite backup API | 15 Docker-групп; [протокол](bekzat-p1-deployment-check.local.json) |
| Anti-spam | 10 POST/min/IP, 60/min глобально; HTTP 429 + Retry-After; счётчики переживают restart | `collab/security.py`, `backend/app/config.py`, `backend/app/main.py` | `ef4baaf`; concurrency, sliding window, proxy spoof tests + реальный Docker HTTP |
| Ёмкость comments | 5000 глобально, 1000/dataset, 8 МиБ текстовых значений; DB+WAL budget 64 МиБ для новых comments; body 64 КиБ | `collab/storage.py`, `collab/security.py` | 409 quota / 413 body, включая chunked; P0 импорт не ограничивается квотой comments |
| Public demo | Comments и AI POST запрещены вместе с import/restore/save, до разбора тела и записи counters | READ_ONLY_DEMO/PublicDemoGuard; capabilities | Логический dump SQLite неизменен после запрещённых запросов |
| AI backend | Flags, quotas, server-only numeric aggregates, 30 КБ context, 20 с общий deadline, 503/502, redaction | `collab/ai.py`, `collab/context.py`, `collab/api.py`; GET `/api/ai/status`, POST `/api/datasets/{id}/ai/explain` | `ef4baaf`; offline/mock tests; **0 реальных provider calls** |
| AI account / live model | **Не подтверждены**: разрешённые ключи не предоставлены, реальных вызовов нет | GROQ/GEMINI runtime env; AI_ENABLED=false | Документация моделей проверена; имя модели не доказывает доступ аккаунта |
| Fullstack Docker | Собирает настоящий React PR #4; SPA/API/deep links, non-root, PORT, healthcheck, один worker | `Dockerfile`, `deploy/run_server.py`, `deploy/compose.yaml` | Build + HTTP E2E на `68f5a56`; UI владельца не редактировался |
| Deployment | Render Blueprint, env, volume, CORS, backup/restore/rollback подготовлены | `deploy/render.yaml`, `deploy/.env.example`, `deploy/README.md` | JSON Schema: 0 ошибок; 2 Compose config checks |
| Contracts и CI config | OpenAPI, примеры comments/offline AI/capabilities; feature branch и integration PR triggers | `contracts/*`, `scripts/export_contracts.py`, `.github/workflows/{backend,web}.yml` | Два экспортера воспроизводимы, повторный diff пуст |
| Документация / README | Новый GitHub README, точный API handoff, матрица UI, текущий отчёт | `README.md`, `docs/BEKZAT_P1_API.md`, `docs/MOBILE_ACCEPTANCE.md`, `docs/PUBLIC_DEPLOYMENT_READINESS.md` | Ссылки доступны в рабочей ветке; main обновляется только после review/merge |

### Первопричины рисков PR #4 и явные изменения контракта

Прототип принимал произвольный target_id, доверял роли ai от клиента и браузерному AI context; отсутствовали квоты и защита collab от public writes. Эти риски закрыты в отдельном PR, не скрытым изменением ветки Дамира.

POST comments принимает только роли teacher/methodist/admin и создаёт kind=human. Старые AI-записи читаются; новые неподтверждённые AI-комментарии не создаются. Target plan_topic имеет формат `<plan_id>:<topic_id>`, snapshot обязан принадлежать dataset из URL.

AI context теперь содержит селекторы, а не произвольные тексты/агрегаты. Сервер берёт проверенные показатели существующей аналитики; IDs, имена, комментарии и metadata наружу не отправляются. Только встроенный demo разрешён; импортированные datasets отклоняются. Непустой question временно запрещён (поле ≤500 сохранено); teachers/comments kinds — 503 до контракта владельцев. Нужен review Дамира/Тони; AI остаётся выключенным. Полная спецификация: [BEKZAT_P1_API.md](BEKZAT_P1_API.md).

Markdown UI использует React text nodes без raw HTML. Промпты Тони, формулы аналитики и правила Айданы не переписывались. Нет автоматического сохранения или изменения плана после AI-ответа.

## B. Что осталось

| Категория | Задача и владелец |
| --- | --- |
| Blocker P0 public | Дамир: учитывать plan_save/read_only в UI; добавить frontend test/lint, ограничить ожидание API и проверить Retry. Команда: review и финальная браузерная приёмка |
| Blocker P1 | Согласовать перечисленные contract changes; AI account/model/quota и методологию; выключить в UI неготовые модули по capabilities |
| Дамир | UI comments/AI, flags comments_write/ai_explain/teachers_api/period_planner_api; новый AI selectors payload; не сохранять роль ai от браузера; мобильные picker/export; static hero пометить как пример |
| Тони | GET teachers, формулы нагрузки, review методологии AI и безопасный teachers/comments context. Вместо него не реализовано |
| Айдана | Серверный period planner и tests; review atomic save/ограничений/защиты, финальный E2E. Вместо неё не реализовано |
| Владелец хостинга | Разрешить бюджет и deploy; создать диск/сервис; проверить ingress, HTTPS, rights, restart и off-service backup |

Учительская страница и period planner уже присутствуют в frontend как **клиентские прототипы**, общего серверного API нет. Capabilities явно сообщает false. На freeze 11 ноября 18:00 Дамиру нужно скрыть неготовое; backend flags не меняют отображение чужого UI автоматически.

`TRUSTED_PROXY_CIDRS` пуст по умолчанию; Uvicorn не переписывает TCP peer. Docker spoof/XFF проверен. **Render ingress не проверен живьём**, поэтому не обещаем индивидуальную IP-квоту за его proxy: пользователи одного proxy могут разделять лимит. Публичная запись всё равно запрещена. Открытие публичных comments требует отдельного защищённого режима и согласования, сейчас его нет.

## C. Тесты

Числа ниже — результаты завершённых запусков; строки subsets входят в общий pytest и не суммируются с ним.

| Test | Passed | Failed | Skipped | Evidence |
| --- | ---: | ---: | ---: | --- |
| Полный pytest, Linux/Python 3.13 | **301** | **0** | **0** | 192,09 с; дополнительно 26 subtests passed; один прежний TestClient/httpx warning |
| Existing P0 regression, subset | 224 | 0 | 0 | Включая 28 atomic-save, 8 percent boundary и 15 public regression cases |
| P1 collab, subset | 77 | 0 | 0 | 8 адаптированных исходных + 69 новых в backend/tests/test_collab_hardening.py |
| Исходные planner unittest отдельно | 7 | 0 | 0 | python -m unittest discover -s tests -p test_planner.py |
| SQLite comments persistence | 1 сценарий | 0 | 0 | Настоящий файл, повторная фабрика, backup/restore; дополнительно Docker restart/recreate |
| Backup/restore | 1 сценарий | 0 | 0 | Online SQLite backup, off-volume copy, новый volume, integrity и равенство JSON/CSV/comments |
| Rate limit | Пройдено в 77 | 0 | 0 | 11-й запрос, Retry-After, несколько IP, глобальные квоты, 20 concurrent attempts, restart, proxy; Docker HTTP |
| AI without keys / mock | Пройдено в 77 | 0 | 0 | 503 offline, 502 provider/deadline, selectors, PII/secret rejection, quota, no autosave |
| Docker fullstack rehearsal | **15 групп** | 0 | 0 | ddc-check-275f4c3066, настоящий web/68f5a56; [JSON](bekzat-p1-deployment-check.local.json) |
| API contract exporters | 2 | 0 | 0 | Общий и analytics export; повторная генерация без diff |
| Frontend TypeScript / build | 2 команды | 0 | 0 | npm run typecheck; npm run build (tsc + Vite), Node 22 в Docker |
| Render JSON Schema / Compose | 3 проверки | 0 | 0 | Schema 0 errors; root + fullstack local override |
| React P0 browser E2E | 1 сценарий | 0 | 0 | Два CSV → отчёт/CSV, ручные правки, comment, restart/deep link; [матрица](MOBILE_ACCEPTANCE.md) |
| Frontend unit tests / lint | — | — | — | **NOT RUN**: scripts отсутствуют; это не pytest skipped |
| Физические телефоны / Safari / macOS / внешний HTTPS | — | — | — | **NOT RUN**: устройств/опубликованного сервиса нет |

Первые диагностические прогоны: Windows full pytest 300 passed / 1 failed из-за ошибочного нового теста (GET списка планов, которого нет); тест заменён проверкой настоящей SQLite, не ослаблением поведения. До этого focused 73/1 выявил проверку escaped JSON вместо разобранного тела. Первый QA image не содержал tests из-за production .dockerignore (0 collected), после исправления только тестового context полный Linux прогон прошёл. Один ранний Docker restore-container не достиг health за 90 с, application log был пуст; таймаут не увеличивался. Следующие два полных прогона прошли, включая restore. Эти ранние ошибки не записаны как успешные проверки.

### Реальный сценарий

Сервер: 120 синтетических учеников, 1440 строк, 720 пар; equations difference gain 8 п.п.; план 24 часа. После restart/recreate/restore совпадают набор, аналитика, сравнение, snapshot, CSV и comments. Public запрещённые действия не меняют dump базы. Upload limits и traversal защищены существующими regression tests.

Браузер: dataset `7fa61eef-6d14-4ecf-ad3a-934b57803797`, ручной plan `d3b1de24-2fe0-4ef7-9e48-0c46c78b61a2`, скачанный CSV и комментарий восстановлены после restart. Проверены шесть ширин 360/390/430/768/1366/1920; это viewport QA, не физический телефон. После нового frontend commit повторены загрузка существующего snapshot/comments после замены контейнера, все шесть измерений layout и визуальная проверка отчёта. Скриншоты и точные ограничения приведены в мобильной матрице.

## D. Deployment

**Fullstack image готов локально. Render-конфигурация готова, но сам сервис и диск не созданы.** Один Docker Web Service: React + FastAPI, один worker/instance, SQLite на /app/data. Переезд на PostgreSQL не нужен для текущего MVP и не выполнялся.

Рекомендуемый Render compute 0.5c-512mb: $7/месяц + persistent disk 1 GB: $0,25/месяц; ориентир **$7,25/месяц**, без дополнительных usage/tax. [Тарифы](https://render.com/pricing). Free с ephemeral filesystem не обеспечивает нужную сохранность. [Free](https://render.com/docs/free), [Disks](https://render.com/docs/disks). Бесплатный проверенный вариант — приватный локальный Docker, без публичного HTTPS.

Обязательные значения public:

```ini
APP_TARGET=fullstack
FRONTEND_DIR=web
VITE_API_BASE_URL=
PORT=8000
DATABASE_PATH=/app/data/curriculum.sqlite3
DATA_MOUNT_PATH=/app/data
REQUIRE_PERSISTENT_STORAGE=true
REQUIRE_P0=true
PUBLIC_DEMO=true
READ_ONLY_DEMO=true
CORS_ORIGINS=
TRUSTED_PROXY_CIDRS=
P1_COMMENTS_ENABLED=true
AI_ENABLED=false
AI_ACCOUNT_VERIFIED=false
AI_PROVIDERS=groq,gemini
```

WEB_DIST_DIR=/app/web задан образом. API-ключи public стенду не нужны. GROQ_API_KEY/GROQ_MODEL/GEMINI_API_KEY/GEMINI_MODEL — только runtime приватного сервера после разрешённой проверки аккаунта и квот, никогда VITE/build args/Git. [Groq models](https://console.groq.com/docs/models), [Gemini model](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite).

Вручную после review и разрешения владельца:

1. Закрыть UI-блокеры, зафиксировать прошедший CI commit; согласовать расходы и публикацию.
2. Создать Render Blueprint из deploy/render.yaml с нужной веткой; disk 1 GB /app/data, один instance, /api/health, auto-deploy off. Создание запускает первый deploy.
3. Проверить build, mount/permissions и health; выполнить в Shell `python deploy/seed_demo_report.py`, сохранить plan_id и ссылки.
4. Проверить фактический HTTPS URL командой `scripts/check_release.py --mode public --require-https`, затем браузером с другого устройства. Сервер и React одного origin, CORS_ORIGINS пуст.
5. Сделать online backup, вынести копию за пределы сервиса, restart, сверить те же ID/CSV/comments; восстановление только в новый файл/volume.
6. При проблеме P1 выключить AI_ENABLED/P1_COMMENTS_ENABLED, оставить public read-only; при rollback использовать проверенный image с public guard и совместимую копию БД. Не удалять volume и новые таблицы.

Подробные команды: [deploy/README.md](../deploy/README.md). Внешней HTTPS-ссылки нет; production deploy и платные ресурсы не запускались.

## E. Git

- Рабочая ветка: **feature/bekzat-p1-infrastructure**, целевая **integration/p0-server**.
- Основной код P1: **ef4baafec7e0dce00bde17d911d6901f0bc63b20**.
- Включение PR #4: **9967e3c1a92446fa151162f42587e9646b8754ee**, актуального оформления: **a8c889d27e31acc45fdc79c1704af55b0225289f**.
- Конфликт при объединении PR #4 и public deployment: backend/app/main.py (lifespan/capabilities). Сохранены guard, preseed и collab initialization; проверены вместе. Последний frontend merge без конфликтов.
- Сравнение web/ с 68f5a56 — без diff; analytics, planner/service.py, rules.py, storage.py, исходные planner tests и atomic-save tests совпадают с integration/p0-server.
- PR #1–4 не merged; submitted reviews нет, approve Айданы для PR #1 отсутствует. CI их проверенных heads успешен; frontend 68f5a56: [Frontend](https://github.com/bekzatwr/data-driven-curriculum/actions/runs/42805125644), [Planner](https://github.com/bekzatwr/data-driven-curriculum/actions/runs/42805126327), [Toni](https://github.com/bekzatwr/data-driven-curriculum/actions/runs/42805125625).
- Новый PR и CI текущей ветки фиксируются после push; результаты чужих heads не являются CI этой ветки. [Actions рабочей ветки](https://github.com/bekzatwr/data-driven-curriculum/actions?query=branch%3Afeature%2Fbekzat-p1-infrastructure).
- Обычный push, без force; main/backend/analytics/planner/frontend ветки не переписываются. Merge только командой после review.

## F. Вердикт

**GO для локального демо.** Серверная часть Бекзата готова к review и интеграции: P0 сохранён, comments/backup/anti-spam работают, AI безопасно выключен, настоящий fullstack image собран.

**Публичный deploy остаётся заблокирован** перечисленными UI/review/hosting проверками. Готовность локального Docker и эмуляция ширин не выдаются за запущенный сайт, проверенный Render persistence или испытания физического iPhone.
