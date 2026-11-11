# Aidana — Final Planner QA & Critical Bug Verification

Дата проверки: **10 ноября 2026, UTC+5**. Автор: Айдана.

**Итог:** серверные P0 и Period Planner проходят проверки. В опубликованном frontend остаётся **P1 Critical: ограничение ±2 в Period Planner**. Полный браузерный сценарий с CSV не принят: выбор файла заблокирован разрешением расширения. Merge и deployment не выполнялись.

## 1. Проверенная версия

| Компонент | Проверенная версия / статус |
| --- | --- |
| Реальный React + FastAPI + SQLite | HEAD PR #9 `de7c58598b61b31e8e29a4da4780cf54ed935688` |
| Planner PR #10 | `62ad936ed19eab9e3beade22fd93dd3253849b33`, OPEN, MERGEABLE, reviewer `bekzatwr`, **12/12 SUCCESS** на момент проверки |
| Серверная подготовка Бекзата | `chore/bekzat-pre-integration`, `64cba3f570d5b8dae0a097350ebc34e26c5feca8` |
| Серверный handoff PR #13 | `0b77889b69ae584018e90c8d92706112f5286a1c`, изменения документации |
| Формальная целевая ветка | `integration/p0-server`, `b25891c332a1e0020e8ac8bdb72b1c5ce5789f27`; финальное объединение ещё предстоит |
| main | `3ebe857c78248bb3a7c056342548ab3a1d25c968` |
| Собственная QA-ветка | `qa/aidana-final-critical-20261110`, создана от опубликованного PR #9; только тесты, документация и доказательства |

PR #9 содержит совместную реализацию, но не является уже согласованным финальным merge. Коммиты PR #10 и серверной подготовки не являются его предками: совместимость проверена по содержимому файлов, а не по одному названию ветки. В `planner/` отличие от PR #10 — только описание ответа 403 в OpenAPI для сохранения. В серверном runtime относительно `64cba3f` отличаются объявления готовности Teachers/Period в `backend/app/main.py`; `collab/` совпадает. Реализация Period соответствует PR #10. Toni PR #12 `b25cfaf` включён в историю PR #9.

Frontend собран из опубликованного `de7c585` **без прежнего локального исправления ±2**. Приложение работало на localhost:8768, с отдельной SQLite и только синтетическими данными. ASGI-обёртка `qa/planner_capture.py` записывала реальные входящие planner-запросы и ответы, передавая их приложению без изменения. Автоматические backend-тесты используют обычное приложение без этой обёртки.

## 2. Что проверено и работает

| Сценарий | Результат и доказательство |
| --- | --- |
| P0 `rules_v1` | PASS: preview/save через браузер, API, регрессии; старый лимит ±2 сохранён для P0 |
| P1 `period_v1` | PASS на сервере: режим `settings.mode="period"`, полный бюджет, алгоритм `period_v1`; UI-ограничение описано ниже |
| Min/max, locked, сумма | PASS: детерминированные и случайные тесты, невозможные ограничения отклоняются; min может превышать старые часы незаблокированной темы; Geometry остаётся 3 ч; сумма 24 |
| Ручные изменения | PASS: JSON сохраняет итоговые и рекомендованные часы раздельно; `manually_modified` корректен для снимка и отдельных тем |
| Ручное +3 | Сервер PASS: Equations 5→8 при max=8 и сумме 24; тот же запрос в P0 получает 422 без записи. Добавлены два QA regression cases |
| `0.69/0.69` | PASS: точно 100%, preview и save работают в P0 и Period; некорректные исходные баллы отклоняются |
| JSON / CSV | PASS: алгоритм, итоговые/рекомендованные часы, delta, флаги ручных правок совпадают; скачанный кнопкой CSV побайтно равен серверному экспорту |
| Legacy plans | PASS: сохранённый P0-снимок без `settings.mode` читается без изменения; `test_legacy_saved_plan_without_mode_remains_readable` |
| Atomic save | PASS: ошибка контракта, отсутствующие метаданные, NaN, invalid UTF-8, render, SQLite после INSERT и deferred COMMIT не оставляют записей; существующие P0/Period снимки неизменны; следующее корректное сохранение успешно |
| Неверные ручные значения | PASS: сумма, min, max, locked, неполная карта и дробные часы → 422, база не изменяется |
| Restart | PASS: настоящая остановка процесса API и запуск с той же SQLite; все 3 сохранённых QA-снимка идентичны, периодный JSON и CSV неизменны, `integrity_check=ok`; отчёт открыт снова в Chrome |
| Backup/restore | PASS: live WAL backup, восстановление планов и комментариев, экспорт после восстановления; основные и отдельные QA-тесты |
| Контракты API | PASS: P0/Period integration, contract tests, экспорт backend/analytics contracts без содержательных изменений |
| TypeScript/Python parity | PASS: 200 случаев настоящего TypeScript Period Planner против Python |

