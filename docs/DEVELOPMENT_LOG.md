# CyberForge — журнал розробки

**Поточний стан:** Phase 2 — **ACCEPTED власником 12.11.2026**;
Phase 3 — **ACCEPTED власником 12.11.2026**. Нижче збережено хронологію попередніх REVIEW;
історичні рішення Phase0–2 збережено, актуальні докази Phase3 — наприкінці журналу.

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
