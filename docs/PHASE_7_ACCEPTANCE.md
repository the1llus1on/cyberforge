# Phase 7 — Hybrid Component-Based Web Constructor

**Статус: REVIEW; очікується незалежний review та рішення власника.** Архітектуру й реалізацію дозволено
власником15.11.2026. Прийняття фази та merge не дозволені; Phase8 не розпочато.
Історична база: Phase6 ACCEPTED, main0fc97861e8e9c84393253e79c142c7c54adcb8b3.

## Вимоги та реалізація

| SRS | Критерій Phase7 |
| --- | --- |
| §§6.4–6.5,9.3,26.5 | Один renderer,9typed components,5presets,3themes; bounded layout/variants, без arbitrary code |
| §§10–11 | WebInputV2/WebSlotsV2/WebComponentSlotV2 → WebPageV2/WebDraftV3; closed wire schema passes unchanged Groq strict projection; legacy contracts retained |
| §§6.1,6.10,11.4 | Saved Email required, exact Scenario/version/parameters, authoritative context including manual sender overrides, Email revision/content digest |
| §§6.6,15.3,16.3 | display_url — лише текст; actual internal origin cyberforge://page/random-token/index; dedicated off-record profile, deny request/navigation gates |
| §§6.2–6.3,26.3 | Dark outer shell, tab/icon/title, read-only address, Reload; Back/Forward disabled for single-page preview; approximately90% central width,1100×720 |
| §§6.7–6.8 | Read-only actual HTML/CSS plus canonical JSON, highlighting/scroll/Copy; visual add/remove/reorder/property/theme/action editor |
| §§6.8–6.9 | Validated local Apply, Cancel, unsaved candidate, explicit Save, Save/Discard/Remain guard; failed/stale workers preserve material |
| §§9.3,10,16.7 | web-prompt-v2, existing LangGraph/Runnable/gateway; text/component/page scopes with deterministic protected merge; source metadata locally composed |
| §§14,4.9 | Additive0005, one canonical JSON per version, optimistic revisions, write transaction validation, immutable published/archived, safe downgrade |
| §§16.4–16.5 | Escaped text, controlled HTML/CSS/CSP; JS off, no external assets, popups/downloads/permissions/file/remote blocked; fixed synthetic form values, no credentials |
| §§21,23–24 | Offline regressions, actual Chromium endpoints/clicks, real WSLg, packaging/migration and exact-head Linux/Windows CI; owner acceptance separate |

Архітектура/довіра/lifecycle/обмеження: [ADR-0007](adr/0007-hybrid-web-constructor.md).
SRSv3.0 має датовану owner-approved Phase7 поправку, numbering/history збережено.

## Збереження та stale source

WebMaterialService повторно використовує AccountService/ScenarioService/Email service.
Instructor та Administrator пишуть власні drafts; Administrator може читати чужі,
Learner доступу не має. Provenance не є authorization. Всі permission/source checks
виконуються до/після генерації, при ручному Apply і в write transaction Save.

0005_web_materials додає лише таблицю, constraints та triggers: exact version FK,
Web revision, scenario revision, source Email revision/digest, source fingerprint,
canonical JSON/schema/renderer version, creator/timestamps. Email rows не змінюються.
Published/archive writes blocked і сервісом, і DB triggers. Downgrade із Web даними
відхиляється; порожню таблицю можна видалити без втрати Email. Нова scenario version
починається без копіювання матеріалів.

Email revision змінюється при кожному explicit Save: навіть повторне збереження
незмінного листа консервативно потребує Web review. Stale Web зберігається для
читання/інспекції; edit/refinement/Save з попереднім source заборонені. Reopen та
«Перегенерувати» використовують новий saved Email, створюють candidate; лише Save
замінює попередній Web. Повна змістова/рубрикована readiness перевірка — Phase8.

## Browser isolation та докази

Custom scheme реєструється перед QApplication; profile не використовує browser чи
account state. Handler обслуговує тільки exact current internal document/GET.
Interceptor до networking stack блокує інші requests; navigation gate відхиляє
redirects/external/file/data, передає лише дозволені action IDs у local controller.
JS, local storage, DNS prefetch, remote/file content access, WebGL/plugins та зайві
features disabled; permissions denied, downloads cancelled, new windows denied.
CSP default/script/connect/img/font/frame/object/form-action none, лише developer
inline CSS. Chromium sandbox ніколи не вимикається. Forms readonly з фіксованими
synthetic values, без довільного credential entry/retention, endpoints або events.

