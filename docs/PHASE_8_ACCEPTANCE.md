# Phase 8 — Scenario Integration

**REVIEW — реалізацію й локальні gates завершено; final-head CI перевіряється в PR.** Реалізацію та feature PR
дозволено власником15.11.2026. ACCEPTED/merge/Phase9 не дозволені.
Основа: main `b84e2fbdfcf1d84f86a6d8c30a9b0b868e678212`, accepted Phases0–7.

## Вимоги, реалізація та межі

| SRS | Реалізована поведінка / evidence |
| --- | --- |
| §§4.8–4.9,6.10,11.4–11.7 | Один closed ScenarioLinkV1: scenario/version, main slot, source Email revision/digest, target Web revision/digest, label, HTTPS display URL, exact internal ID, open_internal, stable provenance |
| §§5,6,16 | Native Email показує інертний CTA лише в main; preview не створює anchor/network. Accepted EmailDraftV2/WebDraftV3 JSON не переписуються link editor. Existing WebEngine isolation retained |
| §§6.10,11.6 | Integration повторно валідує saved payload і metadata, parameters/revisions, context/sender override, exact Email binding, schema/renderer, internal target. Digest не authorizes access |
| §§12.2–12.6 | RubricDefinitionV1: registry8criteria, fixed phase/meaning/evidence, positive finite weights≤10000, applicability enums. Web лише web_visited; хоча б1non-Web criterion. Numeric text editor зберігає precision |
| §§4.8,11.6 | Readiness PASS/WARNING/BLOCKED, Ukrainian corrections, checked sources, deterministic snapshot/fingerprint. Technical readiness окрема від groups/review; BLOCKED не overrideable |
| §§4.8,14 | DB review receipt з actor/time, exact sources/groups/warnings; всі зміни інвалідують підтвердження. Semantic coherence потребує явної attestation; model NIST claims не стають verified |
| §§4.9,14 | BEGIN IMMEDIATE publish повторно перевіряє owner/current version/archive/revisions, contracts, groups, readiness/review; manifest+grants+audit+status commit атомарно. Parameter revision/timestamps незмінні |
| §§11.7,14 | Manifest references/digests замість дублювання JSON; sources/version/history захищено FK, existing/new triggers і INSERT OR REPLACE guards. Новий draft не змінює historical publication |
| §§2.3–2.5,14,16.6 | Grants окремі від content; owner додає assigned group, може revoke після reassignment. Кожна state transition додає audit DB trigger; history append-only, regrant не стирає revoke |
| §§2.4–2.5,4.9 | Read-only future learner catalog/content/internal resolution: active session/account, grant/current membership/archive; dedup, max eligible version per scenario, older publications читаються окремо |
| §§3–4,21,24 | Three-step preparation modal, internal read-only Email/Web previews, checklist/groups/final confirmation/result, contextual publication history/access, explicit next draft; compact1100×720, scroll, guards, session clearing |

Нормативна dated Phase8 amendment збережена в SRSv3.0; accepted history не видалено.
Рішення — [ADR-0008](adr/0008-scenario-integration-publication.md).
Rubric registry: email.sender/link/report, transition.safe_decline/decision,
web.address/leave/report. Applicability: all_attempts, web_visited, web_not_visited.
critical_action=null; rubric-declarations-v1 не є scoring strategy. Phase10 має
узгодити explicit compatibility/algorithm/critical semantics. Оцінки не обчислено.

## Persistence та security

Міграція `0006_scenario_integration_publication` після accepted0005 додає6tables:
scenario_links, rubric_definitions, publication_reviews, scenario_publications,
publication_groups, publication_grant_audit. Existing rows/owner DB не змінювалися
для testing. `PRAGMA foreign_keys=ON`, unique publication per version,
optimistic component/grant revisions та serialized writes збережено.
Міграція0006 починає реальну DBAPI write transaction за відсутності чинної: DDL
та Alembic stamp відкочуються разом навіть при відмові downgrade нижчої фази.
Downgrade із integration/review/publication/audit даними відхиляється.
Published parameters/Email/Web/Link/Rubric/manifest не можна update/delete/replace;
initial grant і audit пишуться в publication transaction. Forced final failure
rollback не залишає publication/grants/audit. Duplicate/concurrent publish має1winner.

