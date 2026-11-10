# Контракты backend

**P0, 10 ноября:** живая `openapi.json` включает четыре маршрута Айданы с моделями `PlanPreview` и `SavedPlan`, ошибками и CSV media type. `integrated-plan-preview.response.json` и `integrated-plan-saved.response.json` получены из общего приложения; ID заменены placeholders. Исходные `plan-*.json` Айданы сохранены и относятся к её изолированному демо.

`analytics-p0.proposed.openapi.json` — отдельный проект интерфейса для review Тони, НЕ описание реализованных маршрутов. Он не добавляется в live OpenAPI. Подробные границы и фильтры — `docs/P0_INTEGRATION.md`.

`openapi.json` — схема реально реализованных маршрутов Бекзата; актуальная живая версия доступна на `/openapi.json`. `*.response.json` получены вызовами приложения на синтетическом демо. `__DATASET_ID__` и `__CREATED_AT__` — заменители изменяющихся значений; в рабочем приложении брать их из ответа API.

- `demo-import.response.json`: успешный `POST /api/datasets/demo`, HTTP 201.
- `filters.response.json`: классы, учебники, темы и версии тестов.
- `results-page.response.json`: первые 3 строки из 1 440; `total` относится ко всей выборке.
- `import-error.response.json`: строка с баллом выше максимума, HTTP 422.
- `results.template.csv`, `curriculum.template.csv`: только заголовки; перед импортом добавить строки данных.
- `plan-review-input.schema.json`: будущий вход P1. Это схема структуры, а не обещание готовых маршрутов review.

Генерация из корня после установки dev-зависимостей:

```powershell
.\.venv\Scripts\python.exe scripts/export_contracts.py
```

В Linux/macOS использовать `.venv/bin/python`. Генератор создаёт и удаляет отдельную временную SQLite, не трогая рабочую базу.

Тони добавляет контракт аналитики/сравнения, Айдана — контракты preview/save/report. После подключения их роутеров обновить генератор, чтобы OpenAPI включал весь сервер. Изменение публичных полей сопровождать обновлением схемы и примера в том же PR.