Actual Chromium tests запускають контрольований loopback server: external images,
styles, scripts, HTTPS і redirects не досягають endpoint. Незалежний interceptor
перевіряється навіть із test-only relaxed remote-content setting та без CSP.
Actual clicks перевіряють form submit, popup/download links та internal action;
script не виконується, навігація не виходить за approved document. Це real engine,
не лише mocks. Windows CI має повторити ті самі tests; physical Windows11 — Phase12.

## Безпечна офлайн-демонстрація власника

У bash з кореня репозиторію:

```bash
phase7_demo_dir="$(mktemp -d /tmp/cyberforge-phase7-demo.XXXXXX)"
uv run --offline --locked cyberforge --init-demo \
  --database "$phase7_demo_dir/demo.sqlite3" \
  --credentials-file "$phase7_demo_dir/credentials.json"
QT_QPA_PLATFORM=wayland uv run --offline --locked cyberforge \
  --database "$phase7_demo_dir/demo.sqlite3" --web-demo
```

Збережіть `phase7_demo_dir` для reopen. Приватний credentials JSON відкрийте локально;
увійдіть `teacher_demo_1` із його випадковим паролем. Не надсилайте паролі в чат.
Команди створюють нову БД; owner .env, credentials, demo DB та native environment
не змінюються. --web-demo потребує --database, ігнорує .env/keys та вмикає позначені
synthetic Email/Web fixtures через real agent/gateway/validation/rendering path.
Це не AI success і не fallback після cloud failure.

1. «+» → новий синтетичний сценарій → Save параметрів. Обидва матеріали «Не створено».
2. Відкрити Web без saved Email: generation blocked із зрозумілим поясненням.
3. Створити Email → за потреби вручну змінити synthetic sender/context → Save.
4. «Створити сайт»: default «Автоматично». Обрати preset/theme → «Згенерувати».
   Перевірити статус/індикатор, display-only адресу, браузерний вигляд і scrolling.
5. Повторити presets Авторизація/Портал/Повідомлення/Документ; це одна library/renderer.
   Зміна dropdown сама не змінює draft або БД. Можна змішувати компоненти після генерації.
6. «Редагувати сайт»: обрати компонент, змінити текст/variant, додати/видалити/
   переставити компоненти; cards/fields/actions мають окремі рядки й allowlists.
   Шапка лише першою, підвал останнім;3–12components,1–6cards,1–3fields,до5actions.
7. Apply оновлює unsaved canonical preview; Cancel відкидає активні dialog edits.
   Invalid fields/order/composition дають українську помилку та не змінюють working draft.
8. Перевірити light/dark, Academic/Corporate/Service, layouts. Editor scrollable;
   preview не звужується постійною боковою панеллю.
9. «Переглянути код»: HTML/CSS точно відповідають actual rendering inputs;
   JSON містить поточні ручні правки; всі вкладки read-only, scrolling/Copy працюють.
10. Перевірити local buttons/confirmation, synthetic form. Адреса не редагується;
    Back/Forward disabled, Reload перезавантажує тільки current internal page.
    Немає реальної автентифікації, введення паролів, learner events чи scoring.
11. AI scopes: «лише текст», «компонент», «уся сторінка». Latest manual candidate
    передається агенту; перші дві межі захищають unrelated data детерміновано.
    Демо лише детерміновано додає інструкцію, без semantic AI переписування.
12. Перейти до іншої сторінки: Remain/Discard/Save. Discard не змінює saved artifact.
    Failed generation не стирає preview або saved JSON.
13. Явний Save повертає до картки: зелений Web, scenario все ще draft/unpublished.
    Reopen та restart із тією самою БД/--web-demo відновлюють exact draft.
14. Змінити й зберегти Email: Web «Потребує перевірки», старий Web збережено;
    refinement/edit blocked. Reopen → нова generation → review → explicit Save.
15. Перевірити1100×720, доступність критичних дій, прокручування, клавіатуру.

