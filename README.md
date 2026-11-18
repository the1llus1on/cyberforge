# CyberForge

Локальний навчальний симулятор і конструктор сценаріїв соціальної інженерії
для магістерської дисертації. Цільова платформа — Windows 11;
нормативне джерело — [SRS v3.0](TECHNICAL_SPECIFICATION.md).

## Поточний стан

**Phases 0–11 — ACCEPTED. Phase 12 — NOT STARTED.**

Phase 0 та Phase 1 — ACCEPTED. Phase 2 — Users & Groups: **ACCEPTED власником
12.11.2026**. Phase 3 — Scenario Management: **ACCEPTED власником 12.11.2026**.
Реалізовано вхід/вихід, Argon2id, три ролі, зміну/скидання паролів,
керування користувачами й навчальними групами, M:N-членство та SQLite/Alembic.
Збережено українську темну оболонку й універсальну Головну Phase 1.

Рішення: [ADR-0001](docs/adr/0001-home-navigation.md),
[ADR-0002](docs/adr/0002-identity-groups.md),
[ADR-0003](docs/adr/0003-scenario-drafts.md).
У Конструкторі доступні створення, пошук і редагування власних сценаріїв,
постійні ID, SQLite persistence, чернеткові версії та зворотне архівування.
Аналіз використовує ті самі ID та показує дозволені історичні результати.
Email/Web Constructor підтримують явну AI-генерацію або позначене офлайн-демо; Web використовує ізольований Qt WebEngine.
Phase 9 learner flow — ACCEPTED власником 2026-11-17; Phase 10 scoring/Mentor — ACCEPTED власником 18.11.2026. Для офлайн-демо ключі та `.env` не потрібні.

## Встановлення й звичайний запуск

