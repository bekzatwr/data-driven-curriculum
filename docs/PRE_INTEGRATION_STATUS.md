# PRE-INTEGRATION STATUS — Data Driven Curriculum

Срез: **10 ноября 2026, 13:11 UTC / 18:11 UTC+5**. Дедлайн: **11 ноября 2026, 23:59 UTC+5**.

**Этап — подготовка, не Release Candidate.** Дамир и Тони продолжают разработку; название PR #9 «final» и `draft=false` не означают согласованное завершение. Незавершённые PR в этой задаче не объединялись. К финальной интеграции всего объёма и публикации сайта команда пока не готова.

Рабочая ветка Бекзата: `chore/bekzat-pre-integration`, создана от **PR #8 / `024d422c52fac3922af5b8896ebfc8f358bd3895`**. В тестируемой базе уже есть React `03395ef`, опубликованный ранее. PR #9 `f6eb7d3` прочитан отдельно, **не включён**. Источники: [Git/CI audit JSON](pre-integration-audit.json), [свежая Docker-репетиция](pre-integration-docker.local.json).

## 1. Что готово сейчас

| Модуль Бекзата / опубликованный P0 | Проверенное состояние |
| --- | --- |
| Backend / CSV | Два CSV, preview/import, ограничения, ошибки строк, идемпотентность, реальные analytics routes |
| Проценты и planner P0 | `100 * (score / max_score)`, полный балл 0.69/0.69, sum/min/max/locked/±2, серверная проверка правок |
| Атомарность | Snapshot, JSON и response проверяются до записи; ошибка не оставляет частичный план/comment |
| SQLite | Общая DATABASE_PATH, WAL, короткие соединения, dataset + snapshots + comments + rate counters |
| Comments | Принадлежность target набору/плану, строгие роли/длины, квоты и стабильное чтение |
| Anti-spam | 10 comments/min/IP, глобальные лимиты, 429 + Retry-After, сохранение rate state, защита от поддельного XFF |
| AI | По умолчанию disabled; публичный POST закрыт, внешних вызовов в этой проверке 0 |
| Docker | Настоящий React + FastAPI, non-root, один worker, health, динамический PORT, SPA и CORS |
| Backup/restore | Согласованный SQLite backup с WAL; восстановление нового файла/volume с теми же данными, JSON/CSV и comments |
| API contracts | OpenAPI и analytics exporters воспроизводимы; новые teachers/period API не выдаются за существующие |

`backend/app`, `planner`, `analytics`, `collab`, `web/` и `contracts/` в этой ветке не изменялись. Безопасная правка своей инфраструктуры: backend CI теперь запускается и у PR, направленного в `deployment/bekzat-cloud-readiness`. Никакие проверки не отключены.

## 2. Зависимости PR #1–#9

Все девять PR открыты, не объединены; submitted reviews отсутствовали в проверенном срезе. GitHub показывал `mergeable=true` **относительно указанной базы каждого PR** — это не проверка совместимости всех PR вместе.

