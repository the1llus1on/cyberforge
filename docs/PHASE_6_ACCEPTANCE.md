# Phase 6 — Email Constructor

**Статус:** REVIEW; прийняття виконує лише власник.
Окремий дозвіл Phase 6 отримано 13.11.2026 після ACCEPTED Phase 5 / PR6,
merge `8a6beabf13ec4da43d2ce26bb78bccc9fce64340`. Гілка:
`feat/phase-6-email-constructor`. Merge та Phase 7 не дозволені цим завданням.

## Owner-requested UX revision in PR #7

The owner did not accept the previous visual presentation. This follow-up stays
in Phase 6 REVIEW and supersedes the earlier mailbox/source-view descriptions.
UI text remains Ukrainian; this change's technical report is in English.
On 14.11.2026 the owner reported manual WSLg review of `0e34dd8`: the overall
layout was acceptable, with typography, icons and reading-view fidelity still
requiring refinement. This feedback does not mark Phase 6 ACCEPTED.

The light native Qt mailbox now has a Gmail-inspired browser tab/address strip,
mail search/header, responsive folder rail, generated inbox and a separate
opened-message view. Single click or Enter opens a message; the mailbox back
button returns to the inbox. Unread emphasis changes only in memory. Synthetic
recipient/time details are template presentation, not learner records or actual
delivery metadata. Browser navigation, compose and reply controls are disabled.
The dark CyberForge shell and its single scenario catalog are unchanged.
The opened body uses available height and internal scrolling, preserving the
critical controls at 1100×720 across different native font metrics.

### Final visual refinement — 14.11.2026

Compared the locally supplied Gmail inbox and opened-message references with
the Phase 6 views. Reference images contain real mailbox data and remain local;
they are not copied to Git or used as training/demo content or graphic assets.

- Mail typography is scoped to the preview: 22px subject, 15px body, 14px sender
  and inbox text, 12px recipient/time. Sender/recipient columns and timestamps
  align; reply/forward have separate native pill controls.
- Original vector drawings extend the existing icon infrastructure. Wide inbox
  rows use one sender/subject/snippet/time line; compact rows use two lines.
  Selected, read and unread states remain local presentation state. The inbox
  and reading view have distinct native toolbars; only real internal navigation
  and search are enabled. No extra fake category/data tabs are introduced.
- The main body uses a developer-controlled native QTextDocument template:
  existing sender text, readable paragraphs, the existing internal resource ID,
  and a clearly inert action card. Strings enter through `insertText`, never
  HTML parsing. Resource loading is blocked. Background messages retain their
  existing text with paragraph formatting. No agent/schema/persistence changes.
- JSON is the canonical stored artifact. The unused HTML source projection
  has been removed; native visual formatting remains.

Remaining visual limits: this is a synthetic native mock, with a text brand,
disabled nonessential folders/actions and no proprietary assets, remote media,
arbitrary HTML/multipart support or external navigation. Long formatted content
and the resource card scroll inside the body, including at1100×720. The scenario
catalog stays visible under the accepted navigation design. The owner has approved the visual design; functional manual editing and live
acceptance remain pending.

«Уточнення викладача для перегенерації» is an instruction for the next generation.
The helper explicitly says it does not directly edit a message; the saved email
changes only after «Зберегти». «Перегенерувати» produces an unsaved candidate.

«Переглянути код» shows the actual current canonical JSON only, read-only with
highlighting, scrolling and Copy. No HTML inspection/rendering/storage exists.

## Mandatory editing completion — current review scope

The owner approved the Gmail-inspired design at cec7d34. Phase 6 remains REVIEW
for functional editing and live acceptance. This section supersedes the earlier
visual/source review descriptions; it does not grant merge or Phase 7 approval.

- Select/open main or background mail, then «Редагувати лист». Native fields:
  synthetic sender name (200), .invalid address (254), subject (300), body (4000).
  Apply validates the complete canonical draft; Cancel discards dialog edits.
  SQLite changes only through the separate «Зберегти» action. The service also
  enforces 1–8 background entries for local add/remove operations; the dialog
  focuses on editing existing messages rather than exposing JSON or attachments.
