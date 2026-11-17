# ADR-0010 — Детерміноване оцінювання та пояснення Mentor

Дата рішення власника: **17.11.2026**.
Статус: **ARCHITECTURE APPROVED**; Phase 10 — **NOT STARTED / ARCHITECTURE APPROVED**.
Це нормативна архітектурна основа для окремо дозволеної майбутньої реалізації.
Публікацію documentation baseline через commit/push/окремий PR дозволено
власником 17.11.2026. Дозвіл на реалізацію, міграцію або merge **не надано**.
Наведені нижче контракти й таблиці є проєктованими, а перевірки — майбутніми.

## Джерела та сумісність

Нормативна основа: [SRS v3.0](../../TECHNICAL_SPECIFICATION.md), датована вузька
поправка Phase 10 від 17.11.2026, §§8–9,12,14,23–24,26.2.
Зберігаємо прийняті [ADR-0008](0008-scenario-integration-publication.md),
[ADR-0009](0009-learner-simulation.md),
[Phase 8 acceptance](../PHASE_8_ACCEPTANCE.md) та
[Phase 9 acceptance](../PHASE_9_ACCEPTANCE.md). Їхні історичні pending/review
позначки не змінюють поточного рішення й не переписуються.

Точні джерела: [rubric/publication contracts](../../src/cyberforge/scenario_integration/contracts.py),
[attempt/event contracts](../../src/cyberforge/learning/contracts.py),
[attempt lifecycle](../../src/cyberforge/application/learner_attempts.py),
[Mentor contracts](../../src/cyberforge/agents/contracts.py) та
[grounded Mentor](../../src/cyberforge/agents/specialized.py).
Schema versions: `rubric-definition-v1`, `scenario-publication-v1`,
`scenario-attempt-v1`, `attempt-event-v1`. Не змінюємо published payloads,
registry meanings, schema validators історичного читання чи існуючі події.

## A. Стратегія й точність обчислення

Незмінний ID стратегії — `cyberforge-weighted-actions-v1`; сумісні лише
`rubric-declarations-v1` та `criterion-registry-v1`. Невідома strategy/schema/
semantics/registry version відхиляється до scoring, без implicit fallback.
Зміна алгоритму потребує нового ID; історичний результат не перераховується.

Сім числових критеріїв оцінюються бінарно: `0` або `1`. Один критерій описовий.
Для завершеної валідної спроби й застосовних числових критеріїв:

`score_percent = 100 * sum(weight_i * score_i) / sum(weight_i)`

Знаменник строго додатний. Незастосовні й описовий критерії не входять до жодної
суми. Default weight — `1`; configurable positive finite weights зберігаються,
включно з чинною верхньою межею `10000`. Вага описового критерію зберігається
як частина незмінної рубрики, але не впливає на число.

Обчислення — Decimal, без binary-float arithmetic. Історичну вагу спершу
завантажують і перевіряють чинним float contract, потім явно конвертують як
`Decimal(str(validated_weight))`; не `Decimal(float)` і не приховане округлення.
Це правило інтерпретує збережене значення, а не відновлює початковий текст вводу.
Published JSON/content_digest не змінюються від такої похідної конверсії.
Суми скінченних Decimal мають бути точними для всіх підтримуваних ваг, незалежно
від ambient Decimal context; проміжне округлення не повинно змінювати результат.
Відсоток округлюється з точного відношення лише для фінального представлення:
`ROUND_HALF_EVEN`, два десяткові знаки (`0.01`). Реалізація має контролювати
precision та точні half-way cases, зокрема при періодичному діленні.
Приклади нормативного округлення: `100 * 1 / 32 = 3.125 → 3.12`;
`100 * 3 / 32 = 9.375 → 9.38`. Pass/fail threshold не вводиться.

