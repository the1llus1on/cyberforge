# CyberForge — Implementation Plan

**Normative source:** `TECHNICAL_SPECIFICATION.md` (SRS v3.0, 11.11.2026), especially §§0, 21–24, 26–27.
**State:** Phases 0–8 — ACCEPTED (Phase8 прийнято власником 2026-11-17); Phase9 — REVIEW (implementation authorized 2026-11-17; owner acceptance pending); Phases10–12 — NOT STARTED (без змін).
**Rule:** Execute only one user-approved phase at a time; never automatically move to the next phase.

## Definitions of status

- **NOT STARTED** — no implementation evidence.
- **IN PROGRESS** — approved work underway.
- **BLOCKED** — material prerequisite or decision unavailable.
- **REVIEW** — implementation finished; tests, user review or acceptance outstanding.
- **ACCEPTED** — criteria verified and phase approved by project owner.

## Roadmap

| Phase | Name | Status | Deliverable and acceptance focus |
|---|---|---|---|
| 0 | Project Foundation | ACCEPTED | Python 3.12/uv, src package, CLI, lockfile, pytest/Ruff; власник підтвердив перевірки у WSL Ubuntu та прийняв фазу 11.11.2026 |
| 1 | Main UI Shell | ACCEPTED | Dark PySide6 shell, universal Home / Guest state, sidebar mode controls, shared scenario panel, mode routing; UI smoke tests |
| 2 | Users & Groups | ACCEPTED | Прийнято власником 12.11.2026: login, Argon2id, 3 roles, demo accounts/groups, RBAC; WSLg і native Windows 11 докази нижче |
| 3 | Scenario Management | ACCEPTED | Create/edit scenarios with unique IDs, persistence, statuses, versioned drafts; SQLite integration tests |
| 4 | LLM Integration | ACCEPTED | Прийнято власником 13.11.2026; Groq primary/Hydrogen verified backup, explicit activation; Mock offline; F-01/F-02; accepted residual risks; ADR-0004 |
| 5 | Specialized Agents | ACCEPTED | Прийнято власником 13.11.2026: four agents, typed contracts, bounded LangGraph, provenance/F-01, offline/provider-neutral integration; PHASE_5_ACCEPTANCE.md |
| 6 | Email Constructor | ACCEPTED | Прийнято власником15.11.2026: Email preview/editor, async generation, explicit SQLite Save; PHASE_6_ACCEPTANCE.md |
| 7 | Web Constructor | ACCEPTED | Hybrid components, isolated WebEngine, visual editor, scoped AI, saved Email binding, explicit SQLite Save; PHASE_7_ACCEPTANCE.md |
| 8 | Scenario Integration | ACCEPTED | Typed Email→Web link, rubric definitions/editor, exact readiness/review, atomic immutable publication, audited grants/access; PHASE_8_ACCEPTANCE.md |
| 9 | Learner Simulation | REVIEW | Email/Web exercises, controlled navigation, persistent learner attempt history/events, safe completion without Web; end-to-end tests |
| 10 | Scoring & Mentor | NOT STARTED | Deterministic scoring compatible with published versioned rubric declarations, evaluation, learner result history/detail, LLM explanations without score edits; reproducibility tests |
| 11 | Analytics Mode | NOT STARTED | Read-only scenario statistics, deduplicated learner table, missing-data rules, filters, CSV/JSON export, RBAC; analytics tests |
| 12 | Finalization | NOT STARTED | Full regression/security checks, Windows 11 package, demonstration dataset, docs and release checklist |

## Implementation requirements for each phase

For the active phase, Codex must record:
1. Objective and exact SRS sections/requirements covered.
2. Dependencies and assumptions, including unresolved SRS items.
3. User-visible working outcome and demonstration steps.
4. Target files/modules and a minimal change sequence.
5. Test commands and acceptance criteria (including negative/security cases where applicable).
6. Actual check results and evidence.
7. Remaining work and a recommendation for the next phase.

Each phase can be divided into substeps, but no substep should leave the working branch in an untestable state without documenting the limitation. Use `docs/DEVELOPMENT_LOG.md` for decisions and verification details.

## Phase 0 — first approved unit of work

**Goal:** prepare the repository for reproducible, incremental development; do not implement the complete product or jump ahead to UI functionality.

**Initial actions:**
- Inspect branch, Git status, files, Python/uv/Qt availability and existing MCP integrations where accessible.
- Preserve existing README, code and uncommitted work.
- Confirm the checked-in SRS is v3.0, then read its status labels and Phase 0 scope.
- Identify whether WSL Ubuntu can launch PySide6 and flag Windows-only runtime/build checks separately.
- Create or adjust the minimal project skeleton, `pyproject.toml`, Python package, test and lint configuration, `.gitignore`, `.env.example`, project startup instructions and baseline checks as justified by existing repository state.
- Avoid live API calls and do not add actual secrets. Do not implement LLM agents, databases, role logic, simulators or full UI in this phase.

**Acceptance gate:**
- The repository contains SRS, AGENTS.md and a maintained plan/log.
- Python and dependency setup command is documented and verified in the actual environment.
- A minimal package import and baseline automated test succeed.
- Ruff and pytest commands work (or any environment blocker is explicitly documented).
- No secrets or generated/local state appear in version control.
- Git diff is scoped, and a concise Phase 0 report is available for user review.
- Status changes to REVIEW after evidence is recorded; ACCEPTED only following user approval.

### Phase 0 — виконання та докази (11.11.2026)

- **Вимоги:** SRS §§15.1, 15.4 (Python 3.12, uv, pytest, Ruff), §21
  (базова перевірка), §§22–22.2 (src layout без порожніх майбутніх модулів),
  §23 Phase 0, §27 (перевірки та звіт).
- **Початковий стан:** чиста гілка `chore/phase-0-foundation`, лише документація;
  SRS v3.0 та AGENTS.md наявні; DEVELOPMENT_LOG.md, код і uv відсутні.
- **Послідовність:** мінімальний пакет/CLI → конфігурація й lockfile → тести
  встановлення/запуску → offline lint/test/build → документація.
- **Файли:** `pyproject.toml`, `uv.lock`, `.python-version`, `.env.example`,
  `.gitignore`, `src/cyberforge/{__init__,__main__,main}.py`,
  `tests/test_foundation.py`, README, цей план і DEVELOPMENT_LOG.
- **Демонстрація:** `uv sync --locked`, `uv run cyberforge`; очікується
  українське повідомлення й код 0, без GUI або зовнішніх сервісів.
- **Докази:** `uv sync --locked --offline`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run pytest`, `uv run cyberforge`,
  `uv run python -m cyberforge`, `uv build --offline` — успішні;
  pytest: **2 passed**. Wheel установлено та запущено в окремому середовищі.
  Деталі команд і середовища — у DEVELOPMENT_LOG.
- **Git hygiene:** `git diff --check` успішний; локальні дані ігноруються,
  `.env.example` доступний для відстеження; секретів у доданих файлах немає.
- **Gate:** Phase 0 — ACCEPTED власником 11.11.2026. Власник особисто
  підтвердив у WSL Ubuntu успішні `uv sync --locked`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run pytest` (2 passed) та
  `uv run cyberforge`. Windows-перевірка не виконувалася.
- **Обмеження:** PySide6 відсутній, запуск Qt/Qt WebEngine у WSL та Windows 11
  не перевірено; MockLLMProvider належить Phase 4. ТЗ не змінювалося,
  його формальне затвердження залишається за власником.
- **Наступний крок:** очікувати окремого явного погодження Phase 1.
  Прийняття Phase 0 не є дозволом на її початок. Phase 1–12 не розпочаті.

## Review protocol

The owner evaluates the working demonstration, diff, test evidence and SRS traceability. If approved, Codex may start the next phase in a *new task/session* based on the updated repository plan/log. If rejected, repair only the current phase.

## Phase 1 — Main UI Shell (11.11.2026)

**Поточний статус: ACCEPTED.** Записи реалізації та уточнення нижче зберігають
історичні результати REVIEW; рішення про прийняття й фінальні перевірки
наведено наприкінці цього розділу.

- **Обсяг:** SRS §§3.1–3.8, 3.10–3.13 (у межах оболонки), 15.1/15.4,
  21.1/21.3/21.4, 22–22.2, 23 Phase 1, 27.4.
- **Передумови:** Phase 0 прийнята й об’єднана PR #1 у `main`
  (`1fc4a596`); дерево чисте; `main` оновлено fast-forward; створено
  `feat/phase-1-main-ui-shell`.
- **Послідовність:** політика MCP/Git → PySide6/pytest-qt → тема та
  навігаційний стан → оболонка/порожні представлення → GUI-тести →
  перевірки й демонстрація → документація → commit/push/PR.
- **Архітектура:** `ui/{shell,navigation,pages,icons,theme}.py`; окремі
  представлення у QStackedWidget, єдиний каталог, локальна історія.
- **Межа Guest:** перемикачі відкривають лише явно позначений попередній
  перегляд оболонки. Каталог порожній та закритий; створення й пошук
  недоступні. Авторизації, сценаріїв, тестових користувачів, оцінок,
  persistence та LLM немає; login/profile пояснює майбутній етап.
- **Критерії:** старт на Home у стані Guest; темна тема; видимі й узгоджені активні
  стани; «+» лише перемикає режим; кнопка нового сценарію видима тільки
  в Конструкторі та недоступна гостю; один каталог; переходи назад/вперед;
  клавіатура, прокручування й розміри 860×620–1920×1080; offline тести;
  фактичні докази WSL та окреме позначення неперевіреного Windows 11.
- **Поза gate Phase 1:** справжня форма входу/RBAC (Phase 2), ID та
  сценарії/захист незбережених матеріалів (Phase 3+), AI (Phase 4+),
  обчислення аналітики (Phase 11).
- **Демонстрація:** `uv sync --locked`, `uv run cyberforge`; перемикнути
  «+», «Аналіз», «Назад/Вперед», профіль, налаштування; змінити розмір.
