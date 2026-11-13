# ADR-0005: спеціалізовані агенти та перевірювані чернетки

Дата: 13.11.2026. Статус: реалізовано для **Phase 5 REVIEW**, прийняття власником очікується.

SRS §§5–6, 9–13, 23, 26.1 деталізовано в межах явно дозволеної Phase 5.
ADR-0004, SRS і provider policy не змінюються.

## Контракти та виконання

`agents/contracts.py`: Pydantic inputs використовують `ScenarioParameters` і
`ScenarioContextV1`; scenario ID/version — metadata, не авторизація. Caller
отримує дані через чинний `ScenarioService` з RBAC, формує синтетичний DTO і
відповідає за його походження. Агенти не мають session/repository/tools.
`synthetic=True` — зобов'язання trusted caller, не універсальний PII detector.
Відомі ознаки ключів, зовнішні email/HTTP references і markup відхиляються;
довільні власні назви не можна надійно класифікувати автоматично.

`EmailSlotsV1`: основний та 1–8 фонових листів, синтетичні `.invalid` адреси,
indicators, claimed NIST IDs, internal resource, обмежені дії. `EmailDraftV2`
доповнює канонічний `EmailArtifactV1`, не змінює його семантику.
`WebSlotsV1`: один із login/portal/notice/document, tab/heading/body,
display-only HTTPS `.invalid`, labels, до 3 синтетичних form descriptors,
instructions/actions/cues. `WebDraftV2` містить канонічний `WebArtifactV1`.
Жодних довільних URL destinations, form values/endpoints, HTML/CSS/JS чи commands
як виконуваних структур. Тексти залишаються даними; майбутні templates повинні
їх екранувати, а Simulator — ізолювати мережу.

Контекст, версія, parameters, internal resource і template перевіряються локально;
context token прив'язує відповідь до проєкції запиту. Це structural consistency,
не доказ повної семантичної узгодженості довільного тексту. Instructor review
має перевірити зміст і навчальну доцільність до майбутньої публікації Phase 8.
Regeneration повертає окрему чернетку, не зберігає/перезаписує artifacts.

`MentorInputV1` містить sanitized educational facts, objective, rubric version,
precomputed result і Web status. `AssistantInputV1` — агрегат attempts/completed,
наявні mean/previous mean, scenario version, trusted sanitized facts та objectives.
`ExplanationSelectionV1` дозволяє LLM обирати лише ID наданих фактів і topics із
allowlist, зберігаючи роль моделі у визначенні доречності пояснень і рекомендацій.
Локальний composer повертає структуровані observation/explanation/defensive
behavior з trusted facts і рекомендації з контрольованого українського каталогу.
Довільний генеративний prose відхилено: regex не доводить відсутність вигаданих
оцінок, метрик чи психологічних висновків. Це свідомо консервативний Phase 5 API;
багатший перевірюваний prose потребуватиме окремого дизайну, а не послаблення gate.

Scoring/analytics не обчислюються: supplied facts копіюються без змін. Немає
result, incomplete, completed з 0 та correctly_skipped Web — різні стани.
За відсутності evidence додається явне обмеження. Рішення про нові сценарії,
складність та призначення залишаються викладачу; психологічних категорій немає.
Trusted facts мають бути вже перевірені й неідентифікуючі: модель не доводить
правдивість входу та не отримує прямого доступу до learner records.

## Groq та локальна валідація

Нові provider-facing схеми містять лише closed required objects, scalar types,
enum/const та arrays — перевіряються незміненим `groq_strict_schema`.
Жодних generic schema projections чи мовчазного видалення constraints.
Ліміти перевіряються явно Pydantic model validators: кожний text 1–4000 символів,
list до 24 елементів, slots JSON до 18000 символів; вужчі email/form правила
перевіряються додатково. Input/refinement і gateway prompt/output budgets також
обмежені. Це відокремлення wire schema від mandatory local semantic/bounds gate,
а не визнання неперевіреного provider output валідним. F-01/F-02 не змінено.
Unsafe content дає terminal SAFETY; invalid slots/structure — VALIDATION.

