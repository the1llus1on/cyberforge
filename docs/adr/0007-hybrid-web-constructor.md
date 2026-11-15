# ADR-0007 — Гібридний компонентний Web Constructor

Дата: 15.11.2026. **Архітектура затверджена власником; реалізація REVIEW.**
SRS v3.0, датована поправка §§6.4–6.10,9.3,11.3,26.3,26.5.

Один deterministic renderer дев'яти компонентів замінює rigid template selection
для нових Web artifacts. П'ять presets — hints/стартові композиції, не незалежні
генератори. Academic/Corporate/Service та approved variants дають незалежну
візуальну тему сайту. Відхилено arbitrary model HTML/CSS/JS та generic frontend framework.

Closed required wire WebSlotsV2 містить компактні component slots без unions;
локальний composer перетворює їх на typed, closed, discriminated domain components
WebPageV2/WebDraftV3. Type-specific properties, ID/order/references/actions/bounds
валідуються локально. groq_strict_schema та legacy V1/V2 semantics не змінюються.
Registry задає дев'ять типів; internal policy задає limits (початково3–12).

Saved Email тієї самої Scenario version є обов'язковим trusted source. Context
береться з його canonical artifact, включно з instructor override. Web зберігає
Email revision/content digest та source fingerprint; це consistency, не підпис
і не authorization. Зміна source зберігає старий Web як stale; refinement/Save
потребують нового source через регенерацію. Нові scenario versions не копіюють Web.

WebMaterialService повторно використовує AccountService/ScenarioService та shared
SQLite transaction/RBAC rules: owner writes, administrator reads unrelated data,
learner denied; published/archived read-only. Additive web_materials migration,
explicit Save, optimistic revisions та DB triggers; downgrade з даними fail closed.
Canonical structured payload + renderer version є authoritative, HTML не дублюється.

AI: existing SpecializedAgent/LangGraph → GatewayRunnable → LLMGateway;
web-prompt-v2 отримує current draft, source Email та registry, із untrusted data
boundary. Text-only та selected-component merge детерміновано обмежують зміни;
source metadata завжди встановлює код. Web-specific optional output override,
shared override, потім Groq GPT-OSS default4096; інші operations не змінюються.
Жодних автоматичних live requests або silent Mock fallback.

Manual modal editor змінює canonical candidate, валідує кожне Apply й оновлює
preview. Cancel відкидає dialog edits, Save записує БД. Worker delivery використовує
queued GUI-thread signals, session/request identity та pre/post source checks;
Save/Discard/Remain guard зберігає несхвалені правки. Inspector показує actual
HTML/CSS inputs та canonical JSON, з highlighting/copy, лише читання.

Qt6.10.3: dedicated off-record profile, memory cache/no persistent cookies,
developer-owned custom scheme registered before QApplication. Handler віддає лише
current approved document; interceptor дозволяє лише точний internal URL/GET.
Navigation повторно перевіряється; action links передають лише validated IDs
trusted controller без реальної навігації. JS/storage/remote/file access disabled,
permissions denied, downloads cancelled, popups denied, restrictive CSP та escaped
content. Chromium sandbox не вимикається. Form descriptors показують фіксовані
synthetic values; довільне credential entry/retention відсутнє. Local status actions
не створюють learner events/scoring. Reload працює лише з поточним документом;
Back/Forward disabled для single-page preview.

Офіційні джерела, перевірені через Context7 15.11.2026:
[Profile](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineCore/QWebEngineProfile.html),
[Interceptor](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineCore/QWebEngineUrlRequestInterceptor.html),
[Page](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineCore/QWebEnginePage.html),
[Scheme handler](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineCore/QWebEngineUrlSchemeHandler.html).

Обмеження: одна сторінка, structural/provenance consistency не доводить змістову
навчальну якість. Owner review/live test окремі. Publication/readiness Phase8,
learner navigation/events Phase9, scoring Phase10, analytics Phase11.
Browser isolation має пройти actual engine gate зараз; physical Windows11,
DPI/installer/final polish — ризики до Phase12, не перевірені вимоги.

Перевірка методичної межі15.11.2026:
[офіційний NIST TN2276](https://csrc.nist.gov/pubs/tn/2276/final) визначає
Phish Scale для human detection difficulty електронних листів. Web prompt/schema
не використовують цю шкалу як Web difficulty або learner score.

Windows CI remediation у межах того самого рішення: native selector minimum hints
обмежено для compact workspace; browser tab elides visual title, зберігаючи повний
tooltip/canonical value. Renderer/trust boundary та збережені дані не змінюються.

Numeric Windows CI identified the remaining bottom action-row minimum828px.
Edit action now lives in the top row, matching Email; code/generate/save remain
below preview. This preserves labels/font size and browser height at1100×720.
