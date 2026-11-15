# ADR-0006 — Email Constructor: явне збереження та доставка результатів

**Статус:** ACCEPTED власником проєкту 2026-11-15 (Phase6, PR7).
**Дата:** 13.11.2026. SRS §§4.5–4.9, 5.1–5.8, 9.2, 10, 11.2–11.7, 14.4, 21, 23.

## Межа сервісу та дані

UI → EmailMaterialService → accepted EmailScenarioAgent → GatewayRunnable →
LLMGateway. Використовуються наявні AccountService/ScenarioService та одна БД.
Права: власник Instructor/Administrator пише лише власний активний draft;
Administrator читає також чужі матеріали. Published/archived лише читаються.
Перевірки до генерації, після виконання і під час Save. Model IDs не надають прав.

Міграція 0004 додає тільки email_materials: version_id — PK/FK до точної
scenario_versions, власна revision, scenario_revision, source_digest,
schema_version, synthetic context, повний EmailDraftV2 з provenance, created_by,
created_at/updated_at. Жоден наявний запис не переписується. Запис після Save
атомарний у наявній BEGIN IMMEDIATE транзакції, перевіряє version/revision,
archive_revision та material revision. Окрема material revision зберігає прийняту
семантику scenario revision як параметрів. Два редактори не можуть тихо затерти
результат. DB triggers захищають published/archived матеріали й ідентичність.
Downgrade із збереженими листами відхиляється без втрати даних.

Контекст v1 детерміновано відтворюється з trusted scenario ID/version:
«Навчальна організація {id}», «Навчальна служба», синтетична premise та
`scenario_{id}_v{version}`. Він не містить learner/account identity, не залежить
від refinement/parameter revision й зберігається разом з Email для Phase 7.
Зміна параметрів робить попередній запис stale без його видалення. Нова версія
починається без копіювання матеріалів. Повторна генерація передає повний
EmailDraftV2 як previous, перевіряє accepted Phase 5 provenance до LLM.
Provenance — consistency fingerprint, не підпис і не authorization.

## UI та lifecycle

Нативний Qt mail template; generated strings — plain text. Вхідні містять лише
main/background slots чинного artifact. Посилання — неактивний internal ID,
без браузера/SMTP/введення credentials.
Час у detail — явно позначений синтетичний час шаблону, детермінований за
порядком повідомлень, без вигаданої фактичної дати доставки.
JSON modal показує фактичний EmailDraftV2,
read-only, monospace, syntax highlighting, copy. NIST selected/claimed/verified
залишаються відмінними; зелена рамка не означає semantic verification/publication.
Довгі subject/address показуються в read-only native text fields з wrapping і
scrolling; Tab переходить між полями та діями. Локальний workspace stack бере
розміри активної сторінки, щоб прихований Email preview не витісняв Save картки
на1100×720. Центральна панель зберігає доступне прокручування.

QRunnable виконує генерацію у QThreadPool; QObject Signal → @Slot із явним
QueuedConnection доставляє результат лише GUI thread. Request UUID, session epoch,
scenario ID/version/revisions та material revision визначають доставку. Переходи
інвалідують її; старий запит не переносять до іншого сценарію/сесії. Один активний
worker на вікно; нову генерацію дозволено після завершення попереднього. UI
deadline припиняє доставку, але не заявляє backend cancellation. Gateway зберігає
SDK timeout/retry/quota/fallback. Закриття з активним запитом асинхронно очікує його
завершення з працюючим event loop, зберігаючи lifetime pool/bridge/database.

Збережений матеріал залишається в БД до явного Save кандидата. Помилка не стирає
preview; навігація з unsaved candidate/refinement має Save/Discard/Remain guard.
Примусове відкликання сесії очищає приватний UI за наявною політикою shell.

## Конфігурація та межі

Звичайний запуск читає accepted .env configuration без API calls; generation
лише явною дією. Default Mock не видає fixtures за продукційну AI-генерацію:
UI чесно показує unavailable. Явний `--email-demo` ігнорує .env/cloud keys,
використовує окремий deterministic synthetic template через реальні agent/gateway/
scripted Mock. Це позначене демо, не AI і не fallback після cloud failure.
Нових залежностей немає. Web/publication/scoring не реалізуються.

