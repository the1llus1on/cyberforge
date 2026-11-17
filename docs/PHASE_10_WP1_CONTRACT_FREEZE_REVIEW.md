# Phase 10 / WP1 — кандидати контрактів та докази Contract Freeze Gate

Дата: 17.11.2026. Baseline: `e5213314c88ca6844384b1349ecf8bc2d7428336`.
Branch: `feat/phase-10-wp1-contracts`. **WP1 — REVIEW; Contract Freeze Gate —
PENDING OWNER ACCEPTANCE.** Engineering evidence не замінює owner acceptance.

Власник дозволив лише contracts/canonical/pure validation/facts, offline fixtures
та test-only SQLite proof. WP2/WP3, production ScoringService/EvaluationService,
ORM changes, migration0008, persistent outputs, UI/cloud integration/Phase11 та
merge не дозволені. Власник окремо дозволив commit/push/Draft PR для independent
review 17.11.2026; WP1 NOT ACCEPTED, gate PENDING OWNER ACCEPTANCE.
Дані власника не використовувалися.

Нормативна основа: [ADR-0010](adr/0010-deterministic-scoring-mentor.md),
[SRS v3.0](../TECHNICAL_SPECIFICATION.md) §§12.2,12.8,14.7,23–24,
[WP1 plan](IMPLEMENTATION_PLAN.md). Окремо погоджені owner field specification та
final contract clarifications застосовано; approved scoring architecture незмінна.

## Реалізований WP1 scope та trust boundary

- [contracts.py](../src/cyberforge/evaluation/contracts.py): closed frozen Pydantic
  candidates, strict scalar types, immutable tuples/nested data, explicit nulls,
  version literals, registry/applicability/outcome/arithmetic/digest validators.
- [canonical.py](../src/cyberforge/evaluation/canonical.py): UTF-8 canonical bytes,
  duplicate-key/noncanonical-wire rejection, explicit historical float conversion,
  exact integer-based verification arithmetic. Не production scoring API.
- [validation.py](../src/cyberforge/evaluation/validation.py): pure Phase9 replay,
  references, source/manifest/rubric/material/operation digests та stored envelope/
  detail/evidence consistency. Немає SQL, session authority, provider чи UI access.
- [facts.py](../src/cyberforge/evaluation/facts.py): versioned immutable educational
  catalogue, deterministic projection/explanation, compatible feedback validation.
  Recommendations copied into a read-only mapping; Phase5 module не змінено.

Public JSON trust boundary — canonical parser/model_validate_json: unknown fields,
missing required nulls, duplicate keys, noncanonical UUID/UTC/Decimal forms,
nonfinite values, unsupported versions та type coercions відхиляються. In-memory
construction використовує strict typed inputs; authoritative revalidation завжди
повторюється перед source/result/feedback verification. model_construct і
model_copy не використовуються як шлях прийняття evaluation data.

Pure validation не є authorization, cryptographic callback attestation чи
persisted-result reader. Майбутній trusted service має спочатку виконати session/
account/role/ownership у consistent DB transaction і передати exact loaded inputs
до validate_stored_projection. Без authoritative sources сам envelope не доводить
правильність historical record. Snapshot/archive provenance не замінюється
поточним archive state. Gate не дозволяє production historical content endpoint.

## Exact candidate versions та поля

Машиночитна специфікація — [contracts.schema.json](../tests/fixtures/evaluation/contracts.schema.json).
Schema snapshot test захищає field sets/enum/required-null contract. Canonical
lexical forms і cross-source invariants нижче додаткові до JSON Schema; сама
JSON Schema не доводить digest чи historical source consistency.
Усі поля таблиці required; nullable поля мають бути явно null. Reference має
рівно два поля, без додаткового discriminator, згідно ADR-0010 §D.1.

