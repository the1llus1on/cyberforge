# Phase 9 — Learner Simulation

**REVIEW — implementation and local gates complete; owner acceptance pending.** Architecture та implementation
окремо дозволено власником 17.11.2026; merge/ACCEPTED/Phase10 не дозволено.
Base main `dfba3fbaa1b2b8b94d279d3cef3f132c03cc9391` (accepted Phase8, merged PR9).
Feature branch: `feat/phase-9-learner-simulation`.

## Scope та нормативне узгодження

Вузька dated amendment SRS v3.0, 17.11.2026: §§3.9,8.1,8.3,8.5–8.6,
11.4,12.8,14.2,16.6,23–24; первісний текст та CRLF збережено.
ADR-0009 фіксує approved lifecycle, authorization, event semantics, Qt boundary
та Phase10 handoff. Phase0–8 залишаються ACCEPTED; старі planning/review записи
є датованою історією, а не чинним станом. Phase10–12 NOT STARTED.

## Реалізована поведінка

- Learner navigation: «Мої сценарії» та «Мої результати». Catalog має лише
  eligible immutable publications, dedup Scenario, latest eligible new start.
  Introduction не створює attempt. Active older publication має пріоритет над
  newer version; revoked active attempt видимий зі станом restriction.
- ScenarioAttemptV1: UUID, learner/scenario/publication/version/manifest,
  original verified grant provenance, immutable title, EMAIL/WEB, decision,
  web_visited, UTC timestamps, revision/sequence. IN_PROGRESS переходить лише
  до explicit COMPLETED або ABANDONED. Нові independent repeats без ліміту.
- SQLite partial unique index за learner+Scenario через всі версії; transactional
  start-or-resume, BEGIN IMMEDIATE, optimistic revision, unique request UUID,
  stable positive sequence. Migration0007 additive, FK/index/checks, immutable
  events/attempt binding, terminal consistency guards. Unsafe downgrade blocked.
- AttemptEventV1 — лише factual actions, закрита vocabulary без score judgment.
  Email: email_opened/inspect_sender/inspect_link/report; transition:
  decline/open_internal; Web: inspect_address/leave/report/confirm/submit_synthetic;
  system: started/web_entered/completed/abandoned. Web component ID звіряється
  з exact immutable artifact. Event API взагалі не приймає form values/metadata.
- Request replay перевіряє current access і operation digest, не дублює events;
  intentional repeated inspection має новий UUID. Insert failure відкочує state.
- Revocation/membership removal/archive/deactivation блокують наступні actions;
  attempts/events зберігаються. Alternative current grant залишається valid.
  Restore resumes original publication. Ownership history/events read не потребує
  current grant, але не завантажує restricted content; foreign learner та
  Instructor/Admin endpoints denied.
- Email використовує MailPreview/MessageBody з learner controls, published
  content без regenerate/edit. Відкриття листа не є sender/link inspection.
  Report не завершує спробу. Decline зберігає pending decision; confirmation
  окремо завершує без Web. Cancel/restart не вигадує terminal outcome.
- InternalNavigationV1 перевіряє exact publication/scenario/version/manifest/
  resource/source main. display_url ніколи не передається URL loader/DNS.
  open_internal commit переводить stage=WEB; тільки successful local load
  записує web_entered/web_visited. Failed load не є visit або inspection.
- WebBrowser/WebPageV2 використовують прийняті isolated off-record profile,
  request interception, popup/download/file/JS restrictions та fixed synthetic
  fields. Component-aware signal додає factual persistence через trusted controller.
  Renderer recovery і disposal order збережено. Confirmation використовує
  asynchronous open/finished; stale session/browser callbacks guarded.
- Completion/abandonment explicit confirmed та terminal. Navigation/logout/close
  очищують widgets, але зберігають unfinished attempt. Resume restores DB stage.
- Personal history показує title/version/status/start/end/basic details та
  «Оцінка ще не обчислена». Жодних points/percent/pass-fail/AI assessments.

## Точна межа Phase10

Future deterministic scorer отримує immutable manifest → snapshot/rubric
reference, rubric-declarations-v1/criterion-registry-v1 та ordered AttemptEventV1.
`web_visited` потребує system/web_entered після successful display;
transition/open_internal сам по собі не означає visit. Safe-decline completion
має transition/decline → system/completed без web_entered. Missing Web evidence
не є failure/zero; applicability застосовує Phase10. Revisioned rubric meanings
не змінюються. ScoringService, penalties, numerical results, Mentor та analytics
не реалізовано/не викликаються. Runtime learning не використовує LLMGateway.

## Перевірки та evidence

Використано лише isolated synthetic fixtures/DB, без live Groq/Gemini та owner DB.

- Initial backend focused: 16PASS/3FAIL; safe-message constructor і archive test
  invocation виправлено; наступний `tests/test_learner_attempts.py`: **19PASS**.
