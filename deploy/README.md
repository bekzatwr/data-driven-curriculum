# Публикация Data Driven Curriculum

Подготовка от 10 ноября 2026. Ветка `deployment/bekzat-cloud-readiness`, основана на `integration/p0-server:b25891c`, включает настоящий React из PR #4 (`03395ef`). **Deploy не выполнен. Нужны review и устранение UI-блокеров публичного режима.** [Текущий cloud audit и 12 шагов публикации](../docs/BEKZAT_CLOUD_READINESS.md) · [Исторические проверки](../docs/PUBLIC_DEPLOYMENT_READINESS.md) · [Frontend handoff](../docs/MOBILE_ACCEPTANCE.md).

## Архитектура и стоимость

Один Docker Web Service: React собирается в `dist`, FastAPI раздаёт его и `/api` с одного HTTPS origin. Один Uvicorn worker и один instance. SQLite, `-wal`, `-shm` и снимки планов находятся в `/app/data` на постоянном диске. TLS завершает Render; отдельный домен не обязателен.

Рекомендация: Render `0.5c-512mb` ($7/месяц), persistent disk 1 GB ($0,25/месяц), Hobby workspace ($0). Базовый ориентир **$7,25/месяц**, дополнительные bandwidth/build usage, налоги и условия кабинета проверяет владелец перед созданием. [Официальные тарифы](https://render.com/pricing?trk=article-ssr-frontend-pulse_little-text-block).

Render Free не поддерживает persistent disk; SQLite исчезает после restart/redeploy/idle spin-down. Для данного сценария Free непригоден. [Ограничения Free](https://render.com/docs/free). Диск привязан к одному экземпляру; deploy с диском может давать краткий простой. [Диски](https://render.com/docs/disks). PostgreSQL не нужен для одного экземпляра текущего MVP; замена SQLite не выполнялась.

Бесплатно можно показать полный сценарий локально с Docker volume. Это не постоянный публичный HTTPS-хостинг. Публикация локального сервера через туннель требует отдельного согласования; writable-порт не открывать в интернет. Никакие туннели, платные ресурсы или домены в этой задаче не создаются.

## Два режима демонстрации

| Режим | PUBLIC_DEMO | READ_ONLY_DEMO | Доступ |
| --- | --- | --- | --- |
| Публичный | true | true | Синтетические данные, аналитика, сравнение, preview, чтение подготовленного JSON/CSV |
| Локальный | false | false | Два CSV, preview/import, ручные правки, save, отчёт и export |

`PUBLIC_DEMO=true` с `READ_ONLY_DEMO=false` останавливает entrypoint. В публичном режиме все изменяющие API-запросы получают 403 до разбора тела. Исключения: POST demo — чтение набора, созданного при запуске; POST plans/preview — расчёт без сохранения. Импорт, dry-run импорта, restore, save, comments POST и AI POST запрещены. CORS не является авторизацией.

Пользовательскую авторизацию не добавляли. Публичный стенд запускается только с новой синтетической БД. Существующие локальные базы и реальные школьные данные не загружать. Полный сценарий записи показывается на отдельном локальном стенде; публичную защиту ради показа не выключать.

## Environment variables

| Переменная | Render | Назначение |
| --- | --- | --- |
| APP_TARGET | fullstack | Build arg: выбрать финальный образ React + API |
| FRONTEND_DIR | web | Build arg: каталог настоящего frontend; уточнить с Дамиром |
| VITE_API_BASE_URL | пусто | Build arg: относительный `/api`, без localhost |
| PORT | 8000 | Прослушивание 0.0.0.0; healthcheck использует тот же порт |
| DATABASE_PATH | /app/data/curriculum.sqlite3 | База внутри диска |
| DATA_MOUNT_PATH | /app/data | Точка монтирования persistent disk |
| REQUIRE_PERSISTENT_STORAGE | true | Отказ запуска без настоящего mount |
| REQUIRE_P0 | true | Отказ запуска без frontend build и analytics routes |
| READ_ONLY_DEMO | true | Публичная политика без импорта и сохранения |
| PUBLIC_DEMO | true | Защита от случайного включения публичной записи |
| CORS_ORIGINS | пусто | Один origin; внешние frontend origins не разрешены |
| TRUSTED_PROXY_CIDRS | пусто | Не доверять XFF, пока ingress не проверен; Uvicorn `--no-proxy-headers` |
| P1_COMMENTS_ENABLED | true | Чтение comments; запись всё равно запрещена READ_ONLY_DEMO |
| AI_ENABLED | false | Выключить внешние AI-вызовы |
| AI_ACCOUNT_VERIFIED | false | Подтверждение разрешённого аккаунта/модели владельцем, не автоматическая проверка |
| AI_PROVIDERS | groq,gemini | Порядок провайдеров в приватном режиме |
| GROQ_API_KEY / GEMINI_API_KEY | не задаются | Не нужны публичному read-only стенду; runtime secrets только после разрешения владельца |
| GROQ_MODEL / GEMINI_MODEL | openai/gpt-oss-120b / gemini-3.5-flash-lite | Значение конфигурации не доказывает доступ аккаунта |
| WEB_DIST_DIR | /app/web | Уже задаётся Docker fullstack stage; вручную не требуется |

Render передаёт env и как Docker build args. В Dockerfile объявлены только несекретные build args; секреты нельзя помещать в `VITE_*`, исходники, `.env` frontend или аргументы сборки. [.dockerignore](../.dockerignore) исключает env/БД/ключи, включая вложенные каталоги. Исходники React входят в ветку без секретов; server keys не передаются в frontend. Не вводить ключи в Git или `VITE_*`. [Docker on Render](https://render.com/docs/docker).

## Локальная приёмка настоящего frontend

1. React и lockfile уже опубликованы и включены из `03395ef`. Build/typecheck есть; test/lint scripts пока ожидаются от Дамира. Исходники UI не изменялись Бекзатом.
2. Проверить исходники: `python scripts/check_frontend_handoff.py --directory web`. Код 2 означает блокер; команда сама не выполняет frontend tests.
3. В `web` выполнить `npm ci`, `npm test -- --run`, `npm run typecheck`, `npm run lint`, `npm run build`. Дамир должен обеспечить совместимый одноразовый test script (без watch). Секреты и абсолютные localhost URL недопустимы.
4. Скопировать `deploy/.env.example` в `deploy/.env`. Этот файл не коммитить. Сохранить `APP_TARGET=fullstack` и `REQUIRE_P0=true`.

Публичная политика на loopback:

```bash
docker compose --env-file deploy/.env -f deploy/compose.yaml up --build -d --wait --wait-timeout 120
docker compose --env-file deploy/.env -f deploy/compose.yaml exec -T app python deploy/seed_demo_report.py
python scripts/check_release.py --mode public --base-url http://127.0.0.1:8080
```

`seed_demo_report.py` запускает владелец из контейнера. Только встроенные синтетические CSV; обычные алгоритмы Тони/Айданы, атомарное сохранение и валидация. Повторный запуск переиспользует отчёт, возвращает `dataset_id`, `plan_id`, `report_url`, `csv_url`. Сохранить эти ссылки для публичного показа; HTTP save остаётся закрытым.

Отдельный **локальный** проект с отдельным volume и портом 8081 (PowerShell):

```powershell
$env:HOST_PORT='8081'
docker compose --env-file deploy/.env -f deploy/compose.yaml -f deploy/compose.local.yaml up --build -d --wait --wait-timeout 120
python scripts/check_release.py --mode local --base-url http://127.0.0.1:8081
Remove-Item Env:HOST_PORT
```

Не задавать `-p`/`COMPOSE_PROJECT_NAME`, совпадающий с публичным стендом. Override задаёт отдельное имя `ddc-private-local`, отдельный volume и writable-режим. Порт привязан к 127.0.0.1, не к 0.0.0.0. Через настоящий React выполнить полный CSV → Import → Overview → Topics → Comparison → Planner → Save → Report → Export. Проверить ручные правки, повторное открытие, restart и backup/restore.

## Что делает владелец Render после разрешённой публикации

1. Получить готовый frontend, успешные проверки и review команды/Айданы; зафиксировать проверенный commit. В этой задаче merge в main не выполняется.
2. Отдельно разрешить создание платного сервиса и публичный deployment. Проверить тариф, workspace и billing limits. **Создание Blueprint запускает первый deploy даже при auto-deploy off.**
3. В Render подключить GitHub, выбрать репозиторий и ветку с проверенным commit. Создать Blueprint с путём `deploy/render.yaml` либо Docker Web Service с теми же настройками. Текущая подготовленная ветка — `deployment/bekzat-cloud-readiness`; не выбирать устаревший backend/bekzat.
4. Frankfurt, один instance `0.5c-512mb`, disk 1 GB, mount `/app/data`, health `/api/health`, Dockerfile `./Dockerfile`, context `.`, auto-deploy off. Сверить env по таблице. Не добавлять disk-dependent pre-deploy command: диск доступен только работающему сервису.
5. Проверить build log: настоящий npm build, fullstack stage, никаких секретов. Runtime должен пройти mount/writeability/P0/public-policy checks и запуститься непривилегированным пользователем. При ошибке прав диска исправлять права средствами платформы, не отключать persistent guard.
6. В Shell работающего сервиса выполнить `python deploy/seed_demo_report.py`, сохранить ссылки отчёта. Не запускать отдельный job для доступа к диску.
7. Получить фактический `https://<service>.onrender.com` в кабинете. Render предоставляет TLS и HTTP→HTTPS redirect автоматически. [TLS Render](https://render.com/docs/tls). До этого момента рабочая внешняя ссылка не существует.
8. Выполнить `python scripts/check_release.py --mode public --require-https --base-url https://<service>.onrender.com`. Проверить из браузера отсутствие CORS/mixed content, прямые SPA URL и API. Скрипт делает только чтение и не заменяет browser E2E.
9. С другого ноутбука и телефона на мобильном интернете проверить публичный сценарий и скачивание CSV. Save/import должны быть отключены интерфейсом и возвращать 403 через API. Полный сценарий с записью показать на отдельном loopback-стенде.
10. Сделать backup, перезапустить сервис из кабинета, сверить те же dataset_id/plan_id/JSON/CSV; выполнить восстановление копии в отдельный файл. Зафиксировать URL, commit, время, браузер/ОС и доказательства.

**Не публиковать при незавершённых шагах 1–2.** Требуемый paid resource не создан, домен не назначен, HTTPS с другого устройства пока не проверен.

## Безопасное хранение, backup и restore

Монтировать весь `/app/data`, включая WAL/SHM. Не удалять persistent disk, не выполнять `docker compose down -v`, не масштабировать SQLite на несколько instances. Новый публичный volume содержит только встроенные синтетические данные.

Перед публикацией, изменением БД и защитой создать согласованную копию через SQLite backup API. Держать последнюю и предрелизную копии **вне сервиса**, ещё на доверенном компьютере/носителе. Автоматический backup scheduler не развёрнут; обязанность владельца — выполнить копирование по инструкции. Render disk snapshots не заменяют согласованную копию SQLite.

PowerShell, локальная публичная конфигурация:

```powershell
$stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
New-Item -ItemType Directory -Force data/offsite-backups | Out-Null
docker compose --env-file deploy/.env -f deploy/compose.yaml exec -T app python -m backend.app.db.backup --output /app/data/backups/$stamp.sqlite3
docker compose --env-file deploy/.env -f deploy/compose.yaml cp app:/app/data/backups/$stamp.sqlite3 data/offsite-backups/$stamp.sqlite3
Get-FileHash data/offsite-backups/$stamp.sqlite3 -Algorithm SHA256
```

На Render выполнить Python-команду в Shell/SSH и забрать копию через SCP/SFTP по реквизитам кабинета. Не создавать публичный endpoint для backup. JSON-пакет набора не содержит все сохранённые планы и не заменяет полный backup.

Восстановление: загрузить копию в `/app/data/backups/`, выполнить `python -m backend.app.db.backup --source /app/data/backups/<copy>.sqlite3 --output /app/data/recovered-<stamp>.sqlite3`. Команда проверяет целостность и отказывается перезаписывать файл. Установить `DATABASE_PATH` на новый файл, перезапустить, проверить старые ID и CSV; старую БД сохранить. На новом volume проверить права appuser. Для rollback кода использовать ранее проверенный SHA и совместимую копию базы; автоотката миграций нет.

## P1: эксплуатация, backup и rollback

Комментарии `collab_comments` и ограниченные rate counters находятся в той же DATABASE_PATH, что datasets и `aidana_plan_snapshots`. Backup API копирует все таблицы и зафиксированный WAL; dataset package JSON не является полным backup комментариев/планов. Восстановление — в новый файл/volume, проверка datasets + plan JSON/CSV + comments, затем переключение; существующая БД не перезаписывается.

До обновления сохранить off-service backup и проверенный предыдущий image digest. При проблеме P1 сначала установить `AI_ENABLED=false`, `P1_COMMENTS_ENABLED=false`, сохранить `READ_ONLY_DEMO=true`; новые таблицы не удалять. При откате к проверенной P0-сборке с PublicDemoGuard дополнительные таблицы остаются в БД и игнорируются. Никогда не откатывать к прототипу, разрешающему публичную запись. Не уменьшать `user_version` и не заменять рабочую БД файлом из Git.

Для writable comments публичного разрешения нет. Потребуются отдельные аутентификация/ограничение доступа, подтверждение proxy CIDRs и review; текущая конфигурация специально не открывает такой режим. Локальная конфигурация с записью привязана к loopback.

Ключи AI не проверялись реальными вызовами, не создавались и не публиковались. Доступность моделей подтверждена только документацией [Groq](https://console.groq.com/docs/models) и [Gemini](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite?authuser=0); доступ и квоту конкретного аккаунта проверяет владелец. Не включать AI до review контракта и методологии Тони. [Лимиты и API](../docs/BEKZAT_P1_API.md), [итоговая готовность](../docs/BEKZAT_P1_STATUS.md).