## 3. Реальный браузер и HTTP payload

Chrome, опубликованный React, FastAPI, SQLite:

1. Форма своих CSV открыта, но выбор файла через расширение отклонён разрешением `Allow access to file URLs`. Dry-run/Import **через браузер не выполнены**. Ограничение не обходилось.
2. Через кнопку демоданных создан набор: 120 искусственных учеников, 4 класса, 6 тем, 1 440 записей.
3. Overview → ячейка heatmap → аналитика темы → Textbook Comparison пройдены. Для Equations: A gain=16 п.п., B gain=8 п.п., разница=8 п.п., по 60 пар.
4. P0 для 7A: preview `[8,5,5,3,2,1]`, сумма 24, save HTTP 201, `rules_v1`.
5. Period для 7A: preview `[8,6,4,3,2,1]`. Значения шести полей DOM **совпали с фактическим серверным `proposed_hours`**.
6. Проверены блокировка Geometry и запрет сохранения при неправильной сумме. Воспроизведён дефект кнопки Equations на 7 ч.
7. Допустимая ручная правка `[7,7,4,3,2,1]` → Save 201 → Report: сумма 24, две ручные правки, рекомендации `[8,6,4,3,2,1]` сохранены отдельно.
8. CSV скачан кнопкой, сверен с HTTP-экспортом. Reload выполнен. API перезапущен отдельным процессом; тот же отчёт снова открыт в браузере с `period_v1` и прежними правками.

Порядок тем во всех массивах: Fractions, Equations, Proportions, Geometry, Statistics, Revision.

Фактический payload браузерного save (не реконструкция из исходного кода):

```json
{
  "class_id": "7A",
  "settings": {
    "target_pct": 70,
    "donor_pct": 80,
    "min_students": 10,
    "max_change": 2,
    "mode": "period"
  },
  "hours_by_topic": {
    "fractions": 7,
    "equations": 7,
    "proportions": 4,
    "geometry": 3,
    "statistics": 2,
    "revision": 1
  },
  "comment": "QA published de7c585: period manual 7/7/4/3/2/1; sum=24; locked geometry=3"
}
```

Ответ: `201`, `algorithm_version="period_v1"`, `manually_modified=true`, plan ID `15c7899c-020e-4476-b161-a91787fbf5f1`. Поле `max_change=2` присутствует, но сервер в period-режиме корректно не применяет лимит P0. Отдельный **HTTP-only** запрос `[6,8,4,3,2,1]` также сохранён с 201; он не выдаётся за браузерный save.

Полный **HTTP/SQLite E2E**: синтетические results.csv + curriculum.csv → dry-run → import → overview → topic analytics → comparison → period → ручная правка → save → JSON/CSV → реальный restart — PASS. Это отдельная проверка, не замена отсутствующему браузерному upload.

Доказательства: [payload, ответы и результаты](../qa/evidence/final-planner-verification.json), [ошибка кнопки](../qa/evidence/period-stepper-blocked.jpg), [отчёт после restart](../qa/evidence/report-after-restart.jpg).

## 4. Найденные ошибки и блокеры

### FE-01 — P1 Critical: старое ограничение ±2 в Period Planner