| Contract | Exact discriminator | Required fields |
| --- | --- | --- |
| `EvaluationSourceV1` | 'evaluation-source-v1' | `schema_version`, `publication_id`, `version_id`, `manifest_schema_version`, `manifest_digest`, `snapshot`, `rubric_id`, `rubric_schema_version`, `registry_version`, `rubric_semantics_version` |
| `EvaluationCriterionSnapshotV1` | 'evaluation-criterion-snapshot-v1' | `schema_version`, `criterion_id`, `label`, `description`, `phase`, `weight`, `applicability`, `evidence_actions`, `critical_action` |
| `CompletedPathV1` | 'completed-path-v1' | `schema_version`, `kind`, `event_refs` |
| `TransitionDecisionV1` | 'transition-decision-v1' | `schema_version`, `final_action_id`, `event_refs` |
| `EvaluationEventReferenceV1` | enclosing contract v1; exactly 2 fields | `event_id`, `sequence` |
| `CriterionEvidenceV1` | 'criterion-evidence-v1' | `schema_version`, `criterion`, `applicable`, `condition_satisfied`, `supporting_event_refs` |
| `CriticalObservationV1` | 'critical-observation-v1' | `schema_version`, `event_ref`, `surface`, `action_id`, `component_id`, `provenance`, `observed_at`, `critical_policy_status` |
| `EvaluationEvidenceV1` | 'evaluation-evidence-v1' | `schema_version`, `attempt`, `source`, `scoring_strategy`, `events`, `event_count`, `terminal_sequence`, `events_digest`, `path`, `transition`, `criteria`, `critical_policy_status`, `critical_observations`, `evidence_digest` |
| `CriterionEvaluationV1` | 'criterion-evaluation-v1' | `schema_version`, `position`, `criterion`, `applicable`, `outcome`, `score`, `weighted_contribution`, `supporting_event_refs`, `descriptive_transition` |
| `EvaluationResultV1` | 'evaluation-result-v1' | `schema_version`, `result_id`, `attempt`, `source`, `scoring_strategy`, `event_count`, `terminal_sequence`, `events_digest`, `evidence_digest`, `path`, `transition`, `criteria`, `critical_policy_status`, `critical_observations`, `status`, `reason_code`, `weighted_numerator`, `weighted_denominator`, `score_percent`, `evaluated_at`, `result_digest` |
| `LocalMentorFeedbackV1` | 'local-mentor-feedback-v1' | `schema_version`, `feedback_id`, `result_id`, `result_digest`, `evidence_digest`, `evaluation_status`, `locale`, `fact_catalog_version`, `synthetic`, `objective`, `facts`, `permitted_topics`, `mode`, `fallback_reason`, `provider`, `model`, `explanation`, `created_at`, `feedback_digest` |
| `EvaluationErrorV1` | 'evaluation-error-v1' | `schema_version`, `operation`, `code`, `retryable`, `correlation_id`, `attempt_id`, `result_id`, `integrity_reason` |

Rule inventory: criterion labels/descriptions/phases/actions/applicability exact
Phase8 registry; weights positive finite ≤10000; applicable numerical 0/1;
non-applicable/descriptive score та contribution null. Selected subset має
exactly one detail/criterion, contiguous positions у canonical registry order.
SCORED → denominator>0/reason null/percentage present. UNSCORABLE → zero sums,
null percentage/NO_APPLICABLE_NUMERICAL_CRITERIA. No thresholds/caps/penalties.
Result ID/timestamp ніколи не регенеруються validation/retry operation.

Error candidate включає final clarification: required nullable integrity_reason,
closed reason/code combinations; transient STORAGE_BUSY/STORAGE_UNAVAILABLE/
SOURCE_UNAVAILABLE retryable, confirmed immutable source corruption/missing та
stored evaluation/feedback corruption nonretryable. ACCESS_DENIED не розкриває
attempt/result IDs. Actual DB exception translation належить майбутньому service,
не WP1 production package. Invalid historical rows never repair/delete/rescore.

## Serialization та обчислення

Sorted object keys, compact comma/colon separators, ensure_ascii=False, UTF-8
без BOM/newline; усі nulls explicit. UUID lowercase; UTC
YYYY-MM-DDTHH:MM:SS.ffffffZ. Decimal — plain string, без exponent/trailing zeros/
negative zero; percentage завжди 2dp. Accepted Phase5 ResultFactsV1 float summary
лише presentation adapter, не input arithmetic/result digest. Array order:
events/references by sequence, criteria by registry, observations by event sequence.

