# Phase 4 — LLM Integration: перевірка власником

Статус: **REVIEW**, не ACCEPTED. Архітектура ADR-0004 погоджена окремо;
прийняття реалізації ще очікується. Phase 5 не розпочато. Live calls не виконано.

## Вимоги та межі

SRS §§10.1–10.8/11.1/23 Phase4: provider-neutral LLMGateway, Gemini Interactions,
Groq/Mock, text/structured contracts, retries/errors/usage та synthetic privacy.
Погоджений нормативний diff обмежено §10.2. Scenario ownership/RBAC/versioning,
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
- [ ] Власник явно приймає Phase4 (поки не підтверджено).

Автоматичні докази наведено в DEVELOPMENT_LOG та final PR checks. Цей checklist
не заповнюється автоматично й не заявляє невиконаних owner перевірок.