Canonical order — наведений нижче registry order, незалежно від порядку вибору
критеріїв у рубриці. Обчислення охоплює тільки вибрані критерії; пропущені не
додаються автоматично. Обмеження доказів: inspection підтверджує факт огляду,
а не правильне розпізнавання загрози чи інтерпретацію побаченого.
Це власна модель CyberForge, без твердження про наукову валідацію.
[NIST TN 2276](https://csrc.nist.gov/pubs/tn/2276/final) описує складність виявлення
фішингового Email людиною; Phish Scale не є індивідуальним scoring algorithm
і не переноситься на складність Web.

## B. Незмінні критерії та доказові умови

Усі вісім ID, labels, descriptions, phases, evidence declarations і дозволені
applicability залишаються точними значеннями Phase 8 registry.
У таблиці `surface/action` уточнює існуючі evidence actions, не розширює vocabulary.

| ID / label | Phase | Evidence declarations та умова | Дозволена applicability |
| --- | --- | --- | --- |
| `email.sender` — Перевірка відправника | email | `inspect_sender`: є `email/inspect_sender` | `all_attempts` |
| `email.link` — Перевірка посилання | email | `inspect_link`: є `email/inspect_link` | `all_attempts` |
| `email.report` — Повідомлення про лист | email | `report`: є `email/report` | `all_attempts` |
| `transition.safe_decline` — Безпечна відмова | transition | `decline`: фінальний completed no-Web path з explicit decline | `all_attempts`, `web_not_visited` |
| `transition.decision` — Рішення про перехід | transition | `decline`, `open_internal`: опис фактичного рішення та його послідовності, без числової оцінки | `all_attempts` |
| `web.address` — Перевірка адреси сайту | web | `inspect_address`: є `web/inspect_address` після trusted display | `web_visited` |
| `web.leave` — Безпечний вихід | web | `leave`: є `web/leave` після trusted display | `web_visited` |
| `web.report` — Повідомлення про сайт | web | `report`: є `web/report` після trusted display | `web_visited` |

Застосовний числовий критерій отримує `1` лише за виконання вказаної умови;
інакше `0`. Повторення дії не збільшує score. Email report і Web report не
взаємозамінні. Web browser controls та валідні authored components є accepted
джерелами evidence з чинною derived provenance; необов'язковий authored component
не є передумовою доступності native control.

Події обробляються за `sequence`, а не сортуються за action чи timestamp.
`decline → open_internal → web_entered → completed` не задовольняє safe_decline.
`open_internal` лише фіксує намір/перехід stage; відвідування потребує trusted
`system/web_entered` після успішного показу точного owned document.
Failed/stopped load та delegated navigation cancellation не є Web visit.
Фінальний no-Web path потребує EMAIL/DECLINED, `COMPLETED`, explicit decline
та відсутності `web_entered`; Web path потребує WEB, confirmed visit і completion.
Стан відтворюється за accepted Phase 9 lifecycle; не вводимо нову вимогу `leave`
для завершення Web, якого чинний service не вимагає. Descriptive decision не
встановлює автоматично правильність рішення щодо навчальної мети викладача.

## C. Застосовність та майбутня publication readiness

`all_attempts` застосовується до обох completed paths; `web_visited` — лише до
confirmed Web path; `web_not_visited` — лише до completed no-Web path.
Non-applicable numerical result має відсутнє значення (`null`), а не `0`;
його вага виключається зі знаменника й чисельника.

Для **майбутніх публікацій після реалізації Phase 10** readiness та atomic
publication повторно перевіряють наявність хоча б одного застосовного числового
критерію **на кожному** підтримуваному completed path:

1. Safe decline без Web.
2. Completion із confirmed Web visitation.

Це prospective service/publication rule, не зміна Phase 8 registry або loader
для історичних рубрик. Чинна перевірка non-Web criterion допускає описовий
`transition.decision`; вона сама не гарантує числового знаменника. Наприклад,
decision-only рубрика або safe_decline з `web_not_visited` без інших числових
критеріїв може не давати числового результату на одному чи обох шляхах.
Історичні accepted publications не змінюються і не стають помилками контракту.
Валідний completed attempt з нульовою кількістю застосовних числових критеріїв
отримує `UNSCORABLE`, reason `NO_APPLICABLE_NUMERICAL_CRITERIA`, denominator `0`,
numerator `0`, percentage `null`. Це не `0%` і не technical failure.

## D. Проєктований EvaluationEvidenceV1

Закритий незмінний локальний контракт, який конструює довірений код із БД;
не приймає user-authored fields, mutable annotations або довільні judgments.
Проєктований schema discriminator: `evaluation-evidence-v1`.

| Група полів | Обов'язковий зміст |
| --- | --- |
| Identity/binding | Exact attempt UUID, learner/scenario/publication IDs, scenario version, manifest digest; exact snapshot/source revisions і digests, rubric ID/revision/digest та schema/semantics/registry versions |
| Events | Ordered immutable `AttemptEventV1` records, event count, terminal sequence, canonical events digest; event IDs, attempt IDs, request/operation identity й provenance зберігаються |
| Terminal state | Валідований `ScenarioAttemptV1`, status `COMPLETED`, completed_at/revision/last_event_sequence; стан звірено з повним replay, terminal event і binding |
| Path | Фактичний completed no-Web або confirmed-Web path, рішення та sequence references; відвідування лише з trusted display event |
| Criterion evidence | Для кожного вибраного критерію: ID, applicability, supporting event IDs/sequences, виконання доказової умови або причина її невиконання; описове рішення окремо |
| Observations | Factual `web/confirm` та `web/submit_synthetic` з event references без field values, secrets або висновків про критичність |
| Integrity | Schema/strategy compatibility, canonical evidence digest, зв'язок із source та events digests |

До scoring відхиляються malformed/unknown versions, digest mismatch, foreign
attempt events, duplicate IDs/sequences, gaps, invalid vocabulary/component
provenance, несумісна request/operation grouping, impossible lifecycle/order,
відсутній або неостанній completion, terminal-state/count/sequence mismatch,
невалідний source binding чи unsupported path. In-progress/abandoned attempts
не оцінюються. Replay перевіряє хронологію за sequence й чинні lifecycle rules;
timestamps мають відповідати accepted UTC/time constraints, а не новому правилу
монотонності настінного годинника. Canonical digest не є криптографічною
атестацією trusted callback і не захищає від довільного local code/DB tampering.

Canonical input/output: SHA-256 UTF-8 JSON, sorted object keys, compact separators,
`ensure_ascii=False`, explicit schema version; arrays мають нормативний порядок.
Events — за sequence, criteria — за registry order, observations — за event sequence.
UUID — стандартний lowercase string; нові contract timestamps — UTC у форматі
`YYYY-MM-DDTHH:MM:SS.ffffffZ` із шістьма microsecond digits; optional поля явно
`null`. Decimal — canonical
plain decimal strings без exponent/зайвих кінцевих нулів/negative zero; фінальний
percentage зберігає два десяткові знаки. Digest field виключається з власного
hash input. Існуючі manifest/rubric digests перевіряються їхнім **існуючим**
`fingerprint` serialization, без перерахунку в новому форматі. Новий evidence
digest включає ці перевірені source digests; canonical event projection зберігає
кожне persisted contract field без доданих learner annotations. Реалізація має
зафіксувати golden vectors до першого persisted v1 result.

### D.1. Canonical supporting references — F10-02

Правила належать до evaluation-evidence-v1; історичний AttemptEventV1 не змінюється.
Один event reference — закритий JSON object рівно з двома полями:
`{"event_id":"<UUID>","sequence":1}`. `event_id` — string із точним persisted UUID
у lowercase canonical form; `sequence` — strict positive integer (не bool/string).
Обидва значення мають відповідати одному запису parent attempt у повному stream.
Reference не має власного mutable label чи нового event identity. Object keys
серіалізуються за §D; масив references завжди ascending sequence, без duplicate
UUID або sequence. Distinct repeated actions з різними IDs зберігаються.

Три структури мають різне призначення:

1. **Complete event stream** — усі immutable AttemptEventV1 від started до
   terminal completed включно, рівно один раз, ascending contiguous sequence.
   Count/terminal sequence та events digest охоплюють весь stream, включно з
   superseded decisions і repeated actions; це не subset criterion evidence.
2. **Per-criterion supporting references** — для applicable ordinary numerical
   action criterion усі qualifying events на exact surface, ascending sequence.
   Для Web — лише actions після trusted system/web_entered з accepted native
   browser-control або authored-component provenance. Visit proof зберігається
   окремо в path references. Repeats не збільшують binary score. Немає matching
   action або criterion non-applicable → порожній references array; score тоді
   відповідно 0 або null. References не дублюють event і не включають unrelated actions.
3. **Completed-path references** — no-Web: останній effective transition/decline
   плюс terminal system/completed; confirmed-Web: transition/open_internal,
   перший trusted system/web_entered та terminal system/completed. References
   exact, unique й ascending sequence; повний replay за §B обов'язковий, самі
   references без stream не доводять відсутності superseding decision/відвідування.

Для transition.safe_decline qualifying proof — лише валідний final completed
no-Web path. Supporting array збігається з no-Web path references: останній
(effective) decline та terminal completion. Попередні repeated declines не
підміняють effective decline; superseded decline перед open_internal ніколи
не є успішним proof. На Web path supporting array safe_decline порожній:
applicable all_attempts дає 0, non-applicable web_not_visited дає null.

Для descriptive transition.decision supporting array містить усі chronological
transition/decline та transition/open_internal, без system events. Final action
визначається останнім transition event: decline для no-Web або open_internal
для Web. Зміна decline → open_internal залишається видимою; terminal decision
state LEFT є окремим factual Web outcome, не переписує transition history.
Число чи judgment правильності не додається. Path references окремо зв'язують
цей опис із validated completion; критерій лишається descriptive.

### D.2. Arithmetic equivalence та source identity — F10-04

Для однакового набору criterion IDs, weights, applicability та evidence outcomes
порядок подання критеріїв не змінює numerical score, normalized numerator/
denominator або canonical registry order evaluation details. Це computational
invariance, а не рівність повних source-bound digests різних публікацій.
Перестановка criteria в published RubricDefinitionV1 може змінити existing
content_digest. Оригінальний digest та payload незмінні; result/evidence binding
включає exact rubric digest. Different immutable source digests дають distinct
source-bound evidence/result digests навіть при однаковій arithmetic. Існуючий
rubric fingerprint algorithm не змінюється, source identity не нормалізується.

## E. Проєктований EvaluationResultV1

Один immutable authoritative result для completed attempt, не mutable cache.
Проєктований schema discriminator: `evaluation-result-v1`.

| Поля | Зміст та інваріанти |
| --- | --- |
| Result/source identity | Result ID, attempt UUID, learner/scenario/version/publication IDs, manifest identity/digest, source snapshot refs, rubric ID/revision/digest, schema/semantics/registry versions |
| Strategy/evidence | `cyberforge-weighted-actions-v1`, evidence/events digests, event count/terminal sequence та completed-state revision, completed path |
| Outcome | `SCORED` або `UNSCORABLE`; reason code `null` для SCORED, явний код для UNSCORABLE |
| Arithmetic | Exact Decimal weighted numerator/denominator; final percentage nullable. SCORED: denominator > 0, percentage 0.00–100.00; UNSCORABLE: нульовий denominator і null percentage |
| Criterion details | Один запис на selected criterion у canonical order: exact identity/label/phase/weight/applicability, applicable flag, numerical 0/1 або null, weighted contribution або null, evidence refs/reason. Descriptive criterion завжди без numerical contribution |
| Description/observations | Фактичний transition outcome, включно з reversed decision, observed risk actions, critical policy status `NOT_CONFIGURED` |
| Audit/integrity | UTC evaluation timestamp, result digest над canonical immutable envelope без власного digest field |

Числовий payload детермінований від immutable inputs. Evaluation timestamp/result
ID позначають перше створення; вони не є повторно обчислюваною оцінкою. Повторний
запит повертає той самий stored envelope/digest. Golden vectors для повного digest
використовують фіксовані ID/timestamp; не вимагають однакової години нових запусків.

| Стан | Представлення та право на final evaluation |
| --- | --- |
| No attempt | Немає attempt/result; жодного score |
| IN_PROGRESS | Незавершена спроба, без final score |
| ABANDONED | Явно припинена спроба, без final score |
| COMPLETED, result відсутній | Очікує scoring; не нуль і не UNSCORABLE |
| SCORED | Валідна оцінка, включно зі справжнім `0.00%` при позитивному знаменнику |
| UNSCORABLE | Валідне завершення, історична рубрика без застосовних числових критеріїв; null percentage та reason |
| Technical evaluation failure | Окремий retryable operation/UI error; не valid final evaluation і не заміна score нулем |

Unsupported strategy/version, corrupted evidence та storage failures не записуються
як успішні `UNSCORABLE` results. Не створюємо placeholder final rows при помилці.

### E.1. StoredEvaluationIntegrityValidation — F10-01

Обов'язковий invariant кожного authoritative stored-result read. Відповідальний
майбутній trusted internal EvaluationService; його єдиний validation path
використовується retries, learner results/history/detail, Mentor preparation
та майбутнім Phase11 analytics adapter. Пряме читання ORM row не надає authority.

Спочатку service перевіряє caller session/active account та права endpoint.
У consistent DB read transaction завантажує attempt і перевіряє learner ownership
до завантаження protected result/details та exact immutable sources. Internal
source loader за §G обмежений цим bound attempt, не вимагає active grant і не
розкриває restricted content. Analytics adapter після окремого Phase11 RBAC
також мусить використовувати цей validator; нових analytics прав не надаємо.
Result, criterion rows, authoritative publication/rubric/events та terminal state
перевіряються в одному consistent snapshot до повернення data, Mentor facts
або включення score в analytics. Authorization failure не розкриває чужі records.

Validator обов'язково звіряє:

1. Supported result schema та frozen scoring strategy version, registry/semantics
   compatibility; невідомі versions fail closed, без fallback до current scorer.
2. Canonical result digest над повним envelope за §E, включно з canonical
   criterion details. Persisted detail rows повинні точно відповідати envelope.
3. Exact attempt identity/learner/scenario binding та immutable referenced sources.
4. Publication, ScenarioVersion та manifest digest із authoritative source rows.
5. Rubric ID, revision, digest і compatible registry/semantics із exact snapshot.
6. Stored evidence/events digests, count, terminal sequence/revision та path
   проти canonical authoritative immutable source за §D/D.1; не проти latest draft.
7. Envelope/detail field equality: IDs, weights, scores, contributions,
   applicability, evidence references, descriptions та canonical position.
8. Exactly one detail на selected rubric criterion: без additional/missing/
   duplicate IDs або positions, із canonical registry order.
9. Validated numerical/descriptive applicability та supporting references;
   descriptive/non-applicable значення й contributions null за §§A–E.
10. Arithmetic consistency: точні converted weights і binary evidence outcomes,
    contributions, numerator/denominator, final half-even percentage, status,
    reason code та null invariants. SCORED має positive denominator і null reason;
    UNSCORABLE має zero sums, null percentage та NO_APPLICABLE_NUMERICAL_CRITERIA.

Це verification stored result проти exact immutable inputs і frozen strategy,
не створення нового evaluation: допустимі read-only digest/evidence/Decimal
consistency calculations, без нового result ID/timestamp, запису чи застосування
новішого algorithm. Retry повертає лише той самий **перевірений** stored envelope.
Для історичних supported versions зберігається відповідний validation contract.

Corruption/inconsistency → explicit integrity error (нормативний reason
STORED_EVALUATION_INTEGRITY_ERROR; exact error schema — Contract Freeze Gate).
Record не повертається як valid evaluation, не передається Mentor і не включається
як valid score в analytics. Не видаємо замість нього 0, UNSCORABLE або pending.
Не overwrite/delete/repair/rescore; зберігаємо record для controlled investigation.
Такий retry не переходить у creation path. SQLite immutability guards не замінюють
цю validation. Технічна неможливість прочитати sources також fail closed без
зміни result, з відмінною operational error причиною за frozen error contract.

## F. Critical observations v1

Історичне `critical_action=null` залишається незмінним. У v1 немає numerical
critical penalties, score caps або retroactive critical violation declarations.
`confirm` і `submit_synthetic` можуть бути factual risk-related observations;
їх наявність не доводить автоматично критичну помилку чи реальне передавання даних.
Для publication без declared critical rules status — `NOT_CONFIGURED`.
Відсутність налаштованих правил **не** є доказом відсутності порушень.
Formal instructor-defined classification/penalties потребують окремо погодженого
versioned publication contract; це не приховане розширення rubric-declarations-v1.

## G. Lifecycle та authorization

1. Accepted Phase 9 completion залишається незалежною atomic операцією.
2. Лише після confirmed completion окрема evaluation operation читає exact
   immutable attempt/events/publication/rubric; жодного latest draft підміщення.
3. Детермінований scorer не викликає AI; перевіряє compatibility/evidence.
4. Одному completed attempt відповідає один immutable authoritative result.
5. Retry після authorization та StoredEvaluationIntegrityValidation (§E.1)
   повертає stored result; algorithm upgrade не замінює історичний result.
6. Concurrent calls серіалізуються й обмежуються DB uniqueness, а не лише UI lock.
7. Result та всі criterion rows commit атомарно; partial result недоступний.
8. Failure відкочує evaluation writes і дозволяє retry без зміни completed attempt.
9. Mentor запускається після scoring commit; його failure не змінює оцінку.
10. Історичне scoring читає exact immutable snapshots через вузький internal
    path без вимоги active learner grant; це не універсальний content endpoint.

Learner-facing operations повторно перевіряють active authenticated learner
account/session і ownership навіть для stored-result retry. Revoke/membership
removal/archive не стирають спроби/оцінки й не блокують власну history/results.
Вони продовжують блокувати learner simulation writes та restricted content.
Internal snapshot loading відбувається лише для bound completed attempt у
довіреному service, не приймає довільний source selector і не повертає приховані
матеріали в UI. Deactivation/logout/stale session залишаються забороною доступу;
instructor/admin не отримують learner endpoints. Їхні майбутні analytics rights
визначає Phase 11 окремо; цей ADR їх не розширює.

## H. Проєктоване зберігання після migration 0007

Одна існуюча SQLite. Майбутня additive migration після
[`0007_learner_attempts`](../../src/cyberforge/persistence/migrations/versions/0007_learner_attempts.py)
проєктується для трьох таблиць; **міграція не створена й не виконана**.

| Таблиця | Ключі та consistency |
| --- | --- |
| `evaluation_results` | PK result ID, UNIQUE NOT NULL attempt_id FK → scenario_attempts.id; FK learner/scenario/publication та exact version/rubric refs до чинних source rows; immutable payload/digests/status/Decimal strings |
| `evaluation_criteria` | FK result_id → evaluation_results; UNIQUE(result_id, criterion_id); один рядок на selected criterion, canonical position, exact Decimal strings/null, applicability/evidence refs |
| `mentor_feedback` | FK result_id → evaluation_results; UNIQUE(result_id) для authoritative v1 feedback; versioned sanitized explanation/fact binding, deterministic/offline або validated model-selection provenance, timestamp/digest |

Rubric row чинно keyed by version_id, не окрема вигадана rubric-ID table:
FK використовує accepted ScenarioVersion/rubric storage identity, а logical
rubric ID/revision/digest звіряються зі snapshot. Усі дубльовані identity поля
мають бути узгоджені з attempt/publication через constraints/DB guards і
transactional validation. `PRAGMA foreign_keys=ON`; жодних orphan/cascade deletes
історії. Result insert дозволено лише для completed bound attempt; status/null/
denominator/criterion completeness перевіряються до atomic commit.
Точні ORM column/index/trigger names визначить окремо дозволена реалізація.

Зберігаємо BEGIN IMMEDIATE/реальну transactional DDL discipline, DB unique
attempt winner та immutable UPDATE/DELETE/INSERT OR REPLACE protection для
results/details/feedback. Mentor feedback commit окремий від scoring, атомарний
сам по собі; відсутній/failed Mentor не лишає placeholder feedback. Після
authoritative offline або AI feedback commit retry повертає stored feedback;
v1 не перезаписує його при відновленні provider. Score залишається незалежним.
Upgrade зберігає existing publications/attempts/events без backfill/rewrite чи
автоматичного scoring. Downgrade з будь-якими evaluation/criterion/feedback
даними fail closed; rejected multi-revision downgrade відкочує DDL/triggers та
Alembic stamp разом, зберігаючи historical results. Порожній downgrade потребує
окремих migration tests; owner DB ніколи не використовується для цих перевірок.

## I. Mentor grounding та offline feedback

Повторно використовуємо `MentorAgent`, `MentorInputV1`, `FactV1`, `ExplanationV1`
і чинну `ExplanationSelectionV1` validation там, де вони сумісні.
Trusted local code лише після StoredEvaluationIntegrityValidation (§E.1)
будує sanitized educational facts із вже збереженого result;
LLM лише обирає/пояснює supplied facts та дозволені topics. Не дозволені нові
scores, причинні/психологічні висновки, unsupported claims або critical labels.
Факт inspection не перетворюється на твердження «загрозу правильно розпізнано».

Cloud input не містить learner/attempt/publication IDs, персональних даних,
raw events, actual credentials, secrets, form values або unanonymized results.
Локальний adapter передає лише мінімальні synthetic facts/objective й permitted
precomputed numerical summary. Score не отримується від provider і не приймається
назад як editable значення. Cloud access лише explicit configuration; baseline
працює offline з MockLLMProvider та deterministic local explanation без моделі.
Provider timeout/unavailability/invalid selection/unsupported facts ведуть до
детермінованого українського feedback, не до failure scoring.

Compatibility boundary Phase 5: `ResultFactsV1(status="completed")` вимагає
non-null float percentage, тому `UNSCORABLE` не можна замаскувати під completed
з нулем або incomplete. Для нього потрібне детерміноване local explanation
з явною причиною; `ExplanationV1(result=None)` може містити sanitized facts і
limitations, а nullable evaluation status/percentage залишаються в локальному
versioned feedback envelope. `MentorInputV1` для цього не викликається.
Для SCORED float потрібен лише як presentation adapter із фінального Decimal;
цей float не повертається в arithmetic/digest result. Наявні topics bounded;
нові topics/statuses/typed evaluation references потребують явного нового
versioned contract, а не тихої зміни Phase 5 contracts. Схему локального
feedback envelope треба зафіксувати перед persistence implementation.

## J. UI та межа Phase 11

Phase 10 додає до «Мої результати» власні results/history, per-criterion details,
applicability, descriptive outcome, observations і feedback. UI українською;
стани відсутності/очікування/припинення/UNSCORABLE/error/справжнього нуля різні.
Незастосовний Web не показується як `0%`; `NOT_CONFIGURED` не означає «порушень немає».
Обмеження evidence пояснюються без автоматичного pass/fail.

Phase 11 володіє instructor analytics, aggregation/comparison, dashboards та
exports. Майбутня analytics service читає stored immutable evaluation results
лише через StoredEvaluationIntegrityValidation (§E.1),
не запускає власний scoring і не змінює rubric/результати. Немає другої бази
чи нового Scenario identity. Впровадження Phase 11 окремо не дозволене.

### J.1. Contract Freeze Gate — F10-03

Вже погоджені architectural invariants: strategy/formula, criterion semantics та
applicability, Phase8–9 compatibility, lifecycle/immutable storage, обов'язкова
StoredEvaluationIntegrityValidation, canonical references §D.1, critical policy,
Mentor grounding/privacy та learner UI/Phase11 boundary. Вони не відкладаються
до schema design і не можуть бути тихо змінені work package.

Exact wire/storage schemas **ще не повністю frozen**. До формалізації належать
exact typed field names/types, enums/reason-code sets, optional/null invariants,
nested criterion/evidence schemas, serialization/golden vectors, SQLite storage
representation/constraints, local versioned Mentor feedback envelope та правила
compatibility/version migration persisted v1 records. Уже визначені normative
reference fields, serialization і reason codes є constraints цієї формалізації.

Contract Freeze Gate обов'язковий у WP1, до persistence WP3, першої Phase10
migration і будь-якого persisted EvaluationResultV1 або Mentor feedback output.
Після окремого implementation authorization WP1 має підготувати й перевірити:

1. Complete typed contract definitions, включно з feedback та errors.
2. Exact canonical serialization specifications і digest coverage кожного поля.
3. Deterministic golden vectors, включно з repeated actions/reversed decisions.
4. Compatibility та corruption test vectors, включно з stored-result reads.
5. Contract-to-database field mapping, constraints та representation.
6. Documented review відповідності ADR-0010 і SRS v3.0 та його результат.

Specification та ці докази повинні пройти documented review до будь-якої першої
migration/schema implementation або persisted v1 output. WP3 не може обійти gate;
WP5 feedback schema входить до цього ж gate, не додається після persistence.
Після freeze incompatible changes потребують explicit new versions та documented
compatibility/migration rules, без silent mutation існуючих v1 records.
Цей docs-only increment не створює typed runtime definitions, tests чи migration
і не оголошує Contract Freeze Gate пройденим або implementation дозволеним.

## K. Майбутня специфікація acceptance tests

**Усі нижче наведені перевірки — вимоги до майбутньої реалізації, не виконані
тести й не докази готовності Phase 10.** Work packages —
[IMPLEMENTATION_PLAN](../IMPLEMENTATION_PLAN.md).

| ID | Майбутній критерій та очікуваний результат |
| --- | --- |
| P10-01 | Обидва valid completion paths; no-Web без fabricated Web zero, confirmed-Web лише після trusted `system/web_entered`; failed display/open_internal-only не є visit/completed evidence |
| P10-02 | Усі сім numerical IDs окремо: defined evidence → 1, відсутнє → 0 для applicable; report surfaces відокремлені, native та authored Web provenance; repeated actions не множать score |
| P10-03 | `transition.decision` descriptive, final decision/chronology збережені; decline→open_internal не дає safe_decline; completion не потребує нового leave rule |
| P10-04 | Усі allowed applicability, criterion subsets/default/custom positive finite weights, descriptive/non-applicable exclusion; future publication обидва paths мають positive numerical denominator; historical rubric load не посилено |
| P10-05 | Genuine 0.00% при positive denominator відрізняється від no attempt, incomplete, abandoned, pending scoring, technical failure; historical decision-only/path-empty → UNSCORABLE/null/reason, без ділення на нуль |
| P10-06 | Decimal conversion історичних floats, tiny/large weights і upper bound; exact sums, fixed rounding/half-even vectors 3.125 та 9.375, periodic ratios/near-boundary cases, ambient context independence; no pass/fail threshold |
| P10-07 | Дві окремі категорії: equivalent criterion inputs у різному selection order → same score/numerator/denominator/canonical detail order; різні exact published rubric digests → distinct source-bound evidence/result digests навіть при identical arithmetic. Golden vectors також перевіряють canonical null/UTC/Decimal, fixed envelope ID/timestamp, original source digests unchanged та verified stored retry identity |
| P10-08 | Unknown strategy/schema/registry/semantics, malformed rubric/nonfinite weights, corrupted digests, foreign/duplicate/gapped/out-of-order histories, invalid component/request grouping/terminal state відхиляються без valid final row |
| P10-09 | Duplicate/concurrent/retried requests мають рівно один authoritative result з повними criterion rows; retry після failure успішний, after commit повертає той самий result; algorithm upgrade не переписує history |
| P10-10 | Forced failures між result/detail writes дають atomic rollback, completed attempt/events незмінні; recovery/restart; migration0007 upgrade preservation, FK/integrity, immutable update/delete/replace denial, unsafe downgrade і multi-revision DDL/stamp rollback |
| P10-11 | Revoke/archive/membership change: owner history та historical scoring без current grant, restricted content і simulation writes denied; restore зберігає original publication; deactivation/logout/stale/foreign learner/instructor/admin learner-endpoint denial |
| P10-12 | `critical_action=null`, policy NOT_CONFIGURED, factual confirm/submit_synthetic; відсутні invented violations/penalties/caps, UI не заявляє відсутності порушень |
| P10-13 | Offline deterministic Mentor/Mock, cloud disabled baseline, sanitized facts/no personal/raw sensitive data; unsupported AI fact/topic/score/claim rejected, timeout fallback; UNSCORABLE не примушує incompatible MentorInputV1; feedback failure не змінює scoring |
| P10-14 | Learner history/detail/UI states, compact layout, restart та session clearing; analytics не реалізовано й не recompute; focused checks → stable full Ruff/pytest, security/RBAC/migration/concurrency regressions, final-head Linux/Windows CI, owner manual WSLg acceptance |
| P10-15 | Native Windows 11/DPI/hardware GPU/package/executable/installer acceptance — Phase 12; CI/WSLg не зараховуються як physical Windows validation. Migration changes потребуватимуть build/isolated-wheel checks за owner workflow |
| P10-16 | StoredEvaluationIntegrityValidation на read/retry/Mentor/analytics: modified result payload/digest, missing/extra/duplicate detail, modified weight/score, envelope/detail numerator/denominator mismatch, modified attempt/publication/rubric binding, evidence digest/terminal sequence corruption → explicit integrity error; invalid record не повертається/не пояснюється/не агрегується, не overwrite/delete/repair/rescore. Навіть recomputed envelope digest не приховує source/detail inconsistency; перевіряється збереження всіх records і result ID/timestamp |
| P10-17 | Canonical reference golden vectors §D.1: repeated sender/link inspections, repeated Email/Web reports, repeated Web address/leave; multiple declines і decline→open_internal→web_entered→completed; final effective decline+completion без Web. Усі qualifying action refs unique/ascending, binary score не зростає; complete stream/per-criterion/path refs відокремлені; identical stream/source → identical references/digests, altered valid order/identity → distinct digest, impossible order → rejection |
| P10-18 | Contract Freeze Gate: complete typed contracts, enums/null/errors/feedback, exact serialization/golden/compatibility/corruption vectors, DB mapping і documented ADR/SRS review до першої migration/WP3 або persisted result/feedback; без gate persistence заборонена; incompatible post-freeze change вимагає versioning. Це future check, не passed gate |

Architecture approval не є implementation acceptance. Окремий дозвіл потрібний
перед будь-якими runtime/test/migration changes; потім engineering checks,
owner review/acceptance та окремий merge gate. Ризики: historical unscorable
rubrics, точна Decimal/canonical serialization реалізація, trusted local process
boundary, privacy/Mentor adapter та ще не виконані concurrency/migration/UI checks.
