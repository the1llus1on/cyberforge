# CyberForge — журнал розробки

**Поточний стан (17.11.2026):** Phases0–9 — **ACCEPTED**;
Phase10 — **IN PROGRESS / WP1 ONLY**, Contract Freeze Gate PENDING OWNER ACCEPTANCE;
production scoring/persistence/migration authorization pending; Phases11–12 — NOT STARTED. Нижче збережено хронологію
попередніх REVIEW/PLANNING та acceptance evidence; актуальний запис — наприкінці журналу.

## 11.11.2026 — Phase 0: Project Foundation

### Обсяг і початкові умови

Виконано лише погоджену Phase 0, відповідно до SRS v3.0 §§15, 21–23, 27
та AGENTS.md. Гілка `chore/phase-0-foundation`, початкове робоче дерево чисте.
Репозиторій містив SRS, AGENTS.md, план, README та .gitignore; коду, тестів,
журналу та конфігурації Python не було. Наявну документацію збережено,
README доповнено; SRS та AGENTS.md не змінено.

### Рішення

- Python `>=3.12,<3.13`, `.python-version` = `3.12`; пакет у `src/cyberforge`.
- Мінімальна консольна точка входу `cyberforge.main:main`, також
  `python -m cyberforge`. Це перевірка встановлення, не графічна оболонка.
- Backend `uv_build>=0.13.7,<0.14`; dev-група: pytest `>=8.4,<9`,
  Ruff `>=0.14,<0.15`. Межі допускають виправлення в обраній серії,
  точні runtime/dev-версії та хеші зафіксовано в `uv.lock`.
- Залежності runtime відсутні: PySide6/pytest-qt, Pydantic, ORM та LLM
  додаватимуться в тих фазах, які їх використовують. Порожні шари наперед
  не створено (§22.2). MockLLMProvider не реалізовано: це Phase 4.
- pytest використовує importlib, строгі маркери/конфігурацію та warnings-as-errors.
  Тести перевіряють метадані встановленого пакета й запуск із тимчасового
  каталогу через ізольований Python (`-I`), без підміни PYTHONPATH.
- `.env.example` містить лише коментарі, не завантажується кодом.
  Локальні БД, кеші, .env, артефакти збирання виключено з Git.

