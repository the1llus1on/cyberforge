# Phase 2 — незалежний pre-acceptance technical audit

**Статус:** REVIEW. База порівняння — origin/main, поточний PR #3.
Переглянуто SRS v3.0, AGENTS, план, журнал, ADR та Phase 2 diff: домен,
identity/application/groups, persistence й міграцію, UI/navigation/geometry/
clipboard, CLI/demo, тести, залежності, CI і документацію. Локальні owner
дані, credentials і налаштування ОС не читали/не змінювали.

## Архітектура та підтверджені межі

Модульний моноліт відповідає SRS §§2–3,14–16,21–23. Domain DTO не містять
hash/credentials; identity ізолює Argon2id і process-local sessions; application
перевіряє дозволи; groups не дублює user/password logic; persistence володіє
однією схемою й connection policy; UI не надає прав видимістю кнопок.
Main є composition root. Немає сценарних/LLM сутностей або runtime MCP.
Додавання generic repository/framework або async redesign не обґрунтоване
знайденими дефектами й не виконувалося.

Записи використовують BEGIN IMMEDIATE, sessionmaker.begin закриває session
і робить commit/rollback. Scope перевіряється перед privileged operation;
різні токени не взаємозамінні. Version та credential fingerprint захищають
від reset/role/active changes і повторного SQLite ID. Останній активний
Administrator захищений, у тому числі тестом конкурентної деактивації.
Argon2id, salt/rehash, generic login error, hidden SQL parameters і DTO без
хешів перевірено. Role triggers, FK/unique/check, M:N, metadata consistency,
upgrade/downgrade й повторне відкриття БД мають автоматизовані докази.

При exit/close таймер зупиняється, поточний token відкликається, sensitive UI
очищається. Engine dispose виконується в CLI finally. Normal init не seed-ить
акаунтів; bootstrap лише порожня БД; demo — явний ідемпотентний setup,
O_EXCL credentials, rollback при колізії. POSIX permissions тестуються у
subprocess з umask000. Наявні файли/права не перезаписуються.

## Відтворені дефекти та вузькі виправлення

| Дефект | Виправлення / доказ |
|---|---|
| Після logout лишалися admin search texts | Clear filters під час session cleanup; refresh зберігає поточні filters. GUI regression двох входів. |
| `save_group(instructors=...)` міг очистити learners, і навпаки | Односторонній набір відхиляється до змін; None/None — metadata-only; обидва tuples — atomic replacement. Negative rollback tests. |
| Create ігнорував unchecked Active | Передано active у service/_create, login inactive заборонено. GUI create-inactive test. |
| Редагування групи прибирало inactive members | Відтворено failing GUI test до fix. Існуючі inactive checked members показуються й зберігаються; нове inactive assignment заборонено, явне removal дозволено. |
| SQLite lock/open/migration errors виходили в Qt/CLI traceback | DBAPIError → safe ApplicationError; UI fail-closed cleanup; startup errors без raw SQL/path/traceback. Реальний exclusive-lock test, recovery і corrupt-file preservation. |
| Guard delete перевіряв усі FK так, ніби вони посилаються на users.id | Correlated query враховує constrained/referred columns, alternate unique username, регістр назви таблиці та parent collation; historical CASCADE tests не втрачають даних. |
| Cancel/New могли показувати «Зміни збережено» | Cancel повертає no-change, нова форма/cancel не показують success-save message; GUI confirmation test. |
| Windows isolated CLI використовував CP1252 у pipe | Реальний Windows CI відтворив UnicodeEncodeError після demo setup і escaped stderr. Перенаправлені stdout/stderr явно UTF-8; interactive console не змінюється. Regression з CP1252 streams та CLI subprocess. |

Жодна зміна не послаблює RBAC чи password protections. Історичні FK
перевіряються без створення Phase 3 моделей; synthetic history tables існують
тільки в тимчасових test databases. Деактивація зберігає membership, але не
дозволяє вхід або нове призначення неактивного користувача.

