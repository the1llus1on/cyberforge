# Phase 12 — Провайдери та політика хмарних порад

У стандартному приватному Windows-профілі Administrator відкриває
«Адміністрування → Провайдери». Збереження маскованого ключа, його
вилучення, синтетична перевірка з’єднання й активація provider/model
є окремими діями. Початковий режим — Mock. Активний ключ недоступний
для читання в UI. Налаштування без ключів лежать поза SQLite. Generic
credentials у Windows Credential Manager мають окремий namespace
`CyberForge/stable/<profile-id>/<provider>`. Окремі Windows-логіни мають
власні vault. Заміна або вилучення ключа вимикає активний режим цього
провайдера та робить попередню перевірку його ревізії непридатною.
Явна development `.env` конфігурація лишається авторитетною для
development-конструкторів за наявності налаштованого cloud route.
Пакет Windows використовує приватні налаштування.

## Керована організацією політика

Машинний корінь довіри — 64-bit Windows registry key
`HKLM\SOFTWARE\Policies\CyberForge\TopicAdvisoryV1`. Розгортає та змінює
його уповноважена організацією служба через Group Policy або контрольовану
локальну процедуру. Власник ключа — SYSTEM або локальна група Administrators.
Ефективні ACE для інших SID дозволяють тільки читання. CyberForge читає
DACL і актуальне значення з того самого handle при кожній перевірці. За
відсутності доступного й довіреного запису лишається офлайн-порада.
[Microsoft Registry Key Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/sysinfo/registry-key-security-and-access-rights).

Значення типу REG_SZ має назву `<profile-id>-<scope-digest>`.
Точний профіль і ревізія ключа видимі адміністратору в налаштуваннях.
Код обсягу доступний викладачу під час підготовки офлайн-поради. Обсяг
охоплює нормалізовані фільтри A11, які змінюють вибір джерел. Ідентичність
акаунта й перевірка його реальної privacy конфігурації підтверджуються в
уповноваженій процедурі організації, включно з тим, як схвалений ключ
прив'язано до акаунта. Запис у Git чи перенесення з SQLite не
підтверджують походження. Час дії визначено за UTC. У разі відкликання
встановіть `revoked: true` або приберіть значення.

Приклад структури з синтетичними ідентифікаторами:

```json
{
  "schema_version": "advisory-policy-evidence-v1",
  "purpose": "instructor-topic-advisory",
  "data_class": "real",
  "scope_digest": "<64 hex characters from Analytics preview>",
  "provider_profile": {
    "profile_id": "<profile id from Administrator settings>",
    "credential_revision": "<active key revision from Administrator settings>",
    "provider": "groq",
    "account_reference": "example-approved-account",
    "endpoint": "https://api.groq.com/openai/v1/chat/completions",
    "model": "openai/gpt-oss-120b",
    "mode": "topic-only-stateless-v1"
  },
  "organization_decision": "example-decision-reference",
  "provider_privacy_review": "example-account-review-reference",
  "responsible_party": "example-governance-role",
  "assessed_at": "2026-11-18T00:00:00Z",
  "expires_at": "2026-11-19T00:00:00Z",
  "revoked": false,
  "residual_linkability_accepted": true
}
```

Gemini використовує `https://generativelanguage.googleapis.com/v1/interactions`.
Відправлення містить форму topic-only, фіксовані інструкції/схему та
параметри протоколу. Акаунт, роль, ідентифікатори та відбитки джерел
залишаються локальними. Мережевий одержувач неминуче бачить свій ключ
автентифікації та звичайні параметри з’єднання. Залишкова можливість
зв’язування теми з особою показується перед кожним підтвердженням.
Зміна фільтра, політики, дозволу, версії джерела або ключа вимагає
нового preview. Зміна або скасування після dispatch прибирає результат
із UI за повторної перевірки. Необроблені відповіді провайдера не
відображаються. Український текст вибирається із замкненого каталогу.

Транспортні тести використовують контрольовані mock responses для Groq
і Gemini. Реальна перевірка акаунта потребує окремого погодження та
компетенції відповідальних осіб.
