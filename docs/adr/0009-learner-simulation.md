# ADR-0009 — Проходження учнем та незмінні події

Дата: 17.11.2026. Архітектуру й реалізацію Phase 9 дозволено власником.
Статус реалізації: REVIEW; acceptance лише окремим рішенням власника.
Нормативна основа: вузька поправка SRS v3.0 від 17.11.2026,
§§3.9, 8, 11.4, 12.8, 14.2, 16, 23–24.

## Рішення

Використовуємо єдину SQLite, AccountService, PublicationAccessService та exact
immutable EmailDraftV2/WebDraftV3/ScenarioLinkV1/RubricDefinitionV1/manifest Phase 8.
PublicationAccessService._content дозволяє повторно використати чинну перевірку
в тій самій BEGIN IMMEDIATE транзакції, що записує події. Нових runtime
залежностей немає. Catalog дедуплікує Scenario; latest eligible publication
використовується лише для нового старту. Introduction не створює записів.

ScenarioAttemptV1: IN_PROGRESS → COMPLETED або ABANDONED; terminal states
незворотні. EMAIL/WEB є останнім робочим етапом, незалежним від outcome.
UUID identity, learner/scenario/publication/version/manifest, початкова verified
authorization_group_id, immutable scenario name, UTC timestamps, revision та
last_event_sequence утворюють durable state. Початкова group є provenance,
не довічною authorization: альтернативний чинний grant також дає доступ.
Partial unique index learner_id+scenario_id WHERE IN_PROGRESS охоплює всі версії.
Start-or-resume серіалізовано SQLite; terminal attempt дозволяє необмежений repeat
із новим UUID. Звичайний вихід/навігація/закриття не змінюють lifecycle.

Кожен write перевіряє active authenticated Learner, ownership, поточний доступ,
immutable binding, stage/action/component та optimistic revision. Revoke,
видалення membership, archive або deactivation блокують подальші дії. Не
видаляємо/завершуємо/припиняємо автоматично. Restore дозволяє продовжити ту саму
стару publication. History/events мають окремий ownership read path без content;
він не потребує чинного grant, але потребує придатного learner account/session.
Instructor/Admin не мають доступу через learner endpoints; analytics — Phase 11.

## Event contract та state machine

AttemptEventV1 містить UUID event/attempt/request, positive sequence, surface,
action_id, optional exact component_id, UTC timestamp, operation_digest/index.
Versioned vocabulary:

| Surface | Actions |
| --- | --- |
| email | email_opened, inspect_sender, inspect_link, report |
| transition | decline, open_internal |
| web | inspect_address, leave, report, confirm, submit_synthetic |
| system | started, web_entered, completed, abandoned |

Opening main Email — фактична подія, без автоматичної sender/link inspection.
Report не завершує спробу. Decline записує explicit decision й залишає
IN_PROGRESS; тільки наступне confirmed completion встановлює COMPLETED.
Після restart pending decline відновлюється з БД. До completion учень може
обрати open_internal; це скидає decline. Web leave записує LEFT; completion
залишається окремою explicit confirmed операцією. Abandon також explicit confirmed.

InternalNavigationV1 звіряється з exact publication/scenario/version/manifest/
resource і source_message_identifier=main; жодного URL/DNS/external handler.
open_internal атомарно записує decision та WEB stage. web_visited залишається false
до system/web_entered, який trusted UI controller надсилає лише після successful
local WebEngine load. Renderer failure не створює web_entered. Resume WEB може
повторно завантажити той самий resource без повторення open_internal.
Web actions дозволено лише після successful display. Component/action pair
перевіряється за immutable Web artifact, а не зі словника довільних callbacks.

Одна logical operation зберігає request UUID для retry. Digest охоплює команду,
component та navigation, без expected_revision; replay тієї самої команди
повертає актуальний state без нового event, включно з terminal retry, але лише
після повторної authorization. Інша команда з тим самим request відхиляється.
Нові deliberate inspections мають нові UUID й не deduplicate за action name.
SQLite виділяє sequence всередині serialized transaction; event failure відкочує
state/status. DB triggers забороняють UPDATE/DELETE event, DELETE attempt,
rebind, terminal mutation, invalid vocabulary, sequence gaps та terminal inserts.
Unsafe downgrade з history відхиляється; real owner database не використовується.