Events SHA-256 охоплює всі persisted AttemptEventV1 fields без derived provenance.
Evidence/result/feedback digest охоплює повний відповідний canonical envelope,
крім лише його власного digest field; nested digests не виключаються.
Legacy manifest/rubric/material/operation fingerprints обчислюються чинними
accepted utilities, не новою canonical projection. Source-valid roundtrips
перевіряються через accepted loaders і source digests.

Weight conversion: Decimal(str(validated historical float)), не Decimal(float).
Verification helper масштабує finite Decimal coefficients до спільного exponent,
сумує integers; numerator/denominator Decimal створюються з exact tuple без
ambient context rounding. Half-even hundredths визначає divmod(10000*N,D),
з tie-to-even quotient. Немає approximation recurring division або production
scoring operation. Вектори 1/32→3.12,3/32→9.38,1/3→33.33,0/1→0.00;
tiny 5e-324 та weight10000 перевірено при низькому ambient precision.

F10-WP1-01 remediation: нові evaluation Decimal scalars мають resource bounds
до fixed-point expansion, integer scaling і hashing: exponent від -324 до 4,
coefficient до 329 digits, magnitude до 70000; raw Decimal text до 345 characters.
Це envelope для shortest-roundtrip historical binary64 weights до10000 та
exact sum максимум семи numerical criteria: 5 integral +324 fractional digits.
Bounds не округлюють значень; historical rubric validator незмінний, event count
не обмежено. Guard діє для JSON strings, Python Decimal і serialization/arithmetic
helpers, включно з zero з hostile exponent. Field bounds weight≤10000 та
percentage≤100 збережено; numerator/denominator≤70000 explicit у schema snapshot.
ROUND_HALF_EVEN divmod oracle та no-intermediate-rounding semantics незмінні.

References: ordinary criteria усі qualifying events; safe decline лише final
effective decline+completion без Web; transition усі decisions/final action;
path окремо (decline/completion або open/first trusted display/completion).
Повний stream зберігає superseded/repeated actions. open_internal не є visit;
Web actions вимагають system/web_entered і exact accepted provenance/components.
Chronology за sequence, не нова monotonic wall-clock policy. Replay звіряє
request/operation identity/digest, terminal state, revision та complete event count.

## Golden vectors і незалежна перевірка

[Test module](../tests/test_evaluation.py) використовує existing publication_env,
accepted Scenario/Email/Web/link/rubric/readiness/review/publication та Phase9
attempt/event services на scratch DB. Mock/demo material generation offline;
UUID/time fixed у фактичних call sites. Historical decision-only rubric
створюється через accepted Phase8 semantics, без prospective rule bypass у
production. App-owned Web actions added до save/publication, не після заморозки.

| Static source-valid fixture | Expected numerator / denominator / percentage |
| --- | --- |
| [safe](../tests/fixtures/evaluation/safe.json) | 4 / 4 / 100.00; Web not applicable |
| [web](../tests/fixtures/evaluation/web.json) | 6 / 7 / 85.71; safe_decline applicable/unmet |
| [reversed](../tests/fixtures/evaluation/reversed.json) | 6 / 7 / 85.71; decline superseded by open_internal |
| [repeated](../tests/fixtures/evaluation/repeated.json) | 6 / 7 / 85.71; 17events, all repeated references retained |
| [unscorable](../tests/fixtures/evaluation/unscorable.json) | 0 / 0 / null; descriptive only, explicit reason |
| [observations](../tests/fixtures/evaluation/observations.json) | 6 / 7 / 85.71; authored confirm/submit, NOT_CONFIGURED |

Кожен fixture містить повні actual source objects/bindings, evidence, result та
SCORED/UNSCORABLE deterministic feedback. Static values порівнюються з відтвореним
accepted path, не оновлюються автоматично тестом. Test reference JSON projection
написана окремо від production canonical helper; Fraction дає незалежну arithmetic.
Усі 18 evidence/result/feedback golden hashes додатково перевірено external
`openssl dgst -sha256` над independently serialized fixture payloads до збереження
static fixtures. Expected source bindings/rubric/manifest digests перевіряються
existing accepted loaders та fingerprint, без зворотного переписування payloads.

