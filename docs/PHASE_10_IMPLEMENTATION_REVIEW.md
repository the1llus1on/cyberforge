# Phase 10 — deterministic scoring та Mentor: implementation review

Дата: 17.11.2026. Статус: **REVIEW / PENDING OWNER ACCEPTANCE**.
Phases0–9, Phase10 architecture та WP1 — ACCEPTED; Contract Freeze Gate — PASSED.
Scope: WP2–WP7 implementation та WP8 review preparation, один Draft PR.
Phases11–12 — NOT STARTED; merge та whole-phase acceptance не дозволені.

Normative sources: [SRS v3.0](../TECHNICAL_SPECIFICATION.md) §§9.4,12,14.7,23–24,
[ADR-0010](adr/0010-deterministic-scoring-mentor.md),
[accepted WP1 freeze](PHASE_10_WP1_CONTRACT_FREEZE_REVIEW.md).
Baseline main: `de40af1899b913cbbdb152117900a25e7c9d6b02`.
Branch: `feat/phase-10-complete-scoring-mentor`.
Exact final SHA, Draft PR та final-head CI evidence фіксуються у PR/delivery після
publication, без circular documentation commits. Цей review не є owner acceptance.

## Реалізований scope та reversible design decisions

- `evaluation/scoring.py`: production pure `ScoringService`; exact immutable-source
  validation до scoring, frozen strategy `cyberforge-weighted-actions-v1`, binary
  criteria, descriptive transition, applicability, Decimal/string arithmetic,
  half-even final percentage, canonical evidence/result digests. Повторні events
  збережено як references; score не множиться. AI не викликається.
- `application/scenario_readiness.py`: prospective service rule перевіряє positive
  numerical denominator обох completion paths. Atomic publication повторно
  використовує цю readiness у write transaction. Historical rubric loader та
  published sources не змінені; decision-only history залишається UNSCORABLE.
- `application/evaluations.py`: evaluation-scoped real SQLite `BEGIN` для read та
  `BEGIN IMMEDIATE` для write до першого DB-backed auth read; role/active session/
  ownership; narrow exact historical-source loader без active grant, без content
  endpoint. Explicit Core detail-first inserts, deferred FK та parent-last seal.
- `StoredEvaluationIntegrityValidation`: єдиний authoritative read/retry/Mentor
  validation path, придатний для майбутнього окремо authorized analytics adapter.
  Перевіряє canonical envelopes, усі relational projections/details, source/event
  binding, complete selected set/order, Decimal totals, versions, timestamps та
  digests. Corruption → explicit integrity error, без repair/delete/rescore.
  DB unavailable/busy відрізняються від integrity error.
- `application/mentor_feedback.py`: scoring commit окремий від feedback. Trusted
  `educational-facts-v1`, sanitized revision label та existing MentorAgent/gateway;
  explicit configured cloud only, bounded fact selection та local validation.
  Offline/timeout/invalid response → deterministic Ukrainian explanation.
  UNSCORABLE не передається як incompatible completed MentorInputV1. Provider
  input не містить identity/raw events/source text/credential/form values.
  Retry зберігає authoritative first feedback навіть після provider recovery.
- `ui/learner_results.py`: «Мої результати» з own history, statuses/dates/version,
  explicit «Обчислити оцінку», detail/applicability/transition/observations,
  background feedback worker, retry, scrollable compact Ukrainian text. Pending,
  incomplete, abandoned, genuine zero, nonzero, UNSCORABLE, missing feedback,
  integrity та denied states різні. Restricted source content не завантажується.
  Dedicated bounded Qt pool, session epoch та existing shell close-wait flow
  відкидають stale callbacks; logout очищує history/detail/feedback.
- Старий Phase9-only history placeholder замінено production results page;
  simulation/completion залишаються незалежними від evaluation failure.

Немає нових dependencies, іншої SQLite, score thresholds, critical penalties,
NIST scoring claims, analytics, exports або release/installer functionality.
SRS, ADR-0010, frozen contracts/canonical validators та golden fixtures незмінні.
Minor decisions вище не змінюють approved architecture або evaluation semantics.

## Migration 0008 та immutable storage

`0008_evaluations` після `0007_learner_attempts` — additive, без backfill.

| Table | Production representation та guards |
| --- | --- |
| `evaluation_results` | UUID PK; UNIQUE attempt FK; learner/scenario/publication/version/rubric FKs; exact rubric/source/event identities; canonical result/evidence TEXT; exact Decimal totals/percentage TEXT/null; status/reason/count/revision/time/digests |
| `evaluation_criteria` | Deferred initially-deferred result FK; PK(result_id,criterion_id), UNIQUE(result_id,position); binary/null/applicability checks; canonical detail TEXT та exact Decimal TEXT |
| `mentor_feedback` | UUID PK, UNIQUE result FK; bound result/evidence digests; mode/fallback/provider/model/time projections; canonical feedback TEXT/digest; independent transaction |

