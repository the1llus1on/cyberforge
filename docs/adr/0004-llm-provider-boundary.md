# ADR-0004: межа LLM-провайдерів та Interactions API

Дата: 13.11.2026. Статус: **ACCEPTED власником — архітектура Phase 4**.

## Контекст і перевірена база

Phase 4 явно дозволено власником. Чистий main синхронізовано через fetch і
fast-forward check; baseline d0b407cbb13cf9e10f5bd65904eef978c321ab7e
містить merge PR #4. GitHub MCP підтвердив commit. Робоча гілка:
`feat/phase-4-llm-integration`. Власник окремо погодив narrow amendment SRS §10.2; інші секції SRS збережено.

SRS §§10.1–10.4 вимагають власний gateway, LangChain і провайдерні адаптери;
§10.2 прямо називає `langchain-google-genai` для Gemini. Власник додатково
затвердив Gemini Interactions, Groq та stateless `store=false`.

## Перевірка офіційних джерел

- [Interactions](https://aistudio.google.com/docs/interactions-overview): GA,
  рекомендований для нових інтеграцій; generateContent підтримується як legacy.
  `store=false` несумісний із background; наступні turns не можуть використовувати
  `previous_interaction_id`. Stateless не є гарантією всіх аспектів data handling
  Free Tier: умови провайдера залишаються чинними; лише синтетичні дані.
- [Thinking](https://aistudio.google.com/docs/thinking): 3.8 Flash підтримує
  low/medium/high; 3.5 Flash-Lite — minimal/low/medium/high.
- [Structured outputs](https://aistudio.google.com/docs/structured-output):
  JSON Schema/Pydantic не замінюють локальну та предметну перевірку.
- [LangChain integration](https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai)
  використовує google-genai. Однак [реалізація ChatGoogleGenerativeAI](https://github.com/langchain-ai/langchain-google/blob/main/libs/genai/langchain_google_genai/chat_models.py)
  викликає `client.models.generate_content`, а не Interactions. Спільний SDK
  не означає підтримки однакових API.
- [Groq Structured Outputs](https://console.groq.com/docs/structured-outputs):
  GPT-OSS 120B підтримує strict JSON Schema; усі properties required,
  `additionalProperties=false`.
- [Groq limits](https://console.groq.com/docs/rate-limits): довідкові Free Plan
  30 RPM / 1000 RPD / 8000 TPM / 200000 TPD підтверджено. Це не перевірені
  квоти ключа власника; dashboard/account responses ще не перевірено.
- Context7 відповів на запити google-genai та Groq. Встановлені офіційні SDK:
  google-genai 2.34.0, groq 1.7.0; langchain-core 1.8.0, python-dotenv 1.2.4.
  Локальна інспекція SDK без мережі підтвердила наявність Interactions і
  `automatic_continuation=False`; continuation за замовчуванням може виконати
  кілька HTTP-запитів. У майбутньому адаптері його потрібно вимкнути, а SDK
  retries вимкнути на користь єдиного бюджету gateway.

## Рішення власника і альтернативи

Власник явно погодив GeminiProvider → official google-genai → Interactions,
із provider-neutral LangChain Runnable над LLMGateway. Точний наданий власником
текст внесено лише до SRS §10.2. LangGraph orchestration лишається Phase 5.
Погодження архітектури не є прийняттям реалізації Phase 4.

Відхилено legacy generateContent adapter лише заради старого формулювання,
паралельні Gemini implementations та другий retry/fallback layer. Збереження
лише langchain-google-genai не забезпечує погодженої поведінки Interactions.
Runnable over gateway зберігає LangChain composition й майбутню LangGraph
сумісність без витоку SDK типів у services/UI/domain.

Раніше запропоновані правки таблиці технологій та §10.5 НЕ застосовано:
власник дозволив змінити тільки §10.2. Нормативне уточнення §10.2 визначає
актуальну поведінку адаптера; перелік дозволених provider/models з додаткового
завдання власника відображено в конфігурації й цьому ADR.

## Реалізація

`llm/contracts.py`: Pydantic v2 request/result/configuration metadata, normalized
errors, versioned context/Email/Web content slots. Текстові slots не є
HTML/rendering contracts. Gateway не має залежностей від БД, RBAC чи scoring.
`synthetic=True` — явне зобов'язання caller, не автоматичний детектор PII.
Предметна валідація, Email/Web consistency та instructor approval — наступні фази.

`config.py`: завантаження лише явного `.env` (поточна директорія за замовчуванням),
без interpolation і без зміни os.environ. Process environment має пріоритет,
включно з порожніми значеннями. SecretStr excluded from exports/repr.
Без конфігурації — mock; відкриття застосунку не завантажує ключі чи SDK.

`gateway.py`: explicit selection, timeout contract, capped exponential backoff
із jitter, Retry-After, до 3 retries на провайдера; optional одноразовий перехід
Gemini → Groq лише після timeout/500/502/503/504, ніколи після 429.
Невідомі transport failures консервативно не повторюються. AUTO не додається.
Gateway синхронний; майбутній UI повинен запускати генерацію у worker.

`limits.py`: rolling minute/day, aggregate provider та model budgets, atomic
reservation. Input UTF-8 bytes + serialized schema UTF-8 bytes + max output tokens —
консервативний локальний резерв,
не виміряний usage; failed attempts також рахуються. Ліміти лише in-memory для
одного gateway/process, не account-wide billing controls. Restart не зберігає
бюджети; durable accounting відкладено. Default локальні caps навмисно нижчі
за довідкові Free Plan. Provider quotas завжди мають пріоритет.

`groq_provider.py`: офіційний SDK, fixed official endpoint, retries=0,
lazy client initialization, strict schema і normalized errors без SDK payload.
`schemas.py`: bounded inline acyclic refs, enum/const, closed required objects,
arrays і scalar types. Titles/descriptions вилучаються; const → singleton enum.
Optional/default fields, unions, recursive refs, довільні patterns/formats та
інші непідтримувані constraints відхиляються до запиту. Для канонічних
EmailArtifactV1/WebArtifactV1 є лише один explicit local-only виняток, описаний
нижче у F-02; він не змінює Pydantic/domain validation. Фактичні agents,
constructors і publication workflows залишаються наступними фазами.
Локальна Pydantic strict validation завжди обов'язкова для structured generation.

Telemetry містить лише затверджені metadata; відсутній provider usage лишається
None. Повні prompts/responses виключено з serialization за замовчуванням.
TelemetrySink — best-effort extension point, durable storage/analytics відкладено.
Mock повертає reproducible fixtures і scripted errors без API keys/network.

## Gemini і LangChain

Gemini використовує Interactions v1, text та JSON response_format із Pydantic
JSON Schema; store/background/stream=False, automatic_continuation=False.
Thinking перевіряється per-model; думки/signatures/continuation IDs не
передаються до public result. Usage/actual model лишаються None за відсутності
даних. Incomplete output не вважається success. Обидва SDK закривають clients.

У google-genai 2.34.0 виявлено несумісну семантику retries: parent client
перетворює attempts=0 на 1, NextGen Interactions трактує 1 як retry count.
Тому parent налаштовано на attempts=1, а на generated Interactions resource
явно встановлюється sdk_configuration.retry_config.strategy="none".
Це вузький SDK compatibility point; версію зафіксовано ==2.34.0. Відсутність
цього config завершується configuration error до мережі. Real SDK/fake HTTP
тести доводять рівно один transport call на 429/5xx/timeout та відсутність
continuation. Upgrade потребує повтору цих тестів. Підстава — офіційний
[SDK source](https://github.com/googleapis/python-genai), функції retry_args і
_translate_retry_config; це локальне налаштування SDK, без іншого API path.

GatewayRunnable реалізує invoke; LangChain Core забезпечує ainvoke (worker
executor), batch/abatch та stream/astream одного повного GenerationResult.
Token streaming не реалізовано. Structured type задається при створенні Runnable.
Немає callback emission/_call_with_config; tracing_context(enabled=False)
блокує tracing усередині boundary, config callbacks/metadata не пересилаються.
Pydantic exports/repr і LangChain dumpd не містять prompt/result content.
Зовнішні майбутні workflows також повинні виконуватися без content tracing:
цей adapter не може змінювати політики сторонніх outer nodes. SDK keys ніколи
не входять до invocation contract. Єдиний дозволений observability hook —
metadata-only TelemetrySink. Стандартний batch має обмежувати max_concurrency;
atomic gateway budgets діють і для паралельних викликів.

Rate-limit Retry-After створює cooldown для всього provider, зокрема інших
моделей. Значення понад max_backoff не скорочується: поточний виклик завершується
rate_limit, наступні блокуються до кінця cooldown. Fallback для цього заборонено.
Quota configuration typos fail closed. Requested model для invalid configuration
редагується до safe marker у telemetry, не експортується як довільний рядок.

## Діагностика й відкладене

cyberforge-llm-check вимагає --live та explicit provider/model. Одна коротка
synthetic text request, max_output_tokens=256, timeout=20s, max_retries=0,
fallback=False; SDK retries/continuation вимкнено. Виводить тільки provider,
model, outcome, elapsed, available usage. Аргументи --help або відсутність
--live не читають .env і не створюють clients. Жодного live request не виконано:
поточне рішення власника вимагає окремого дозволу на таке виконання.
Account model access/quotas лишаються неперевіреними; це не offline failure.

AUTO, agents/orchestration, UI generation, artifact publication/approval,
durable telemetry/quota persistence і comparative experiments відкладено.
Змінена лише SRS §10.2, жодної міграції чи зміни RBAC/scenarios/scoring немає.
Phase 4 передається на REVIEW після checks, не ACCEPTED; merge заборонено.
Native Windows 11 physical acceptance — Phase 12, не Windows CI evidence.

## Перевірка privacy під DEBUG

Відомі SDK payload/exception loggers фільтруються context-local filter лише
під час provider.generate, включно з initialization/close. Звичайні application
logs інших threads не вимикаються. Це запобігає витоку payload навіть за
root DEBUG або GOOGLE_GENAI_DEBUG; тести використовують тільки synthetic keys
і fake HTTP. У runtime не вмикається full prompt/response logging.


## 13.11.2026 — independent review F-01/F-02 remediation

Обидва findings відтворено на reviewed HEAD5913183: Flash-Lite minimal після
transient failure завершувався configuration error; raw strict checker
відхиляв обидві versioned artifact schemas через context internal_resource_id.
Scope — SRS §§10.4–10.8/11.1, без нових вимог або змін SRS/архітектури.

### F-01: deterministic fallback parameters

Для вже дозволеного Gemini→Groq fallback застосовується фіксована політика:

| Requested thinking | Effective Groq thinking |
| --- | --- |
| minimal (лише Gemini3.5FlashLite) | low |
| low / medium / high | те саме значення |
| None | None; provider default лишається explicit unknown choice |

Це вибір найнижчого дозволеного Groq reasoning_effort, не твердження про
однакову поведінку моделей. [Офіційний SDK контракт](https://github.com/groq/groq-python/blob/main/src/groq/types/chat/completion_create_params.py)
підтверджує GPT-OSS low/medium/high, без minimal. Context7 підтвердив той самий
контракт. Інші generation parameters зберігаються. Original request/parameters
не змінюються: створюються нові frozen objects лише для effective fallback.
Telemetry тепер містить requested_parameters та effective_parameters разом
з наявними requested_model/actual_model/version metadata. Prompts/responses
не додаються до telemetry. None не підміняється вигаданим reasoning level.

Mapping виконується тільки після allowlisted temporary failure, за enabled
fallback. Він не виправляє invalid original configuration і не дозволяє
fallback для safety/authorization/credentials/schema/validation/rate-limit/
quota/permanent failures. Залишаються попередні retries/budgets/cooldowns.

### F-02: bounded artifact wire schema з незміненою локальною перевіркою

Actual Pydantic JSON Schema обох V1 contracts містить у
$defs.ScenarioContextV1.properties.internal_resource_id:

```json
{"pattern":"^[a-zA-Z0-9_-]{1,64}$","title":"Internal Resource Id","type":"string"}
```

За попередньою політикою groq_strict_schema відхиляє pattern. Рішення:
groq_output_schema працює у gateway, де є canonical Pydantic output_type і
обов'язковий validator. Тільки для точних EmailArtifactV1/WebArtifactV1
він копіює JSON Schema, перевіряє точний expected regex у зазначеному полі
і делегує лише цей regex локальній валідації. Wire field стає type=string.
Подальший strict checker не змінюється; const→enum, closed required objects,
scalar/array types та інші підтримувані constraints зберігаються. Новий або
змінений regex/інший pattern не видаляється автоматично: unsupported_schema.
Raw GroqProvider сам не застосовує lossy projection, бо не має Pydantic type.

| Перевірка | Provider-facing strict schema | Локальна canonical Pydantic |
| --- | --- | --- |
| Required fields, closed objects, types, version enum | Так | Завжди повторно |
| context.internal_resource_id ASCII letters/digits/_/-, length1–64 | Ні, лише type=string | Завжди повний original regex |
| Інші непідтримувані patterns/constraints | Reject до HTTP | Не обходяться |

Telemetry.schema_projection=groq-artifact-v1-local-resource-id позначає
застосований виняток, включно з validation failures. На Gemini schema
залишається повною, без проєкції. Повернення structured result можливе лише
після original output_type.model_validate_json(...,strict=True); provider
compliance не є достатнім security gate. Invalid ID не повертається як
артефакт, не повторюється і не запускає додатковий fallback.

Alternatives: зняття canonical pattern відхилено (послаблює local rule);
загальне видалення patterns відхилено (silent weakening); повна окрема wire
model hierarchy не потрібна для одного відомого поля. Обраний виняток явно
дозволений remediation scope власника і зберігає effective validation rule,
тому нового архітектурного погодження не потребує. Самі канонічні контракти,
SDK adapters, dependencies і public gateway call signature не змінено.

[Groq Strict Outputs](https://console.groq.com/docs/structured-outputs)
визначає provider-level guarantee для переданої схеми; це не доводить
безпечність навчального змісту. Synthetic data/domain consistency та instructor
approval лишаються окремими наступними gates; агенти/конструктори не реалізовано.
Live verification не виконувалася. Докази: tests/test_llm_review.py, журнал,
final PR checks. Phase4 лишається REVIEW, без merge або Phase5.
