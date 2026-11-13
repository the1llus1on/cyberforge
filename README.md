# CyberForge

Локальний навчальний симулятор і конструктор сценаріїв соціальної інженерії
для магістерської дисертації. Цільова платформа — Windows 11;
нормативне джерело — [SRS v3.0](TECHNICAL_SPECIFICATION.md).

## Поточний стан

Phase 0 та Phase 1 — ACCEPTED. Phase 2 — Users & Groups: **ACCEPTED власником
12.11.2026**. Phase 3 — Scenario Management: **ACCEPTED власником 12.11.2026**.
Реалізовано вхід/вихід, Argon2id, три ролі, зміну/скидання паролів,
керування користувачами й навчальними групами, M:N-членство та SQLite/Alembic.
Збережено українську темну оболонку й універсальну Головну Phase 1.

Рішення: [ADR-0001](docs/adr/0001-home-navigation.md),
[ADR-0002](docs/adr/0002-identity-groups.md),
[ADR-0003](docs/adr/0003-scenario-drafts.md).
У Конструкторі доступні створення, пошук і редагування власних сценаріїв,
постійні ID, SQLite persistence, чернеткові версії та зворотне архівування. Аналіз використовує
ті самі ID та показує відсутність результатів. AI-генерація в UI, обчислення оцінок і
Qt WebEngine ще не реалізовано. Ключі API та `.env` не потрібні.

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
без мережі: `uv run --offline --locked pytest`. MockLLMProvider належить
Phase 4; поточний код узагалі не викликає LLM або зовнішніх сервісів.
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
Режим Аналізу показує відсутність результатів. Email/Web генерація,
публікація й обчислення аналітики ще не реалізовані.

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
LLM Integration: реалізацію передано на REVIEW; прийняття власником ще не виконано.
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
| Preferred backup candidate, disabled до owner verification | gemini / gemini-4-hydrogen | low, medium, high, xhigh |
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

### Hydrogen connectivity — власник запускає перший тест після review

Попередня bounded live перевірка на reviewed32e6de1 підтвердила доступ до
Groq GPT-OSS120B та Gemini3.5FlashLite. Gemini3.8Flash повернув unavailable;
власник повідомив про два такі результати. Це не доводить access/quota restriction.
Попереднє Hydrogen повідомлення про allowlist було локальним rejection, без
Google API request. Published availability не підтверджує доступ конкретного
ключа. **Hydrogen live не викликався в цьому завданні.**

Після review власник виконує один synthetic connectivity request:

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
agents/LangGraph workflows та Email/Web generation UI лишаються наступними фазами.