[synthetic_hashing.json](../tests/fixtures/evaluation/synthetic_hashing.json) —
окремий serialization-only fixture з external source digest placeholders.
Не є valid published-source fixture. Original five canonical SHA vectors retained:
reference6de80492…; empty-array4f53cda1…; events1e13d0b6…;
evidence6300955d…; resultdbf253ea…. Повні значення — у test assertions/fixture.

Negative coverage: malformed/unknown schemas/IDs/extra/missing nulls, duplicate
JSON keys, bool/fraction integer coercion, noncanonical Decimal/time, corrupted
stream/path/source metadata/criterion weights/sums, missing/extra/reordered detail
rows, recomputed-digest forgeries, unsupported facts/limitations. Shared pure
stored projection pipeline verifies sources перед returning result; feedback
binding/projection перевіряється перед consumption. Existing MentorAgent
перевірено через scripted Mock для valid supplied-facts selection та rejected
invented fact; deterministic fallback не змінює result. No live providers.

## educational-facts-v1

Каталог відповідає owner wording/IDs/topics/fallback design. Для
transition_safe_decline_not_met використано точний виправлений текст:
«Перехід до Web не підтверджує фінальну відмову від переходу, незалежно від
попередніх рішень.» Demonstrated reversal — окремий transition_decision_reversed.
Recommendations/FactV1/MentorInputV1/ExplanationV1 accepted Phase5 незмінні.
Facts не містять raw events, learner IDs/names/attempt IDs, field values або
психологічних/unsupported recognition claims. Trusted objective фіксований;
невідомий fact ID або змінений catalogue text відхиляється. Non-applicable
не перетворюється на failed fact. Versioned feedback зберігає source result digest;
UNSCORABLE не примушує completed MentorInputV1 з null чи fabricated zero.

F10-WP1-02 remediation: Mentor ResultFactsV1.rubric_version тепер
`rubric-revision-<snapshot.rubric_revision>`, а не internal rubric_id.
Strict positive revision береться з validated immutable snapshot; до48 digits,
інакше bounded `rubric-revision-large` (без integer-to-string expansion).
Це non-identifying presentation label, не authoritative identity або digest.
Exact rubric ID/source digests залишаються лише local evaluation records;
precomputed score і accepted Phase5 schemas незмінні. Privacy regression перевіряє
actual MentorInputV1, scenario rubric ID, result/attempt IDs та identity fields.
П'ять SCORED feedback labels/digests оновлено; evidence/result/source objects і
UNSCORABLE fixture byte-identical. Новий label не є fingerprint revision content.

## Contract-to-database mapping — лише специфікація для майбутнього WP3

| Future table | Contract mapping / required constraints |
| --- | --- |
| evaluation_results | result_id PK; attempt_id UNIQUE FK; learner/scenario/publication/version FKs; rubric_version_id FK rubric_definitions.version_id; scenario_version/logical rubric identity/revision/source digests; immutable canonical result_json/evidence_json TEXT; Decimal sums/percentage TEXT/null, closed status/reason, terminal sequence/revision/count, evaluated_at UTC |
| evaluation_criteria | result_id deferred FK; PK(result_id,criterion_id); UNIQUE(result_id,position); strict applicable/outcome/0-or-1/null invariants; exact Decimal weight/contribution TEXT; canonical criterion_json equals envelope |
| mentor_feedback | feedback_id PK; result_id UNIQUE FK; exact result/evidence digest binding, mode/fallback/provider/model/time projections, immutable feedback_json TEXT та feedback_digest |

Усі projections мають точно відповідати envelopes та accepted source rows.
No REAL scoring columns, no orphan/cascade history deletion. Completeness:
selected rubric set = envelope set = persisted detail set, canonical positions.
Production DB schema, triggers/column names і migration0008 ще не створені.
Final WP3 schema потребує окремих migration-chain/downgrade/field-parity tests;
це не підміняється scratch proof. No historical backfill/rescoring/upgrades.

## Test-only SQLite/SQLAlchemy protocol proof