- Expanded backend run: 30PASS/2FAIL (test used nonexistent Database.path);
  test виправлено; focused restart/navigation/rollback/migration: **11PASS**.
- Дві довші sandboxed backend batches завершено signal143 без final summary;
  їх не зараховано як full PASS. Required full run виконується окремо нижче.
- Real Qt first path виявив deprecated QMessageBox.setButtonText під warnings
  as errors; button(...).setText виправлено відповідно до official Context7 docs.
- Outer workspace sandbox не запускає Chromium (`Operation not permitted` у
  sandbox_host_linux.cc); tests повторено поза outer sandbox зі збереженим
  Chromium sandbox, без insecure flags чи runtime policy exceptions.
- Real default WSLg learner E2E/revoke/restore/recovery/compact/lifecycle:
  `QT_QPA_PLATFORM=wayland UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest tests/ui/test_learner_simulation.py -q --tb=short`
  **5PASS**; latest 14.10s before final reading-space adjustment.
- Final targeted WSLg learner + actual WebEngine isolation:
  `QT_QPA_PLATFORM=wayland CYBERFORGE_LEARNER_SCREENSHOTS=/tmp/cf9-screens UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest tests/ui/test_learner_simulation.py tests/ui/test_web_security.py -q --tb=short`
  **8PASS/16.83s**, exit0. Settled synthetic Email/Web screenshots inspected at
  1100×720; footer within viewport, body text readable, no horizontal clipping.
  Three render/leave/resume cycles retain one attempt and responsive MainWindow.
  WSLg may emit existing nonfatal Mesa/Zink/EGL initialization messages.
- `tests/test_learner_demo.py`: **2PASS/1.99s**, socket.connect forbidden,
  valid publication through accepted services, private credentials preserved,
  existing DB sentinel untouched by refused learner-demo initialization.
- `uv run --no-sync ruff check .`: PASS; `ruff format --check .`: **136files PASS**.
  `git -c core.whitespace=cr-at-eol diff --check`: PASS (SRS retains existing CRLF).
- `UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv build --offline --out-dir /tmp/cf9-build`:
  wheel+sdist PASS. Fresh installed wheel under `/tmp/cf9-wheel-env`, Python `-I`:
  wheel-origin import, packaged migration0007, offline publication, learner safe
  decline/completion/history PASS. Empty dependency cache lacked google-genai,
  so wheel installed with --no-deps and read-only existing verified dependencies
  added through a temporary .pth; fresh dependency resolution is not claimed.
- Expanded all-action demo correction: strict Form tuples require JSON validation;
  fixture failure corrected before delivery. Final learner backend **32PASS/46.39s**.
  Final demo/WSLg/WebEngine security **10PASS/22.80s** with all five Web actions,
  including submit_synthetic and explicit leave→confirmed completion.
- Native Chromium keyboard activation (Tab→Enter) records published hero confirm
  through the real page/controller/event path with JavaScript disabled:
  `QT_QPA_PLATFORM=wayland UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest tests/ui/test_learner_simulation.py -k real_web_navigation -q --tb=short`
  **1PASS/4.33s**. No runtime JavaScript bridge added.
- Actual offline WSLg CLI startup/shutdown smoke with fresh `/tmp` DB exits0:
  `QT_QPA_PLATFORM=wayland UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync cyberforge --database /tmp/cf9-cli-smoke-final.sqlite3 --learner-demo --smoke-test`.
- Final stable full offline gate (source/tests frozen throughout):
  `QT_QPA_PLATFORM=offscreen UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest -q --tb=short`
  **1053PASS/670.67s**, exit0: 1014 prior +39 new cases. Includes migration,
  data-integrity, RBAC, concurrency, actual Qt/WebEngine security and regression
  checks. Intermediate full1053PASS/655.75s and1053PASS/728.93s are not the final
  stable-source evidence. Only evidence/status documents changed afterwards.
- Final delivery wheel/sdist rebuilt in `/tmp/cf9-delivery-build`; installed-wheel
  Qt WSLg startup/shutdown smoke with fresh DB exits0. No source import fallback.
- Final commit/PR and exact-head Linux/Windows CI: recorded in PR/delivery report
  after push, avoiding another documentation commit that would change that HEAD.

## Owner manual WSLg acceptance — точні кроки

З root репозиторію, у звичайному терміналі власника (не у Chromium-incompatible
outer execution sandbox), без ключів і мережі:

```bash
demo_dir=$(mktemp -d /tmp/cyberforge-phase9.XXXXXX)
uv run cyberforge --init-demo --learner-demo --database "$demo_dir/demo.sqlite3" --credentials-file "$demo_dir/demo-credentials.json"
QT_QPA_PLATFORM=wayland uv run cyberforge --learner-demo --database "$demo_dir/demo.sqlite3"
```

