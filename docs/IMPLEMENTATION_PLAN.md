# CyberForge — Implementation Plan

**Normative source:** `TECHNICAL_SPECIFICATION.md` (SRS v3.0, 11.11.2026), especially §§0, 21–24, 26–27.
**State:** Phase 0 — ACCEPTED; Phase 1 — ACCEPTED власником 11.11.2026; Phase 2 — ACCEPTED власником 12.11.2026; Phase 3 — ACCEPTED власником 12.11.2026.
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
| 4 | LLM Integration | REVIEW | Gateway/Gemini Interactions/Groq/Mock/Runnable; 314 local tests; packaging/WSLg startup success; owner acceptance pending; ADR-0004 |
| 5 | Specialized Agents | NOT STARTED | Typed I/O contracts for four specialized agents and bounded orchestration; mock agent tests |
| 6 | Email Constructor | NOT STARTED | Email shell, generation, preview, code view, regeneration, explicit save and validation; UI tests |
| 7 | Web Constructor | NOT STARTED | Web templates, isolated Qt WebEngine, generation, preview, code view, explicit save; security and UI tests |
| 8 | Scenario Integration | NOT STARTED | Shared Email→Web context, internal link validation, readiness gate, immutable publishing; integration tests |
| 9 | Learner Simulation | NOT STARTED | Email/Web exercises, controlled navigation, persistent learner attempt history/events, safe completion without Web; end-to-end tests |
| 10 | Scoring & Mentor | NOT STARTED | Versioned deterministic rubrics, evaluation, learner result history/detail, LLM explanations without score edits; reproducibility tests |
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