Один main relationship; URL не витягується з тексту. Safe URL mismatch дає явний
warning. Wrong resource/scenario/version, unsafe URL, unsupported schema/renderer,
stale Email/Web, invalid rubric/group/review блокують. Sender/Web domains не
порівнюються як обов’язково однакові. Publication status не змінює parameter revision.
Сервісні permissions перевіряються до кожної write; administrator може читати чужі
сценарії, але не змінює/публікує їх. Administrator має чинний global group access.

Archive зберігає publications/grants/audit, забороняє нові publications/new starts;
restore повторно використовує current grants/membership без зміни historical content.
«Створити нову версію» працює без parameter changes: new number/DRAFT/р1,
копіює лише валідні parameters; матеріали/link/rubric/grants не копіюються.

## Фактичні перевірки

- Focused persistence/security + accepted Scenario/Email/Web/database:
  `.venv/bin/pytest tests/test_scenario_integration.py tests/test_web_materials.py tests/test_email_materials.py tests/test_scenarios.py tests/test_groups_database.py -q --tb=short`
  — **172passed/234.24s**.
- Migration-chain rollback після відмови older-phase guard: focused
  `.venv/bin/pytest tests/test_scenario_integration.py tests/test_web_materials.py tests/test_email_materials.py tests/test_groups_database.py -k 'migration or refused_lower' -q --tb=short`
  — **5passed/8.50s**. Порівняно tables/triggers/stamp; повторний probe PASS.
- Додаткові corruption/attestation/grant-race/restart:
  `.venv/bin/pytest tests/test_scenario_integration.py -k 'corrupt_persisted or attestation or concurrent_grant or restart' -q --tb=short`
  — **8passed/13.14s**.
- Scenario/Phase8 GUI initial gate:
  `.venv/bin/pytest tests/ui/test_scenario_integration.py tests/ui/test_scenarios_ui.py -x -q --tb=short`
  — **45passed/120.82s**.
- Real WSLg/Chromium:
  `QT_QPA_PLATFORM=wayland .venv/bin/pytest tests/ui/test_scenario_integration.py tests/ui/test_web_security.py tests/ui/test_email_constructor.py::test_mail_navigation_source_copy_explicit_save_reopen -q --tb=short`
  — **11passed/44.36s**; включено exact weight precision, actual Web review,
  repeated disposal та existing external network/JS/popup/form isolation regressions.
- WSLg compact screenshot probe на окремій synthetic DB — **1passed/2.77s**, final refresh **1passed/3.28s**;
  [Конструктор](screenshots/phase-8-constructor.png),
  [Готовність](screenshots/phase-8-readiness.png),
  [Main Email CTA](screenshots/phase-8-email-link.png) оглянуто Codex.
- Ruff lint/format PASS,126Python files; final run нижче. Initial migration name
  collision і forged serialization warning виправлено до stable gate, history у log.
- Offline sdist/wheel build PASS; новий /tmp venv, hash-verified58runtime dependencies,
  built wheel install, `python -I`0005→0006 preservation/integration/review/publish/
  grants/audit/access/new draft/FK та Qt `--web-demo --smoke-test` PASS.
  Wheel/source parity85Python files PASS, private .env/DB/credentials absent.
  Після DDL hardening wheel перебудовано й повторно встановлено; той самий
  installed migration/publication/startup gate та source parity PASS.
  Lock/dependencies/runtime AI policy не змінено.

Це Codex automation. **Owner manual acceptance ще не виконано/не підтверджено.**
Final offline full pytest **977passed/673.63s**, Ruff lint/format126Python files PASS.
Exact commands (cache path потрібний лише в поточному restricted environment):

```bash
UV_CACHE_DIR=/tmp/cyberforge-phase8-uv-cache uv run --offline --locked ruff check .
UV_CACHE_DIR=/tmp/cyberforge-phase8-uv-cache uv run --offline --locked ruff format --check .
UV_CACHE_DIR=/tmp/cyberforge-phase8-uv-cache QT_QPA_PLATFORM=offscreen uv run --offline --locked pytest -q --tb=short
```

Цей977case run виконано після migration-chain rollback fix; попередній976run
залишено в log як historical evidence. Final-head Linux/Windows CI evidence — у PR
та delivery report після завершення remote run;
CI не означає ACCEPTED. Exact delivery SHA/PR/CI у фінальному звіті без circular commits.

## Безпечна WSLg демонстрація власника

З кореня repository створіть окрему нову БД:

```bash
phase8_demo_dir="$(mktemp -d /tmp/cyberforge-phase8-demo.XXXXXX)"
uv run --offline --locked cyberforge --init-demo \
  --database "$phase8_demo_dir/demo.sqlite3" \
  --credentials-file "$phase8_demo_dir/credentials.json"
QT_QPA_PLATFORM=wayland uv run --offline --locked cyberforge \
  --database "$phase8_demo_dir/demo.sqlite3" --web-demo
```