[Protocol tests](../tests/test_evaluation_protocol.py) використовують existing
Database/session factory/Python3.12/SQLAlchemy/connection foreign_keys+busy_timeout
на тимчасовій DB, з accepted users і власними scratch protocol tables. Жодних
production models чи migration changes. Source criterion IDs у proof навмисно
у зворотному selection order; expected positions виводяться з accepted registry,
а не з source array order чи caller criterion_count.

Explicit BEGIN precedes first DB-backed AccountService.require/role/ownership
read. Same read snapshot залишається consistent під час writer commit;
concurrent account deactivation видима наступному request. Denied roles/ownership
не читають protected details. BEGIN IMMEDIATE серіалізує separate-connection writers.
Deferred child FK дозволяє detail-first inserts; parent-last trigger seals exact
selected set/canonical positions/envelope IDs. Missing/extra/duplicate/wrong IDs/
positions, parent-first/lying envelope rejected; orphan commit fails; transaction
context rolls back all rows і recovery succeeds. SQL tracing proves actual Core
statement ordering без ORM autoflush/relationship reordering. Two writers return
one authoritative winner. Post-seal INSERT/UPDATE/DELETE/REPLACE/UPSERT rejected
з recursive_triggers=0 і1; foreign_key_check clean. Scratch WAL лише для concurrent
read/write snapshot proof, не runtime setting change. Alternative protocol не
вводився; actual production consumer authorization залишається майбутнім WP3.

F10-WP1-03 scope clarification: scratch existing-result branch повертає лише
winner ID і доводить idempotent identity, не stored-result integrity. Scratch
payload не містить complete EvaluationResultV1 envelope. Integrity окремо
перевіряють source-valid `test_stored_pipeline_and_feedback_consumption` та
corruption/detail-projection tests через pure validation. Майбутній WP3 retry
зобов'язаний викликати `validate_stored_projection` після transactional authority
та authoritative reads перед поверненням existing result. Scratch proof не
вважається end-to-end verified production retry і не замінює P10-16.

Intermediate scaffold corrections (не final evidence): accepted Web save/control
API test calls виправлено; missing static fixture files заповнено лише після
independent hash checks; one-row reverse-order negative case уточнено, бо reversal
одного елемента не є corruption. Source-order SQL refinement потребував заміни
obsolete scratch position lookup на registry-derived positions; протокол
залишився detail-first/deferred-FK/parent-last. Final proof результат нижче.

## Фактичні verification commands та результати

Environment: Linux/WSL2 6.6.114.1-microsoft-standard-WSL2, Python3.12.3,
Pydantic2.14.3, SQLAlchemy2.0.57, pytest8.4.2, Ruff0.14.14, PySide6 6.10.3.
Existing lock/dependencies залишилися незмінними. Це не native Windows11 evidence.

- Initial focused WP1 batch: **104PASS/89.79s**.
- Expanded WP1 batch: **129PASS/99.38s**.
- Final registry-derived scratch protocol: **47PASS/46.72s**.
- Final schema snapshot/Mock compatibility: **3PASS/0.61s**.
- `UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync ruff check .` — PASS.
- `UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync ruff format --check .`
  — PASS,143Python files.
- Final legacy-instance hardening: **16PASS/13.90s** focused golden/stored/
  schema/Mock/deep-immutability regressions. Revalidated legacy ExplanationV1
  instances through accepted JSON parser after field validation, preserving tuple
  immutability without changing Phase5 models. Initial before-validator variant
  conflicted with strict JSON tuple parsing; corrected and verified before final run.
- First full run deliberately stopped at78%/exit143 after a separate hostile
  legacy-instance probe reproduced a nested mutable-list gap; **не PASS**.
  Немає code/test edits під час цього run. Hardening застосовано після stop;
  final wheel rebuilt/reinstalled і isolated six-fixture parity probe PASS.
- Final stable full offline regression — **1189PASS/656.89s**, exit0,
  **0failed/0skipped**: усі1056accepted cases +133new WP1 cases. Source/tests/
  fixtures hashes remained unchanged throughout final run. Command:
  `QT_QPA_PLATFORM=offscreen UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv run --no-sync pytest -q --tb=short`.
  Outside outer workspace sandbox для normal Chromium sandbox; security flags
  не змінено. Це automated Linux/offscreen, не native Windows11/owner WSLg.
