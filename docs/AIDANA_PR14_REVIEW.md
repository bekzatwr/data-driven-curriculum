# Айдана — review Planner в интеграции PR #14

Проверено 10 ноября 2026 года, UTC+5. **Точный HEAD: `aaa78e1bc0ba5606d2239aa60839458f5f10c3b8`**. PR #14 остаётся Draft. Review касается P0/Period Planner, ручных изменений, сохранённых отчётов и совместимости SQLite.

**Серверный Planner: GO для командного review.** Потери данных и ошибок алгоритма не найдено. **Полная приёмка Period UI: NO-GO** до исправления кнопок ±2. Общий deployment остаётся NO-GO также по известному frontend body-timeout и незавершённому browser/mobile E2E.

## Найденное замечание

### P1 Critical — Period-кнопки всё ещё ограничены ±2

- **Owner:** Дамир, PR #9; дефект также включён в PR #14.
- **Файл:** `web/src/pages/PlannerPage.tsx`, строки 540–541.
- **Reproduction:** открыть синтетический демонабор → План часов → класс 7A → «План на весь период» → «Ограничения тем». Equations: current=5, min=3, max=8, сервер рекомендует 6. Кнопкой увеличить до 7 и уменьшить Fractions до 7: сумма 24. Кнопка Equations «+» уже disabled, хотя max=8.
- **Expected:** в period кнопки и ArrowUp/Down ограничиваются min/max, без `current_hours ± max_change`. В P0 старое ограничение сохраняется.
- **Actual:** `lo/hi` всегда вычислены через лимит P0; 7→8 кнопкой недоступно. Воспроизведено в реальном Chrome на **PR #14**, без изменения frontend.
- **Уточнение / рабочий обход в интерфейсе:** прямой ввод числа **8 + Enter работает**. Через него сохранён валидный period-план `[6,8,4,3,2,1]`, сумма 24. Это снимает неоднозначность прежнего описания: ошибка относится к кнопкам и стрелкам, а не ко всем способам ввода и не к серверу.
- **Fix status:** OPEN. Предложение ниже передано Дамиру; чужой frontend не изменялся. [Предыдущий bug report](https://github.com/bekzatwr/data-driven-curriculum/pull/9#issuecomment-6771423440).

```tsx
const lo = isPeriod ? it.min_hours : Math.max(it.min_hours, it.current_hours - maxChange);
const hi = isPeriod ? it.max_hours : Math.min(it.max_hours, it.current_hours + maxChange);
```

Regression acceptance для Дамира: period Equations 5→8 кнопкой, Fractions=6, сумма 24, save 201/period_v1; 9 запрещено max=8, Geometry locked=3, неверная сумма запрещает сохранение. В P0 Equations остаётся ограничен 7. Отдельно проверить period min=9/max=10 при прежних current=6.

**Minor:** подпись «Настройки алгоритма … лимит ±2 ч» остаётся в period-режиме; на серверные расчёты не влияет. Owner Дамир, OPEN.

Известный body-timeout из PR #14 относится к frontend transport; он не исправлялся и не объявляется закрытым этим planner review. Его отдельные 9 passed / 1 failed приведены Бекзатом; в этой проверке probe повторно не запускался.

## Что проверено независимо

| Область | Результат |
| --- | --- |
| Совместимость модулей | `planner/` и `web/` совпадают с ранее проверенным опубликованным `de7c585`. От PR #10 в planner отличается только OpenAPI-описание 403. Новое изменение импорта PR #14 находится отдельно в datasets/store |
| P0 `rules_v1` | PASS: реальный browser preview и ручной save `[7,6,5,3,2,1]`, сумма 24, правильный алгоритм и флаги ручной правки |
| Period `period_v1` | PASS backend: actual preview/save HTTP payload содержит `settings.mode="period"`, ответ/снимок `algorithm_version="period_v1"` |
| Серверные рекомендации | PASS: значения шести DOM-полей `[8,6,4,3,2,1]` совпали с реальным серверным `proposed_hours` |
| Ручная правка +3 | PASS через прямой ввод: `[6,8,4,3,2,1]`, Equations current=5→8, рекомендации остались `[8,6,4,3,2,1]`, `manually_modified=true` и две изменённые относительно рекомендации темы |
| Min/max/locked/сумма | PASS backend и UI-валидация: max=8 при вводе 9 с общей суммой 24 запрещает save; min=1 при вводе 0 с суммой 24 запрещает save; сумма 25 запрещает save; Geometry disabled и остаётся 3 |
| Сохранённый Report | PASS: рекомендованные и итоговые часы раздельны; Fractions recommendation=8/final=6, Equations recommendation=6/final=8; алгоритм period_v1, сумма 24 |
| JSON/CSV | PASS: предложенные/рекомендованные/текущие часы, min/max, algorithm и manual flags совпадают; CSV, скачанный кнопкой Chrome, побайтно совпал с API |
| Старые планы | PASS: online backup SQLite из предыдущей QA-сборки содержит 3 прежних P0/Period-снимка. Новая интеграция открыла их без изменения JSON; прежний period-отчёт открыт в Chrome |
| Legacy без mode | PASS: существующая regression-проверка `test_legacy_saved_plan_without_mode_remains_readable` в полном pytest |
| Restart | PASS: настоящий stop/start процесса API; 3 старых + 2 новых браузерных плана неизменны, JSON совпадает, SHA256 CSV совпадают; новый period-отчёт повторно открыт в Chrome |
| SQLite | PASS: `integrity_check=ok`, `foreign_key_check=[]` |
| Atomic save | PASS: ошибки контракта/метаданных/NaN/UTF-8/render/INSERT/COMMIT не оставляют частичных записей, прежние снимки сохранены; после устранения искусственной ошибки save работает |
| Неверные ручные запросы | PASS: sum/min/max/locked/incomplete/fractional → 422 без записи; +3 допустимо только для period, P0 корректно отклоняет |
| Floating point | PASS: 0.69/0.69=100% в preview/save обоих режимов, включая строгий верхний предел контракта |
| Backup/restore | PASS в полном pytest: P0/Period и комментарии сохраняются после восстановления |
| Новый atomic import | 9 regression cases PR #14 прошли в полном pytest; изменения импорта не нарушили planner |

Порядок тем: Fractions, Equations, Proportions, Geometry, Statistics, Revision.

Новый браузерный P0 plan ID: `32a48c69-05a4-458b-8df0-4cec2e664aa9`.
Новый браузерный Period plan ID: `bb8ae49e-9993-4e10-9cac-3f4c293165a7`.

Actual Period save: `settings={target_pct:70,donor_pct:80,min_students:10,max_change:2,mode:"period"}`, `hours_by_topic={fractions:6,equations:8,proportions:4,geometry:3,statistics:2,revision:1}` → **201 / period_v1 / manually_modified=true**. `max_change=2` в payload корректно не применяется сервером в period-режиме.

## Тесты без двойного подсчёта

| Запуск | Результат |
| --- | --- |
| Полный pytest исходного PR #14 | **436 passed / 0 failed / 0 skipped**, 102 subtests отдельно |
| Дополнительный собственный QA-файл | **15 passed / 0 failed / 0 skipped** |
| Frontend `npm test` | **8 passed / 0 failed / 0 skipped** |
| TypeScript/Vite production build | PASS |
| Реальный TypeScript/Python Period parity | **200 случаев passed** |
| Реальный HTTP/SQLite E2E с restart | PASS: dry-run/import/dedup, overview/analytics/comparison/Teachers, оба planner/manual/save/JSON/CSV, comments/offline AI, ошибки и rollback |
| Chrome, focused Planner review | PASS для открывания старых отчётов, direct manual input/save/report/export/reload/restart; **FAIL для кнопки +** |

В PR #14 `pytest.ini` уже включает `qa`: **7 существующих acceptance-тестов входят в 436**, повторно они не прибавлены. 15 дополнительных случаев перенесены из собственной QA-ветки и запущены отдельно после полного upstream-прогона. Итог независимых Python test cases — 451; 102 subtests не прибавляются. Эти 15 QA-cases не являются исправлением production-кода. Один Starlette/httpx deprecation warning, без падений.

Команды из корня checkout:

```text
python -m pytest -q
python -m pytest -q qa/test_final_period_atomicity.py
npm --prefix web test
npm --prefix web run build
python scripts/check_period_parity.py web
python qa/check_http_e2e.py . data/pr14-http.json
```

После добавления дополнительного QA-файла первый запуск соберёт также его 15 случаев; не складывать его результат с отдельным повтором файла. Первоначальный запуск parity без аргумента завершился ошибкой вызова; исправленная команда с `web` дала 200 PASS.

## Границы browser review

Использованы реальный Chrome, production React из `aaa78e1`, FastAPI и отдельная SQLite на localhost:8769, только синтетические данные. Доступ браузера **в этой проверке работал**, в отличие от предыдущего общего прогона Бекзата. Неподменённые planner HTTP запросы/ответы зафиксированы локальной QA-обёрткой; основные тесты используют обычное приложение.

Это **focused Planner browser review**, а не полный CSV → mobile E2E. CSV picker заново не проверялся, его прежний permission blocker не объявляется устранённым. HTTP dry-run/import выполнены отдельно. Шесть ширин, физические mobile devices, frontend Retry/body-timeout и внешняя публикация остаются задачей Дамира. Docker здесь повторно не запускался; 19 групп из отчёта Бекзата не выдаются за новый прогон Айданы.

Доказательства: [JSON evidence](../qa/evidence/pr14-planner-review.json), [stepper при корректной сумме 24](../qa/evidence/pr14-stepper-blocked.jpg), [сохранённый +3 отчёт после restart](../qa/evidence/pr14-report-after-restart.jpg). Полные локальные логи: `output/aidana-pr14-review` рядом с checkout.

## Handoff и вердикт

PR #14: **OPEN / DRAFT**, проверенный HEAD `aaa78e1`. GitHub показывает 8 разных job names, все успешны для push и pull_request: **16 check records, без удвоения количества сценариев**. Review Айданы передан в PR #14, замечание по кнопкам — Дамиру в PR #9.

В собственной ветке `qa/aidana-pr14-review-20261110` только QA, отчёт и синтетические доказательства. Production/frontend и ветки участников не изменялись. Merge, force push, deployment и новые функции не выполнялись.

- **GO — P0 и серверный Period Planner:** ручные данные и сохранённые отчёты совместимы с интеграцией, повреждения SQLite не обнаружено.
- **NO-GO — окончательная приёмка Period UI:** требуется исправление кнопок ±2 и повтор regression.
- **NO-GO — весь продукт / публичный запуск:** остаются известный frontend body-timeout и общий browser/mobile acceptance. Этот review не является Approve всей сборки.

После fix Дамира повторить ровно affected planner controls и transport/browser gates на новом integration SHA; исправления backend Planner по этому review не требуются.