Eleven production triggers захищають immutable UPDATE/DELETE, replacement та
conflicting UPSERT, closed post-seal detail insertion, exact selected set та
registry order, envelope/projection equality й feedback source binding.
Parent insertion без complete details та orphan commit відхиляються. Unique indexes
підтримують authoritative attempt/feedback winner; FK history без cascade delete.
Будь-які evaluation/detail/feedback rows блокують downgrade. Rejected multi-revision
DDL/stamp operations rollback разом; empty downgrade/re-upgrade перевіряються.
Усі destructive migration/tampering probes виконуються лише у temporary test DB.
Owner database, credentials, environments та native Phase2 snapshot не змінені.

## Traceability P10-01–P10-18

Усі test paths нижче відносні до `tests/`; actual final execution evidence наведено
нижче. Windows CI, WSLg та owner manual acceptance — різні види доказів.

| Criterion | Implementation / evidence |
| --- | --- |
| P10-01 | Scorer/evidence replay, `test_scoring.py::test_production_golden`, invalid no-visit vector; `ui/test_learner_simulation.py` real safe/Web/display-failure |
| P10-02 | `test_scoring.py::test_independent_action_criteria` positive/negative each action; safe/reversed/repeated golden; accepted native/authored Web tests |
| P10-03 | Frozen transition chronology, safe/Web/reversed vectors, production result UI; Phase9 completion rule preserved |
| P10-04 | `test_prospective_paths`, historical loader; `test_evaluation_service.py::test_prospective_publication_rejects_nonnumerical_paths`; exact subset/applicability/weight tests |
| P10-05 | Historical UNSCORABLE fixture and production persistence/feedback; `ui/test_learner_results.py::test_empty_incomplete_abandoned_and_genuine_zero` |
| P10-06 | Production half-even/extreme-weight vectors and frozen WP1 resource/rounding tests; independent Fraction oracle; context independence |
| P10-07 | Byte-identical six golden results; production source-order arithmetic invariance/distinct source digests; exact stored retry identity |
| P10-08 | `test_production_rejects_invalid_sources_and_histories`, source-valid WP1 hostile contracts, production source/seal rejection |
| P10-09 | Production concurrent evaluation/feedback first-winner; idempotent retry; detail-first protocol and recovery tests |
| P10-10 | `test_evaluation_persistence.py` forced detail/parent/commit failures, immutable UPDATE/DELETE/REPLACE/UPSERT; `test_evaluation_migration.py` 0007 preservation/metadata/upgrade rollback; unsafe multi-revision downgrade/restart |
| P10-11 | Owner history/scoring after revoke/archive/membership removal, restarted services; all endpoint denial for foreign learner/admin/instructor/logout/deactivation/stale session; real snapshot before auth |
| P10-12 | Frozen factual confirm/submit_synthetic provenance, policy NOT_CONFIGURED/null critical_action; persisted vectors та UI observations, unsupported critical labels rejected |
| P10-13 | `test_mentor_feedback.py` recording Mock as configured provider, bounded valid selection, timeout/unavailable/key failure, invalid JSON/fact/topic/score/claim, prompt privacy; independent feedback failure/corruption and reauthentication after provider |
| P10-14 | `ui/test_learner_results.py` all states, compact keyboard, actual shell navigation/logout/close; existing UI regression; full local checks, final-head CI and owner checklist below |
| P10-15 | Offline sdist/wheel, isolated installed package migration/evaluation/feedback/startup checks; physical Windows11/DPI/GPU/installer explicitly deferred Phase12 |
| P10-16 | Every production consumer invokes stored validator; modified payload/projection/digest/details/sources/events/attempt/time/recomputed digest fail closed; original ID/history preserved; feedback corruption keeps valid score |
| P10-17 | Repeated/reversed/source-order vectors; full source/evidence/criterion/path references stay canonical and binary; altered invalid chronology denied |
| P10-18 | Owner-accepted WP1 gate predates migration0008; frozen schemas/fixtures retained byte-identically; no incompatible v1 change |

## Verification evidence

Environment: Python3.12 / existing locked dependencies, Linux/WSL2, normal Chromium
sandbox. No live provider/key needed. Source/test/fixture hashes frozen for final
full run; temporary logs/builds/databases remain outside Git.

- Production scorer focused: **37PASS/2.27s**.
- Production persistence guards/integrity/RBAC/concurrency/restart: **60PASS/152.32s**.
- Added production real-read snapshot/revocation, operational errors та prospective
  publication checks: **3PASS/8.47s**.
