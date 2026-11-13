# Phase 4 — LLM Integration: перевірка власником

Статус: **ACCEPTED власником 2026-11-13**. Реалізацію прийнято після
independent architectural/code reviews; ordinary merge PR5 дозволено лише після
success Linux/Windows CI фінального HEAD. Phase5 — **NOT STARTED**.
Hydrogen connectivity підтверджено owner-run test; повний GUI checklist не
виконаний. Історичні інструкції нижче не є заявою про виконання всіх кроків.

## Вимоги та межі

SRS §§10.1–10.8/11.1/23 Phase4: provider-neutral LLMGateway, Gemini Interactions,
Groq/Mock, text/structured contracts, retries/errors/usage та synthetic privacy.
Погоджені SRS clarifications: §10.2 та narrow Groq-primary policy references,
зафіксовані в ADR-0004; це acceptance step без нових SRS changes. Scenario ownership/RBAC/versioning,
scoring і migrations не змінювалися. Генерація з UI та спеціалізовані агенти
відкладені; ця фаза надає перевірений Python integration layer.

## Offline gateway і Runnable

Після `uv sync --locked` у WSL виконайте з кореня репозиторію:

```bash
uv run python - <<'PY'
import asyncio
from cyberforge.llm.contracts import Contract, GenerationRequest
from cyberforge.llm.factory import create_gateway
from cyberforge.llm.runnable import GatewayRunnable

class Message(Contract):
    message: str

request = GenerationRequest(
    prompt="Synthetic acceptance fixture", synthetic=True,
    operation="structured", schema_version="message-v1",
)
runnable = GatewayRunnable(create_gateway(), Message)
result = runnable.invoke(request)
assert result.structured.message == "Синтетичний приклад"
assert result.telemetry.local_validation == "passed"
assert asyncio.run(runnable.ainvoke(request)).structured == result.structured
print(result.telemetry.model_dump_json())
PY
```

Очікування: mock/mock-v1, success, local_validation=passed; жодного API key,
мережевого запиту або запису в БД. Telemetry не містить prompt/response.
Додатково: `uv run pytest tests/test_llm_gateway.py tests/test_llm_gemini.py
tests/test_llm_groq.py tests/test_llm_runnable.py tests/test_llm_diagnostics.py
tests/test_llm_integration.py -q` (команда в один рядок).

## Коротка WSLg перевірка

1. `QT_QPA_PLATFORM=wayland uv run cyberforge --database /tmp/cyberforge-phase4-acceptance.sqlite3`
   відкриває окрему порожню БД; наявні owner/demo DB не змінюються.
2. Переконайтеся, що оболонка відкривається як Guest, Головна доступна,
   закриття вікна працює, cloud generation не запускається.
3. `uv run cyberforge-llm-check --provider gemini --model gemini-3.8-flash`
   має відмовити з exit2 через відсутність --live, не читаючи ключів.

UI цієї фази не змінювався; повтор усіх Phase0–3 manual scenarios не потрібен.
Не змінюйте Phase2 native Windows acceptance environment. Routine physical
Windows11/DPI/installer acceptance відкладено до Phase12; Windows CI не є
підтвердженням фізичного Windows11 тестування.

## Independent review F-01/F-02: додаткова offline перевірка

`uv run pytest tests/test_llm_review.py -q` перевіряє fixed fallback policy і
Groq structured artifacts без live API. Усі prior Phase0–4 tests збережено.

- Для enabled transient Gemini3.5FlashLite fallback requested_parameters.thinking
  лишається minimal, effective_parameters.thinking стає low; original request
  незмінний. Інші дозволені рівні/None зберігаються. Denied failures не обходяться.
- EmailArtifactV1/WebArtifactV1 через Groq (direct і fallback) проходять schema
  projection лише для known resource-ID regex. Telemetry.schema_projection
  позначає цей виняток. Provider перевіряє structure/types/version, а повний
  regex завжди перевіряє original local Pydantic model до повернення результату.
- Порожній/задовгий/path/URL/space/non-ASCII string ID має завершуватися
  validation/local_validation=failed, хоча він допускається wire type=string.
  Non-string ID також додатково відхиляється локально. Це не full content
  safety/consistency/instructor approval workflow.

Нових UI controls/agents немає, ручний WSLg checklist не розширюється.
Завершення remediation не є owner acceptance і не дозволяє merge/Phase5.

## Live API — окреме виконання

Потрібен окремий явний дозвіл власника. Команди в README; максимум один
запит на кожну дозволену модель, послідовно, без автоматичних retries/fallback.
До такого виконання model access і account quotas позначаються unknown.
Не відкривайте .env/credentials у звітах і не додавайте їх до Git.

## Рішення власника

