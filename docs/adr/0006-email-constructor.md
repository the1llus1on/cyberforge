# ADR-0006 — Email Constructor: явне збереження та доставка результатів

**Статус:** реалізація Phase 6, очікує review власника.
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
