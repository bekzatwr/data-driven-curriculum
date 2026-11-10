# Передача period planner Айданы без обхода GitHub 403

**Обновление 10 ноября: код уже опубликован Айданой в [PR #10](https://github.com/bekzatwr/data-driven-curriculum/pull/10), `feature/aidana-period-planner:37c0dd9`.** Первоначальный GitHub 403 больше не блокирует получение этой реализации. Ниже — запасная инструкция на случай новой проблемы публикации, а не требование передать уже доступный код повторно. Проверка опубликованного SHA описана в [PRE_INTEGRATION_STATUS](PRE_INTEGRATION_STATUS.md). Patch/bundle не получали; код получен через git fetch и протестирован отдельно, без merge.

## Сначала согласовать передачу

Айдана и капитан фиксируют: исходный репозиторий, полный `base SHA`, полный `HEAD SHA`, название локальной ветки, авторство, состав изменений, готовность или WIP, разрешённый канал передачи и получателя. Токены, пароли и `.env` не передаются. Бекзат не входит под аккаунтом Айданы и не пишет в её remote-ветку.

Обычный путь устранения 403: владелец проверяет приглашение/роль участника; Айдана — `git remote -v`, используемый GitHub-аккаунт и разрешения собственного средства входа. В отчёт достаточно обезличенного текста ошибки и операции (push/PR/API), без заголовков Authorization. Права доступа не обходятся и не расширяются автоматически.

Если код передаётся файлом, отправитель явно подтверждает именно этот HEAD и SHA256 файлов. Контрольная сумма проверяет целостность передачи, но сама по себе не удостоверяет автора. Пока автор не подтвердил завершение, файл можно изучать изолированно; включать его в общую ветку нельзя.

## Вариант A — bundle, предпочтительно при merge-коммитах

Команды ниже выполняет **Айдана в своём репозитории**, после замены `AGREED_BASE_SHA` на согласованный существующий commit. Это инструкция, сейчас она не выполнялась.

```powershell
$periodBaseSha = 'AGREED_BASE_SHA'
git status --short
git rev-parse HEAD
git merge-base --is-ancestor $periodBaseSha HEAD
git log --format='%H %an %s' "$periodBaseSha..HEAD"
git diff --check $periodBaseSha HEAD
git diff --stat $periodBaseSha HEAD
New-Item -ItemType Directory -Force -Path ../aidana-handoff | Out-Null
git bundle create ../aidana-handoff/aidana-period.bundle "$periodBaseSha..HEAD"
git bundle verify ../aidana-handoff/aidana-period.bundle
git bundle list-heads ../aidana-handoff/aidana-period.bundle
Get-FileHash ../aidana-handoff/aidana-period.bundle -Algorithm SHA256
```

Остановиться при ненулевом exit code; не продолжать набор команд автоматически после ошибки. Сохранить исходники в коммитах до экспорта: bundle не включает незакоммиченные изменения. Ограниченный bundle требует наличия base/history у получателя. Если prerequisite отсутствует, согласовать базу или более полный bundle; не использовать force или подмену истории. [Документация Git bundle](https://git-scm.com/docs/git-bundle).

## Вариант B — серия patches для линейной истории

Подходит, если `git rev-list --merges "$periodBaseSha..HEAD"` пуст. При merge-коммитах использовать bundle: обычный format-patch не является полной передачей merge-истории.

```powershell
git format-patch --binary --full-index --base=$periodBaseSha --output-directory ../aidana-handoff/patches "$periodBaseSha..HEAD"
Get-ChildItem -LiteralPath ../aidana-handoff/patches -File -Filter '*.patch' | Get-FileHash -Algorithm SHA256
```

Проверить, что экспортируется только согласованная работа: planner, связанные tests/contracts/docs; `.env`, SQLite, реальные данные и посторонние изменения не входят в передаваемые коммиты. Не применять фильтрацию путей, которая незаметно удалит зависимости реализации. [Документация format-patch](https://git-scm.com/docs/git-format-patch).

## Что приложить к bundle/patch

- `base SHA`, `HEAD SHA`, порядок patches и SHA256, подтверждение автора и WIP/готовность.
- Список изменённых файлов и зависимостей; отдельное описание изменений хранения и совместимости старых snapshot.
- Запрос/ответ `settings.mode="period"`, OpenAPI/schema, пример сохранённого JSON/CSV на synthetic data.
- Команды тестов с реальными passed/failed/skipped; сохранить проверки старого P0 и atomic save.
- Неуспешные случаи: невозможный бюджет часов, min/max/locked, ручные правки, валидация/сериализация перед commit, rollback и restart/restore.

## Приём Бекзатом

1. Положить согласованный файл в игнорируемый `data/handoff-incoming/`, сверить SHA256 с подтверждением Айданы. Не публиковать архив автоматически.
2. Для bundle выполнить `git bundle verify` и `git bundle list-heads`; для patches — прочитать diff, `git apply --stat` и `git apply --summary`. Не запускать присланные скрипты и не применять изменения к рабочей ветке.
3. После подтверждения состава разрешённый bundle можно получить в отдельный локальный ref (`refs/remotes/handoff/aidana-period`) и прочитать `git diff BASE...REF`. Это только intake, не включение в приложение. Любые неожиданные пути, hooks/CI, Docker, secrets или изменения чужих модулей обсудить с автором.
4. **Только после подтверждения завершения и согласования команды** создать отдельную integration/worktree-ветку от согласованной базы. Для patches использовать `git am --3way` по порядку; при конфликте остановиться и разбирать вместе с Айданой. Для bundle сохранить исходные commits и авторство, без squash/force или перезаписи её ветки.
5. После code review выполнить тестовую матрицу из [PRE_INTEGRATION_STATUS](PRE_INTEGRATION_STATUS.md), регенерировать контракты и проверить старые snapshot. Получение файла или успешный `git apply --check` ещё не означает готовую интеграцию.
6. Публикация — отдельная согласованная ветка/PR получателя с указанием происхождения и HEAD Айданы. Публикация в `planner/aidana`, merge в main и запуск сайта не входят в этот протокол без последующего решения команды.

**Текущий итог:** PR #10 опубликован, блокер поставки снят. Запасная процедура не выполнялась: никаких patches не применено, алгоритм не реализован вместо Айданы, интеграция не выполнена. Следующие шаги — review опубликованного кода и общая приёмка после завершения команды.