- Stable focused integration batch (Mentor, migrations, scorer, service, original
  protocol, publication, learner regressions): **209PASS/390.59s**.
- Combined offscreen results/simulation GUI: **21PASS/83.08s**.
- Final malformed-history hardening: source metadata помилка більше не виходить
  raw ValidationError; safe integrity response та cached UI clearing.
  Backend/read-retry **7PASS/10.03s**, actual WSLg negative UI **1PASS/2.18s**.
  Final full regression перезапущено після цієї security correction.
- Full local Ruff lint/format: **PASS**,154Python files.
- Offline `uv build --offline --out-dir /tmp/cyberforge-p10-final-dist`: sdist+wheel **PASS**.
- Isolated `uv pip install --offline --no-deps --python .venv/bin/python --target
  /tmp/cyberforge-p10-final-installed /tmp/cyberforge-p10-final-dist/cyberforge-0.1.0-py3-none-any.whl`:
  **PASS** (`UV_CACHE_DIR=/tmp/cyberforge-uv-cache`).
- `.venv/bin/python -I /tmp/cf-p10-final-wheel-probe.py`: installed-package-only imports,
  six golden scorer vectors, actual migration0008, fresh offline demo, persisted
  result/feedback/reconnect/FK та source-byte parity **PASS**, socket.connect denied.

- Real WSLg `QT_QPA_PLATFORM=wayland` на тих самих results/simulation tests:
  **21PASS/86.00s**, automated agent evidence, не owner manual acceptance.
- Installed-wheel desktop startup/migration0008/Qt event loop у WSLg: **PASS**.
- Production results screenshot1100×720 inspected; requested900×650 retained
  accepted1100×720 shell minimum, не окремий smaller-window proof. Standalone
  results widget680×600 automated compact checks PASS.

Final full offline gate: **1349PASS/942.96s,0failures/0skips**, exit0.
Exact command:
`QT_QPA_PLATFORM=offscreen UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest -q --tb=short --junitxml=/tmp/cf-p10-final-gate.xml`.
All1203accepted baseline tests +146new implementation tests. Final source/tests/
fixtures hashes unchanged throughout. Rebuilt final offline package та isolated
installed-wheel/source parity/WSLg startup PASS after integrity correction.
Початкові interrupted runs не є passing evidence. Три legacy latest-revision
assertions оновлено з0007 на0008 перед restart повного regression gate;
accepted tests/requirements не вилучено. WP1 scratch tables перейменовано у
`proof_*`, щоб зберегти всі original protocol probes поруч із production schema.

## Owner manual WSLg acceptance — PENDING

Використати нову окрему demo DB за existing initialization workflow; не
перезаписувати попередні demo files або owner DB:

```bash
demo_dir=$(mktemp -d /tmp/cyberforge-phase10.XXXXXX)
uv run cyberforge --init-demo --learner-demo --database "$demo_dir/demo.sqlite3" --credentials-file "$demo_dir/demo-credentials.json"
uv run cyberforge --learner-demo --database "$demo_dir/demo.sqlite3"
```

Відкрити приватний JSON локально, без публікації/копіювання паролів у report.
Обліковий запис `learner_demo_1`, synthetic publication для Групи A.

1. Safe decline: «Мої сценарії» → вступ → почати → відкрити main Email → перевірити
   відправника → відмовитися → підтвердити completion. «Мої результати» → pending
   row → «Обчислити оцінку». Очікується100.00% із default demo rubric, Web criterion
   «Не застосовується», final decline та local Ukrainian Mentor explanation.
2. Email→Web: почати нову спробу; внутрішній CTA → дочекатися owned page display →
   перевірити адресу → report/confirm/синтетична form action за бажанням → leave
   або explicit completion. Оцінити. Показано factual Web path та selected criteria;
   confirm/form не оголошені violation, penalties або реальним витоком даних.
3. History/detail: перевірити version/date/state, кілька attempts, keyboard/Tab,
   scroll та compact1100×720. У новій Web спробі без sender/address inspection
   завершити explicit completion та оцінити: actual0.00%, відмінне від pending.
4. Припинити окрему спробу та залишити одну in-progress. Для них немає final score.
   Historical UNSCORABLE перевірено автоматично на isolated pre-Phase10 publication;
   production publication навмисно блокує нову decision-only rubric.
5. Закрити/повторно відкрити ту саму DB (без повторної initialization): result ID,
   score та feedback збережені; незавершена спроба відновлюється. Cloud у
   `--learner-demo` вимкнено; локальний feedback доступний без ключів/мережі.
