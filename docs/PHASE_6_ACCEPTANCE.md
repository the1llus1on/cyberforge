# Phase 6 — Email Constructor

**Статус:** REVIEW; прийняття виконує лише власник.
Окремий дозвіл Phase 6 отримано 13.11.2026 після ACCEPTED Phase 5 / PR6,
merge `8a6beabf13ec4da43d2ce26bb78bccc9fce64340`. Гілка:
`feat/phase-6-email-constructor`. Merge та Phase 7 не дозволені цим завданням.

## Вимоги та перевірка

| SRS | Реалізація / критерій REVIEW |
| --- | --- |
| §§4.5–4.7 | Окремі Email/Web блоки; п’ять правдивих Email states; зелена рамка лише після commit і local structural validation; Web не створено |
| §§4.9,11.4–11.7 | Точні ID/version/parameter revision/context/provenance; immutable published; stale draft fail-closed; без копіювання матеріалів між версіями |
| §§5.1,9.2,10.1–10.5 | Authorized EmailMaterialService → accepted EmailScenarioAgent → GatewayRunnable → LLMGateway; generation лише явним натисканням |
| §§5.2–5.4 | Native Qt mail template приблизно 90% центральної ширини, main + 1–8 background messages, sender/address/subject/snippet, keyboard/read state/scroll; лише валідні slots |
| §5.5 | Read-only modal JSON EmailDraftV2, monospace, syntax highlighting, scrolling, copy; без вигаданого HTML |
| §§5.6–5.7 | Full previous envelope, refinement, новий unsaved candidate; попередній saved artifact зберігається; Save/Discard/Remain guard |
| §§5.8,11.2,14.4 | SQLite email_materials + additive Alembic 0004; full validated payload/context/provenance; explicit transactional Save, повернення на картку, reopen |
| §§16,21 | Service RBAC, archived/published protection, optimistic concurrency/rollback, plain text, no external navigation/SMTP/credential forms; delayed-worker lifecycle tests |
| §§23–24 | Phase 6 REVIEW після перевірок і exact-head Linux/Windows CI; Windows 11 фізично не підтверджено |

Архітектура, схема, concurrency та threading:
[ADR-0006](adr/0006-email-constructor.md). Наявний каталог NIST не змінено:
selected — вибір викладача, claimed — заяви моделі, verified — порожній набір.
Немає NIST score, semantic cue detector або дозволу на публікацію.

## Безпечна ручна WSLg демонстрація власника

У каталозі репозиторію, в одному bash-терміналі:

```bash
phase6_demo_dir="$(mktemp -d /tmp/cyberforge-phase6-demo.XXXXXX)"
uv run --offline --locked cyberforge --init-demo \
  --database "$phase6_demo_dir/demo.sqlite3" \
  --credentials-file "$phase6_demo_dir/credentials.json"
printf 'Приватний файл паролів: %s\n' "$phase6_demo_dir/credentials.json"
QT_QPA_PLATFORM=wayland uv run --offline --locked cyberforge \
  --database "$phase6_demo_dir/demo.sqlite3" --email-demo
```

Збережіть шлях `phase6_demo_dir` для повторного запуску з тією самою БД.
Відкрийте вказаний приватний JSON у локальному редакторі; для входу використайте
`teacher_demo_1` і його випадковий пароль. Паролі не потрібно надсилати в чат.
Команда створює нову ізольовану БД; наявні owner/demo/native Windows дані не чіпає.
`--email-demo` не читає .env, не створює cloud clients і не використовує ключі.
Це позначений deterministic synthetic template через real agent/gateway/Mock,
а не якісна демонстрація результатів хмарної моделі. Refinement у демо додається
як текст інструкції: семантичне переписування потребує явно налаштованого LLM.

1. Увійти → «+» → «+ Новий сценарій». Заповнити синтетичну тему/параметри → Save.
2. Побачити Email/Web «Не створено». Натиснути «Створити електронний лист».
3. Перевірити напис «Офлайн-демо», preview main/background, адреси `.invalid`,
   перемикання мишею й клавіатурою, read/unread state і довгий український текст.
4. «Переглянути код»: JSON відповідає preview, лише читання, copy, scrolling.
5. Додати refinement → «Згенерувати». Новий candidate має unsaved state.
6. Перейти на Home/інший сценарій: «Залишитися» зберігає чернетку;
   «Відкинути зміни» не записує її; «Зберегти лист» явно записує preview.
7. Явне «Зберегти» повертає на картку: Email зелений «Збережено», Web не створено,
   сценарій draft, не опубліковано.
8. Повторно відкрити лист, потім закрити й запустити застосунок з тією самою БД
   і `--email-demo`: запис відновлюється. Не повторювати init-demo для reopen.
9. Змінити й зберегти параметри: Email «Потребує перевірки». Нова генерація
   створює кандидат; попередній persisted record не стирається до явного Save.
10. Перевірити компактне вікно 1100×720, scrolling, focus order і читабельність.
    За потреби прокрутити центральну панель до дій під preview; довгі
    subject/address і body мають власне перенесення та прокручування.

Для реальної хмарної генерації власник окремо запускає звичайний GUI без
`--email-demo` зі своєю чинною accepted `.env` configuration. UI показує provider/
model до явної дії. Startup/selection/refresh API не викликають. Без cloud config
показується unavailable, не fabricated AI success. Groq primary/Hydrogen backup
і gateway quota/retry/fallback не змінено. Live API verification у Phase 6
агентом не виконується і не є частиною цього offline checklist.

## Автоматизовані докази та gate

Фактичні focused/full/packaging/WSLg результати — у DEVELOPMENT_LOG.md.
Final local Ruff lint/format: success,90Python files; full pytest:
**690passed/305.56s**, усі622попередні +68нових cases. Wheel/sdist, packaged
migration і isolated installed-wheel offline agent/Save/reopen/startup — success.
Фінальні27GUI cases пройшли через real WSLg/Wayland, включно з footer regression
на1100×720 та1400×900; preview/save screenshots:
[Email preview](screenshots/phase-6-email-preview.png),
[Saved card](screenshots/phase-6-email-saved.png).
Exact final HEAD, PR URL та Linux/Windows CI job/run evidence фіксуються в PR
і фінальному звіті після push, без циклічного documentation-only commit.
Owner manual checklist поки **не виконано / очікується**. Codex WSLg automation
не є owner manual acceptance. Physical native Windows 11/DPI/keyboard/installer
відкладено до Phase 12 як ризик. Windows Server 2022 CI цього не замінює.

Поза Phase 6: Web Constructor/WebEngine, readiness/publication/assignments,
Learner Simulation, ScoringService та Analytics. Saved green — тільки Email
local structural validity + persistence, не готовність всього сценарію.
