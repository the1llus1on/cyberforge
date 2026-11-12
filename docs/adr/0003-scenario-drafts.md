# ADR-0003 — Ідентичність, версії, архів і бажані ознаки листа

**Статус:** прийнято власником разом із Phase3 12.11.2026; F01–F03 незалежно
reviewed за підтвердженням власника. Manual WSLg evidence — часткове.
**Джерело:** SRS v3.0 §§2.2–2.4, 3.5–3.8, 4, 11, 14, 16.6, 17, 21–23.
**Дата:** 12.11.2026. SRS не змінено.

## Погоджена межа та ідентичність

Власник явно включив зворотне архівування в Phase 3 під час remediation
F-01–F-03. Це замінює попереднє відкрите питання про відкладання функції.
Публікація, призначення учням і наслідки для активних проходжень поза обсягом.

`scenarios` містить постійний AUTOINCREMENT ID, незмінного автора та дату
створення UTC. Назва обчислюється як `Сценарій {id}`, тема зберігається окремо.
`scenario_versions` має унікальні `(scenario_id, number)`, ревізію, статус,
version timestamps та JSON-знімок параметрів Pydantic v2. Обидва UI-режими
використовують один ScenarioService та один каталог, без копій сутностей.

Поля §§4.3/11.1: тема, бажана складність, аудиторія, опис, мета, власні
тактики, бажані ознаки листа та додатковий JSON-об’єкт генерації. Ліміти:
тема 1–2000, аудиторія до 1000, опис/мета до 10000, тактики до 100 записів
по 1–200 символів, увесь JSON до 50000 символів. Параметри не виконуються
як код. Scenario/ScenarioParameters і get() — контракт для пізніших генераторів.

## Зворотний архів і конкурентні зміни

Архів — metadata ідентичності, відокремлена від draft/published версії:
`archived_at` (UTC або NULL) та `archive_revision` (початково 0).
Archive встановлює час; Restore очищає його; кожен перехід збільшує тільки
archive_revision. ID, автор, created_at, усі version rows/параметри/status/
revision/timestamps залишаються незмінними. Нової content-версії немає.
Повторна операція з актуальним очікуваним станом — no-op, час не оновлюється.
Застарілий контекст відхиляється. Архів переживає restart, видалення немає.

Окремий counter потрібний для захисту від циклу archive → restore між
відкриттям форми та її Save: content revision у такому циклі не змінюється,
але старий редактор повинен повторно відкрити актуальний стан. Write API
перевіряють очікувані version, revision та archive_revision в наявній
BEGIN IMMEDIATE транзакції разом із правами. Compatibility default 0 у
update() дозволяє початковим Phase3 клієнтам працювати з ніколи не
архівованими сценаріями; після переходів потрібний актуальний counter.
Archive/Restore вимагають явного контексту. Locking/revision checks не послаблено.

Instructor/Administrator змінюють тільки власні сценарії. Administrator
читає також чужі активні/архівні записи, без зміни їх archive state або
контенту. Guest/Learner/неактивна чи відкликана сесія не мають management
доступу. Невідомий та чужий ID дають однакову відмову. Архівні сценарії
читаються власником/адміністратором, а редагуються лише після Restore.

Один catalog API має active (default), archived та all запити; у UI один
QListWidget і фільтр «Архівні сценарії». Пошук поєднується з цим фільтром.
Archive/Restore автоматично показують відповідний фільтр, зберігаючи ID.
Аналіз лишається read-only, показує архівний стан і відсутність результатів.

## Міграції та захист SQLite

0002 не редагується. Адитивна `0003_scenario_archive` додає дві колонки через
ALTER ADD COLUMN, без recreation/reset таблиць або переписування JSON.
Шлях 0001 → 0002 → 0003 і наявна 0002 підтримуються; IDs, SQLite sequence,
користувачі/групи й сирі version rows зберігаються. ORM metadata узгоджена.

`scenario_identity_update` тепер відхиляє лише зміну id, owner_id або
created_at (`IS NOT`), дозволяючи схвалену mutable metadata. Окремий trigger
перевіряє archive transitions, дату та відповідний приріст counter.
Архівні version rows захищені від INSERT/UPDATE/DELETE також прямим SQL;
для UPDATE перевіряються початковий і новий parent scenario. Published
UPDATE/DELETE triggers незмінні, діють незалежно від archive state.
Downgrade 0003 відхиляється після archive history, щоб не стерти її мовчки;
fresh empty downgrade використовується лише в ізольованих тестах.

