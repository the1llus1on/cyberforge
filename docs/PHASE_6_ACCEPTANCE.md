# Phase 6 — Email Constructor

**Статус:** REVIEW; прийняття виконує лише власник.
Окремий дозвіл Phase 6 отримано 13.11.2026 після ACCEPTED Phase 5 / PR6,
merge `8a6beabf13ec4da43d2ce26bb78bccc9fce64340`. Гілка:
`feat/phase-6-email-constructor`. Merge та Phase 7 не дозволені цим завданням.

## Owner-requested UX revision in PR #7

The owner did not accept the previous visual presentation. This follow-up stays
in Phase 6 REVIEW and supersedes the earlier mailbox/source-view descriptions.
UI text remains Ukrainian; this change's technical report is in English.

The light native Qt mailbox now has a Gmail-inspired browser tab/address strip,
mail search/header, responsive folder rail, generated inbox and a separate
opened-message view. Single click or Enter opens a message; the mailbox back
button returns to the inbox. Unread emphasis changes only in memory. Synthetic
recipient/time details are template presentation, not learner records or actual
delivery metadata. Browser navigation, compose and reply controls are disabled.
The dark CyberForge shell and its single scenario catalog are unchanged.

«Уточнення викладача для перегенерації» is an instruction for the next generation.
The helper explicitly says it does not directly edit a message; the saved email
changes only after «Зберегти». «Перегенерувати» produces an unsaved candidate.

«Структура / код» separates canonical full EmailDraftV2 JSON from an HTML content
projection for the selected message. The HTML is generated locally with escaped
data and fixed markup; it is not returned by the AI, used by the Qt interface,
executed or persisted. This is the explicit SRS §5.5 trade-off: inspectable email
markup without presenting fabricated HTML as native widget source. See ADR-0006.

### Updated owner review checklist (WSLg)

Use the isolated setup below, or restart against your existing demo database
with `--email-demo`; do not reinitialize an existing database or credentials.

1. Open a saved scenario and its Email Constructor. Confirm the outer shell is
   dark and only the browser/mail preview is light.
2. Review the generated inbox, sender/subject/snippets and timestamps. Search for
   a background sender; open it by click or keyboard Enter.
3. Review the reading view: subject, sender/address, synthetic recipient/time,
   body and inactive internal resource. Return to the inbox with its back arrow.
4. Open «Структура / код». JSON is canonical; the separate HTML tab is clearly
   described as a local content projection. Check read-only behavior and Copy
   in each tab. HTML should reflect the currently opened message.
5. Type a regeneration instruction. Confirm the existing preview/saved artifact
   stays unchanged until «Перегенерувати» finishes and a new unsaved candidate
   appears. Save explicitly, return to the card, reopen and inspect persistence.
6. At 1100×720, check both inbox and reading views: Back, refinement, source,
   Generate/Regenerate and Save remain visible. Long content scrolls within the
   message/source fields. Review keyboard focus and the light/dark contrast.
7. Confirm no browser navigation, real sending, publication or Web Constructor
   action is available. Native Windows 11 manual acceptance remains Phase 12.

Review screenshots: [inbox](screenshots/phase-6-gmail-inbox.png),
[opened message](screenshots/phase-6-email-preview.png),
[1100×720 reading view](screenshots/phase-6-gmail-compact.png).
Automated evidence for this revision is appended to DEVELOPMENT_LOG.md and the
existing PR #7; owner manual acceptance remains pending.

## Вимоги та перевірка

| SRS | Реалізація / критерій REVIEW |
| --- | --- |
| §§4.5–4.7 | Окремі Email/Web блоки; п’ять правдивих Email states; зелена рамка лише після commit і local structural validation; Web не створено |
| §§4.9,11.4–11.7 | Точні ID/version/parameter revision/context/provenance; immutable published; stale draft fail-closed; без копіювання матеріалів між версіями |
| §§5.1,9.2,10.1–10.5 | Authorized EmailMaterialService → accepted EmailScenarioAgent → GatewayRunnable → LLMGateway; generation лише явним натисканням |
| §§5.2–5.4 | Native Qt mail template приблизно 90% центральної ширини, main + 1–8 background messages, sender/address/subject/snippet, keyboard/read state/scroll; лише валідні slots |
| §5.5 | Canonical JSON and a separately labelled inert HTML content projection; read-only modal, monospace, highlighting, scrolling/copy; never claimed as Qt interface source |
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
4. «Структура / код»: canonical JSON and separate HTML content projection,
   both read-only with highlighting, copy and scrolling (details above).
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
Final UX-revision Ruff lint/format: success,92Python files; full pytest:
**698 passed / 324.13s**, all690existing tests retained plus8new cases.
Focused source/UI suite: **33 passed / 48.43s**, plus the final active-search
regeneration regression: **1 passed / 1.77s**. Real WSLg/Wayland:
**30 passed / 73.76s**, plus **1 passed / 2.50s** for the final search reset,
including both minimum-size mailbox states and the
existing scenario-card footer regressions. The baseline Phase6 packaging/
migration/installed-wheel checks passed before this UI-only follow-up; packaging
was not repeated under the approved verification policy. Review screenshots:
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
