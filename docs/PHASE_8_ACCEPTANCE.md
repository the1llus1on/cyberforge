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
| §§3–4,21,24 | Constructor integration section, link/rubric modals, read-only Email/Web review, detailed checks/groups/final confirmation, grants/history, explicit next draft; compact1100×720, scroll, guards, session clearing |

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
2. Створіть Email → review → explicit Save; створіть Web → Generate → review → Save.
   Зелені картки означають saved artifacts; стан ще «Чернетка».
3. Нижче карток відкрийте «Зв’язок · Рубрика · Публікація».
   Налаштуйте label, HTTPS URL і єдину дозволену internal target; Save link.
4. «Email preview»: main показує label/URL/internal ID та інертний CTA.
   Прокрутіть body до ресурсу; фоновий лист не отримує primary CTA.
   «Web preview» показує exact saved Web; URL не навігує назовні.
5. «Рубрика»: позначте email.sender, transition.safe_decline та web.address.
   Змініть додатні weights; Web applicability лише після відвідування.
   Збережіть. Спробуйте empty rubric/недодатну чи нечислову вагу — save blocked.
6. «Готовність і публікація»: перегляньте individual reasons/corrections, exact
   material revisions і rubric count. Без груп/підтвердження publication не проходить.
7. За бажанням явно змініть link URL на інший safe synthetic HTTPS URL; Save.
   Перевірте display_url_mismatch warning. Перегляньте обидва матеріали й зміст.
8. Позначте GroupA. Позначка attestation підтверджує semantic review та warnings
   exact snapshot. «Публікувати сценарій» відкриває фінальне підтвердження;
   Cancel нічого не публікує. Повторіть і явно підтвердьте.
9. Перевірте published identity/version і read-only Link/Rubric/Email/Web.
   Немає learner screens/events/scores. Закрийте діалог: картка показує publication.
10. «Історія та доступ»: revoke GroupA, перевірте audit; regrant GroupA додає
    нову подію, не стирає revoke. Вміст і manifest незмінні.
11. «Створити нову версію» без зміни parameters: v2 DRAFT, матеріалів/рубрики/link
    немає. Історія дозволяє відкрити v1 read-only незалежно від нової чернетки.
12. Archive/restore: history/grants/audit збережені. У draft після створення нових
    materials/review повторне Email Save робить Web stale; publication blocked.
13. Перевірте Save/Discard/Remain у link/rubric editor, account switch/signout,
   1100×720, вкладки/прокручування/клавіатуру, reopen/restart тієї самої synthetic DB.

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