- Main sender edits update artifact context and optional instructor_sender_name
  metadata. The service recomputes provenance from authoritative identity,
  parameters and controlled context. Organization, premise, version and resource
  stay fixed. Existing saved payloads without this metadata remain readable.
  This is an additive payload change using the existing JSON column, no migration.
- AI gets the current validated working draft, including applied unsaved edits.
  Explicit main-body scope deterministically preserves all other message/slot
  fields; all-content scope permits wider changes. Scope overrides conflicting
  prose. Manual edits require confirmation before regeneration; errors retain
  the working draft and persisted material is unchanged until Save.
- email-prompt-v2 uses scenario topic/audience/objective/description/difficulty,
  tactics, selected NIST intentions, synthetic context and refinement constraints.
  No cue is promoted to verified and no learner scores are generated.
- Email-only output cap4096 (bounded512–8192), independent of the general512
  default. Both provider/model local quota caps still apply. Untyped arbitrary
  generation_parameters are intentionally excluded; no allowlist is needed yet.

### Owner-initiated Groq acceptance — PENDING

Run from the repository with the existing local key; do not paste credentials:

```console
uv run --offline --locked python -m cyberforge.agents.email_live_check --live
```

The opt-in runner uses Groq/openai/gpt-oss-120b only, low reasoning,4096 output
cap,60s timeout, gateway and SDK retries0, max_corrections0, backup=None and
fallback disabled. At most one initial and one main-body refinement request per
invocation. Initial failure stops immediately. The isolated in-memory local
reservation caps (2requests,128000 token reservation) accommodate conservative
UTF8+schema+output accounting; these are not verified account quotas or billing
limits. Provider quotas still apply. No .env updates, artifact persistence,
raw prompts/responses or reasoning traces. Share only the sanitized JSON lines.
Live structure success does not establish pedagogical quality: owner reviews
content through the application and independently decides acceptance.

### Updated owner review checklist (WSLg)

Use the isolated setup below, or restart against your existing demo database
with `--email-demo`; do not reinitialize an existing database or credentials.

1. Open a saved scenario and its Email Constructor. Confirm the outer shell is
   dark and only the browser/mail preview is light.
2. Review the generated inbox, sender/subject/snippets and timestamps. Search for
   a background sender; open it by click or keyboard Enter.
3. Compare typography/icons/row alignment with the supplied references. Review
   the opened subject, aligned sender/recipient/time, formatted paragraphs,
   synthetic header and inert resource card. Scroll the body; return to the
   inbox with its back arrow. Reply/forward remain nonfunctional.
4. Edit both main/background messages; check invalid .invalid addresses/code
   are rejected. Cancel, then Apply. Preview and «Переглянути код» must reflect
   applied edits; persistence must stay unchanged until explicit Save. Reopen.
   Refine in main-body scope and confirm subject/background preservation.
5. Type a regeneration instruction. Confirm the existing preview/saved artifact
   stays unchanged until «Перегенерувати» finishes and a new unsaved candidate
   appears. Save explicitly, return to the card, reopen and inspect persistence.
6. At 1100×720, check both inbox and reading views: Back, refinement, source,
   Generate/Regenerate and Save remain visible. Long content scrolls within the
   message/source fields. Review keyboard focus and the light/dark contrast.
7. Confirm no browser navigation, real sending, publication or Web Constructor
   action is available. Native Windows 11 manual acceptance remains Phase 12.

Review editor: [manual fields](screenshots/phase-6-email-editor.png).

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
| §5.5 | Canonical JSON only; read-only modal, monospace, highlighting, scrolling and Copy; no HTML projection |
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
4. «Переглянути код»: current canonical JSON only,
   read-only with highlighting, copy and scrolling (details above).
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

Current mandatory-editing completion evidence: full offline suite726passed,
Ruff lint/format97files, focused agent/provenance155passed, WSLg editing checks,
and wheel/installed-wheel persistence checks are recorded in DEVELOPMENT_LOG.md.
The first completion CI passed Linux but exposed7compact-layout failures on
Windows; a bounded native scope-selector size hint corrects that regression.
Compact checks now include the Edit and AI scope controls. Final-head CI results
belong to PR7 and the delivery report; owner GUI/live acceptance remains pending.

The following numbers describe the earlier visual revision, before mandatory
manual editing, and are retained as historical evidence:

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