Збережіть phase8_demo_dir для reopen. Відкрийте credentials JSON лише локально;
увійдіть teacher_demo_1 із його випадковим паролем. Не надсилайте його в чат.
--web-demo ігнорує .env/keys, використовує явні синтетичні Mock fixtures; це не
live AI і не fallback. Owner environments/native Phase2 snapshot не змінюються.

1. «+» → «Новий сценарій» → synthetic parameters → «Зберегти».
2. Створіть лист і сайт через existing constructors; review → explicit Save.
   Зелені картки означають saved artifacts, сценарій ще є чернеткою.
3. «Підготовка сценарію» відкриває окреме window-modal вікно. Перевірте identity,
   compact summary та три вільно доступні кроки; перехід «Далі» не публікує.
4. «Матеріали»: картки показують exact saved subject/title. «Переглянути лист» →
   main CTA інертний; background не має primary CTA. «Повернутися до матеріалів».
   «Переглянути сайт» → actual isolated Web; адреса read-only, зовнішньої навігації
   немає. Повторіть Email/Web/повернення; контекст scenario/version незмінний.
5. Змініть «Назва посилання» та «Відображувана адреса» → «Зберегти зв’язок».
   Target лише read-only у «Технічні деталі». Safe synthetic HTTPS mismatch дає
   попередження, не rewrite/автоматичну відмову. Email/Web JSON не змінюються.
6. «Оцінювання»:8criteria у3groups, розгорніть рядок для weight/applicability.
   Web має лише permitted applicability. Перевірте0.000000000123, потім explicit
   «Зберегти критерії» й reopen. Недодатні/nonfinite/нечислові weights, empty rubric
   та Web-only rubric мають відхилятися; попередня saved rubric зберігається.
7. «Використати базовий набір критеріїв» лише готує unsaved editable selection;
   replacement існуючого набору потребує confirmation. Cancel не змінює редактор.
   Після застосування Save виконується окремо; preset не є validated methodology.
8. Змініть link або rubric й перейдіть в інший крок/preview/constructor/Close/X:
   «Залишитися» зберігає edits/view, «Відкинути» відновлює editor baseline без DB
   writes, «Зберегти» виконує explicit service Save. Без правок prompt не з’являється.
9. «Публікація»: checklist походить із readiness service; all reason codes/statuses
   лишаються в «Показати технічні результати». Correction buttons відкривають
   відповідний existing workflow без generation/Save/publication. У missing/stale
   state показано потребу створити/оновити матеріал; target не вигадується.
10. Без груп «Опублікувати сценарій» disabled і показано «Виберіть хоча б одну
    навчальну групу». Оберіть authorized group, прочитайте exact version/statuses,
    критерії, групи й попередження; позначте instructor acknowledgement.
    Зміна editor/group/source має скинути acknowledgement. External changes
    помічаються read-only refresh; незбережені buffers не стираються.
11. «Опублікувати сценарій» → final confirmation називає scenario/version/groups
    та immutable content. «Скасувати» не публікує. Повторіть і явно підтвердьте.
    Result: version зафіксовано, показано groups і повідомлення про future learner
    module. «Переглянути публікацію» відкриває history; «Повернутися до сценарію»
    закриває modal. Learner screens/attempts/events/scoring відсутні.
12. «Опубліковані версії» на ScenarioPage → selected version/date, exact read-only
    Email/Web, link/rubric summary, group state. Revoke → Cancel не записує змін;
    confirm називає exact scenario/version/publication/group/operation. Regrant
    додає audit event, не стирає revoke; audit розгортається окремо.
13. «Створити нову версію»: новий draft без materials/link/rubric/grants.
    «Опубліковані версії» лишається доступним. Виберіть попередню version й
    перевірте exact historical materials/grants/audit, потім close: current draft
    лишається відкритим. Archive/restore зберігає publication content/history.
14. Через actual ScenarioPage button повторіть open → Web → Email → Web → return →
    close → reopen щонайменше3times; використайте «Закрити» та window-manager X.
    Main GUI/renderer мають залишатися responsive; повторіть із maximized window,
    1100×720, keyboard Tab/Space та resize зі stacked material cards.