- `UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv build --offline --out-dir /tmp/cyberforge-wp1-dist`
  — sdist+wheel PASS.
- `UV_CACHE_DIR=/tmp/cyberforge-uv-cache uv pip install --offline --no-deps --target /tmp/cyberforge-wp1-installed /tmp/cyberforge-wp1-dist/cyberforge-0.1.0-py3-none-any.whl`
  — PASS (final rebuild uses --reinstall). `.venv/bin/python -I` installed-wheel import/roundtrip/source-parity
  probe — PASS для всіх six source-valid envelopes; no source-package fallback.

Dependencies/lock/startup/UI/production schema не змінювалися. New package
packaging verified. Current official Pydantic strict/frozen/JSON docs перевірено
через Context7; revalidate_instances і explicit canonical boundary застосовано.

## Findings, risks та gate recommendation

BLOCKER/MAJOR architecture deviations не виявлено. Approved only delta:
owner-requested safe-decline wording correction та previously reviewed error
integrity_reason taxonomy; scoring/publication/lifecycle semantics незмінні.
Read-only canonical/source validity не доводить cryptographic UI attestation.
No persistent results, application authorization endpoint чи production scorer.
No unresolved BLOCKER/MAJOR/MINOR implementation findings identified after final
checks. Remaining verification limitations: Windows CI не запускалося (no publication
permission), physical Windows11 remains Phase12, production migration/schema
verification requires separately authorized WP3 після owner freeze acceptance.
Owner acceptance PENDING навіть після automated PASS. Next action — owner review
candidate contracts/evidence; commit/push/PR лише після окремого дозволу.


Final delivery audit: baseline tracked-file hashes matched for every file except
approved plan/log updates; all existing source/tests/migrations/dependencies/SRS/
ADR remained byte-identical. Exactly18changed/new files: five evaluation modules,
two test modules, eight static fixture/schema JSON files, review doc, plan/log.
36relative documentation links resolved. `git -c core.whitespace=cr-at-eol diff --check`
PASS; nothing staged; HEAD stays e5213314c88ca6844384b1349ecf8bc2d7428336.
Engineering recommendation: ready for owner Contract Freeze Gate review;
**PENDING OWNER ACCEPTANCE**, not accepted automatically. На момент delivery
Git publication не виконувалася; subsequent authorization наведено нижче.

## 17.11.2026 — publication for independent review

Власник дозволив commit/push existing feat/phase-10-wp1-contracts та Draft PR до
main, без acceptance/merge/next work package. Preflight exact base/local/remote
main e5213314c88ca6844384b1349ecf8bc2d7428336; GitHub MCP read confirmed remote.
Hashes усіх15verified code/test/fixture files збіглися; baseline accepted files
незмінні крім authorized plan/log. Complete18file scope/secret-pattern audit PASS.
Full1189/protocol47/hardening16 та packaging results вище — previous executed
evidence, не повторені лише для publication. New lightweight checks: Ruff lint,
format143files, relative links/hash/scope та CRLF-aware staged diff checks.
Exact pushed SHA/PR/CI status записуються у delivery report, без moving-HEAD
documentation commits. WP1 ready for independent review, NOT ACCEPTED.


## Independent review remediation — golden feedback evidence

F10-WP1-01/02/03 corrections описано вище. Original reviewed HEAD:
`90ff3976fcaefd2371d6ec31b71c61a17f246e87`. Five updated SCORED feedback digests:

| Fixture | Expected feedback SHA-256 |
| --- | --- |
| safe | `03d23c9e8fc00d6f0b8da5142e30359787a6b06f120f1d794cfab638a1c509c7` |
| web | `cc21fe27db48511ad4fe0e00fb963b00e4709e33f40725e43837be1b691188f7` |
| reversed | `7529ccf00af505f02f6f1eeb14c3c610f81ec0924233fb96937c02cffe7858b4` |
| repeated | `fb01edbe8b9151a4755119753216880fed2e56ccc7bd48e05620952a239662c5` |
| observations | `11ba42b3d7b83cd3a2deef6128000022981a4bfc18ca0a9a5bf6f315bff9e037` |

