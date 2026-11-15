"""Explicit deterministic mail demonstration, separate from normal configuration."""

import json

from cyberforge.agents.contracts import EmailInputV1
from cyberforge.agents.specialized import EmailScenarioAgent
from cyberforge.llm.config import GatewayConfig, RateLimits
from cyberforge.llm.contracts import Provider, ProviderResponse
from cyberforge.llm.gateway import LLMGateway
from cyberforge.llm.mock import MockLLMProvider


def demo_gateway(source: EmailInputV1) -> LLMGateway:
    """Script accepted slots for the active source; no .env, clients or fixtures."""
    message = dict(
        sender_name=source.context.sender_name,
        sender_address="notice@training.invalid",
        subject=source.parameters.topic[:250],
        body_text=(
            f"Вітаємо!\n\n{source.context.organization} запрошує перевірити навчальне "
            "повідомлення. Перевірте відправника та внутрішнє "
            "призначення посилання.\n\n"
            "Це синтетичний приклад. Справжні облікові дані не потрібні."
            + (f"\n\nІнструкція демо: {source.refinement}" if source.refinement else "")
        ),
    )
    payload = dict(
        schema_version="email-slots-v1",
        context_token=EmailScenarioAgent.context_token(source),
        internal_resource_id=source.context.internal_resource_id,
        main=message,
        background=[
            dict(
                sender_name="Навчальна бібліотека",
                sender_address="library@training.invalid",
                subject="Нові навчальні матеріали",
                body_text="Матеріали для самостійного навчання вже підготовлено.",
            ),
            dict(
                sender_name="Координатор навчання",
                sender_address="course@training.invalid",
                subject="Розклад занять",
                body_text="Наступне синтетичне заняття присвячене безпечним рішенням.",
            ),
        ],
        indicators=["Синтетичний приклад для огляду викладачем"],
        claimed_cues=[],
        expected_actions=[
            "inspect_sender",
            "inspect_link",
            "report",
            "decline",
            "open_internal",
        ],
    )
    return LLMGateway(
        GatewayConfig(
            limits={
                key: RateLimits(tpm=1000000, tpd=1000000)
                for key in ("mock", "mock:mock-v1")
            }
        ),
        {
            Provider.MOCK: MockLLMProvider(
                [ProviderResponse(text=json.dumps(payload, ensure_ascii=False))]
            )
        },
    )