Нова initialization потребує nonexistent DB; повторний запуск використовує лише
останню команду. Відкрийте приватний JSON у локальному редакторі для паролів;
не надсилайте/не копіюйте credentials до PR чи logs. Setup не друкує паролів.

1. Sign in `teacher_demo_1`; Constructor → створений scenario → «Опубліковані
   версії». Перевірте version1 та grant «Група A». Нічого не регенеруйте.
2. Sign out, sign in `learner_demo_1`; «Мої сценарії». Є один training scenario;
   Constructor/Analytics/Admin не доступні. «Переглянути інформацію» показує
   simulated objective/no-real-credentials notice; history ще порожня.
3. Explicit «Розпочати навчання». Відкрийте main Email, виконайте sender/link
   inspections і report. Report залишає IN_PROGRESS.
4. «Не переходити за посиланням» → «Повернутися»: completion не відбувся.
   «Завершити сценарій» → «Підтвердити»: neutral completion без Web/grade.
5. «Мої результати»: version1/COMPLETED/start/end, factual details, «Оцінка ще
   не обчислена». Немає 0%,100%,pass/fail або AI feedback.
6. Start repeat з catalog; нова спроба. Main Email → approved CTA → Web. Адреса
   лише visual; actual content internal. Прокрутіть сторінку до allowed action
   controls, перевірте адресу/report та доступні synthetic actions. Fields readonly.
   Leave або explicit complete → confirmation. History має дві terminal attempts.
7. Start третю спробу; виконайте кілька Email actions, закрийте застосунок без
   abandonment. Запустіть останню CLI-команду, sign in; «Продовжити проходження»
   відновлює ту саму спробу/Email. Перейдіть Web, повторіть restart; stage=WEB,
   новий open_internal не дублюється. Back/Forward не завершують attempt.
8. Для revocation залиште unfinished Web attempt; sign out, sign in instructor;
   «Опубліковані версії» → selected version1 → revoke Group A з confirmation.
   Sign in learner: restricted active attempt збережено; нові actions/content
   blocked, власна history доступна. Instructor відновлює Group A grant;
   learner resumes original attempt/version. Publication artifact/manifest не змінено.
9. «Припинити проходження» → cancel не змінює status; confirm → ABANDONED,
   history збережена, наступний start створює нову спробу.
10. Повторіть кілька open/Web/Back/resume/logout циклів, 1100×720, Tab/Space;
    основне вікно має залишатися responsive. Запишіть owner evidence та issues.

## Ризики й acceptance gate

Owner manual acceptance та independent review ще не виконані цим документом.
Physical native Windows11, DPI, hardware GPU, executable/installer залишаються
Phase12 risks; Windows Server2022 CI не є physical acceptance. Історичні results
не оцінено: це навмисний Phase9 boundary. Тест failed-load відтворює Qt failure
callback і реальне recovery load; accepted renderer-process termination/security
regressions зберігаються в загальній suite. No sandbox/graphics flags changed.

Після engineering checks статус лише REVIEW. Next action: незалежний review та
owner checklist; без merge/ACCEPTED/Phase10 до окремого дозволу власника.

## Змінені файли

- SRS; README; IMPLEMENTATION_PLAN; DEVELOPMENT_LOG; PHASE_8_ACCEPTANCE status;
  цей PHASE_9_ACCEPTANCE; ADR0009.
- learning/__init__.py, learning/contracts.py; application/learner_attempts.py,
  learner_demo.py; publication `_content` transaction reuse.
- persistence/models.py, migrations/versions/0007_learner_attempts.py.
- ui/learner_pages.py, shell.py, email_preview.py, email_body.py, web_browser.py;
  main.py explicit offline demo flag.
- tests/test_learner_attempts.py, test_learner_demo.py,
  ui/test_learner_simulation.py; existing migration tests' expected head updated
  без видалення assertion/regression; CI early learner gate/30min allowance.

### Leave cancellation regression — final correction

Actual WSLg regression reproduced1FAIL/3.97s: Web leave recorded correctly,
but cancelling completion left the Web view hidden. Guarded asynchronous
confirmation cancellation now restores the current browser surface; persisted
leave evidence stays immutable and status remains IN_PROGRESS. Test asserts
visible recovery, deliberate repeat leave, then confirmed completion.
Final focused learner/WebEngine security8PASS/18.71s; Ruff136files PASS.
One new stable full suite is running after this correction; preceding full
runs are retained as intermediate evidence and not used as final-head proof.

Final engineering state: REVIEW. Stable full1053PASS/670.67s, Ruff136files PASS,
focused actual WSLg8PASS/18.71s, packaged offline startup/lifecycle PASS.
Source/tests frozen during final suite; owner manual acceptance pending.
CI final-head evidence remains a mandatory independent remote gate.