Потрібні Python 3.12 та [uv](https://docs.astral.sh/uv/getting-started/installation/).
Команди однакові у WSL і PowerShell:

```console
uv sync --locked
uv run cyberforge
```

Альтернатива: `uv run python -m cyberforge`. Початковий стан — Guest.
Звичайний запуск створює порожню схему, не створює користувачів або demo.
Спільний файл БД розміщується в каталозі даних CyberForge поточного профілю ОС
(`QStandardPaths.AppLocalDataLocation`). Для явного вибору файлу:

```console
uv run cyberforge --database .local/training.sqlite3
```

Для першого адміністратора у порожній БД виконайте в інтерактивному терміналі:

```console
uv run cyberforge --init-admin
```

Якщо обрано власний файл БД, додайте той самий `--database` до setup і запуску.
Команда запитує логін, пароль і підтвердження; пароль не відображається.
Повторне створення початкового адміністратора у непорожній БД заборонене.
Використовуйте синтетичні імена й облікові записи.

## Окрема демонстраційна база

```console
uv run cyberforge --init-demo --database .local/demo.sqlite3 --credentials-file .local/demo-credentials.json
uv run cyberforge --database .local/demo.sqlite3
```

Setup створить сім облікових записів SRS §2.6 і дві групи:

| Логін | Роль | Група |
|---|---|---|
| Administrator_demo | Адміністратор | глобальні права |
| teacher_demo_1 | Викладач | Група A |
| teacher_demo_2 | Викладач | Група B |
| learner_demo_1 | Учень | Група A |
| learner_demo_2 | Учень | Група A, Група B |
| learner_demo_3 | Учень | Група A, Група B |
| learner_demo_4 | Учень | Група B |

Кожен отримує окремий випадковий пароль. Відкрийте локальний файл
`.local/demo-credentials.json` у редакторі й візьміть пароль потрібного логіна.
Застосунок не друкує паролі й не записує їх у логи; `.local/` і файли
`*credentials*.json` виключені з Git. POSIX-права нового файлу — 0600.
У Windows зберігайте файл у приватному каталозі профілю. ACL окремого native
test demo перевірено; права інших Windows БД автоматично не змінюються.
Не копіюйте цей файл у PR, документацію або спільні каталоги.

Повторення тієї самої setup-команди не змінює існуючі demo-акаунти,
паролі або правки адміністратора. Непорожня стороння/часткова база
відхиляється; існуючий файл паролів не перезаписується.
Для незалежного нового набору вкажіть **два нові шляхи** БД та паролів.
Demo не додається до звичайної БД автоматично.

## Перевірка трьох ролей

1. Guest: доступні Головна, Профіль/Вхід і Налаштування; «+»/«Аналіз» приховані та заблоковані.
   Профіль відкриває форму входу на всю область вікна; «Закрити» повертає Home.
2. Увійдіть як `Administrator_demo`: Home, Конструктор, Аналіз і
   «Адміністрування» (іконка налаштувань у верхній групі лівої панелі).
   У вкладці «Користувачі» виберіть запис для зміни імені, логіна, ролі або
   стану; «Новий запис» очищає форму. Для створення задайте пароль.
   «Скинути пароль» використовує новий пароль із маскованого поля.
3. У вкладці «Навчальні групи» створіть або виберіть групу, змініть назву/опис
   і позначте викладачів та учнів. «Зберегти групу» атомарно зберігає
   назву, опис і склад, зокрема для нової групи. Один користувач може бути в декількох групах.
   Перезапустіть застосунок із тією самою БД: зміни збережуться.
4. Вийдіть через Профіль. Увійдіть як `teacher_demo_1`: Home, Конструктор,
   Аналіз; адміністративного доступу немає. Сервіс дозволяє читати лише
   закріплені групи; зміна складу та облікових записів заборонена.
5. Вийдіть і ввійдіть як `learner_demo_2`: Home, «Мої сценарії»,
   «Мої результати». Конструктор та адміністрування недоступні.
6. У Профілі змініть пароль, указавши поточний і новий (12–1024 символи).
   Після успіху потрібно ввійти повторно. Адміністративний reset, зміна ролі
   або деактивація також відкликають попередні сесії. Історія переходів і
   адміністративні списки не переносяться між входами.

Вимкнення облікового запису зберігає його дані, але забороняє вхід.
Зміна ролі прибирає попереднє членство у групах. Останнього активного
адміністратора вимкнути або перевести в іншу роль неможливо.

## Перевірки

```console
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run pytest tests/test_accounts.py tests/test_groups_database.py
uv run pytest tests/ui
uv run cyberforge --database .local/smoke.sqlite3 --smoke-test
uv build
```

Тести використовують тимчасові БД й масковані форми; за замовчуванням Qt
працює через `offscreen`. Після встановлення залежностей перевірки працюють
без мережі: `uv run --offline --locked pytest`. MockLLMProvider забезпечує
офлайн-перевірки; звичайні тести та GUI startup не викликають cloud API.
У Phase 6 хмарна генерація потребує явної конфігурації та дії викладача.
GitHub Actions виконує Ruff та pytest для PR і push у main на Linux та Windows.

WSLg Wayland:

```bash
QT_QPA_PLATFORM=wayland uv run cyberforge --database .local/demo.sqlite3
QT_QPA_PLATFORM=wayland uv run pytest tests/ui -q
```

Без дисплея використовуйте `QT_QPA_PLATFORM=offscreen`.
У цьому WSL XCB потребує відсутньої системної залежності `libxcb-cursor0`;
використовується Wayland. Підготовлено [ізольований native Windows 11 workspace](docs/diagnostics/native-windows.md)
з portable Python3.12, locked dependencies та подвійним кліком на
`Launch-CyberForge.cmd`. Автоматизований native startup не замінює фізичні
перевірки рамки, шрифтів, DPI100/125/150/200% і клавіатури.
Не задавайте `QT_QPA_PLATFORM=wayland` у Windows.

## Структура

- `domain/` — публічні значення й ролі; `identity/` — Argon2id і сесії.
- `application/accounts.py`, `groups/service.py` — транзакції й авторизація.
- `persistence/` — ORM, SQLite policy, пакетні міграції Alembic.
- `ui/` — збережена оболонка, форма входу/профілю, адміністративні форми.
- `tests/`, `.github/workflows/ci.yml` — перевірки.
- `docs/IMPLEMENTATION_PLAN.md`, `docs/DEVELOPMENT_LOG.md` — стан і докази.

БД і паролі захищаються також правами доступу ОС. Не публікуйте `.env`, БД,
локальні облікові дані або токени. Phase 4 потребує окремого погодження.

Нові каталоги БД на POSIX створюються з правами 0700, файли БД — 0600;
SQLite journal/WAL/SHM успадковують права БД. Права наявних файлів і каталогів
не змінюються: старі БД потребують окремої перевірки власником ОС.
Це не налаштовує Windows ACL автоматично. В окремому native test workspace
створено приватний profile demo-каталог і перевірено ACL; це не змінює прав
інших наявних Windows БД. Докладніше — у native Windows guide вище.

Пошук у списках користувачів, груп і учасників зберігає поточний вибір та
незбережені позначки учасників. «Новий запис» починає з ролі Учень.
«Видалити користувача» потребує підтвердження; поточного адміністратора
видалити не можна. За наявності історичних зв’язків використовуйте деактивацію.
[Діагностика української клавіатури у WSLg](docs/diagnostics/wslg-keyboard.md).

Вибір ролі — три взаємовиключні радіокнопки, початково Учень; запис у БД
виконується лише кнопкою збереження. Membership pickers не мають row-selection:
клік лише в індикатор або Space змінює checkbox; пошук зберігає чернетку.

Власник підтвердив фізичний ввід Standard Ukrainian; Enhanced не працює
через WSLg mapping. Для Ctrl shortcuts під Standard додано описану нижче
корекцію за фізичними доказами. Для baseline-порівняння
фізичних Ctrl+V/C/X/A та Shift+Insert запустіть `tools/keyboard_probe.py`
за інструкцією diagnostics. Надсилайте лише metadata-рядки — не текст,
clipboard або паролі. Виправленого офіційного релізу Enhanced не підтверджено.

Актуальне уточнення Phase 2: membership змінюється лише кліком у checkbox
або Space; клік на ім’я/порожню область нічого не змінює. Admin actions
розташовані поза прокручуваними формами. Preferred старт 1400×900, minimum
1100×720 на достатньому екрані; менші екрани обмежують ці значення й мають
scroll fallback. [Деталі геометрії](docs/diagnostics/window-sizing.md).

Після отримання фізичних key/scan доказів додано вузьку корекцію Ctrl+C/V/X/A
для Standard Ukrainian під WSLg Wayland. Вона не змінює системну розкладку,
English, Shift+Insert або Unicode typing; password copy/cut лишаються заборонені.
12.11.2026 власник підтвердив Standard typing/shortcuts фізично у WSLg.
Власник також підтвердив native Windows Enhanced input, shortcuts і minimum
window size та прийняв Phase2. Повну DPI-матрицю не заявлено; WSLg Enhanced
не виправлено. [Native launcher і межі перевірок](docs/diagnostics/native-windows.md).

Перед прийняттям Phase 2 проведено [технічний аудит](docs/audits/phase-2-pre-acceptance.md).
[Запис прийняття власником](docs/PHASE_2_ACCEPTANCE.md) відділяє owner evidence
від автоматизації та відомих environment limitations. CI має Linux і Windows Server2022 offscreen jobs;
успіх такого job не означає фізичну Windows11 acceptance. Перевіряйте фактичний
стан PR checks: queued не є success. Existing inactive memberships зберігаються
при редагуванні групи; нове призначення inactive account заборонено.

Перенаправлені повідомлення CLI (`stdout`/`stderr`) мають кодування UTF-8,
зокрема при запуску Python `-I` у Windows; читачі pipes мають декодувати UTF-8.

## Scenario Management — Phase 3

Instructor/Administrator: «+» → «+ Новий сценарій» → параметри → «Зберегти».
ID і назва `Сценарій {id}` виникають тільки після валідного Save. Картка має
основні та розширені поля; параметри зберігаються локально як чернетка.
Зміни чернетки підвищують ревізію; застарілий Save не перезаписує новіші дані.
Переходи/вибір іншого сценарію/New/закриття захищені Save/Discard/Cancel.

Instructor працює лише зі своїми сценаріями. Administrator бачить усі,
редагує й архівує власні; чужі картки й архів доступні для читання. Learner не бачить чернеток.
Конструктор і Аналіз мають один каталог та зберігають вибраний ID.
На етапі Phase 3 режим Аналізу показував стан відсутності результатів.
Email Constructor додано у Phase 6. Web, публікацію й обчислення
аналітики було заплановано на наступні фази.

Повна демонстрація й manual Windows gate:
[PHASE_3_ACCEPTANCE](docs/PHASE_3_ACCEPTANCE.md).

«Архівувати сценарій» потребує підтвердження та захищає незбережені правки.
«Архівні сценарії» фільтрує той самий каталог; «Відновити з архіву» повертає
можливість редагування. ID й content versions не змінюються, JSON snapshots
не видаляються. Міграція0003 додає metadata до наявних0001/0002 БД без reset.
Старий редактор після archive→restore має повторно відкрити актуальний стан.

Бажані ознаки листа обираються з перевіреного каталогу NIST TN2276 (2023)
за AppendixB IDs, а власні тактики вводяться окремо. Старі вільні рядки
показуються як некласифіковані для читання/копіювання й зберігаються без
автоматичного mapping. Desired selection не означає фактичної наявності
ознак; detection difficulty не обчислюється. Джерела/правила — ADR-0003.
«Скасувати зміни» запитує підтвердження відкидання й не виконує Save.


Phase3 прийнята після automated checks, незалежного review F01–F03 та часткового
owner manual WSLg verification; усі manual scenarios не заявляються виконаними.
Routine physical Windows11 verification Phases3–11 відкладено до Phase12 як
acknowledged risk; Windows CI не є native desktop acceptance. Phase4 —
LLM Integration: **ACCEPTED власником 13.11.2026** із прийнятими залишковими ризиками.
Деталі — план/журнал/acceptance record.

## Phase 4 — LLM Integration

Архітектуру погоджено власником у [ADR-0004](docs/adr/0004-llm-provider-boundary.md)
та SRS §10.2. Python integration layer `cyberforge.llm`:

`GatewayRunnable → LLMGateway → GeminiProvider / GroqProvider / MockLLMProvider`

Gemini: official google-genai 2.34.0, Interactions v1, stateless store=false,
без background/continuation. Groq: official SDK, strict JSON Schema з explicit
bounded compatibility check. Provider SDK типи не входять до domain/services/UI.
Канонічна structured validation — локальна Pydantic v2; це ще не предметна
перевірка навчального контенту або публікація артефакту.

Звичайний GUI startup не створює cloud clients, не викликає LLM і не потребує
API keys. `.env` не завантажується при імпорті або запуску GUI. `load_config()`
явно читає `.env` з поточної директорії; process environment має пріоритет
включно з порожніми значеннями. Interpolation `${...}` вимкнено. Існуючі
`GOOGLE_API_KEY`/`GROQ_API_KEY` зберігаються лише локально; налаштування без
секретів наведено в [`.env.example`](.env.example).

Без явної cloud-конфігурації — mock/mock-v1. Operational priority, погоджена
власником 13.11.2026, замінює попередню Gemini-primary preference:

| Роль | Provider / model | Thinking |
| --- | --- | --- |
| Primary cloud | groq / openai/gpt-oss-120b | low, medium, high |
| Preferred verified backup; explicit activation | gemini / gemini-4-hydrogen | low, medium, high, xhigh |
| Optional lightweight, explicit selection | gemini / gemini-3.5-flash-lite | minimal, low, medium, high |
| Earlier approved, unresolved access | gemini / gemini-3.8-flash | low, medium, high |

Hydrogen використовує той самий Interactions v1 adapter; temperature/top_p/top_k
не передаються. max_output_tokens/timeout залишаються bounded; automatic
continuation/background вимкнені. Existing Gemini3 request formats збережено.

### Явна primary/backup конфігурація

Додайте лише несекретні поля до свого existing .env, не перезаписуючи ключів:

```dotenv
CYBERFORGE_LLM_PROVIDER=groq
CYBERFORGE_LLM_MODEL=openai/gpt-oss-120b
CYBERFORGE_LLM_FALLBACK=false
CYBERFORGE_LLM_BACKUP={"provider":"gemini","model":"gemini-4-hydrogen","enabled":false,"access_verified":false}
```

`configured_request(config, ...)` застосовує ці primary defaults; direct
GenerationRequest має власний явний вибір. Backup застосовується лише для
запиту, що відповідає configured primary, і лише після owner-verified access
та explicit enabled=true. Після успішного owner live test для поточного ключа
можна вручну встановити обидва flags true; підтвердження не робиться автоматично.
Можна зберегти access_verified=true із enabled=false, щоб fallback лишався off.
Invalid/unapproved target, enabled без verification, однаковий primary/backup
або cloud fallback із configured mock primary відхиляються.

Один fallback hop, без циклів і AUTO. Дозволені лише classified timeout/selected
5xx після bounded retries; 429, quota/budget, refusals, auth, missing keys,
configuration/schema/validation та permanent failures fallback не запускають.
Mock requests ніколи не перенаправляються у cloud. Provider/model budgets
незалежні; Retry-After cooldown діє між requests/models. Budgets in-memory,
не замінюють account quotas і не зберігаються після restart.

`CYBERFORGE_LLM_FALLBACK=true` збережено як **deprecated** Gemini→Groq path із
попередньою поведінкою. Це той самий execution/retry loop. Для нового BACKUP
legacy flag має бути false/unset; одночасне налаштування відхиляється, а не
мовчки змінює маршрут. Сумісні thinking levels/None зберігаються; unsupported
minimal→low і xhigh→high mappings явні. На Hydrogen effective temperature=None
означає omission; original requested parameters не змінюються. Telemetry містить
requested_provider/model/parameters, effective provider/model/parameters та
actual_model (або None, якщо відповідь його не надала). При переході до Gemini
Groq artifact schema projection не переноситься: діє original full schema.

GatewayRunnable підтримує invoke/ainvoke, batch/abatch і stream/astream
одного повного результату; token streaming не передбачено. Retry/quota/fallback
існують лише в gateway. Tracing/callbacks на цьому boundary вимкнено; майбутні
outer workflows теж не повинні trace prompts/results. Для observability є
metadata-only TelemetrySink; prompts/responses за замовчуванням не зберігаються.

### Hydrogen connectivity — SUCCESS підтверджено власником 13.11.2026

Попередня bounded live перевірка на reviewed32e6de1 підтвердила доступ до
Groq GPT-OSS120B та Gemini3.5FlashLite. Gemini3.8Flash повернув unavailable;
власник повідомив про два такі результати. Це не доводить access/quota restriction.
Попереднє Hydrogen повідомлення про allowlist було локальним rejection, без
Google API request. Published availability не підтверджує доступ конкретного
ключа. Власник повідомив Hydrogen **success**:5.148s, input39/output5/reasoning25.
Це owner-run evidence; агент не повторює live calls. Live complex Email/Web
Structured Outputs/account-wide quotas не перевірені; counters process-local.
Manual GUI checklist неповний; physical native Windows11 gate — Phase12.
Ризики прийняті власником і не блокують Phase4 acceptance.

Власник уже виконав цей synthetic connectivity command (не повторювати автоматично):

```console
uv run cyberforge-llm-check --live --provider gemini --model gemini-4-hydrogen
```

Explicit --live обов'язковий. Ця команда має low thinking, 256 output tokens,
timeout20s; max_retries=0, обидва fallback config paths off, store/background/
continuation off. Виводить лише provider/model/outcome/elapsed/available usage,
без key/prompt/response. Incomplete output є normalized validation failure;
малі token caps можуть обмежити thinking, команда ніколи не продовжує generation.
Не змінюйте flags verification/enabled на true до успішного результату для
поточного ключа. При failures не повторюйте API usage автоматично.

Інші approved models можна перевірити тим самим CLI лише за окремого дозволу
на відповідні виклики. GUI startup/pytest/CI live diagnostics не запускають.

[Phase4 acceptance](docs/PHASE_4_ACCEPTANCE.md) містить offline перевірку
контрактів і короткі WSLg кроки. Нового graphical model selector немає;
Agents/LangGraph workflows додано у Phase 5, Email UI — у Phase 6; Web UI
залишається Phase 7.


### Phase 5: спеціалізовані агенти (офлайн)

```bash
uv run --locked python -m cyberforge.agents.demo
```

Демонстрація чотирьох агентів використовує scripted `MockLLMProvider`, реальні
`LLMGateway`/`GatewayRunnable` і LangGraph, синтетичні fixtures; не читає `.env`,
не викликає cloud API і не працює з БД. Усі результати — `pending_review`.

Python API: `cyberforge.agents` експортує `EmailScenarioAgent`, `WebScenarioAgent`,
`MentorAgent`, `AssistantAgent`. Передайте existing gateway у constructor і
відповідний `*InputV1` із `cyberforge.agents.contracts` у `.run(input)`.
`result.status`, `.error`, `.telemetry` — metadata; лише за `pending_review`
використовуйте `.draft` (виключено з default serialization). Нічого автоматично
не зберігається й не публікується. Див. повний executable приклад у
`src/cyberforge/agents/demo.py` та [ADR-0005](docs/adr/0005-specialized-agent-drafts.md).

Inputs мають походити з авторизованих application services і бути синтетичними;
scenario ID не надає агенту прав доступу. Mentor/Assistant обирають supplied facts
і контрольовані рекомендації, не генерують нові score/analytics assertions.
Selected/claimed NIST cues не є verified. Semantic review викладачем обов'язковий.
Default `max_corrections=0`; явне `1` дозволяє максимум одне content correction
лише після validation failure та в межах чинних gateway budgets. Transport
retry/fallback і model selection залишаються політикою Phase 4; demo не змінює
cloud configuration. Нових live API-викликів для Phase 5 не дозволено.

### Phase 6: Email Constructor (ACCEPTED — 2026-11-15)

Прийнято власником після GUI generation/regeneration і live Groq перевірки.
Scope, докази та Phase12 deferrals — [PHASE_6_ACCEPTANCE](docs/PHASE_6_ACCEPTANCE.md).
Phase7 окремо дозволено15.11.2026; поточний стан і перевірки наведено нижче.

Open a saved scenario → «Створити електронний лист». The native Qt preview now
resembles a Gmail mailbox inside a browser frame, with a light mail area inside
the dark CyberForge shell. Search the generated inbox, click a message (or press
Enter) to open it, and use the mailbox back button to return. Addresses and
timestamps are synthetic; browser controls and sending actions do not navigate
or send mail. No browser engine or external web content is used.

The reading view uses a 22px subject, 15px paragraph text and a native formatted
content template. The main message's sender supplies its synthetic header;
its existing internal resource ID appears in an inert information/action card.
Model strings remain literal text. Wide inbox rows align sender, subject,
snippet and time; compact rows wrap their overview. Icons are painted locally.

«Уточнення викладача для перегенерації» supplies an instruction for the next
generation. It does not edit the current preview or saved email directly:
«Перегенерувати» creates an unsaved candidate; «Зберегти» explicitly persists it
and returns to the scenario card. Reopening restores the stored artifact.

«Редагувати лист» opens native sender/name/address/subject/body fields for the
selected main or background message. Apply changes only the validated working
draft; Cancel discards dialog edits. Only «Зберегти» writes SQLite. Sender edits
rebind the synthetic context/provenance through the authorized service.

«Переглянути код» inspects the current canonical JSON, including unsaved edits,
with read-only highlighting, scrolling and Copy. The unused HTML projection
has been removed; developer-controlled native visual formatting remains.

Refinement uses the latest working draft. Select «AI: лише текст основного листа»
to deterministically preserve subject, senders, background mail and other fields;
«AI: весь лист і фон» permits broader changes. Scope takes precedence over
conflicting prose. Regeneration after manual edits requires confirmation and
never saves automatically. Failure preserves the current candidate.

Email prompts use email-prompt-v3. Provider output limits are optional: omit
max_output_tokens (or set null) in CYBERFORGE_LLM_PARAMETERS to leave provider
defaults in force. An explicit positive value has no application maximum.
CYBERFORGE_EMAIL_MAX_OUTPUT_TOKENS is an optional Email-specific override;
when absent, Email inherits an explicit shared setting. If both are unset,
Groq Email with openai/gpt-oss-120b sends4096 for initial and refinement requests
(owner-verified compatibility default). Gemini and other operations retain
optional limits. Provider context/output/account limits still apply.

Local rate/token quotas are opt-in through CYBERFORGE_LLM_LIMITS. Unspecified
provider/model keys and dimensions have no local cap. Both explicitly configured
levels still apply; Retry-After cooldowns, timeouts and bounded retries remain.
Token reservations estimate UTF8 prompt+schema bytes plus an explicitly configured
output allowance. With no output limit, unknown completion tokens cannot be
reserved; these estimates are not billing/account limits. Content field/artifact
bounds and local validation remain mandatory. Arbitrary generation_parameters
remain unsupported for cloud prompting.

Owner-only live acceptance (up to two paid requests, no retries/fallback):

```console
uv run --offline --locked python -m cyberforge.agents.email_live_check --live
```

This reads GROQ_API_KEY and the optional Email limit, leaves .env unchanged,
and uses synthetic data. It stops after an initial failure and emits only safe
contract/usage/timing metadata. Do not run it during baseline tests or CI.
Owner follow-up found HTTP400 when omitting the output limit; explicit4096
passed initial/refinement validation and protected-field checks. Metadata includes
safe HTTP status, allowlisted error type/code and context/output/schema category.
The runner defaults to4096 output tokens, with no local token quota.
CYBERFORGE_EMAIL_MAX_OUTPUT_TOKENS overrides the default; --max-output-tokens N
takes precedence. Values8192 and higher remain supported without an app ceiling.
It still makes at most two requests with no retries, corrections or fallback.
No live calls were made by Codex.

Existing RBAC, archive/published restrictions, worker identity guards, provenance
and SQLite behavior remain in force. Configured cloud generation requires an
explicit instructor action; startup/navigation do not call a model. Without
cloud configuration generation is unavailable. `--email-demo` explicitly selects
the synthetic offline Mock demonstration and ignores `.env`/cloud keys.

Safe isolated setup/launch commands and the updated owner review checklist:
[PHASE_6_ACCEPTANCE](docs/PHASE_6_ACCEPTANCE.md). Phase 7 remains out of scope.


Owner-approved address rule (14.11.2026): ordinary email domains and legacy
`.invalid` addresses are accepted as inert display data. Minimal ASCII syntax
validation bounds the local part to64 and total address to254 characters,
requires a dotted domain with labels up to63 characters and rejects whitespace,
controls and header injection. No DNS/MX/mailbox checks or delivery. Use fictional
identities only; never include real personal data in cloud prompts. External URL
restrictions remain unchanged. Email prompt is now email-prompt-v3.

Owner live follow-up: omitted Groq max_completion_tokens returned HTTP400;
explicit4096 passed initial/refinement validation (889/780output tokens), with
protected fields preserved. This is owner evidence; Codex made no live calls.

## Phase 7 — компонентний Web Constructor

Web працює з тим самим збереженим Scenario/Email: один renderer дев'яти
компонентів, автоматична композиція й чотири presets, три теми, visual editor,
AI refinement у трьох межах, read-only HTML/CSS/JSON та explicit SQLite Save.
WebEngine ізольований: display-only HTTPS адреса не завантажується, JS/зовнішня
мережа/довільні файли/popups/downloads заборонені. Зміна saved Email робить Web stale
без видалення матеріалу. Публікація реалізована в Phase8 нижче; learner simulation — Phase9.

Явне offline demo: `uv run --offline --locked cyberforge --database /path/to/demo.sqlite3 --web-demo`.
Прапорець потребує явно обраної БД, ігнорує .env/keys, не викликає cloud API та не
видає synthetic fixtures за AI. Ізольоване створення БД, owner checklist, screenshots
та minimal owner-only live workflow: [PHASE_7_ACCEPTANCE.md](docs/PHASE_7_ACCEPTANCE.md).
Web Groq output default4096; `CYBERFORGE_WEB_MAX_OUTPUT_TOKENS` overrides shared/default,
explicit positive limits без hard application maximum. Phase7 **ACCEPTED власником
2026-11-15**; PR8 merge дозволено після final-head CI. Owner підтвердив live Groq
generation/regeneration, ручне редагування шапки, light/dark та preview/rendering.
Save/reopen і всі presets мають automated evidence, не окреме owner confirmation.
Physical Windows11/DPI/installer та інші Phase12 checks залишаються ризиками.
Історичний Phase7 acceptance завершено; Phase8 реалізується за окремим дозволом нижче.


## Phase 8 — інтеграція та публікація

Сценарій має явний main Email→Web link, версійовану рубрику, детерміновану
перевірку готовності та підтвердження точних ревізій викладачем. Публікація атомарно
заморожує canonical content і manifest; доступ груп керується окремими grants
з append-only audit. Нова версія копіює лише parameters, зберігаючи стару публікацію.
У Конструкторі відкрийте «Підготовка сценарію»: матеріали → оцінювання →
публікація. «Опубліковані версії» окремо відкриває history/access навіть із нової чернетки.

Підтримується safe-decline applicability; спроби/learner simulation додає
Phase9 нижче, числові оцінки — Phase10. Phase8 не потребує AI calls; `--web-demo` дозволяє всю synthetic
демонстрацію офлайн в окремій БД. Owner checklist, міграція, security evidence та
limitations: [PHASE_8_ACCEPTANCE.md](docs/PHASE_8_ACCEPTANCE.md).
Phase8 — **ACCEPTED власником 2026-11-17** після ручної WSLg перевірки.
Implementation CI: Linux1014PASS, Windows Server2022 1011PASS/3POSIX skips;
Ruff/GUI/security gates PASS. PR9 merged у main `dfba3fbaa1b2b8b94d279d3cef3f132c03cc9391`;
release evidence — PHASE_8_ACCEPTANCE.md та PR9.
Phases0–9 ACCEPTED; Phase9 прийнято власником 2026-11-17.
На момент прийняття Phase 10 (18.11.2026) Phases 11–12 мали стан NOT STARTED.
Physical Windows11, DPI, GPU-specific behavior та installer — Phase12 risks.

## Phase 9 — ізольоване офлайн-демо проходження

Phases0–9 ACCEPTED; Phase9 прийнято власником 2026-11-17 після independent
review/remediation та п’яти manual WSLg scenarios. Phase10 scoring/Mentor
реалізовано нижче для independent review; analytics залишається Phase11.
Архітектура: [ADR-0010](docs/adr/0010-deterministic-scoring-mentor.md),
accepted WP1 та окремий owner authorization WP2–WP8 від17.11.2026.
Нова additive migration0007, durable attempts та immutable events.
Demo setup потребує **нового** файлу БД; наявні demo/owner БД не перезаписуються.

```bash
demo_dir=$(mktemp -d /tmp/cyberforge-phase9.XXXXXX)
uv run cyberforge --init-demo --learner-demo --database "$demo_dir/demo.sqlite3" --credentials-file "$demo_dir/demo-credentials.json"
uv run cyberforge --learner-demo --database "$demo_dir/demo.sqlite3"
```

Відкрийте приватний JSON у локальному редакторі. `teacher_demo_1` має готову
публікацію для Групи A; `learner_demo_1` має доступ. «Мої сценарії» → вступ →
Start → main Email → inspection/report → decline/confirmation або internal CTA
→ isolated Web → actions → explicit completion. «Мої результати» містить реальну
history та pending evaluation. Phase10 додає score/detail/Mentor. Restart із тією самою БД відновлює unfinished
attempt. Повний checklist: [Phase 9 acceptance](docs/PHASE_9_ACCEPTANCE.md).
`--learner-demo` явно використовує offline Mock/demo services без `.env`/cloud keys.


## Phase 10 — особисті результати та навчальне пояснення

**ACCEPTED** 18.11.2026.
Existing `--learner-demo` вище запускає повністю offline workflow. Після завершення
відкрийте «Мої результати», виберіть own attempt та «Обчислити оцінку».
Система фіксує immutable deterministic result; feedback готується у background.
«Отримати пояснення» повторює лише відсутній feedback; «Оновити результати»
перевіряє persisted state. Restart із тією самою DB зберігає score та explanation.

Справжній0.00%, pending, incomplete/abandoned, historical UNSCORABLE та integrity
error відрізняються. Web без visit не отримує fabricated zero; non-applicable
criterion не входить до arithmetic. Critical confirm/form actions — factual
observations, policy NOT_CONFIGURED, без penalties/pass-fail claims.
Нові publications потребують numerical criterion на кожному completion path.
Історичні accepted rubrics/publications не переписуються.

Additive migration `0008_evaluations` виконується normal startup в existing SQLite;
backfill/rescoring немає. Оцінка й усі details commit атомарно, feedback окремо.
При integrity error результат не повертається й не repair/rescore автоматично;
збережіть DB для controlled investigation. Не видаляйте history для повторного
оцінювання. Learner history доступна owner після revoke/archive, restricted
scenario content — ні. Logout очищує results та stale worker responses.

Normal startup cloud Mentor використовує лише explicit existing gateway config;
без нього deterministic Ukrainian feedback. `--learner-demo` завжди offline.
Provider бачить лише trusted synthetic educational facts та sanitized precomputed
summary; score не визначається моделлю. Аналітика та експорт належать до Phase 11.
Traceability, exact verification та manual checklist:
[Phase10 implementation review](docs/PHASE_10_IMPLEMENTATION_REVIEW.md).
Native Windows11/DPI/GPU/installer acceptance — Phase12 deferral, не verified claim.


## Phase 11 — Аналіз

Архітектура — **APPROVED**, реалізація — **ACCEPTED / MERGED**.
Власник прийняв фазу 18.11.2026 після повідомлення про виконання ручної
перевірки WSLg. [PR #16](https://github.com/the1llus1on/cyberforge/pull/16)
було злито раніше за окремим дозволом для подання програми.

«Аналіз» показує дозволені історичні результати викладачу й адміністратору.
Доступні режими останньої та всіх завершених спроб, показники якості
даних, три графіки, таблиця учнів, історія спроб, фільтри, пошук,
сортування, пагінація, CSV/JSON та офлайн-рекомендації.
[Запис прийняття і докази](docs/PHASE_11_IMPLEMENTATION_REVIEW.md).

F11-ADR-01 залишається відкритим. Хмарні рекомендації вимкнено.
Phase 12 — **NOT STARTED**. У цій фазі заплановані перевірки фізичного
Windows 11, DPI, апаратного GPU, фінального виконуваного файла та інсталятора.
