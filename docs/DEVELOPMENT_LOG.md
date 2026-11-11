# CyberForge — журнал розробки

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
