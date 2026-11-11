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