- **Докази:** `uv sync --locked --offline`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run pytest` — успіх, **23 passed**;
  startup CLI та module з `--smoke-test`/offscreen — exit 0;
  `QT_QPA_PLATFORM=wayland uv run cyberforge --smoke-test` — exit 0;
  `QT_QPA_PLATFORM=wayland uv run pytest tests/ui -q` — **19 passed**;
  `uv build --offline` та перевірка вмісту архівів — успіх.
  GUI-перевірки виконані у WSL2, Python 3.12.3, Qt/PySide6 6.10.3.
- **Візуальний огляд:** фактичні знімки WSLg у `docs/screenshots/`; перевірено
  Guest, Аналіз та компактний Конструктор. Регресійний тест перевіряє,
  що текст не обрізається у всіх п’яти представленнях і трьох розмірах.
- **MCP:** GitHub, Context7, OpenAI Developer Docs — функціональні запити
  успішні; політика додана до AGENTS.md, credentials не змінювалися.
- **Обмеження:** Windows 11/DPI ще не перевірені; XCB у цьому WSL не
  завантажується через системну залежність; WSLg Wayland працює поза
  обмеженням sandbox-дисплея. MockLLMProvider ще не існує (Phase 4);
  оболонка і тести не викликають LLM/зовнішні сервіси.
- **Gate:** технічні критерії оболонки у WSL пройдено; **REVIEW**.
  Прийняття власником та Windows-перевірка залишаються відкритими.
  Наступна дія — рев’ю PR/демонстрації; Phase 2 не починати без дозволу.
- **Рев’ю:** [PR #2](https://github.com/the1llus1on/cyberforge/pull/2),
  гілка `feat/phase-1-main-ui-shell`; merge не виконано.


### Уточнення після рев’ю власника — Home (11.11.2026)

- **Статус на момент уточнення:** REVIEW; той самий PR #2 і feature branch.
- **Погоджене відхилення від SRS v3.0:** універсальна Home додається до
  Конструктора й Аналізу; джерело рішення — прямий запит власника.
  [ADR-0001](adr/0001-home-navigation.md) містить рішення, межі та рольову
  матрицю для Phase 2. SRS не редагується.
- **Поведінка:** `View.HOME` відокремлено від `AuthenticationState.GUEST`;
  Home — інформаційна сторінка без каталогу, з привітанням, підказками
  та циклом «Сценарій → Електронний лист → Вебсайт → Аналіз».
  Каталог існує в одному екземплярі й видимий тільки в робочих режимах.
  Повторюваний disclaimer видалено з UI; security-вимоги залишаються чинними.
- **Межі:** автентифікація/RBAC не реалізовані. Home не залежить від ролі;
  контракт після входу — Home для всіх; Administrator/Instructor зберігають
  Конструктор/Аналіз, Learner отримає «Мої сценарії»/«Мої результати» (§3.9).
  Перемикання поточних порожніх режимів не змінює Guest і не дає доступу.
- **Перевірки:** `uv run ruff check .`, `uv run ruff format --check .` — успіх;
  `uv run pytest` — **25 passed** offscreen. CLI/module startup smoke — exit 0.
  `QT_QPA_PLATFORM=wayland uv run pytest tests/ui -q` — **21 passed**;
  Wayland startup smoke — exit 0. Візуально оглянуто Home у двох розмірах
  і компактний Конструктор; докази наведено в журналі розробки.
- **Знімки:** оновлено `phase-1-home.png`, `phase-1-home-compact.png`,
  `phase-1-analytics.png`, `phase-1-compact.png`; старий guest-знімок замінено.
- **Gate:** WSL-перевірки й рев’ю уточнення; Windows 11/DPI залишаються
  неперевіреними. Наступна дія — рев’ю власником; merge та Phase 2 заборонені
  без нового явного погодження.


### Прийняття Phase 1 власником — 11 листопада 2026 року

- **Рішення:** Phase 1 — **ACCEPTED**. Власник особисто запустив і візуально
  перевірив застосунок; схвалив дизайн, Home, Конструктор, Аналіз та уточнення.
  Gate Phase 1 пройдено; попередні записи REVIEW збережені як історія.
- **Фінальна перевірка:** `uv run ruff check .` та
  `uv run ruff format --check .` — успіх; `uv run pytest` — **25 passed**;
  `QT_QPA_PLATFORM=wayland uv run pytest tests/ui -q` — **21 passed**.
  CLI/module startup smoke в offscreen і CLI startup smoke через WSLg — exit 0.
- **Обсяг:** PR #2 містить лише погоджену оболонку Phase 1, тести, необхідні
  залежності та супровідну документацію. SRS v3.0 не змінено; Phase 2 не реалізовано.
- **Git:** власник явно дозволив merge PR #2 до `main` після успішних перевірок;
  перед злиттям перевіряються конфлікти та точний head SHA. Гілки не видаляються.
- **Обмеження доказів:** автоматизовані GUI-перевірки виконані у WSL2/WSLg;
  нативна Windows 11/DPI-верифікація не заявляється. ОС особистої перевірки
  власника в повідомленні про прийняття не вказана.
- **Наступна дія:** Phase 2 готова до окремого погодження, залишається
  **NOT STARTED**. Прийняття Phase 1 та дозвіл merge не дозволяють її початок.

## Phase 2 — Users & Groups (11.11.2026)

**Поточний статус: ACCEPTED власником 12.11.2026.** Нижче збережено історію
реалізації та REVIEW; остаточні докази прийняття наведено наприкінці фази.

Власник явно погодив реалізацію, commit/push/PR. Початок: чиста `main`,
`HEAD == origin/main == fc713837109b3a5b5cd9ad53e10d1fcb223764ee`,
GitHub MCP підтвердив remote; створено `feat/phase-2-users-groups`.

План: моделі Users/LearningGroups/GroupInstructors/GroupLearners і міграція
(§§2.5,14–15) → Argon2id, сесії, service-level RBAC (§§2.7–2.8,16.6) →
рольова оболонка, login/profile/admin (§3, ADR-0001) → явний demo setup (§2.6) →
позитивні/негативні тести, CI, WSLg, документація (§§21–23).
Gate: входи всіх ролей, ізоляція logout/reset, persistence та M:N,
заборонені service/UI шляхи, Alembic consistency, Ruff/pytest/GUI.
Windows 11 потребує окремої перевірки. Сценарії та LLM не входять у фазу.


### Реалізація та gate Phase 2

**Статус на момент первинного gate: REVIEW (11.11.2026).** Остаточне рішення
власника 12.11.2026 — ACCEPTED. Phase 3–12 не розпочато.

- Реалізовано login/logout, три ролі й Guest, Argon2id/rehash, власну зміну
  та адміністративне скидання паролів, відкликання сесій через auth_version.
- SQLite/SQLAlchemy/Alembic: Users, LearningGroups, GroupInstructors,
  GroupLearners; M:N, FK, constraints, role-тригери, транзакційні записи.
- Administrator керує користувачами, ролями, активністю, групами й складом;
  Instructor/Learner мають лише scoped читання груп. Прямі service-виклики
  та навігація перевіряються незалежно від видимості кнопок.
- Рольова оболонка з універсальною Home, повновіконним login, профілем,
  адмінформами й порожніми сценаріями/результатами; logout очищає UI/історію.
- Явна normal/bootstrap/demo ініціалізація; сім точних demo-логінів та дві
  групи SRS §2.6; незалежні випадкові паролі у приватному файлі поза Git.
- Нові модулі domain/identity/application/groups/persistence та дві UI-сторінки;
  README, ADR-0001/0002, журнал, CI й чотири WSLg-знімки оновлено.
- `uv sync --locked --offline`, `uv run --offline ruff check .`,
  `uv run --offline ruff format --check .` — успіх.
- `uv run --offline pytest --tb=short -q` — **68 passed** (147.71 s),
  включно з 8 integration/database/demo-тестами та негативними RBAC-шляхами.
- `QT_QPA_PLATFORM=wayland uv run --offline pytest tests/ui -q --tb=short`
  — **37 passed** (103.62 s); справжній WSLg, не Windows.
- `uv build --offline` — wheel/sdist; міграції присутні, БД/секретів/кешів
  немає; ізольований wheel встановлено і запущено з `/tmp`, exit 0.
- CLI smoke offscreen й WSLg Wayland, login/admin/learner screenshots;
  подробиці команд — DEVELOPMENT_LOG.
- Тести та runtime не використовують мережу/LLM; MockLLMProvider — Phase 4.
  Windows 11/DPI/ACL не перевірено. Міграція перевірена на SQLite у WSL;
  GitHub Actions виконує окрему Linux-перевірку після відкриття PR.

**Наступна дія:** рев’ю PR і демонстрація Phase 2 власником. Не виконувати merge
або Phase 3 без окремого явного дозволу.

**Доставка:** реалізація `83e803d`, гілка відправлена;
[PR #3](https://github.com/the1llus1on/cyberforge/pull/3) відкрито до `main`.
Remote CI запущено; актуальний результат — у checks PR. Merge не виконано.

### Уточнення security review — права SQLite

Phase 2 залишається REVIEW. SRS §§2.8,14.9,16,21.4: нові каталоги БД 0700,
файл 0600 на POSIX без зміни umask або прав наявних файлів. Додано
subprocess-тести з umask 000 для DELETE journal і WAL/SHM та preservation.
Windows ACL не перевірено; див. ADR-0002.

### Повторний owner UI review PR #3

Phase 2 — REVIEW. Погоджено вісім корекцій у коментарі 6804044603:
видалення користувачів із захистами, негайний вибір popup ролі, діагностика
української клавіатури, атомарне збереження групи/складу, чотири фільтри,
Learner default, активний/неактивний selection і deselect, заборона Guest
Constructor/Analytics. План: сервісні зміни (§§2,14.9,16.6) → UI/фільтри
(§3, ADR-0001/0002) → unit/integration/GUI/WSLg (§21) → CI та той самий PR.
SRS незмінний. Фізична клавіатура власника після environment remediation
потребує окремого підтвердження; докази Weston — docs/diagnostics/wslg-keyboard.md.

### Повторна перевірка чотирьох залишкових дефектів

Phase 2 — REVIEW. SRS §§2–3,16.6,21: стандартний QComboBox замість custom
popup, однакові EditableList з focus-out selection cleanup, display name
у Users/search/tooltip та responsive elision. Окремі тести обох списків,
mouse/keyboard dismissal і explicit Save. Для фізичного вводу mapping error
Weston 0x20422 підтверджений повторно; додано незалежний Qt probe й план
native Windows порівняння. Фізичне введення й Windows залишаються неперевіреними.
Owner demo-БД/credentials не змінюються; PR #3 без merge, Phase 3 не починається.

Докази поточного уточнення: Ruff check/format — успіх; повний pytest —
74 passed; WSLg GUI — 34 passed, 3 synthetic-mouse skips із поясненням.
Native mouse selection/dismissal — offscreen/CI; keyboard popup — також WSLg.
Прийняття фізичного UI та українського вводу потребує власника.

### Owner refinement: radio roles / checkbox pickers / shortcut metadata

Phase 2 — REVIEW. План у межах §§2–3,16,21: QRadioButton exclusive role choice
→ NoSelection membership pickers → safe probe фізичних Ctrl events →
unit/GUI/WSLg/CI → той самий PR #3. Сценарії/Phase 3 не починати.
Standard Ukrainian typing підтверджено власником; фізичні shortcut mapping
та Enhanced лишаються окремими відкритими пунктами. Систему не змінювати.

Докази: Ruff — успіх; pytest 79 passed; WSLg GUI 42 passed, без skips.
UI-пункти реалізовано; фізична перевірка radio/checkbox залишається власнику.
Ctrl shortcuts: діагностика готова, корекція відкладена до фактичних event
метаданих, а не synthetic mapping. Enhanced fix у офіційному релізі не
підтверджений. Owner acceptance не надається автоматично.

### Indicator-only / geometry / confirmed clipboard mapping

Phase 2 — REVIEW. SRS §§2–3,16,21: default Qt indicator hit testing замість
row toggle; screen-bounded 1400×900 / 1100×720 і root fallback; sticky admin
actions; exact WSLg Wayland Ctrl mappings на owner physical evidence.
Порядок: UI/Qt geometry → scoped native editing operations → positive/negative
unit+GUI → WSLg 100/150/200% → docs/screenshots/CI → existing PR #3.
Ні Enhanced fix, ні Windows DPI acceptance не заявляються. Phase 3 не починати.

Результат уточнення: Ruff — успіх; pytest106 passed; WSLg GUI69 passed;
layout/indicator tests при 150% і200% Qt scale — по16 passed. Qt minimum hints
передаються на перевіреному WSLg шляху; надано незалежний root fallback.
Знімки1400×900/1100×720 актуальні. Physical acceptance shortcuts/manual resize
та Windows11 DPI лишаються власнику; Enhanced не виправлено. REVIEW збережено.

### Pre-acceptance technical audit

Phase 2 — REVIEW. Прочитано Phase2 diff проти origin/main і SRS/ADR.
Вузькі виправлення data loss (partial save, inactive memberships), active flag,
session filter cleanup, DB error handling і historical FK deletion guard,
правдиві cancel statuses; додано негативні й concurrency тести.
CI matrix Linux/Windows Server2022: locked sync, Ruff, pytest/DB/GUI/import/smoke.
6ba0a6a queued узгоджується з офіційним major outage GitHub Actions; не success.
Повний звіт docs/audits/phase-2-pre-acceptance.md; тільки залишкові фізичні
owner тести — docs/PHASE_2_ACCEPTANCE.md. Phase3/merge заборонені без дозволу.

Підсумок audit head: 119 pytest passed; WSLg73 passed; Ruff/locked sync/
startup/build/isolated wheel — успіх. Стан Windows hosted jobs перевіряється
окремо; до фактичного завершення Windows CI verification не зараховується.

Перший Windows run виявив redirected CP1252 CLI defect; виправлено явним
UTF-8 для pipes, не змінюючи interactive console. Historical FK guard
додатково перевірено з parent NOCASE collation та mixed-case table name.
Повторний matrix run43103905494 для60947fa — success: Linux119 passed,
Windows117 passed/2 POSIX skips; locked sync, Ruff, import/Qt startup — success
на обох OS. Native Windows11 gate не закрито. Phase 2 лишається REVIEW.

### Native Windows 11 acceptance workspace (12.11.2026)

SRS §§2–3,14–15,21–23; REVIEW. Власник підтвердив9/10 WSLg physical checks;
відкритий physical minimum-size defect. План: tracked HEAD export → portable
Windows uv/Python3.12 без PATH/registry → locked install → private profile demo
з ACL → native geometry/probe/startup/tests → launcher і manual checklist.
Workspace D:\Programs\Own\program\cyberforge-win-test, створено новим.
Baseline04f01db: native Python3.12.16/Qt6.10.3/windows backend; pytest117/2skips,
native shell14tests passed. Win32 tracking min1393×947 physical при125%.
Виявлено initial-frame clipping6logical px; вузький showEvent positioning fix
і regression без fixed size. Системні settings/owner existing data не змінено.
Документація й обмеження: docs/diagnostics/native-windows.md. Physical native
acceptance залишається власнику; без merge/Phase3.

Native GUI розширення виявило clipping admin action row при1100×720,
непомітний offscreen: preferred page height730 приviewport656. Вузький
minimumHeightForWidth override зберігає internal scrolling і sticky actions;
регресія посилена до повних bounds та message wrapping. Без redesign/RBAC змін.

Code1e11497: native Windows GUI47passed (включно з admin/roles/buttons і
WM_GETMINMAXINFO), Windows full119passed/2POSIX skips, local121passed,
WSLg75passed. CMD startup і ACL checks успішні. Native125% widget captures
додано в docs/screenshots; поточний desktop scale не змінювався. Owner physical
resize/keyboard/Enhanced/DPI/restart gate лишається відкритим; Phase2 REVIEW.

### Остаточне прийняття Phase 2 — 12.11.2026

Власник явно прийняв Users & Groups та дозволив merge PR #3 після успішного
CI фінального документаційного коміту. Стан **ACCEPTED** замінює попередній
REVIEW; записи вище лишаються історичними. Прийнята реалізація —
`50d89e970559d725ca0f603e3db220b130d55847`; далі змінюється лише документація.

- За повідомленням власника у WSLg перевірено основні user/group operations,
  Guest/Administrator/Instructor/Learner navigation і permissions, radio roles,
  membership controls, persistence/logout, Standard Ukrainian typing/shortcuts.
- За повідомленням власника native Windows 11 підтвердив Ukrainian Enhanced
  input, keyboard shortcuts і фізичне дотримання мінімального розміру вікна.
- Автоматизовані докази прийнятої ревізії: Linux121 passed, Windows119 passed/
  2 POSIX skips; Ruff/locked install/migrations/import/startup та
  [CI run43131852256](https://github.com/the1llus1on/cyberforge/actions/runs/43131852256)
  — success. Окремий native Windows GUI suite47 passed; WSLg GUI75 passed.
- WSLg Enhanced mapping і physical resize нижче minimum лишаються відомими
  environment limitations; native Windows є цільовою платформою.
- Повна фізична DPI100/125/150/200%/multi-monitor матриця не підтверджена
  цим повідомленням власника й не позначається як пройдена.
- SRS v3.0, runtime, schema, dependencies, owner demo/credentials та ізольоване
  Windows environment не змінюються. Merge — звичайний merge commit, після
  перевірки фінального HEAD/CI; branches і локальні дані зберігаються.

**Phase 3 — Scenario Management: NOT STARTED.** Прийняття й merge Phase 2
не є дозволом почати Phase 3 або іншу наступну фазу.

## Phase 9–10 — історія спроб і подання результатів (лише план)

Обидві фази — **NOT STARTED**. Цей запис уточнює вже наявний scope SRS
§§3.9,8,12,23; жодних моделей, міграцій або екранів зараз не додається.

- **Phase 9 — Learner Simulation:** кожне проходження має окрему
  ScenarioAttempt, пов'язану з учнем і опублікованою версією сценарію;
  зберігаються події та стан спроби. Історія власних спроб доступна учню
  після перезапуску; чужі спроби не розкриваються. Безпечне завершення без
  переходу до Web підтримується згідно §8.5.
- **Phase 10 — Scoring & Mentor:** «Мої результати» представляє історію
  власних результатів і деталі конкретної спроби: сценарій/версія, стан,
  фактичні оцінки та пояснення. Відсутній результат, незавершена спроба й
  фактичний нуль відрізняються; незастосовний Web не перетворюється на нуль.
  ScoringService детерміновано обчислює та зберігає результат із прив'язкою
  до версій рубрики/алгоритму й подій; LLM лише пояснює вже обчислене.
- Поточні порожні learner views Phase 2 залишаються чесними заглушками;
  історія спроб і scoring не є реалізованими можливостями прийнятої фази.

## Phase 3 — Scenario Management (12.11.2026)

**Статус: REVIEW.** Власник окремо дозволив початок Phase 3,
commit/push/PR до main, без merge або ACCEPTED. Phase 4 не розпочато.

- Передумови: чиста main, GitHub MCP підтвердив merge PR#3 та remote main
  `5b15ff0a9a963202075b0ed9c652ef4df4b9846a`; fetch/merge --ff-only успішні;
  створено нову `feat/phase-3-scenario-management`.
- План/SRS: §§4.2–4.5/11.1/14.1–14.3 — поля Pydantic, ID та міграція;
  §§2.2–2.4/4.9/11.7/16.6 — ownership, RBAC, версії й захист конфліктів;
  §§3.5–3.8/3.13/21.3 — єдиний каталог, картка, пошук, dirty guard;
  §§21/23 Phase3 — regression, persistence, security/GUI, докази й PR.
- Інкремент 1: domain/scenarios, application/scenarios, ORM і міграція 0002;
  BEGIN IMMEDIATE, draft revision, immutable published fixture/fork.
- Інкремент 2: ScenarioPage, каталог у shell, shared selected ID, read-only
  Analytics empty state, Save/Discard/Cancel і session cleanup.
- Технічні рішення: [ADR-0003](adr/0003-scenario-drafts.md). Відкрите owner
  уточнення: межа архівування §2.3 (правила SRS не деталізовані, питання
  поставлено; функцію не позначено виконаною). Генерація/публікація/оцінювання й
  аналітичні обчислення поза обсягом. Наявні owner DB/credentials/native
  Windows acceptance files не використовуються для тестів і не змінюються.
- Проміжні докази: `uv run --offline pytest tests/test_groups_database.py
  tests/ui/test_shell.py tests/ui/test_accounts_ui.py -q --tb=short` —
  **54 passed**, 199.32s; Ruff lint — success. Нові scenario-тести виконуються.
- Gate: валідне створення/відмова невалідним полям; унікальні ID й restart;
  update без зміни draft number, stale-edit conflict; RBAC для кожної ролі;
  published fixture immutable/fork; один каталог/ID між режимами;
  guard на переходах/New/selection/close; регресії Phase0–2; owner demo.

### Фінальні докази початкової Phase 3 (baseline7d2084d)

- `uv run --offline --locked pytest -q --tb=short` — **163 passed**, 335.36s;
  містить 121 попередню й 42 нові перевірки.
- WSLg повний GUI — **93 passed**, 266.97s; form_actions Qt150% і Qt200% —
  по **2 passed**. Ruff lint/format47files, locked sync, build, CLI/module,
  isolated wheel startup, migration packaging і diff check — success.
- Нові файли: `domain/scenarios.py`, `application/scenarios.py`,
  `ui/scenario_page.py`, `persistence/migrations/versions/0002_scenarios.py`,
  `tests/test_scenarios.py`, `tests/ui/test_scenarios_ui.py`, ADR-0003,
  PHASE_3_ACCEPTANCE.md, три phase-3 screenshots.
- Змінені: `persistence/models.py`, `ui/{shell,pages}.py`, `tests/conftest.py`,
  `tests/test_groups_database.py`, `pyproject.toml`, `uv.lock`, README,
  IMPLEMENTATION_PLAN і DEVELOPMENT_LOG. SRS/AGENTS незмінні.
- Design: незмінна identity + version snapshot; draft number стабільний,
  revision захищає конкурентні правки; published boundary/fork протестовано
  fixture, публікації у runtime немає. Деталі — ADR-0003.
- Технічні локальні checks пройдено; owner acceptance ще не надано.
  Native Windows11 Phase3 не перевірено. Уточнення межі архівування очікує
  відповіді; не позначено реалізованим. Phase 3 — REVIEW, не ACCEPTED.
- Наступна дія: PR review і ручна демонстрація за PHASE_3_ACCEPTANCE.md,
  погодження відкритої межі. Merge і Phase4 не виконувати автоматично.

**Доставка:** implementation `a94a00d`, feature-гілку відправлено;
[PR#4](https://github.com/the1llus1on/cyberforge/pull/4) відкрито до main.
Phase3 REVIEW. CI Linux/Windows запущено (run43171462386); на момент
запису ще in_progress, не зараховано як success. Поточний результат —
[checks](https://github.com/the1llus1on/cyberforge/pull/4/checks).

## Phase 3 — pre-acceptance remediation F-01–F-03

**Статус: REVIEW — готово до повторного незалежного review.** Власник явно включив archive/
restore та схвалив remediation. Попередню відкриту межу архівування закрито.
Baseline7d2084d і PR#4 head підтверджено GitHub MCP; дерево чисте, та сама гілка.

План/SRS: F01/F02 (§§2.3/4.9/14/16.6) — адитивна міграція0003, identity guards,
soft archive, RBAC, archive counter; F03 (§§4.3/11.5/17) — verified desired-cue
catalog і lossless legacy adapter; UI (§§3.5–3.8/21.3) — один каталог/filter,
confirmation, restore, dirty/session safety; §§21–23 — migration/concurrency/
security/UI/regression/package/CI. Рішення — оновлений ADR-0003.

Інкремент persistence/service: archive metadata відокремлена від content
версій, no-op повтори, archive→restore ABA protection, legacy read adapter
без переписування snapshots. Перевірки: 36 попередніх service/migration tests
і 18 початкових нових archive tests пройдено. Наступний combined subset із
NIST і GUI — 67passed/107.01s. Розширений GUI/regression виконується.

Міграція0002/SRS/owner DB/credentials/native Windows acceptance files незмінні.
Немає LLM, publishing, assignment, scoring або Phase4. Final evidence — нижче.

### Підсумок remediation

- **F01 — реалізовано:** soft archive/restore, persistence/restart, owner RBAC,
  readonly inspection/admin, один каталог/filter/search, confirm/dirty safety.
- **F02 — реалізовано:** additive0003, targeted identity trigger, archive state
  guards, immutable published/archived snapshots. Fresh/0001/0002 paths,
  raw snapshot/table preservation, SQL negatives і metadata consistency пройдено.
- **F03 — реалізовано:** verified23-cue catalog/AppendixB IDs, Ukrainian selector,
  strict unknown/duplicate rejection, desired/legacy/custom separation,
  no text mapping і жодного переписування published JSON.
- Concurrency: незалежні Database/AccountService/session, два OS processes,
  два GUI windows, content/metadata conflicts та archive→restore ABA; losing
  buffer збережено, duplicate versions немає. Cancel/revert/session safety перевірено.
- `uv run --offline --locked pytest -q --tb=short`: **208passed**,450.19s.
- WSLg GUI: **109passed**,339.44s; Qt150%/200% form+cue — по **3passed**.
- Targeted archive/migration/NIST: **29passed**,44.33s. Додаткова safe malformed
  stored-data read/update перевірка: NIST suite **8passed**,8.30s.
- Locked sync, Ruff52files, build, CLI/module, packaged migration/catalog,
  isolated wheel startup+archive/restore, diff check — success.
- Змінено21файл remediation відносно baseline: existing domain/service/ORM/UI,
  tests, README і чотири docs; нові nist_cues.py, cue_picker.py, migration0003,
  два test modules і три remediation screenshots. Нових dependencies немає.
- Джерела/рішення: ADR0003. Actual commands/limitations: DEVELOPMENT_LOG.
- Phase3 лишається **REVIEW**, не ACCEPTED. Native Windows11 physical gate
  ще відкритий (PHASE_3_ACCEPTANCE). Попереднє owner scope question про
  архівування вирішене цим дорученням; нових owner decisions немає.
- Доставка: та сама feature-гілка і PR#4; final CI Linux/Windows перевіряється
  після push і фіксується у PR description/final report. Без merge/Phase4.

## Phase3 — final empty state і погоджений workflow (12.11.2026)

Phase3 лишається REVIEW. Власник повідомив про ручні WSLg перевірки кількох
функцій (не повне acceptance) і явно погодив вузьку UI-корекцію та політику.
Baseline/PR4 head d507f45, дерево чисте, та сама feature-гілка.

План: §§3.5–3.8/4.2 — neutral empty/New/existing states у ScenarioPage,
один existing form і збереження selected ID/dirty guards; §21.3 — focused GUI
regressions + final full pytest/Ruff + relevant real WSLg; §§23–24 — policy.
Порожній стан використовує наявний card/label/style; жодного DB write.
New відкриває форму без ID, Save/selection використовують існуючий workflow.

### Рішення про прийняття та ефективність

- Phases3–11: основне manual acceptance у WSLg Ubuntu; automated Linux і
  Windows CI залишаються обов’язковими gates перед окремо дозволеним merge.
- Routine physical native Windows11 acceptance перенесено до Phase12;
  рання native перевірка можлива за конкретного platform defect/significant risk.
  Існуючий native Phase2 workspace не оновлювати й не копіювати нові snapshots.
- Phase12: comprehensive native Windows11, packaging/executable/installer,
  DPI, keyboard, permissions, security, regression та end-to-end verification.
- Це відкладений ризик, не verified Windows11 behavior. Суперечності з SRS
  не виявлено: §24 задає Windows11 criterion завершеного MVP, §23 включає
  Windows-збирання у Phase12. Вимогу не скасовано; SRS не редагується.
- Focused tests спочатку; full pytest/Ruff один раз після стабілізації;
  повтор full suite лише за relevant code changes. Relevant WSLg GUI checks,
  без повтору всіх manual scenarios. Security/data/RBAC/migration/concurrency
  regression tests зберігаються. Packaging/wheel лише за відповідних змін.
- Постійна настанова — AGENTS.md; короткі докази — DEVELOPMENT_LOG.
  Для цього UI-only change packaging/dependencies/migrations/startup не змінено,
  тому build/wheel не повторюються. Final checks/доставка — у журналі.

Результат вузького UI-кроку: logical empty/new/existing states реалізовано,
valid selection/filter/dirty guards збережено, no SQL writes на entry доведено.
Final full pytest214passed/460.94s; Ruff52files і diff check success; final
relevant WSLg9passed/26.75s. Existing minimum-size regression виправлено після
initial WSLg39passed/1failed; проміжний full run перервано, не зараховано як pass.
Поточний крок готовий до review, Phase3 REVIEW. Build/wheel не повторено за
погодженою UI-only policy. Final CI Linux/Windows — PR4 checks/final report.


## 12.11.2026 — остаточне прийняття Phase3 власником

**Phase3 — ACCEPTED власником 12.11.2026.** Явне рішення власника замінює
попередні REVIEW/pending записи цієї фази; хронологію перевірок збережено.
Погоджено документаційний commit/push у поточну Phase3 branch та звичайний
merge commit PR4 після success Linux/Windows CI фінального PR HEAD.

Прийнятий обсяг: create/validation/edit/persistence/versioning, service RBAC/
ownership, archive/restore/archive revision concurrency, NIST TN2276 desired
cue selector/legacy compatibility, neutral Constructor empty state. Власник
підтвердив закриття F01–F03 та незалежне review. Owner evidence — часткові
manual WSLg перевірки й схвалення результатів, не виконання всього checklist.
Automated implementation HEAD3b31210: local214passed, relevant WSLg9passed;
CI43296448273 success: Linux214passed, Windows212passed/2POSIX skips, locked
sync/Ruff/import/Qt startup успішні. Новий documentation-only HEAD проходить
окремий обов’язковий CI перед merge; SHA/run/result — PR4 і фінальний звіт.

Routine physical native Windows11 verification Phases3–11 лишається відкладеним
до Phase12, як acknowledged risk. Windows CI не є physical Windows11 evidence;
повний DPI/input/permissions/security/packaging/E2E gate ще не виконано.
Старі manual checklist items не позначаються автоматично виконаними.
SRS/функціональність/owner data не змінюються; Phase2 native workspace збережено.
**Phase4 — NOT STARTED**, потрібен окремий дозвіл; acceptance/merge Phase3
не є дозволом початку LLM Integration.


## Phase 4 — LLM Integration (13.11.2026)

Власник явно дозволив фазу та окремо погодив архітектурне уточнення SRS §10.2.
Baseline main d0b407c, branch feat/phase-4-llm-integration. Історичні записи
NOT STARTED/pending у попередніх секціях описують стан до цього дозволу.

План і traceability:

| SRS | Реалізований increment / gate |
| --- | --- |
| §§10.1–10.4, §23 Phase4 | Єдиний LLMGateway; Gemini Interactions v1; Groq SDK; functional LangChain Core Runnable; без LangGraph agents |
| §§10.4,10.7 | Typed text/structured generation, explicit selection, deterministic mock, bounded retries/quota/fallback та normalized metadata |
| §§10.8,11.1 | Safe explicit dotenv, synthetic-only caller contract, versioned Pydantic content slots, local validation, privacy-safe logging/telemetry |
| §21 / AGENTS verification | Focused fake-transport tests, complete pytest/Ruff, sdist/wheel/isolated install, startup/WSLg, final Linux/Windows CI |

Документи: [ADR-0004](adr/0004-llm-provider-boundary.md),
[Phase4 acceptance](PHASE_4_ACCEPTANCE.md), README та DEVELOPMENT_LOG.
SRS змінено тільки в §10.2 точним текстом власника; решта bytes/CRLF збережені.
Наявні сценарії/версії, RBAC, scoring, migrations і user data не змінювалися.

Доступні Gemini3.8Flash/Gemini3.5FlashLite/Groq GPT-OSS120B; activation лише
через explicit config/request. Mock — offline default. AUTO не потрібен цій фазі.
Fallback default-off, лише Gemini→Groq після timeout/selected transient5xx;
429/quota/access/safety/config/schema/data failures його не дозволяють.
Локальні provider+model rolling budgets враховують input/schema/output reservation;
Retry-After cooldown діє також між requests/models. Counters лише in-memory.

Live diagnostics реалізовано, але НЕ виконано: остання інструкція власника
вимагає окремого дозволу на API usage. Model access/account quotas unknown;
це явний remaining risk і не fabricated success. Durable telemetry/quota,
comparative experiments, specialized agents, UI generation, Email/Web rendering
та publication/approval workflows відкладено. Phase5 не розпочато.

Після локальних gates — commit/push/PR до main та перевірка Linux/Windows CI
фінального HEAD. Phase4 передається тільки на REVIEW, не ACCEPTED, без merge.
Owner manual acceptance ще не виконане. Physical native Windows11 gate лишається
Phase12; WSLg і Windows CI не замінюють фізичної acceptance матриці.

Локальний final gate: **314passed/341.67s**, focused LLM100passed/5.30s,
Ruff lint/format72files success, sdist/wheel та isolated installed wheel
mock/async/guard/startup success. Реальний WSLg startup/close success;
це не owner visual/functional acceptance. Phase4 **REVIEW**. Final PR HEAD
і Linux/Windows CI results фіксуються в PR та фінальному звіті після push.


## Phase 4 — independent review remediation F-01/F-02 (13.11.2026)

Phase4 **REVIEW**. Reviewed baseline5913183, та сама feature branch/PR5.
План перед кодом: §§10.4–10.8 — deterministic minimal→low fallback,
immutable original request та requested/effective parameter telemetry;
§11.1 — bounded Groq projection лише V1 artifact resource-ID pattern,
незмінена canonical validation; §21 — focused then one stable full Ruff/pytest,
Linux/Windows CI exact final HEAD. Packaging/startup/dependencies/UI не
зачеплено, тому повтор wheel/WSLg checks не потрібний за AGENTS workflow.

Початкові3 regression cases відтворили обидва findings. Виправлення не знімає
local security rule і не змінює SRS/архітектуру: provider checks structure;
canonical Pydantic завжди додатково перевіряє original regex. Telemetry позначає
schema projection та параметри. Generic unsupported schemas і fallback denylist
залишаються чинними. Details/alternatives — ADR0004, acceptance — PHASE4 record.
Live API не виконувати; owner acceptance/merge/Phase5 не дозволені цим кроком.
Final counts/CI будуть у журналі та описі PR5 після завершення перевірок.

Remediation final local gate: Ruff73files success, focused192passed/3.74s
(100prior +92new), one full pytest406passed/203.92s. Final SHA та Linux/Windows
CI results оновлюються в PR5/final report після push. Phase4 лишається REVIEW.


## Phase4 — Groq primary та Hydrogen backup candidate (13.11.2026)

Нова owner-approved policy supersedes Gemini3.8 primary: Groq GPT-OSS120B
primary cloud, Hydrogen preferred backup candidate після owner access verification,
Lite optional, Flash3.8 unresolved; Mock offline default. Phase4 **REVIEW**.
Baseline32e6de1, existing branch/PR5. Owner повідомив local Hydrogen allowlist
rejection, не Google failure, і два unavailable дляFlash3.8. Попередній bounded
live run підтвердив Groq/Lite; у цьому завданні live API заборонені.

План перед реалізацією: SRS §§10.2–10.8/11.1 — model catalog/capabilities,
Hydrogen sampling omission у existing Interactions adapter, explicit primary/
verified backup config, один shared fallback loop/telemetry/local validation;
§21 — focused first, one stable full Ruff/pytest, Linux/Windows CI final HEAD;
нормативні narrow policy references і owner acceptance command. LangGraph,
AUTO engine, new GUI selector/agents/constructors — поза scope.

Виконано: Hydrogen low/medium/high/xhigh, no minimal; xhigh відхиляється для
інших моделей. Температура дляHydrogen omitted/effective=None, requested
збережена. Single-hop backup enabled/access_verified за замовчуванням false;
маршрут лише для configured cloud primary, ніколи mock→cloud. Legacy
CYBERFORGE_LLM_FALLBACK Gemini→Groq збережено deprecated через той самий loop;
конфлікт із новим BACKUP fail-closed. Denylist/cooldowns/budgets/F-01/F-02
збережено; full original schema повертається після Groq→Hydrogen.

Нормативний SRS scope: header primary/model, §10.5 policy, gateway MVP
criterion23 і conclusion primary sentence; інші sections/CRLF збережено.
AGENTS, README, safe .env.example та ADR0004 синхронізовані. Actual owner .env
не змінюється: рекомендовані primary provider/model задаються явно користувачем.

Dependencies/lock, installation metadata/entrypoints, main startup та UI не
змінені. Installed pinned google-genai2.34.0 сумісний із bounded Hydrogen
Interactions у fake HTTP tests; retry safeguard збережено. Packaging/wheel та
unrelated WSLg не повторюються за AGENTS gates. CI включає locked install,
package import і Qt startup на обох OS. Physical native Windows11 — Phase12.

Focused gate:253passed/4.49s (усі prior192 +61new). Full gate/CI results
додаються після завершення. Hydrogen live command лише підготовлена й
mock-tested; owner запускає перший реальний тест після review. Жодної
автоматичної активації backup до success/confirmation і explicit enable.

Фінальний local gate: **467passed/232.84s**, focused253passed/4.49s,
Ruff74files success. Усі prior406 regressions збережено. Final HEAD та обидва
Linux/Windows CI jobs будуть підтверджені після push у PR5/final report.
Hydrogen live — owner acceptance step після review, не виконаний агентом.


## 13.11.2026 — Phase4 ACCEPTED власником; merge PR5 дозволено

Власник явно прийняв Phase4 LLM Integration: **REVIEW → ACCEPTED**,2026-11-13.
Це рішення замінює попередні REVIEW/pending записи поточного milestone;
історію реалізації та її перевірок збережено. Дозволено лише documentation-only
acceptance commit/push і ordinary merge commit PR5 після обох successful CI
jobs exact FINAL PR HEAD. Baseline98a019ce99df992c7ad54bc4f4a49ca02f6516b2.

Прийнято provider-independent gateway, Gemini Interactions/Groq/Mock adapters,
LangChain Runnable, structured/Pydantic validation, per-model thinking/config,
bounded retries/timeouts/limits/fallback, privacy-safe telemetry/secret handling,
Groq→Hydrogen backup configuration та F-01/F-02. Незалежні architecture/code
reviews і попередній CI підтверджені; поточний owner approval є acceptance.

Докази розділено:
- Automated reviewed HEAD: Linux467passed, Windows465passed/2skipped, Ruff,
  locked install, package import/Qt startup success (run43391679188).
- Hydrogen focused offline acceptance:61passed, повідомлено власником;
  попередній stable combined gate253passed і full local467passed збережено.
- Live connectivity: Groq GPT-OSS120B SUCCESS, Gemini3.5Lite SUCCESS;
  Hydrogen SUCCESS **owner-run/owner-reported**,5.148s,39input/5output/25reasoning.
- Manual GUI: повний checklist власником не виконувався; непідтверджені пункти
  не позначаються виконаними. WSLg/CI не є physical native Windows11 acceptance.

Approved policy: Groq/openai/gpt-oss-120b primary cloud; Gemini/gemini-4-hydrogen
preferred verified backup. Existing controlled backup дозволено enabled лише
через explicit local configuration; runtime defaults/flags і actual .env цим
acceptance step не змінюються. Mock — safe offline default.

Accepted residual risks: Flash3.8 availability unresolved; live complex
Email/Web Structured Outputs не перевірено; account-wide quotas не встановлено;
rate counters process-local; production generation workflows наступних фаз;
manual GUI checklist incomplete; physical native Windows11 gate Phase12.
Ці обмеження acknowledged owner acceptance і не блокують Phase4.

Фінальна docs-only branch обов'язково проходить Linux/Windows CI перед merge;
failed/pending checks, conflicts або unexpected HEAD зупиняють merge без bypass.
Після merge — clean checkout main + fetch/ff-only sync, перевірка merge SHA та
clean tree; owner data/native workspace збережено. Actual final SHA/CI/merge
result — PR5 і фінальний звіт, без circular documentation commit.
**Phase5 — NOT STARTED**, потрібен окремий дозвіл; Phase4 acceptance/merge
не є дозволом Specialized Agents.


## Phase 5 — Specialized Agents (13.11.2026)

Власник явно дозволив Phase 5 після ACCEPTED Phase 4 / merge PR #5
`6683f6e2569de05c57995eb5f7b1b3f6f603cce7`. GitHub MCP підтвердив main;
clean tree, fetch/ff-only check і feature branch `feat/phase-5-specialized-agents`.

План: SRS §§5–6/9/11/26.1 — four typed specialists і draft contracts;
§§10.1–10.4 — bounded LangGraph через existing GatewayRunnable;
§§11–13 — structural linkage, NIST claim separation та grounded explanations;
§21 — offline focused/full tests, package gate після new dependency, Linux/Windows
CI final HEAD, owner REVIEW. Phase 6–12 implementation не дозволено.

Реалізовано input validation, closed slots, versioned prompts, mandatory local
validation, pending_review, до одного explicit content correction; ніяких
persistent graph state, UI/DB mutations, publication чи live API calls.
Деталі, обмеження й наступні integration points — ADR-0005.
Stable local gate: Ruff lint/format success (81 files); agents104passed/1.24s;
combined agents+Phase4 LLM355passed/5.37s перед2додатковими command-refusal cases;
full **571passed/205.14s** після остаточних code changes. Build/sdist/wheel,
exact hashed58runtime dependencies install у /tmp, isolated wheel demo чотирьох
agents, package privacy/source match і Qt startup smoke — success.

Перед публікацією — final diff/staged secret scan. PR→main без merge;
цей milestone подано на REVIEW, readiness gate завершується лише successful
Linux/Windows CI на exact final PR HEAD. Actual SHA, CI run/jobs і результати
фіксуються в PR та фінальному звіті після push без circular doc commits.
ACCEPTED — тільки окреме рішення власника; Phase6 NOT STARTED.

### Phase 5 F-01 — independent review remediation

Phase5 лишається **REVIEW**, owner acceptance не надано. Scope: SRS §§5.6–5.7,
11.4–11.7 — previous draft provenance, identity/version/context і stale inputs.
Resource ID не є scenario identity. Додано additive local DraftProvenanceV1 та
повні previous envelopes; refinement відокремлено від stable source digest.
Web також прив'язаний до associated Email content/metadata без request token. Legacy envelopes readable,
але reuse без provenance/відомої identity відхиляється до LLM. RBAC unchanged.

На reviewed HEAD8 deterministic cases відтворили помилку. Focused final:
`pytest tests/test_agent_provenance.py tests/test_agents.py -q --tb=short` —
154passed/2.45s (104existing +50new). Original provider schemas і Groq strict
conversion порівняно з reviewed commit: identical. Offline demo success.
Stable full gate: Ruff lint/format success,82files; **621passed/210.74s**,
усі571prior tests збережено. Exact-final-head Linux/Windows CI evidence та HEAD
фіксуються після push в PR6/final report; merge/ACCEPTED/Phase6 заборонені.


F-01 final audit: вкладений Email request token також виключено зі stable Web
digest. Додано positive regression для Email refinement без зміни content з
подальшим Web refinement; content/identity/context changes усе ще stale.
Final focused155passed/5.07s (104prior+51new); остаточний full
**622passed/447.22s**, Ruff lint/format success,82files. Попередній full621pass
був до цієї поправки. Final-head Linux/Windows CI evidence — PR6/final report.


## Phase 5 — ACCEPTED власником 13.11.2026

Власник явно прийняв Phase5 після independent review/F-01 remediation та
успішного **owner-run/owner-reported offline agent demo**. Це рішення замінює
попередні REVIEW/pending записи Phase5; історичні докази збережено.
Reviewed HEAD `37a0f5e290a9068c8b24255acf276b826022c231`, PR6.
Прийнятий scope/обмеження — [PHASE_5_ACCEPTANCE.md](PHASE_5_ACCEPTANCE.md).
Дозволено documentation-only acceptance commit/push, звичайний merge commit
PR6 лише після successful Linux/Windows CI exact final HEAD, потім local main
fetch/ff-only sync. Final SHA/CI/merge evidence — PR6 і фінальний звіт.
Phase6 **NOT STARTED**: потрібен окремий дозвіл. SRS/runtime/.env/DB не змінено.

## Phase 6 — Email Constructor (13.11.2026)

**Статус: REVIEW.** Власник окремо дозволив повну Phase 6, включно з
feature branch/commit/push/PR та offline verification. Phase 7 не дозволено.
Попередній NOT STARTED запис вище — історичний стан до цього дозволу.

План перед coding: §§4.5–4.9/11/14 — artifact migration, trusted service,
stable synthetic context і optimistic concurrency; §§5.1–5.8/9.2/10 — accepted
agent/gateway, Qt worker, native mail preview/JSON/refinement/Save; §§21/23/24 —
focused/full regressions, migration/package/WSLg, exact-final-head Linux/Windows CI.

Перші інкременти: additive 0004_email_materials та EmailMaterialService;
ScenarioPage інтегровано з EmailPage без нового scenario catalog; QRunnable/
QThreadPool queued delivery та request/session/scenario identity; explicit
--email-demo, default unconfigured Mock чесно unavailable. ADR-0006,
PHASE_6_ACCEPTANCE містять архітектуру, статуси та ізольовані owner demo commands.
Остаточний local gate: Ruff lint/format success (90files), full pytest
**690passed/305.56s**, усі622accepted regressions +68new cases. Real WSLg:
**27passed/66.89s**, включно з fixed1100×720 footer. Wheel/sdist і isolated
installed-wheel migration/agent/Save/reopen/startup — success. Наявні DB/keys/
native environment збережено, SRS/dependencies/lockfile не змінено.
Архітектура — ADR-0006, safe offline demo/checklist — PHASE_6_ACCEPTANCE.md.
Exact-final-head Linux/Windows CI evidence та PR/SHA — у PR і фінальному звіті
після push. Owner acceptance очікується; native Windows11 лишається Phase12 risk.
REVIEW не означає ACCEPTED або дозвіл на merge/Phase7.

14.11.2026 visual refinement in PR7: the owner reviewed0e34dd8 in WSLg and found
the layout acceptable, requesting closer Gmail typography/icons/reading content.
SRS §§5.2–5.5: refine native presentation using existing structured fields,
without changing contracts/persistence/workers or the scenario catalog. Keep
explicit Save and security regressions, minimum-size/font-metric checks, updated
WSLg screenshots and exact-final-head Linux/Windows CI. Evidence and limitations
are recorded in DEVELOPMENT_LOG/PHASE_6_ACCEPTANCE and PR7. Phase6 stays REVIEW;
only the owner can grant final visual acceptance. Phase7 remains NOT STARTED.


## Phase 6 mandatory editing completion — 14.11.2026 (REVIEW)

Owner approved the Gmail-inspired visuals at cec7d34 and authorized manual
editing, protected AI refinement, JSON-only inspection and an owner-run live
Groq acceptance procedure. No merge/Phase7/automatic live calls are authorized.
SRS §§4.7,5.1–5.8,9.2,10,11,16,21 remain authoritative and unchanged.
Earlier HTML-projection descriptions are historical and superseded: the unused
projection/highlighter/tab are removed; native QTextEdit formatting remains.

Manual edits pass through EmailMaterialService with current ownership, role,
archive/version/revision and material-revision checks. A complete JSON roundtrip
validates every candidate; main subject/body mirror the artifact. Main sender
updates controlled context plus optional instructor_sender_name payload metadata
and recomputes stable provenance. Authoritative scenario identity/parameters,
organization/premise and internal resource remain fixed. Missing override in
legacy payloads means original stable context. No migration or alternate store.
Provenance remains consistency evidence, not authorization or a PII detector.

Apply is local; Cancel discards dialog fields; Save is transactional persistence.
AI receives the current working draft. Explicit main-body scope merges only the
validated new body into previous slots; all other fields stay deterministic.
Wider scope is explicit. Scope wins over conflicting natural-language requests.
Regeneration after manual edits asks confirmation; failures preserve working and
saved data. JSON inspection reflects the whole current draft and stays read-only.

Email-only prompt v2 improves educational coherence and provider-neutral policy.
Email max output4096, bounded512–8192; general request default512 unchanged.
Provider/model quota accounting, retries and strict schema/local validation are
unchanged. Scripted fixtures reserve both model/provider budgets for the larger
prompt/output; no production quota checks are bypassed. Untyped generation
parameters remain intentionally unsupported. No new dependencies.

Owner-run live procedure: see PHASE_6_ACCEPTANCE.md. Module CLI requires --live,
uses only the existing Groq key, stops on initial failure, allows at most2requests,
zero retries/corrections/fallback, logs metadata only. Live acceptance is PENDING;
Codex has not run it. Physical native Windows11 remains Phase12 risk.
Focused/full/persistence/package/WSLg and final-head CI evidence follows in the
log and PR7. The current task remains REVIEW until owner GUI/live acceptance.


### Phase 6 ordinary email domains — 14.11.2026 (REVIEW)

Owner authorized removal of the mandatory .invalid email-domain restriction.
SRS §§5.4–5.8: shared text validation no longer infers synthetic identity from
an email domain. MessageV1 enforces bounded ASCII mailbox syntax; ordinary
domains and existing .invalid addresses remain unchanged through Apply/Save/
reopen/refinement. Editor labels/errors and email-prompt-v3 reflect the rule;
shared policy v2 retains fictional identities and forbids real personal data.
Provider schema structure, persistence, provenance, RBAC and external URL
restrictions are unchanged. No DNS/MX checks, SMTP, navigation or live API calls.
Focused offline tests and Ruff locally; final Linux/Windows CI runs the full
suite. Phase 6 stays REVIEW; no merge or Phase 7.


### Optional provider token limits and refinement diagnosis — 15.11.2026

Phase6 stays REVIEW in PR7. SRS §§5.6–5.8,10–11,16: owner explicitly removes
implicit output and local token ceilings. Shared/Email output limits default to
None, accept any explicit positive integer and have no application maximum.
Email inherits shared settings unless explicitly overridden. Groq/Gemini omit
unset output fields. Local quotas/dimensions are opt-in; explicit provider/model
levels still apply together, while Retry-After, timeouts and bounded retries
remain. Unknown provider-default output cannot be reserved; configured token
budgets estimate prompt/schema bytes plus an explicit output allowance. They
are not billing guarantees. Content length/artifact-size limits remain intact.

Owner live evidence: initial Groq/gpt-oss-120b success,1452input/742output tokens,
local validation passed; refinement invalid_request without usage/artifact.
Root cause remains UNKNOWN from that category alone. No causal token claim.
Offline real-SDK/in-memory HTTP tests exercise previous draft, prompt-v3,
identical strict schema, low reasoning, initial+refinement success, protected
main-body merge and injected400 failures. No request-construction defect is
reproduced. New diagnostics retain only HTTP status, exact allowlisted error
code/type and context/output/structured-output/invalid-request classification.
Unknown strings, error messages, failed_generation and raw bodies are discarded.
A fresh owner-only live run is required to identify the actual provider failure;
no live call was made by Codex. Existing opt-in command remains unchanged,
with optional --max-output-tokens N, no local token quotas, at most2requests,
zero retries/corrections/fallback. No .env or owner demo data changes.


### Groq Email compatibility default — 15.11.2026

Owner approved targeted SRS §§5.4,5.6–5.7,10.4 configuration correction: after
owner live HTTP400 with omitted output limit, explicit4096 passed initial/
refinement (889/780output tokens), validation and protected-field checks.
EmailScenarioAgent uses4096 only for Groq/openai/gpt-oss-120b when neither Email
nor shared limit is explicit. CLI uses the same path, with flag > Email env >
default. Explicit8192+ remains valid; no hard application maximum or default
local quotas. Gemini, unrelated operations, validation and refinement protections
remain intact. No live API calls by Codex. Focused tests/Ruff locally and final
Linux/Windows CI; Phase6 stays REVIEW, no merge/acceptance/Phase7.


## Phase 6 — ACCEPTED власником 2026-11-15

Явне рішення власника замінює попередні REVIEW/pending записи без видалення
історії. Прийнято Gmail-inspired Email Constructor, manual main/background
editing, Apply/Cancel/explicit Save, canonical JSON/persistence/reopen,
AI refinement/regeneration та чинні security/RBAC/provenance/versioning/threading
межі. Повний scope і accepted limitations:
[PHASE_6_ACCEPTANCE.md](PHASE_6_ACCEPTANCE.md).

Owner GUI: generation зі змістовними параметрами та regeneration — success.
Owner live Groq4096: initial889/refinement780output tokens, validation PASSED,
protected fields preserved. Reviewed HEAD9653b72ddd65be590a60a21aeb2bb59ad3d4f2aa;
[PR7](https://github.com/the1llus1on/cyberforge/pull/7), CI43679237327:
Linux783passed, Windows781passed/2POSIX skips, Ruff/import/Qt smoke success.
Документаційний acceptance HEAD повторно перевіряється CI; власник дозволив
звичайний merge commit, потім fetch/ff-only local main synchronization.
Final HEAD/CI/merge SHA — у PR7 та фінальному звіті, без циклічних doc commits.

Phase12: UX polishing, ширша якість сценаріїв, final optimization і physical
Windows11 acceptance matrix залишаються відкладеними ризиками, не виконаними
перевірками. Occasional generation failure за underspecified input —
неблокувальна robustness/diagnostic opportunity.

**Phase7 — NOT STARTED / PLANNING.** Наступний запланований етап — Web
Constructor (SRS §23); architecture/UI/templates/editing/acceptance criteria
потребують окремого погодження власника. Реалізацію, branch або PR Phase7
не розпочато цим рішенням. Phases8–12 без змін: NOT STARTED.


## Phase 7 — Hybrid Component-Based Web Constructor (15.11.2026)

**REVIEW**; реалізацію та локальні gates завершено. Власник дозволив branch/commit/push/PR; merge й ACCEPTED заборонено.
База: main 0fc97861e8e9c84393253e79c142c7c54adcb8b3, clean tree, fetch/ff-only.
План та gates:

1. §§6.4–6.10,9.3,11.3,26.3/26.5: scoped approved SRS amendment та ADR-0007.
2. §§6,10–11,16: closed wire V2 → canonical component contracts, registry, provenance;
   focused positive/negative/Groq strict tests, без зміни legacy contracts.
3. §§6.2–6.7,15.3,16.3–16.5: deterministic renderer, isolated WebEngine/browser shell;
   real browser network-isolation gate до подальшої інтеграції.
4. §§4.9,6.9–6.10,11,14: additive migration, authorized WebMaterialService,
   exact saved Email binding, explicit Save/concurrency/stale handling та workspace UI.
5. §§6.8,21: validated modal component editor, apply/cancel/current candidate.
6. §§9.3,10,16: web-prompt-v2, existing graph/gateway, protected scopes, current draft,
   workers/guards та explicit offline demo; live requests лише власником.
7. §§21,23–24: focused/full Ruff/pytest, actual WebEngine/WSLg, migration/package,
   scoped diff/secret review, push/PR та exact-head Linux/Windows CI.

Acceptance evidence: PHASE_7_ACCEPTANCE.md. Full publication/readiness — Phase 8,
learner flow — Phase 9; physical Windows 11/DPI/installer — Phase 12 risk.


Phase7 final local gate: Ruff lint/format117files PASS; full offline pytest
882passed/504.65s. Два додаткові test-only session/close cases2passed/6.27s;
application code після full-suite start не змінено. Real WSLg35passed/30.20s,
actual Chromium isolation/clicks, migration/RBAC/concurrency та built/isolated-wheel
checks passed. docs/screenshots/phase-7-web-*.png оглянуто. Final PR HEAD і exact
Linux/Windows CI status — у PR/final report після push. Owner manual/live acceptance
pending, native physical Windows11 лишається Phase12 risk. Phase7 REVIEW, не ACCEPTED;
Phase8 NOT STARTED. Повний checklist — PHASE_7_ACCEPTANCE.md.


Phase7 Windows remediation final local gate: native combo sizing та elided browser
metadata preserve1100×720; original width assertions retained,2new regressions.
Ruff117files PASS; full **886passed/506.40s**, all783prior+103Phase7 cases.
Focused Web UI/security15passed/34.17s; post-fix real WSLg compact3passed/9.36s.
Initial CI43749813530: Linux884passed, Windows881passed/2skips/1compact failure;
history retained. Final exact-head CI evidence belongs to PR8/delivery report.
Phase7 REVIEW, owner acceptance pending; no merge/Phase8.


Measured native action-row correction: Edit moved to top row (Email design),
three actions below preview; Windows numeric row minimum828 identified directly.
Final local gate **886passed/518.91s**, Ruff117files PASS; focused Web UI/security
15passed/35.12s, real WSLg compact3passed/11.22s plus measured-width1passed/4.33s.
Failure-only diagnostics retained; CI runs compact gate before full suite.
Final PR8 HEAD and Linux/Windows evidence remain in PR/delivery report; Phase7 REVIEW.


## Phase 7 — ACCEPTED власником 2026-11-15

Власник явно прийняв Phase 7 — Hybrid Component-Based Web Constructor та дозволив
звичайний merge commit PR #8 після successful CI на точному final HEAD.
Reviewed implementation HEAD: `43462c5b963030db060ca0e515b09f6120017414`.
Це рішення замінює попередні REVIEW/pending записи; історію перевірок збережено.

**Owner-tested / owner-reported:** реальний GUI, live Groq GPT-OSS120B Web generation,
AI regeneration, ручне редагування шапки сайту, light/dark switching, коректні
browser preview та component rendering. Independent review critical implementation
paths/security tests не виявив підтвердженого блокувального дефекту.
Ручні Save/reopen, всі presets та physical Windows11 окремо НЕ підтверджені власником.

**Automated evidence:** reviewed HEAD CI
[43754808309](https://github.com/the1llus1on/cyberforge/actions/runs/43754808309):
Linux886passed, Windows884passed/2POSIX-only skips; Ruff, compact native gate,
Qt startup smoke та actual WebEngine security tests PASS. Persistence, Save/reopen,
presets, RBAC, concurrency/migration та isolation мають окремі automated докази
вище/у DEVELOPMENT_LOG, не приписуються власнику. Codex live API не виконував.

**Accepted limitations:** одна сторінка, fixed synthetic form values, structured
provenance не доводить повну семантичну/навчальну якість. Physical Windows11,
DPI, keyboard, executable/installer, broader performance та final presentation
polish залишаються Phase12 ризиками; Windows CI їх не замінює. Неперевірені
вимоги не позначено перевіреними. .env/keys/SQLite/user data/environments збережено.

Документаційний acceptance HEAD повторно проходить Linux/Windows CI перед merge;
точні SHA/CI/merge evidence фіксуються в PR8 та фінальному звіті без циклічних
документаційних commits. Phase8 — **NOT STARTED / PLANNING**: architecture та
implementation requirements потребують окремого review/дозволу. Phases9–12 без змін.

## Phase 8 — Scenario Integration (15.11.2026)

**REVIEW**, реалізацію та local gates завершено; feature PR дозволено, без merge/ACCEPTED/Phase9.
База main b84e2fbdfcf1d84f86a6d8c30a9b0b868e678212, clean tree, GitHub MCP,
fetch/ff-only; feat/phase-8-scenario-integration.

| Інкремент | SRS | Gate / evidence |
| --- | --- | --- |
| Поправка/ADR/contracts | §§4,6.10,11–12,14,23–24 | Closed schemas, registry positive/negative serialization |
| Integration/link | §§6.10,11.4–11.6,16 | exact persisted Email/Web/provenance/target, stale and forged rejection, inert visible CTA |
| Rubric | §§12.2–12.6 | bounded criteria/actions/applicability, weights/editor, safe decline |
| Readiness/review | §§4.8,11.6 | deterministic reason codes, exact receipts, warning ack, nonoverrideable blockers |
| Persistence/publication | §§4.9,14 | additive0006, rollback/races/direct-write protection, explicit new version |
| Grants/access | §§2.3–2.5,14,16 | RBAC, audit regrant, current membership, dedup/latest, archive/restore |
| GUI/delivery | §§3–4,21,24 | guards/modals/compact WSLg, full Ruff/pytest/package, final-head Linux/Windows CI |

Деталі — ADR-0008 та PHASE_8_ACCEPTANCE. No AI calls/learner attempts/scoring.


Phase8 final local gate: full offline pytest **977passed/673.63s**, Ruff lint/format
126Python files PASS. Focused persistence172passed +8additional, migration rollback
5passed, GUI45passed; real WSLg11passed plus final compact screenshot1passed.
Built/installed wheel,0005→0006 preservation, full publication/grants/access,
Qt startup and85file source parity PASS. First full976passed/686.21s preceded
DDL hardening; final977run includes the rollback regression. CI includes early
native compact check, final-head Linux/Windows evidence follows in PR/final report.
Owner manual acceptance pending; physical Windows11/DPI/installer Phase12 risk.
Phase8 REVIEW, no merge/ACCEPTED/Phase9. ADR0008 and PHASE_8_ACCEPTANCE contain details.

## Phase8 — independent review F8-01/F8-02 (16.11.2026)

**REVIEW**, продовження PR9 від reviewed c8f95eb; без merge/ACCEPTED/Phase9.
План точкової remediation:

1. SRS §§4.8,11.6,16.6: reproduce no/unauthorized/stale groups через actual Qt
   click та direct service. Зберегти technical readiness окремо; explicit group
   validation перед strict receipt, GUI preflight до confirmation, write revalidation.
2. §§2.5,4.9,14: two published versions/separate grants; selection/reload/reopen
   має зберігати exact publication, preview та audit target. Grant/revoke dialog
   вказує scenario/version/publication/group; recheck target після modal.
3. Focused failure evidence → targeted fixes → integration/persistence/UI regressions,
   relevant real WSLg, Ruff/full pytest та final-head Linux/Windows CI; push у PR9.

Нових contracts/dependencies/migrations немає; accepted content immutability та
SRS scope не змінюються. Actual evidence — DEVELOPMENT_LOG/PHASE_8_ACCEPTANCE.

F8 remediation final local gate:988passed/857.37s, Ruff126files PASS;
focused11passed, relevant regressions131passed, actual WSLg7passed. F8-01 confirmed
GUI preflight defect fixed; claimed uncaught ValidationError not reproduced because
existing server BLOCKED gate already denied invalid groups. F8-02 exact historical
target/reset reproduced and fixed with synchronized selection and explicit grant
confirmation. Final-head CI evidence in PR9/delivery report; Phase8 remains REVIEW.

## Phase8 — WSLg Web preview lifecycle correction (16.11.2026)

**REVIEW**, existing PR9, baseline988bc421. Owner authorized investigation/fix/push,
not merge/ACCEPTED/Phase9. Targeted plan, mapped to SRS:

1. §§3.13,6.2–6.6,21: reproduce through real sign-in, saved scenario and ScenarioPage
   button/QDialog lifecycle; distinguish native process exit, renderer exit, GUI
   heartbeat, page load and native-window hide. Use one isolated published fixture.
2. §§6.6,16.3–16.5: compare default and documented graphics overrides individually;
   preserve sandbox/network isolation and existing runtime configuration.
3. §§3.13,4.8,21: replace verified nested-modal lifetime defect with Qt open/finished,
   explicit ownership/cleanup and retained guards; safe renderer/load diagnostics.
4. §§14,16,21: repeated default/software WSLg rendering/close/reopen, actual renderer
   termination/reload, source immutability, security/compact regressions, Ruff/full
   offline suite and exact-head Linux/Windows CI in PR9. No startup/schema changes.

Preview correction final local gate:992passed/828.97s, Ruff126files PASS;
default WSLg30passed, single --disable-gpu11passed, five separate backend variants
with3cycles each PASS. Actual native-window recreation verified; open/finished fixes
premature exec return/deletion, renderer-only failure/reload covered independently.
No startup/default graphics/security/schema changes. Owner hardware recheck pending;
exact-head CI evidence follows in PR9. Phase8 REVIEW; no merge/ACCEPTED/Phase9.


## Phase8 — UX redesign: підготовка й публікація (16.11.2026)

**REVIEW**, owner acceptance pending. Власник дозволив реалізацію, commit/push та
оновлення PR9; без merge/ACCEPTED/Phase9. База redesign — `34e3198`.

| Інкремент | SRS | Поведінка / gate |
| --- | --- | --- |
| Структура | §§3.13,4,21 | Три вільно доступні кроки; stable modal open/finished; один central stack |
| Матеріали | §§6.10,11.4–11.6 | Responsive картки, exact persisted previews, read-only technical target, explicit link Save, URL warning |
| Оцінювання | §§12.2–12.6 | Registry8 у3групах, expandable rows, lossless numeric text, unsaved editable preset, explicit Save |
| Публікація | §§4.8–4.9,14 | Service-derived checklist, correction navigation, groups, exact-source attestation, final confirmation/result |
| Історія | §§4.9,14,16 | Окремий ScenarioPage action навіть із newer draft; exact version, grants та collapsible audit |
| Перевірки | §§16,21,24 | Existing regressions retained; focused new UI, real WSLg lifecycle/security/compact, full suite/Ruff, final-head Linux/Windows CI |

Save/Discard/Remain охоплює кроки, previews, history, Close/X, constructor handoff,
workspace/account navigation. Session invalidation примусово очищує buffers.
Редагування й зміна груп скидають attestation; відкритий огляд періодично повторює
read-only service checks для external changes без втрати незбережених правок.
Accepted contracts/services/DB triggers/atomic publication не змінено. Нових
залежностей, migrations, startup flags або runtime security exceptions немає.
Деталі дизайну — dated addendum ADR0008; результати — log/PHASE_8_ACCEPTANCE.

UX stable local gate: **1011passed/1091.99s** (992prior+19new cases), Ruff127files
PASS; real default WSLg48PASS, extra production Close/WM-X3cycles PASS. Seven
synthetic screenshots inspected.15scoped files, owner AGENTS.md excluded. Source/
tests stable throughout full run; only evidence docs updated afterwards. Exact
final-head Linux/Windows CI follows in PR9/delivery. Phase8 REVIEW; owner acceptance
pending, no merge or Phase9.

### UX Windows CI correction (16.11.2026)

First-head Linux1011PASS; Windows1007PASS/3skip/1new narrow-resize failure. Native
card minima prevented self-width-driven stacking. Forced420px/card reproduces the
same failure locally; viewport-driven geometry fixes it, with assertions retained.
Resize test now covers normal+native-pressure cases; early CI includes both.
Focused2PASS and real WSLg5PASS, Ruff127files PASS. Final suite now1012cases
(992prior+20new;38Phase8 UI); engineering gate requires new full run and both
platforms on final HEAD. Phase8 REVIEW, no merge/ACCEPTED/Phase9.

Corrected final local gate: **1012passed/1403.08s**, Ruff127files PASS, native-width
focused2PASS, real WSLg5PASS. New stable run retains992prior+20new/38Phase8 UI.
Combined redesign16files; corrective increment8files; owner AGENTS.md excluded.
New final-head Linux/Windows CI follows in PR9/delivery. Phase8 stays REVIEW.

### UX acknowledgement native-width correction

Second Windows early gate confirms cards fixed, exposes step2 native multiline
QCheckBox minimum686>556. Native668px hint regression reproduces1FAIL/1PASS.
Wrapping buddy label plus native checkbox fixes2PASS; label click/focus/Space
assertions retained. Real WSLg compact/resize/lifecycle/full flow/final modal6PASS,
Ruff127files PASS. New stable full run required; final CI must pass both platforms.
Scope remains UI/tests/docs/CI, Phase8 REVIEW, no merge/Phase9.

Final wrapped-attestation/harness gate: **1012passed/1119.68s**, zero errors;
Ruff127files PASS, real WSLg6PASS plus isolated fixture3PASS. All992prior+20new/
38Phase8 UI retained. Final increment10files, combined16; owner AGENTS.md excluded.
Final-head Linux/Windows CI follows in PR9/delivery. Phase8 REVIEW; no merge/Phase9.

## 17.11.2026 — F8-UX-01/02 targeted visual correction

REVIEW. Native checkmark/text hidden by selected dark foreground on membership
row dark background; logical state intact. Two-line selected-row QSS correction,
rendered-pixel/state/keyboard regression, before/after captures. Full1014PASS,
Ruff127files PASS, WSLg5PASS + unsuppressed3cycle probe1PASS/exit0 reproduces
nonfatal Mesa/Zink/EGL warnings. Approved AGENTS.md committed separately. Final
exact-head CI follows in PR9; no merge/ACCEPTED/Phase9. Owner process exit unknown.

## Phase8 — остаточне прийняття та release gate (17.11.2026)

**Phase 8 — ACCEPTED on 2026-11-17.** Owner manual WSLg acceptance та рішення
власника записано в PHASE_8_ACCEPTANCE.md; попередню review/test history збережено.
План release: docs-only commit у чинній branch → push PR9 → exact-final-head
Linux+Windows CI → recheck scope/base/conflicts → standard merge commit з expected
head SHA → fetch/local main fast-forward-only → verify remote/local merge SHA та
clean tree. За unexpected CI failure/conflict/integrity issue зупинитися.
Без runtime/test/dependency changes або live AI. Physical Windows11/DPI/GPU/
installer залишаються Phase12 risks. Phase9 NOT STARTED / PLANNING; не починати.

## Phase 9 — Learner Simulation (17.11.2026)

**REVIEW**, implementation/local engineering gates complete; commit/push/PR owner-approved.
Phase 0–8 ACCEPTED; Phase 8 merged PR9 at dfba3fbaa1b2b8b94d279d3cef3f132c03cc9391.
This supersedes earlier Phase 9 NOT STARTED entries; prior history is retained.

| Increment | SRS | Gate |
| --- | --- | --- |
| Contracts / ADR0009 / amendment | §§3.9,8,11.4,12.8,14,16,23–24 | closed state/event vocabulary |
| Persistence / services | §§8,14,16 | migration, exact binding, races, RBAC, immutable events |
| Catalog / Email / Web | §§3.9,8,11.4,16 | existing renderers, no external navigation, actual actions |
| Completion / recovery / history | §§8.5–8.6,12.8,14 | decline, resume, revoke/restore, repeats, no scores |
| Demo / verification / PR | §§21,24 | offline, Qt/WSLg, full Ruff/pytest/package, final-head CI |

No merge/ACCEPTED/Phase10 authorization. Details: ADR0009/PHASE_9_ACCEPTANCE.

Phase9 final stable local gate: **1053PASS/670.67s**, including all1014accepted
regressions +39learner/demo/UI cases; Ruff136files PASS, actual default WSLg
learner/security8PASS/18.71s, native Chromium keyboard interaction PASS.
Offline sdist/wheel, packaged migration/publication/learner lifecycle and
installed-wheel Qt startup PASS with dependency-reuse limit documented.
Intermediate full1053PASS/655.75s and1053PASS/728.93s retained; final source/test
unchanged throughout670.67s run. Owner manual acceptance pending. Final-head
Linux/Windows CI will be recorded in PR/delivery without changing verified HEAD.
No merge/ACCEPTED/Phase10. PHASE_9_ACCEPTANCE contains exact manual steps.

### Phase9 first-head Linux CI correction

PR10 initial edcc7d3: Linux learner early gate4PASS/1FAIL exposed expected
delegated-navigation loadFinished(False) being treated as render failure.
Use exact owned-document loadingChanged URL/status; keep actual failed-resource
and renderer diagnostics. Offscreen focused10PASS/19.32s; real WSLg10PASS/23.95s.
No new dependencies/schema/authorization/scoring semantics. New stable full and
exact updated PR HEAD Linux/Windows CI required; Phase9 REVIEW unchanged.

### Corrected final local gate — current delivery evidence

After the CI-derived loading-signal correction, stable offline full suite
**1053PASS/595.76s**, exit0; all1014prior +39new cases retained. Command:
`QT_QPA_PLATFORM=offscreen UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest -q --tb=short`.
Source/tests frozen throughout. Previous670.67s/728.93s gates are superseded
for delivery by this595.76s result, with history retained.

Focused actual offscreen10PASS/19.32s and default WSLg10PASS/23.95s:
`QT_QPA_PLATFORM=wayland UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest tests/ui/test_learner_simulation.py tests/ui/test_web_security.py tests/ui/test_scenario_integration.py -k 'learner or actual_engine or real_engine or actual_constructor_button or renderer_diagnostics or production_dialog' -q --tb=short`.
The offscreen variant uses QT_QPA_PLATFORM=offscreen. Both assert actual native
Qt cancellation, continued interaction and actual owned-resource failure.
Ruff check/format136files PASS; CRLF-aware diff check PASS. Corrected offline
sdist/wheel rebuilt, reinstalled in isolated wheel environment (existing read-only
dependencies reused); actual installed-wheel WSLg startup/shutdown exits0.

Append-only corrective commit/push in PR10; new exact-head Linux+Windows CI
mandatory. Final SHA/CI evidence recorded in PR/delivery without another commit.
Phase9 REVIEW, owner acceptance pending; no merge/Phase10.

## Phase9 independent review remediation — 17.11.2026

REVIEW; F9-01/F9-02 confirmed at3c44281. Plan mapped to SRS §§8,11.4,14,16:
native application-owned Web actions independent of authored components; closed
service provenance; separate bound owned-display acknowledgement; regular-preset
regressions without all-action demo helper; existing security/migration/lifecycle
checks, full offline suite, real WSLg and exact-final-head Linux/Windows CI.
No Phase8 publication/rubric contract changes, scoring or later phases.
ADR0009 records event identity compatibility and realistic local trust limits.
Evidence follows; owner data/credentials/env untouched.

Remediation final local evidence: full offline **1056PASS/683.61s**, source/tests
frozen throughout. `QT_QPA_PLATFORM=offscreen UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest -q --tb=short` includes all prior regression/security/
migration/integrity tests. Focused learner backend/UI/security42PASS/54.10s
preceded the extra closed-control authorization regression (included in full).
Actual WSLg11PASS/31.05s:
`QT_QPA_PLATFORM=wayland UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest tests/ui/test_learner_simulation.py tests/ui/test_web_security.py tests/ui/test_scenario_integration.py -k 'learner or actual_engine or real_engine or actual_constructor_button or renderer_diagnostics or production_dialog' -q --tb=short`.
Ruff check . and format --check .136files PASS; CRLF-aware diff check PASS.
No dependencies/startup/schema changes; no repeated package gate necessary.
Final-head Linux/Windows CI recorded in PR10/delivery after push to preserve
verified HEAD. Phase9 REVIEW; independent owner acceptance still pending.