- **Owner:** Дамир (`@foxfordkz-cyber`), PR #9.
- **Версия:** воспроизведено на `de7c585`, без локального исправления.
- **Reproduction:** демоданные → План часов → 7A → План на весь период → «Ограничения тем». У Equations current=5, min=3, max=8, server recommendation=6. Нажать «+»: значение 7, дальнейшая кнопка «+» отключена. Для законного целевого плана уменьшить Fractions до 6 и увеличить Equations до 8: итог должен быть 24.
- **Expected:** в period-режиме шаговый ввод допускает весь `[min_hours,max_hours]`; сумма и locked проверяются отдельно. Equations 8 разрешено. В P0 предел остаётся 7.
- **Actual:** `lo/hi` в `web/src/pages/PlannerPage.tsx:540–541` всегда пересекаются с `current_hours ± maxChange`; UI останавливается на 7, хотя реальный API принимает 8 с 201.
- **Fix status:** OPEN, frontend не изменён. Минимальное предложение и тест-кейс переданы [в PR #9](https://github.com/bekzatwr/data-driven-curriculum/pull/9#issuecomment-6771423440).

Минимальное изменение для Дамира:

```tsx
const lo = isPeriod ? it.min_hours : Math.max(it.min_hours, it.current_hours - maxChange);
const hi = isPeriod ? it.max_hours : Math.min(it.max_hours, it.current_hours + maxChange);
```

Regression acceptance для frontend: period Equations 5→8, Fractions 6, total 24, Save 201/period_v1; при 9 действует max=8; Geometry locked; при сумме 23 Save запрещён. После переключения на P0 граница Equations снова 7. Дополнительно period Fractions min=9/max=10 при old current=6 должен отображать и допускать серверный результат ≥9, без старого hi=8. Последний сценарий покрыт backend-регрессией; после исправления требуется повтор в браузере.

### FE-02 — Minor: настройка ±2 показана в period-режиме

- **Owner:** Дамир.
- **Reproduction:** выбрать «План на весь период», посмотреть свёрнутую строку «Настройки алгоритма».
- **Expected:** пояснение соответствует распределению всего периода без лимита P0.
- **Actual:** виден текст «цель 70%, порог донора 80%, лимит ±2 ч»; он не соответствует period-семантике. Снимок FE-01 содержит этот текст.
- **Fix status:** OPEN, передано вместе с FE-01; это отображение, серверные часы не искажаются.

### ENV-01 — блокер полного Browser E2E: выбор CSV

- **Severity:** QA environment blocker; не доказанная ошибка импорта приложения и не backend P0.
- **Owner:** команда, запускающая ручной Browser E2E; Дамир для повторной frontend-приёмки.
- **Reproduction:** «Свои CSV» → выбрать локальный синтетический results.csv через file chooser расширения.
- **Expected:** файл выбран, доступен dry-run/import.
- **Actual:** расширение требует `Allow access to file URLs`; файловый ввод не завершён, несмотря на ранее сообщённое включение разрешения.
- **Fix status:** BLOCKED. Обход не выполнялся. HTTP dry-run/import прошли; ручной чеклист ниже.

### ENV-02 — Docker smoke не запущен локально

- **Severity:** environment coverage gap, не обнаруженный дефект приложения.
- **Owner:** Бекзат для интеграционной CI-проверки; Дамир для окружения deployment.
- **Reproduction:** `docker version` с ограничением ожидания 20 секунд.
- **Expected:** доступный Docker daemon и запуск smoke.
- **Actual:** команда не отвечает за 20 секунд; контейнерный smoke не выполнялся.
- **Fix status:** BLOCKED локально. PR #10 имеет успешные container/deployment-rehearsal checks, но они не заменяют локальный запуск на `de7c585` и не означают выполненный deployment.

## 5. Что исправлено и кому передано

- Ошибок planner backend и повреждения сохранённых данных в выполненных сценариях не найдено. Production-код не менялся; новые функции не добавлялись.
- Старые исправления fractional percentage и atomic save подтверждены повторными тестами; это не новые исправления данного QA.
- В собственной QA-ветке опубликованы 15 дополнительных atomicity/manual-contract cases и harness записи фактического HTTP; вместе с 7 имеющимися acceptance cases дают **22** отдельных QA-теста.
- Дамиру переданы FE-01, FE-02 и frontend regression acceptance: [PR #9](https://github.com/bekzatwr/data-driven-curriculum/pull/9#issuecomment-6771423440).
- Бекзату передан итоговый review handoff с GO сервера, NO-GO пользовательского Period-сценария до FE-01, CSV/Docker coverage gaps и точными HEAD: [PR #10](https://github.com/bekzatwr/data-driven-curriculum/pull/10#issuecomment-6771443902). Новых серверных багов для исправления нет.

## 6. Результаты тестов

| Запуск | Passed | Failed | Skipped / статус |
| --- | ---: | ---: | --- |
| Полный `python -m pytest -q` (`backend/tests`, `tests`) | **420** | **0** | **0** |
| Отдельно `qa/test_p1_acceptance.py` + `qa/test_final_period_atomicity.py` | **22** | **0** | **0** |
| `npm test` в web | **8** | **0** | **0** |
| TypeScript/Python Period parity | **200 случаев** | **0** | **0** |
| TypeScript/Vite build | PASS | — | завершён |
| Backend/analytics contract export + проверка diff | PASS | — | содержательных изменений нет |
| Real HTTP/SQLite E2E с restart | PASS | — | отдельный smoke-сценарий |
| Browser demo → report/export/reload/restart | PARTIAL | FE-01 | загрузка CSV не входила |
| Full Browser CSV → Report E2E | — | — | BLOCKED / не принят |
| Local Docker smoke | — | — | NOT RUN: Docker недоступен |

В полном pytest отдельно отмечены **102 успешных subtests**. Они не прибавлены к 420 как новые тесты. Planner regression, period, API contracts, persistence и backup/restore уже входят в приведённые наборы и второй раз не суммируются. QA-папка не входит в стандартные `testpaths`, поэтому 22 QA-теста запущены отдельно. Один Starlette/httpx deprecation warning, без падений.

Воспроизводимые команды (из корня checkout с установленными requirements-dev и web dependencies):

```text
python -m pytest -q
python -m pytest -q qa/test_p1_acceptance.py qa/test_final_period_atomicity.py
npm --prefix web test
npm --prefix web run build
python scripts/check_period_parity.py
python scripts/export_contracts.py
python -m scripts.export_analytics_contracts
git diff --exit-code -- contracts
python qa/check_http_e2e.py .
```

Локальные подробные логи/JUnit, actual HTTP capture и CSV: `output/aidana-final-critical` рядом с QA-checkout. Ключевые результаты и синтетические browser evidence включены в `qa/evidence/` этой ветки. Паритет и HTTP smoke не выдаются за browser tests. Неуспешная попытка прямого запуска analytics exporter без module path была исправлена запуском `python -m scripts.export_analytics_contracts`; это ошибка команды запуска, а не приложения.

## 7. Ручной QA-чеклист до финальной интеграции

1. Дамир публикует FE-01 fix в PR #9. Проверить новый commit и повторить конкретный +3/min9 сценарий, P0 ±2, locked и запрет неправильной суммы.
2. В разрешённом обычном Chrome открыть согласованный frontend/API. Выбрать синтетические `results.csv` и `curriculum.csv` из `data/browser-fixtures` локального QA-checkout (либо получить их из `backend.app.demo.demo_files`). Не использовать реальные данные учеников.
3. Нажать dry-run: проверить отсутствие записей. Нажать Import: успешный набор, 120/4/6/1440 для этих fixtures; проверить предупреждения/ошибки файла.
4. Overview → Analytics темы → Comparison. Equations: A gain 16, B gain 8, разница 8 п.п.
5. P0 7A: `rules_v1`, сумма 24, ограничения ±2. Save → Report.
6. Period: в Network проверить фактический preview/save payload `settings.mode="period"`; server/UI часы `[8,6,4,3,2,1]`. Ручной план `[6,8,4,3,2,1]` должен сохраняться; итоговый алгоритм `period_v1`, ручные флаги, исходные рекомендации не потеряны.
7. Отрицательные сценарии: неправильная сумма, выход за min/max, locked. Проверить отсутствие нового снимка после 422/ошибки сохранения.
8. Save → Report → JSON/CSV: сравнить все часы и флаги. Reload → restart API с той же SQLite → открыть тот же URL. Проверить также старый P0-снимок.
9. Повторить Docker smoke/backup/restore в доступном окружении. После согласованного Бекзатом объединения записать итоговый integration SHA и повторить ключевой E2E на нём.

## 8. Статус PR #10 и решение

PR #10 остаётся **OPEN / MERGEABLE**, HEAD `62ad936`, **12/12 checks SUCCESS**, review запрошен у Бекзата. В этот PR не добавлялись frontend-код или коммиты других участников; QA-отчёт находится в собственной отдельной ветке. Самостоятельного merge, force push, deployment и изменения чужого frontend не было.

- **GO — P0 Planner** на проверенном snapshot.
- **NO-GO — Period Planner как полный пользовательский сценарий** до исправления FE-01. **Серверный period_v1: GO** для review и согласованной интеграции PR #10.
- **NO-GO — Full Browser E2E**: CSV upload не проверен из-за ENV-01, FE-01 открыт.

До общей финальной приёмки остаются frontend fix + regression, ручной полный CSV E2E, доступный Docker smoke и повтор ключевых проверок на согласованном финальном integration HEAD. Выполненные проверки не выявили потери или повреждения сохранённых данных.
