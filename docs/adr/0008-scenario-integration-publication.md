# ADR-0008 — Інтеграція, готовність і незмінна публікація

Дата: 15.11.2026. Архітектура дозволена власником; реалізація **REVIEW**, local gates PASS; owner acceptance pending.
Нормативна основа — датована вузька поправка SRSv3.0 §§4.8–4.9,6.10,11–12,14,23–24.

Зберігаємо ScenarioService/AccountService та єдину SQLite. IntegrationService
повторно валідує canonical EmailDraftV2/WebDraftV3 і metadata без AI. Один
ScenarioLinkV1 від main (сталий slot ID, background не дозволено) містить source
та target revision/digest, CTA label/display URL, exact internal ID, open_internal
і source provenance. Не шукаємо URL у тексті, не змінюємо accepted artifacts.
Safe display URL mismatch — acknowledged warning; wrong internal target — blocked.
Preview вставляє plain text, без anchor/network. Hash — consistency, не permission.

RubricDefinitionV1 використовує bounded criterion-registry-v1: фіксовані meanings,
actions, phase, positive finite weights, дозволена applicability. Web лише
web_visited; non-Web safe path обов’язковий. critical_action=null: meanings та
penalties невирішені до Phase10. rubric-declarations-v1 не є scoring strategy;
майбутній scorer має явно перевіряти compatibility, не змінювати historical meaning.

Readiness завжди похідна. Preflight показує технічну готовність без groups/review.
BLOCKED не overrideable; warnings та semantic coherence потребують explicit
confirmation. DB review receipt записує actor/time, snapshot/groups/warnings;
будь-яка source revision/digest change робить його непридатним. Publish повторює
всі перевірки в тій самій BEGIN IMMEDIATE транзакції, перевіряє expected Scenario,
review ownership і групи; manifest/grants/status commit атомарно. Status change
не збільшує parameter revision. Preview/Save не публікують.

Manifest містить immutable references+digests, schema/renderer/semantics versions,
review identity, publisher/time. Не дублюємо великі JSON: existing Email/Web,
ScenarioVersion, Link/Rubric та manifest захищено DB triggers/FK. Немає READY status.
Нова explicit version копіює лише parameters, без materials/link/rubric/grants.
Історичні публікації читаються за version незалежно від latest draft.

Group grants живуть окремо. Власник додає лише assigned groups (Administrator
має existing administrative group access); revoke дозволено після reassignment.
DB triggers додають audit кожного grant state change; audit append-only,
grant rows не видаляються, regrant зберігає весь ланцюжок. Manifest digest незмінний.
Archive зберігає content/grants/audit, блокує publication/new starts; restore
повторно перевіряє grants/membership. Read-only learner access deduplicates
publication та обирає max eligible version per scenario для future new starts.
Running-attempt revoke policy належить Phase9; attempts/events тут відсутні.

Нових залежностей немає. Офіційний SQLAlchemy SQLite transaction API звірено через
Context7: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#transactions-with-sqlite-and-the-sqlite3-driver
Чинний AccountService BEGIN IMMEDIATE збережено. SQLite migration0006 additive;
unsafe downgrade із даними відхиляється. Physical Windows11 — Phase12 risk.

Перевірка методичної межі15.11.2026: офіційний
[NIST TN2276](https://csrc.nist.gov/pubs/tn/2276/final) описує human email phishing
 detection difficulty. Readiness не трактує шкалу як learner score або Web metric.

SQLite migration0006 explicitly starts real BEGIN IMMEDIATE only if DBAPI has no
transaction: sqlite3 legacy SELECT/DDL does not imply one. This protects upgrade
and multi-revision downgrade schema/stamp rollback when an older material guard
refuses a later downgrade step. Focused regression compares tables/triggers/stamp;
owner data are never used for migration testing.
