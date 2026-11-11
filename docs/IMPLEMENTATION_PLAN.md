# CyberForge — Implementation Plan

**Normative source:** `TECHNICAL_SPECIFICATION.md` (SRS v3.0, 11.11.2026), especially §§0, 21–24, 26–27.
**State:** Phase 0 — ACCEPTED; Phase 1 — ACCEPTED власником 11.11.2026; Phase 2 — REVIEW.
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
| 2 | Users & Groups | REVIEW | Login, Argon2id, 3 roles, demo accounts/groups, permission enforcement; denied-access tests |
| 3 | Scenario Management | NOT STARTED | Create/edit scenarios with unique IDs, persistence, statuses, versioned drafts; SQLite integration tests |
| 4 | LLM Integration | NOT STARTED | LLMGateway, provider adapter, Gemini configuration, deterministic MockLLMProvider; schema and fallback tests |
| 5 | Specialized Agents | NOT STARTED | Typed I/O contracts for four specialized agents and bounded orchestration; mock agent tests |
| 6 | Email Constructor | NOT STARTED | Email shell, generation, preview, code view, regeneration, explicit save and validation; UI tests |
| 7 | Web Constructor | NOT STARTED | Web templates, isolated Qt WebEngine, generation, preview, code view, explicit save; security and UI tests |
| 8 | Scenario Integration | NOT STARTED | Shared Email→Web context, internal link validation, readiness gate, immutable publishing; integration tests |
| 9 | Learner Simulation | NOT STARTED | Email and Web exercises, controlled navigation, recorded attempts/events, safe completion without Web; end-to-end tests |
| 10 | Scoring & Mentor | NOT STARTED | Versioned deterministic rubrics, evaluation, result display, LLM explanations without score edits; reproducibility tests |
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

**Статус: REVIEW.** Технічний gate у WSL пройдено; ACCEPTED потребує рев’ю
власника. Phase 3–12 не розпочато.

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