Звірено офіційні джерела:
[uv projects](https://docs.astral.sh/uv/guides/projects/),
[uv build backend](https://docs.astral.sh/uv/concepts/build-backend/)
(також Context7 `/astral-sh/uv`),
[Ruff configuration](https://docs.astral.sh/ruff/configuration/),
[pytest good practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html),
[Qt getting started](https://doc.qt.io/qtforpython-6/gettingstarted.html).
Фактична сумісність інструментів підтверджена встановленням і перевірками.

### Середовище та встановлення

WSL2 Linux x86_64, Python 3.12.3, uv 0.13.7, pytest 8.4.2, Ruff 0.14.14.
`uv` спочатку відсутній. Bootstrap:

```console
python3 -m venv /tmp/cyberforge-bootstrap
/tmp/cyberforge-bootstrap/bin/python -m pip install --no-cache-dir uv
/tmp/cyberforge-bootstrap/bin/uv sync --cache-dir .uv-cache
```

Початкові pip install та uv sync у sandbox завершилися DNS-помилкою;
повторні мережеві команди з наданим дозволом успішні. Системний Python
не модифіковано. uv розміщений у `/tmp`, тому для наступного сеансу
його треба встановити за README або повторити bootstrap.

### Фактичні перевірки

Для команд нижче використано локальний кеш і повністю offline режим:

```bash
export PATH=/tmp/cyberforge-bootstrap/bin:$PATH UV_CACHE_DIR="$PWD/.uv-cache" UV_OFFLINE=1
```

| Команда | Результат |
|---|---|
| `uv sync --locked --offline` | Успіх, lockfile узгоджений, 7 установлених пакетів |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 4 files already formatted |
| `uv run pytest` | 2 passed, 0.04 s |
| `uv run cyberforge` | Повідомлення українською, exit 0 |
| `uv run python -m cyberforge` | Повідомлення українською, exit 0 |
| `uv build --offline` | Створено sdist і wheel |
| `git diff --check` | Без помилок |

Перед фінальною перевіркою `.venv/bin/ruff format .` відформатував два файли.
Вміст sdist і wheel перевірено через tarfile/zipfile: лише пакет і метадані,
README/pyproject у sdist; .env, БД і кешів немає. uv попередив, що кеш
розташований усередині дерева; фактичні архіви його не містять.

Додаткова перевірка зібраного wheel:

```console
python3 -m venv /tmp/cyberforge-wheel-check
/tmp/cyberforge-bootstrap/bin/uv pip install --offline --cache-dir .uv-cache --python /tmp/cyberforge-wheel-check/bin/python dist/cyberforge-0.1.0-py3-none-any.whl
/tmp/cyberforge-wheel-check/bin/python -I -m cyberforge
/tmp/cyberforge-wheel-check/bin/cyberforge
```

Усі команди успішні. uv застосував копіювання замість hardlink між файловими
системами; це не вплинуло на результат.
`git check-ignore` підтвердив ігнорування `.env`, `.env.local`,
`local.sqlite3`, `local.sqlite3-wal`, `.venv`, `.uv-cache`, `dist`.
Для `.env.example` отримано очікуваний exit 1: файл не ігнорується.

### Межі доказів і gate

DISPLAY=:0 та WAYLAND_DISPLAY=wayland-0 наявні, але PySide6 не встановлено
(`find_spec('PySide6')` повернув None). Можливість запуску Qt у WSL не доведена.
Windows 11, GUI та Qt WebEngine не тестувалися. Live Gemini не викликався;
тести не потребують ключів або мережі. RBAC та інші предметні функції відсутні,
тому їхні security-тести ще не застосовуються.

Технічний gate Phase 0 у цьому середовищі пройдено. Статус **REVIEW**;
ACCEPTED потребує рішення власника. Phase 1 не починалася. Комітів, push,
merge чи переписування історії не виконано. Наступна рекомендована дія —
перегляд результатів Phase 0 власником та окреме погодження Phase 1.

## 11.11.2026 — прийняття Phase 0 власником

Власник явно прийняв **Phase 0 — Project Foundation (ACCEPTED)** та повідомив
про особисту перевірку у WSL Ubuntu:

| Команда | Результат, підтверджений власником |
|---|---|
| `uv sync --locked` | Успішно |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | Успішно |
| `uv run pytest` | 2 passed |
| `uv run cyberforge` | Успішно |

У `docs/IMPLEMENTATION_PLAN.md` статус Phase 0 оновлено з REVIEW на ACCEPTED.
Цей запис фіксує прийняття після попереднього запису REVIEW; обмеження щодо
неперевірених Windows 11 та Qt залишаються чинними. Код і залежності не змінено;
автоматизовані тести повторно не запускалися для цієї зміни документації.

Phase 1 залишається NOT STARTED і потребує окремого явного погодження.
Git commit, push та merge не виконувалися.

## 11.11.2026 — Phase 1: Main UI Shell — REVIEW

### Обсяг і початковий стан

Власник явно погодив Phase 1 та branch/commit/push/PR після перевірок.
Phase 0 перевірена у локальному Git та через GitHub MCP: PR #1 об’єднано
в `main`, commit `1fc4a59610e00c7d1345d7bf389c3624d10e66da`.
Робоче дерево було чисте. `git pull --ff-only origin main` підтвердив,
що main актуальний; створено `feat/phase-1-main-ui-shell`.

Покриття SRS: §§3.1–3.8 (оболонка режимів), 3.10 (історія контекстів),
3.11 (Guest), 3.13 (активні стани, клавіатура, прокручування, розміри),
15.1/15.4 (PySide6/uv), 21.1/21.3/21.4 (тести в межах Phase 1),
22–22.2 (розмежування UI), 23 Phase 1, 27.4 (MCP).

### Реалізація та рішення

- `main.py`: QApplication, тема та MainWindow; console/module entry points
  відкривають вікно. `--smoke-test` закриває його через QTimer/Qt event loop.
- `ui/theme.py`: Fusion, палітра, типографіка та QSS в одному модулі;
  майбутня тема може замінюватися без зміни навігації.
- `ui/icons.py`: власні векторні іконки через QPainter; немає залежності
  від мережі, зовнішніх шрифтів іконок або сторонніх зображень.
- `ui/navigation.py`: незалежна від Qt історія контекстів GUEST,
  CONSTRUCTOR, ANALYTICS, PROFILE, SETTINGS. Повторний вибір не дублює
  історію; новий перехід після «Назад» прибирає історію «Вперед».
- `ui/shell.py`: основна панель, верхня навігація, один екземпляр панелі
  «Сценарії», QStackedWidget із QScrollArea для кожного представлення.
- `ui/pages.py`: привітання, опис навчального циклу, порожні режими,
  пояснювальні сторінки профілю/налаштувань. Весь UI українською.
- Guest може лише оглянути явно позначену оболонку. Каталог закритий,
  сценарії не завантажуються. Кнопка «+» перемикає контекст, нічого не
  створює. «+ Новий сценарій» видима тільки у Конструкторі та disabled;
  пошук також disabled із поясненням. Жодного demo-login чи тестових даних.
- Справжня форма входу й service-level RBAC залишені Phase 2, persistence/ID
  та захист незбережених сценаріїв — Phase 3+, AI — Phase 4+, аналітичні
  обчислення — Phase 11. Оболонка не оголошує ці вимоги виконаними.
- Мінімум 860×620 обрано як оборотне UI-рішення: дві панелі залишають
  читабельний простір; текст переноситься, довгий вміст прокручується.
- Візуальна перевірка виявила стискання QLabel та обрізання заголовків.
  Усунуто через вертикальну Minimum size policy та розтягування контейнера;
  додано регресійні перевірки висоти тексту для всіх сторінок/розмірів.

### Залежності та MCP

Додано лише PySide6 `>=6.10.1,<6.11` (lock: **6.10.3**) і pytest-qt
`>=4.5,<5` (lock: **4.5.0**). Python **3.12.3**, Qt **6.10.3**,
pytest **8.4.2**, Ruff **0.14.14**, uv **0.13.7** у WSL2.
Офіційну інсталяцію, вимоги Python та Qt API звірено через Context7:
[Qt installation](https://doc.qt.io/qtforpython-6/gettingstarted.html),
[QButtonGroup](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QButtonGroup.html),
[pytest-qt](https://github.com/pytest-dev/pytest-qt/blob/main/README.rst).
Фактична сумісність підтверджена встановленням і тестами.

MCP перевірено саме MCP-викликами, окремо для кожного сервера:

| Сервер | Функціональна перевірка | Результат |
|---|---|---|
| GitHub MCP | `list_commits` для `main` | Отримано merge Phase 0 та SHA |
| Context7 | `resolve_library_id` + `query_docs` Qt for Python / pytest-qt | Отримано актуальну документацію та приклади |
| OpenAI Developer Docs | `search_openai_docs` + `fetch_openai_doc` AGENTS.md guide | Отримано документацію |

OpenAI-документація використана як функціональна перевірка з’єднання;
OpenAI SDK/runtime не додавалися. MCP credentials не читалися/не змінювалися.
AGENTS.md доповнено політикою MCP та workflow для погодженої фази;
merge в main/force-push/видалення гілок залишаються за явним дозволом.
Локальний Git використано для checkout, sync та транспорту локальних комітів;
віддалені перевірки й PR — через GitHub MCP.

### Фактичні перевірки

Для команд `uv` нижче використано:

```bash
export UV_CACHE_DIR="$PWD/.uv-cache" UV_OFFLINE=1
```

| Команда | Результат |
|---|---|
| `uv sync --locked --offline` | Успіх, lockfile узгоджений |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 13 files already formatted |
| `uv run pytest` | **23 passed**, 23.72 s; offscreen за замовчуванням |
| `QT_QPA_PLATFORM=offscreen uv run cyberforge --smoke-test` | Exit 0 |
| `QT_QPA_PLATFORM=offscreen uv run python -m cyberforge --smoke-test` | Exit 0 |
| `QT_QPA_PLATFORM=wayland uv run cyberforge --smoke-test` | Exit 0, реальний WSLg |
| `QT_QPA_PLATFORM=wayland uv run pytest tests/ui -q` | **19 passed**, 24.15 s |
| `uv build --offline` | sdist і wheel успішно зібрані |
| Python tarfile/zipfile inspection | UI у wheel; кешів, .venv, .env, .git в архівах немає |
| `git diff --check` | Успіх |

Тести перевіряють встановлений пакет і subprocess запуск поза репозиторієм,
історію й відсікання гілки переходів, Guest/profile, недоступність створення
та пошуку, одну панель для режимів, активний стан, кнопку створення лише
в Конструкторі, назад/вперед, клавіатуру, всі п’ять сторінок у розмірах
860×620, 1280×800 та 1920×1080, відсутність обрізаного тексту.

WSLg-знімки отримано через QWidget.grab після роботи Qt event loop:
`docs/screenshots/phase-1-{guest,analytics,compact}.png`.
Візуально оглянуто звичайний та компактний вигляд; це реальні порожні
представлення, без синтетичних «результатів» або вигаданих показників.

### Обмеження середовища та gate

- Початкові `git pull` та доступ Wayland до дисплея блокував sandbox;
  повтор із дозволеним доступом успішний. Перше встановлення залежностей
  мало DNS-помилку; повторний доступ PyPI поза sandbox успішний.
- `QT_QPA_PLATFORM=xcb uv run cyberforge --smoke-test`: exit 134;
  Qt повідомляє про відсутню системну залежність `libxcb-cursor0`.
  Системні пакети не змінювалися. Робочий шлях у цьому WSL — Wayland.
- `uv build` попереджає про кеш у дереві; фактичні архіви перевірені,
  локальний кеш не потрапив у них.
- Windows 11, нативні шрифти й DPI 100/125/150/200% не перевірялися.
  WSLg не є Windows-верифікацією. Qt WebEngine у Phase 1 не використовується.
- MockLLMProvider належить Phase 4 і ще не існує. Поточні тести offline,
  оболонка не викликає LLM або зовнішні сервіси й не потребує ключів.

Технічний gate оболонки у WSL пройдено; Phase 1 — **REVIEW**.
Прийняття власником та Windows-перевірка залишаються відкритими.
Рекомендована наступна дія — рев’ю PR та демонстрації. Phase 2 не починалася
і потребує окремого явного погодження. Merge в main не виконується.

### Публікація для рев’ю

GitHub MCP `mcp__github` читає main, але `create_branch` повернув 403
«Resource not accessible by personal access token». Credentials не змінювалися.
Альтернативне підключене GitHub MCP-з’єднання (`codex_apps.github`)
успішно прочитало metadata/permissions та створило віддалену feature-гілку
з `main`; для PR використовується це з’єднання. Це обмеження прав першого
з’єднання, а не недоступність GitHub. Локальна гілка не перезаписувалася.

Перевірений implementation commit `e21b47a` опубліковано у
`origin/feat/phase-1-main-ui-shell`. Через альтернативне GitHub MCP-з’єднання
створено [PR #2](https://github.com/the1llus1on/cyberforge/pull/2) до `main`.
PR відкритий для рев’ю, не об’єднаний; `main` залишається на `1fc4a596`.
Останнє доповнення стосується лише запису результатів Git/PR;
повторні тести коду для цього запису не потрібні.

## 11.11.2026 — уточнення Phase 1 за UI-рев’ю власника

### Рішення й обсяг

Власник погодив універсальну Home як додаткове навігаційне призначення
відносно SRS v3.0 §§3.3–3.4/3.11. Оформлено
[ADR-0001](adr/0001-home-navigation.md); SRS не змінено.
Робоче дерево перед змінами чисте, гілка `feat/phase-1-main-ui-shell`;
GitHub MCP підтвердив PR #2 open/unmerged та head `12afacc`.
Це уточнення Phase 1, яка залишається REVIEW; Phase 2 не починалася.

### Реалізація

- `ui/navigation.py`: `View.HOME` замінює маршрут GUEST, історія починається
  на Home. `AuthenticationState.GUEST` є окремим presentation-станом,
  незалежним від навігації; жодних облікових записів чи авторизації не додано.
- `ui/shell.py`: верхні іконки Home, «+», графік; окремі активні стани.
  Єдиний каталог показується тільки в Конструкторі й Аналізі; Home,
  профіль та налаштування не перевантажені панеллю сценаріїв.
  Переходи та Back/Forward не змінюють Guest-стан і не надають доступу.
- `ui/pages.py`: універсальне привітання, опис, навігаційні підказки;
  «Навчальний цикл» має точний текст
  «Сценарій → Електронний лист → Вебсайт → Аналіз».
  Обмежена ширина контенту центрована, текст переноситься.
  Повторюваний disclaimer прибрано з усіх сторінок.
- ADR визначає майбутню рольову навігацію Phase 2: Home доступна всім,
  є початковою після входу; Administrator/Instructor — Конструктор/Аналіз;
  Learner — «Мої сценарії»/«Мої результати». Ця матриця не є реалізацією
  ролей чи перевіркою автентифікованих шляхів, які залишені Phase 2.
- Security-правила AGENTS.md та SRS §16, внутрішній цикл
  Email → Web → Scoring → Feedback, детерміноване оцінювання не змінено.
  Реальних/тестових сценаріїв і аналітичних даних немає; пошук і створення
  недоступні, режими позначені як попередній перегляд оболонки.
- Оновлено README, план та наявні тести; нових залежностей немає.
  API компонування звірено через Context7 з офіційною документацією
  [QBoxLayout](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QBoxLayout.html).

### Перевірки

Команди uv виконані з `UV_CACHE_DIR="$PWD/.uv-cache" UV_OFFLINE=1`:

| Команда | Результат |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 13 files already formatted |
| `uv run pytest` | **25 passed**, 23.00 s; offscreen |
| `QT_QPA_PLATFORM=offscreen uv run cyberforge --smoke-test` | Exit 0 |
| `QT_QPA_PLATFORM=offscreen uv run python -m cyberforge --smoke-test` | Exit 0 |

Оновлені тести перевіряють Home окремо від Guest, точний цикл й відсутність
видаленого тексту, порядок та доступні назви трьох верхніх кнопок,
незмінні гостьові обмеження, єдиний каталог і його видимість, історію
Home ↔ режими, keyboard Space та всі п’ять сторінок у 860×620,
1280×800 і 1920×1080 без обрізання тексту.

| Додаткова GUI-перевірка | Результат |
|---|---|
| `QT_QPA_PLATFORM=wayland uv run pytest tests/ui -q` | **21 passed**, 27.13 s, реальний WSLg |
| `QT_QPA_PLATFORM=wayland uv run cyberforge --smoke-test` | Exit 0 |
| `git diff --check` | Успіх |

Через WSLg/Qt event loop отримано свіжі знімки:
[Home](screenshots/phase-1-home.png),
[Home 860×620](screenshots/phase-1-home-compact.png),
[Аналіз](screenshots/phase-1-analytics.png),
[Конструктор 860×620](screenshots/phase-1-compact.png).
Старий `phase-1-guest.png` замінено актуальними Home-знімками;
попередній запис журналу з цим ім’ям залишається історичним.
Візуально оглянуто Home у двох розмірах і компактний Конструктор.

Технічний gate уточнення у WSL пройдено; Phase 1 залишається **REVIEW**.
Windows 11/DPI не перевірялися; WSLg не замінює нативну перевірку.
Нових LLM-залежностей немає, MockLLMProvider залишається Phase 4.
Зміни публікуються в ту саму гілку й
[PR #2](https://github.com/the1llus1on/cyberforge/pull/2); новий PR,
merge в main та Phase 2 не виконуються. Наступна дія — рев’ю власника.

## 11.11.2026 — офіційне прийняття та фіналізація Phase 1

Власник явно прийняв **Phase 1 — Main UI Shell (ACCEPTED)** після особистого
запуску та візуального рев’ю CyberForge. Схвалено дизайн, універсальну Home,
Конструктор, Аналіз та погоджені уточнення. Дата рішення — **11 листопада
2026 року**. Це прийняття замінює попередній статус REVIEW; історичні записи
збережено. Власник також явно дозволив злиття PR #2 до main після перевірок.

Початковий стан фіналізації: чиста `feat/phase-1-main-ui-shell`,
HEAD `46dff5357f0ee7a384f3e4023002c9f781fcc439`; GitHub MCP підтвердив той самий
head, base `main`, PR #2 open/unmerged і `mergeable=true`.
Перелік 22 файлів PR та локальний diff відповідають погодженому обсягу
Phase 1: UI, необхідні PySide6/pytest-qt, тести, документація, ADR і знімки.
SRS v3.0 незмінна. Реалізації Phase 2 чи інших фаз немає.

### Фінальні перевірки

Середовище: WSL2, Python 3.12.3, Qt/PySide6 6.10.3, pytest 8.4.2.
Команди uv виконано з `UV_CACHE_DIR="$PWD/.uv-cache" UV_OFFLINE=1`:

| Команда | Результат |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 13 files already formatted |
| `uv run pytest` | **25 passed**, 27.01 s, offscreen |
| `QT_QPA_PLATFORM=wayland uv run pytest tests/ui -q` | **21 passed**, 26.91 s, WSLg |
| `QT_QPA_PLATFORM=offscreen uv run cyberforge --smoke-test` | Exit 0 |
| `QT_QPA_PLATFORM=offscreen uv run python -m cyberforge --smoke-test` | Exit 0 |
| `QT_QPA_PLATFORM=wayland uv run cyberforge --smoke-test` | Exit 0 |
| `git diff --check` | Успіх |
| `git diff --exit-code origin/main...HEAD -- TECHNICAL_SPECIFICATION.md` | Успіх, SRS не змінено |

GitHub MCP повернув порожні списки commit statuses та workflow runs:
віддалений CI не налаштовано; це не замінює локальних перевірок вище.
Тести виконані offline без API-ключів чи LLM; MockLLMProvider залишається Phase 4.
Windows 11/DPI не перевірялися агентом. Платформу особистого запуску власник
не вказав, тому його схвалення не позначається як Windows-верифікація.

План, README і статус фази в ADR оновлено до ACCEPTED. Код і залежності
під час фіналізації не змінюються. Технічний gate та прийняття власником
завершено; документація публікується в існуючу feature-гілку PR #2.
Злиття виконується лише після повторної перевірки актуального head і
відсутності конфліктів, без force-push, переписування історії та видалення гілок.

Phase 2 — **NOT STARTED**, готова до окремого явного погодження.

## 11.11.2026 — Phase 2: початок

Погоджено лише Users & Groups. Чиста main синхронна з origin/main
(`fc713837`), створено feat/phase-2-users-groups. GitHub MCP та Context7
функціональні. Перевірено офіційну документацію SQLAlchemy, Alembic,
argon2-cffi; рішення й результати реалізації будуть записані нижче.

## 11.11.2026 — Phase 2: реалізація та перевірки

### Обсяг і архітектура

Покрито SRS §§2.1–2.8, 3.9–3.13 і рольові частини §3, 14.1–14.2/14.9,
15.1/15.4, 16.2/16.6, релевантні перевірки §§21–23, ADR-0001.
Реалізація на гілці `feat/phase-2-users-groups`; SRS та AGENTS.md не змінено.

- `domain/accounts.py`: Role/Workspace та публічні DTO без паролів/хешів.
- `identity/{passwords,sessions}.py`: Argon2id, перевірка/rehash,
  випадкові процесні сесії.
- `application/accounts.py`: login/logout, зміна/скидання пароля,
  користувачі, авторизація маршрутів, транзакційні перевірки Administrator.
- `groups/service.py`: CRUD груп і M:N-членство; scoped читання для
  Instructor/Learner, усі зміни виконує лише Administrator.
- `persistence/{models,database}.py`, пакетні `migrations/`: чотири таблиці,
  PK/unique/check/FK, role-тригери, foreign_keys=ON, Alembic revision
  `0001_users_groups`. Сценарних таблиць немає.
- `ui/{account_pages,admin_page}.py`, shell/navigation/pages/icons:
  масковані форми, рольові маршрути, Home й нова історія після входу/виходу,
  українські адміністративні екрани, очищення даних і відкликаних сесій.
  Візуальну основу Phase 1 збережено.
- `main.py`, `application/demo.py`: явні normal/bootstrap/demo режими,
  необов’язковий шлях БД, ідемпотентний demo seed, випадкові паролі лише у
  новому приватному локальному файлі. Нормальна ініціалізація не додає demo.
- Нові unit/integration/security/GUI-тести; мінімальний GitHub Actions CI;
  README, ADR-0001/0002, план і цей журнал; актуальні WSLg-знімки.

Рішення й наслідки детально наведено в ADR-0002: деактивація замість
видалення користувача, захист останнього адміністратора, від’єднання
членства при зміні ролі, межі паролів/логінів, `BEGIN IMMEDIATE` для записів,
auth_version для відкликання між процесами. Це локальні реалізаційні
деталі в погодженому обсязі; нових продуктових ролей або вимог немає.
Після reset/change потрібен повторний вхід. Сесії не переживають перезапуск.

### Залежності та джерела

Python 3.12.3, uv 0.13.7; наявні PySide6/Qt 6.10.3, pytest 8.4.2,
pytest-qt 4.5.0, Ruff 0.14.14. Додано лише необхідні runtime-залежності:
SQLAlchemy `>=2.0,<2.1` (lock 2.0.57), Alembic `>=1.18,<2` (1.20.1),
argon2-cffi `>=25.1,<26` (25.1.0). Установлення й сумісність перевірено.

GitHub MCP функціонально підтвердив remote main `fc713837…`; локальний
fetch/fast-forward підтвердив тотожність HEAD/origin/main і чисте дерево.
Context7 перевірив офіційні джерела API:

- [SQLAlchemy SQLite foreign keys](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#foreign-key-support)
  — connect event і PRAGMA.
- [Alembic shared connection](https://alembic.sqlalchemy.org/en/latest/cookbook.html#sharing-a-connection-across-one-or-more-programmatic-migration-commands)
  — Config.attributes і пакетні міграції.
- [argon2-cffi API](https://argon2-cffi.readthedocs.io/en/stable/api.html)
  — Argon2id defaults, verification errors, check_needs_rehash.

GitHub MCP також прочитав `astral-sh/setup-uv` action.yml у tag v6:
версія uv задається офіційним параметром `version`. OpenAI-документація
для цієї фази не потрібна. Runtime не залежить від developer MCP.

### Середовище й виправлені проміжні помилки

Фактичне середовище: WSL2 Linux 6.6.114.1, Ubuntu/glibc 2.39, x86_64.
Запис у `.git` і доступ до WSLg потребували дозволеного виконання поза sandbox.
Початковий мережевий `uv add` у sandbox завершився DNS-помилкою;
повтор з дозволом успішний. Усі перевірки проєкту після встановлення — offline.

Перший прогін старих GUI-тестів виявив запис БД у read-only каталог профілю;
тести переведено на власні тимчасові БД та ін’єкцію сервісів, subprocess smoke
отримав явний тимчасовий шлях БД. Після зміни layout короткий проміжний прогін
виявив пропущений імпорт QFrame/QHBoxLayout; виправлено та повторно перевірено.
Жодного з цих станів не опубліковано.

Початковий Wayland-запуск у sandbox: `wl_display (Operation not permitted)`.
Повтор з доступом до WSLg успішний. Першій isolated wheel-інсталяції offline
бракувало кешованих wheels; залежності встановлено з дозволеною мережею,
подальший запуск і повторна інсталяція актуального wheel — offline.

### Докази

Для команд uv використано `UV_CACHE_DIR=$PWD/.uv-cache`.
Команди та підсумкові результати наведено нижче після фінального прогону.


| Команда / перевірка | Підсумковий результат |
|---|---|
| `uv sync --locked --offline` | Успіх, 23 resolved / 22 installed checked |
| `uv run --offline ruff check .` | All checks passed |
| `uv run --offline ruff format --check .` | 33 files already formatted |
| `uv run --offline pytest --tb=short -q` | **68 passed**, 147.71 s |
| `QT_QPA_PLATFORM=wayland uv run --offline pytest tests/ui -q --tb=short` | **37 passed**, 103.62 s |
| `uv build --offline` | Wheel і sdist успішні |
| ZipFile/tarfile inspection | Пакетні міграції присутні, local/cache/credentials/БД відсутні |
| Ізольована інсталяція wheel та `python -I -m cyberforge --database … --smoke-test` з `/tmp` | Успіх, exit 0 |
| `QT_QPA_PLATFORM=offscreen uv run --offline cyberforge --database /tmp/cyberforge-phase2-cli-smoke.sqlite3 --smoke-test` | Exit 0 |
| `QT_QPA_PLATFORM=wayland uv run --offline cyberforge --database /tmp/cyberforge-phase2-wayland-smoke.sqlite3 --smoke-test` | Exit 0 |
| WSLg preview script `/tmp/cyberforge-phase2-preview.py` | 4 актуальні знімки, exit 0, оглянуто |
| `git diff --check` | Успіх |

Повний pytest включає 19 identity/RBAC unit-security тестів, 8 database/demo
integration тестів (зокрема CLI без виведення паролів), 37 GUI-тестів і
4 foundation/navigation тести. Негативні перевірки охоплюють Guest, Instructor,
Learner, підроблений/відкликаний токен, чужу групу, некоректне членство,
повторний логін без logout, деактивацію та заборонені адміністративні зміни.
Alembic перевірено через metadata diff, повторний upgrade, downgrade/upgrade,
FK/unique/check/role constraints і повторне відкриття БД.

Знімки фактичного WSLg:
[вхід](screenshots/phase-2-login.png),
[користувачі](screenshots/phase-2-admin-users.png),
[групи](screenshots/phase-2-admin-groups.png),
[учень](screenshots/phase-2-learner.png).
Секрети у знімках відсутні; preview використовував тимчасову синтетичну БД.

### Обмеження та рішення gate

Технічний gate Phase 2 у WSL пройдено, статус **REVIEW**. Windows 11, DPI,
Windows ACL demo-файлу й майбутнє Windows-пакування не перевірено.
WSLg не є Windows-верифікацією. Runtime та baseline тести offline без cloud
викликів; MockLLMProvider належить Phase 4 і не додавався завчасно.
Статистики/результатів/сценарних сутностей немає; майбутні правила доступу
до них перевірятимуться у відповідних фазах. GitHub Actions workflow додано,
але результат remote CI слід відрізняти від локальних доказів.

Рекомендована наступна дія — рев’ю PR та особиста демонстрація власником.
Прийняття Phase 2 і merge залишаються за власником. Phase 3 не починалася.

### Git та PR

Реалізацію закомічено як `83e803d` і відправлено в
`origin/feat/phase-2-users-groups`. Через GitHub MCP створено
[PR #3 — Phase 2: автентифікація, користувачі та навчальні групи](https://github.com/the1llus1on/cyberforge/pull/3)
до `main`, відкритий для рев’ю; merge не виконувався.

GitHub MCP `get_check_runs` повернув 403 через scope PAT. Fallback —
підключений GitHub app MCP: він підтвердив запуск Actions `Python checks`.
Установлення, Ruff lint і format пройшли; pytest виконувався на момент
запису. Це не збій локальних перевірок і не недоступність GitHub MCP загалом:
branch read та створення PR були успішні. Поточний результат CI доступний
у [перевірках PR](https://github.com/the1llus1on/cyberforge/pull/3/checks).
Після основного коміту внесено лише цей запис про доставку результату.

## Phase 2 — уточнення security review: POSIX SQLite permissions

Нові каталоги створюються приватно (0700), файл БД резервується через
ексклюзивний os.open з mode 0600 до відкриття SQLite. Наявні файли й каталоги
не змінюються, глобальний umask не змінюється. Нові subprocess-тести з
umask 000 перевіряють файл, вкладені каталоги, живі DELETE journal і WAL/SHM,
а також збереження наявних mode 0755/0640. Windows ACL не перевірено й не
гарантується POSIX mode; старі відкриті БД потребують окремого огляду власником.
Оновлено README, ADR-0002 та план. Phase 2 — REVIEW, Phase 3 не починалася.
Перевірки: Ruff lint — успіх; format — 34 файли; нові permission-тести —
2 passed. Повний pytest включає міграції, persistence, RBAC та GUI.

Фінальний `uv run --offline pytest -q --tb=short`: **70 passed**, 130.25 s.
`git diff --check` успішний. Remote CI перевіряється після push у PR #3.

## Повторний owner UI review — PR #3, коментар 6804044603

Усі вісім пунктів прочитано через GitHub MCP. Робоче дерево на початку чисте,
гілка feat/phase-2-users-groups. Обсяг: SRS §§2–3,14.9,16.6,21–23.

Причини: відсутня delete-операція; default role був index 0 (Administrator);
metadata/membership мали дві транзакції та дві кнопки; фільтри відсутні;
Guest preview був явно дозволений попереднім ADR; selection не мав окремого
inactive treatment або empty-area deselect. Combo використовував стандартний
popup: додано widget popup і явне прийняття clicked index. Фізичний збій
старого popup у середовищі власника не оголошується відтвореним; поточна
поведінка перевірена реальним Qt popup mouse click у WSLg.

Зміни: admin-only delete у транзакції, current/last-admin protections,
FK-перевірка історичних даних незалежно від CASCADE, membership cleanup.
Credential fingerprint сесії захищає також від повторного використання ID;
rehash консервативно відкликає старі сесії. Єдиний save metadata+membership
відкочується повністю при помилці. Фільтри приховують items без rebuild,
зберігаючи edit identity і checked draft state. Додано Learner default,
confirmation dialog, selection styles/empty deselect, Guest deny routes.

WSLg 1.0.73 журнал містить Failed to switch 0x20422, layout=(null), reset
keymap. ua symbols присутні, C.UTF-8 підтримує Unicode. Це підтверджений збій
Weston RDP→XKB для Enhanced; зміна locale застосунку не випливає з доказів.
Тест QKeyEvent/QInputMethodEvent у трьох полях успішний у WSLg. Фізичний
ввід власника/перемикання Windows Settings не виконано агентом; кроки та
джерела наведено в docs/diagnostics/wslg-keyboard.md. Власник не перевіряв
інші Linux GUI, Windows Terminal використовує інший шлях введення.

Оновлено README, ADR-0001/0002 з явним заміщенням попередніх Guest/deletion
рішень, план і фактичні WSLg screenshots. SRS/AGENTS.md не змінено.
Початкові прогони: 63 pytest passed; 27 WSLg GUI passed. Після додавання
регресій confirmation/ID-reuse запущено фінальні прогони нижче.
Windows 11 та фізичне введення після зміни розкладки не перевірено.
Phase 2 залишається REVIEW; Phase 3/merge не виконуються.

Фінальні результати: `uv run --offline pytest -q --tb=short` — **65 passed**,
88.49 s; `QT_QPA_PLATFORM=wayland uv run --offline pytest tests/ui -q --tb=short`
— **28 passed**, 47.63 s. Ruff check/format — успіх, 34 Python-файли.
Окремий WSLg popup regression додатково перевіряє Home/End з клавіатури та
empty-area deselect зі збереженням identity при простій втраті фокуса.
Зменшення загальної кількості тестів від попередніх 70 пояснюється заміною
старих Guest-preview тестів новими Guest-deny/layout тестами; рольові
layout/regression тести для трьох авторизованих ролей збережено.
`git diff --check` — успіх. CI запускається push у той самий PR #3.

## Залишкові чотири дефекти після фізичного owner review

Початкове дерево чисте, поточна feat/phase-2-users-groups. Прочитано SRS §§2,
план/журнал/ADR і відповідні UI-тести. План (§§2–3,16.6,21): прибрати custom
popup lifecycle → уніфікувати списки → display names/search/elision → повторна
keyboard діагностика → Ruff/pytest/WSLg/CI, push у той самий PR #3.

RoleCombo власноруч викликав setCurrentIndex/hidePopup з clicked усередині
Qt event dispatch. Його видалено; тепер стандартний QComboBox без popup
stylesheet override і без власних mouse event handlers. Context7 перевірив
офіційний контракт Qt hidePopup/activated/currentIndexChanged. Нові повні
mouse-тести спочатку виявили межу QTest: без наведення/settling перший release
може ігноруватися штатним Qt. Додано реалістичне наведення й перевірку закриття
самого popup window після наступних event-loop turn; усі три ролі та клавіатура.
У Wayland synthetic pointer не надає compositor serial і warp; зафіксовано
Failed to create grabbing popup, три mouse-випадки явно skipped, а keyboard
popup проходить окремо. Не додавали event workaround в продукт заради тесту.

Асиметрію списків підтверджено в коді: instructors=EditableList,
learners=QListWidget. Обидва уніфіковано, focus-out знімає лише selection,
current identity/check states зберігаються. Тести обох списків незалежні.
Users раніше взагалі не включав display_name у текст — додано повний запис,
elide-right/tooltip, пошук за ім’ям/логіном і перевірку оновлення після Save.

Фізична клавіатура: свіжі логи Weston повторюють failure 0x20422; reliable
solution/physical workaround не підтверджено. Read-only Windows interop:
Python лише 3.13, PySide6 відсутній, uv не знайдено. Native Windows 11 не
запускався. tools/keyboard_probe.py дає незалежне порівняння без БД/секретів,
ручні кроки наведено у docs/diagnostics/wslg-keyboard.md. Системні налаштування,
owner demo-БД й credentials не читали/не змінювали. Скриншоти — тимчасова demo-БД.

Фінальні перевірки: `uv run --offline pytest -q --tb=short` — **74 passed**,
59.77 s. `QT_QPA_PLATFORM=wayland uv run --offline pytest tests/ui -q --tb=short`
— **34 passed, 3 skipped**, 37.80 s; усі skips — окремо позначені synthetic
mouse-popup випадки, не фізична перевірка. Ruff check/format — успіх,
35 Python-файлів; git diff --check — успіх. Актуальні WSLg-знімки оглянуто:
імена видно, групи/позначки після зміни фокуса збережено. Remote CI перевіряється
після push. Phase 2 — REVIEW; фізичний Ukrainian input лишається відкритим,
Windows verification не виконано, Phase 3/merge заборонені без погодження.

## Owner refinement: три ролі без popup, checkbox pickers, Ctrl metadata

Початкове дерево чисте, гілка feat/phase-2-users-groups. Прочитано актуальні
SRS §§2–3, план/журнал/ADR, UI і probe; обсяг §§2–3,16,21 у межах REVIEW.

Upstream прочитано через GitHub MCP: WSLg #1522 open; Weston #172 open,
merged=false, виправляє popup/RAIL; Weston #150 open, merged=false, додає
Enhanced/Unicode layouts, автор зазначив відсутність тестування. WSL 3.0.5
release notes та standalone WSLg release list не підтверджують доставку
Enhanced fix. Не робимо висновок про всі bundled builds лише з цього списку.
Локальна версія 1.0.73/Weston 2318feca; фікс у офіційному доступному релізі
не верифіковано. Система не змінювалася, Weston не збирали/не патчили.

Причини/зміни: власник повторно підтвердив popup defect навіть зі стандартним
QComboBox; тепер popup взагалі прибрано. RoleChoice: три accessible radio,
exclusive QButtonGroup, Учень default, зміна лише форми до explicit Save.
Membership — checkbox pickers NoSelection/items not selectable; default Qt
check indicators постійно видимі, unchecked мають контрастну рамку. Row release
змінює check state рівно раз, Space — штатний delegate. Додано незалежні
тести обох picker: checked/unchecked toggle, клавіатура, no row-selection,
фільтрація draft values. Atomic group service і RBAC не змінювалися.
Проміжний тест виявив enum/int відмінність CheckStateRole у PySide6;
порівняння виправлено, повторний toggle перевірено.
Context7 звірив офіційні QButtonGroup/NoSelection/delegate контракти.

Фізичні докази власника: Standard Ukrainian typing працює; Enhanced typing
не працює і в app, і в чистому probe; English Ctrl+V працює, Standard Ctrl+V
ні. Це не доказ конкретного Qt shortcut mapping. Probe тепер показує лише
числові Ctrl/Shift+Insert key/modifiers/scan/native virtual/backend і Qt matches,
без event.text(), clipboard, паролів, stdout або файлів. Звичайні символи,
AltGr/GroupSwitch і password fields не спостерігаються. Observer не споживає
події; тестується стандартне copy/cut/paste/select-all, Shift+Insert і Qt paste
метод. Власнику запитано фізичні English/Standard рядки; поки їх немає,
application-level shortcut correction не вводиться. Ctrl+V під Standard —
відкритий пункт, Shift+Insert можливий workaround лише після фізичного тесту.

Оновлено README, ADR, план, діагностику і WSLg screenshots (тимчасова synthetic
demo-БД, owner БД/credentials не змінено). Native Windows не перевірено;
ніяких автоматичних змін Windows layouts/WSL configuration. Після додаткового
редагування контрасту запущено фінальний повний pytest і WSLg suite.
Попередній прогін 78 passed / WSLg 41 passed; додатковий probe-editing test
і перевірки privacy/password protections включені у фінальний набір.

Фінальні команди: `uv run --offline ruff check .` — успіх;
`uv run --offline ruff format --check .` — 36 files formatted;
`uv run --offline pytest -q --tb=short` — **79 passed**, 60.43 s;
`QT_QPA_PLATFORM=wayland uv run --offline pytest tests/ui -q --tb=short` —
**42 passed**, 40.91 s, без skips. Popup tests замінено radio tests, бо popup
видалено з продукту. Нові probe privacy/Qt editing tests перевіряють StandardKey,
Shift+Insert, paste(), Copy/Cut/SelectAll і password copy restriction, але це
не фізичні Windows/XKB події. Скриншоти оновлено й оглянуто, unchecked border
контрастний; owner demo-файлів не торкалися. git diff --check — успіх.
Phase 2 — REVIEW; Ctrl+V під Standard і Enhanced лишаються відкритими,
фізичні event-метадані очікуються від власника. CI буде перевірено після push.

## Owner evidence: indicator-only, window sizing, scoped shortcuts

Початок: чиста feat/phase-2-users-groups, Phase 2 REVIEW. Прочитано SRS §§2–3,
план/журнал/ADR, shell/admin і відповідні тести. Погоджений обсяг §§2–3,16,21:
штатний Qt indicator hit-testing → availableGeometry sizing/sticky actions →
точний clipboard mapping за фізичними доказами → unit/WSLg/DPI/CI → PR #3.

Broad row-click delegate прибрано: лишився default QStyledItemDelegate.
Positive test визначає rect через SE_ItemViewItemCheckIndicator; negative
clicks у SE_ItemViewItemText та порожній області не змінюють CheckStateRole.
Space/NoSelection/draft filtering/atomic save збережено. Context7 звірив
офіційний Qt delegate/style контракт.

Новий ui/clipboard_shortcuts.py: exact owner pairs (421,36) Copy, (41C,37)
Paste, (427,35) Cut, (424,26) SelectAll, hex; тільки Ctrl 04000000, Qt backend
wayland + WSLg marker. Already-matching StandardKey не перехоплюється.
Filter обмежений Qt text editors-нащадками MainWindow. ShortcutOverride
лише резервує подію; KeyPress викликає native operation один раз, без
synthetic events і logging. Password copy/cut блокуються, paste/select-all
працюють; readonly не змінюється. Інші modifiers, platforms, scans/keys,
Unicode, IME, AltGr і Shift+Insert лишаються Qt. Тести перевіряють scope,
signal count, exact mapping, негативні умови, English, Shift+Insert і три
типи text editor. Standalone probe залишається baseline observer.

Window sizing: старе preferred1280×800/min860×620 і full-page form scroll
було незручним для admin. Тепер preferred1400×900/min1100×720, bounded
availableGeometry (logical pixels), centered, 48 px screen reserve. Root
scroll з usable content860×620 незалежний від WM hints. Admin actions у
двоколонковому footer поза scrollable forms. Тест fallback спершу виявив,
що root без content minimum просто стискався без scrollbars; додано explicit
content minimum, після чого forced640×480 із знятим frame minimum має
scrollbars і досяжний Profile. Sticky actions перевірено на обох admin tabs.

WSLg діагностика з тимчасовою порожньою БД: screen1920×1080, DPR1,
initial1400×900, minimum1100×720; resize(1,1) обмежено до1100×720. Wayland
trace містить set_min_size1100×720 і1106×753 (decoration extents).
Фізичний owner drag RDP-рамки нижче minimum агентом не відтворено; не
стверджується, що Windows/compositor завжди виконає hints. Root fallback
покриває випадок фактичного меншого Qt viewport. Деталі — window-sizing.md.
Windows11/native DPI не тестувалися; WSLg QT_SCALE_FACTOR не є Windows acceptance.

Фінальні перевірки:
- `uv run --offline ruff check .` — успіх.
- `uv run --offline ruff format --check .` — 40 Python-файлів.
- `uv run --offline pytest -q --tb=short` — **106 passed**, 85.89 s.
- `QT_QPA_PLATFORM=wayland uv run --offline pytest tests/ui -q --tb=short`
  — **69 passed**, 66.86 s, без skips.
- `QT_QPA_PLATFORM=wayland QT_SCALE_FACTOR=1.5 uv run --offline pytest tests/ui -k 'role_layout or admin_actions or indicator_only or screen_sizing' -q --tb=short`
  — **16 passed**, 15.70 s.
- Та сама команда з QT_SCALE_FACTOR=2 — **16 passed**, 26.07 s.
- git diff --check — успіх; screenshots1400×900 і1100×720 оновлено й оглянуто.
Owner demo-БД/credentials не змінено. Фізичні виправлені shortcuts і manual
resize ще має перевірити власник. Enhanced upstream limitation не змінена.
Phase 2 — REVIEW, SRS не редаговано, Phase 3/merge не виконуються.

## Phase 2 — pre-acceptance independent technical audit

Старт: чиста feat/phase-2-users-groups на 6ba0a6a, порівняння з origin/main.
Прочитано SRS v3.0, AGENTS, план/журнал/ADR і Phase2 diff (production, tests,
міграція, CI, залежності, документи). Scope §§2–3,14–16,21–23. Незалежний
огляд не спирався лише на попередні green checks. Нових фаз/LLM/scenarios немає.

Реальні audit fixes:
- Logout залишав текст admin filters; тепер cleanup очищає, refresh зберігає.
- Частковий optional membership payload міг стерти інший набір: відхиляється
  до mutation, обидва sets зберігаються атомарно або none/none metadata-only.
- New-user Active checkbox ігнорувався: обраний стан передано в сервіс,
  inactive account не може ввійти.
- Відтворено failing GUI test: деактивований member зникав із picker й
  metadata Save стирав membership. Existing inactive membership тепер видимий
  і зберігається; нове inactive assignment відхиляється, removal явний.
- DB lock/open/migration errors не мали safe handling. DBAPIError перетворюється
  у safe ApplicationError; UI fail-closed скидає сесію/дані; startup не виводить
  SQL/traceback. Реальні lock/recovery та corrupt-file preservation тести.
- Historical delete guard неправильно припускав users.id для всіх FK.
  Correlated FK predicates враховують referenced columns (username теж),
  не повертають hash/records у UI й не каскадують історію.
- Cancel/New могли показувати false «Зміни збережено»: це виправлено.

Сервіси/RBAC/role triggers/Argon2id/credential tags/atomic writes залишилися
окремими відповідальностями. sessionmaker.begin closes/rolls back — звірено
Context7 з офіційним SQLAlchemy. Додано concurrency test двох адміністраторів:
BEGIN IMMEDIATE допускає лише одну взаємну деактивацію; залишається active admin.
Заборонені delete paths включено в загальну Guest/Instructor/Learner matrix.

CI: GitHub MCP/app для status/jobs, read-only gh api для полів, які wrapper
не повертає. 6ba0a6a run43098666057 queued, jobs=[]; created22:53:35 Kyiv,
до нього GitHub підтвердив Actions major outage з22:48 Kyiv. Workflow не має
approval/self-hosted/concurrency gates; run6 того самого workflow успішний.
Статус не оголошено success; exact per-run scheduler reason API не віддає.
Посилання інциденту й аналіз — docs/audits/phase-2-pre-acceptance.md.

Додано matrix ubuntu-latest/windows-2022, locked Python3.12 sync/Ruff/full pytest,
import і Qt event-loop smoke у runner.temp. Windows Server2022/offscreen не
дорівнює Windows11 physical desktop. Host Windows власника не змінено, нічого
не встановлено. POSIX permissions tests лишаються platform-skipped на Windows;
ACL/DPI/keyboard/clipboard bridge потребують фізичної перевірки.

Фінальні локальні докази:
- uv sync --locked --offline — успіх.
- uv run --offline ruff check . — успіх.
- uv run --offline ruff format --check . — 40 files already formatted.
- uv run --offline pytest -q --tb=short — **117 passed**, 97.32 s.
- QT_QPA_PLATFORM=wayland uv run --offline pytest tests/ui -q --tb=short —
  **73 passed**, 73.92 s, справжній WSLg, без skips.
- Package import та CLI --smoke-test на тимчасовій БД — exit0.
- uv build --offline; wheel reinstall в окреме /tmp environment; isolated
  Python -I startup smoke — exit0. Пакетна міграція присутня, local DB/credentials
  у wheel відсутні. Попередження uv про кеш перевірено оглядом архіву.
- YAML matrix розібрано системним parser без нової залежності.
- git diff --check — успіх. Усі runtime перевірки offline без cloud/LLM.

README, ADR, план оновлено; docs/audits/phase-2-pre-acceptance.md — повний звіт,
docs/PHASE_2_ACCEPTANCE.md — лише залишкові owner physical tests. Owner local
files/DB/credentials/system settings не читали/не змінювали. Phase2 REVIEW;
Windows CI до фактичного завершення не вважається верифікованим. Без merge/Phase3.

### Доповнення аудиту: фактичний Windows run і FK collation

Run43102780570 для5eb443a: Linux success; Windows113 passed,2 skipped,
2 failed. Обидва CLI failures від redirected CP1252 при Python -I (env UTF-8
mode в isolated запуску не застосовується). Demo дані створювались, але
status print кидав UnicodeEncodeError. CLI тепер налаштовує перенаправлені
stdout/stderr на UTF-8, без зміни console/stdin/system locale. Consumer tests
явно декодують UTF-8; regression моделює CP1252 streams. Перевірки не послаблено.

Окремий failing-first test виявив CASCADE corner з parent NOCASE unique key.
Guard ставить parent column зліва згідно SQLite FK comparison semantics і
розпізнає mixed-case referred table name. Production schema не розширювалася.

Повторний local pytest:119 passed,79.82s; Ruff lint/format40files — успіх;
uv build --offline — успіх. WSLg Wayland GUI:73 passed,61.18s (із доступом до
socket поза sandbox; sandbox socket denial не є application regression).
Оновлений isolated wheel startup:exit0; archive inspection підтвердив packaged
migration і відсутність local DB/credentials/cache. Повторний Windows matrix
перевіряється після push; фактичні hosted результати див. checks PR#3.
Owner data/credentials/host settings збережено; REVIEW, без merge/Phase3.

### Підтверджений hosted matrix результат

11.11.2026, code commit60947fa, run43103905494 — completed/success.
GitHub MCP перевірено job status, усі steps та pytest summaries у logs:
- Ubuntu:119 passed,90.12s.
- Windows Server2022:117 passed,2 skipped,124.67s; skips — POSIX mode tests.
- На обох: locked install, Ruff lint/format40files, package import та
  Qt event-loop CLI smoke — success.

Попередні Windows CLI failures усунуто реальним application fix; tests не
вимикали/не послаблювали. Windows host власника не змінювався. Hosted Server
offscreen результат не доводить Win11 desktop, physical keyboard/resize/DPI/ACL.
PR#3 оновлюється результатами; автоматизовані gates пройдено, Phase2 REVIEW.

### 12.11.2026 — native Windows acceptance environment

Owner report:9/10 фізичних WSLg acceptance checks passed; remaining — tiny
physical window frame. Стан REVIEW. Новий дозволений D:\Programs\Own\program\
cyberforge-win-test; existing contents були відсутні. git archive04f01db
експортував лише tracked files, без WSL .venv/.local/DB/secrets.
Portable uv0.13.7 перевірено за release SHA256; Python3.12.16 x64 local install
з --no-bin/--no-registry. Усі cache/temp/runtime dirs у test root. Python3.13,
PATH/registry/PyCharm/Windows keyboard settings не змінювалися.

Native PowerShell5.1: PySide6/Qt6.10.3, backendwindows, desktopDPR1.25,
available1536×816 logical. minimum1100×720; hint36×54; native min tracking
1393×947 physical; resize(1,1) →1100×720. Native startup/migrations success;
baseline full pytest117passed/2POSIX skips,81.51s; native shell/geometry14passed,
7.18s. Ці автоматизовані дії не є physical mouse/keyboard acceptance.

Реальний frame(68,-6,1400,798) відтворив clipping над screen6logical px.
Додано showEvent clamp початкової позиції після native decorations, без
fixed-size і resize loops; regression перевіряє frame containment, native
tracking metadata (лишеwindows backend) та вільний resize. Новий window_probe
збирає geometry/version metadata з порожньої temporary DB, без account data.
Preliminary geometry tests:5passed offscreen/5passed WSLg Wayland.

Окремий random-suffix profile demo-каталог захищено ДО init: ACL inheritance
off; FullControl тільки user SID/SYSTEM/Administrators. Get-Acl перевірив dir,
DB, credentials; repeat init зберіг credentials (вміст/хеші не логувалися).
Запускний tracked PS script перевіряє ACL, викликає явний local Python і
backendwindows, не seed-ить і не встановлює нічого. Root cmd wrapper створюється
лише в дозволеному test workspace. docs/diagnostics/native-windows.md — guide.
Final snapshot/export і результати після source fix фіксуються наступним кроком.

Перед export виправлення: Ruff lint/format41files, diff check — success;
повний local pytest120passed,80.24s; geometry5passed offscreen та5passed
WSLg Wayland. PowerShell5 parser прийняв launcher (UTF-8 BOM навмисно).
Native OS caption підтвердив Windows11 Pro, build26300; automation не є
physical acceptance. Результат source fix на native backend ще не зараховано.

Snapshoteb6cf79 експортували окремо; native frame тепер(68,0,1400,798) замість
(68,-6,1400,798), min1100×720 не змінено. Full Windows pytest118passed/2skips,
94.44s; native geometry/shell15passed,9.12s. WSLg suite74passed,73.51s.
Root CMD/PS launcher smoke пройшов із Windows cwd; contradictory modes rejected.

Додатковий native account/admin suite:30passed/1failed (53.58s), failure —
test_admin_actions_stay_visible. Діагностика на empty temporary DB показала
page730px приviewport656px; preferred heightForWidth outer scroll відсував
нижні actions за viewport.30/300ms дали однаковий стан: це реальний layout
дефект native metrics, не timing. Вузький AdminPage.heightForWidth override
делегує layout.minimumHeightForWidth, зберігає існуючі containers/inner scroll.
Candidate native measurement: page656px і нижня кнопка закінчується685px при
window720px. Регресія тепер перевіряє повні bounds і multiline message.
Final suites/новий tracked export виконуються до публікації цього уточнення.

Після minimumHeightForWidth fix: local pytest121passed,96.99s; справжній WSLg
GUI75passed,75.01s; Ruff41files і diff check — success. CI дляпопереднього
eb6cf79 завершивсяsuccess наобох OS (run43130028480), але не доводить новий
layout fix; його native regression виконується на окремому наступному snapshot.

Committed code1e11497c09c60ee4bd02b097d330f682d2ada420 перевірено окремо:
- Native Windows backend GUI47passed,65.62s (accounts/admin/shell/geometry).
- Full Windows pytest119passed/2POSIX skips,82.52s.
- Locked offline sync, Ruff lint/format41files, packaged migrations і launcher
  startup — success. Усі69tracked files побайтово відповідають git archive.
- Frame(68,0,1400,798), client1400×768 приavailable1536×816/DPR1.25;
  declared minimum1100×720, native tracking1393×947physical.
- Existing Python3.13.5 успішно запущено read-only через py launcher, без змін.
- Native125% synthetic widget captures Users/Groups на1100×720 збережено й
  переглянуто: кнопки повністю видимі; inner scroll доступний, стиль збережено.
  Це QWidget.grab лише власного вікна, не desktop/credentials screenshot.

Private Windows profile demo зберігається між source snapshots; password values
не читали/не логували; WSL owner data не копіювали/не змінювали. Root PS/CMD
launcher залежить тільки від Windows файлів у дозволеному root/profile dirs,
не від WSL або IDE. Мінімальний physical Windows frame test лишається owner:
WM_GETMINMAXINFO/programmatic resize не дорівнює ручному dragging. Phase2 REVIEW.

## 12.11.2026 — Phase 2: остаточне прийняття та дозвіл merge

Власник явно прийняв Users & Groups: **REVIEW → ACCEPTED**. Він дозволив
документаційний commit/push у поточну гілку й merge PR#3 після перевірки
фінального HEAD та CI. Це замінює попередні pending owner gates, не змінюючи
історичні записи їх фактичних результатів.

Початковий стан фіналізації: чиста feat/phase-2-users-groups, локальний і
remote PR HEAD `50d89e970559d725ca0f603e3db220b130d55847`, base=main,
PR відкритий/mergeable. CI run43131852256 completed/success: обидва jobs
ubuntu-latest/windows-2022, locked sync, Ruff, pytest, import/Qt startup — success.
Раніше: Linux121 passed, Windows119 passed/2 POSIX skips; local native GUI47
і WSLg GUI75 passed. Новий документаційний HEAD проходить окремий CI перед merge.

**Owner-reported physical evidence:**
- WSLg: основні user/group operations; navigation/permissions Guest,
  Administrator, Instructor, Learner; roles/membership controls;
  persistence/logout; Standard Ukrainian input/shortcuts.
- Native Windows11: Ukrainian Enhanced input, keyboard shortcuts та правильне
  фізичне enforcement мінімального розміру вікна.

Це повідомлення власника, не physical tests агента. Повну DPI100/125/150/200%
та multi-monitor матрицю не заявлено як виконану. WSLg Enhanced mapping і
фізичний tiny-frame resize лишаються відомими environment limitations;
native Windows acceptance не означає виправлення Weston/WSLg.

План/acceptance record/README/ADR/diagnostics оновлюються узгоджено. Історію
власних ScenarioAttempt і learner result list/detail зафіксовано лише в
існуючому Phase9–10 scope (SRS §§3.9,8,12,23). Код, schema, dependencies,
SRS v3.0 та локальні demo/credentials/native workspace не змінюються.

GitHub MCP Actions доступний; окремий MCP combined-status endpoint повернув
403, app connector statuses=[] (Actions check-runs не є legacy statuses).
Read-only gh API використано для branch/check metadata: main protected=false;
rules endpoint повернув403 із вимогою GitHub Pro для цієї private repository
feature. Нічого не вимикали; обидва видимі CI jobs мають пройти на фінальному SHA.
Звичайний merge commit відповідає PR#1/#2, merge прив'язується до перевіреного
HEAD без force/admin bypass. Feature branches зберігаються; main синхронізується
лише fast-forward після merge. Фактичний merge SHA та фінальні CI доступні в PR#3.

**Phase 3 — Scenario Management: NOT STARTED.** Жодної реалізації наступної
фази не розпочато; acceptance/merge Phase2 не є її дозволом.

## 12.11.2026 — Phase 3: дозволений початок та перші інкременти

Власник явно дозволив Scenario Management, feature commit/push/PR до main.
Початкове дерево чисте; main і remote `5b15ff0…` підтверджено через GitHub MCP
та локальний fetch/fast-forward. PR#3 merged. Нова feature-гілка
`feat/phase-3-scenario-management`; не використано Phase2 branch.
План перед кодом подано власнику, traceability — у IMPLEMENTATION_PLAN.

Інкремент 1: Pydantic Scenario/ScenarioParameters, ScenarioService із ownership,
RBAC, serialized writes та optimistic revision check; scenarios і
scenario_versions у міграції 0002. Unique ID/автор/UTC identity відокремлено
від змінних параметрів версії. Published update/delete заборонені DB triggers;
fixture-перевірка fork не реалізує publishing. Поточний runtime створює
лише draft. Немає генерації, cloud calls, artifacts, scoring чи publication API.

Інкремент 2: ScenarioPage із двома scrollable вкладками та explicit save;
єдиний каталог, пошук, selected ID між Constructor/Analytics, read-only empty
state. Unsaved guard Save/Discard/Cancel, Cancel default, failed-save retention;
втрата сесії очищає редактор і каталог. Чужі записи Administrator читає через
readonly fields із доступними вкладками; Instructor не бачить їх навіть через
прямий service ID. Подробиці й оборотні ліміти — ADR-0003.

Додано тільки SRS-залежність Pydantic >=2.12.5,<3, lock **2.14.3** і її
транзитивні пакети. Наявні залежності зберегли версії. Context7 перевірив
офіційні API SQLAlchemy2, Pydantic2 та Qt QMessageBox Save/Discard/Cancel.
Джерела: https://docs.sqlalchemy.org/en/20/orm/versioning.html,
https://docs.pydantic.dev/latest/concepts/models/,
https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QMessageBox.html.
GitHub MCP branch/PR read успішні. OpenAI-specific docs не потрібні.

Sandbox не дозволяв запис .git/FETCH_HEAD та DNS PyPI; повторні дозволені
команди успішні. Усі runtime перевірки використовують нові тимчасові БД;
owner databases, credentials, Windows acceptance workspace та системні
налаштування не змінено. Ruff initial formatting/line-length помилки усунено.
Перший regression subset: 54 passed/199.32s; новий scenario suite ще виконується.
Результати фінальних перевірок та gate будуть записані нижче.

### Нові тести та проміжні виправлення harness

Додано 42 scenario-перевірки: 24 domain/service/database/security та 18 GUI.
Окремо `pytest tests/test_scenarios.py -q --tb=short` — 24 passed/17.48s;
`pytest tests/ui/test_scenarios_ui.py -q --tb=short --durations=5
-o faulthandler_timeout=30` — 18 passed/52.95s.

Перший спільний новий прогін перервано: pytest-qt закривав навмисно dirty
вікно до фіналізатора фікстури й відкривав справжній unsaved dialog. Це
усунуто `before_close_func` тільки для test cleanup. Тест самого діалогу
окремо перевіряє українські кнопки, Cancel default та реальний event loop.
Довгі повторні repolish у apply_theme також усунуто для нової фікстури:
ідентична тема не застосовується заново на кожному case. Runtime dirty guard
і production theme не послаблені. Додатково виявлено й виправлено
selection при Save з guard: catalog rebuild не інвалідує вибраний ID і
не повертає виділення на попередній рядок; є regression test.

Уточнення, поставлене власнику: SRS §2.3 дозволяє архівування, але не задає
його наслідків для чернеток/публікацій. Запропоновано окреме завдання після
узгодження правил; відповіді ще немає. Архівування не реалізовано й не
заявлено виконаним. Це залишається відкритим пунктом owner review.

### Перевірки пакування, запуску та GUI

Усі команди uv: `UV_CACHE_DIR=$PWD/.uv-cache`; runtime/tests після встановлення
залежностей — offline. Python3.12.3, PySide6/Qt6.10.3, Pydantic2.14.3,
SQLAlchemy2.0.57, Alembic1.20.1, pytest8.4.2, Ruff0.14.14.

| Команда | Результат |
|---|---|
| `uv sync --offline --locked` | 27 resolved, 26 checked, success |
| `uv run --offline --locked ruff check .` | All checks passed |
| `uv run --offline --locked ruff format --check .` | 47 files already formatted |
| `QT_QPA_PLATFORM=wayland uv run --offline --locked pytest tests/ui -q --tb=short` | **93 passed**, 266.97s, WSLg |
| `QT_QPA_PLATFORM=wayland QT_SCALE_FACTOR=1.5 uv run --offline --locked pytest tests/ui/test_scenarios_ui.py -k form_actions -q --tb=short` | **2 passed**, 16 deselected, 6.50s |
| Та сама команда з `QT_SCALE_FACTOR=2` | **2 passed**, 16 deselected, 6.23s |
| `uv build --offline` | wheel/sdist, success |
| ZipFile/tarfile inspection | scenarios modules і migration0002 у wheel; local data/cache/credentials відсутні |
| `QT_QPA_PLATFORM=offscreen uv run --offline --locked cyberforge --database /tmp/cyberforge-phase3-cli-smoke.sqlite3 --smoke-test` | exit0 |
| `QT_QPA_PLATFORM=offscreen uv run --offline --locked python -m cyberforge --database /tmp/cyberforge-phase3-module-smoke.sqlite3 --smoke-test` | exit0 |
| `QT_QPA_PLATFORM=wayland uv run --offline python /tmp/cyberforge_phase3_preview.py` | exit0, три знімки власного QWidget на temporary DB |
| `QT_QPA_PLATFORM=offscreen /tmp/cyberforge-phase3-wheel-review/bin/python -I -m cyberforge --database /tmp/cyberforge-phase3-wheel-smoke.sqlite3 --smoke-test` з cwd=/tmp | exit0, isolated installed wheel |
| `git diff --check`; diff SRS/AGENTS | success; SRS/AGENTS незмінні |

Ізольоване середовище створено через `uv venv --python .venv/bin/python
/tmp/cyberforge-phase3-wheel-review`. Перша offline wheel-install спроба
не знайшла cached wheel Pydantic-core; повтор із мережею та constraints,
згенерованими з uv.lock, успішний. Подальший isolated startup — без мережі.
Це інсталяційний доступ PyPI, не runtime cloud/LLM виклик.

Знімки WSLg: `docs/screenshots/phase-3-{constructor,advanced,analytics}.png`.
Оглянуто компактну форму 1100×720: внутрішнє прокручування й Save доступні,
вкладки показують поля, каталог має один ID в обох режимах, відсутні вигадані
оцінки. Native Windows11 перевірки Phase3 ще не виконано. Існуючі Phase2
Windows acceptance files/workspace збережено. Manual gate — PHASE_3_ACCEPTANCE.md.
MockLLMProvider ще не існує (Phase4); scenario/runtime тести не потребують
ключів, зовнішніх ресурсів або LLM. Повний Linux/CI результат — нижче.

### Фінальний локальний gate

`uv run --offline --locked pytest -q --tb=short` — **163 passed**, 335.36s.
Усі 121 попередні тести збережено; додано 42. Ruff lint/format47files та
повний WSLg GUI93passed успішні. Покрито create/validation/IDs/restart,
draft updates/conflicts/concurrent creates, ownership/RBAC/revocation,
immutable published fixture/fork, migrations/constraints, UI/shared ID,
read-only view, усі unsaved decisions та Session cleanup.

Phase3 переведено **IN PROGRESS → REVIEW**. Технічні локальні checks пройдені;
owner acceptance не надано, архівування потребує відповіді про межу,
Windows11 Phase3 manual gate відкритий. Ні ACCEPTED, ні merge не виконано.
Phase4 NOT STARTED. Git/PR/CI delivery evidence буде дописано після публікації.

### Git/PR delivery — Phase 3 REVIEW

Implementation commit `a94a00d9ecf8547c40e50f391a86c0ba44c3fd8b` відправлено
звичайним push у `origin/feat/phase-3-scenario-management`. GitHub MCP створив
[PR#4](https://github.com/the1llus1on/cyberforge/pull/4) до main; PR open,
не draft, не merged. Base main залишається `5b15ff0…` (merge PR#3), scope21files.
Дерево чисте, локальна й remote feature-гілки синхронні перед цим
документаційним записом. SRS, user data і Phase2 branches не змінено.

GitHub MCP branch/PR read та PR creation успішні. Combined-status endpoint
основного MCP повернув403 через scope PAT; fallback — підключений GitHub app
MCP `fetch_commit_workflow_runs`, який підтвердив run43171462386 Python checks,
in_progress на момент запису (Linux/Windows matrix). Це не success і не
native Windows11 acceptance. Credentials не читали/не змінювали. Фінальний
стан CI після документаційного push доступний у
[PR checks](https://github.com/the1llus1on/cyberforge/pull/4/checks) та буде
повідомлено власнику окремо. Merge не виконано, Phase4 не починалася.

## 12.11.2026 — Phase3 pre-acceptance remediation F-01–F-03

Власник явно погодив archive/restore в Phase3 та всі findings. Це замінює
попереднє відкрите scope question; Phase3 лишається REVIEW. GitHub MCP:
PR#4 open/unmerged, baseline7d2084d, base main5b15ff0, scope21files; local tree
clean/same branch. Прочитано SRS/AGENTS/plan/log/ADR/acceptance/code/PR diff.
План перед реалізацією подано з traceability до §§2–4,11,14,16–17,21–23.

F01/F02: адитивна0003 додає archived_at/archive_revision; immutable identity
trigger звужено до id/owner/created_at. Archive/restore — транзакційні,
owner-only, read archived для owner/admin, edits blocked; усі version rows
збережено. Counter захищає старі форми після archive→restore. Published
snapshot guard не послаблено; DB guards блокують також writes до archived
версій. Ізольовані тести upgrade з0002 перевіряють raw snapshots і table
rootpage, fresh/0001 path лишається під regression. Міграцію0002 не редаговано.

F03: офіційні NIST PDF/metadata перевірено через web; DOI redirect був
недоступний у web, прямі nvlpubs.nist.gov PDF і nist.gov publication page
успішні. Table1 p6 та AppendixB підтверджують23 cues/5 types; IDs — AppendixB
section references, catalog namespace nist-tn-2276:2023. Оригінальні англійські
назви збережено, українські labels власні. Unknown/duplicate IDs відхиляються.
Desired selection окрема від legacy strings/custom tactics, не означає
AI-declared/verified presence чи detection calculation. Read adapter не
змінює stored JSON; legacy text зберігається після Save і під час fork.
Джерела, алгоритм і обмеження — ADR0003. Context7 перевірив офіційні
Alembic add_column (без batch recreation) та Pydantic enum validation APIs.
Нових залежностей не додано.

UI: один каталог + archive filter, explicit confirmation/restore; read-only
архівний/чужий контент зі scrolling/copy. Зовнішня зміна archive state не
стирає dirty recovery buffer. «Скасувати зміни» — явне discard confirmation,
без Save у цьому діалозі. Усі інші переходи зберігають Save/Discard/Cancel.

Проміжні результати: 36passed/37.08s service+migrations; 18passed/30.52s
початковий archive suite; combined scenario/archive/NIST/GUI67passed/107.01s.
Після цього додано expanded UI, restore rollback/deactivation/direct SQL
негативні випадки. Final full suites/package/CI будуть наведені нижче.

### Фінальні докази remediation

Команди uv виконано з `UV_CACHE_DIR=$PWD/.uv-cache`. Усі baseline runtime
тести offline, без LLM/ключів або зовнішніх ресурсів. Нових dependencies
немає. Native Windows11 physical acceptance цього remediation не виконано.

| Команда / перевірка | Результат |
|---|---|
| `uv sync --offline --locked` | success,27resolved/26checked |
| `uv run --offline --locked ruff check .` | success |
| `uv run --offline --locked ruff format --check .` |52files formatted |
| `uv run --offline --locked pytest -q --tb=short` | **208passed**,450.19s |
| `uv run --offline --locked pytest tests/test_scenario_archiving.py tests/test_nist_cues.py -q --tb=short` | **29passed**,44.33s |
| `uv run --offline --locked pytest tests/test_nist_cues.py -q --tb=short` після safe stored-data read/update guard | **8passed**,8.30s |
| `QT_QPA_PLATFORM=wayland uv run --offline --locked pytest tests/ui -q --tb=short` | **109passed**,339.44s |
| `QT_QPA_PLATFORM=wayland QT_SCALE_FACTOR=1.5 uv run --offline --locked pytest tests/ui/test_scenarios_ui.py -k 'form_actions or cue_selector_keyboard' -q --tb=short` | **3passed**,31deselected,8.71s |
| Та сама команда з `QT_SCALE_FACTOR=2` | **3passed**,31deselected,8.85s |
| `uv build --offline` | success,wheel/sdist |
| `uv pip install --offline --reinstall-package cyberforge --python /tmp/cyberforge-phase3-wheel-review/bin/python --no-deps dist/cyberforge-0.1.0-py3-none-any.whl` |success,final package installed |
| `QT_QPA_PLATFORM=offscreen uv run --offline --locked cyberforge --database /tmp/cyberforge-phase3-remediation-cli.sqlite3 --smoke-test` |exit0 |
| `QT_QPA_PLATFORM=offscreen uv run --offline --locked python -m cyberforge --database /tmp/cyberforge-phase3-remediation-module.sqlite3 --smoke-test` |exit0 |
| `QT_QPA_PLATFORM=offscreen /tmp/cyberforge-phase3-wheel-review/bin/python -I -m cyberforge --database /tmp/cyberforge-phase3-remediation-wheel-final.sqlite3 --smoke-test`,cwd=/tmp |exit0 |
| Isolated wheel `python -I` management smoke: packaged migration→create B.4.4→archive→restore |success,stableID/revision/cue |
| wheel/sdist inspection |newcatalog/selector/migration0003 packaged; no localDB/credentials/cache |
| `git diff --check`; diff SRS/AGENTS/0002 |success; all three unchanged |

Перший запит дозволу на WSLg timeout-нув в automatic approval review до
запуску процесу. Один дозволений повтор успішний; це не залишковий blocker.
Знімки `phase-3-remediation-{cues,archive,analytics}.png` отримано на справжньому
WSLg через QWidget.grab лише власного вікна, temporary synthetic DB. Оглянуто
1100×720: cue list/вкладки scroll, archive marker/filter/restore видимі,
identity між режимами спільна. Це не physical Windows11/DPI evidence.

F01/F02/F03 закриті реалізацією й локальними тестами. Додатково safe error
для непідтримуваного збереженого каталогу не змінює дані. Збережено всі163
попередні тести, додано45. Scope question архівування погоджено власником;
нових продуктових рішень, що потребують owner approval, немає. Legacy
mapping навмисно ручний, downgrade після archive history заборонений для
захисту даних. Phase3 **REVIEW**, не ACCEPTED; Phase4 NOT STARTED.

GitHub MCP використовується для PR4 read/update і final CI. Commit/push
виконуються в поточну feature-гілку після scoped diff review. Final pushed
SHA/CI run/обидва jobs будуть перевірені й наведені у PR description та
фінальному звіті; саме посилання на checks не зараховується як success.

## 12.11.2026 — Phase3: neutral Constructor і workflow refinement

Власник повідомив про часткові manual WSLg перевірки й уточнив empty-state
поведінку. GitHub MCP підтвердив PR4 open/unmerged/head d507f45; local clean,
same feature branch. Переглянуто тільки relevant ScenarioPage/shell/tests,
SRS §§3.5–3.8/4.2/21.3/23–24 та ADR/policy; owner credentials/DB не читали.

Мінімальна зміна: existing form поміщена в editor container поряд із neutral
empty card у QStackedWidget. Logical states: inactive/no selection; active
new/no ID після явного New; active existing після selection/Save. _changed
обирає екран, без service writes. _show_scenario очищає form при вході до
Constructor без valid selected ID; повторний «+» та valid mode roundtrip
зберігають вибір/архівний фільтр. Dirty guards і RBAC/archive services незмінні.
Context7 підтвердив official QStackedWidget API. Focused new cases6passed,
34deselected,15.17s; final full suite/WSLg виконується після стабілізації.

Власник погодив Phases3–11 manual WSLg acceptance із routine physical native
Windows11 deferral до Phase12. Early native checks — concrete platform defect
або significant risk; existing Phase2 Windows workspace зберігається без refresh.
Linux/Windows CI обов’язкові; Windows CI не physical Windows11. Це acknowledged
risk, не claim виконання native вимоги. SRS §24 Windows11 MVP criterion чинний,
§23 Phase12 Windows-build/finalization gate його покриє; конфлікту не виявлено,
SRS не змінено. Phase12 включатиме packaging/executable/installer/DPI/keyboard/
permissions/security/regression/end-to-end verification. Policy синхронізовано
в AGENTS, плані, ADR0003 та PHASE3_ACCEPTANCE; старі результати історичні.

Workflow: relevant context → focused checks → stable full pytest/Ruff → relevant
real WSLg → push/обидва final CI jobs. Не прибирати existing security/regressions,
не пропускати integrity/RBAC/migration/concurrency. Build/wheel не повторюються:
тільки UI/policy, без package/dependency/migration/startup/install змін. Немає
нових screenshots/reports у Git; один temporary QWidget preview для visual
inspection допустимий. Final evidence/CI — нижче, Phase3 REVIEW без merge/Phase4.

Проміжний WSLg run Constructor:39passed/1failed,149.41s. Existing regression
виявив footer Save нижче viewport при1100×720 після додавання stack. Причина:
preferred height editor у QStackedWidget замість попередньої minimumHeightForWidth.
ScenarioPage.heightForWidth тепер використовує minimum layout активного content;
виправлено без нового abstraction і без послаблення тесту. Focused layout/empty:
4passed/36deselected,8.67s. Попередній full run перервано до завершення (не pass);
повторний full обґрунтований цією UI code change. WSLg повтор focused layout/
state/readonly subset, а не всіх unrelated/manual checks. Final results — нижче.

Фінальна стабільна перевірка (UV_CACHE_DIR=.uv-cache):
- `uv run --offline --locked ruff check .` — success.
- `uv run --offline --locked ruff format --check .` —52files formatted.
- `uv run --offline --locked pytest -q --tb=short` — **214passed**,460.94s;
  усі208 попередні тести збережено, додано6 focused GUI cases.
- `QT_QPA_PLATFORM=wayland uv run --offline --locked pytest tests/ui/test_scenarios_ui.py -k 'empty_state or explicit_new or selected_mode or unselected_new or invalid_selection or form_actions or archived_foreign' -q --tb=short`
  — **9passed**,31deselected,26.75s; реальний WSLg після layout fix.
- `/tmp/cyberforge-phase3-empty-preview.py`,backendWayland — visual inspection
  одного temporary QWidget capture1100×720: centered neutral card, no editor/actions,
  каталог/New доступні. Нових screenshots/diagnostics files у Git немає.
- `git diff --check` — success. SRS/backend/persistence/dependencies/install
  не змінено; owner .local DB/credentials/native Windows workspace не чіпали.
  Build/wheel свідомо не повторено за погодженою UI-only policy.

Змінено8файлів: ScenarioPage, shell, existing GUI test module, AGENTS, plan,
цей log, PHASE3_ACCEPTANCE, ADR0003. PR4 оновлюється у тій самій гілці;
фінальний HEAD/обидва Linux-Windows CI jobs перевіряються після push, actual
run/results фіксуються в PR description і final report без зайвого doc-only
commit/повторного CI циклу. Phase3 REVIEW; ні merge, ні Phase4 не виконуються.


## 12.11.2026 — Phase3: остаточне прийняття та дозвіл merge

Власник явно прийняв Scenario Management: **REVIEW → ACCEPTED**,12.11.2026.
Дозволено лише documentation-only фіналізацію поточної branch, push і PR4
merge після перевірки exact final HEAD та обох CI jobs. Phase4 NOT STARTED.
Початковий стан: clean feat/phase-3-scenario-management; GitHub MCP підтвердив
PR4 open/unmerged/clean, base main5b15ff0, HEAD3b31210d8678738f677d8effce9130a7002d6e12.
CI43296448273 completed/success: Linux214passed, Windows212passed/2POSIX skips;
locked sync/Ruff/pytest/import/Qt startup success на обох OS. Локальний source
цього HEAD:214passed, final relevant WSLg9passed. Наявна Git історія PR3
підтвердила звичайний merge commit; майбутній merge прив’язується до final SHA.

Owner-reported evidence: часткова ручна WSLg перевірка й схвалення результатів;
власник підтвердив реалізацію create/validation/edit/persistence/versioning,
ownership/service RBAC, archive/restore/concurrency, NIST selector/legacy,
Constructor empty state, закриття F01–F03 і незалежне review. Це не твердження
агента про виконання всіх manual scenarios. Checklist залишається reference;
непідтверджені boxes не заповнюються.

Routine physical native Windows11 verification Phases3–11 deferred to Phase12
за погодженою політикою. Це acknowledged risk, не completed verification;
Windows Server2022/offscreen CI не замінює Windows11 desktop/DPI/input/ACL/
security/package/E2E evidence. Phase2 native workspace/owner data зберігаються.
SRS v3.0, runtime, dependencies, migrations і tests не змінюються. README,
plan, acceptance record та ADR синхронізуються зі статусом ACCEPTED.

Новий documentation-only diff перевіряється git diff --check і scoped diff;
локальні повні тести/build/wheel не повторюються без code changes. Фінальний
PR HEAD обов’язково проходить Linux/Windows CI перед merge. CI failure,
конфлікт або неочікуваний HEAD зупинить merge без bypass/force. Після merge:
fetch → switch main → merge --ff-only origin/main, перевірка SHA/clean tree;
feature branch не видаляється. Merge SHA та actual final CI — PR4/final report.
# 13.11.2026 — Phase 4: початковий незалежний increment

Власник явно дозволив Phase 4 LLM Integration. Перед кодом перевірено AGENTS,
SRS §§10–11/23, релевантні plan/log/ADRs, структуру source/tests, dependencies,
clean working tree та ignored `.env`. GitHub MCP підтвердив Phase 3 merge
d0b407cbb13cf9e10f5bd65904eef978c321ab7e. Fetch + ff-only check: main already
up to date. Створено `feat/phase-4-llm-integration`. Owner DB/credentials/.env
і Phase 2 native Windows environment не змінювалися.

Подано план: §§10.4/10.7/10.8/11.1 — contracts/config/mock/telemetry;
§§10.1–10.5 — provider adapters/retries/quotas/fallback; §23 — diagnostics,
verification і PR REVIEW. Context7 функціонально відповів для Google SDK/Groq;
офіційні web docs і source перевірено, findings/links у ADR-0004.

Виявлено material conflict: §10.2 вимагає `langchain-google-genai`, але його
ChatGoogleGenerativeAI використовує generateContent. Водночас Interactions
GA/recommended і `store=false` затверджені власником для нового адаптера.
Надіслано запит погодити direct google-genai + provider-neutral LangChain
Runnable. **Рішення ще не отримано.** Точний proposed SRS текст у ADR-0004;
сам SRS не змінено. Спірні GeminiProvider/Runnable не реалізовано до рішення.

Незалежна частина: provider-neutral Pydantic contracts/errors/versioned content
slots; safe explicit dotenv loading; deterministic offline mock; gateway із
selection validation, bounded backoff/jitter/Retry-After, quota reservations,
optional Gemini→Groq fallback лише timeout/selected 5xx; Groq SDK adapter і
bounded strict-schema checker; privacy-safe telemetry та best-effort sink.
AUTO, durable generation persistence, full artifact workflows/agents/UI — deferred.
Config/model allowlist не підтверджує account access. Дані й обмеження schema
subset, in-memory quota scope, synchronous worker requirement — ADR-0004.

Додано SDK google-genai 2.34.0, groq 1.7.0, langchain-core 1.8.0,
python-dotenv 1.2.4; актуалізовано pyproject/uv.lock, .env.example і README.
Внутрішні retry/continuation особливості SDK інспектовано без реальних keys.

Перевірки незалежного increment (UV_CACHE_DIR=/tmp/cyberforge-uv-cache):

- `uv run --offline ruff check .` — success.
- `uv run --offline ruff format --check .` — success, 63 files.
- `uv run --offline pytest tests/test_llm_gateway.py tests/test_llm_groq.py -q --tb=short`
  — **51 passed**. Реальний Groq SDK тестується тільки через httpx.MockTransport;
  fake clocks/sleep використовуються для retry і budget tests. Спочатку 38
  gateway tests, потім 50 з Groq, після sink regression — 51.

Live Gemini/Groq requests не виконувалися; доступ до моделей/квоти account не
підтверджено. Повний pytest, package/isolated-wheel/startup checks та Linux/
Windows CI залишаються обов'язковими після завершення реалізації перед push/PR.
Жодного commit/push/PR/merge не виконано. UI не змінювався; WSLg acceptance
instructions будуть із завершеною фазою. Native Windows11 — Phase12 deferral,
не verified evidence. Phase4 **IN PROGRESS**, gate не пройдено; Phase5 не почато.


## 13.11.2026 — Phase 4: погоджена архітектура і завершення реалізації

Власник явно погодив direct google-genai Interactions та provider-neutral
LangChain Runnable і дозволив точну вузьку зміну SRS §10.2. Це замінює
pending decision попереднього increment. ADR-0004 — ACCEPTED як архітектурне
рішення; сама реалізація Phase4 — **REVIEW**, не ACCEPTED.

Реалізовано GeminiProvider (Interactions v1, store/background/stream=False,
automatic_continuation=False, text/JSON Schema, thinking per model, usage і
normalized errors); functional GatewayRunnable (invoke/ainvoke, batch/abatch,
whole-result stream/astream); lazy factory/config defaults; guarded CLI
cyberforge-llm-check. Немає generateContent adapter, duplicate policy layer,
LangGraph agents, UI generation чи domain/persistence modifications.
SRS byte comparison підтвердив незмінність усього поза §10.2, включно з CRLF.

Офіційні джерела/альтернативи/наслідки — ADR-0004. Google SDK pinned2.34.0
через перевірену особливість retry translation: attempts=0→1→extra retry.
Generated Interactions retry strategy явно none; відсутність config fail-closed.
Real SDK/fake HTTP тести доводять single request на failures і disabled continuation.
Groq1.7.0, LangChain Core1.8.0, python-dotenv1.2.4; SDK types лише в adapters.

Фінальні security/reliability corrections: DEBUG SDK payload/exception logs
фільтруються context-local під час generation; Retry-After створює provider-wide
cooldown між моделями/requests; Retry-After залишається у normalized failure;
input + serialized schema + output reservation враховуються у локальних квотах;
unknown quota keys/non-JSON Pydantic schemas fail before transport. Telemetry
не експортує content/keys, invalid model strings redacted; unknown usage=None.
Сам synthetic flag не є PII detector; future domain validation обов'язкова.

Перевірки (UV_CACHE_DIR=/tmp/cyberforge-uv-cache):

| Команда / перевірка | Результат |
| --- | --- |
| uv run --offline --locked ruff check . | success |
| uv run --offline --locked ruff format --check . | success,72files |
| uv run --offline pytest tests/test_llm_gateway.py tests/test_llm_gemini.py tests/test_llm_groq.py tests/test_llm_runnable.py tests/test_llm_diagnostics.py tests/test_llm_integration.py -q --tb=short | **100passed,5.30s** |
| GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false uv run --offline --locked pytest -q --tb=short | **314passed,341.67s**; усі214 Phase0–3 tests збережено |
| uv build --offline --out-dir /tmp/cyberforge-phase4-dist | sdist + wheel success, final code |
| uv export --offline --locked --no-dev --no-emit-project --format requirements-txt та uv pip install --require-hashes у /tmp/cyberforge-phase4-wheel-env |53 exact runtime dependencies + installed wheel; success |
| isolated wheel python -I з /tmp: import path, mock structured invoke/ainvoke, disabled-live exit2, archive privacy | success |
| isolated wheel cyberforge --database /tmp/cyberforge-phase4-final-wheel-smoke.sqlite3 --smoke-test,QT_QPA_PLATFORM=offscreen | success |
| QT_QPA_PLATFORM=wayland uv run --offline --locked cyberforge --database /tmp/cyberforge-phase4-wslg-smoke.sqlite3 --smoke-test | real WSLg startup/close success; appearance не інспектувалася |
| git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --check | success; збережено original SRS CRLF |
| working diff29files + local API-value scan | success; значення не виводились; .env ignored; accepted service/domain/persistence/UI unchanged |

Перші SDK tests виявили retry/continuation-warning issues, виправлені до final
focused100. Два проміжні full runs перервано під час privacy/quota review;
вони не зараховуються як success (Qt interrupt diagnostics також не є final
regression result). Async executor tests у sandbox зависали на event-loop wakeup;
поза sandbox100focused і314full пройшли. Live network до провайдерів не було:
тільки mock/fake HTTP; install network використовувалася лише для PyPI packages.
Початкова offline isolated install не знайшла uncached wheels; exact hashed
runtime dependencies отримано з PyPI, final wheel reinstall виконано offline.

Live diagnostic реалізовано, але **НЕ запускалося**: поточна інструкція
власника вимагає окремого дозволу на API quota execution. Доступ до approved
models і account-specific quotas не підтверджено. Інші remaining risks:
SDK-specific retry config під pinned version; in-memory quota scope, bounded
Groq schema subset, external future workflow tracing, native Windows11 Phase12.
Durable telemetry/quota records і experiments відкладено. Phase5 не розпочато.

Підготовлено docs/PHASE_4_ACCEPTANCE.md; owner manual acceptance pending.
Після final diff/staged secret verification — commit/push і PR→main, без merge.
Linux/Windows CI exact final HEAD обов'язково перевіряються після публікації;
actual SHA/run/results будуть у PR description і final report без зайвого
code-free commit/повтору CI. Наявні .env, credentials, DB і Phase2 native
Windows environment збережено. Відсутність live tests не позначається success.


## 13.11.2026 — Phase4 independent review remediation F-01/F-02

Власник дозволив вузькі fixes у тій самій branch feat/phase-4-llm-integration,
PR5, reviewed HEAD5913183500bbaa03bee4d800a5f7fdedf02661de. Початкове дерево
чисте; GitHub MCP підтвердив open/unmerged PR→main з тим самим HEAD.
Phase4 лишається REVIEW, не ACCEPTED. План перед кодом — SRS §§10.4–10.8/11.1:
parameter compatibility + observability, bounded schema projection + original
local validator, focused tests → один stable full Ruff/pytest → final-head CI.

Обидва findings підтверджено до fixes: нові3 focused tests очікувано FAILED
(configuration для FlashLite minimal fallback, unsupported_schema для обох
EmailArtifactV1/WebArtifactV1). Actual model_json_schema містить pattern
^[a-zA-Z0-9_-]{1,64}$ у $defs.ScenarioContextV1.properties.internal_resource_id.
Official Groq docs/SDK через Context7 підтвердили GPT-OSS low/medium/high та
strict schema contract; source links, alternatives і consequences — ADR0004.

F-01: тільки enabled allowlisted transient Gemini→Groq fallback maps minimal
до explicit low; low/medium/high/None зберігаються. Temperature/output limit/
timeout не змінюються. Original request і params immutable; telemetry додає
requested_parameters/effective_parameters. Invalid original config не ремонтується.
Safety/auth/credentials/schema/validation/quota/rate-limit/permanent errors
не обходять existing denylist. Retries, budgets і cooldown logic не змінені.

F-02: canonical models і regex незмінені. Тільки gateway, який має original
output_type та mandatory local validation, застосовує explicit Groq V1-artifact
projection. У копії лише exact known resource-ID pattern делегується локально;
provider strict checker зберігає types/required/closed objects/version enum.
Інші patterns/constraints і changed expected regex fail-closed. Raw adapter
не отримує автоматичного lossy transformer. Schema projection позначено в
telemetry, зокрема errors. Original Pydantic strict validation завжди відхиляє
invalid ID до повернення result. Provider compliance не є content safety,
consistency або instructor approval. Agents/constructors не реалізовувалися.

Перевірки (UV_CACHE_DIR=/tmp/cyberforge-uv-cache):

| Команда | Результат |
| --- | --- |
| uv run --offline --locked pytest tests/test_llm_review.py -q --tb=short | до fix3failed (reproduction); після fix92passed,0.73s |
| uv run --offline --locked pytest tests/test_llm*.py -q --tb=short |192passed,3.74s; попередні100 LLM tests збережено |
| uv run --offline --locked ruff check . | success |
| uv run --offline --locked ruff format --check . | success,73files |
| GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false uv run --offline --locked pytest -q --tb=short | **406passed,203.92s**; усі prior314 tests збережено |
| git diff --check | success |

Focused matrix: усі9 valid Gemini model/thinking combinations × timeout/5xx;
10 denied categories ×2canonical artifacts; disabled fallback/invalid thinking;
actual schema snapshots/non-mutation/fail-closed projection; real Groq SDK на
httpx.MockTransport direct та fallback; valid ID boundaries, empty/overlong/
path/URL/space/non-ASCII/newline/non-string ID і local validation failures.
Фінальний full suite виконано один раз після стабілізації. Async/full checks
поза sandbox для раніше встановленого event-loop wakeup limitation; requests
лише fake/offline. Live API не виконувалися, model access/quotas досі unknown.

Змінено8files: contracts/gateway/schemas, новий test_llm_review.py, ADR0004,
plan/log/acceptance. SRS, dependencies/uv.lock, packaging/startup, migrations,
UI та accepted application/domain services не змінено; wheel/WSLg повтори
не потрібні за погодженим workflow. .env/credentials/DB/Phase2 Windows workspace
збережено. Native Windows11 physical acceptance — Phase12, не CI evidence.

Перед commit/push — final diff/staged secret-value scan. Linux/Windows CI
перевіряються для exact нового PR HEAD; SHA/run/results будуть у PR description
та final report без зайвого documentation-only CI циклу. Owner acceptance
очікується; ні merge PR5, ні Phase5 не дозволені цим remediation.


## 13.11.2026 — Groq primary / Hydrogen backup candidate

Власник явно погодив нову operational policy та narrow SRS clarification.
Baseline32e6de1090d819c06fa7d1bd2e79100eef0af501, чиста existing feature branch,
PR5 open/unmerged→main підтверджено GitHub MCP. Phase4 лишається REVIEW.
План перед кодом: §§10.2–10.8/11.1 — Hydrogen catalog/capabilities і model-specific
request config, explicit verified backup через existing retry/fallback loop,
neutral telemetry/validation; §21 — focused then one stable full Ruff/pytest,
final-head Linux/Windows CI; owner-only first Hydrogen live test після review.

Нова primary policy: Groq/openai/gpt-oss-120b; preferred backup candidate
Gemini/gemini-4-hydrogen після owner verification+enable. Lite3.5 optional;
Flash3.8 unresolved. Mock лишається default без explicit cloud config.
Actual .env не редагувалася; рекомендовані несекретні поля в .env.example/README.
Попередній Gemini-primary вибір superseded, історичні acceptance/evidence збережено.

Використано4 official Google links власника, Developer API Interactions v1
reference, AI Studio thinking/structured outputs/rate limits docs і installed
SDK source. Blog прямо підтверджує AI Studio/Gemini API applicability. v1
reference має model ID; structured guide показує Hydrogen response_format.
Деякі individual AI Studio model pages web tool не відкрив; заміна — official
API reference/feature guides, не сторонні джерела. Context7 index повертав
legacy examples; direct installed SDK + fake transport доводять serialization.
Cloud long-decode v1beta1 restriction не застосовується до обраного bounded
Developer API v1 mode. Джерела/деталі/наслідки — ADR0004.

GeminiProvider той самий: Hydrogen low/medium/high/xhigh, minimal denied;
xhigh rejected для інших approved models. Temperature/top_p/top_k не
передаються Hydrogen; original requested temperature збережена, effective=None
означає omission. Older Gemini formats збережено. SDK pinned2.34.0 уже сумісний;
ніякої dependency/lock зміни. store/background/continuation off, timeout bounded,
retry compatibility safeguard strategy=none та privacy filter збережені.

BackupConfig provider/model/enabled/access_verified — explicit optional config;
обидва flags default false, enabled без verification fail-closed. Owner attests
access для поточного ключа; config не робить live verification сам. Route лише
для configured cloud primary; mock/mismatched request не переадресовується.
Single hop/один existing execution loop; per-provider/model limits незалежні,
allowlisted transient errors only, denylist/cooldowns незмінні. Legacy
fallback_to_groq/env FALLBACK збережено deprecated; simultaneous new BACKUP +
legacy=true reject ambiguous config. Unsupported minimal→low/xhigh→high mapping
явні; original params immutable. Після Groq→Hydrogen schema projection reset,
full canonical schema/local strict validation збережені (F-01/F-02 regressions).
Telemetry має requested_provider і effective_model разом із prior metadata.

CLI приймає Hydrogen лише з --live; low/256tokens/20s, retries0, legacyfalse,
backupNone, single synchronous request без background/continuation. Command
підготовлена та offline tested, але **НЕ запускалася проти Google**. Current
scope забороняє додаткову API quota. Перший Hydrogen test виконує власник після
review; до success backup лишається disabled/unverified. Старе allowlist
rejection було local, не provider response. Published availability не означає
owner access. Попередні bounded3live calls на32e6de1 зафіксовані в ADR: Groq/Lite
success, Flash3.8unavailable; другий Flash unavailable — owner-reported.

Перевірки (UV_CACHE_DIR=/tmp/cyberforge-uv-cache):

| Команда / перевірка | Результат |
| --- | --- |
| uv run --offline --locked pytest tests/test_llm_hydrogen.py -q --tb=short | incremental49/58cases passed; final61cases у combined run |
| uv run --offline --locked pytest tests/test_llm*.py -q --tb=short | **253passed,4.49s**, prior192 preserved +61new |
| uv run --offline --locked ruff check . | success |
| uv run --offline --locked ruff format --check . | success,74files |
| GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false uv run --offline --locked pytest -q --tb=short | **467passed,232.84s**, усі prior406 preserved, один stable full run |
| SRS narrow byte-scope review | header/§10.5/criterion23/conclusion only, surrounding CRLF preserved |
| git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --check | success; header hard breaks represented without trailing spaces |

Matrix: real google-genai2.34 fake HTTP for4thinking×text/schema, xhigh
serialization, v1 endpoint/privacy/usage, single request on401/403/429/503,
no continuation; exclusive thinking rejects; offline default/Groq config;
verification gate/disabled states/legacy conflict/cycle prevention;2transient
categories×4Groq thinking settings; all10denied errors; independent budgets,
missing keys, bounded retries with fake clock; valid/invalid canonical artifacts
across fallback, no fallback for invalid primary data/schema; telemetry/redaction;
Hydrogen CLI --live guard and mocked success/errors. Ніяких live API у тестах/CI.

Packaging/entrypoints/dependencies/install/startup/migrations/UI не зачеплено:
build/isolated-wheel та unrelated WSLg не повторено за AGENTS policy. CI виконує
locked install/import/Qt startup на обох OS. Native Windows11 acceptance лишається
Phase12 risk, не completed evidence. Domain/RBAC/scoring/user data/native Phase2
workspace не змінювалися. Remaining risks: Hydrogen actual access/quotas unknown,
pinned SDK retry compatibility point, in-memory counters, future full artifact
safety/consistency/approval workflows. Backup ніколи не активується сам.

Перед commit/push — scoped diff і staged secret-value scan; final SHA/CI run
будуть у PR5 та final report після обох jobs без redundant doc-only CI cycle.
Ні merge/ACCEPTED, ні Phase5 не дозволені. Owner acceptance instructions оновлено.


## 2026-11-13 — Phase4 остаточно ACCEPTED власником; PR5 merge дозволено

Власник явно прийняв Phase4 LLM Integration: **REVIEW → ACCEPTED**,2026-11-13.
Це рішення замінює попередні pending/REVIEW записи. Прийнято gateway, Gemini
Interactions/Groq/Mock, LangChain Runnable, structured/Pydantic validation,
model/thinking config, bounded timeout/retry/rates/fallback, privacy telemetry/
secrets, verified Hydrogen backup configuration та F-01/F-02. Підтверджено
independent architectural/code reviews. Phase5 **NOT STARTED**, окремий дозвіл.

Початкові перевірки: clean feat/phase-4-llm-integration; local HEAD та GitHub
MCP PR5 HEAD98a019ce99df992c7ad54bc4f4a49ca02f6516b2 збігаються; PR open/unmerged/
clean, base main d0b407cbb13cf9e10f5bd65904eef978c321ab7e. Workflow43391679188
completed/success: Linux467passed, Windows465passed/2skipped; locked sync,
Ruff lint/format, pytest, package import і Qt startup success на обох OS.
Власник також повідомив Hydrogen focused offline acceptance61passed.

Новий live evidence — **owner-run/owner-reported**, не agent повтор:
`uv run cyberforge-llm-check --live --provider gemini --model gemini-4-hydrogen`
→ success, elapsed5.148s, input39/output5/reasoning25. Groq120B та Gemini3.5Lite
live connectivity SUCCESS підтверджено. Контент/ключі/private account data не
зберігаються. Agent не виконує жодного нового API call.

Approved policy: Groq/openai/gpt-oss-120b primary cloud;
Gemini/gemini-4-hydrogen preferred verified backup. Existing controlled policy
можна enabled при explicit local env configuration; actual .env/keys/config
flags у цьому documentation-only step не змінюються. Без explicit cloud config
Mock offline default, startup/ordinary tests не використовують cloud API.

Прийняті власником residual risks: Gemini3.8 availability unresolved; live
complex Email/Web Structured Outputs unverified; account-wide quotas не
встановлено; rate counters process-local; production workflows next phases;
manual GUI checklist not fully executed; physical native Windows11 deferred
Phase12. Не робиться припущень про повну manual acceptance чи всі native gates.
Owner approval явно визнає ці обмеження такими, що не блокують Phase4.

Scope: тільки acceptance documentation — plan/log/PHASE4 record/ADR, README
і AGENTS policy wording. Code/dependencies/migrations/SRS/.env/API keys/DB/
Windows workspace не змінюються. Локальний full pytest, packaging і manual GUI
не повторюються без code changes. Scoped diff і secret checks перед commit.

Власник явно дозволив documentation commit/push у наявну branch і **ordinary
merge commit** PR5 після successful Linux/Windows CI exact FINAL PR HEAD.
Після push checks очікуються без bypass; failure/pending/conflict/unexpected
HEAD або base зупинить merge. Merge pin до verified expected_head_sha.
Після merge: fetch origin → switch main → merge --ff-only origin/main;
перевірка equal SHAs/merge parents/clean tree, feature branch зберігається.
Actual final HEAD/CI run/merge SHA і sync evidence — PR5/final report без
circular doc commit. Phase5 не починати. Ніякого force/reset/clean/reseed.


## 13.11.2026 — Phase 5 Specialized Agents

Власник явно дозволив Phase 5 після прийнятої Phase 4. Baseline main
`6683f6e2569de05c57995eb5f7b1b3f6f603cce7` підтверджено GitHub MCP; clean
working tree, fetch/ff-only synchronization і гілка
`feat/phase-5-specialized-agents`. .env/ключі/local SQLite/user files та native
Windows acceptance environment не змінювалися. SRS збережено без змін.

Перед coding представлено план SRS §§5–6,9–13,23,26.1: four typed specialists,
existing scenario/gateway reuse, minimal LangGraph, independent validation,
offline tests, packaging і exact-head CI. Офіційні LangGraph overview/Context7
підтвердили StateGraph/conditional edges/compile(checkpointer=False)/recursion_limit.
NIST TN2276 official page підтверджує email detection difficulty boundary.

Реалізовано `agents/{contracts,prompts,workflow,specialized,demo}.py` та exports.
Email/Web slots композиційно доповнюють canonical V1 artifacts у draft V2,
не створюють нової Scenario entity/repository. Input revalidation/deep copy,
scenario/version/parameters/context/internal-resource/template gates, synthetic
.invalid addresses, bounded text/arrays, no markup/executable slots/commands.
Selected NIST IDs copied from existing catalog; claims перевіряються як subset,
verified cues порожні з explicit instructor-review requirement. Повна semantic
cue detection та publishing readiness — не Phase 5.

Mentor/Assistant використовують model-selected supplied fact IDs і дозволені
topics; deterministic composer повертає trusted explanations/defensive behavior
та curated recommendations. Немає довільного generated prose для score/metrics/
psychological claims. Supplied result/aggregate copied unchanged, missing,
incomplete, actual0 і correctly_skipped Web розрізняються. Розширення facts і
catalog можливе наступними фазами; caller відповідає за sanitized synthetic
inputs, походження фактів та application RBAC. Agents не читають/пишуть БД.

ADR-0005 пояснює consequential grounded-output design і explicit wire/local
validation split. Нові output schemas проходять unchanged Groq strict subset
без projections; mandatory local Pydantic validators перевіряють усі bounds і
semantic rules. F-01/F-02, gateway/provider/config/domain/application код не
змінено. Versioned policy/task prompts відмежовують trusted policy й untrusted
refinements/previous drafts. No payload telemetry; graph tracing disabled для
всього run. Result default export приховує draft, metadata-only gateway telemetry
збережено. State per invocation, no checkpoint/store/tools/supervisor.

Graph START→generate→validate→END; optional один content correction лише після
VALIDATION, default0, max2 generations, recursion_limit6. Safety/refusal/auth/
transport/quota не запускають agent retries. Gateway залишається єдиною retry/
fallback/limits межею. Перший incremental run виявив, що дві генерації в межах
strict default budgets можуть бути зупинені BUDGET — це очікувана поведінка.
Scripted Mock fixtures отримали explicit великі provider+model budgets, production
caps не змінено; окремий тест доводить quota stop для correction.

Dependency: langgraph>=1,<2, lock1.2.21 та4transitive packages; existing locked
versions не оновлювалися. Initial restricted PyPI DNS failure вирішено approved
network execution для dependency installation. Offline isolated install спершу
не мав cached wheels; exact hashed58 runtime dependencies завантажені з PyPI
в /tmp environment. Це dependency transport, не live LLM API calls.

Перевірки incremental/focused: initial91passed/4failed через mock budget keys,
виправлено лише test/demo budgets; final agents104passed/1.24s; prior combined
agents+allPhase4LLM355passed/5.37s перед додаванням2command-refusal cases.
Реальні Groq SDK fakeHTTP tests для всіх4agents підтвердили strict wire schemas,
mandatory local validation, no schema_projection і payload/key log redaction.
No unintended cloud/network/DB access перевірено guards; state isolation,
regeneration immutability, input tampering, invalid schemas/content, score/
aggregate grounding, safety/errors, transport retry ownership covered.

Sandbox limitation: unchanged baseline Runnable async test зависає в asyncio
selector/wakeup; відтворено окремо, interrupted. Позасandbox combined gate
348passed/4.62s, потім355passed/5.37s. Перший partial full run перервано для
завершення command safety check; interrupted-run warnings не є stable result.
Final full suite запущено без sandbox із blank API keys/LANGSMITH_TRACING=false.
Нових live Groq/Gemini requests не виконано. GUI не змінено, WSLg visual checks
не потрібні; native Windows11 лишається Phase12 risk, не verified requirement.

Фінальні stable перевірки:

| Команда / перевірка | Результат |
| --- | --- |
| uv run --offline --locked ruff check . | success |
| uv run --offline --locked ruff format --check . | success,81files |
| uv run --offline --locked pytest tests/test_agents.py -q --tb=short | **104passed,1.24s**, final code |
| combined tests/test_agents.py tests/test_llm*.py -q --tb=short | **355passed,5.37s**, перед2final command-refusal cases |
| GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false uv run --offline --locked pytest -q --tb=short | **571passed,205.14s**, final code, усі467baseline regressions |
| uv build --offline --out-dir /tmp/cyberforge-phase5-dist | sdist+wheel success |
| uv export --offline --locked --no-dev --no-emit-project --format requirements-txt; uv pip install --require-hashes -r exported file |58exact runtime dependencies, isolated /tmp wheel environment success |
| uv pip install --offline --no-deps --reinstall final wheel |success |
| /tmp/cyberforge-phase5-wheel-env/bin/python -I -m cyberforge.agents.demo, cwd=/tmp |4agents pending_review, offline success |
| wheel/sdist inspection |6agent modules source match, no DB/.env/credentials |
| QT_QPA_PLATFORM=offscreen isolated wheel cyberforge --database /tmp/cyberforge-phase5-wheel-smoke.sqlite3 --smoke-test |exit0 |
| git diff --check |success |

Phase5 подано на **REVIEW**, не ACCEPTED. Готовність REVIEW gate залежить від
successful Linux/Windows CI exact final PR HEAD; actual final SHA/CI run/jobs
фіксуються в PR і фінальному звіті після push, без circular documentation commit.
Перед commit/push: final diff і staged secret scan, включно з порівнянням actual
local secret values без їх виведення. PR→main; merge заборонено цим завданням.
Phase6 NOT STARTED; physical native Windows11 acceptance лишається Phase12.


## Phase 5 F-01 — previous draft provenance remediation

Independent review: Phase5 REVIEW, PR6, baseline
`1d8ac8cdec5e84cca1713e3d801246ba21691d05`; clean existing feature branch,
GitHub MCP підтвердив PR open/unmerged/base main/exact reviewed HEAD.
План перед coding: відтворити resource-ID collision; відокремити stable provenance
від request refinement; закрити Email/Web previous і canonical Email binding;
focused first, one stable full gate, final-head Linux/Windows CI без live API.
SRS §§5.6–5.7,11.4–11.7; SRS/RBAC/provider policy не змінюються.

Root cause: previous inputs містили лише slots; resource ID/template не доводять
scenario identity/version/context.8baseline regressions (2agents × differentID,
version,context,parameters із однаковим resource) усі failed: generation викликано
замість input rejection. Після fix попередні full envelopes перевіряються через
local DraftProvenanceV1. Digest включає identity/version, усі parameters,context,
language; Web також template і exact associated Email. Поточний refinement і
previous виключено, existing request context_token незмінний. Email envelope
self-consistency перевіряє provenance після relabeling metadata. Bare slots та
legacy envelopes без provenance readable, але reuse fail-closed; unknown identity
не допускається для reuse/Email→Web. Caller передає previous=result.draft.
Fingerprint не є authorization/signature; trusted application service/RBAC intact.

Changed: agents/contracts.py, specialized.py (local provenance stamping),
prompts.py (тільки slots previous у prompt), existing valid-regeneration test
оновлено на full envelope; new test_agent_provenance.py, ADR0005, plan/log.
Provider-facing schemas порівняно з reviewed commit через isolated module load:
EmailSlotsV1/WebSlotsV1/ExplanationSelectionV1 schemas та Groq strict conversion
**identical**. Phase4 gateway/adapters/config/domain/services не змінювалися.

Focused final:154passed/2.45s,104prior+50new. Cases: same-resource cross-scenario/
version,changedcontext/all relevant parameter fields/language,canonicalEmail
mismatch,relabelledidentity,exactEmail main/body/background changes forWeb,
changed/tamperedtemplate,missingidentity,legacy inputs,JSON roundtrip,
legitimate same-source regeneration з None/двома refinements для обох agents,
immutability. Rejected inputs:REQUEST,0generations/0Mock calls; network guarded.
Intermediate fixture issues (enum/model_copy,strictJSON,staticmockNIST claims)
виправлено у tests без послаблення production validation. Offline demo4agents
pending_review success. Ніяких live API, UI/DB/migration/dependency/startup changes;
packaging/GUI checks не повторюються без зміни відповідних integration points.
Native Windows11 physical verification лишається Phase12 acknowledged risk.

Перший local gate (до final audit нижче):

| Команда / перевірка | Результат |
| --- | --- |
| uv run --offline --locked pytest tests/test_agent_provenance.py tests/test_agents.py -q --tb=short | **154passed/2.45s** |
| uv run --offline --locked ruff check . | success |
| uv run --offline --locked ruff format --check . | success,82files |
| GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false uv run --offline --locked pytest -q --tb=short | **621passed/210.74s**, усі571prior regressions збережено |
| baseline/current provider schema + Groq strict conversion comparison |3schemas identical |
| uv run --offline --locked python -m cyberforge.agents.demo |success,4agents offline |
| git diff --check |success |

Full pytest виконано поза sandbox через відоме й раніше відтворене baseline
asyncio wakeup limitation, без live API. Перед commit/push — staged diff/secret
scan. Final HEAD і Linux/Windows exact-head CI jobs/log results будуть у PR6 та
фінальному звіті після push, без circular doc-only commits. Phase5 REVIEW, не
ACCEPTED; без merge/force/history rewriting/Phase6. .env/ключі/SQLite/user data
і native Windows acceptance environment збережено.


F-01 final audit перед completion виявив зайву залежність: exact associated
Email snapshot включав context_token з Email refinement. Виключено тільки цей
request-specific token, зі збереженням повної content/metadata binding. Новий
positive regression доводить Web regeneration після Email refinement без зміни
content, разом зі зміною Web refinement; existing stale-email cases лишаються.
Перший full621passed/210.74s і commit f155dc6 — перед цією додатковою поправкою,
не остаточне verification evidence. Final focused155passed,104prior+51new.
Остаточні full Ruff/pytest та exact-final-head CI фіксуються нижче/у PR6.


F-01 остаточний stable gate після request-token correction:
- focused `uv run --offline --locked pytest tests/test_agent_provenance.py tests/test_agents.py -q --tb=short`: **155passed/5.07s**,104prior+51new;
- `uv run --offline --locked ruff check .`: success;
- `uv run --offline --locked ruff format --check .`: success,82files;
- `GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false uv run --offline --locked pytest -q --tb=short`: **622passed/447.22s**; усі571reviewed-HEAD tests preserved;
- provider-schema/Groq strict conversion comparison повторено після остаточної code change:3schemas identical;
- final diff/staged secret scan перед follow-up commit/push; історія не переписується.
Final SHA та обидва successful exact-head CI jobs/log evidence фіксуються в PR6
і фінальному звіті після push. Phase5 REVIEW, не ACCEPTED; merge/Phase6 відсутні.


## 13.11.2026 — Phase 5 ACCEPTED власником; PR6 merge дозволено

Власник явно прийняв Phase5, включно з independent review/F-01 resolved та
успішним owner-run/owner-reported offline demo. ACCEPTED supersedes попередні
Phase5 REVIEW записи. Accepted scope/limitations — PHASE_5_ACCEPTANCE.md.
GitHub MCP підтвердив clean/open/unmerged PR6, base main6683f6e, reviewed HEAD
37a0f5e290a9068c8b24255acf276b826022c231; local feature branch clean/equal.
Reviewed CI43407344393: Linux622passed, Windows620passed/2POSIXskipped;
обидва jobs success, locked install/Ruff/package import/Qt smoke success.

План acceptance scope: SRS §23/§§9–11 — тільки plan/log/acceptance record/ADR
status. Runtime, tests, dependencies, SRS, .env/keys/DB/user/native environment
не змінюються. Нові live calls/local full suites/build/GUI не потрібні.
Owner authorization: docs commit/push existing branch, обидва CI exact FINAL
HEAD, ordinary merge commit із pinned expected head, local fetch/switch main/
merge --ff-only origin/main, перевірка SHAs/parents/clean tree. Failed/pending CI,
unexpected head/base/scope або conflicts зупинять merge без bypass. Staged
secret/diff checks перед commit. Actual final HEAD/CI/merge outcome — PR6/final
report після виконання, без circular doc commit. Phase6 NOT STARTED.

## 13.11.2026 — Phase 6 Email Constructor: початок та інкременти

Власник окремо дозволив Phase 6 з реалізацією, offline перевірками та PR, без
merge/Phase 7. GitHub MCP підтвердив merged/ACCEPTED PR6; clean local main
містить accepted merge 8a6beabf13ec4da43d2ce26bb78bccc9fce64340. Fetch/ff-only
успішні; створено feat/phase-6-email-constructor. Sandbox read-only .git вимагав
escalation; user changes відсутні. Наявні .env, keys, databases і Windows
acceptance environment не змінювалися. Старі NOT STARTED записи — історичні.

План перед coding зіставлено з SRS §§4.5–4.9,5.1–5.8,9.2,10,11,14.4,21,23–24.
Context7 функціонально доступний; офіційні Qt QRunnable/QThreadPool/queued
signals перевірено. GitHub MCP доступний. Інші MCP для цієї зміни не потрібні;
нових runtime dependencies немає. SRS незмінний, матеріальних відкритих рішень
не виявлено. Boundary/schema/context/lifecycle — ADR-0006.

Інкремент persistence: additive 0004 без зміни старих rows, EmailMaterialService
із наявним RBAC/BEGIN IMMEDIATE, independent material revision, exact scenario
revision/archive revision/provenance, full validated envelope. Детермінований
контекст v1 — лише trusted scenario ID/version. Stale/corrupt records не стираються,
повертаються як requires-review; valid replacement лише явним Save. Нові versions
не копіюють material. Downgrade nonempty table відмовляє без втрати даних.

Інкремент UI: ScenarioPage materials + EmailPage у наявному stack, приблизно 90%
preview, native plain-text inbox/detail/read state, JSON modal/copy/highlighting,
refinement та explicit Save/reopen/green. Accepted real EmailScenarioAgent і
gateway; no fixture-based normal generation. --email-demo явно синтетичний,
повністю offline і не читає .env. Default Mock unavailable показано чесно.
Workers QRunnable/QThreadPool, queued GUI slots, request/session/scenario/revision
identity; navigation/logout/version/archive/timeout відхиляють стару доставку.
Закриття з worker асинхронно очікує завершення; backend cancellation не заявлено.

Проміжні перевірки: existing scenario UI/database focus 51passed,1failed через
очікування попереднього Alembic head; test оновлено. New service focus
39passed,2failed через test-only str замість Path; fixtures виправлено.
Ці3cases повторно: 3passed/6.65s. New GUI focus:22passed/78.27s. Перший GUI
прогін перервано через assertion у modal test callback без finally-close;
harness виправлено, production dialog не змінено. Усі tests без live API.
Остаточні результати наведено нижче після стабілізації.

### Phase 6 — стабілізація та WSLg

- `UV_CACHE_DIR=/tmp/cyberforge-phase6-uv-cache uv run --offline --locked pytest tests/test_email_materials.py tests/ui/test_email_constructor.py -q --tb=short`:
  **67passed/156.71s** перед останнім session-epoch case і візуальною поправкою.
- WSLg screenshot review виявив обрізані другі рядки sender/resource; додано
  minimum height і regression assertion. Додано явно synthetic 09:30/09:25…
  timestamps у developer template згідно §5.3. Final layout/source cases:
  **2passed/7.27s** (такий самий focus до timestamps:2passed/7.81s).
- `QT_QPA_PLATFORM=wayland GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false UV_CACHE_DIR=/tmp/cyberforge-phase6-uv-cache uv run --offline --locked pytest tests/ui/test_email_constructor.py -q --tb=short`:
  **25passed/115.29s**, код до остаточних header/layout поправок нижче,
  real WSLg/Wayland.
- Реальний Wayland probe з ізольованою temporary DB: generation → preview →
  explicit Save → card; saved=true, scenario_status=draft, horizontal_overflow=0.
  Фінальні screenshots `phase-6-email-preview.png` (1400×900) та
  `phase-6-email-saved.png` (1100×720) візуально перевірено. Це Codex automation,
  не owner manual acceptance й не фізична Windows11 перевірка.
- Final `uv run --offline --locked ruff check .`, `ruff format --check .`:
  success,90Python files. Cache перенаправлено в /tmp, бо default uv cache
  read-only у sandbox. `git diff --check`:success.
- `uv build --offline --out-dir /tmp/cyberforge-phase6-dist`: sdist+wheel success.
  Archive inspection:61Python sources byte-identical тому code snapshot, packaged
  0004 migration присутня, private DB/.env artifacts відсутні.
- Fresh isolated wheel environment: offline dependency install виявив cache miss
  Alembic; дозволене завантаження58exact runtime dependencies із locked export
  та --require-hashes. Це package downloads, не LLM API calls. Остаточний
  installability/runtime outcome наведено нижче після завершення.

Змінені файли: README; IMPLEMENTATION_PLAN/DEVELOPMENT_LOG; main.py;
persistence/models.py; ui/scenario_page.py,shell.py; migration-head expectation
у test_groups_database.py. Додані: application/email_materials.py,email_demo.py;
migrations/versions/0004_email_materials.py; ui/email_page.py,email_source.py,
email_worker.py; tests/test_email_materials.py,ui/test_email_constructor.py;
ADR-0006,PHASE_6_ACCEPTANCE та2WSLg screenshots. Pyproject/uv.lock і SRS незмінні.

### Phase 6 — пауза власника та завершення layout remediation

До паузи власника повний прогін завершився **689passed,1failed/725.80s**:
`test_form_actions_and_internal_scroll[size0]` — кнопка Save виходила за viewport
1100×720. Focus із новими header widgets також відтворив цю регресію:
**18passed,1failed/72.07s**. Публікації за failing checks не було. Власник
зупинив роботу, потім окремо попросив продовжити; commit/push/PR до паузи відсутні.

Гранична тема без пробілів показала обмеження QLabel wrapping: headers переведено
на native read-only QPlainTextEdit зі scrolling і Tab focus navigation. Після
відновлення роботи root cause footer regression підтверджено: стандартний
QStackedWidget застосовував minimum size прихованої EmailPage до картки.
Локальний _WorkspaceStack тепер бере sizeHint/minimumSizeHint активної сторінки
і повідомляє layout про перехід. Global shell/theme не змінювалися.
Офіційні QWidget layout/updateGeometry API додатково перевірено Context7.

Focused existing footer (2sizes) + new Email save/source/long-header cases:
**4passed/6.68s**; після доповнення Save→card viewport assertions:
**1passed/1.84s**. Ці перевірки залишаються у загальній suite.

Final `QT_QPA_PLATFORM=wayland GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false UV_CACHE_DIR=/tmp/cyberforge-phase6-uv-cache uv run --offline --locked pytest tests/ui/test_email_constructor.py tests/ui/test_scenarios_ui.py::test_form_actions_and_internal_scroll -q --tb=short`:
**27passed/66.89s**. Оновлений real WSLg probe: saved=true,
scenario_status=draft, horizontal_overflow=0, save_visible=true на1100×720.
Обидва screenshots оновлено й візуально перевірено. Headers та body мають власне
прокручування; за потреби доступне прокручування всієї центральної панелі.
Owner manual acceptance не виконано; Windows11 native verification — Phase12 risk.

Остаточне пакування після layout fix: `uv build --offline --out-dir /tmp/cyberforge-phase6-dist`;
`uv export --offline --locked --no-dev --no-emit-project --format requirements-txt --output-file /tmp/cyberforge-phase6-requirements.txt --quiet`;
`uv venv --offline --python .venv/bin/python /tmp/cyberforge-phase6-wheel-env`;
`uv pip install --offline --python /tmp/cyberforge-phase6-wheel-env/bin/python --require-hashes -r /tmp/cyberforge-phase6-requirements.txt`;
`uv pip install --offline --python /tmp/cyberforge-phase6-wheel-env/bin/python --no-deps /tmp/cyberforge-phase6-dist/cyberforge-0.1.0-py3-none-any.whl`:
успішно,58locked runtime dependencies встановлено офлайн.61Python sources у
wheel/sdist byte-identical остаточному src; міграція присутня, private artifacts
відсутні. Isolated installed wheel, `python -I`, cwd=/tmp: packaged migration
0004, foreign_key_check, real offline Email agent, Save/reopen — success;
`python -I -m cyberforge --email-demo --database /tmp/cyberforge-phase6-wheel-smoke.sqlite3 --smoke-test`
з QT_QPA_PLATFORM=offscreen та blank keys — exit0.

GitHub MCP після resume: main лишається8a6beabf13ec4da43d2ce26bb78bccc9fce64340;
попереднього Phase6 PR немає. Final lint/format — success,90files; final full
pytest та exact-final-head CI результати фіксуються після їх завершення.

### Phase 6 — final local gate / REVIEW

Один попередній final-code pytest процес перервався кодом143/SIGTERM без pytest
summary; його не зараховано як success. Повторено в PTY з постійним /tmp log:
`GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false UV_CACHE_DIR=/tmp/cyberforge-phase6-uv-cache uv run --offline --locked pytest -vv --tb=short --durations=10`:
**690passed/305.56s**, exit0. Збережено всі622accepted tests, додано68cases.
Обидва existing footer regression sizes і Save→card viewport assertions пройдено.
Фінальні lint/format (`uv run --offline --locked ruff check .`,
`uv run --offline --locked ruff format --check .`, з UV_CACHE_DIR у/tmp) — success,
90files; `git diff --check` — success. Production code після цього не змінюється.

Phase6 подано на **REVIEW**, не ACCEPTED. Повний local gate, real WSLg27cases,
packaging/migration/installability gates пройдено. Owner manual checklist — pending;
physical native Windows11 — acknowledged Phase12 risk. Live API calls відсутні;
Groq/Hydrogen integration selection перевірено scripted provider через existing
gateway, не реальними account requests. Offline demo чесно позначено synthetic.

Перед publishing — complete diff/staged secret/private-path scan. Feature branch
commit/push та PR→main дозволені початковим запитом. Exact final HEAD, PR URL,
обидва successful Linux/Windows CI jobs/log evidence фіксуються в PR/final report
після push, без circular documentation-only commit. CI failure не обходиться.
Merge/force/history rewriting/Phase7 заборонені цим завданням. GitHub/Context7
MCP доступні; fallback для цих перевірок не потрібний. SRS/.env/owner databases/
keys/native Windows acceptance environment незмінні.

## 13.11.2026 — Phase 6 owner-requested Gmail-style UX revision (PR #7)

The owner did not accept the previous Email Constructor UX and authorized this
change in the existing Phase 6 branch/PR only. Communication/new technical notes
are English; application text remains Ukrainian. Phase 7, live LLM requests and
manual native Windows 11 validation remain excluded. The existing owner demo
database/credentials were not read, reset or modified by development probes.

Initial state: clean feat/phase-6-email-constructor at
61e766830c4a31929f2942a6fd4345b58bb4c281; GitHub MCP confirmed PR7 open/unmerged,
base main8a6beab, matching HEAD. Reviewed SRS §§5.2–5.7, current source/view code,
acceptance record and ADR-0006. Context7 supplied official native QListWidget/
delegate/activation and QStackedWidget documentation. No new dependencies.

Plan before implementation: scope light styling to the preview; add native
browser/mail chrome, inbox/search and reading view; clarify regeneration;
provide canonical JSON plus an honest inert HTML content projection under §5.5;
focused UI/security tests, then one stable full gate, WSLg and exact-head CI.

Implementation: MailPreview owns only native presentation/read state. Its data
comes from current EmailDraftV2 slots. Inbox click/Enter opens a message, search
filters real fields, back returns to the inbox. The read-only `.invalid` address
bar and disabled sending/navigation controls cannot open a website or send mail.
The surrounding application theme/catalog are unchanged. Native active-view
minimum-height sizing and compact folders preserve critical controls at1100×720;
early compact-layout failures were fixed before the final gate.

The refinement label/helper and Generate/Regenerate button now explain the
instruction → new unsaved candidate → explicit Save flow. Canonical JSON stays
unchanged. A second source tab contains escaped deterministic HTML for the
selected message's content only, not AI HTML or Qt interface source. It is not
rendered/executed/persisted. Both tabs are read-only, highlighted and copyable;
UI clearing clears both. Fixed-template escaping/allowed-tags tests include
validation-bypass injection cases. This source-view trade-off is recorded in
the existing ADR-0006; no new architectural document or SRS change was needed.

Focused final-code checks:
`UV_CACHE_DIR=/tmp/cyberforge-phase6-ux-uv-cache uv run --offline --locked pytest tests/test_email_source.py tests/ui/test_email_constructor.py -q --tb=short`:
**33 passed / 48.43s**. Covers both source tabs/copy/read-only semantics, escaped
HTML, inbox/reading/search/read state, refinement guidance, Save/reopen/failure,
stale/session/version/archive/timeout delivery rejection and responsive controls.
Ruff lint/format pass,92Python files. Final full/WSLg/CI evidence follows below.

This is UI/source-inspection-only: application services, agents/gateway,
threading/identity code, schema/migrations, dependencies/lockfile and startup
configuration are unchanged. Packaging/wheel checks are not repeated under the
approved UI-only verification policy; standard CI import/startup checks remain.
Documentation is limited to README, this log, PHASE_6_ACCEPTANCE and the focused
ADR amendment, plus updated WSLg screenshots. No documentation-only commit is
planned. Phase6 stays REVIEW and awaits the owner's UX review/acceptance.

### Gmail-style UX revision — final local verification

- `UV_CACHE_DIR=/tmp/cyberforge-phase6-ux-uv-cache uv run --offline --locked ruff check .`
  and `ruff format --check .`: success,92Python files.
- `GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false UV_CACHE_DIR=/tmp/cyberforge-phase6-ux-uv-cache uv run --offline --locked pytest -vv --tb=short --durations=10`:
  Initial full pass before the final search-reset correction below:
  **698 passed / 341.97s**, exit0, PTY log in /tmp. All690previous tests retained;
  eight new cases cover the light/native mailbox, compact inbox/reading controls
  and deterministic/safe HTML content projection.
- `QT_QPA_PLATFORM=wayland GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false UV_CACHE_DIR=/tmp/cyberforge-phase6-ux-uv-cache uv run --offline --locked pytest tests/ui/test_email_constructor.py tests/ui/test_scenarios_ui.py::test_form_actions_and_internal_scroll -q --tb=short`:
  **30 passed / 73.76s**, real WSLg. The isolated offline screenshot probe confirms
  3real artifact messages, opened index0, unsaved=true, zero horizontal overflow
  and all critical controls visible at1100×720. Inbox, opened-message and compact
  screenshots were inspected. These are Codex checks, not owner acceptance.
- `git diff --check`: success. Before commit/push, review staged diff and scan
  actual local secret values/private paths without printing those values.

Changed in this revision: ui/email_preview.py (new), ui/email_page.py,
ui/email_source.py; tests/test_email_source.py (new),
tests/ui/test_email_constructor.py; README, PHASE_6_ACCEPTANCE, this log,
ADR-0006; screenshots phase-6-email-preview.png, phase-6-gmail-inbox.png (new),
phase-6-gmail-compact.png (new). No services, agents, workers, schema, lockfile,
global theme or main shell edits. One combined implementation/docs commit goes
to the current PR7 branch. Exact final HEAD and final Linux/Windows CI job/log
evidence will be recorded in PR7 and the final English report after push;
no circular documentation-only commit. No merge or Phase7 work is authorized.

Final diff review caught an active-search regeneration edge case: clearing a
nonempty search query could call the filter between clearing/rebuilding inbox
rows. QSignalBlocker now prevents that intermediate callback. The refinement
test explicitly regenerates with an active query and checks the rebuilt inbox.
Focused final regression: **1 passed / 1.77s** offscreen, **1 passed / 2.50s**
real WSLg. The 30-case WSLg visual/interaction pass above remains the renderer
evidence; the final change affects only search callback delivery during reset.

Required final full suite repeated because code changed:
`GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false UV_CACHE_DIR=/tmp/cyberforge-phase6-ux-uv-cache uv run --offline --locked pytest -vv --tb=short --durations=10`:
**698 passed / 324.13s**, exit0, PTY log
`/tmp/cyberforge-phase6-ux-after-reset-pytest.log`. This supersedes the earlier
full-pass timing for commit45d1318. The subsequent Windows CI correction below
supersedes this as final-code evidence. No live LLM calls,
native Windows manual tests or owner-database operations were performed.

### Windows CI compact reading-view correction

CI run43517074528 at45d1318 passed Linux (698passed/355.49s) but failed Windows
(1failed,695passed,2POSIX-only skips/400.33s). The existing 1100×720 reading-view
test caught a real issue: Segoe UI metrics plus nested height-for-width sizing
reserved the body's preferred editor height and pushed refinement/actions below
the viewport. The assertion was retained and strengthened to require no outer
vertical scrolling and a usable body minimum height.

Reproduced with locally loaded Segoe UI fonts in an isolated Linux/offscreen
probe; the correction ignores only the body's preferred vertical size while
retaining its minimum, stretch allocation and internal scrolling. No font files
are copied into the repository. Context7 confirmed native layout sizing APIs.
A custom-layout experiment was discarded after focused tests exposed recursive
Qt callbacks; the final correction uses standard QSizePolicy only (six lines).

Final focused source/UI suite: **33passed/48.16s**. Real WSLg compact inbox,
reading and Save/reopen: **3passed/5.78s**. The Segoe UI WSLg probe also passes,
with page/viewport both656px high and all critical controls visible. Sandboxed
Wayland startup was denied by the environment; rerunning with authorized access
to the WSLg socket passed. These are Linux/WSLg checks, not native Windows11
manual acceptance. Review screenshots were refreshed and visually inspected;
their image content is unchanged. Replacement exact-head CI evidence follows
in PR7 after completion. The necessary correction goes to the same
Phase6 branch/PR7 as a second implementation/test/evidence commit, without
rewriting the first commit or adding a documentation-only commit.

The initial restricted-sandbox full run stalled in the unchanged offline asyncio
batch test; it was interrupted and is not counted as a pass. The full suite was
restarted with access to local sockets, keeping API keys empty/tracing disabled.

Final full command (PTY, outside the socket-restricted sandbox):
`GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false UV_CACHE_DIR=/tmp/cyberforge-phase6-ux-uv-cache uv run --offline --locked pytest -vv --tb=short --durations=10`:
**698passed/323.50s**, exit0;
`/tmp/cyberforge-phase6-ux-final-layout-pytest.log`. Ruff lint/format pass92files;
`git diff --check` passes. This supersedes the previous local full-suite evidence.
This verifies commitf8e1417; the final padding adjustment below supersedes it.
PR7 records exact pushed HEADs and Linux/Windows CI job/log results without an
extra documentation-only commit.

### Windows CI outer-padding correction

Run43520321517 atf8e1417 passed Linux (698passed/324.42s). Windows passed every
critical-control visibility assertion but found **2pixels** of outer vertical
scrolling under the newly added stricter assertion (1failed,695passed,
2POSIX-only skips/479.10s). Kept that assertion and reduced EmailPage's vertical
padding from8px to4px; no controls/text/font sizes or workflow behavior changed.
This adds8px of layout headroom at the minimum size. The focused compact and
Save/reopen check passes **3cases/5.05s** offscreen and **3cases/7.79s** WSLg.
An isolated Segoe UI WSLg probe with a650px viewport (matching Windows CI) passes
all control visibility/zero-outer-scroll assertions. Only the temporary probe's
window minimum was reduced; the application's1100×720 minimum is unchanged.
The three review screenshots were refreshed; the compact image was inspected.
Final full/CI evidence follows. The additional commit is a verified correction in
PR7, not a separate phase or documentation-only change.

Final full command (PTY, local-socket access):
`GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false UV_CACHE_DIR=/tmp/cyberforge-phase6-ux-uv-cache uv run --offline --locked pytest -vv --tb=short --durations=10`:
**698passed/327.86s**, exit0; `/tmp/cyberforge-phase6-ux-padding-pytest.log`.
This is final local evidence after both Windows CI findings. Ruff lint/format
pass92Python files and `git diff --check` passes. No further production edits
follow this gate; exact final HEAD/CI evidence is recorded in PR7/final report.

## 14.11.2026 — Phase 6 final visual fidelity pass (PR #7)

Owner-reported manual WSLg review of0e34dd8ae9061221921448c28f00391d82852f20:
the overall layout was acceptable, with typography/icons/reading presentation
still requiring refinement. This authorizes one focused visual pass, not Phase6
acceptance, merge or Phase7. Started on the matching clean tracked branch/PR7.
The owner then supplied local inbox/opened Gmail references in temp/. Inspected
them and existing Phase6 captures; originals contain real mailbox data and are
left untracked, without copying any content, identities or graphical assets.
The open owner demo credential files/databases were not read, reset or modified.

Plan mapped to SRS §§5.2–5.5: refine the existing native preview's hierarchy and
iconography, format existing structured message content with controlled native
Qt primitives, retain canonical JSON/source clarification, then focused/full
regressions, WSLg captures and exact-final-head Linux/Windows CI. SRS §§5.6–5.8,
16/21 persistence/security/worker guarantees remain regression requirements.
GitHub MCP confirmed the reviewed HEAD and open/unmerged main-target PR7;
Context7 verified official QTextEdit/QTextCursor/block/frame-format APIs.

Implementation: scoped Arial/native fallback typography, 22px subject, 15px body,
14px sender/inbox text, 12px recipient/time. Metadata is aligned around a native
avatar; reply/forward use separate outlined pills. Existing icon infrastructure
now supplies original painted mail glyphs, with optional color and doubled
pixmap resolution; default shell icon colors/API are preserved. Inbox/read views
have separate toolbars; wide rows align sender/subject/snippet/time in one line,
compact rows use two. Read/unread/selection styling remains in memory.

MessageBody is native QTextEdit/QTextDocument, not a browser engine. QTextCursor
inserts only literal existing sender/body/resource strings. Native character,
block and frame formats provide paragraphs, a synthetic sender header and an
inert resource/action card. No arbitrary HTML parsing, anchors, scripts, external
resources or new content claims. Resource loading is denied. Background text
retains paragraph boundaries. JSON/HTML inspection remains unchanged and honest:
the HTML tab is still an inert content projection, not native UI source.
No agent/contracts/services/workers/schema/dependency/startup/catalog changes.
No live API calls, physical Windows11 checks or native-environment refresh.

Early focused feedback caught1px outer overflow with8px extra toolbar reserve;
reduced preview bottom padding from8px to4px and retained strict assertions.
Tests check custom toolbar labels without imposing them on Qt-owned line-edit
buttons. Focused source/UI: **38passed/157.59s**; relevant real WSLg UI/card:
**35passed/164.71s**. After the final sender font/height adjustment, compact
inbox/read with native-metric reserve, hierarchy/icons, source/Save/reopen and
long Unicode content: **7passed/33.87s** offscreen, **7passed/35.23s** WSLg.
Three new tests cover native hierarchy, literal injection/resource denial and
background paragraph fidelity; two added compact cases reserve8px for differing
native metrics. All698previous cases remain present; no new skips.

Commands use `UV_CACHE_DIR=/tmp/cyberforge-phase6-ux-uv-cache uv run --offline --locked`:
`pytest tests/test_email_source.py tests/ui/test_email_constructor.py -q --tb=short`;
WSLg adds `QT_QPA_PLATFORM=wayland` and checks the constructor module plus
`tests/ui/test_scenarios_ui.py::test_form_actions_and_internal_scroll`. Final
focused selection: `test_compact_mailbox_keeps_critical_controls_visible`,
`test_reading_hierarchy_vector_icons_and_inert_resource`,
`test_mail_navigation_source_copy_explicit_save_reopen`,
`test_long_unicode_wrap_and_layout_at_supported_sizes` in the constructor module.

Isolated synthetic WSLg captures: inbox1400×900, opened message1400×1060, compact
reading1100×720. An additional Segoe UI probe with642px available viewport
(Windows650px minus8px reserve) confirms all critical controls visible and zero
outer scrolling. This is WSLg/font-metric evidence, not native Windows11 proof.
Compared the hierarchy, vector icons, rows and formatted content with both local
references. The native mock intentionally omits real brands/media/apps and
arbitrary multipart rendering; long body/card content scrolls internally.
The accepted scenario catalog remains visible. Owner final visual decision is
pending; Phase6 stays REVIEW, Phase7 NOT STARTED.

Ruff lint/format pass93Python files; `git diff --check` passes. Packaging/wheel
checks are not repeated for this UI-only change under the approved workflow.
Final full-suite, staged scan and exact-HEAD CI evidence follow below/PR7.

Final stable full command (PTY, local asyncio-socket access):
`GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false UV_CACHE_DIR=/tmp/cyberforge-phase6-ux-uv-cache uv run --offline --locked pytest -vv --tb=short --durations=10`:
**703passed/887.67s**, exit0; `/tmp/cyberforge-phase6-fidelity-pytest.log`.
No production changes after this verification. Lint/format93files and diff
whitespace checks pass. The intended12-file commit includes native body/preview,
icons, UI tests, README, plan/log/acceptance/ADR and three synthetic screenshots.
Reference images/temp files, credentials, databases, .env and native acceptance
files are excluded. Exact final HEAD and Linux/Windows CI job/log evidence are
recorded in PR7/final report after push, without a documentation-only commit.

### Windows CI width correction for the final visual pass

Run43571914708 atfa81ce8 passed Linux (703passed/425.64s, plus startup smoke).
Windows failed3reading/long-content geometry cases (698passed,2POSIX-only skips,
377.81s): the page widened to1078px inside a760px viewport, which also introduced
horizontal-scroll height loss. No service/source/security case failed.
Local Arial/Segoe probes did not reproduce the platform-specific growth; the
correction explicitly prevents native text size hints from widening the page.

Read-only subject/sender/body fields ignore horizontal preferred/minimum hints
while retaining available-space allocation, wrapping and internal scrolling.
Recipient metadata can wrap; the fixed synthetic timestamp has a bounded width.
Added an oversized-native-body-hint regression and geometry diagnostics to the
existing strict assertions, without removing or loosening checks. Context7
confirmed QSizePolicy.Ignored semantics. This is a native layout correction only;
contracts, content, source inspection, Save and workers are unchanged.
Focused offscreen geometry/source/Save-reopen: **7passed/25.61s**. Final WSLg,
full-suite and replacement exact-head CI evidence follow. The additional commit
will stay in PR7; no merge, acceptance or Phase7 work is authorized.

Final WSLg correction selection: **7passed/26.00s**, including the new oversized
native hint case, all4compact states, long-content and source/Save/reopen.
Refreshed all3screenshots; their image content is unchanged. An isolated native
Arial+Segoe WSLg probe also fits642px available height without outer overflow.
Full Ruff lint/format pass93files and diff whitespace check passes. Required
stable full suite is repeated after the code correction; no tests are omitted.

Final correction full command (PTY, local asyncio sockets):
`GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false UV_CACHE_DIR=/tmp/cyberforge-phase6-ux-uv-cache uv run --offline --locked pytest -vv --tb=short --durations=10`:
**704passed/691.55s**, exit0; `/tmp/cyberforge-phase6-fidelity-width-pytest.log`.
This supersedes the703case local result as final production-code evidence.
Test diagnostics were made failure-only, without changing assertions; the exact
final focused selection was rerun: **7passed/28.44s** offscreen. No further
production edits follow the gate. Replacement exact-head CI proof is recorded
in PR7/final report after push; owner visual acceptance remains pending.

### Native active-page minimum-height correction

Run43574506367 at762f71c passed Linux (704passed/386.14s). Windows confirmed
the horizontal-growth/long-content fix, but found the reading page still655px
high inside650/642px viewports (3failed,699passed,2POSIX skips/476.44s).
The remaining5/13px reservation came from native preferred-height sizing.
A48px body fallback was explored locally (7cases passed offscreen/WSLg), but
the final correction retains the original65px minimum. A private native
QStackedLayout now answers current-page minimum/height-for-width queries at the
layout level; widget-only overrides can be bypassed when Qt asks an owned layout
directly. The small view wrapper keeps the existing currentIndex/currentWidget
API. Inactive inbox/preferred text-editor heights cannot inflate the reader.

Retained all strict checks; added a three-text-line viewport assertion at1100×720
and extended the oversized-hint case with an1800px preferred inactive inbox.
Native active-layout focused selection: **7passed/25.35s** offscreen. No font,
content, service/worker or persistence changes. Final WSLg/full/CI follows.

Final native-layout WSLg source/UI/card suite: **41passed/128.22s**. Command:
`QT_QPA_PLATFORM=wayland GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false UV_CACHE_DIR=/tmp/cyberforge-phase6-ux-uv-cache uv run --offline --locked pytest tests/ui/test_email_constructor.py tests/test_email_source.py tests/ui/test_scenarios_ui.py::test_form_actions_and_internal_scroll -q --tb=short`.
The refreshed screenshots are pixel-identical to the reviewed refinement
captures. Arial/Segoe642px viewport probe passes. Lint/format93files and diff
whitespace checks pass. No production edits after this stable verification;
the complete704case suite is repeated before publishing the correction.

Final active-layout full command (PTY, local asyncio sockets):
`GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false UV_CACHE_DIR=/tmp/cyberforge-phase6-ux-uv-cache uv run --offline --locked pytest -vv --tb=short --durations=10`:
**704passed/682.25s**, exit0; `/tmp/cyberforge-phase6-fidelity-layout-pytest.log`.
This is final local evidence for the active-layout correction; all698previous
cases remain, with6added cases and no new skips. Lint/format93files and diff
whitespace checks pass. No production edits follow; final HEAD and both exact
Linux/Windows CI job/log results are recorded in PR7/final report after push.

### Wrapped-label minimum policy — reproduced final height cause

Run43577486176 at7337ef3 again left the Windows page655px tall (3failed,
699passed,2POSIX-only skips/302.53s); the inner-stack policy did not resolve
this outer constraint. Inspected the EmailPage root labels: the shared label
factory gives them vertical QSizePolicy.Minimum, which treats their preferred
wrapped height as a hard minimum even when the actual width needs fewer lines.

Added a native-label preferred-height fault test. Before the fix it reproduces
locally: page1439px versus viewport656px,783px outer scroll (1failed/4.56s).
EmailPage now uses vertical Preferred for its six wrapped title/status/helper
labels, retaining height-for-width wrapping. This changes no text/fonts or
global label behavior. The exact same regression and existing geometry/source/
Save selection then pass: **8passed/29.59s** offscreen. The body keeps65px.
Existing strict assertions, inactive/editor hint case and three-line body guard
remain intact. Final focused/full/CI proof follows; Phase6 remains REVIEW.

The local label policy explicitly preserves height-for-width. Final focused
selection (label/editor/inactive hints,4compact states, long content, source/
Save/reopen) passes **8cases/28.30s** offscreen and **8cases/32.43s** WSLg,
including assertions that wrapped text receives its measured required height.
Broader WSLg UI/source/card pass: **42cases/139.92s** before the final wrapping
flag preservation. Refreshed/inspected inbox; opened/compact captures remain
pixel-identical. Arial/Segoe642px probe passes. Lint/format93files pass. Final
complete705case run follows; no further production edits are planned.

Final wrapped-label full command (PTY, local asyncio sockets):
`GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false UV_CACHE_DIR=/tmp/cyberforge-phase6-ux-uv-cache uv run --offline --locked pytest -vv --tb=short --durations=10`:
**705passed/931.94s**, exit0; `/tmp/cyberforge-phase6-fidelity-label-pytest.log`.
All698previous cases remain with7added cases, no new skips. This supersedes
earlier local totals for the final label policy. Lint/format93files, diff and
staged exact-scope/private-value checks pass before publishing. No production
changes follow this gate. The visual pass now touches13files after adding the
scoped EmailPage label fix; original references/temp/credentials stay excluded.
Final HEAD and both CI job/log proofs are recorded in PR7/final report.


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


Editing increment evidence: new service/editing cases passed13/27.06s before
three further restriction cases; acceptance-runner/prompt tests4/1.80s, with
scripted providers only. Full Phase5 agent/provenance suite155/6.37s passes after
explicit Email→Web input projection updates and fixture quota reservations.
Initial incremental runs exposed those compatibility/fixture issues; they are
not counted as final passes. The superseded combined focused run was terminated
without a final success summary; final full/WSLg checks are authoritative.

Build: `uv build --offline --out-dir /tmp/cyberforge-phase6-edit-dist` passed
wheel+sdist. A fresh fully dependency-isolated offline install could not resolve
google-genai from the temporary cache. Installed the built wheel with --no-deps
into a separate /tmp venv, reused verified dependencies through a .pth path,
and asserted cyberforge.__file__ is inside that venv. From /tmp with python -I:
manual Apply→Save→reopen via the actual service/UI passed; packaged live-check
--help passed without requests. This is wheel-content/installability evidence,
not an independently redownloaded dependency resolution. No source tree fallback,
owner DB/credentials or preserved Windows environment was used.

The new UI failed-regeneration regression confirms the worker receives the
manual draft and retains both working and saved content:1passed/6.15s offscreen.
Ruff lint/format pass97Python files; whitespace checks pass. WSLg preview/editor/
compact captures inspected; source view now JSON-only, native formatting retained.
Final full/WSLg counts and exact PR HEAD/CI evidence follow.

WSLg final constructor suite37passed/221.12s; final added manual-worker-failure
case1passed/5.32s. These are Codex checks, not owner acceptance. All captures use
fresh synthetic temporary databases; existing owner credentials were not read.
The UI currently edits existing main/background entries; background add/remove
is validated by the service but intentionally not added to this focused dialog.
The explicit refinement scope is the deterministic protection mechanism; free
text is not parsed as an authoritative patch specification. All-content scope
requires instructor review and does not guarantee natural-language preservation.
Context/provenance do not prove that arbitrary names are synthetic; the existing
synthetic-only input policy, known unsafe-pattern checks and owner review remain.

Final review found legacy fields could be silently truncated on dialog open.
The editor now retains existing full values; narrower Apply limits are enforced
by validation. Focused legacy/edit workflow:3passed/12.47s. Added a regression
for preserving existing long fields on Cancel. Regeneration confirmation now
uses explicit Ukrainian buttons with Keep as default, without changing worker
semantics. The previous full run was superseded/interrupted after these final
UI fixes; the complete stable suite is repeated. No failure is counted as a pass.

Final installed-wheel and screenshot probes are repeated after the legacy-field
fix. Full stable suite collects726cases; final WSLg selection evidence follows.

Final WSLg selection:5passed/25.94s. Rebuilt wheel/sdist and installed-wheel
Apply/Save/reopen passed after the legacy fix. Screenshot probe confirms all
critical controls including Edit visible at1100×720, zero horizontal overflow,
main/background artifact messages and a current unsaved edited candidate.
No screenshots contain real identities from the owner's Gmail references.


Final stable full command (PTY with local asyncio sockets):
`GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false UV_CACHE_DIR=/tmp/cyberforge-phase6-ux-uv-cache uv run --offline --locked pytest -vv --tb=short --durations=10`:
**726passed/1021.98s**, exit0; `/tmp/phase6-edit-stable-full.log`.
The705baseline cases retain meaningful security/persistence/worker regressions;
four net HTML-projection-only cases were removed and25editing/source/prompt/
live-runner/legacy/confirmation cases added. No new skips. Final lint/format:
`uv run --offline --locked ruff check .` and `ruff format --check .` pass97files;
`git diff --check` passes. Focused155agent/provenance cases, WSLg37+5 and final
wheel/sdist/installed-wheel Apply→Save→reopen gates are recorded above.

Final diff/staged exact-scope scan covers27intended files and excludes temp/,
.env, credentials and databases. No code changes follow this stable full gate.
Commit/push remain in the existing Phase6 branch/PR7. Exact final HEAD and both
Linux/Windows CI jobs/log evidence will be recorded in PR7 and the final report
without a documentation-only commit. No merge, ACCEPTED or Phase7 transition.
Live Groq remains owner-initiated and PENDING; no real API calls were made.

### Windows CI compact-layout correction

Completion commit ee370503 passed Linux CI; Windows CI run43591272955 reported
7layout failures (717passed,2platform skips). Native combo font metrics widened
the Email page to812px inside a768px viewport. The AI scope selector now uses a
shorter Ukrainian label,12px typography and a bounded minimum-content size hint.
The existing compact tests also assert Edit/scope visibility; no assertions were
removed. Focused compact/native-hint/long-Unicode suite:7passed/36.85s. Real
WSLg capture confirms zero horizontal overflow, visible critical controls and a
current unsaved edited candidate at1100×720; three mailbox screenshots refreshed.
The sandbox's first Wayland attempt lacked socket access; the authorized WSLg
probe then passed with local-display access. Ruff lint/format pass97files.
Final correction full gate:
`GOOGLE_API_KEY= GROQ_API_KEY= LANGSMITH_TRACING=false UV_CACHE_DIR=/tmp/cyberforge-phase6-ux-uv-cache uv run --offline --locked pytest -q --tb=short --durations=10`:
**726passed/1010.40s**, exit0; `/tmp/phase6-edit-layout-full.log`.
The same7focused layout cases also pass through real WSLg/Wayland in40.30s.
Final lint/format and whitespace checks pass; no production edits follow this
gate. Final-head Linux/Windows CI evidence will be recorded in PR7 and delivery.

Run43596471556 for2efb258 passed Linux; Windows confirmed the width fix but
reported4remaining opened-view height failures (720passed,2platform skips).
The page needed8–16px more than the compact viewport. Edit now uses the same
compact padding as Back, and page gaps decrease from3px to2px. This recovers
space from controls without shrinking the body, hiding actions, changing
functional behavior or relaxing tests. Focused/full/WSLg verification is repeated.

Final height-correction checks:7focused cases passed offscreen/35.79s and
WSLg/41.39s. Fresh synthetic WSLg captures retain every critical control and
zero horizontal overflow; compact reading area gains19px. Final full command
is the same offline `pytest -q --tb=short --durations=10` invocation above:
**726passed/1049.72s**, exit0, `/tmp/phase6-edit-final-full.log`.
Ruff lint/format97files and whitespace checks pass. No production edits follow
this gate; final CI evidence is kept in PR7 and the delivery report.


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

Address-rule focused verification: `pytest -q tests/test_email_editing.py
tests/test_email_live_check.py tests/test_agents.py tests/test_agent_provenance.py`:
202passed/29.27s. UI `pytest -q tests/ui/test_email_constructor.py -k
'visual_editor_apply_cancel_json_save_reopen or visual_editor_invalid'`:
2passed/11.15s. All use offline Mock/scripted providers with socket guards.
Ruff lint/format pass97files and `git diff --check` passes. The initial wider
focused run used the old prompt marker and domain-only rejection expectation;
those two expectations are superseded by prompt-v3/ordinary-address acceptance
coverage. No repeated full local suite or live API calls. Final-head Linux/
Windows full CI evidence will be recorded in PR7 and the delivery report.

Address-rule CI run43642852695 found the long-address UI fixture used a single
200-character domain label. It now uses multiple valid labels at the identical
total address length; layout assertions are unchanged. Focused long-Unicode
layout test:1passed/3.25s; Ruff/format97files and whitespace checks pass. This
fixture-only follow-up adds no production change or repeated full local suite.


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

Verification: initial provider/gateway/live-runner batch155passed/11.17s;
additional optional-limit/diagnostic/CLI cases24passed/2.33s. The first wider
focused attempt stalled at asyncio in the socket-restricted sandbox and was
interrupted, not counted as a pass. Runnable-only rerun with local socket access:
6passed/0.50s. Final stable focused selection (no real API keys, tracing off,
offline/locked uv): tests/test_llm_token_policy.py, test_llm_gateway.py,
test_llm_groq.py, test_llm_gemini.py, test_llm_hydrogen.py,
test_email_live_check.py, test_agents.py, test_agent_provenance.py,
test_email_editing.py, test_llm_review.py, test_llm_integration.py and
test_llm_runnable.py: **471passed/43.32s**. Ruff lint/format98files, diff
whitespace and packaged-module-style `python -m ...email_live_check --help`
pass. No full local suite; Linux/Windows CI will verify the exact pushed HEAD.
Official Groq Python API docs confirm optional max_completion_tokens omission
and APIStatusError status_code/body metadata; local pinned SDK transports
verify serialization without network. Raw provider messages/bodies are never
exported. No packaging/dependency/migration changes or GUI redesign.

Final scan found the separate connectivity CLI still hard-coded256tokens.
It now inherits the configured optional provider limit too. Diagnostic/Hydrogen
focused selection:70passed/4.82s, including absent and explicit50000-token
settings. Ruff lint/format98files and whitespace pass. No live call; this small
follow-up is covered by final-head CI rather than another full local run.


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

Focused offline selection: `pytest -q tests/test_email_live_check.py
tests/test_llm_token_policy.py tests/test_agents.py tests/test_llm_groq.py
tests/test_llm_gemini.py`:172passed/11.98s. Updated provider-neutral assertion
selection rerun:4cases verify Email4096 vs unrelated operations unset. Ruff
lint/format98files and whitespace checks pass. Final-head CI evidence follows
in PR7 and delivery; no full local suite or live requests.


## Phase 6 — остаточне прийняття та дозволене злиття, 2026-11-15

Власник явно оголосив Phase6 ACCEPTED і дозволив normal merge commit PR7 у
main після final-head CI. Reviewed implementation HEAD:
9653b72ddd65be590a60a21aeb2bb59ad3d4f2aa. PR відкритий, base main,
mergeable_state clean; review threads, reviews і comments порожні, блокувальних
зауважень немає. Reviewed CI43679237327: Linux783passed/280.37s,
Windows781passed/2POSIX-only skips/476.08s; Ruff98files/import/Qt smoke success.

Owner-reported прийняття: approved Gmail-inspired UI; manual main/background
editing; Apply/Cancel/Save; canonical JSON, persistence/reopen; refinement і
regeneration; GUI generation зі змістовними scenario parameters і GUI
regeneration. Owner live Groq4096: initial889/refinement780output tokens,
validation PASSED, protected_fields_preserved=true. Ці GUI/live докази належать
власнику; Codex не запускав нових live API calls під час acceptance.

Документаційний інкремент змінює лише README, PHASE_6_ACCEPTANCE,
IMPLEMENTATION_PLAN, DEVELOPMENT_LOG та ADR-0006 status. Історію REVIEW збережено,
SRS/runtime не змінено. Остаточний doc HEAD має пройти Linux/Windows CI перед
звичайним merge через GitHub MCP із expected_head_sha; фактичний merge SHA і
результати ff-only local main sync фіксуються в PR7/звіті.

Прийняті Phase12 deferrals: подальше UX polishing, ширша scenario quality,
фінальна оптимізація та physical Windows11/DPI/keyboard/installer acceptance.
WSLg/Windows Server CI не є доказом фізичної Windows11 перевірки. Occasional
failure за underspecified scenario input — nonblocking robustness/diagnostic
opportunity, яку не приховано й не оголошено виправленою.

Локально до змін: tracked tree clean, owner temp/ залишається untracked і
зберігається. Baseline hashes8private/database files та metadata .venv збережено
локально у /tmp без виведення вмісту секретів. Після merge перевірити їхню
незмінність; не виконувати cleanup/reset/init-demo. Phase7 — NOT STARTED /
PLANNING; лише майбутнє погодження Web Constructor, без branch/PR/реалізації.
Phases8–12 лишаються NOT STARTED.


## 15.11.2026 — Phase 7: затверджена архітектура та початок

Власник явно дозволив complete Hybrid Component-Based Web Constructor, narrow SRS
amendment, feature branch/commits/push/PR. Не дозволено merge, ACCEPTED або Phase 8.
GitHub MCP підтвердив main 0fc97861e8e9c84393253e79c142c7c54adcb8b3; clean local tree,
fetch/ff-only success; feat/phase-7-web-constructor. PySide6 installed6.10.3,
lock/dependencies збережено. Context7/official Qt docs підтверджують off-record
profile, interceptor до Chromium network stack, navigation gate та scheme registration
before QApplication. Змінені лише погоджені normative Web sections SRS v3.0 із датою;
історичні contracts й accepted Phase 0–6 не переписуються.

### Phase 7 — contracts, renderer/isolation та persistence

WebInputV2/WebSlotsV2/WebComponentSlotV2 → typed WebPageV2/WebDraftV3; registry9
components, presets5, themes3/light-dark, deterministic scoped merges.
Unchanged groq_strict_schema accepts compact required wire schema. Focused initial
contracts+accepted agent/provenance regressions:205passed/5.35s. Renderer:7passed.
Actual Chromium integration with controlled loopback HTTP endpoint: forbidden
resources/redirects/file/data navigation blocked;3passed/2.86s після додавання
actual popup/download/form/action clicks та JS-off evidence. Chromium sandbox
залишено enabled; sandboxed test process initially exited133, successful runs
потребують дозволеного host execution, не QTWEBENGINE_DISABLE_SANDBOX.

0005_web_materials — additive table/triggers; canonical payload, source and Email
revision/digest, transactional pre/post validation, optimistic concurrency; saved
Email/context overrides mandatory.18service tests passed/29.35s;43existing Email
service regressions passed у попередньому combined run. Перший combined run мав
6failures у нових tests: Path fixture та warnings при forged nested models;
виправлено без послаблення revalidation. Downgrade з Web даними fail closed.
Old migration-head assertions updated to0005, coverage retained.

### Phase 7 — UI/editor/gateway integration

Scenario card має functional Web status/open; modal visual component editor,
actual HTML/CSS/JSON inspector, explicit Save/reopen, scoped AI та safe local actions.
Shared QRunnable/signals/request identity pattern retained; MainWindow чекає обидва
workers. --web-demo ignores .env/keys and requires owner-selected --database.
Groq Web-specific override → shared limit → GPT-OSS4096, no hard maximum;
Gemini/Email policy unchanged. Real SDK/in-memory transport, contracts/renderer
focused68passed/2.52s; no live API.

Native debug виявив application-wide Python ClipboardShortcuts filter у
PySide getWrapperForQObject при Chromium object destruction (Reload crash).
Filter тепер attaches лише focused native editors, включно з dynamic dialogs;
старі shortcut tests і нова binding regression retained. Page/view/profile explicit
release та live QIODevice wrappers прибрали shutdown crash. Focused Web UI/security/
clipboard suite33passed/22.51s with exit0. Це WSL offscreen automation, не physical
Windows acceptance; real WSLg/full/package/CI gate ще попереду.

### Phase 7 — WSLg та package gate

Real Wayland command:
`QT_QPA_PLATFORM=wayland .venv/bin/pytest tests/ui/test_web_constructor.py tests/ui/test_web_security.py tests/ui/test_clipboard_shortcuts.py tests/ui/test_email_constructor.py::test_mail_navigation_source_copy_explicit_save_reopen -q --tb=short`
— **35passed/30.20s**, exit0. Earlier mistyped Email test selector зупинив collection
без виконання; corrected exact selector наведений тут. Screenshot probe створив
нову synthetic БД у /tmp: window1100×720, page768×656, browser662×453,
Web viewport662×358, Save visible, off-record true. Screenshots compact/editor/
saved card у docs/screenshots/phase-7-web-*.png оглянуто; critical actions доступні,
сайт має незалежну світлу тему, card показує обидва saved materials/draft status.
WSLg Mesa/EGL warnings присутні, але content/clicks/scroll/rendering тести успішні;
це не native Windows11 evidence. Owner manual checklist ще не виконувався.

`uv build --offline --out-dir /tmp/cyberforge-phase7-package.CZAt7h` — sdist/wheel
success. `uv export --offline --locked --no-dev --no-emit-project --format requirements-txt`
та new /tmp venv; hash-verified offline install locked runtime dependencies,
no-deps install built wheel — success. Ізольований `python -I -m cyberforge --web-demo
--database .../startup.sqlite3 --smoke-test` — exit0. Installed-wheel script:
0005 migration, synthetic Email/Web generate/explicit Save/reopen, rendered CSS
parity та PRAGMA foreign_key_check — PASS. Wheel/source parity й exclusion of
.env/databases/credentials — PASS. Dependency/lock versions не змінено.

Додаткові focused lifecycle tests після основного WSLg run:
`QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ui/test_web_constructor.py::test_actual_signout_switch_ignores_delayed_web_result tests/ui/test_web_constructor.py::test_closing_waits_asynchronously_for_web_worker -q --tb=short`
— **2passed/6.27s**. Перевірено реальний signout→other session та asynchronous
window close з running Web worker; stale result не потрапляє в іншу сесію.
Це test-only доповнення, application code після stable full-suite start не змінено.


### Phase 7 — stable local gate та PR REVIEW

`uv run --offline --locked ruff check .` — PASS;
`uv run --offline --locked ruff format --check .` — PASS,117Python files;
`uv run --offline --locked pytest -q --tb=short` — **882passed/504.65s**, exit0,
усі783accepted Phase0–6 regressions збережено. Два test-only lifecycle cases додано
під час run після collection: окремо2passed/6.27s; application code не змінювався.
Final CI має884Linux cases/882Windows+2POSIX skips, якщо середовище не додає skips;
це очікування, не результат CI. `git -c core.whitespace=cr-at-eol diff --check`
PASS (SRS CRLF збережено). Changed-file credential/private-file scan:40files,
zero findings; .env/owner databases/credentials/environments не змінено.

Focused commits: approved SRS/ADR; contracts/renderer/agent/persistence;
UI/editor/actual browser security та worker/session lifecycle; delivery evidence/docs.
Normal push/PR→main дозволено; final SHA/CI links фіксуються після push у PR та
фінальному звіті, без circular docs commits. Phase7 — REVIEW, не ACCEPTED.
Owner WSLg/manual/live Groq acceptance pending; no live API performed by Codex.
No merge/force-push/deletion/Phase8. Physical Windows11/DPI/installer Phase12 risk.

### Phase 7 — Windows CI compact-width remediation

First PR8 HEAD6f1c9664e5a5588ecc402a1565d65a6b6d23fe6e,
[run43749813530](https://github.com/the1llus1on/cyberforge/actions/runs/43749813530):
Linux **884passed/390.38s**, Ruff/import/Qt smoke PASS. Windows **1failed,
881passed,2POSIX skips/548.28s**: new Web compact assertion860px page vs768px
viewport; усі browser security, persistence та accepted Phase0–6 tests passed.
Failure reported before further publishing; no merge.

Four adjacent native combo minimum hints were too wide under Windows font metrics.
Bounded six-character closed-control hints preserve popup choices and leave the
selected-component control the remaining width. New larger-glyph regression
retains actual viewport/no-horizontal-overflow assertions. Additional valid maximum
metadata check reproduced a separate150-character tab title overflow (1653px);
browser tab now elides visual text with full tooltip/canonical metadata preserved.
No source content, renderer, service, schema, security policy or persistence change.

Focused Web UI+actual browser security: **15passed/34.17s**. An intermediate full
run was superseded/interrupted while the additional metadata regression was fixed;
it is not counted as a passed gate. Final full run starts only after both fixes.
Original882passed gate and first CI remain historical evidence, not final HEAD
claims. UI-only remediation does not repeat packaging/migration/wheel checks under
the owner-approved workflow. Affected compact screenshot refreshed only.

Post-remediation real WSLg:
`QT_QPA_PLATFORM=wayland .venv/bin/pytest tests/ui/test_web_constructor.py::test_compact_critical_controls_and_browser_width tests/ui/test_web_constructor.py::test_compact_native_combo_metrics_cannot_widen_workspace tests/ui/test_web_constructor.py::test_long_valid_tab_title_does_not_expand_compact_browser -q --tb=short`
— **3passed/9.36s**. Original full metadata overflow відтворено окремо до виправлення
(1failed/3.93s); assertion не послаблено. Final stable Ruff lint/format PASS117files;
full rerun з обома виправленнями триває. Official NIST TN2276 source перевірено
15.11.2026; evidence link додано до ADR, NIST не застосовується до Web scoring.


Final post-remediation stable commands:
`uv run --offline --locked ruff check .` — PASS;
`uv run --offline --locked ruff format --check .` — PASS117files;
`uv run --offline --locked pytest -q --tb=short` — **886passed/506.40s**, exit0.
All783accepted regressions retained plus103Phase7 cases. Final code was frozen
before this run; only evidence/docs updated afterward. Final candidate published
only after this complete local gate. No live API, merge, owner acceptance or Phase8.
Exact new HEAD, PR8 Linux/Windows run/jobs/results recorded in PR/final delivery
without circular doc commit. UI-only fix leaves prior package/migration gate valid.

### Phase 7 — Windows native measurement before further remediation

HEAD3140a49a93034accca21b8f58796377ca40e3103, CI43752490696:
Linux886passed/358.69s plus Ruff/import/Qt smoke success; Windows881passed,
2POSIX skips,3compact failures/467.13s, page remains860px vs768px. Initial
selector attribution was incomplete: reduced hints did not remove the Windows
constraint. Assertions retained; next diagnostic-only increment adds numeric
widget/row minimum-size evidence on failure and a focused compact CI gate before
full pytest, so Windows root-cause inspection no longer waits for unrelated suites.
Local focused compact3passed/9.68s, Ruff117files PASS. Application code unchanged
in this diagnostic increment; prior886-test local gate remains the application
baseline. No security/persistence failures, live calls, merge or Phase8.

### Phase 7 — measured Windows action-row root cause

Diagnostic HEAD04393b6fdcafb2b93da72fb072557162345d04e3,
CI43753536827 focused Windows gate supplied full numeric evidence in seconds:
page min860; selector row548 (692with larger font), browser min142;
**bottom action row min828** from button hints232/232/218/134 + spacing12.
Page margins32 yield860. This identifies the remaining constraint directly;
selector/metadata bounds alone could not remove it. No content or credentials
are included in numeric diagnostics. The compact assertions remain unchanged.

Move «Редагувати сайт» to the existing top row, matching accepted Email layout;
keep code/generate/save below preview. No labels shortened, font reduced, preview
permanently shrunk or checks weakened. Native-pressure regression now enlarges
both combo and button fonts. Focused Web UI/security **15passed/35.12s**;
real WSLg compact3cases **3passed/11.22s**. Refreshed screenshot inspected:
1100×720, page768×656, browser662×453, viewport662×358, Save visible/off-record true.
Full stable regression rerun before publishing this measured correction.

Portable native regression уточнено за фактичними Windows measurements:
minimum button hint232px замість припущення про pixel font conversion; assertion
і component/viewport bounds не змінені. Test-only уточнення виконано під час full
run, application code frozen. Focused compact **3passed/9.86s**, real WSLg measured
hint case **1passed/4.33s**. Повний CI повторить актуальну версію цього тесту.


Measured-fix stable local gate before publishing:
`uv run --offline --locked ruff check .` — PASS;
`uv run --offline --locked ruff format --check .` — PASS117files;
`uv run --offline --locked pytest -q --tb=short` — **886passed/518.91s**, exit0.
Portable measured-width test-only refinement separately3passed/9.86s and WSLg
1passed/4.33s; product code remained frozen during full run. Existing783regressions
retained. Publish only after this successful gate; exact-head Linux/Windows CI
follows, including focused compact gate first and then complete886-case suite.
No live API/merge/owner acceptance/Phase8; UI-only change, package policy unchanged.


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

Acceptance increment: документаційні зміни лише в README, ADR0007, acceptance,
plan/log. SRS/runtime/tests/dependencies/migrations не змінено. Локальний full suite
не повторюється для docs-only; required final-head CI виконує обидві платформи.
Перед merge перевіряються base/main, scope, mergeability та expected_head_sha.

## 15.11.2026 — Phase 8: дозволений початок

Вкладений owner request явно затвердив ScenarioLinkV1, RubricDefinitionV1 та
окремі audited group grants; дозволив narrow SRS amendment, branch/commit/push/PR.
GitHub MCP main SHA b84e2fbd… підтверджено; tree clean. Перший sandbox fetch
відхилено через read-only .git; elevated authorized fetch/ff/switch успішні.
Існуючі owner .env/DB/credentials/environments не відкривалися й не змінювалися.
Прочитано accepted Scenario/Email/Web/RBAC/contracts/migrations/UI та relevant
SRS/Phase6–7/ADR5–7. Existing BEGIN IMMEDIATE та material/parameter revisions
збережено. Context7 SQLAlchemy functional docs request успішний; dependencies без змін.
Нормативні уточнення лише в SRSv3.0 з датою; ADR0008 і plan фіксують рішення/gates.
Contracts: typed link, bounded rubric registry, reviewed snapshot, report/receipt,
manifest/internal navigation; actual scoring/attempts/AI поза Phase8.

### Phase8 — contracts/integration/persistence gate

Додано closed ScenarioLinkV1, rubric registry/declarations, reviewed sources/report,
review receipt та manifest/internal-navigation contracts. Additive0006 додає6tables,
immutable-source/history triggers, REPLACE guards і automatic grant audit transitions.
Existing published-version/archive/Email/Web triggers збережено. Explicit new draft
копіює тільки parameters; publication status не збільшує content revision.

Початковий focused run виявив collision назви audit trigger; усунуто до GUI gate.
Наступний run:68passed до нового forged-rubric тесту, який виявив serializer warning
перед revalidation. warnings=False лише для serialization, повна local validation
збережена. Повторний rubric focused:12passed/16.36s. Детальні combined security/
persistence/regression результати додаються після завершення. Dependency versions
незмінні; uv cache перенаправлено в /tmp через read-only default cache.

### Phase8 — completed focused persistence/UI increments

`.venv/bin/pytest tests/test_scenario_integration.py tests/test_web_materials.py tests/test_email_materials.py tests/test_scenarios.py tests/test_groups_database.py -q --tb=short`
— **172passed/234.24s**. Включено75new Phase8 cases: exact source/link, forbidden
roles/groups, warning ack, stale receipts, atomic rollback/concurrent publication,
direct UPDATE/DELETE/REPLACE denial, immutable historical references, grant/revoke/
regrant audit, current membership/archive/restore/latest eligible та0005→0006.

`.venv/bin/pytest tests/ui/test_scenario_integration.py tests/ui/test_scenarios_ui.py -x -q --tb=short`
— **45passed/120.82s**. Додано integrated constructor workspace з read-only Email/
Web review, link/rubric saves, detailed readiness, group picker, final confirmation,
history/grants, explicit next draft. Save/Discard/Remain й session guards retained.
Зелений saved матеріал не означає publication. Додатковий precision review замінив
rubric spinbox на validated numeric text, щоб не округлювати довільні positive
saved weights; focused precision/actual Web/WSLg gate виконується окремо.

### Phase8 — WSLg та installed-wheel gates

Real Wayland command:
`QT_QPA_PLATFORM=wayland .venv/bin/pytest tests/ui/test_scenario_integration.py tests/ui/test_web_security.py tests/ui/test_email_constructor.py::test_mail_navigation_source_copy_explicit_save_reopen -q --tb=short`
— **11passed/44.36s**, exit0; actual browser/isolated profile, network-isolation
regressions, native main CTA/weight precision/disposal/session/compact covered.
Synthetic compact screenshot probe1passed/2.77s; docs/screenshots/phase-8-*.png
переглянуто, main/footer/modal controls reachable1100×720. Automation не є owner
functional acceptance або physical Windows11. PASS corrections уточнено, щоб
не показувати failure action для успішної перевірки; focused2passed/3.91s.

Додаткові persisted corruption/attestation/exact groups/concurrent revoke/restart:
8passed/13.14s. `uv build --offline --out-dir /tmp/cyberforge-phase8-package`
PASS (UV_CACHE_DIR=/tmp/cyberforge-phase8-uv-cache). Перший isolated install із
новим порожнім cache fail offline (alembic відсутній); повторено з наявним cache,
без мережі,58hash-verified runtime packages installed у новий /tmp venv, wheel install
PASS. `python -I` installed-package script0005→0006 з existing synthetic Email/Web,
full integration/review/publish/grants/audit/access/new draft/FK PASS. Installed
Qt `--web-demo --database /tmp/.../smoke.sqlite3 --smoke-test` exit0.
Wheel/source parity85Python files, no private data PASS; source/dependency versions
не змінено після wheel build. Final full suite виконується; CI додає ранній
Phase8 native compact gate перед existing full suite.

Офіційний NIST TN2276 перевірено через primary csrc.nist.gov: email detection
difficulty, не learner score/Web metric. GitHub MCP remote .github listing
підтвердив лише workflows; PR templates не знайдено локально або remote .github.

### Phase8 — migration-chain rollback hardening

Додатковий isolated probe підтвердив дефект sqlite3 legacy DDL: downgrade через
empty0006 до0004 відхиляється existing0005 Web data guard, але без real BEGIN
міг видалити0006tables/triggers, залишивши Alembic stamp0006. Owner DB не зачіпалася.
0006тепер перед upgrade/downgrade перевіряє DBAPI in_transaction і починає реальний
BEGIN IMMEDIATE, якщо його ще немає. Вже відкриту транзакцію не дублює; existing
AccountService/Database semantics не змінює. Весь migration chain rollback
відновлює tables/triggers/stamp, включно з відмовою попередньої фази.
Новий regression порівнює complete tables/triggers/stamp і перевіряє usable link/Web
після rollback. Focused migration gates5passed/8.50s. Потрібен повторний stable full
suite і rebuild/installed-wheel, оскільки змінилася packaged migration; перший full
run не використовується як остаточний evidence цього hardening.

Pre-hardening full run завершився976passed/686.21s; це історичний evidence,
не остаточний gate після DDL fix. Final screenshot refresh1passed/3.28s та
overview/CTA screenshots оглянуто; PASS corrections не показують failure actions.
Rebuilt wheel повторно встановлено офлайн; installed0005→0006/full publication/
audit/access/new draft/FK і new explicit-database startup smoke PASS, source parity
PASS. Context7 підтвердив public Connection.connection.driver_connection API та
sqlite3 legacy DDL behavior. Нових dependencies немає; runtime phase boundaries незмінні.

### Phase8 — stable final local gate / REVIEW

`UV_CACHE_DIR=/tmp/cyberforge-phase8-uv-cache QT_QPA_PLATFORM=offscreen uv run --offline --locked pytest -q --tb=short`
— **977passed/673.63s**, exit0. Усі886accepted Phase0–7 regressions збережено,
91Phase8 cases added (84service/security/migration та7UI). Після початку цього
final run application/test Python code не змінювався; тільки документація.
`UV_CACHE_DIR=/tmp/cyberforge-phase8-uv-cache uv run --offline --locked ruff check .`
та `... ruff format --check .` PASS,126Python files. Focused/package/WSLg evidence
вище; final rebuilt wheel parity85files і new-database Qt smoke PASS.
`git -c core.whitespace=cr-at-eol diff --check` PASS, SRS CRLF збережено;
changed-file/private-key scan27files/zero findings, owner data поза scope.

Статус Phase8 REVIEW. Owner manual checklist у PHASE_8_ACCEPTANCE; owner acceptance
не приписується automation. No live Groq/Gemini, attempts/events/scoring/analytics,
merge/force-push/branch deletion або Phase9. GitHub MCP повторно підтвердив main
b84e2fbd… незмінним. Feature commits auditable; final push/PR/exact-head Linux та
Windows CI фіксуються у PR і delivery report без circular evidence commits.

## 16.11.2026 — Phase8 independent review F8-01/F8-02 remediation

Owner дозволив targeted investigation/fix у PR9 від reviewed
c8f95eb786b850e9171054aed72ea1a5a35271f7. GitHub MCP підтвердив exact head/base main,
PR open/unmerged; local tree clean, fetch/ff-only current branch без змін. Жодних
reset/rewrite/merge/ACCEPTED/Phase9. Relevant SRS §§4.8–4.9,11.6,14/ADR0008 та
current service/UI/contracts/tests перевірено; owner .env/DB/keys не використовувалися.

**Baseline reproduction**, до implementation edits:
`.venv/bin/pytest tests/test_scenario_integration.py tests/ui/test_scenario_integration.py -k 'f8_01 or f8_02' -q --tb=short`
— **4failed/4passed/91deselected/26.12s**. Три actual Qt clicks відкривали final
confirmation при empty/unauthorized/stale groups. Historical v1 preview після
load_history мав selector publication2. Тести фіксували це до змін.

**F8-01 уточнення review:** заявлений uncaught Pydantic ValidationError не
відтворено. На reviewed HEAD confirm() already rejects groups BLOCKED через
existing any(BLOCKED except instructor_confirmation); усі4direct-service cases
empty/unauthorized/reassigned/deleted давали controlled ApplicationError, zero
review receipts/publications. Confirmed root cause — GUI enablement лише за
technical_ready, без групового gate/pre-dialog recheck. Додано explicit empty та
current group authorization в confirm() до InstructorConfirmationV1; contract
min_length=1 незмінний. GUI enablement враховує groups/checks, click preflight
оновлює authorization/source fingerprint до final dialog; service write transaction
зберігає незалежну повторну валідацію, включно з reassignment під час modal.

**F8-02 root cause:** load() clear/addItem автоматично обирав first/latest pub,
а load_history() не відновлював selected ID. refresh_grants/change_grant читали
currentData незалежно від displayed expected/preview. Тепер QSignalBlocker
охоплює rebuild і відновлення publication, відповідної opened version; draft
не має grant target до явного вибору historical publication. Selection synchronizes
expected/read-only Email/Web preview/grants/audit. Перед grant read/write перевіряється
publication identity/version; modal вказує exact scenario/version/publication/group,
Cancel нічого не пише, після modal recheck не дає redirect write на іншу publication.
Unsaved Remain відновлює попередній selector; no automatic grant target switch.
Official Qt QSignalBlocker context-manager/currentIndexChanged behavior звірено через
Context7. Нових API/dependencies/міграцій або SRS requirement changes немає.

Initial post-fix reproduction gate8passed/26.56s; expanded actual Qt group/modal/
history tests6passed/40.53s. Final focused/regression/full/WSLg/CI results follow.

### F8-01/F8-02 — stable focused/WSLg gates

Final focused command:
`.venv/bin/pytest tests/test_scenario_integration.py tests/ui/test_scenario_integration.py -k 'f8_01 or f8_02' -q --tb=short`
— **11passed/91deselected/63.64s**. Включено actual click path і receipt zero writes,
після-dialog reassignment, two-publication grant targeting, real modal Cancel/Confirm,
refresh/reload/reopen, selection change during modal, immutable sources/manifest,
та unsaved draft Remain/Discard. Before-fix4failures збережено вище як reproduction.

Real WSLg:
`QT_QPA_PLATFORM=wayland .venv/bin/pytest tests/ui/test_scenario_integration.py -k 'f8_01 or f8_02' -q --tb=short`
— **7passed/7deselected/59.55s**, exit0. Це Codex automation на isolated synthetic DB,
не owner manual або native Windows11 acceptance. Ruff lint/format126Python files
PASS. Ширші regressions і final full988case run виконуються; application/test code
після початку full run стабільний. Packaging/dependencies/migrations/startup не
змінено, повторний build/wheel не потрібен для цих service/UI corrections.

Relevant regression command
`.venv/bin/pytest tests/test_scenario_integration.py tests/ui/test_scenario_integration.py tests/ui/test_scenarios_ui.py -k 'not f8_01 and not f8_02' -q --tb=short`
initial restricted execution завершився133 під час actual Chromium setup без
assertion report (accepted environment behavior, documented in Phase7). Повторено
ту саму команду через allowed host execution; Chromium sandbox не вимикався.
Final full suite також запускається через host execution. Owner data не зачіпалася.

Повторний relevant regression run через allowed host execution —
**131passed/11deselected/287.78s**, exit0. Це всі existing integration/persistence/
ScenarioPage UI cases у targeted modules;11new finding tests виконано окремо.

### F8-01/F8-02 — final local gate / REVIEW

`UV_CACHE_DIR=/tmp/cyberforge-phase8-uv-cache QT_QPA_PLATFORM=offscreen uv run --offline --locked pytest -q --tb=short`
— **988passed/857.37s**, exit0;977previous cases retained та11new finding cases.
Після початку final full run application/test code не змінювався.
`UV_CACHE_DIR=/tmp/cyberforge-phase8-uv-cache uv run --offline --locked ruff check .`
та `... ruff format --check .` — PASS,126Python files. `git -c core.whitespace=cr-at-eol diff --check`
PASS. Changed-file scan7files: no private-key patterns, no owner DB/.env in scope.

Виправлення: application/scenario_readiness.py та ui/scenario_integration.py;
regressions: tests/test_scenario_integration.py і tests/ui/test_scenario_integration.py;
docs: цей log, IMPLEMENTATION_PLAN і PHASE_8_ACCEPTANCE. No dependencies/schema/
canonical artifact changes. No real Groq/Gemini requests; only synthetic isolated DB.
Owner manual/physical Windows11 acceptance не заявляються. Phase8 REVIEW.
Final commit/push та exact-head Linux/Windows CI evidence фіксуються в existing PR9
і фінальному звіті без circular documentation commits. Merge/ACCEPTED/Phase9 заборонені.

## 16.11.2026 — Phase8 owner-reported WSLg Web preview failure

Scope: owner authorized targeted investigation/fix in existing PR9, baseline
988bc421e3458678a9e4dca05a6ccdbd6b113e3c. GitHub MCP confirms exact head, main base,
open/unmerged; clean tree and fetch/ff-only. Relevant SRS §§3.13,6.6,16.3–16.5,21,
ADRs0007/0008, startup/custom scheme/renderer/browser/dialog cleanup and tests read.
No owner .env/keys/DB/credentials inspected or modified; no live AI. All graphics
experiments use one NEW synthetic published scenario/database under /tmp, seeded
with explicit Mock demo services and private random demo credentials (never printed).
Installed Python3.12/PySide6/Qt6.10.3, WSL Linux, Wayland; /dev/dxg absent in this
runner. Only allowlisted graphics environment settings inspected; no full env dump.

### Evidence and verified cause

Restricted Wayland startup fails before QApplication: wl_display Operation not
permitted, process134/SIGABRT. This is runner display isolation, not the owner's
preview failure. Subsequent display tests run as the SAME UID1000 with host display
access: no sudo, root privileges, package installs or system graphics changes.

Production main --web-demo -> real demo-instructor login form -> saved published
scenario -> actual ScenarioPage integration button -> Web tab reproduced failure.
Default graphics logs contain the owner's EGL/Mesa/Zink messages. Qt/Chromium then
report llvmpipe, GPU blocklisted/software compositor. The GUI timer remains alive;
no renderer-termination signal and no whole-application native crash observed.
Trace: page.setUrl causes a transient native dialog hide while Qt changes rendering
surface; QDialog.exec returns0 WITHOUT finished/rejected. ScenarioPage's synchronous
continuation schedules deleteLater on the loading dialog; no loadFinished arrives.
The same failure occurs with only --disable-gpu. Mesa warnings therefore do not
establish a fatal GPU failure; a verified application modal-lifetime defect causes
loss of the preview. The owner's exact process-exit state remains unconfirmed.

A diagnostic harness initially needed independent timer driving (same-timer callbacks
cannot drive a nested exec while their own timeout slot remains active); corrected
before extracting the regression. Actual production-path regression on unchanged
code: **1failed/4.30s**, assertion 'Web initialization destroyed the integration dialog',
with the same Mesa warnings. Existing tests only showed IntegrationDialog directly,
so they did not exercise ScenarioPage.open_integration's nested exec continuation.
A preload experiment rendered successfully before modal entry; the chosen smaller
lifecycle fix follows Qt's recommended asynchronous open/finished API instead of
forcing eager hidden WebEngine initialization or changing rendering defaults.

Official version-matched Qt6.10.3 references, checked through Context7/official web:
https://doc.qt.io/qt-6.10/qdialog.html#exec
https://doc.qt.io/qt-6.10/qtwebengine-features.html#hardware-acceleration
https://doc.qt.io/qt-6.10/qtwebengine-debugging.html
https://doc.qt.io/qt-6.10/qtwebengine-platform-notes.html
Unversioned Qt URLs redirect to newer docs; implementation decisions use6.10 docs.

### Fix and controlled graphics comparisons

ScenarioPage retains a single window-modal IntegrationDialog via open()/finished;
transient hide no longer unwinds a nested loop or deletes a loading page. Finished
clears ownership, refreshes the same authorized scenario, and schedules deletion;
forced/session changes skip stale refresh. Window-manager close explicitly emits
completion after the existing Save/Discard/Remain guard. Duplicate opens reuse
the current dialog. WebBrowser retains accepted view->page->profile disposal order.
loadFinished(false)/renderProcessTerminated show Ukrainian recovery instructions;
logs contain only status/code, never URLs/content/credentials. Reload stays on the
current approved internal resource; no fake automatic graphics fallback.

Same isolated DB, actual production main/login/button path,3open/render/close cycles
and4Email/Web switches per cycle; first default and --disable-gpu baseline failed
as above, all following results are AFTER the lifecycle fix:

| Single override | Exit | Rendered loads | Renderer terminations | EGL warnings | DB unchanged |
| --- | --- | --- | --- | --- | --- |
| none, Wayland default | 0 | 3 | 0 | 8 | yes |
| QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu | 0 | 3 | 0 | 4 | yes |
| QT_QUICK_BACKEND=software | 0 | 3 | 0 | 4 | yes |
| LIBGL_ALWAYS_SOFTWARE=1 | 0 | 3 | 0 | 0 | yes |
| GALLIUM_DRIVER=llvmpipe | 0 | 3 | 0 | 6 | yes |
| QT_QPA_PLATFORM=xcb | -6/SIGABRT | 0 | 0 | 0 | yes |

Each override used alone, established BEFORE QApplication by the child process
environment. Screens had actual nonempty page text and19sampled pixel colors,
GUI heartbeat continued;3view/page/profile sets invalidated after explicit close.
Xcb cannot initialize without libxcb-cursor0 here; no packages installed and xcb
not recommended as a verified workaround. Software flags do not repair the original
exec defect; no app-wide rendering configuration/default was introduced. Qt's
existing explicit environment overrides remain supported, with no Windows leakage.

Initial new test errors (waitUntil predicate returning[]; synthetic enum-valued
signal emit unsupported by PySide6.10) were test harness defects. Predicates fixed;
portable diagnostic handler test plus real child-process termination cover the
supported signal. Real renderer SIGTERM test passed: GUI alive, Ukrainian error,
internal Reload succeeds with a new renderer, sources unchanged. Linux renderer
status Seccomp2/NoNewPrivs1 and no --no-sandbox verified before terminating ONLY the
PID returned by this page. Baseline process and renderer were never run as root.

### Preview correction — stable focused gates

Before-fix actual production-button WSLg regression1failed/4.30s; after lifecycle
fix the same test1passed/6.21s,3cycles and explicit view/page/profile disposal.

Default real WSLg command:
`QT_QPA_PLATFORM=wayland .venv/bin/pytest tests/ui/test_scenario_integration.py tests/ui/test_web_security.py tests/ui/test_web_constructor.py -k 'not actual_signout and not closing_waits and not generation and not manual and not refinement' -q --tb=short`
— **30passed/3deselected/173.37s**, exit0. Includes all18Phase8 UI cases, accepted
actual browser/network isolation, real renderer termination/reload, F8-01/F8-02
regressions, modal-close/session guards and compact layout. Four new cases added.

Single software override, set before QApplication:
`QT_QPA_PLATFORM=wayland QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu .venv/bin/pytest tests/ui/test_scenario_integration.py tests/ui/test_web_security.py tests/ui/test_web_constructor.py -k 'actual_constructor_button or renderer_ or production_dialog or actual_engine or actual_clicks or real_engine or compact or long_valid_tab_title' -q --tb=short`
— **11passed/22deselected/35.28s**, exit0. Actual Chromium isolation remains enforced.
No --no-sandbox, QTWEBENGINE_DISABLE_SANDBOX, disabled web security or remote access
introduced. Default rendering and software override both preserve isolation.

Ruff lint/format126Python files PASS; diff check PASS. Full offline992case suite
running via unprivileged host execution. No Python source/test changes after its
start; only documentation evidence. No entry point/config/dependency/migration
changes, so repeated package/wheel checks not required for this UI lifecycle patch.
CI's early Phase8 gate now includes the real Constructor-button lifecycle case,
before full suite, to cover the path missed by show-only tests. No owner manual
acceptance claimed; default native hardware GPU was unavailable in this runner.

Final default-backend native-window trace independently confirms the surface
transition: SELECT_WEB_TAB -> dialog hide inside page.setUrl -> old QWindow.destroyed
-> loadFinished(true), on EACH of3cycles after the async fix. The IntegrationDialog
itself survives until explicit close; zero renderProcessTerminated signals.
One /tmp synthetic screenshot inspected: published version identity and actual
rendered Web content visible, read-only display address, Close reachable. No extra
repository screenshot/audit artifact. This confirms native-window recreation rather
than inferring it solely from Mesa diagnostics or a dialog hide event.

### Preview correction — final local gate / REVIEW

`UV_CACHE_DIR=/tmp/cyberforge-phase8-uv-cache QT_QPA_PLATFORM=offscreen uv run --offline --locked pytest -q --tb=short`
— **992passed/828.97s**, exit0. All988previous cases retained plus4new preview cases.
No Python source/test changes after full-suite start. Ruff check and format --check
PASS,126Python files. Diff/private-file scan PASS,9changed files; owner .env/DB/keys
untouched. Actual Chromium sandbox/isolation retained; no root/sudo or new packages.

Files: ui/scenario_page.py, scenario_integration.py, web_browser.py;
tests/ui/test_scenario_integration.py; early CI lifecycle selector; existing
IMPLEMENTATION_PLAN/DEVELOPMENT_LOG/PHASE_8_ACCEPTANCE/ADR0008. No source snapshots,
new database schema/dependencies, startup config changes or new navigation modes.
The verified premature-modal-deletion defect is fixed; a fatal exit on the owner's
specific GPU/host was not established by the supplied warnings or reproduced here.
Owner must repeat the documented real button/open/close/reopen workflow. Full app
native failures outside supported Qt signals still require the safe diagnostic log.
Phase8 remains REVIEW. Exact final commit and Linux/Windows CI run/results follow
in existing PR9 description/final report, avoiding circular evidence-only commits.
No merge, ACCEPTED, Phase9, force-push or history rewrite.


## 16.11.2026 — Phase8 UX: три кроки підготовки (REVIEW)

Owner-approved redesign у чинній feature branch/PR9, baseline34e3198; GitHub MCP
підтвердив open/unmerged/main base. Єдину початкову локальну зміну AGENTS.md
(власника) збережено й виключено з task commit. SRS §§3–4,6.10,11–12,14,16,21,
plan/log/acceptance, ADR0007/0008, service contracts та UI/security tests прочитано.
Немає live AI, роботи з owner .env/keys/DB, migrations/dependencies/startup changes.

План: stable three-step modal structure → material cards/internal previews/link →
compact registry rubric → service-derived readiness/attestation/result → separate
history/access → focused/full/WSLg/final-head CI. Owner English session/PR language
застосовано; Ukrainian application UI та existing documents збережено.

Context7 functional read PASS (official Qt for Python). Qt документація рекомендує
open()/finished замість nested exec; QStackedWidget володіє inserted widgets.
https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QDialog.html
https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QStackedWidget.html
Existing safe WebBrowser/disposal/security та service/persistence implementations
залишено без змін. Лише native UI presentation/interaction redesign.

Інкременти1–5 реалізовано:3steps, responsive materials, inert exact previews,
optional read-only technical details, grouped8criteria, lossless weights/preset,
readiness checklist/corrections/groups/review, explicit publish/result, separate
history доступний із newer draft. Save/Discard/Remain та session clearing збережено;
baselines відновлюються при Discard, relevant edits скидають review. Історичний
preview показує exact version; link/rubric read-only summary доступний окремо.

Перший editor/precision probe:2passed/8.17s. Existing18Phase8 UI regressions adapted
від obsolete tab indexes до behavioral navigation:18passed/161.52s, including
F8-01/F8-02, source/manifest immutability, real browser/renderer recovery, production
button3cycles, signout/Close/X та compact viewport checks. Жоден prior case не видалено.
Додаткові redesign tests і backend regressions виконуються; stable gates нижче.
Default uv cache був read-only в sandbox: використано task-specific
UV_CACHE_DIR=/tmp/cyberforge-uv-cache з --no-sync та чинним .venv; dependency updates
не виконуються. Host-access Qt tests працюють без root/sudo чи sandbox disablement,
лише з synthetic pytest fixtures. Owner manual acceptance не стверджується.

### UX redesign — focused / real WSLg gates

- `UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest tests/ui/test_scenario_integration.py -q --tb=short`
  (prior18adapted cases, before adding new coverage): **18passed/161.52s**.
- Same module `-k redesign -q --tb=short`, initial new behavior set:
  **16passed/18deselected/230.71s**. Additional final-confirmation, compact/keyboard
  and group-reassignment cases retained in final complete suite.
- `UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest tests/test_scenario_integration.py -q --tb=short`:
  **88passed/150.55s** (RBAC, publication, persistence, integrity, migration, races).
- `QT_QPA_PLATFORM=wayland CYBERFORGE_UX_SCREENSHOTS=docs/screenshots UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest tests/ui/test_scenario_integration.py -k 'end_to_end_result or actual_final_confirmation or resizing_keyboard' -q --tb=short`:
  **3passed/33deselected/19.08s**. Actual final modal Cancel/Publish,600×580 and
  960×680, stacked/side-by-side cards, keyboard Space/focus, result/history.
- After visual spacing correction, same prefix/module with
  `-k 'rubric_groups or end_to_end_result' -q --tb=short`:
  **2passed/34deselected/10.36s**. All8collapsed rows visible in viewport; both exact
  persisted previews, explicit publication and seven screenshots visually inspected.
- Final real WSLg command:
  `QT_QPA_PLATFORM=wayland CYBERFORGE_UX_SCREENSHOTS=docs/screenshots UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest tests/ui/test_scenario_integration.py tests/ui/test_web_security.py tests/ui/test_web_constructor.py -k 'not actual_signout and not closing_waits and not generation and not manual and not refinement' -q --tb=short -o faulthandler_timeout=90`
  — **48passed/3deselected/502.92s**. Includes all36Phase8 UI cases existing at
  collection, F8-01/F8-02, real browser isolation, renderer termination/internal
  Reload, production entry3cycles, compact/keyboard/Close/signout. The later extra
  group-assignment-refresh case is included in the final full offline suite.
- Supplemental existing production-path test with temporary observation plugin:
  `QT_QPA_PLATFORM=wayland PYTHONPATH=/tmp UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest -p cyberforge_ux_close_probe tests/ui/test_scenario_integration.py -k actual_constructor_button -q -s --tb=short`
  — **1passed/36deselected/7.61s**. Plugin only routes existing final reject calls
  through actual Close button (cycles1/3) and window-manager closeEvent (cycle2),
  after return-to-materials; all3engines disposed and main GUI alive. Original
  lifecycle test retains its exact source equality and view/page/profile validity
  assertions. Temporary plugin is outside repository, not runtime code.
- Real renderer test verifies off-record profile, own-renderer PID termination,
  Seccomp2/NoNewPrivs1/no --no-sandbox, responsive application, Ukrainian diagnostic
  and successful internal-only reload. Existing network/JS/file/navigation tests
  retained. Default graphics; no unsafe flags or system/package changes.
- `UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync ruff check .` PASS;
  `UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync ruff format --check .` PASS
  (**127Python files**); `git diff --check` PASS.

No runtime/test changes after stable full-suite start. Documentation/evidence only.
No repeat wheel/build gate: UI-only change; no dependencies/migrations/installation/
entry point changes. Existing package evidence retained and CI startup smoke remains.

### UX redesign — stable full local gate / REVIEW

`UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest -q --tb=short -o faulthandler_timeout=120`
— **1011passed/1091.99s**, exit0. All992prior cases retained plus19new redesign
cases (37Phase8 UI cases total). Includes final authorized-group refresh/ack reset,
invalid weights, missing/stale sources, source/manifest integrity, RBAC/migrations/
concurrency, real browser lifecycle/security, unrelated accepted regressions.
Ruff lint/format127files PASS; staged diff check PASS. No runtime/test changes
since this run started; only documentation evidence updated afterwards.

15scoped files:3UI modules (including new progressive-disclosure/responsive helpers),
existing UI test module,4documents,7synthetic screenshots. No SRS/backend/service/
contract/schema/dependency/WebBrowser/startup changes. Owner AGENTS.md edit remains
unstaged and excluded. GitHub MCP rechecked PR9 main base/open/unmerged/unchanged
remote head34e3198 before publication. Local feature commit/push authorized; final
exact-head Linux+Windows CI will be recorded in PR9/delivery after push, without a
redundant documentation-only commit. Phase8 remains REVIEW; no owner acceptance,
merge or Phase9. Native Windows11/GPU/DPI/installer acceptance remains Phase12 risk.

## 16.11.2026 — UX Windows CI: responsive-card minimum-size correction

First redesign commit95ebf362d3d6ac9076fce9c2e3833cae55617a55, workflow43856088261:
GitHub App MCP confirms Linux **1011passed/633.37s**, all steps SUCCESS. Windows
**1failed/1007passed/3POSIX-only skips/784.81s**; Ruff127files and early compact/
production-lifecycle gates passed. Failure: new600×580 resize assertion found
content856px inside viewport556px. Reported failure to owner before further push;
no merge or acceptance. Data-integrity, RBAC, migration and WebEngine
lifecycle/security cases passed; this was a real narrow-layout defect.

Confirmed root cause: responsive cards chose horizontal/vertical layout from their
own current width. Native card minima could keep the content wider than viewport,
preventing a resize below the hardcoded threshold and therefore preventing stacking.
Local deterministic reproduction adds420px minimum to each card (no font hacks):
old code **1failed/1passed/36deselected/11.47s**, same material-step overflow864>556.
Assertions retained; native-pressure case added as a second resize-test parameter.

Correction: MaterialCards watches the scroll viewport's Resize events and chooses
direction from available viewport width minus body margins, including actual card
minimum widths and spacing. It no longer depends on its own potentially oversized
width. Geometry is invalidated after direction changes; no WebEngine ownership or
services/persistence changes. Early CI Phase8 gate now includes resizing_keyboard,
so ordinary and forced-native-minimum cases run before the complete suite.

After correction, same local resize test: **2passed/36deselected/9.90s**.
`QT_QPA_PLATFORM=wayland UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest tests/ui/test_scenario_integration.py -k 'compact_page or actual_constructor_button or resizing_keyboard or end_to_end_result' -q --tb=short`
— **5passed/33deselected/35.64s**. Real viewport stacking, keyboard, actual3cycle
WebEngine lifecycle and full publish/history flow retained. Existing wide-layout
screenshots remain representative; only narrow-layout behavior changed.
Ruff lint/format127files and diff check PASS. New full suite runs on stable corrected
sources; final exact-head Linux/Windows evidence will follow in PR9/delivery.

MCP capability limitation: direct GitHub PAT-backed check-runs read returned403.
GitHub App MCP Actions run/job/log reads succeeded and supplied the actual failure
and platform results; PR metadata/update via GitHub MCP also succeeded. Context7
read succeeded. Credentials/configuration were not read or changed.

Context7 official Qt check for the correction: QScrollArea.widgetResizable uses
viewport geometry; QObject.eventFilter must preserve normal event delivery when
observing Resize. The implementation delegates to the base filter and never deletes
the watched widget. References:
https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QScrollArea.html
https://doc.qt.io/qtforpython-6/PySide6/QtCore/QObject.html

### Native-width correction — final stable local gate

`UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest -q --tb=short -o faulthandler_timeout=120`
— **1012passed/1403.08s**, exit0. All992prior cases plus20new redesign cases retained;
38Phase8 UI cases include both normal and forced-native-minimum resize variants.
Ruff lint/format127files PASS, diff check PASS. Source/tests unchanged throughout
this corrected complete run; only evidence docs appended. Focused resize2PASS and
real WSLg compact/lifecycle/resize/publish-history5PASS precede this full gate.

Corrective commit scope8files:2UI modules, existing UI tests, early CI gate and
4documents. Combined redesign scope16files including the original7synthetic
screenshots and3UI modules; owner AGENTS.md remains excluded. No backend/contracts/
schema/dependencies/WebBrowser/security/startup changes. Commit/push the verified
correction in existing branch/PR9; both platforms must pass on new exact HEAD.
Final CI run/results will be recorded in PR9/delivery, preserving initial Windows
failure history here. Phase8 REVIEW; owner acceptance pending; no merge/Phase9.

## 16.11.2026 — UX Windows early gate: acknowledgement wrapping

Correction commit2a223b89a11ae81c14045c420e3a3f59f4e05d9d, workflow43886284383:
early Windows gate now reaches step2 at600px, confirming material stacking fixed.
It reports2resize failures/2passes/34deselected/13.49s: publication content686px
in556px viewport, in both ordinary and card-pressure variants. Full Windows suite
is correctly skipped after early failure; Linux complete suite continues.

Root: native QCheckBox multiline text minimum-size hint. Local regression models
668px native multiline hint (plus18px content margins = actual686px), preserving
all original widths and assertions. Before correction: **1failed/1passed/11.12s**,
exact same step2 686>556. Native card420px pressure remains covered as well.

Use native textless QCheckBox plus wrapping plain-text CheckLabel with buddy/full
Ukrainian accessible name. Label click focuses/toggles the native checkbox; keyboard
Space remains native. No review semantics/service checks changed. The regression
also verifies label click, focus ownership and Space toggling, with an authorized
group selected to keep the source/group acknowledgement stable during interaction.

After correction, narrow tests: **2passed/36deselected/10.56s**.
`QT_QPA_PLATFORM=wayland CYBERFORGE_UX_SCREENSHOTS=docs/screenshots UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest tests/ui/test_scenario_integration.py -k 'compact_page or actual_constructor_button or resizing_keyboard or end_to_end_result or actual_final_confirmation' -q --tb=short`
— **6passed/32deselected/39.48s**, including actual final Cancel/Publish, full
publish/history, native-pressure cases and3WebEngine cycles. Screenshots refreshed;
new publication view visually inspected. Ruff127files/diff checks PASS. New stable
full run follows; no further source/test edits during it. Backend/contracts/DB/
WebBrowser/security/dependencies unchanged. Owner AGENTS.md still excluded.

Second-head Linux CI completed SUCCESS: **1012passed/456.97s**, Ruff127files,
Web compact3PASS, strengthened preparation early gate4PASS and startup smoke PASS.
This is workflow43886284383 / head2a223b8; Windows early acknowledgement-width
failures remain recorded above. The final correction requires a new exact-head
CI run on both platforms after its fresh complete local gate.

### Final verification harness isolation

First full run of wrapped-checkbox candidate: **1011passed/1setup error/1418.65s**.
The error occurs in the following integration fixture's apply_theme(qapp) at
app.setStyle("Fusion"), with an old AdminPage.heightForWidth callback reporting
missing layout. It is a Qt fixture/global-style cleanup error, not an assertion
in the wrapped-checkbox interaction. Nothing was committed/pushed from this run.

Keep AdminPage and application behavior unchanged. The integration fixture now
reuses an already identical STYLE instead of repeatedly resetting global Qt style.
Native multiline-size pressure uses a test-local QCheckBox subclass substituted
only into the integration module, rather than monkeypatching Qt's global class.
This retains the668px native-hint regression while isolating Qt virtual callbacks.

Same resize variants plus the following group-assignment fixture:
`UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest tests/ui/test_scenario_integration.py -k 'resizing_keyboard or group_assignment_changes' -q --tb=short`
— **3passed/35deselected/13.02s**. With QT_QPA_PLATFORM=wayland, identical selector:
**3passed/35deselected/15.00s**. No tests removed/deselected from the new complete
run. Ruff127files/diff PASS; fresh stable full gate runs before commit/push.

### Final wrapped-attestation / isolated-harness gate

`UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest -q --tb=short -o faulthandler_timeout=120`
— **1012passed/1119.68s**, exit0, no errors. All992prior+20new/38Phase8 UI retained;
both native-pressure variants and the next fixture pass in complete-suite order.
Ruff lint/format127files and diff checks PASS. Application/test sources unchanged
throughout this final complete run; only evidence documentation appended.

Real WSLg application gate6PASS/39.48s and isolated fixture sequence3PASS/15.00s;
local fixture sequence3PASS/13.02s. Refreshed publication/history/Web captures are
synthetic; final publication view inspected with wrapping, clickable Ukrainian
attestation and native keyboard control. Existing wide-layout material/rubric/
Email/result images remain current. No backend/contracts/DB/WebBrowser/security/
dependency/startup changes. Final increment10files (2UI, tests,4docs,3screenshots),
combined redesign16files; owner AGENTS.md excluded. Push a focused third task
commit, then require both CI platforms on its exact HEAD. Final run/results in
PR9/delivery; retain both Windows findings and the local harness failure above.
Phase8 stays REVIEW, owner acceptance pending; no merge or Phase9.

## 17.11.2026 — F8-UX-01/02: видимість group checkbox (REVIEW)

Owner reports manual satisfaction with redesigned preparation functionality; Phase8
acceptance remains pending. Scope: SRS3.13 visual readability, existing4.8/RBAC
unchanged. Existing AGENTS.md English policy explicitly authorized for commit;
reviewed diff contains no secrets/personal paths. Two contradictory older language
clauses aligned; Ukrainian end-user UI/dissertation documentation retained.

Actual group-picker rendering reproduced selected checked indicator AND text
becoming dark/invisible while check state/selected group IDs remain unchanged.
Cause: membershipPicker's dark item background combines with generic selected-row
dark foreground (#19151f); native checked indicator inherits selected foreground.
No lost check state. Two-line membership-specific selected-item QSS sets existing
dark #30343e background and light #eef0f5 foreground. Native Qt checkbox retained;
no delegate, custom painting, glyph/image substitution or application logic change.

Before: focused pixel regression1FAIL/1PASS/8.57s (selected check interior0bright
pixels). After:2PASS/7.29s, enabled/disabled, selected/unselected, checked/unchecked,
focus, Space, unchanged group IDs. Same-theme before/after captures inspected:
phase-8-group-before.png / phase-8-group-after.png. Exact commands:
`CYBERFORGE_GROUP_SCREENSHOTS=/tmp/group-after UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest tests/ui/test_scenario_integration.py -k group_indicator -q --tb=short`.
Context7 official Qt stylesheet reference confirms item selection color/background
styling: https://doc.qt.io/qtforpython-6/overviews/qtwidgets-stylesheet-reference.html
Ruff lint/format127files PASS. No backend, persistence, RBAC, graphics settings,
dependencies or owner secrets/databases changed. Full/WSLg evidence follows.

WSLg focused command:
`QT_QPA_PLATFORM=wayland UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest tests/ui/test_scenario_integration.py -k 'group_indicator or actual_constructor_button or production_dialog or renderer_diagnostics' -q --tb=short`
—5PASS/35deselected/22.84s, exit0. Unsuppressed actual_constructor_button run with
-q -s --tb=short:1PASS/39deselected/8.90s, exit0. All four reported Mesa/Zink/EGL
message patterns reproduced during real MainWindow/startup/preview/normal shutdown;
three render/switch/close/reopen cycles passed, main GUI responsive, sources unchanged.
No new crash reproduced. These messages are nonfatal initialization warnings here,
consistent with previous accepted lifecycle investigation; owner's unknown exit
status cannot be inferred from the shell prompt alone. No graphics flags, drivers,
packages or sandbox settings changed. Current owner hardware exit remains unconfirmed.

Full offline gate:
`UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest -q --tb=short`
—1014PASS/885.92s, exit0, all40Scenario Integration UI cases including F8-01/F8-02.
Ruff check . / format --check .: PASS127files; diff check PASS. Source/tests stable
throughout full run. Only evidence docs added afterwards. AGENTS policy committed
separately as a89e34f; owner text preserved, older language conflicts aligned.
No live AI or owner database/credential/environment changes. Final-head CI evidence
will be recorded in PR9/delivery without another docs-only commit. Phase8 REVIEW;
no merge, ACCEPTED or Phase9. Physical Windows11 remains Phase12 risk.
Actual WSLg CLI startup/shutdown smoke also exits0:
`QT_QPA_PLATFORM=wayland UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync cyberforge --database /tmp/cyberforge-group-cli-smoke-20261117.sqlite3 --web-demo --smoke-test`.
Fresh synthetic temporary DB; offline demo ignores owner .env. CLI smoke emits no
graphics warnings; real Web Preview probe above reproduces them with exit0.


## 17.11.2026 — Phase8 explicit owner acceptance / authorized release

**Phase 8 — ACCEPTED on 2026-11-17.** Власник підтвердив успішну ручну WSLg
перевірку redesigned Scenario Preparation та прийняв весь Phase8 scope, включно
з integration/rubric/readiness/immutable publication/grants/audit, three-step UX,
history/access, WebEngine lifecycle, checkbox visibility та English AGENTS policy.
За повідомленням власника independent review не має confirmed blocking defects.
Це owner-attributed acceptance, не автоматизований чи physical Windows11 check.

Перед release: clean feature tree, HEAD7ee62b5; GitHub MCP PR9 open/unmerged/clean,
base main b84e2fbdfcf1d84f86a6d8c30a9b0b868e678212, remote main тотожний.
Повторно підтверджено CI44020116085 SUCCESS: Linux1014PASS, Windows1011PASS/3POSIX
skips; Ruff127files/GUI/security/lifecycle/startup PASS. Implementation unchanged.

Docs-only increment: acceptance record, current plan state, README current entry
and ADR0008 status. Prior findings/corrections/evidence retained, historical REVIEW
labels explicitly superseded. No SRS/runtime/test/dependency changes. Local repeated
full/GUI/build checks unnecessary for documentation; final-head CI still mandatory.
Release sequence: commit/push existing feature branch; wait/recheck both platforms
on exact docs HEAD; standard merge with expected_head_sha, no squash/rebase; fetch
and ff-only local main; verify merge SHA, remote equality, clean tree. Stop for any
unexpected failure/conflict/integrity issue. Final SHA/CI/merge evidence recorded
in PR9/delivery to avoid another docs-only commit changing the verified HEAD.

Physical Windows11/DPI/GPU-specific/installer acceptance remains Phase12 risk;
owner databases/credentials/.env/API keys/Phase2 snapshot untouched, no live AI.
Phase0–8 ACCEPTED; Phase9 NOT STARTED / PLANNING; Phases10–12 unchanged.

## 17.11.2026 — Phase 9 authorized implementation

Phase0–8 ACCEPTED; verified clean main matches dfba3fb Phase8 merge PR9.
GitHub MCP functional branch read and Context7 SQLAlchemy partial-index docs PASS.
Safe fetch/ff-only and feat/phase-9-learner-simulation created. Sandbox read-only
.git required authorized escalation; no owner data/credentials touched.
Plan: contracts/SRS/ADR → database/services → catalog/Email/Web → completion/history
→ offline demo/security/concurrency/migration/Qt/WSLg/full/package/final-head CI.
Current increment IN PROGRESS. Scoring/Mentor/analytics excluded.

### Phase9 increments 1–6 — contracts, persistence, learner workspace

SRS dated narrow amendment та ADR0009; migration0007, attempt/event contracts,
transactional services, effective-access/history separation, exact publication
binding, cross-version one-active constraint, immutable event/terminal guards.
Learner catalog/intro, reused MailPreview/WebBrowser with explicit interactions,
safe decline/confirmed completion, explicit abandonment, persistent recovery,
repeats та real personal history без numerical scores. Demo --learner-demo creates
validated immutable publication only with explicit fresh --init-demo, ignores
cloud configuration та не торкається owner databases/credentials.

Focused backend19PASS; expanded30PASS/2test path failures corrected; focused11PASS;
demo2PASS. Final real WSLg learner/security8PASS/16.83s, three resume cycles,
settled1100×720 captures inspected. Initial deprecated Qt method and compact
reading/footer space corrected; existing constructor defaults preserved.
Long sandbox backend batches signal143 без summary не зараховано як PASS;
Chromium outer sandbox initialization refused, so actual GUI/full checks run
outside outer sandbox with Chromium sandbox retained. No insecure flags.
Ruff136files PASS; CRLF-aware diff check PASS. Offline wheel/sdist PASS;
installed-wheel source isolation/migration/publication/learner lifecycle PASS
using read-only existing dependencies (empty cache prevented fresh offline
resolution). Full offline suite currently running; final evidence below.
See PHASE_9_ACCEPTANCE for exact commands, limitations and owner checklist.

Expanded demonstration uses app-owned Form/Actions via existing strict contracts
and accepted save/publication services. All five canonical Web actions exposed;
no metadata/values stored. Initial Python-list/strict-tuple validation failure
fixed using existing JSON validation convention. Learner backend32PASS/46.39s;
demo+real WSLg/security10PASS/22.80s; actual offline WSLg CLI smoke exits0.
Initial full run started before this refinement is not the final stable gate;
new final suite follows after focused checks. No scope beyond Phase9.

Pre-refinement full run1053PASS/655.75s, exit0. Because the all-action demo/native
keyboard test changed after that run began, it is not the stable final gate.
Final source/test suite rerun is in progress with output in temporary local log;
no additional source changes planned. Final installed-wheel probe repeated with
updated demo: imports/migrations/publication/learner lifecycle PASS.

### Leave cancellation regression — final correction

Actual WSLg regression reproduced1FAIL/3.97s: Web leave recorded correctly,
but cancelling completion left the Web view hidden. Guarded asynchronous
confirmation cancellation now restores the current browser surface; persisted
leave evidence stays immutable and status remains IN_PROGRESS. Test asserts
visible recovery, deliberate repeat leave, then confirmed completion.
Final focused learner/WebEngine security8PASS/18.71s; Ruff136files PASS.
One new stable full suite is running after this correction; preceding full
runs are retained as intermediate evidence and not used as final-head proof.

### Phase9 final stable local engineering gate

`QT_QPA_PLATFORM=offscreen UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest -q --tb=short`
— **1053PASS/670.67s**, exit0. All1014prior regressions plus39new learner/demo/UI
cases. Source/tests frozen throughout; only evidence/status docs changed after.
Ruff check . / format --check .136files PASS; CRLF-aware diff check PASS.
Actual WSLg learner/security8PASS/18.71s, native Chromium Tab/Enter1PASS; final
wheel/sdist rebuilt, installed-wheel isolated import/migration/publication/attempt
lifecycle and Qt WSLg startup/shutdown PASS. Existing dependency reuse limit
explicit; no claim of fresh offline dependency resolution or physical Windows11.
Intermediate full1053PASS/728.93s also retained, superseded by stable final run.
Phase9 REVIEW. Next: verified commit/push, PRmain, exact-head Linux/Windows CI;
no merge/owner ACCEPTED/Phase10. Final SHA/CI/PR evidence in PR and delivery report
to avoid another docs-only commit changing final verified HEAD. Owner data,
credentials, .env, keys and native Phase2 environment untouched; no live AI.

### First-head CI correction — delegated navigation cancellation

PR10 initial head edcc7d3: Linux run44040059722 failed learner early gate
(4PASS/1FAIL), Windows passed early gate and continued full suite. Native
Chromium action wrote its event, then Qt loadFinished(False) for intentionally
rejected action navigation marked render_failed and blocked subsequent actions.
Official Context7 Qt6 docs explicitly describe this false signal after delegation:
https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineCore/QWebEnginePage.html

WebBrowser now uses loadingChanged URL/status for the exact application-owned
document. Rejected action/external URL loads cannot mark render failure, recover
rendering or count a Web visit. Actual document failure/renderer termination
remain errors. Regression waits for the real false signal and then performs
a second native action; no sleeps replace this signal assertion. Security flags,
network denial, JS restrictions and event semantics unchanged. Focused/full/WSLg
and new exact-head CI results follow. Phase9 stays REVIEW, no merge/acceptance.

Corrected focused offscreen gate:10PASS/19.32s (38deselected). The accepted
preview diagnostic test now removes the resource handler and verifies an actual
failed owned-document reload, retaining error/immutability assertions rather
than emitting the obsolete boolean-only signal. Native learner test waits for
Qt's real cancellation False signal, verifies no render error, then activates
a second actual action before the rest of the event/revocation workflow.
Security settings unchanged. New stable full suite/WSLg/final CI follows.

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

## 17.11.2026 — Phase9 explicit owner acceptance / authorized release

**Phase 9 — ACCEPTED on 2026-11-17.** Owner reports all five manual WSLg scenarios
PASS at5bd1854: safe decline without Web (sender/link inspected), Email→Web/all
three native controls, own history without grades, close/restart/original resume,
teacher_demo_1 Group A revoke blocking / restore resuming same saved attempt.
Власник не має зауважень або вимог додаткових змін. Увесь Phase9 scope прийнято;
F9-01/F9-02 RESOLVED після independent review/remediation. Owner manual evidence
відокремлено від automated checks; не стверджується every UI variation/native Win11.

Owner occasionally observed known libEGL/MESA-LOADER/ZINK/dri2 initialization
warnings. Усі сценарії працювали, restart можливий, наступний launch без warnings;
observable functional impact відсутній за повідомленням власника. Non-blocking
WSLg warnings, не доказ exact owner process exit status. No driver/Mesa/GPU/
rendering/WebEngine flag changes. Internal API trust limit documented in ADR0009.

Before edits: clean synchronized feature HEAD5bd185431434f43a85664fadcfd4af71899bc605;
local/origin main dfba3fbaa1b2b8b94d279d3cef3f132c03cc9391. GitHub MCP PR10 open,
unmerged/clean/base main/expected HEAD; existing fixes inspected. Revalidated
implementation-head run44049089386 SUCCESS: Linux1056PASS, Windows1053PASS/3POSIX
skips, Ruff136files and GUI/security/lifecycle/startup PASS. No implementation drift.

Focused docs-only acceptance update: PHASE_9_ACCEPTANCE, IMPLEMENTATION_PLAN,
DEVELOPMENT_LOG, README current state, ADR0009 status. Historical failures/review/
corrections preserved. No SRS/runtime/migration/dependency/test changes; local
full/GUI/package reruns unnecessary. New documentation HEAD still requires both
platform CI SUCCESS before authorized standard merge with expected_head_sha.
Then fetch, switch clean main, ff-only, verify merge/local/origin/remote SHA and
preserved feature branch. Stop for unexpected CI/conflict/history/integrity issue.
Final SHA/CI/merge evidence goes in PR10/delivery to avoid moving verified HEAD.
Phases0–9 ACCEPTED; Phase10 NOT STARTED / PLANNING; Phase11–12 NOT STARTED.
Owner databases/credentials/env/keys/Phase2 snapshot preserved; no live AI.
Physical Windows11/DPI/hardware GPU/installer/executable/final release acceptance
remain Phase12 risks. Phase10 architecture requires separate owner approval.

Acceptance docs lightweight checks: `uv run --no-sync ruff check .` PASS;
`uv run --no-sync ruff format --check .`136files PASS; relative Markdown file
targets in all5changed docs PASS; `git -c core.whitespace=cr-at-eol diff --check`
PASS. Exact diff reviewed: only5documentation files, no secrets or runtime drift.


## 17.11.2026 — Phase10: погоджена архітектура, лише документація

Власник погодив scoring architecture 17.11.2026. Статус Phase10 —
**NOT STARTED / ARCHITECTURE APPROVED**. Implementation та migration authorization
залишаються pending. Погодження дизайну не є дозволом писати runtime/tests/schema,
не є implementation acceptance і не дозволяє commit/push/PR/merge або Phase11.

Початковий стан: clean main/origin-main tracking, HEAD
`fd4f29dcbef23dec9b98b424fac100beefb89bb7` за local Git; remote повторно не
опитувався. Owner work/дані/env/credentials/native Phase2 workspace збережено.
Переглянуто AGENTS, relevant SRS §§8–9,12,14,23–24,26.2, plan/log, ADR0008/0009,
PHASE_8_ACCEPTANCE/PHASE_9_ACCEPTANCE та accepted source contracts:
RubricDefinitionV1/criterion-registry-v1/rubric-declarations-v1/publication manifest,
ScenarioAttemptV1/AttemptEventV1, migration0007, MentorAgent/MentorInputV1/FactV1/
ExplanationV1 та grounding. Runtime contract files лише читалися.

Додано [ADR-0010](adr/0010-deterministic-scoring-mentor.md), narrow owner-approved
SRS amendments зі збереженням попереднього тексту/labels, expanded Phase10 work
packages та future acceptance specification P10-01–P10-15. Strategy
cyberforge-weighted-actions-v1: seven binary numerical + descriptive decision,
applicable-only Decimal mean, persisted-float conversion, canonical order/digests,
ROUND_HALF_EVEN 2dp; no implicit threshold. No-Web/Web paths визначаються accepted
chronological events; inspection не доводить правильну інтерпретацію загрози.
Evaluation contracts/lifecycle/persistence/idempotency/RBAC/critical observations/
Mentor offline/privacy/UI/Phase11 boundary зафіксовано як майбутню архітектуру.

Виявлені compatibility limits: Phase8 non-Web validation допускає descriptive
criterion і не гарантує numerical denominator для обох paths. Prospective
publication rule застосовуватиметься лише до future publications; historical
path без numerical criteria → UNSCORABLE/null/reason. Phase5 completed
ResultFactsV1 потребує non-null float score; UNSCORABLE отримує deterministic
local explanation без incompatible MentorInputV1, а не forged zero/incomplete.
NOT_CONFIGURED critical policy не доводить відсутності порушень. SRS historical
critical proposals залишено; current v1 amendment явно обмежує їх observation
policy без penalties. Непогодженого конфлікту не виявлено; accepted meanings не
змінено. Stale log header Phase2/3 та current README architecture-pending status
оновлено; dated historical entries збережено. Змінено лише п'ять Markdown files:
SRS, ADR-0010, IMPLEMENTATION_PLAN, DEVELOPMENT_LOG та README.
NIST methodological boundary звірено з official
[TN2276 abstract](https://csrc.nist.gov/pubs/tn/2276/final): email detection difficulty,
не learner score; методику не використано для scoring.

Фактична документаційна верифікація:

- `python3 /tmp/cyberforge_phase10_docs_check.py` — PASS: exactly five Markdown
  files, no staged changes/unchanged HEAD; 50 relative file targets існують;
  UTF-8 без BOM, original LF/CRLF styles збережено. SRS має рівно 11 insertion-only
  amendments: увесь попередній byte content збережено в початковому порядку.
  Source AST comparison усіх восьми criterion IDs/labels/phases/evidence actions/
  applicability та canonical order — PASS. Вісім future work packages,
  15 future acceptance criteria, A–K coverage та architecture status — PASS.
  Це одноразовий read-only documentation verifier у /tmp, не новий project test.
- `git -c core.whitespace=cr-at-eol diff --check` — PASS.
- `git diff -- README.md docs/IMPLEMENTATION_PLAN.md docs/DEVELOPMENT_LOG.md`,
  `git diff -- TECHNICAL_SPECIFICATION.md` та огляд нового ADR — лише
  documentation baseline; changes/links/history/compatibility перевірено.

Documentation baseline gate PASS: review-ready; owner review ще попереду.
Phase10 implementation acceptance не пройдено/не заявляється. Ruff/pytest/GUI,
build/package, migration та CI не запускалися для цього docs-only increment.

Future acceptance tests не створювалися/не виконувалися. Немає runtime,
migration/schema, dependency або existing-test changes, live LLM calls чи DB
operations. Physical Windows11 та ще не виконані Decimal/digest/concurrency/
migration/privacy/UI acceptance checks залишаються ризиками майбутньої реалізації.
Наступна дія — owner review baseline та окремий implementation authorization;
Phase10 implementation і Phase11 не почато.


## 17.11.2026 — Phase10 architecture remediation F10-01–F10-04 (docs only)

Власник дозволив лише documentation remediation чотирьох review findings.
Preflight: main, HEAD fd4f29dcbef23dec9b98b424fac100beefb89bb7; чотири tracked
Markdown modifications і untracked ADR-0010 від попереднього baseline збережено.
Зроблено hashes project files та snapshots чотирьох document inputs у /tmp для
перевірки scope; accepted sources read-only. README вже коректний, у цьому
increment не змінювався. Попередні preparation/verification записи вище є історією,
а не підтвердженням architectural acceptance або виконаних runtime tests.

Нормативні corrections інтегровано в ADR-0010, existing dated SRS amendments
§§12.2/12.8/14.7/23–24 та Phase10 work packages:

- F10-01: StoredEvaluationIntegrityValidation, відповідальний future internal
  EvaluationService, authorization → consistent DB snapshot → exact source/
  envelope/criterion/arithmetic validation → authorized consumer. На read/retry/
  Mentor/future analytics corruption fail closed, record preserved; жодного
  automatic overwrite/delete/repair/rescore. Future P10-16 містить усі негативні
  payload/digest/detail/binding/evidence/sequence та consumer/retry cases.
- F10-02: closed reference event_id UUID string + strict positive sequence;
  full stream, per-criterion та completed-path references distinct; усі matching
  ordinary actions, unique/ascending, без repeat score credit. Safe decline —
  final effective decline+completion; descriptive decision — chronological
  transition history/final action. P10-17 — repeated-action/reversed-decision vectors.
- F10-03: approved invariants відокремлено від exact schemas, які ще не fully
  frozen. Mandatory Contract Freeze Gate WP1 → WP3 до першої migration/persisted
  result/feedback: typed definitions, serialization/golden/compatibility/corruption
  vectors, DB mapping, documented ADR/SRS review. WP5 feedback schema також у
  gate; incompatible post-freeze changes versioned. P10-18; gate зараз не пройдено.
- F10-04: §D.2 і P10-07 окремо визначають same arithmetic/canonical detail order
  для equivalent inputs та distinct source-bound digests для different published
  rubric identities. Original fingerprint/payload не нормалізуються/не змінюються.

Збережено strategy/formula, seven numerical/one descriptive criteria, applicability,
prospective per-path readiness, historical UNSCORABLE, critical_action=null /
NOT_CONFIGURED без penalties, Phase5 Mentor та Phase8–9 contracts/lifecycle/events.
Усі P10-01–18 — future acceptance specification, не executed tests.
Фактична verification цього remediation:

- `python3 /tmp/cf10_remediation_docs_check.py` — PASS: рівно чотири document
  changes від preflight; інші 203 project files byte-identical, включно з README,
  accepted sources/tests/migrations; нових repository files немає. 50 relative
  Markdown links valid; вісім registry IDs/labels/phases/actions/applicability/
  canonical order та Phase8–9 version references matched. Вісім work packages,
  18 future acceptance criteria, explicit F10-01–04 normative rules та mandatory
  WP1 → WP3/feedback freeze dependency перевірено. HEAD/staging незмінні.
  UTF-8 без BOM, SRS CRLF/original line endings збережено; original SRS HEAD
  content лишається byte-preserved із 11 insertion-only amendment regions.
- `git -c core.whitespace=cr-at-eol diff --check` — PASS.
- `git status --short`, `git diff --name-only`, `git diff --stat` та exact
  pre-remediation document diff review — лише очікуваний documentation scope.
  Untracked ADR-0010 прочитано explicitly, його remediation delta оглянуто
  окремо від ordinary git diff. README pending baseline change збережено без
  нового редагування. Local main/HEAD fd4f29d незмінні, нічого не staged.

F10-01/F10-02/F10-03/F10-04 — RESOLVED у документації за engineering review;
documentation acceptance залишається власнику. Checks підтверджують лише
documentation consistency/scope, не runtime correctness. Ruff/pytest/GUI,
migrations/build/CI/live AI не запускалися для цього documentation increment.
Phase10 — NOT STARTED / ARCHITECTURE APPROVED; implementation unauthorized,
acceptance лише власником. No runtime/migration/test/dependency/live LLM/Git
publication changes; Phase11 не розпочато. Нових approved-requirement conflicts
або unresolved MAJOR findings у цьому remediation не виявлено; exact schema
freeze та runtime/security/concurrency/migration/Windows acceptance ще попереду.

## 17.11.2026 — Phase10 documentation baseline: дозволена публікація

Власник дозволив лише commit/push dedicated documentation branch та PR до main.
F10-01–04 resolved у документації; Phase10 NOT STARTED / ARCHITECTURE APPROVED.
Цей дозвіл замінює попередню заборону Git publication для baseline, але не надає
дозволу merge, runtime implementation, migration, test changes або Phase11.
ADR header і current plan authorization notes уточнено без зміни архітектури.

Preflight local main/HEAD/origin-main fd4f29dcbef23dec9b98b424fac100beefb89bb7;
GitHub MCP list_branches підтвердив той самий remote main і функціональний read.
Тому fetch/fast-forward не потрібні; existing owner modifications збережено.
Повністю переглянуто pending tracked diffs та untracked ADR-0010. Очікувані лише
README, TECHNICAL_SPECIFICATION, IMPLEMENTATION_PLAN, DEVELOPMENT_LOG, ADR-0010.

Final docs gate: `python3 /tmp/cf10_remediation_docs_check.py` PASS — 50 relative
links, eight exact registry definitions, accepted Phase8–9 versions, eight work
packages, P10-01–18, mandatory Contract Freeze Gate та F10-01–04 rules. Повторено
після authorization-note edits. UTF-8/SRS CRLF і pre-existing SRS bytes збережено;
runtime/migrations/tests/dependencies unchanged. Команда
`git -c core.whitespace=cr-at-eol diff --check` PASS. Не запускали local pytest,
GUI/package/migration/live AI для documentation-only publication. CI після push
перевіряється на exact PR HEAD; результати/PR/SHA — у delivery report, без
додаткового commit, який змінює перевірений HEAD. No implementation acceptance.


## 17.11.2026 — Phase10 / WP1 implementation, only authorized contracts/verification

Owner explicitly дозволив WP1 після read-only design/clarifications. Preflight
clean main e5213314c88ca6844384b1349ecf8bc2d7428336; GitHub MCP main matched;
створено feat/phase-10-wp1-contracts. Немає Git publication authorization.
План перед coding mapped SRS §§12.2/12.8/14.7/23–24 та ADR0010 D/E/J.1:
closed candidates → canonical/pure replay/facts → static accepted-source vectors
і isolated SQLite proof → focused/full/package checks → owner gate review.

Додано лише evaluation package, focused tests/static fixtures/schema snapshot та
[WP1 review evidence](PHASE_10_WP1_CONTRACT_FREEZE_REVIEW.md). Contract Freeze Gate
PENDING OWNER ACCEPTANCE; Phase10 only WP1 engineering REVIEW. All later WPs
not started. Production source models/services/UI/migrations не змінювалися.

12 exact candidate models preserve field/version/null semantics; error taxonomy
includes integrity_reason, permanent missing/corrupted source cannot become
retryable transient failure. Closed canonical JSON boundary rejects coercions,
unknown/duplicate/noncanonical data. Pure validation checks exact authoritative
attempt/publication identity, accepted legacy source/operation hashes, complete
Phase9 lifecycle, references/applicability/observations та stored projections.
No DB or LLM calls in evaluation package. Reference arithmetic verification
helpers не є production ScoringService. Catalogue wording follows final owner
correction; recommendations and Phase5 contracts unchanged. Context7 official
Pydantic v2 strict/JSON/frozen docs used; no new dependency.

Accepted service paths породили six frozen-clock/UUID source-valid fixture bundles,
включно з SCORED/UNSCORABLE feedback. Independent test projection/Fraction та
external OpenSSL18envelope digest checks перед static snapshot. Synthetic original
hash fixture retained окремо без false source-valid claim. Test-only scratch
protocol proves explicit BEGIN before account authorization, snapshot consistency,
registry-derived sealed detail set, deferred FK/rollback, replace/UPSERT guards,
concurrent one-winner and recovery; no migration0008. Initial scaffolding/API/
fixture/negative-case refinements retained у focused review notes, не final PASS.

Actual focused104PASS/89.79s, expanded129PASS/99.38s; final protocol47PASS/46.72s,
schema+Mock3PASS/0.61s. Ruff check ./format143files PASS. Stable full offline
suite running; no code/test edits during full. Package sdist/wheel build and
isolated installed-wheel six-vector roundtrip/import/source parity PASS.
Exact commands/final results у linked review doc. No live AI/owner DB/credentials/
env/native Phase2 snapshot changes; no commits/push/PR/merge. Gate disposition
only recommendation; final owner acceptance required. Windows CI not run without
publication; physical native Windows11 remains Phase12 risk.


WP1 final review hardening: hostile manually constructed legacy ExplanationV1
could retain mutable selected_facts under model-selection feedback. Added fresh
accepted-JSON revalidation after field validation (before-validator intermediate
broke strict JSON tuple parsing і був виправлений до final run). Phase5 contracts
unchanged; no new fields/digest/schema changes. Regression asserts independent
immutable copy after hostile list mutation. Focused16PASS/13.90s. First full run
stopped at78%, exit143, not PASS; code/tests unchanged during it. Final full run
restarted after fix; source/tests frozen, captured hashes для final comparison.
Final offline wheel rebuilt/reinstalled, isolated imports/six-fixture roundtrips/
source parity PASS. Detailed evidence у WP1 review; owner gate acceptance pending.


Final WP1 delivery gate: **1189PASS/656.89s**, exit0, no failures/skips. Command:
`QT_QPA_PLATFORM=offscreen UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest -q --tb=short`.
Normal Chromium sandbox retained outside outer workspace restriction. All1056
accepted baseline tests +133new WP1 cases; final source/tests/fixtures hashes
unchanged. Final16focused PASS covers nested legacy revalidation; protocol47PASS
and original synthetic five SHA vectors/source-valid six bundles retained.
Ruff lint/format143files PASS, final rebuilt installed wheel isolated import/
roundtrip/parity PASS. Earlier interrupted full is not final evidence.

Final audit: exactly18WP1files,36relative documentation links, diff --check PASS,
accepted sources/tests/migrations/dependencies/SRS/ADR byte-identical. No runtime
scoring/persistence/production authorization/Mentor cloud integration/UI/Phase11,
no owner DB or native Phase2 snapshot changes. Branch feat/phase-10-wp1-contracts,
HEAD remains e5213314c88ca6844384b1349ecf8bc2d7428336, staging empty. No unresolved
implementation findings after final verification; native Windows11/remote CI/
future migration checks remain documented limitations. WP1 engineering REVIEW;
Contract Freeze Gate PENDING OWNER ACCEPTANCE. No Git publication without owner.

## 17.11.2026 — WP1 publication explicitly authorized, Draft PR only

Owner дозволив commit/push feat/phase-10-wp1-contracts та Draft PR targeting main
для independent architectural/code review. Acceptance/merge/next WP не дозволені.
Preflight branch/HEAD/main/origin-main e5213314c88ca6844384b1349ecf8bc2d7428336;
GitHub MCP confirmed same remote main. Owner work preserved; exactly18WP1 files.
All15code/test/fixture hashes match final verified run. Accepted Phase0–9 source/
existing tests/production persistence/migrations/dependencies/SRS/ADR untouched.
No secrets/credentials/private DB/temp build/unrelated files in publication scope.

Previous execution evidence remains1189full PASS/656.89s,47protocol PASS,
16hardening PASS, offline sdist/wheel/isolated installed-wheel/import/parity PASS,
source-valid vectors/independent OpenSSL hashes PASS. Full suite/package не
повторюються лише для publication byte-identical implementation. New checks:
`UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync ruff check .`,
`UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync ruff format --check .`,
relative links/hash/scope/secret-pattern audit та
`git -c core.whitespace=cr-at-eol diff --check` (also staged variant).
Publication updates лише current authorization notes у three WP1 docs; code/tests
unchanged. Exact commit/Draft PR/CI evidence у delivery report без circular commits.
WP1 NOT ACCEPTED; gate PENDING OWNER ACCEPTANCE; no merge or implementation advance.


## 17.11.2026 — WP1 independent review F10-WP1-01–03 remediation

Reviewed HEAD90ff3976fcaefd2371d6ec31b71c61a17f246e87, clean feature branch;
GitHub MCP confirmed PR#12 OPEN/Draft/base main. Owner дозволив corrective
implementation/tests/docs/commit/push лише до цього PR, без merge/next WP.

F10-WP1-01: fixed-point formatting/scaling раніше не обмежували compact Decimal
exponent. Новий bound -324..4,329coefficient digits,345raw chars,abs≤70000
перевіряється до expansion; strict JSON/Python guards та direct helper guards.
Seven numerical criteria максимум, event-count cap не додано. No intermediate
rounding; accepted Phase8 float loader unchanged. Binade/subnormal/neighbor probe
3263historical float conversions PASS. Strict JSON before-validator interaction
виправлено перед final24focused PASS; schema зберігає standard maximum/minimum.

F10-WP1-02: rubric_id містив scenario identity у Mentor summary. Замінено на
validated snapshot revision label з bounded large-revision fallback; score/schema
Phase5 незмінні. Five SCORED feedback labels/digests оновлено; source/evidence/
result objects та UNSCORABLE/synthetic fixtures unchanged. Privacy regression
перевіряє actual MentorInputV1 та Mock path без provider network calls.

F10-WP1-03: explicit narrowing scratch retry claim/comment: winner identity only,
не stored-integrity proof. Separate source-valid stored pipeline/corruption/detail
checks retained; future WP3 must invoke pure integrity validation before returning
existing result. No production EvaluationService/migration0008.

Executed: `uv run --no-sync pytest -q tests/test_evaluation.py
tests/test_evaluation_protocol.py --tb=short`147PASS/95.68s (QT_QPA_PLATFORM=offscreen,
UV_CACHE_DIR=/tmp/cyberforge-uv-cache). Final focused `-k 'decimal or rounding or tiny
or mentor or schema'`24PASS/0.62s. Ruff lint/format143files PASS; diff --check PASS.
18golden envelope hashes independently recomputed using openssl dgst -sha256;
Fraction arithmetic і unchanged source/evidence/result comparisons PASS.
`uv build --offline --out-dir /tmp/cyberforge-wp1-remediation-dist` sdist/wheel PASS;
`uv pip install --offline --no-deps --python .venv/bin/python
--target /tmp/cyberforge-wp1-remediation-installed
/tmp/cyberforge-wp1-remediation-dist/cyberforge-0.1.0-py3-none-any.whl` PASS.
`.venv/bin/python -I /tmp/cf-wp1-remediation-wheel-probe.py` PASS: all six
source-valid fixture roundtrips/full stored-source integrity/feedback,97source files
identical installed wheel, imports only installed package; socket.connect forbidden.
Full suite in progress on frozen11code/test/fixture hashes; final evidence follows.
WP1 NOT ACCEPTED, Contract Freeze Gate PENDING OWNER ACCEPTANCE. No live AI.


Final remediation verification: **1203PASS/649.98s**, exit0, no failures/skips.
Command: `QT_QPA_PLATFORM=offscreen UV_CACHE_DIR=/tmp/cyberforge-uv-cache
uv run --no-sync pytest -q --tb=short --junitxml=/tmp/cf-wp1-remediation-pytest.xml`.
Normal Chromium sandbox retained; all1056accepted baseline +147WP1 tests, including
14new remediation cases. Frozen11code/test/fixture hashes unchanged throughout.
Final Ruff lint/format143files, whitespace/link/scope audit PASS; exactly14corrective
files within original18file PR scope, accepted SRS/ADR/Phase5/8/9/production DB/
migrations/dependencies untouched. F10-WP1-01/02 RESOLVED by guards/privacy adapter;
F10-WP1-03 RESOLVED by explicit proof-scope correction (not a production retry proof).
Corrective commit/push to Draft PR#12 authorized; exact SHA/CI evidence у delivery
і PR description to avoid circular commits. No merge. Gate pending owner acceptance
and independent re-review; physical native Windows11 remains Phase12 risk.


## Owner decision — November 17, 2026 — WP1 acceptance / Contract Freeze

Власник формально прийняв Phase10 / WP1 — Contracts & Evidence Validation
і затвердив Contract Freeze Gate після незалежного review та remediation.
Це актуальне рішення замінює попередні REVIEW/PENDING записи лише як поточний
статус; усі попередні review records збережено як історичні докази.

- Phase10 / WP1: **ACCEPTED**.
- Contract Freeze Gate: **PASSED / OWNER APPROVED**.
- Phase10: **IN PROGRESS / WP1 ACCEPTED / CONTRACT FREEZE PASSED**; не whole-phase ACCEPTED.
- Approved implementation commit: `5d91716544b8a7764f3e2735783e0289b3803c82`.
- [PR #12](https://github.com/the1llus1on/cyberforge/pull/12): owner-authorized
  standard merge-commit лише після final documentation HEAD Linux/Windows CI.
- F10-WP1-01 (Decimal bounds), F10-WP1-02 (sanitized Mentor revision) та
  F10-WP1-03 (scratch retry-proof boundary): **RESOLVED**, прийнято власником.
- У прийнятому WP1 scope немає outstanding BLOCKER, MAJOR або MINOR findings.

Verified evidence: local full offline regression **1203 passed**, focused WP1
**147 passed**, isolated SQLite protocol **47 passed**, final Decimal/Mentor/schema
**24 passed**. Golden vectors/independent digest checks, Ruff lint/format, offline
sdist/wheel та isolated installed-wheel verification — **PASS**.
Original final implementation [CI run44131758053](https://github.com/the1llus1on/cyberforge/actions/runs/44131758053):
Linux `checks (ubuntu-latest)` **SUCCESS**; Windows Server2022
`checks (windows-2022)` **SUCCESS**, verified через GitHub MCP.
Ці CI results стосуються approved implementation SHA, не нового acceptance commit.
Для нового exact PR HEAD обидва CI jobs мають завершитися SUCCESS до merge;
final SHA/run/merge evidence фіксуються у PR description і delivery без circular commits.

Frozen v1 contracts, canonical serialization/golden vectors та documented mapping
тепер normative inputs для майбутньої окремо approved роботи. Incompatible changes
до frozen v1 потребують explicit versioning і documented review. Це не створює
production storage schema: deferred-FK SQLite proof ізольований і test-only;
production migration та actual persisted-result lifecycle ще не реалізовано.
Physical Windows11 release acceptance залишається відповідальністю Phase12.

Phases0–9 та Phase10 architecture — ACCEPTED. WP2 deterministic scoring і WP3
persistence — **NOT STARTED / NOT AUTHORIZED**; migration0008 — **NOT CREATED /
NOT AUTHORIZED**. Production ScoringService/EvaluationService, result UI, cloud
Mentor integration та analytics не дозволені. Phases11–12 — **NOT STARTED**.
Після acceptance recording/merge/ff-only synchronization роботу зупинити;
цей дозвіл не починає наступний work package. SRS v3.0/ADR-0010 незмінні.

## 17.11.2026 — Phase 10 remaining implementation authorized; WP2 increment

Clean main/local origin/main та GitHub MCP remote main підтвердили accepted
`de40af1899b913cbbdb152117900a25e7c9d6b02`. Створено один feature branch
`feat/phase-10-complete-scoring-mentor`. Owner authorization: WP2–WP7, WP8 review,
commits/push/Draft PR, без merge/whole-phase acceptance/Phase11–12.
GitHub MCP functional read PASS; Context7 SQLAlchemy documentation read PASS
(explicit real SQLite read BEGIN та serialized write transaction). Dependencies
не змінено. Frozen WP1 serialization/schema/fixtures/contract semantics збережено.

WP2: production pure scorer використовує accepted projection/source validator,
Decimal exact arithmetic та half-even final representation; no LLM dependency.
Prospective readiness/atomic publication перевіряє numerical denominator кожного
шляху. Historical rubric loader unchanged; historical test fixture явно відтворює
pre-Phase10 decision-only publication у вузькому test-only context.
`UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest -q tests/test_scoring.py --tb=short`:
11PASS/0.97s. First real production evaluate/retry/read on six source bundles:
6PASS/7.73s. WP3 schema/integrity/migration hardening та решта WP тривають.
Owner DB, credentials та native Phase2 environment не змінювалися.

## 17.11.2026 — Phase10 WP3–WP6 integration та focused verification

Production migration `0008_evaluations` additive після0007: three approved tables,
Decimal TEXT, six result FKs, UNIQUE authoritative attempt/result/feedback identities,
deferred detail FK, detail-first/parent-last complete-source seal,11immutable/
projection/order/binding triggers. Empty downgrade allowed; any history blocks
unsafe downgrade. Explicit real BEGIN/BEGIN IMMEDIATE evaluation-scoped boundary
до DB auth; trusted historical source loader не обходить ownership і не повертає
restricted content. `StoredEvaluationIntegrityValidation` обов'язковий для
retry/read/history/Mentor; structural/source/detail/arithmetic corruption explicit,
operational failures retryable, no repair/delete/rescore.

Mentor scoring-independent commit: educational-facts-v1, existing provider-neutral
MentorAgent/gateway, bounded model selection, deterministic Ukrainian offline/
timeout/invalid-output fallback; UNSCORABLE separate compatibility path. No raw
learner events/IDs/source text/credentials/form values у provider request.
First verified feedback immutable, reauthentication після provider call.
Initial valid-selection probe виявив incorrect telemetry.model access; corrected
на existing effective_model, з actual recorded-provider regression. Test-only
migration FK-count expectation corrected6; frozen contracts unchanged.

UI замінює Phase9 placeholder на actual results/history/detail, explicit evaluation,
background feedback, empty/incomplete/abandoned/pending/zero/nonzero/UNSCORABLE/
missing/error/denied states, plain Ukrainian text, compact scrolling. Dedicated
one-thread Qt pool/session epoch та existing shell close-wait flow забезпечують
logout cleanup, stale-response rejection та safe close while generation runs.
No Phase11 UI/analytics/exports. Minor reversible choices documented у review;
no approved architecture/semantics change або SRS/ADR edit.

Executed offline focused checks (UV_CACHE_DIR=/tmp/cyberforge-uv-cache):
- `uv run --no-sync pytest -q tests/test_scoring.py --tb=short`:37PASS/2.27s.
- `uv run --no-sync pytest -q tests/test_evaluation_persistence.py -x --tb=short`:
  60PASS/152.32s; real schema concurrent winner, failures/rollback/retry, corruption,
  immutable operations з recursive_triggers0/1, RBAC/revoke/archive/restart.
- Added real-read snapshot/deactivation та busy/unavailable/prospective-publication
  focused selection:3PASS/8.47s; no source/data repair.
- `uv run --no-sync pytest -q tests/test_mentor_feedback.py tests/test_evaluation_migration.py
  tests/test_scoring.py tests/test_evaluation_service.py tests/test_evaluation_protocol.py
  tests/test_scenario_integration.py tests/test_learner_attempts.py --tb=short`:
  209PASS/390.59s. Earlier runs interrupted across session limit, not passing evidence.
- `QT_QPA_PLATFORM=offscreen ... pytest -q tests/ui/test_learner_results.py
  tests/ui/test_learner_simulation.py --tb=short`:21PASS/83.08s.
- Same two files on real `QT_QPA_PLATFORM=wayland` WSLg:21PASS/86.00s.
  Це automated agent evidence, не owner manual acceptance чи physical Windows11.
- Actual production-window visual probe на fresh offline temp demo:1100×720 PNG
  inspected; score/applicability/details/actions readable, feedback scrollable.
  Requested900×650 resize залишив1100×720 через accepted shell minimum; smaller
  screenshot не зараховується як окремий compact-window proof. Standalone results
  widget tests680×600 PASS. Screenshots лише /tmp, без owner credentials у output.
- Ruff check . / format --check .:154files PASS; whitespace та documentation links PASS.

Offline sdist/wheel build та isolated target install PASS. Installed-package-only
probe: six golden vectors, actual migration0008, fresh offline demo, persisted
score/feedback/reconnect/FK, all-source-byte parity PASS, socket.connect forbidden.
Installed wheel desktop startup/migration/Qt event-loop smoke на real WSLg PASS.
SRS/ADR/WP1 freeze doc/contracts/fixtures/dependencies byte-identical accepted main.
Legacy latest-head migration assertions updated0007→0008; all existing regression
probes retained. Scratch-only protocol tables renamed proof_* to coexist with
production tables. Owner DB та native Phase2 environment untouched.

WP7 final full regression на frozen source/test/fixture hashes триває; first run
stopped early to update remaining three legacy migration-head expectations,
не counted as PASS. WP8 review/checklist prepared у PHASE_10_IMPLEMENTATION_REVIEW.md;
exact final suite/package/CI/Git evidence follows. No acceptance/merge/next phase.

### Phase10 final integrity hardening — malformed attempt metadata

Final audit додав production corruption probe: пустий persisted scenario_name у
isolated DB після контрольованого видалення immutability trigger. Existing result
read уже fail closed, але history error branch повторно викликав attempt_value
поза safe validation boundary і піднімав raw Pydantic ValidationError. Regression
спочатку відтворив defect (1FAIL), без зміни authoritative evaluation.

History тепер перевіряє typed immutable attempt metadata та повертає explicit
IMMUTABLE_SOURCE_INTEGRITY_ERROR перед будь-яким invalid history entry. Stored
read/retry errors використовують safe nullable UUID projection навіть при malformed
source/result identity. Немає repair/rescore/history deletion або contract change.
Focused production read/retry six paths + malformed metadata:7PASS/10.03s.
Actual WSLg cached-results clearing/source-integrity message:1PASS/2.18s.
Full regression з попереднім code snapshot перервано, не counted as PASS;
final full gate перезапущено на нових frozen hashes разом із two new regressions.
Final offline package rebuilt/reinstalled для цієї source revision; результати нижче.

Final local implementation checkpoint:
`27e99f482766dfac50caa794ab313f979511da53`
(`feat(evaluation): implement deterministic scoring and learner feedback`).
22source/test files,2814insertions/124deletions; exact staged scope/whitespace та
credential-pattern audit PASS. Four documentation files retained for final evidence
commit. No push/PR until full local gate passes. Remote GitHub MCP main reverified
at accepted de40af1; origin target verified without exposing URL credentials.


## Phase10 final stable engineering gate — 17.11.2026

**1349PASS/942.96s**, exit0,0failures/0skips. Exact command:
`QT_QPA_PLATFORM=offscreen UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest -q --tb=short --junitxml=/tmp/cf-p10-final-gate.xml`.
All1203accepted baseline tests retained +146new Phase10 implementation tests;
source/test/fixture hashes unchanged from frozen final gate manifest. Initial
interrupted runs are superseded by this complete final run, not counted as PASS.
Ruff check . та format --check .154files PASS. No live provider use.

Final rebuilt package commands (UV_CACHE_DIR=/tmp/cyberforge-uv-cache):
`uv build --offline --out-dir /tmp/cyberforge-p10-final-dist` PASS;
`uv pip install --offline --no-deps --python .venv/bin/python --target /tmp/cyberforge-p10-final-installed /tmp/cyberforge-p10-final-dist/cyberforge-0.1.0-py3-none-any.whl` PASS;
`.venv/bin/python -I /tmp/cf-p10-final-wheel-probe.py` PASS, installed package only,
network forbidden, all source bytes identical. `QT_QPA_PLATFORM=wayland
.venv/bin/python -I /tmp/cf-p10-final-startup-smoke.py` PASS: new temp DB migration0008,
actual desktop startup та Qt event loop. Earlier21WSLg/21offscreen UI cases та
final1WSLg source-corruption probe retained; not owner manual acceptance.

WP2–WP6 implemented/locally verified; WP7 local gate PASSED; WP8 review/checklist
READY. Overall Phase10 REVIEW / PENDING OWNER ACCEPTANCE. No known unresolved
implementation BLOCKER/MAJOR/MINOR after self-audit; independent review pending.
Exact final docs HEAD, Draft PR та Linux/Windows CI URLs/conclusions recorded
in PR/delivery after publication, avoiding circular commits. Native Windows11/
DPI/GPU/executable/installer remains Phase12 deferral. No merge/Phase11/12 start.

## 17.11.2026 — PR13 independent review remediation F10-R01/R02

Owner authorized only these findings/tests/docs/corrective commit/push to existing
Draft PR13; reviewed HEAD f4e6c04a13adf70cc5d7dbd6b1ad50b5713c5130, clean local
branch and matching GitHub MCP head/base main/Draft verified. No merge/acceptance.
SRS §12, ADR0010 P10-11/14; frozen contracts/migrations/scoring unchanged.

F10-R01 root cause: heartbeat _sync_session→_render unconditionally refreshed
complete results history. Shell now detects actual entry into MY_RESULTS before
switching workspace widgets; initial entry/return refresh, unchanged active view
renders do not. Periodic current-session authorization and invalid-session cleanup
remain intact. Explicit refresh/evaluation/feedback callbacks retain their existing
update paths. No global session-policy change or new database writes.

F10-R02 root cause: one try/except covered both verified score and optional Mentor
read, so feedback-only operational errors replaced the score. Retrieval now has
separate exception boundaries. Feedback-only failures stay in feedback; evaluation
failure stays fail closed; denied/revoked session clears all protected content.

New regression probes count history calls and trace absence of evaluation reads
and writes on repeated heartbeat/render; keyboard/selection stability, explicit
changed-history refresh, return, logout/deactivation; storage-busy/unavailable
feedback preserves score and recovers; ACCESS_DENIED clears. Existing corruption,
post-evaluation/worker and Phase9 tests retained. Actual verification follows.

Remediation final verification: `QT_QPA_PLATFORM=offscreen
UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest -q --tb=short`:
**1354PASS/825.06s**,0failures/0skips; all1349previous tests +5new regressions.
`QT_QPA_PLATFORM=wayland UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync
pytest -q tests/ui/test_learner_results.py tests/ui/test_learner_simulation.py
--tb=short`: **27PASS/57.25s**, actual automated WSLg, not owner acceptance.
Initial offscreen focused run26PASS/51.83s preceded added deactivation coverage.
`UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync ruff check .` and
`uv run --no-sync ruff format --check .`: PASS,154files. diff --check PASS.
No cloud credentials, migration/frozen fixture changes or packaging changes;
UI-only remediation does not require repeating build/wheel checks under approved
workflow. Existing CI package/startup smoke remains enabled. F10-R01/R02 RESOLVED
by implementation and local verification; final exact-head CI in PR/delivery.
Phase10 REVIEW / PENDING OWNER ACCEPTANCE, independent re-review pending.

## 18.11.2026 — F10-R03 final UI integrity boundary

Owner authorized focused UI/tests/docs correction and push to Draft PR13, reviewed
20ccfb9e248d9c5387b4d61cb29bd80e31c0aac9. Clean branch and matching remote Draft
head verified. SRS §12/ADR0010 P10-16: Mentor.read revalidates evaluation in a
subsequent transaction; R02's call-site-only feedback classification could retain
stale score after this second validation failed. Error code now takes precedence:
evaluation/source integrity errors remove score/feedback, replace the selected
cached history result with an integrity-error entry and disable actions. No extra
read, refresh loop, write, repair or rescore. Feedback integrity/operational errors
continue preserving independently verified score; access denial clears content.
Three added cases: both evaluation/source error codes and real controlled result
corruption between reads in isolated DB, with corrupted record preserved. Existing
feedback failure/recovery, corrupt feedback, access and R01 heartbeat tests retained.
Scoring/contracts/migration0008/source semantics unchanged. Evidence follows.

F10-R03 final local gates: `QT_QPA_PLATFORM=wayland
UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest -q
 tests/ui/test_learner_results.py tests/test_evaluation_persistence.py --tb=short`:
87PASS/256.56s, including real WSLg UI and isolated persistence corruption tests.
`QT_QPA_PLATFORM=offscreen UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync
pytest -q --tb=short`: **1357PASS/1731.42s**,0failures/0skips, all1354previous +3new.
`uv run --no-sync ruff check .` and `uv run --no-sync ruff format --check .`
(UV_CACHE_DIR=/tmp/cyberforge-uv-cache): PASS,154files; diff --check PASS.
No live credentials/providers; UI-only change requires no repeated build/wheel
checks under approved workflow. Existing CI package/startup gates retained.
F10-R03 RESOLVED locally, pending independent re-review. Exact new HEAD and
final-head Linux/Windows CI recorded in existing Draft PR13 and delivery.
Automated WSLg evidence is not owner manual acceptance; native Windows11 remains
Phase12 deferral. No merge/acceptance/Phase11/12 work.


## 18.11.2026 — Остаточне прийняття Phase 10

Власник прийняв Phase 10 після незалежного огляду, автоматизованих перевірок
і повідомленої ним ручної функціональної перевірки у WSLg. Статус ручного
приймання — **ACCEPTED**. Зауваження F10-R01, F10-R02 і F10-R03 — **RESOLVED**.

| Обсяг | Остаточний статус |
| --- | --- |
| WP1 — Contracts & Evidence Validation | ACCEPTED |
| Contract Freeze Gate | PASSED / OWNER APPROVED |
| WP2 — Deterministic Scoring | ACCEPTED |
| WP3 — Persistence & Integrity | ACCEPTED |
| WP4 — Critical Observations | ACCEPTED |
| WP5 — Mentor Feedback | ACCEPTED |
| WP6 — Learner Results UI | ACCEPTED |
| WP7 — Verification | ACCEPTED |
| WP8 — Review & Owner Acceptance | COMPLETED |
| Phases 0–10 | ACCEPTED |
| Phase 11 | NOT STARTED |
| Phase 12 | NOT STARTED |

[PR #13](https://github.com/the1llus1on/cyberforge/pull/13) — **MERGED**.
Прийнятий HEAD реалізації: `0c2d36c72bafed0d32f5f84ac0bd928b5c405fb0`.
Коміт злиття: `3011e966eb6d6f0bfa95ba56ed9ea11c4e67e4fc`.

[GitHub Actions 44198755132](https://github.com/the1llus1on/cyberforge/actions/runs/44198755132):
Linux — 1 357 пройдено. Windows Server 2022 — 1 354 пройдено, 3 очікувані
пропуски перевірок лише для POSIX. Ruff lint і format, автоматизовані WSLg
та відповідні GUI перевірки — **PASS**.

Перевірки native Windows 11, DPI, апаратного GPU, фінального виконуваного файла
та інсталятора залишаються завданнями Phase 12.

## 18.11.2026 — Архітектура Phase 11 «Аналіз»

Власник погодив ядро архітектури D11-01–D11-05. Записано
[ADR-0011](adr/0011-analytics-mode.md) та
[поправку A11](../TECHNICAL_SPECIFICATION.md#srs-v30--amendment-a11-analytics-mode).
Обсяг цього завдання обмежено документацією. Реалізацію Phase 11, додавання
моделей, міграцій, UI чи тестів за цим завданням заборонено.

- **D11-01.** Читати одну SQLite, перевіряти збережені авторитетні оцінки
  без повторного оцінювання. Міграція 0009 не є передумовою.
- **D11-02.** Типовий режим `LATEST_COMPLETED_PER_LEARNER`, альтернатива
  `ALL_COMPLETED_ATTEMPTS`. Зберігати вибір останньої завершеної спроби,
  якщо її оцінка відсутня, UNSCORABLE чи недійсна.
- **D11-03.** Instructor читає власний сценарій тільки для поточних груп
  викладання, використовуючи історичний `authorization_group_id`.
  Вибуття учня зберігає історію, вибуття викладача відкликає доступ.
  Administrator має глобальні права.
- **D11-04.** За `NOT_CONFIGURED` показувати «Не налаштовано», окремо
  рахувати спостереження `confirm` і `submit_synthetic`.
- **D11-05.** Необов'язковий AssistantAgent пояснює перевірені агрегати й
  радить. Хмара вмикається явно, офлайн-поради детерміновані.

Запроєктовано `AnalyticsQueryV1`, `ScenarioAnalyticsSnapshotV1`,
`ScenarioMetricsV1`, `LearnerAnalyticsRowV1`, `AttemptAnalyticsDetailV1`,
`CriterionStatisticsV1`, `AnalyticsDataQualityV1` і `AnalyticsExportManifestV1`.
Власна межа авторизації Аналітики використовуватиме
`StoredEvaluationIntegrityValidation` у тому самому знімку SQLite.
Збережена оцінка, learner-only API, контракти Phase 10 та Mentor зберігають
прийняту поведінку. Запропонований хмарний поріг із п'ятьох учнів очікує огляду.

P11-01–P11-16 визначено як майбутні умови приймання для прав доступу,
історії, агрегації, цілісності, UI, експорту, порад, регресій, CI та
ручного приймання власником. Phases 0–10 — **ACCEPTED**,
Phases 11–12 — **NOT STARTED**. Документація — **PENDING REVIEW**.