Draft Save оновлює ту саму версію та збільшує content revision. No-op Save
нічого не змінює. Зміни після published створюють наступну draft; незмінний
опублікований JSON зберігається. Publishing API немає; цей шлях перевіряється
fixture-даними. Міграція не оголошує контент готовим або доступним учням.

## F-03: перевірений каталог NIST та legacy-дані

Джерело: Shanée Dawkins, Jody Jacobs, **NIST Phish Scale User Guide**, NIST
TN 2276, November 2023; публікація 15.11.2023 за офіційною сторінкою NIST.
DOI: https://doi.org/10.6028/NIST.TN.2276.
PDF: https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.2276.pdf.
Metadata: https://www.nist.gov/publications/nist-phish-scale-user-guide.
Перевірено 12.11.2026: §2.1.1, Table1 (printed p6 / PDF page13), AppendixB
(printed pp29–36), включно з оригінальною таблицею PDF.

Каталог `nist_cues.py` містить усі 23 cues. Оригінальні cue types Table1:
Error; Technical indicator; Visual presentation indicator; Language and
content; Common tactic. Це типи ознак, а не категорії кількості Few/Some/Many.
ID — наявні посилання Appendix B від B.1.1 до B.5.6 у namespace
`nist-tn-2276:2023`; це адреси пунктів, не вигадані номери стандарту.
Original English names збережені; українські labels — переклад CyberForge,
не офіційний переклад NIST. Селектор показує українські назви, оригінальний
термін і type — в tooltip. Зберігаються IDs, не тексти UI.

Новий `nist_cues` приймає лише enum каталогу без повторів; невідомі IDs,
назви замість IDs та невідомі catalog versions відхиляються. Власні тактики
залишаються окремим вільним полем. Desired cues не є AI-declared або verified
cues. Наявність, Cue Count, Premise Alignment, Detection Difficulty, оцінки
учня та класифікація Web не обчислюються.

Legacy strategy: JSON без `nist_cue_catalog` адаптується лише під час читання:
всі старі рядки переходять у `legacy_nist_cues`, desired IDs порожні. Навіть
точне співпадіння назви або схожість на ID не є підставою автоматично
класифікувати старий текст. Оригінальний JSON залишається побайтово незмінним.
UI показує legacy text окремо для читання/копіювання. При справжньому Save
змін чернетки новий формат зберігається з усіма legacy strings; сервіс
забороняє їх зміну/видалення через update. Для published зміни створюють draft,
історичний JSON не змінюється. No-op Save адаптованого snapshot не створює
версію чи ревізію лише через зміну формату. Користувач явно позначає desired
IDs; старі рядки залишаються без автоматичного mapping. Новим сценаріям
legacy strings через create не додаються — власні побажання йдуть у tactics.
Обмеження: семантичне зіставлення старих назв автоматично не підтверджується.

## Незбережені зміни та сесія

Навігація, New, selection, archive filter, закриття та lifecycle actions
використовують Save/Discard/Cancel, Cancel default. Перед Archive додаткове
явне підтвердження. Невдалий/застарілий Save не дозволяє archive/перехід і
зберігає input. «Скасувати зміни» має окреме підтвердження відкидання без
можливості несподіваного Save; повертає актуальні збережені параметри.

Зовнішній Archive блокує форму, зберігаючи dirty buffer для копіювання.
Зовнішній Restore не надає старому буферу новий expected counter: stale Save
відхиляється, потрібне повторне відкриття. Read-only fields/selector дозволяють
перегляд, copy, scroll і keyboard navigation. Відкликання сесії очищає всі
захищені дані; воно не залежить від згоди на збереження.

## Докази й межі

Перевірки й exact commands — IMPLEMENTATION_PLAN / DEVELOPMENT_LOG.
Concurrency покриває незалежні Database/AccountService/sessions, два GUI
вікна та два OS-процеси на одній temporary SQLite. Baseline без мережі/ключів.
За окремим рішенням власника 12.11.2026 основне manual acceptance Phases3–11
виконується у WSLg; routine physical native Windows11 перевірку відкладено
до Phase12. Конкретний Windows-specific дефект або суттєвий ризик дозволяє
ранню native перевірку. Windows CI обов’язковий, але не замінює physical gate.
Відкладення — відкритий ризик, не підтвердження Windows11; SRS §24 лишається
чинним. Повний Phase12 gate і workflow — IMPLEMENTATION_PLAN та AGENTS.md.
Існуючий native workspace Phase2 зберігається без оновлення. Phase3 ACCEPTED
власником 12.11.2026; це не означає виконання всіх manual checks або фізичної
Windows11 перевірки. Phase4 — NOT STARTED до окремого дозволу.