Офіційні Qt API перевірено через Context7:
[QRunnable](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QRunnable.html),
[QThreadPool](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThreadPool.html),
[queued signals](https://doc.qt.io/qtforpython-6/overviews/qtdoc-threads-qobject.html).
Native Windows 11 acceptance лишається ризиком до Phase 12.

## Owner-requested UI/source revision — 13.11.2026

The owner explicitly requested a Gmail-inspired light work area in the existing
Phase 6 PR. A local native Qt stylesheet/palette applies only to MailPreview;
the accepted dark application shell stays intact. The browser/address strip is
visual data, using a reserved `.invalid` address in a read-only QLineEdit. There
is no browser engine, external navigation, SMTP or JavaScript.

Inbox rows use a native delegate, real artifact fields and in-memory read state.
A separate reading view provides sender, synthetic recipient/time and plain-text
body. Active-view minimum-height calculation keeps critical controls visible
at 1100×720 without letting hidden views impose their preferred size.

SRS §5.5 forbids fabricated HTML claimed as the source of native Qt widgets.
The owner prefers inspectable email markup where honest, so the source dialog
now provides **two explicitly different representations**:

- Canonical full EmailDraftV2 JSON, unchanged and still the only stored format.
- A deterministic, standalone HTML **content projection** of the selected
  message. `render_email_html` escapes every data field into a fixed, inert
  template. No scripts, styles, forms, navigable links or external resources
  are emitted. It is viewed only in QPlainTextEdit, never executed or saved.

The HTML projection is neither AI output nor the source of the Gmail-like Qt
interface. The dialog says this explicitly. Recipient and training time are the
same synthetic presentation context shown in the native view, not account data
or model claims. Copy uses the active tab; forced UI clearing clears both buffers.
This resolves the UX expectation without changing the canonical artifact/schema
or weakening structured-output validation. The SRS itself is not edited.

Refinement is labelled as a next-generation instruction. It does not mutate
preview/persistence directly; regeneration creates a candidate and Save remains
explicit. Existing services, worker/request identity, RBAC, provenance, archived/
published restrictions and database schema are unchanged by this follow-up.

## Native content formatting refinement — 14.11.2026

The owner requested richer email presentation without new agent contracts.
The body now uses native QTextEdit/QTextDocument formatting. A controlled
QTextCursor template inserts existing sender/body/resource strings with
`insertText`; no generated string reaches `setHtml`/`insertHtml`. Character,
paragraph and frame formats provide typography, a synthetic sender header and
an inert resource card. Resource loading is denied; there are no anchors,
remote images, scripts, navigation or credential fields. Template labels are
presentation, not additional AI-authored content or persisted data.

This keeps SRS §§5.3/5.5 and the accepted native-widget boundary: EmailDraftV2
JSON is unchanged and canonical. The HTML source tab remains a separately
labelled inert content projection, not the source of the native document.
No agent, service, worker, persistence or migration interface changes are needed.

The private inbox/reader stack uses a native QStackedLayout subclass whose
minimum/height-for-width calculation follows only the active page. This places
the policy at the layout level used by Qt's native geometry queries and prevents
inactive/preferred editor heights from enlarging the constructor. The body keeps
its original65px fallback minimum and internal scrolling; the outer view API,
data flow, lifecycle and accepted application architecture are unchanged.

EmailPage's wrapped title/status/helper labels use vertical Preferred locally,
so platform-dependent preferred line counts cannot become hard outer-page
minimums. Actual wrapping still follows available width. The shared label
factory and surrounding shell are unchanged; a native preferred-height fault
test reproduces the former overflow and protects this policy.


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


## Остаточне прийняття — 2026-11-15

Власник прийняв поточну архітектуру Email Constructor: native Gmail-inspired
preview, canonical JSON, manual edits через trusted service, explicit Save,
protected AI refinement, persistence/provenance/RBAC/threading boundaries.
Owner GUI generation/regeneration і live Groq initial/refinement успішні;
докази та Phase12 deferrals — PHASE_6_ACCEPTANCE.md. Попередні pending/review
записи ADR є історією рішень. SRS/runtime не змінено для acceptance.
Phase7 залишається NOT STARTED / PLANNING до окремого погодження архітектури,
UI/templates/editing та acceptance criteria. Merge PR7 дозволено окремо
власником; final-head CI і actual merge SHA фіксуються в PR7/звіті.
