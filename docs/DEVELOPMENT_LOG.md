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