Усі18evidence/result/feedback hashes перевірено незалежним OpenSSL serialization
probe; Fraction oracle підтвердив arithmetic. Source/evidence/result objects
unchanged; UNSCORABLE feedback і synthetic hashing vectors unchanged. Additional
3263binary64 boundary/neighbor conversions PASS. Focused147PASS (47protocol),
final Decimal/Mentor/schema24PASS;14new parametrized regression cases. Offline
sdist/wheel/isolated installed-wheel six-source pipeline/97source-file parity PASS.
Final full offline regression1203PASS/649.98s, exit0, no failures/skips;
11code/test/fixture hashes unchanged. Final-HEAD Linux/Windows CI після push.
WP1/Contract Freeze Gate remain PENDING OWNER ACCEPTANCE; повторний independent
review обов'язковий, це не approval gate і не authorization для WP2/WP3.


## Owner decision — November 17, 2026 — WP1 acceptance / Contract Freeze

Власник формально прийняв Phase10 / WP1 — Contracts & Evidence Validation
і затвердив Contract Freeze Gate після незалежного review та remediation.
Це актуальне рішення замінює попередні REVIEW/PENDING записи лише як поточний
статус; усі попередні review records збережено як історичні докази.

- Phase10 / WP1: **ACCEPTED**.
- Contract Freeze Gate: **PASSED / OWNER APPROVED**.
- Phase10: **IN PROGRESS / WP1 ACCEPTED / CONTRACT FREEZE PASSED**; не whole-phase ACCEPTED.
- Approved implementation commit: `5d91716544b8a7764f3e2735783e0289b3803c82`.
- [PR #12](https://github.com/the1llus1on/cyberforge/pull/12): owner-authorized
  standard merge-commit лише після final documentation HEAD Linux/Windows CI.
- F10-WP1-01 (Decimal bounds), F10-WP1-02 (sanitized Mentor revision) та
  F10-WP1-03 (scratch retry-proof boundary): **RESOLVED**, прийнято власником.
- У прийнятому WP1 scope немає outstanding BLOCKER, MAJOR або MINOR findings.

Verified evidence: local full offline regression **1203 passed**, focused WP1
**147 passed**, isolated SQLite protocol **47 passed**, final Decimal/Mentor/schema
**24 passed**. Golden vectors/independent digest checks, Ruff lint/format, offline
sdist/wheel та isolated installed-wheel verification — **PASS**.
Original final implementation [CI run44131758053](https://github.com/the1llus1on/cyberforge/actions/runs/44131758053):
Linux `checks (ubuntu-latest)` **SUCCESS**; Windows Server2022
`checks (windows-2022)` **SUCCESS**, verified через GitHub MCP.
Ці CI results стосуються approved implementation SHA, не нового acceptance commit.
Для нового exact PR HEAD обидва CI jobs мають завершитися SUCCESS до merge;
final SHA/run/merge evidence фіксуються у PR description і delivery без circular commits.

Frozen v1 contracts, canonical serialization/golden vectors та documented mapping
тепер normative inputs для майбутньої окремо approved роботи. Incompatible changes
до frozen v1 потребують explicit versioning і documented review. Це не створює
production storage schema: deferred-FK SQLite proof ізольований і test-only;
production migration та actual persisted-result lifecycle ще не реалізовано.
Physical Windows11 release acceptance залишається відповідальністю Phase12.

Phases0–9 та Phase10 architecture — ACCEPTED. WP2 deterministic scoring і WP3
persistence — **NOT STARTED / NOT AUTHORIZED**; migration0008 — **NOT CREATED /
NOT AUTHORIZED**. Production ScoringService/EvaluationService, result UI, cloud
Mentor integration та analytics не дозволені. Phases11–12 — **NOT STARTED**.
Після acceptance recording/merge/ff-only synchronization роботу зупинити;
цей дозвіл не починає наступний work package. SRS v3.0/ADR-0010 незмінні.