6. Вийти під час/після feedback; history/detail очищені. Увійти іншим learner:
   чужі спроби відсутні. Instructor/admin не отримують learner results endpoint.
   Закриття під час активного feedback коректно очікує завершення worker.
7. Instructor revoke/archive: owner learner історія та evaluation лишаються
   доступними; restricted simulation content/actions — заборонені. Restore не
   змінює original publication/result. Automated negative service probes покривають
   foreign IDs, session revocation/deactivation та storage corruption.

Ці кроки не оголошено owner-verified. Owner confirmation та independent review
потрібні перед окремим рішенням про acceptance/merge.

## Remaining risks та acceptance gate

Немає відомого unresolved BLOCKER, MAJOR або MINOR implementation finding.
Local engineering gate PASSED; exact-head Linux/Windows CI evidence фіксується
після publication у Draft PR/delivery. Це не independent review чи acceptance.
Owner manual acceptance **PENDING**. Physical native Windows11, DPI, hardware GPU,
executable/installer та final release acceptance — deferred Phase12 risks.
WSLg/Windows Server CI не замінюють physical Windows11 verification.
No live provider availability claim; configured model grounding тестовано offline.
Локальні digests не є захистом від довільного authorized local code/DB tampering;
corruption reads fail closed, без automatic repair. Existing owner data збережені.
Наступна дія — independent owner review Draft PR та checklist, без Phase11 start.

## Exact implementation scope

Implementation checkpoint: `27e99f482766dfac50caa794ab313f979511da53`.
Загалом26files:9source,13test,4documentation; final evidence commit не змінює code.

New production files:
`src/cyberforge/evaluation/scoring.py`,
`src/cyberforge/application/evaluations.py`,
`src/cyberforge/application/mentor_feedback.py`,
`src/cyberforge/persistence/migrations/versions/0008_evaluations.py`,
`src/cyberforge/ui/learner_results.py`.
Modified production files: `application/scenario_readiness.py`,
`persistence/models.py`, `ui/learner_pages.py`, `ui/shell.py` під `src/cyberforge`.

New tests: `test_scoring.py`, `test_evaluation_service.py`,
`test_evaluation_persistence.py`, `test_evaluation_migration.py`,
`test_mentor_feedback.py`, `ui/test_learner_results.py` під `tests`.
Updated tests: `test_evaluation.py`, `test_evaluation_protocol.py`,
`test_scenario_integration.py`, `test_email_materials.py`, `test_web_materials.py`,
`test_groups_database.py`, `ui/test_learner_simulation.py`.
Docs: README, IMPLEMENTATION_PLAN, DEVELOPMENT_LOG та цей review.
No secrets, databases, generated screenshots/build artifacts або unrelated files.


WP2–WP6 IMPLEMENTED / LOCAL ENGINEERING VERIFIED; WP7 local gates PASSED,
final-head CI recorded separately; WP8 READY FOR OWNER REVIEW. Overall REVIEW /
PENDING OWNER ACCEPTANCE. Independent review, manual owner confirmation та
separately authorized merge лишаються відкритими gates; Phases11–12 NOT STARTED.

## Independent review remediation — F10-R01 (MAJOR), F10-R02 (MINOR)

Reviewed f4e6c04a13adf70cc5d7dbd6b1ad50b5713c5130; owner authorized narrow
corrections in existing Draft PR13. Original evidence/history above retained.
F10-R01: _render refreshes results only on actual view entry, not unchanged
one-second heartbeat. Auth checks/cleanup still run; explicit refresh and successful
evaluation/feedback updates remain available. F10-R02: result and optional feedback
reads have separate error boundaries; feedback operational/corruption errors cannot
hide an already verified score. Access denial clears protected content, evaluation
corruption remains fail closed. Five new regression cases cover read/write counts,
selection/keyboard/refresh/return/revocation and feedback failure/recovery.
Only shell.py, learner_results.py, tests/ui/test_learner_results.py and review/log
are changed; no migration, scoring, source semantics or frozen fixture changes.
Final checks and exact corrective SHA/CI recorded below/in PR after publication.
Phase10 remains REVIEW / PENDING OWNER ACCEPTANCE; no merge or next phase.

Remediation local gates: full offline1354PASS/825.06s,0failures/0skips;
Ruff lint/format154files PASS; real automated WSLg27PASS/57.25s, including five new
cases and existing learner paths. Exact commands/root causes in DEVELOPMENT_LOG.
F10-R01 MAJOR and F10-R02 MINOR: **RESOLVED / PENDING INDEPENDENT RE-REVIEW**.
No known unresolved BLOCKER/MAJOR/MINOR implementation findings. Native Windows11
and owner manual acceptance limitations unchanged. New final HEAD/CI evidence is
recorded in existing Draft PR13/delivery without circular documentation commits.
