# Контракты общего сервера

P1: `GET /api/datasets/{id}/teachers` и `features.teachers_api=true`. Примеры `analytics-teachers.response.json` и `integrated-analytics-teachers.response.json` включают нагрузку, средние по школам и ограничения. [Формулы и подключение UI](../docs/TONI_P1.md).

`openapi.json` описывает действующие маршруты импорта, аналитики Тони, сравнения учебников и планировщика Айданы в стандартном `backend.app.main.create_app()`. Живая схема — `/openapi.json`. `/api/capabilities` сообщает `analytics=true`, `textbook_comparison=true` и доступность плана/отчёта/CSV.

`analytics.openapi.json` — схема отдельного демоприложения аналитики. `analytics-*.response.json` получены из его реальных ответов: обзор, детали темы, сравнение, пустая выборка и ошибка. Поля и единицы описаны в [TONI.md](../docs/TONI.md). Предварительный `analytics-p0.proposed.openapi.json` удалён после реализации; его enum и имена `status`/`gain_difference_pp` не являются текущим контрактом сравнения. Используйте `comparison_status`/`difference_gain_pp` из действующих схем.

Общий `/api/datasets/demo` и CSV Тони используют `analytics.demo.demo_files()`. `*.response.json` — искусственные примеры, а не существующие наборы на сервере. `__DATASET_ID__`, `__CREATED_AT__`, `__PLAN_ID__`, `__PLAN_CREATED_AT__` заменяют изменяющиеся значения; в приложении брать ID и время из API.

- `demo-import.response.json`: успешный `POST /api/datasets/demo`, HTTP 201.
- `filters.response.json`: классы, учебники, темы и версии тестов.
- `results-page.response.json`: первые три строки из 1440; `total` относится ко всей выборке.
- `quality.response.json`: структурная полнота набора, не образовательная оценка.
- `capabilities.response.json`: функции и ограничения общего сервера.
- `integrated-plan-preview.response.json`, `integrated-plan-saved.response.json`: ответы общего приложения с моделями `PlanPreview` и `SavedPlan`.
- `plan-*.json`: исходные примеры изолированного демо Айданы; его фиксированные ID отличаются от общего сервера.
- `dataset-package.schema.json`, `dataset-package.example.json`: перенос исходного набора между серверами.
- `import-error.response.json`: строка с баллом выше максимума, HTTP 422.
- `results.template.csv`, `curriculum.template.csv`: заголовки CSV для заполнения.
- `plan-review-input.schema.json`: структура будущего входа P1; готовых маршрутов повторной проверки нет.

Генерация из корня после `python scripts/start.py --dev --install-only`:

```powershell
.\.venv\Scripts\python.exe scripts/export_contracts.py
.\.venv\Scripts\python.exe -m scripts.export_analytics_contracts
```

В Linux/macOS используйте `.venv/bin/python`. Генератор общего сервера использует временную SQLite и не меняет рабочую базу. Схемы OpenAPI зависят от установленных FastAPI/Pydantic: общий сервер проверяется с `requirements-dev.txt`, а не со старыми зависимостями отдельных демо.

Изменение публичных полей сопровождать обновлением схемы и примера в том же PR. CI сверяет генерируемые контракты с файлами репозитория. Сохранённый отчёт строится из `GET /api/plans/{id}` и не должен пересчитываться по текущим фильтрам аналитики.
