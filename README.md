# CyberForge

Multi-Agent Social Engineering Simulation and Cyber Hygiene Training Platform.

Master's thesis software project.

Локальний навчальний симулятор і конструктор сценаріїв соціальної інженерії.
Цільова платформа — Windows 11; нормативне джерело —
[SRS v3.0](TECHNICAL_SPECIFICATION.md).

## Поточний стан

Phase 0 — Project Foundation: пакет Python, консольна перевірка запуску,
pytest та Ruff. Графічний інтерфейс починається з окремо погодженої Phase 1.
Залежності PySide6, БД та LLM додаватимуться, коли з'являться відповідні модулі.
Секрети, Gemini API та налаштування `.env` для поточного запуску не потрібні.

## Встановлення

Потрібні Python 3.12 та [uv](https://docs.astral.sh/uv/getting-started/installation/).
У корені репозиторію виконайте (команди однакові для WSL і PowerShell):

```console
uv sync --locked
uv run cyberforge
uv run python -m cyberforge
```

`uv` створює локальну `.venv`; активація вручну не потрібна. Перше встановлення
потребує мережі. `uv.lock` фіксує залежності; його слід зберігати у Git.
Очікуваний результат запуску — повідомлення українською про готовність базового
середовища й код завершення 0; вікно поки не відкривається.

## Перевірки

```console
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv build
```

Після встановлення залежностей перевірки можна виконати без мережі:

```console
uv run --offline --locked ruff check .
uv run --offline --locked ruff format --check .
uv run --offline --locked pytest
uv run --offline --locked cyberforge
```

Тести перевіряють установлену дистрибуцію та запуск модуля поза репозиторієм
в ізольованому Python. Для виведення українського тексту в консолі Windows
можна встановити `PYTHONUTF8=1`. Запуск на Windows 11 ще не перевірено.
PySide6 / Qt WebEngine та MockLLMProvider у Phase 0 не реалізовані й не тестувалися.

## Структура та правила

- `src/cyberforge/` — мінімальний пакет і точка входу.
- `tests/` — базові автоматизовані перевірки.
- `pyproject.toml`, `.python-version`, `uv.lock` — середовище та інструменти.
- `docs/IMPLEMENTATION_PLAN.md` — фази й критерії прийняття.
- `docs/DEVELOPMENT_LOG.md` — рішення, фактичні перевірки та обмеження.

Локальні `.env`, бази даних, кеші та результати збирання ігноруються Git.
`.env.example` містить лише безпечні пояснення. Використовуйте виключно
синтетичні навчальні дані. Межі майбутніх модулів визначені SRS §22;
порожні модулі наперед не створюються.

Налаштування звірено з офіційними рекомендаціями
[uv](https://docs.astral.sh/uv/guides/projects/),
[Ruff](https://docs.astral.sh/ruff/configuration/) та
[pytest](https://docs.pytest.org/en/stable/explanation/goodpractices.html).