| PR | HEAD / база | Что уже включено / что ещё требуется |
| --- | --- | --- |
| [#1](https://github.com/bekzatwr/data-driven-curriculum/pull/1) | `d83ce28` → main | Backend и atomic-save fix уже являются предками #3/#4/#5/#6/#8/#9 |
| [#2](https://github.com/bekzatwr/data-driven-curriculum/pull/2) | `a2a89fa` → main | Опубликованная P0-аналитика уже внутри #3/#4/#5/#6/#8/#9; новые работы Тони ещё ожидаются |
| [#3](https://github.com/bekzatwr/data-driven-curriculum/pull/3) | `b25891c` → main | Объединяет #1 + #2; база серверной линии, уже внутри #4/#5/#6/#8/#9 |
| [#4](https://github.com/bekzatwr/data-driven-curriculum/pull/4) | `03395ef` → integration/p0-server | Этот frontend целиком включён в #8 и #9; в #6 есть только более ранний `68f5a56` |
| [#5](https://github.com/bekzatwr/data-driven-curriculum/pull/5) | `2e6f375` → integration/p0-server | Ранняя deployment-подготовка уже внутри #6/#8/#9, отдельное повторное применение не требуется |
| [#6](https://github.com/bekzatwr/data-driven-curriculum/pull/6) | `cfce13d` → integration/p0-server | Comments/anti-spam/AI-off/fullstack; общий предок #8 и #9 |
| [#7](https://github.com/bekzatwr/data-driven-curriculum/pull/7) | `af1bdc0` → main | Только README/banner; не включён в #8/#9, требует согласования README-конфликта |
| [#8](https://github.com/bekzatwr/data-driven-curriculum/pull/8) | `024d422` → feature/bekzat-p1-infrastructure | Проверенная основа Бекзата: включает #1–#6 и cloud gates. Отдельный #7 и исправления #9 отсутствуют |
| [#9](https://github.com/bekzatwr/data-driven-curriculum/pull/9) | `f6eb7d3` → integration/p0-server | Содержит #6 + актуальный #4 + собственные UI/CI/tests; не содержит cloud-дельту #8. Остаётся WIP по указанию капитана |

При проверке ancestry учитывались **полные SHA** из JSON, не только названия веток. Не нужно переносить код #1/#2/#5 вручную поверх #8. После общего review команда выбирает каноническую цепочку и судьбу перекрывающихся PR; этот аудит ничего не закрывает и не retarget-ит автоматически.

CI соответствующих HEAD: #1 — 2 workflows successful; #2/#3/#4/#5 — по 3; #6/#8/#9 — по 4. Для #7 connector не вернул PR-triggered runs; успешный CI ему не приписывается. Логи CI #9 подтверждают **8 npm tests passed, 0 failed, 0 skipped**, typecheck/build. Это проверка опубликованного промежуточного HEAD, не приёмка окончательного frontend.

## 3. Возможные конфликты и риски совместимости

Выполнена **только симуляция** `git merge-tree --write-tree --messages`: ветки, HEAD, index и рабочие файлы не объединялись. Полученный tree не использовался для сборки или тестов. [Поведение merge-tree](https://git-scm.com/docs/git-merge-tree).

| Проверенные SHA / PR | Результат симуляции |
| --- | --- |
| #8 `024d422` + #9 `f6eb7d3` | Exit 0, текстовых конфликтов нет; две общие базы — `03395ef` и `cfce13d` |
| #8 + #7 | Exit 1: `README.md` |
| #6 + #7 | Exit 1: `README.md` |
| #3 + #7 | Exit 1: `README.md` |
| #8 + #5 | Exit 0, #5 уже предок #8 |

Из этого **не следует**, что будущие HEAD объединятся без конфликтов или что вся функциональность совместима. После завершения участников симуляцию повторить на новых SHA.

Места будущего совместного review:

- `planner/models.py`, `contracts.py`, `service.py`, `api.py`, `storage.py`: period-режим не должен удалить атомарность, проверку response до INSERT, нормализацию процентов, общие метрики Тони и чтение старых snapshot. При конфликте не выбирать файл целиком через ours/theirs.
- `backend/app/main.py`, общий OpenAPI/exporter: регистрация teachers/period и capabilities только после появления настоящего API. Не выставлять флаги ради демонстрации.
- `web/src/api/types.ts`, `client.ts`, `lib/features.ts`, `PlannerPage.tsx`, `TeachersPage.tsx`: Дамир подключает новые серверные контракты после согласования с авторами.
- `.github/workflows/web.yml`: сохранить новые npm tests и frontend AI contract checks из #9. Backend CI и Docker gate #8 тоже должны остаться.
- `README.md`: вручную совместить оформление #7 с актуальной архитектурой, командами и статусом; не потерять документацию backend/planner. Пока конфликт только зафиксирован, не разрешён через merge незавершённых PR.

## 4. Что ожидается от Дамира

В опубликованном PR #9 уже видны capabilities, отключение запрещённых POST, selectors вместо произвольного AI context, `question=null`, comments Retry-After, timeout, скрытие незавершённых P1-разделов и npm tests. Его runtime backend совпадает с PR #6; новых серверных teachers/period модулей он не добавляет.

До финальной интеграции нужны:

1. Явное подтверждение завершения и полный SHA; актуальные проверки и список известных ограничений.
2. Настоящий `GET /api/datasets/{dataset_id}/teachers` вместо клиентского расчёта. Сейчас `TEACHERS_SERVER_CONNECTED=false`: одного backend capability недостаточно, подключение делает Дамир.
3. Передача `settings.mode="period"` и правильная работа с period snapshot. Сейчас `PERIOD_PROTOTYPE_ENABLED=false`; старый обход через высокий `max_change` не считается реализацией режима.
4. Общий React E2E после появления API Тони/Айданы, read-only UX, ошибки 403/404/409/413/429/503, cancellation/timeout/Retry и скачивание CSV.
5. Мобильные проверки 360/390/430/768/1366/1920 на утверждённом SHA. `npm run lint` отсутствует: согласовать проверку/границы качества с командой; этот отчёт не объявляет lint пройденным.

Его собственный browser/mobile отчёт — данные автора PR #9. Здесь browser E2E не повторялся; эмуляция не выдаётся за физический Android/iPhone или Safari.

## 5. Что ожидается от Тони

Опубликованная P0-аналитика работает и проверена. Последний remote `analytics/toni` — `a2a89fa`; незавершённая новая реализация Teachers не опубликована на проверенных refs.

Ожидается серверный **`GET /api/datasets/{dataset_id}/teachers`** и OpenAPI/пример ответа. По командному ТЗ нужны `teacher_id`, `school_id`, `class_ids`, `students`, `textbooks`, `upcoming_hours`, `mean_post_pct`, `mean_gain_pp`, `n_pairs`; итоговые `teachers`, `students`, `students_per_teacher`, `classes_per_teacher`, `hours_per_teacher`.

Тони должен зафиксировать структуру response, фильтры, уникальность учеников/классов, отсутствующий teacher_id, несколько школ/версий тестов, правила pre/post и null. `upcoming_hours` и средние не должны удваиваться из-за повторных строк тестирования. Командный synthetic пример: 120 учеников / 4 учителя = 30; 24 часа на класс. Это будущие проверки Teachers, **не уже полученный teachers API response**.

Нужны tests, methodological notes и завершённый HEAD. Сохраняются диапазон процентов, деление до умножения, парные выборки и отсутствие причинного ранжирования учебников/учителей. AI остаётся disabled; live provider calls для этой задачи не требуются.

## 6. Айдана: period planner и GitHub 403

**Реализация `settings.mode="period"` не опубликована на проверенных refs.** `planner/aidana:7660b17` содержит только README и ТЗ; P0 planner уже ранее поступил через main и интеграционную цепочку. В опубликованном `planner/models.py` Settings включает только target_pct/donor_pct/min_students/max_change, `extra="forbid"`.

Проверка доступности контракта на настоящем текущем FastAPI/SQLite показала:

- `features.period_planner_api=false`, `features.teachers_api=false`;
- `GET /api/datasets/{id}/teachers` → **404**;
- preview с `{"class_id":"7A","settings":{"mode":"period"}}` → **422 INVALID_REQUEST**, поле `body.settings.mode`, extra input;
- AI status: `configured=false`, providers/models пусты.

Это доказательство отсутствия поддержки, **не тест алгоритма period**. Локальную реализацию Айданы без опубликованного SHA/полученного artifact не считаем поставкой.

Блокер **`AIDANA-PUBLISH-403`**: GitHub 403 при публикации сообщён капитаном. Сам 403 от аккаунта Айданы не воспроизводился; причина прав/аккаунта ещё не подтверждена. Подготовлен [протокол согласованного patch/bundle](PERIOD_PLANNER_HANDOFF.md): base/HEAD, авторство, SHA256, verify, изолированная проверка; без входа под чужим аккаунтом и обхода прав. Сейчас bundle/patch не получен и не применён.

Для подключения Айдана предоставляет:

- Совместимый серверный `settings.mode="period"` на существующих preview/save endpoints, схемы/ошибки и примеры. Без mode сохраняется прежнее поведение P0.
- Явно сохранённый режим в snapshot/settings и различимый algorithm_version; `recommended_hours` отражает period-рекомендацию, `manually_modified` сравнивается с ней. JSON/CSV должны одинаково описывать сохранённый план.
- Правила общего бюджета, min/max/locked, невозможного распределения и ручных правок; отдельные period rules не ослабляют существующие P0-тесты ±2.
- Чтение старых snapshot, atomic save/rollback, restart/restore, граничные дробные баллы, tests и полный SHA.

Алгоритм Айданы за неё не реализован и не переписан.

## 7. Render готов к будущей настройке, не к публикации

Переиспользуются `Dockerfile`, `deploy/render.yaml`, public/local Compose, `deploy/run_server.py`, `deploy/seed_demo_report.py`, SQLite online backup и `scripts/check_release.py`. Новые облачные ресурсы не создавались.

| Параметр | Проверенная конфигурация |
| --- | --- |
| Сервис | Один Docker React + FastAPI, один worker / instance |
| Build | APP_TARGET=fullstack, FRONTEND_DIR=web, VITE_API_BASE_URL пусто |
| Сеть / health | PORT=8000, 0.0.0.0, `/api/health`; `/api` и SPA с одного origin |
| Storage | Disk 1 GB `/app/data`, DATABASE_PATH=/app/data/curriculum.sqlite3, WAL/SHM там же |
| Guards | REQUIRE_PERSISTENT_STORAGE=true, DATA_MOUNT_PATH=/app/data, REQUIRE_P0=true |
| Public mode | PUBLIC_DEMO=true, READ_ONLY_DEMO=true, AI_ENABLED=false, AI_ACCOUNT_VERIFIED=false |
| CORS / proxy | CORS_ORIGINS и TRUSTED_PROXY_CIDRS пусты; proxy headers автоматически не доверяются |
| Deploy | autoDeployTrigger=off; ветка deployment/bekzat-cloud-readiness — подготовительная, не согласованный release ref |
| Synthetic report | Операторский seed, реальные расчёты; import/save/comments/AI/restore по public HTTP запрещены |
| HTTPS | Подготовлен strict HTTPS precheck; настоящего опубликованного URL в этой проверке нет |

Render YAML повторно проверен по официальной JSON Schema: **0 ошибок**. Root/fullstack/local Compose валидны. Docker проверяет mount guard, нестандартный PORT=8765, SPA/assets, CORS, health и non-root. Постоянство данных доказано локально; реальный Render disk и внешний TLS ещё не проверены. Кабинет Render не открывался повторно; прошлый отказ доступа не обходился.

Полная инструкция env/seed/backup/rollback — [cloud audit](BEKZAT_CLOUD_READINESS.md) и [deployment README](../deploy/README.md). После готовности всей команды выбрать разрешённый ref/SHA; не включать автоматический deploy из текущих WIP-веток. Платный сервис/диск и production deployment требуют отдельного решения владельца.

## 8. Реальные результаты этой проверки

| Проверка | Результат | Область |
| --- | --- | --- |
| Полный pytest | **319 passed, 0 failed, 0 skipped**, 26 subtests; 249.53 s | Неизменённый код PR #8 |
| Исходные planner tests | **7 passed**, 1.749 s | Реальный P0 planner |
| OpenAPI + analytics exports | Exit 0, diff contracts пустой | Существующие API |
| Docker build / HTTP smoke / E2E | **16 групп passed**, 0 failed | Реальный React `03395ef`, FastAPI и SQLite |
| Server scenario | 2 synthetic CSV → analytics → comparison **8 п.п.** → plan **24 часа** → JSON/CSV | 120 synthetic учеников, 1 440 строк |
| Persistence / backup | Данные, расчёты, plan, CSV и comments одинаковы после restart, replacement и восстановления нового volume | Реальная SQLite с WAL |
| Public / anti-spam | Запрет записи без мутаций БД; 429/Retry-After и spoofed XFF checks passed | Существующая защита |
| AI disabled | Offline/capabilities проверены, внешних вызовов **0** | Unit mock tests не являются вызовами провайдера |
| Frontend typecheck/build | Docker `tsc -b && vite build` прошёл | Версия #8, не приёмка #9 |
| Teachers / Period acceptance | **NOT RUN — модули не опубликованы** | Только диагностика 404/422 и false capabilities |
| Browser/mobile/external HTTPS | **NOT RUN** | Незавершённый frontend, нет разрешённого deployment |

Один известный Starlette/TestClient deprecation warning; использовался новый pytest basetemp внутри проекта. Старые ожидаемые результаты тестов не менялись.

Свежий Docker run **`ddc-check-19fa98d943`**, source commit `024d422`, `source_dirty=false`, frontend tree `5df386a4b0ddb3eb393d15aade7cf3ae5d427fc8`. `full_p0_verified=false` сохранён: HTTP E2E не заменяет полный проход через React. После этих проверок менялись только CI trigger и документация; CI текущего отчётного PR фиксируется отдельно в его Checks.

## 9. Подготовленная матрица финальной приёмки

Выполнять после завершения реальных модулей, на зафиксированных SHA. До этого не подменять отсутствующие Teachers/Period фиктивными ответами.

| Сценарий | Что проверить | Сейчас / владелец |
| --- | --- | --- |
| CSV → analytics → comparison → planner → report | Dry-run/ошибки, два CSV, фильтры/pre/post/версии, ручная правка, save, JSON/CSV | Серверный P0 passed; финальный React E2E после завершения Дамира |
| Comments | Все target types, чужой dataset 404, пустой/слишком большой текст, 429 + Retry-After, квота, rollback | Backend passed; UI #9 проверить после freeze / Бекзат + Дамир |
| Teachers | Synthetic 120/4, dedup, фильтры, missing teacher, несколько школ, null и версии, совпадение UI/API | Заблокировано / Тони → Дамир |
| Period planner | Настоящий mode, бюджет/min/max/locked, невозможные условия, ручная правка, mode в JSON/CSV, старые snapshots, atomic rollback | Заблокировано / Айдана → Дамир |
| AI disabled | Без ключей: configured=false, UI не отправляет POST, нет провайдерских вызовов, P0 работает | Backend passed; повторить в финальном UI / Бекзат + Дамир |
| Public read-only | Import/save/comments/AI/restore запрещены; preview и подготовленный report/CSV доступны | Backend passed; финальная проверка capabilities в UI / Дамир |
| Mobile | 360/390/430/768/1366/1920; меню, формы, picker, таблицы, графики, direct report/reload, timeout/Retry и CSV | После freeze; эмуляция отдельно от физических устройств / Дамир |
| SQLite / release | Сравнение report до/после restart, replacement и off-service restore; затем настоящий HTTPS + disk | Локально passed; облако после разрешения / Бекзат |

Команды, подготовленные для полного согласованного дерева:

```bash
python -m pytest -q
python -m unittest discover -s tests -p test_planner.py -v
python scripts/export_contracts.py
python -m scripts.export_analytics_contracts
git diff --exit-code -- contracts
python scripts/verify_deployment.py
# Из web/ после появления окончательного frontend:
npm ci
npm test
npm run typecheck
npm run build
# npm run lint — когда script предоставлен/согласован командой.
```

Teachers/Period tests добавляют владельцы вместе с модулями, они должны входить в общую pytest/CI. После намеренного расширения контрактов сначала review схем/примеров и commit, затем повторный экспорт должен давать пустой diff. Не менять ожидания ради зелёного статуса.

## 10. Безопасный порядок финальной интеграции

1. Получить от Дамира, Тони и Айданы явное подтверждение завершения, точные HEAD/base SHA, контракты, test results и ограничения. До этого продолжаются раздельные ветки; #9 не объединять.
2. Устранить `AIDANA-PUBLISH-403` обычным путём или получить согласованный artifact. Intake/review не равен публикации или включению в приложение.
3. Согласовать Teachers/Period schemas с Дамиром и Бекзатом, проверить режимы snapshot и обратную совместимость. Не активировать capabilities раньше настоящей регистрации API и tests.
4. После team review создать новую финальную integration-ветку от **тогда актуального main**. Использовать согласованную серверную цепочку #8, содержащую #3/#6 и их предков, а не повторно переносить каждую перекрывающуюся PR-дельту. Ни этот шаг, ни последующие merge сейчас не выполнялись.
5. По одному подключить завершённые серверные модули Тони и Айданы; проверить P0/atomic save и их новые tests. Затем подключить окончательный frontend Дамира к уже согласованным API. Конфликты разбирать с владельцами, сохраняя авторство и без force push.
6. Согласовать README #7 с финальным деревом, обновить описание функций, OpenAPI/JSON, fixtures и runtime env. Повторить merge-tree на новых SHA: текущая совместимость #8/#9 не гарантирует будущую.
7. Запустить полную матрицу выше: текущие backend tests + новые Teachers/Period + frontend tests/typecheck/build + Docker + реальный browser/mobile E2E. Проверить реальные ограничения lint и устройств, зафиксировать результаты без предположений.
8. Получить review/approve команды, включая Айдану по planner/atomic save и Тони по метрикам. Только после этого обсуждать Release Candidate и разрешённое объединение; сейчас RC **не объявляется**.
9. Владелец отдельно разрешает хостинг/бюджет и deploy. После него — настоящий HTTPS, второй ноутбук/телефон, Render disk restart, off-service backup/restore и rollback rehearsal. Без этих проверок публичный запуск остаётся NO-GO.
10. Предлагаемый график для согласования капитаном: до **11 ноября 18:00 UTC+5** заморозить функции; до **22:00 UTC+5** провести внутреннюю сдачу. Если Teachers/Period не успевают, капитан согласует P0 scope и скрытые flags; этот отчёт не принимает такое решение за команду. Финальный дедлайн **23:59 UTC+5**.

## Итог и ответственность

| Направление | Сделано | Что осталось | Кто отвечает |
| --- | --- | --- | --- |
| Бекзат | Повторная проверка P0, SQLite, comments, anti-spam, Docker, contracts, backup/restore | Интеграция завершённых модулей и итоговая приёмка | Бекзат |
| Дамир | Опубликован промежуточный #9, CI зелёный | Завершение, Teachers/Period API, финальный React/mobile E2E, границы lint | Дамир |
| Тони | P0-аналитика опубликована и работает | Финальный Teachers API, schemas/tests и методологический review | Тони |
| Айдана | P0 planner работает | Публикация period или согласованный bundle, контракт/tests, review | Айдана; владелец GitHub по 403 |
| Git | Зависимости/текстовые конфликты установлены, отдельная отчётная ветка | Review, затем согласованное объединение; README конфликт | Капитан + команда |
| Render | Конфигурация подготовлена, локальные проверки прошли | Разрешённый сервис/HTTPS/disk verification после всех модулей | Владелец + Бекзат |

**Сделано:** собственная часть перепроверена, зависимости и порядок объединения подготовлены. **Осталось:** завершение/поставка модулей и общая приёмка. **Ждём:** Дамира, Тони, Айдану и team review. **Финальная интеграция:** пока NO-GO. **Публикация сайта:** NO-GO. Эта работа не является финальным merge или Release Candidate.