15. При unsaved edits перевірте voluntary signout/account navigation guard.
    Forced session expiration очищує review/private buffers і не дозволяє writes
    старою сесією. Restart тієї самої synthetic DB зберігає saved publications.

Не використовуйте звичайний owner database для демонстрації або migration tests.
Групові права, account invalidation, multiple memberships/latest eligibility та
конкурентність мають окремі automated tests; learner read model UI ще відсутній.

## Обмеження та незалежне review

Structural equality/provenance не доводять педагогічну узгодженість; потрібен owner
content review. Phish Scale описує difficulty detection Email, не Web score;
[офіційний NIST TN2276](https://csrc.nist.gov/pubs/tn/2276/final) перевірено15.11.2026.
critical semantics/penalties/actual scorer — Phase10; running attempts after revoke —
Phase9. Жодних live Groq/Gemini requests, deliveries, learner attempts/events/scores
або analytics у Phase8. Physical Windows11/DPI/keyboard/installer залишаються
Phase12 ризиками; Windows CI не є фізичним Windows11 acceptance.

Independent review має оцінити immutable reference triggers/FK/REPLACE guards,
transaction ordering, exact receipt bindings, registry/scorer compatibility й
future internal-navigation API. Review receipt є authenticated instructor attestation,
а не криптографічним доказом фактичного прочитання.

## Змінені файли

- SRS, README, IMPLEMENTATION_PLAN, DEVELOPMENT_LOG, ADR0008, цей acceptance record,
 3WSLg screenshots.
- application/scenario_integration.py, scenario_readiness.py, scenario_publication.py,
 scenarios.py; scenario_integration/{__init__,contracts}.py.
- persistence/models.py та additive0006 migration.
- ui/scenario_integration.py, scenario_page.py, email_preview.py, email_body.py.
- tests/test_scenario_integration.py, ui/test_scenario_integration.py;
 existing Email/Web/database migration-head assertions оновлено, tests збережено.

## Independent review F8-01/F8-02 — 16.11.2026

Phase8 **REVIEW**, existing PR9. Reviewed baseline c8f95eb; previous evidence вище
збережено. No merge/ACCEPTED/Phase9, owner databases/.env/keys поза scope.

- **F8-01 частково відтворено:** actual Qt button відкривав final confirmation без
  груп, з unauthorized або stale group selection. Uncaught ValidationError не
  підтверджено: existing service BLOCKED check уже давав ApplicationError без receipt.
  Додано explicit group validation до strict confirmation contract, GUI groups gate
  та click-time preflight; transaction-side revalidation retained, min_length=1 unchanged.
- **F8-02 відтворено:** при2publications відкритий v1 залишався preview, selector
  reset на first/latest publication2. Rebuild відновлює exact ID під QSignalBlocker;
  selection synchronizes opened content/grants/audit, mismatch блокує grant write.
  Grant/revoke confirmation ідентифікує scenario/version/publication/group; Cancel
  не пише, selection change during modal не redirects write. Draft не отримує
  автоматично target historical publication. Existing source/manifest immutability
  перевіряється після grant/regrant.

Baseline automated gate:4failed/4passed/26.12s; exact commands і final evidence —
DEVELOPMENT_LOG. Additional tests охоплюють service empty/unauthorized/reassigned/
deleted groups, actual button no groups/forged group/stale assignment, loss of
assignment during final confirmation,2published versions із separate grants,
selection/refresh/reload/reopen, actual grant modal Cancel/Confirm, source/manifest
immutability, target switch during modal та unsaved Remain/Discard.

Owner checklist доповнення (не заявляється виконаним):

1. Технічно валідний draft без обраних груп показує technical readiness, але Publish
   disabled. Оберіть assigned group → дія доступна; зміна прав адміністратором до
   click або final confirmation блокує publish з українським поясненням.
2. Створіть2published versions із різними group grants. В history оберіть v1:
   version identity, Email/Web previews, selector і grants/audit мають показувати v1.
   Оновіть/reopen v1; target не має змінюватися на v2.
3. Revoke/grant показує exact publication/group. Cancel залишає grants/audit без
   змін; Confirm змінює лише selected publication, published content незмінний.
4. На новій draft версії history не має обраного grant target. Якщо є unsaved edits,
   Remain при виборі history залишає draft і поля; Discard відкриває selected version.

Remediation final local evidence:

| Gate | Actual result |
| --- | --- |
| Baseline reproduction before fixes | 4failed/4passed/26.12s; service ValidationError не відтворено |
| Focused F8-01/F8-02 | 11passed/63.64s |
| Relevant integration/persistence/ScenarioPage UI regressions | 131passed/287.78s |
| Real WSLg finding tests / actual Qt clicks and modals | 7passed/59.55s |
| Full offline pytest after stable fixes | **988passed/857.37s** |
| Ruff lint/format | PASS,126Python files |
| Diff/private-file check | PASS,7changed files; owner DB/.env/keys поза scope |

Точні команди й initial restricted Chromium exit133/retry evidence — DEVELOPMENT_LOG.
Initial restricted regression run не вважається PASS; identical allowed-host run
пройшов131tests із Chromium sandbox enabled. Packaging/migrations/dependencies не
змінено, repeated wheel/build не потрібні. Final-head Linux/Windows CI перевіряється
в PR9; precise SHA/run/results додаються у PR description і delivery report.
Owner manual acceptance pending; native physical Windows11 лишається Phase12 risk.
Phase8 REVIEW, no merge/ACCEPTED/Phase9.

## WSLg Web preview failure — 16.11.2026 (REVIEW)

Owner reported loss of the application after opening Web in Integration/Publication.
The actual production button path reproduced premature dialog deletion on default
Wayland and with --disable-gpu; **no full app crash or renderer crash was observed**
in the unrestricted-display UID1000 run. A Qt native rendering-surface hide made
nested QDialog.exec return; the caller then deleted the loading dialog. This is a
verified application lifecycle defect. The owner's exact fatal exit/freeze state
cannot be inferred from the supplied Mesa messages alone.

Fixed by window-modal open/finished with explicit ownership, safe refresh and
cleanup. Guards/session changes retained. Load/renderer failures show Ukrainian
messages with internal-only Reload; status/code logging excludes URLs/content.
No graphics defaults, startup configuration, dependencies or migrations changed.

Controlled AFTER-fix matrix:3actual render/close/reopen cycles per configuration,
same isolated published synthetic DB, GUI heartbeat, nonempty text/pixels, zero
renderer terminations and byte-identical DB: default Wayland, --disable-gpu,
QT_QUICK_BACKEND=software, LIBGL_ALWAYS_SOFTWARE=1 and GALLIUM_DRIVER=llvmpipe PASS.
Default and --disable-gpu retain Mesa warnings despite successful rendering.
Xcb fails before QApplication due missing libxcb-cursor0; no package installation.
The runner has no /dev/dxg, so these results do not prove physical GPU compatibility.

Recommended normal launch after updating the existing PR branch:

```bash
QT_QPA_PLATFORM=wayland uv run --offline --locked cyberforge \
  --database "$phase8_demo_dir/demo.sqlite3" --web-demo
```

Optional Qt-supported software-rendering comparison, set before application startup:

```bash
QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu" QT_QPA_PLATFORM=wayland \
  uv run --offline --locked cyberforge \
  --database "$phase8_demo_dir/demo.sqlite3" --web-demo
```

Use an isolated synthetic database; the commands do not edit .env. No application
code adds flags or changes unrelated Windows startup. No unsafe renderer settings,
root/sudo, network bypass or sandbox disablement is part of the fix.

If a separate hardware-dependent problem remains, collect safe Qt diagnostics on
that synthetic DB (logs stay local, do not share credentials or private content):

```bash
QT_QPA_PLATFORM=wayland \
QT_LOGGING_RULES="qt.webenginecontext.debug=true;qt.webengine.compositor.debug=true" \
uv run --offline --locked python -X faulthandler -m cyberforge \
  --database "$phase8_demo_dir/demo.sqlite3" --web-demo \
  2> "$phase8_demo_dir/webengine-diagnostics.log"
printf 'CyberForge exit status: %s\n' "$?"
```

Owner recheck required: open Integration via the actual Constructor button, switch
Email/Web repeatedly, close via Close and window-manager X, reopen at least3times,
confirm page content and main GUI remain responsive, then repeat with only the
optional software flag if needed. Report process exit status versus renderer-only
failure. Earlier automation is not owner acceptance. Phase8 REVIEW; no merge,
ACCEPTED or Phase9. Native physical Windows11/GPU/DPI remains an unverified risk.

Preview-fix focused evidence: unchanged production-path WSLg regression
**1failed/4.30s**, then **1passed/6.21s** after fix. Default WSLg integration/security/
compact suite **30passed/173.37s**; single --disable-gpu suite **11passed/35.28s**.
Real own-renderer SIGTERM produces the supported signal, safe Ukrainian message,
responsive main app and successful internal-only Reload with a new renderer PID.
Linux child Seccomp2/NoNewPrivs1/no --no-sandbox verified; direct portable diagnostic
handler test supplements this real-process test (POSIX-only test skipped on Windows).
Saved materials/publication data remain unchanged; three-cycle matrix DB hashes match.
Exact commands and honest restricted-display/test-harness failures are in log.

Additional default-backend trace confirms old QWindow.destroyed between Web tab
selection/page.setUrl and successful loadFinished on all3cycles. The dialog itself
survives until explicit close under open/finished. One /tmp synthetic rendered-view
image inspected; no owner content or credentials recorded. Thus native surface
recreation is observed directly, not inferred only from EGL log messages.

Final preview-correction local gate:

- Full offline suite **992passed/828.97s**, including all988prior cases plus4new.
- Ruff lint/format PASS,126Python files; diff/private-file scan PASS,9changed files.
- Default WSLg30passed; explicit --disable-gpu11passed;5working backend variants
  each3complete published-scenario preview cycles; native-window trace3cycles PASS.
- No source/test changes after stable full-suite start. Early CI Phase8 gate now
  runs actual_constructor_button alongside compact_page; default Linux/Windows CI
  on exact final HEAD is recorded in PR9 and delivery report after push.

This fixes the reproduced modal-lifecycle defect. It does not claim a reproduced
whole-app fatal crash on the owner's exact hardware, nor native Windows11/GPU
acceptance. Owner workflow recheck remains required; Phase8 REVIEW, no merge or Phase9.


## UX redesign — 16.11.2026 (REVIEW)

Owner direction approved; implementation acceptance pending. Before:6permanent
tabs. After:3preparation steps with responsive material cards, internal previews,
compact grouped rubric, readiness checklist, explicit review/publish/result;
publication history/access is a separate contextual ScenarioPage action, available
when any version is published even with a newer current draft. Current manual
procedure above replaces the old tab-based walkthrough; earlier evidence retained.

UI files: `scenario_integration.py`, `scenario_page.py`, new `preparation_widgets.py`;
existing UI test module extended, prior18cases retained. No accepted backend
contract/service/DB semantics, migration, dependency, renderer/security/startup
changes. Source of truth: SRS §§3–4,6.10,11–12,14,16,21 and ADR0008 UX addendum.
No live Groq/Gemini, owner .env/credentials/databases or Phase2 Windows snapshot use.
Owner's preexisting AGENTS.md edit is preserved outside task commit.

WSLg synthetic review screenshots:
[Матеріали](screenshots/phase-8-ux-materials.png),
[Оцінювання](screenshots/phase-8-ux-rubric.png),
[Публікація](screenshots/phase-8-ux-publication.png),
[Лист](screenshots/phase-8-ux-email.png),
[Сайт](screenshots/phase-8-ux-web.png),
[Результат](screenshots/phase-8-ux-result.png),
[Історія](screenshots/phase-8-ux-history.png).

Visual inspection: all8collapsed criteria+summary fit960×680; group/warning/
acknowledgement visible on publication step; preview readable at full content
width.600×580 tested with stacked cards, scrollable content and accessible footer.
Screenshots are synthetic automation, not owner functional acceptance. Physical
Windows11/hardware GPU/DPI/installer verification remains deferred Phase12 risk.
Stable automated evidence is recorded below after full local gates.

UX focused verification: prior18adapted UI regressions PASS; initial16new behavior
cases PASS; Scenario Integration backend88PASS. Real default WSLg stable gate
**48passed/3deselected/502.92s**, actual final-confirmation/resize/keyboard probe3PASS,
final all8rows/both previews/screenshots probe2PASS. Supplemental actual production
Close-button/WM-X lifecycle probe1PASS with3complete cycles, disposal and unchanged
persisted sources. All existing security/isolation/renderer-recovery checks retained.
Full commands, counts and limitations: DEVELOPMENT_LOG (UX focused / real WSLg gates).

Stable full local gate: **1011passed/1091.99s** (all992prior+19new), Ruff lint/format
**127files PASS**, staged diff check PASS.37Phase8 UI cases total in full suite,
including authorized-group reassignment refresh/acknowledgement invalidation.
Runtime/test sources unchanged since full run began.15task files, owner AGENTS.md
excluded. Exact final commit, Linux/Windows CI and run URL are recorded in PR9 and
owner delivery after push; no additional docs-only commit is needed. Engineering
local gate PASS; Phase8 remains **REVIEW**, owner manual acceptance pending.