WSLg screenshots (Codex automation, не owner manual acceptance):
[Компактний preview](screenshots/phase-7-web-compact.png),
[Візуальний редактор](screenshots/phase-7-web-editor.png),
[Збережені матеріали](screenshots/phase-7-web-saved.png).

## Owner-only live Groq acceptance

Codex не виконував live requests. Для minimal test створіть/збережіть synthetic
Scenario та Email у новій demo БД за кроками1–3; Web ще не генеруйте. Закрийте GUI.
Власник запускає зі своєю чинною accepted .env, без зміни файлу:

```bash
QT_QPA_PLATFORM=wayland uv run --offline --locked cyberforge \
  --database "$phase7_demo_dir/demo.sqlite3"
```

Показаний provider/model має бути groq/openai/gpt-oss-120b. Startup/selection API
не викликають. Увійти → saved Scenario → Web → Generate — перший явний live request.
Перевірити local validated output, source inspector і visual quality окремо.
Застосувати одну manual text edit; обрати «AI: лише текст» або «AI: компонент» →
коротка інструкція → Generate — другий явний request. Звірити protected source,
unrelated components, ручні правки й unsaved semantics. Save лише після review.

Output default4096 лише для Groq GPT-OSS Web; CYBERFORGE_WEB_MAX_OUTPUT_TOKENS
має пріоритет над shared parameters; shared limit має пріоритет над default.
Будь-яке додатне explicit значення, включно8192+, дозволене без hard cap.
Для першого test не потрібно змінювати .env. Власник фіксує лише available usage/
output count у Groq console, outcome й local validation; keys/prompts/content не
логувати й не надсилати. Підвищення Web default потребує фактичних usage/payload
доказів. Cloud failure не перемикається на Mock. Backup діє лише за чинною explicit
provider configuration; перевірка backup не входить у minimal test.

## Перевірки, gate та залишкові ризики

Поточні focused/full/build/WSLg результати й precise commands — DEVELOPMENT_LOG.md.
Exact final SHA, PR та Linux/Windows CI фіксуються після push у delivery report/PR
без циклічного documentation-only commit. Final local gate: Ruff117files PASS, full pytest886passed/506.40s,
Web UI/security15passed/34.17s; real WSLg35passed/30.20s та post-fix compact
3passed/9.36s. Package/installed-wheel/migration/security PASS. Initial Windows CI
compact-width failure та remediation збережено у DEVELOPMENT_LOG; final Linux/Windows
CI gate перевіряється на final PR HEAD.

Owner WSLg functional acceptance та live Groq/visual quality review очікуються.
Structural validation не доводить semantic consistency чи навчальну якість; source
provenance — fingerprint, не підпис. Один renderer/одна сторінка; HTML/CSS не
редагуються; forms тільки fixed synthetic values. Multi-page authoring, learner
navigation/events, readiness/publication, scoring/analytics поза Phase7.
Native physical Windows11, DPI/keyboard/installer, broader performance та final
presentation polish відкладено до Phase12 як ризики. Windows CI не є physical
Windows11 acceptance. **Phase7 не може стати ACCEPTED без рішення власника.**

## Змінені файли

- Normative/docs: TECHNICAL_SPECIFICATION.md, docs/adr/0007-hybrid-web-constructor.md,
  docs/IMPLEMENTATION_PLAN.md, docs/DEVELOPMENT_LOG.md, цей acceptance record, README.md,
  три phase-7 screenshots.
- Contracts/renderer: src/cyberforge/web/{__init__,contracts,presets,renderer,resources}.py.
- AI/config/demo: agents/{web,workflow}.py, llm/config.py,
  application/web_demo.py, .env.example; general gateway/schema projection unchanged.
- Services/storage: application/web_materials.py, persistence/models.py,
  persistence/migrations/versions/0005_web_materials.py.
- UI/startup: main.py, ui/{web_page,web_browser,web_editor,web_source,scenario_page,
  shell,clipboard_shortcuts}.py.
- Tests: tests/test_web_{contracts,generation,materials,renderer}.py,
  tests/ui/test_web_{constructor,security}.py; conftest.py,
  existing test_email_materials.py/test_groups_database.py migration-head assertions,
  test_clipboard_shortcuts.py binding regression. Existing tests retained.