SQLite FK порівнює значення з collation/affinity батьківської колонки;
тому в guard вона стоїть зліва. Тест NOCASE спершу відтворив втрату
history через CASCADE, після виправлення delete відхиляється.
[Правила SQLite FK](https://www.sqlite.org/foreignkeys.html) враховано без
додавання майбутніх production entities.

## Windows CI

Workflow тепер має matrix ubuntu-latest / windows-2022, fail-fast=false,
Python3.12 через uv, uv sync --locked, Ruff, повний pytest і explicit
package import + Qt event-loop CLI smoke у runner.temp. Windows environment
має PYTHONUTF8=1 та QT_QPA_PLATFORM=offscreen; Linux apt step conditional.
Міграції й DB інтеграції входять у повний pytest. Два POSIX mode tests
очікувано skip на Windows, Windows DACL цим не доводяться.

[Офіційний windows-2022 image](https://github.com/actions/runner-images/blob/main/images/windows/Windows2022-Readme.md)
— Windows Server 2022, не desktop Windows11. Такий CI перевіряє імпорт,
locked dependency compatibility, SQLite/Alembic/Argon2id, service/RBAC і
відрендерений offscreen Qt. Він не перевіряє фізичну клавіатуру, compositor,
clipboard bridge, desktop fonts/DPI, ACL власного профілю або інсталятор.
На Windows host власника нічого не встановлювалося.

Перший фактичний [matrix run для 5eb443a](https://github.com/the1llus1on/cyberforge/actions/runs/43102780570):
Linux успішний; Windows — 113 passed, 2 POSIX skips, 2 CLI failures.
Обидва failures спричинено redirected CP1252, не GUI/DB/RBAC. Виправлення
внесено в application CLI, перевірки не вимикалися. Поточний повторний
результат доступний у checks PR #3; hosted CI залишається окремим від
фізичного Windows 11 gate.

## Чому 6ba0a6a queued

Через GitHub app MCP: run43098666057 status=queued, jobs=[]; logs відсутні.
Для додаткових полів використано read-only gh api (MCP wrapper їх опускає):
event=pull_request, path=.github/workflows/ci.yml, attempt1, created_at і
updated_at однакові. Час створення — 22:53:35 Kyiv 11.11.2026. YAML має
ubuntu-latest, без environment approval/self-hosted/concurrency gate; та сама
конфігурація успішно виконала run6 до інциденту. Неправильних labels не знайдено.

[GitHub incident](https://www.githubstatus.com/incidents/dvy0t3mvh1lg) почався
22:48 Kyiv 11.11.2026, Actions позначено major_outage. Це підтверджений
зовнішній інцидент до створення run і узгоджене пояснення затримки перед jobs,
а не помилка тестів або Python. Точний внутрішній per-run scheduler reason
API не надає; billing/capacity конкретного акаунта не вигадуються.
Queued не є success. Checks не вимикали, continue-on-error не додавали,
old runs не скасовували; нові jobs можуть чекати відновлення GitHub.
Повторний API-запит після завершення run43102780570 все ще повертав для
старого run43098666057 queued. Новий matrix уже виконувався; це не дає
підстав вважати старий run успішним або приписувати йому test failure.

## Автоматизовані докази та межі

Повний pytest і WSLg GUI запущено після audit fixes; результати зафіксовано
в DEVELOPMENT_LOG. YAML matrix розібрано доступним системним parser без
нових залежностей. Перевірено uv sync --locked --offline, import, CLI smoke,
build, пакетну міграцію й isolated wheel startup. Тести offline без LLM.

Автотести не доводять фізичну Win11/WSLg поведінку. Залишкові owner tests —
[окремий короткий checklist](../PHASE_2_ACCEPTANCE.md). Acceptance не надано;
Phase 2 — REVIEW, merge/Phase 3 не виконуються.

Підсумок локального head: **119 pytest passed**, **73 WSLg GUI passed**,
Ruff lint/format, locked sync/import/startup/build/isolated wheel — успіх.
Початковий hosted Windows failure й виправлення описано вище; актуальний
результат повторного workflow слід перевіряти в checks PR #3.