- [ ] Offline контракти та normalized telemetry перевірено власником.
- [ ] Короткий WSLg startup/close та disabled-live guard перевірено власником.
- [x] Власник явно прийняв Phase4 2026-11-13; accepted residual risks нижче.

Автоматичні докази наведено в DEVELOPMENT_LOG та final PR checks. Цей checklist
не заповнюється автоматично й не заявляє невиконаних owner перевірок.


## Groq primary / Hydrogen backup: reference процедури до acceptance

Попередню Gemini-primary policy superseded. Primary cloud — Groq GPT-OSS120B;
Hydrogen — preferred backup candidate, Lite optional, Flash3.8 access unresolved.
Mock залишається default без explicit cloud config. Нового GUI selector немає.

1. Після review запустіть offline `uv run pytest tests/test_llm_hydrogen.py -q`.
   Тут навіть CLI --live cases використовують fake providers, без API quota.
2. Не змінюючи існуючі ключі, додайте primary Groq provider/model та disabled
   backup config з README/.env.example. Legacy FALLBACK має бути false/unset.
3. Перший реальний Hydrogen test власник запускає явно, один request:

```console
uv run cyberforge-llm-check --live --provider gemini --model gemini-4-hydrogen
```

4. Очікуйте лише metadata, без content/keys. Success підтвердить connectivity
   поточного ключа; unavailable/auth/rate-limit/validation не вважаються success
   і не повторюються автоматично. До success enabled/access_verified лишаються false.
5. Лише після успішного owner test можна вручну підтвердити access_verified=true
   та, якщо бажаний automatic fallback, enabled=true. Тоді застосовується один
   Groq→Hydrogen hop лише після allowlisted technical failures. Щоб вимкнути
   route після verification, лишіть enabled=false.

Hydrogen sampling omission і effective=None відображено в telemetry; requested
parameters зберігаються. Existing F-01/F-02 і local Pydantic validation чинні.
Попередні bounded live evidence на32e6de1: Groq іLite success, Flash3.8 unavailable;
власник повідомив про другий unavailable3.8. Це не підтверджує його access/quota
restriction і не доводить Hydrogen access. У цьому завданні agent не робить
live calls. Native Windows11/Phase12 deferral та owner acceptance gate незмінні.


## Остаточне рішення власника — 2026-11-13

**Phase4 ACCEPTED власником.** Reviewed implementation HEAD:
98a019ce99df992c7ad54bc4f4a49ca02f6516b2. Пройдено independent architecture/code
review; F-01/F-02 усунено. Власник дозволив docs-only фіналізацію та ordinary
merge commit PR5 після final-head CI. Це рішення supersedes pending/REVIEW
формулювання ранніх sections; reference checklist збережено без автоматичного
позначення невиконаних ручних перевірок.

| Тип доказу | Підтверджено |
| --- | --- |
| Automated implementation CI | Linux467passed; Windows465passed,2skipped; run43391679188 success; Ruff/locked install/import/Qt startup success |
| Hydrogen offline acceptance |61passed, owner-reported; agent повтор не виконує |
| Groq openai/gpt-oss-120b live |SUCCESS; попередня bounded connectivity evidence збережена в ADR/log |
| Gemini3.5FlashLite live |SUCCESS; попередня bounded connectivity evidence збережена в ADR/log |
| Gemini4Hydrogen live |SUCCESS, owner-run/owner-reported:5.148s; input39/output5/reasoning25 |
| Manual GUI |Повний owner checklist не виконано; не заявляється як pass |
| Physical native Windows11 |Deferred Phase12; Windows CI не є physical acceptance |

Owner Hydrogen command (вже виконано власником; агент НЕ повторює):

```console
uv run cyberforge-llm-check --live --provider gemini --model gemini-4-hydrogen
```

Approved primary Groq/openai/gpt-oss-120b; preferred **verified** backup
Gemini/gemini-4-hydrogen. Власник погодив activation existing controlled policy
при explicit local environment configuration. .env/keys/default-off runtime
flags не змінюються цим documentation-only acceptance. Access confirmation
стосується перевіреного ключа, не всіх акаунтів/моделей/Structured Outputs.

### Прийняті залишкові ризики

- Gemini3.8Flash availability unresolved.
- Live complex Email/Web structured schema generation ще не перевірено.
- Account-wide provider quotas незалежно не встановлено.
- Rate-limit counters process-local.
- Production Email/Web generation workflows належать наступним фазам.
- Manual GUI checklist неповний; непідтверджені boxes залишаються unchecked.
- Physical native Windows11 acceptance лишається Phase12 gate.

Власник визнав ці ризики такими, що не блокують Phase4 acceptance. Подальші
live calls/розширення implementation scope тут не дозволені. Final docs-only
HEAD проходить обидва CI jobs до merge; actual SHA/run/merge commit — PR5/final
report. Phase5 NOT STARTED і потребує окремого дозволу.