Payload не має metadata/form/free-text input. Не пишемо паролі, значення полів,
clipboard, URL query, секрети чи персональні дані до events. Synthetic forms
зберігають fixed readonly demo values та лише action fact.

## UI та WebEngine trust boundary

Learner catalog/workspace/history інтегровано в accepted dark shell. Немає
constructor/source/rubric/hidden cues. Використовуємо MailPreview і WebBrowser,
без паралельного renderer. Native learner controls викликають trusted controller.
WebBrowser додає component-aware signal; preview behavior залишається доступним.
Profile/network/navigation/download/popup/JS/local-file restrictions збережено.
No nested WebEngine QDialog.exec; confirmations asynchronous open/finished.
Session token captured for each simulation; stale callbacks cannot write under
another account. Logout clears content and closes pending confirmations; persisted
attempt remains. Event failure never advances UI as successful persistence.

## Phase 10 handoff

COMPLETED означає завершене проходження, не pass/fail. History показує
«Оцінка ще не обчислена». Немає numerical result, penalty, Mentor або AI calls.
Future ScoringService читає exact publication manifest → snapshot rubric reference,
rubric-declarations-v1/criterion-registry-v1, ordered AttemptEventV1 та state.
web_visited=true потребує successful-display event; open_internal саме по собі
не доводить візит. Explicit decline + COMPLETED + no web_entered є no-Web path.
Missing Web evidence не є zero/failure; criterion applicability визначає Phase 10.
Phase 10 мусить перевіряти schema/semantics compatibility й не змінювати historical
meaning. Critical penalties залишаються окремо погоджуваним Phase 10 scope.

Official API reference checked through Context7:
https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#partial-indexes
BEGIN IMMEDIATE повторно використовує verified AccountService convention.
Physical native Windows 11/DPI/GPU/installer — Phase 12 risk, CI не підміняє їх.

Explicit offline demo adds app-owned Form and Actions before save/publication,
covering inspect_address/report/leave/confirm/submit_synthetic without model
callbacks or editable credentials. Strict canonical tuples revalidate through
JSON, consistent with accepted content loaders. Actual Chromium Tab/Enter
activation is verified separately from deterministic callback mapping checks.

First-head Linux CI exposed Qt delegated-action cancellation emitting
loadFinished(False), as documented by QWebEnginePage. Browser diagnostics and
visit acknowledgement now consume loadingChanged URL/status only for the exact
owned document. Rejected action/external navigation never becomes a renderer
failure or successful visit. Real native cancellation→second action and actual
owned-resource failure are distinct regression checks. No security relaxation.

## Independent review F9-01/F9-02 — 17.11.2026

Обидва root causes підтверджено. Optional authored actions не гарантують evidence
для valid web.address/report/leave rubric. Native Ukrainian browser controls
завжди доступні в learner Web mode; explicit click створює inspect_address/report/
leave. Reserved component namespace browser:<action> не допускається resource_id
авторського компонента. BrowserControl є closed Literal; окремий service endpoint
сам визначає identity, generic endpoint відхиляє reserved IDs. AttemptEventV1
надає typed provenance browser_control/authored_component/application, derived
losslessly з existing persisted identity. No migration/rewrite historical events;
старі authored identities зберігають значення. Publication/rubric незмінні.

Generic record більше не приймає system/web_entered. Private composition hook
створює callback, bound до token+attempt; trusted controller використовує його
лише після exact owned-document loadingChanged success. Request UUID/revision,
current authorization/binding/stage, transactional append і retries збережено.
Failed/stopped load, delegated cancellation, external URLs і renderer termination
не створюють acknowledgement. Restart створює новий callback, зберігає attempt.
Це separation API у довіреному локальному процесі, не cryptographic attestation:
власник Python process/DB може змінити код або storage; private hook не security
boundary проти довільного local code execution. Ordinary learner command не має
доступу до lifecycle dispatch. No JS/network/sandbox exceptions.
