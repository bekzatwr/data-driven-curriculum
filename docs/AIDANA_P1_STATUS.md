# Айдана — Period Planner и интеграционный QA

Проверено 10 ноября 2026. Ветка: `feature/aidana-period-planner`.
Основа: `integration/p0-server` — `b25891c332a1e0020e8ac8bdb72b1c5ce5789f27`.
Commit реализации: `89650cccaf67b12fb356c17a0fe6b0e9a9bc6198`.
HEAD на момент окончательного аудита реализации: `6b52786f2d1274116ed6bd2d9b49d3a638477d5b`.
Последующее обновление добавляет только документы и отдельный QA backup/restore; точный SHA checkout: `git rev-parse HEAD`.
Удалённый [PR #10](https://github.com/bekzatwr/data-driven-curriculum/pull/10) **опубликован от Aidana17022007**, base `integration/p0-server`, конфликтов нет. Merge не выполнялся.
Ветка отслеживает `origin/feature/aidana-period-planner`; origin — `https://github.com/bekzatwr/data-driven-curriculum.git`. Перед финальными QA-правками git status/diff были пусты, локальный и удалённый HEAD совпадали. Незакоммиченные изменения не потеряны.

## Что реализовано

- `settings.mode="period"`, `algorithm_version="period_v1"`: весь бюджет равен сумме исходных `current_hours`.
- Заблокированные темы сохраняют часы; остальные начинают с `min_hours`. Остаток выдаётся по одному часу с учётом важности, дефицита до цели, половинного веса освоенных тем и уже добавленных часов. Tie-break соответствует реальному TypeScript: `topic_order`, tolerance `1e-9`.
- При отсутствии сопоставимого среднего используется важность. Это распределение бюджета, а не оценка эффекта или достоверности результатов.
- Сумма, целочисленность, min/max, блокировки проверяются на сервере. Невыполнимые минимумы/максимумы дают понятную 422-ошибку.
- В period разрешены новые границы, не содержащие исходные часы незаблокированной темы: проверяется итоговый бюджет. У заблокированной темы исходные часы обязаны оставаться внутри границ.
- P0 `rules_v1` остаётся режимом по умолчанию с прежними правилами и лимитом изменения. `max_change` игнорируется только при проверке period. Алгоритм P0 не переписан.
- Preview/save/JSON/CSV сохраняют настройки, метрики, рекомендованные и итоговые часы, ручные изменения. Сохраняется `period_v1`; прежние снимки без поля mode читаются.
- Атомарный `SnapshotStore` Бекзата сохранён: полный контракт и ответ готовятся до INSERT. Floating-point нормализация в общей аналитике не изменена.
- Обновлены OpenAPI и реальные примеры ответов. Backend CI теперь запускается и для PR в `integration/**`.

Пример:

```json
{"class_id":"7A","settings":{"mode":"period"}}
```

Этот запрос используется для `POST /api/datasets/{id}/plans/preview` и `POST /api/datasets/{id}/plans`.
Для ручного сохранения добавить `hours_by_topic` со всеми темами. Сервер рассчитывает рекомендацию заново и сам определяет `manually_modified`.

## Изменённые файлы

- `planner/period.py`, `models.py`, `rules.py`, `service.py`, `contracts.py`.
- `tests/test_period_planner.py`, `backend/tests/test_period_integration.py`.
- `qa/test_p1_acceptance.py`, `qa/check_http_e2e.py`, `scripts/check_period_parity.py`.
- `scripts/export_contracts.py`, `contracts/openapi.json`, два обновлённых P0-примера, два новых period-примера.
- `.github/workflows/backend.yml`, этот отчёт.

`collab/` и frontend не изменялись. Чужие ветки и main не изменялись.

## Выполненные проверки

1. Python 3.13: исходный локальный полный прогон **232 passed**, затем 8 period integration tests после двух добавлений. Полный remote pytest окончательной реализации прошёл в GitHub CI; отдельные локальные запуски не выдаются за CI.
2. 150 случайных наборов внутри regression-теста: бюджет, min/max, блокировки, детерминизм при перестановке входа.
3. **200 реальных TypeScript/Python parity cases passed**: TypeScript из опубликованного frontend исполнялся Node.js через его установленный TypeScript compiler. Расчёты не подменялись моками.
4. Финальный полный прогон в совмещённой копии PR #6 `cfce13d24b68b70a8bbec7e196f70886d254cfe7` плюс наш planner: `pytest backend/tests tests qa/test_p1_acceptance.py` — **332 passed**, 26 subtests, 79.38 с. После добавления отдельной проверки backup/restore весь QA-файл — **7 passed**. Не складываем пересекающиеся прогоны. Есть одно известное Starlette/httpx deprecation warning.
5. Comments: dataset/topic/plan/plan_topic, пустые и длинные строки, неизвестный dataset, повторное открытие и сохранность после рестарта.
6. AI: без ключей — 503 `AI_NOT_CONFIGURED` с понятным сообщением; mock provider success/error/timeout; неверный context; отсутствие синтетического ключа в ответах/логах; неизменность учебных данных. **Технические rate counters изменяются штатно**; утверждения об отсутствии вообще любых записей в БД нет. Внешних AI-запросов не выполнялось.
7. Реальный localhost HTTP, отдельный SQLite и отдельный процесс Uvicorn: два CSV → dry-run/import → overview/topic/comparison → period preview → ручная правка → save → JSON/CSV → комментарий → offline AI → остановка и новый процесс с той же SQLite → точное совпадение плана, CSV и комментария. Проверка завершилась с exit code 0; тестовый сервер остановлен.
8. Актуальный `frontend/damir` — `03395ef5db68ac9fab379f622ddf6fbe09112327`: `npm ci`, TypeScript/Vite build, 200 parity cases и повторный реальный HTTP E2E успешны. FastAPI отдаёт собранный HTML. Это не подтверждает интерактивный браузерный E2E.
9. `0.69/0.69=100` в period preview/save; допустимые новые границы выше исходных часов; ошибка формирования ответа не меняет ранее сохранённые строки SQLite.
10. Python 3.10: один прежний CSV fixture test падает на NUL при подготовке CSV. Python 3.13, как в CI, проходит его. Код импорта ради этого не менялся.
11. Новый QA backup/restore проверяет настоящий SQLite backup и восстановление в новый файл: period snapshot, CSV и plan_topic comment совпадают. Результат включён в 7 passed выше.
12. Общий exporter PR #6 запускается с новым planner. OpenAPI включает mode enum/default P0, comments и AI; diff — только mode в Settings и двух примерах planner. Обнаружено ожидаемое `period_planner_api=false`: включение остаётся за Бекзатом.
13. Docker Compose конфигурация валидна. Локальный Docker Desktop запускался, но API daemon не стал доступен для нового совмещённого smoke. Docker/container/deployment и backup/restore **на ветке Айданы** подтверждены реальными GitHub jobs; локальный Docker smoke совмещённой P1-копии не объявляется пройденным.

Команды (из нужной тестовой копии, с активированным Python 3.13 окружением):

```text
python -m pytest -q
python scripts/export_contracts.py
git diff --exit-code -- contracts
python scripts/check_period_parity.py ../combined-checkout/web
python -m pytest -q qa
python qa/check_http_e2e.py ../combined-checkout
```

`qa` требует подключённого `collab/`; в базовой integration-ветке его ещё нет. Команда намеренно не скрывает это skip-результатом. Сборку `web/dist` выполнить заранее. Последние две команды — на совмещённой копии; стандартный pytest базовой ветки запускает `backend/tests` и `tests`.

## Найденные ограничения и передача

**Дамиру:** frontend в проверенной версии вычисляет period локально и отправляет `max_change=totalCurrent`, не отправляя `settings.mode="period"`. Поэтому браузерный save маркируется как `rules_v1`, а локальная рекомендация может считаться ручной правкой. Добавить mode в `PlanSettings`; preview/save period должны отправлять `mode="period"`; использовать серверные `items[].proposed_hours` и причины. Снять UI-ограничение ±N для period; сохранить min/max/locked/сумму. После этого повторить интерактивный E2E.

**Бекзату:** включить planner commit в интеграцию вместе с P1 infrastructure; в P1 capabilities заменить `period_planner_api: false` на true после подключения; при объединении OpenAPI перегенерировать контракты. В `collab/` новых блокирующих дефектов нашими тестами не обнаружено. Учесть отличие технических rate counters от учебных данных.

**Публикация/403:** Айдана выполнила штатный GCM browser login для `Aidana17022007` и push с явным выбором этого username. Push прошёл, PR #10 создан от того же аккаунта. Следовательно, Git CLI Write-доступ подтверждён действием; новый collaborator grant не нужен. GitHub connector остался под `foxfordkz-cyber`, с прежним 403 на запись; его не используем для публикации от чужого имени. Credentials/токены не извлекались, настройки доступа не менялись. Описание PR и запрос review Бекзату требуют отдельной проверки публикации; на момент создания PR body и requested_reviewers пусты.

**PR #1:** замечания к `d83ce28` проверены, исправления признаны корректными. Технический результат review положительный; публикация Approve не выполнена из-за прав подключения.

**Браузер:** повторная проверка завершилась `transport closed before response`; native Chrome также не дал состояние минимизированного окна. Контроль через Yandex ранее был остановлен политикой инструмента. Ограничения не обходились. Полный интерактивный E2E и мобильная приёмка не подтверждены. Точный сценарий для команды опубликован в [AIDANA_INTEGRATION_HANDOFF.md](AIDANA_INTEGRATION_HANDOFF.md).

**GitHub CI для `6b52786f2d1274116ed6bd2d9b49d3a638477d5b`:** независимо проверены все jobs и steps. Push — 6/6 successful; PR #10 — **6/6 successful**: backend, container, deployment-rehearsal, planner, analytics Windows, analytics Ubuntu. В container успешно выполнены Docker smoke, backup, restore, restart и повторный smoke. Это удалённые результаты, не вывод из локальных тестов.

- [Backend/container/deployment PR run](https://github.com/bekzatwr/data-driven-curriculum/actions/runs/42823564790)
- [Planner PR run](https://github.com/bekzatwr/data-driven-curriculum/actions/runs/42823564816)
- [Analytics PR run](https://github.com/bekzatwr/data-driven-curriculum/actions/runs/42823564704)

## Задачи и ответственные

| Задача | Сделано | Осталось | Блокер | Ответственный |
| --- | --- | --- | --- | --- |
| Аудит git/HEAD/upstream | SHA, чистое исходное дерево, правильный upstream | Сверять новый SHA после каждого push | Нет | Айдана |
| Исправление 403 для push | GCM вход своим аккаунтом, push успешен | Connector всё ещё отдельно без write | Connector permissions | Айдана |
| Публикация | PR #10 открыт в integration/p0-server | Описание и формальный review request проверить отдельно | Browser/connector write | Айдана |
| period_v1/P0 | Реализовано, regression и CI пройдены | Code review | Нет технического блокера | Айдана, Бекзат |
| Совместимость PR #6 | Полный 332-test прогон, comments/AI/SQLite/OpenAPI | Merge командой после review, capability=true, общий exporter | Незавершённая общая интеграция | Бекзат |
| Frontend period | Проверены две актуальные ветки, точные JSON и инструкция подготовлены | mode=period, server recommendations, UI flags | Клиент ещё считает period локально | Дамир |
| Backup/restore | Новый QA подтверждает plan/CSV/comments в восстановленной БД | Совмещённый Docker-прогон на рабочем daemon | Локальный Docker API недоступен | Айдана/Бекзат |
| GitHub CI | Все 6 push и 6 PR jobs успешны на указанном SHA | Проверить jobs нового HEAD после обновления документов | Нет | Айдана |
| Browser E2E | Реальный HTTP маршрут и React build пройдены; точный browser checklist готов | Выполнить весь UI-маршрут после изменения frontend | Browser transport и неподключённый frontend mode | Дамир/Бекзат |
| Передача | Инструкция и JSON находятся в PR-файлах | Подтверждение прочтения и формальный review | Ответ команды | Дамир/Бекзат |

До заморозки **11 ноября 18:00 UTC+5**: подключить mode в UI и capability на сервере, пройти совместный браузерный QA. До дедлайна **11 ноября 23:59 UTC+5**: review, CI итоговой интеграции и зафиксированное GO/NO-GO. Если P1 не принят — сохранить работающий P0, не объявлять полный E2E готовым.

## Вердикт

- **Period Planner готов на сервере. GO для code review и интеграции**: ветка и PR опубликованы, CI реализации зелёный.
- **GO для локального API-демо** в проверенной совмещённой конфигурации, без внешнего AI.
- **NO-GO для объявления полного P1/E2E готовым**: frontend ещё не отправляет новый mode; требуется включение capability, review команды и реальный интерактивный браузерный прогон.

Презентация, видео, дизайн и новые функции вне задания не выполнялись.
