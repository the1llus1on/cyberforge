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
