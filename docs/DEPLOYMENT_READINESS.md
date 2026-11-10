# Deployment readiness — 10 ноября 2026

**Вердикт:** конфигурация готова к интеграции оставшихся модулей и review. Production не развёрнут, платные ресурсы не созданы, публичный туннель не запущен. Полный пользовательский P0 пока заблокирован отсутствием опубликованных frontend и аналитики.

## Архитектура и область изменений

Аудит выполнен от `backend/bekzat:f274142`, `main:3ebe857`. FastAPI, SQLite WAL, импорт двух CSV, планировщик Айданы, JSON/CSV отчёта и backup API существуют. Общий сервер уже умеет отдавать собранную SPA через `WEB_DIST_DIR`. React исходники/package.json не опубликованы; analytics APIRouter отсутствует. Ветки `analytics/toni`, `frontend/damir`, `planner/aidana` при проверке на `7660b17`; планировщик Айданы получен из main.

Изменены только deployment/CI/документация: Docker build stages и запуск, проверка mounted storage, Compose, Render Blueprint, изолированная Docker-репетиция и release precheck. Код `backend/`, `planner/`, исходные тесты и OpenAPI-контракты не изменены относительно f274142. PostgreSQL-миграция не нужна и не выполнялась. Чужие ветки не изменены.

Рекомендуемый облачный путь — один Docker Web Service на Render `0.5c-512mb` + persistent disk 1 GB, около $7,25/месяц до дополнительных начислений. React + API работают с одного HTTPS-origin, SQLite и планы хранятся на диске. Бесплатный резерв — тот же контейнер с volume на ноутбуке через временный Cloudflare Quick Tunnel. Railway trial возможен при доступном кредите/подходящем аккаунте; Supabase требует отдельной PostgreSQL-миграции и backend-хостинга. Обоснование и источники: [deployment README](../deploy/README.md).

## Что передано

| Файл | Назначение |
| --- | --- |
| [Dockerfile](../Dockerfile) | Backend по умолчанию; fullstack npm build после поступления клиента |
| [deploy/compose.yaml](../deploy/compose.yaml) | Локальный полный сайт, отдельный volume, loopback, один процесс |
| [deploy/render.yaml](../deploy/render.yaml) | Подготовленный платный Blueprint с постоянным диском; не применён |
| [deploy/.env.example](../deploy/.env.example) | Все настройки Compose и безопасные значения по умолчанию |
| [deploy/run_server.py](../deploy/run_server.py) | PORT, writable/mounted storage, технический P0 gate, exec Uvicorn |
| [scripts/check_release.py](../scripts/check_release.py) | Read-only precheck health/capabilities/OpenAPI/frontend, exit 2 при блокерах |
| [scripts/verify_deployment.py](../scripts/verify_deployment.py) | Воспроизводимая локальная Docker-репетиция, только синтетические данные |
| [deploy/README.md](../deploy/README.md) | Сравнение хостингов, переменные, публикация, backup/restore, rollback, финальная приёмка |

## Результаты проверки

Среда: Windows, Docker Desktop Linux engine 29.1.5, Python 3.13.3. Повторный pytest: **127 passed, 1 warning, 66,37 с**. Предупреждение TestClient/HTTPX прежнее; закреплённые зависимости не изменены.

Финальная локальная Docker-репетиция `ddc-check-abe875ecf9` завершилась с кодом 0. [Машинный протокол](deployment-check.local.json). Проверено:

1. Сборка backend и fullstack-упаковки; fullstack использует временный тестовый npm-проект, не frontend Дамира.
2. Отказ запуска без постоянного mount; отдельные отказы при отсутствии frontend и маршрутов аналитики.
3. Запуск непривилегированным пользователем, `no-new-privileges`, удалённые Linux capabilities, нестандартный `PORT=8765`.
4. SPA fallback и assets, отсутствие HTML вместо ошибок API/JS, OpenAPI, разрешённый и запрещённый CORS origins.
5. Release precheck не принимает тестовый frontend за готовый продукт.
6. Реальный multipart HTTP: два синтетических CSV → preview/import → повтор без дубля → filters → перераспределение 24 часов → сохранённый план и CSV; строки CSV соответствуют часам сохранённого плана.
7. Те же dataset_id, plan_id и побайтно тот же CSV после restart **и удаления/создания контейнера с тем же volume**.
8. Согласованный backup вынесен на хост и восстановлен в **новый volume**; исходный набор, JSON-план и CSV доступны без изменений.
9. Docker healthcheck подтвердил healthy на нестандартном PORT.
10. Compose config корректен; Render YAML проверен по [официальной JSON Schema](https://render.com/schema/render.yaml.json): 0 ошибок. Проверка схемы не создаёт облачный ресурс.

Временные контейнеры/volumes теста удалены, существующие Docker-проекты и БД не использовались. Локальные логи и синтетический backup находятся в игнорируемом `data/deployment-checks/ddc-check-abe875ecf9/`. SHA-256 backup: `e5687bb76610ded8289734953c0a7508f91f04e82eb5476806091935b1866dcb`.

В CI добавлена `deployment-rehearsal`, повторяющая Docker-проверку на Linux. Результат для опубликованного SHA смотреть в Checks PR №1; успешность локальной проверки не подменяет результат CI.

## Полный сценарий и блокеры

| Этап | Фактический результат |
| --- | --- |
| Два CSV → импорт | Проверен локально в настоящем контейнере |
| Аналитика тем | Нет опубликованного модуля Тони; не проверена |
| Сравнение учебников | Нет опубликованного модуля Тони; не проверено |
| Перераспределение часов | Модуль Айданы проверен через HTTP |
| Сохранённый план → отчёт | JSON и CSV проверены после restart/recreate/restore |
| React UI на другом ноутбуке | Нет исходников Дамира; публичного deploy нет, проверка не выполнена |
| Облачный диск / HTTPS | Конфигурация подготовлена; проверка фактического сервиса ожидает P0 и выбора хостинга |

До публикации нужны: PR Тони с реальными схемами и алгоритмами; PR Дамира с подтверждением npm/Node/output directory и относительного API; совместный E2E в браузере; review команды; разрешение на оплату при выборе Render. Айдане остаётся review общего подключения/хранения и подтверждение границ часов из P0-отчёта.

При полном сценарии `READ_ONLY_DEMO=false`: публичный импорт в текущем коде не имеет пользовательской авторизации. Разрешены только синтетические данные, для закрытого доступа нужен внешний gateway. Backup хранить вне сервиса; не удалять volume, не копировать живой SQLite обычным cp вместо backup API. Все команды публикации и восстановления приведены в [инструкции](../deploy/README.md).

Дедлайн: **11 ноября 2026, 23:59 UTC+5**. Подготовленная инфраструктура сокращает оставшуюся работу до подключения опубликованных модулей, review, финальной проверки и согласованной публикации.