Selected NIST cues походять із `ScenarioParameters`; claimed — лише дозволені
`NistCueId` з існуючого каталогу; verified завжди порожні, статус
`requires_instructor_review`. Phase 5 не має достовірного semantic cue detector.
Немає invented NIST score/Cue Count/Difficulty. [NIST TN 2276](https://csrc.nist.gov/pubs/tn/2276/final)
визначає email phishing-detection difficulty, не learner performance чи Web score.

## Мінімальний LangGraph

За [офіційним overview](https://docs.langchain.com/oss/python/langgraph/overview)
та Context7 перевірено StateGraph, conditional edges, compile(checkpointer=False)
і invoke(recursion_limit). Залежність locked: LangGraph 1.2.21.

`START → generate → validate → END`; лише VALIDATION може повернутися до generate
за явно заданого `max_corrections=1` (default 0). Максимум 2 content generations,
recursion_limit=6. Gateway є єдиним transport retry/fallback/quota механізмом:
`SpecializedAgent → GatewayRunnable → LLMGateway → existing provider`.
Виправлення не повторює transport failures, quota, authorization або SAFETY.
Default gateway budgets можуть зупинити навіть дозволене виправлення; агент не
збільшує їх сам. Scripted demo задає великі ліміти лише для Mock, включно з
provider і model keys, не впливає на cloud configuration.

Кожен run має власний state і deep revalidation/copy inputs; graph не має
checkpointer/store, інструментів, filesystem чи network nodes. Повертається
`AgentResult`: pending_review/failed, schema/prompt versions, normalized error,
generation_count і metadata-only gateway telemetry. Draft виключений із default
serialization/repr; доступний як `.draft` для явної обробки caller.
Tracing вимкнено навколо всього run навіть за enabled process environment,
callbacks не приймаються. Raw payloads/errors не логуються.
`pending_review` чесно позначає необхідність погодження; pause/resume і approval
workflow не реалізовані. `publication_allowed=False` завжди.

## Інтеграція та межі

`agents/demo.py` і `tests/test_agents.py` використовують scripted MockLLMProvider,
реальний gateway і graph без .env/API keys/БД. Офлайн default лишається Mock.
Cloud selection — лише явно переданий existing configured gateway: Groq
`openai/gpt-oss-120b`, optional explicitly enabled verified Hydrogen backup;
інші approved model options лишаються чинними. Нових live calls не виконано.

Phase 6–7 інтегрують slots із UI/templates; Phase 8 — readiness/publication;
Phase 9 — події; Phase 10 — authoritative ScoringService/trusted feedback facts;
Phase 11 — sanitized aggregates та analytics UI. Жодна з цих фаз не почата.
Native Windows 11 verification відкладено до Phase 12 як ризик. Phase 5 не
змінює GUI, persistence, migration чи accepted RBAC/versioning services.

## F-01 — provenance попередніх чернеток (independent review remediation)

Перевірка лише resource ID (і Web template) не розрізняла сценарії/версії з
однаковим internal resource. `previous` тепер використовує повний EmailDraftV2
або WebDraftV2 з additive локальною `DraftProvenanceV1`. Її SHA-256 source digest
охоплює scenario ID/version, усі ScenarioParameters, ScenarioContextV1 та мову.
Web digest додатково охоплює template і associated Email envelope/slots,
крім request-specific context_token вкладеного Email.
Генератор створює provenance локально після валідації; LLM її не генерує.

`context_token()` залишається request-specific, включно з refinement. Stable
provenance не містить поточного refinement/previous: зміна лише інструкції
зберігає legitimate regeneration. Новий Email, навіть із тією самою scenario
provenance, робить попередній Web stale, якщо змінився його envelope/slots.
Зміна лише Email refinement/request token без зміни змісту не робить Web stale.
Попередні drafts перевіряються на вході до graph/LLM; canonical Email для Web
також перевіряється на expected identity/version/parameters/context/provenance.
Email envelope повторно звіряє власні metadata з provenance: просте relabeling
ID/version не переприв'язує чернетку. Web зберігає явну перевірку template.

Сумісність: provider-facing slots schemas, Groq strict conversion, prompt/schema
versions, canonical Phase 4 contracts і gateway незмінні. Старі draft envelopes
без provenance читаються (`provenance=None`), але не приймаються як regeneration
inputs або Email source для Web. Bare slots у legacy input union відхиляються
fail-closed: відсутні докази походження не можна безпечно відновити. Caller має
передавати `previous=result.draft`, а не `.draft.slots`; для legacy даних потрібна
нова генерація з trusted scenario input. Відомі ID і version обов'язкові для
reuse/Email→Web; standalone fresh Email може лишатися synthetic без identity.

Provenance — consistency fingerprint, не підпис, authorization або доказ
правдивості caller data. Trusted application service лишається межею RBAC;
нових repositories, checkpoint stores, migrations або permissions не додано.
