> Следующий этап: [BEKZAT_CLOUD_READINESS.md](BEKZAT_CLOUD_READINESS.md), актуальный frontend `c1e6e01`, новый cloud PR. Ниже сохранён протокол предыдущей сборки.

# Готовность публичного демостенда · 10 ноября 2026

**GO для локального демо. Публичный deploy пока не разрешён.** Настоящий React Дамира опубликован и включён в `feature/bekzat-p1-infrastructure`; прежний блокер отсутствия frontend снят. Актуальная приёмка и границы ответственности — [BEKZAT_P1_STATUS.md](BEKZAT_P1_STATUS.md), рабочие интерфейсы — [BEKZAT_P1_API.md](BEKZAT_P1_API.md).

## Что подготовлено

- FastAPI, аналитика Тони, planner Айданы, атомарный save, CSV/JSON отчёты и comments используют общую SQLite.
- Один Docker image собирает **настоящий web/ из PR #4**, без тестовой оболочки. Алгоритмы и UI владельцев не переписывались.
- Корень сайта, assets, /api/health и прямой /plans/{id} работают. Volume смонтирован целиком в /app/data; запуск от appuser, один worker/instance.
- Публичные import/restore/save/comments/AI POST запрещены. Preview, чтение demo, подготовленного отчёта и CSV разрешены. AI по умолчанию выключен.
- Реальный HTTP E2E подтвердил сохранность datasets, аналитики, плана, CSV и comments после restart, пересоздания контейнера и восстановления off-volume backup в **новый** volume.
- Render Blueprint проверен по официальной JSON Schema; Compose проверен. Новый README, инструкции env, backup/restore/rollback опубликованы в этой рабочей ветке.

[Машинный Docker-протокол P1](bekzat-p1-deployment-check.local.json) описывает серверные проверки; его `full_p0_verified=false` означает, что скрипт не управляет браузером. Настоящая браузерная приёмка оформлена [отдельно](MOBILE_ACCEPTANCE.md). Исторический public-deployment-check.local.json относится к раннему P0 без React и не является итоговым результатом этой ветки.

## Что блокирует внешний сайт

| Блокер | Ответственный | Условие закрытия |
| --- | --- | --- |
| UI сохраняет активные save/comments при запрете записи | Дамир | Учесть capabilities; понятные отключённые действия |
| AI и клиентские P1-прототипы доступны в навигации | Дамир + владельцы API | Скрыть по flags; согласовать новые AI selectors и provenance |
| Нет frontend test/lint scripts | Дамир | Добавить и выполнить проверки |
| Нет командного approve | Айдана и команда | Review backend/integration/P1, без автоматического merge |
| Нет созданного Render-сервиса/диска | Владелец | Отдельное разрешение расходов и публикации |
| Нет проверки реального ingress/HTTPS/телефонов | Команда после разрешённого deploy | Реальный URL, disk permissions, restart, внешний ноутбук/телефон |

## Хостинг

Один Render Docker Web Service `0.5c-512mb` + persistent disk 1 GB: ориентир **$7,25/месяц** до дополнительных начислений. [Тарифы Render](https://render.com/pricing). Render Free не предоставляет постоянный диск и не подходит для сохраняемой SQLite. [Ограничения Free](https://render.com/docs/free).

Ресурсы не создавались, внешней HTTPS-ссылки пока нет. Локальные Docker volumes уже проверены; это не доказательство наличия диска в Render. Для полного сценария с записью используется отдельный локальный writable стенд. Публичную защиту ради демонстрации не отключать.

Публикация, точные переменные и восстановление — [deploy/README.md](../deploy/README.md). Владелец сначала получает review и разрешает бюджет, затем применяет Blueprint, готовит синтетический отчёт и проверяет HTTPS/restart/off-service backup. Создание Blueprint запускает первый deploy даже при выключенном auto-deploy.
