"""Synthetic offline demonstration: python -m cyberforge.agents.demo.

Uses the real gateway and scripted MockLLMProvider. Never loads .env or keys.
"""

from cyberforge.agents import (
    AssistantAgent,
    EmailScenarioAgent,
    MentorAgent,
    WebScenarioAgent,
)
from cyberforge.agents.contracts import (
    AggregateV1,
    AssistantInputV1,
    EmailInputV1,
    FactV1,
    MentorInputV1,
    ResultFactsV1,
    WebInputV1,
)
from cyberforge.domain.nist_cues import NistCueId
from cyberforge.domain.scenarios import ScenarioParameters
from cyberforge.llm.config import GatewayConfig, RateLimits
from cyberforge.llm.contracts import Provider, ProviderResponse, ScenarioContextV1
from cyberforge.llm.gateway import LLMGateway
from cyberforge.llm.mock import MockLLMProvider


def email_input() -> EmailInputV1:
    return EmailInputV1(
        synthetic=True,
        scenario_id=1,
        scenario_version=1,
        parameters=ScenarioParameters(
            topic="Перевірка навчального повідомлення",
            difficulty="beginner",
            learning_objective="Перевіряти відправника та посилання",
            nist_cues=(NistCueId.URGENCY,),
        ),
        context=ScenarioContextV1(
            schema_version="scenario-context-v1",
            organization="Навчальна установа Альфа",
            sender_name="Навчальна служба",
            premise="Синтетичне службове повідомлення",
            internal_resource_id="training_notice",
        ),
    )


def email_payload(source: EmailInputV1) -> dict:
    message = dict(
        sender_name=source.context.sender_name,
        sender_address="training@alpha.invalid",
        subject="Навчальне повідомлення",
        body_text="Терміново перевірте навчальне повідомлення.",
    )
    return dict(
        schema_version="email-slots-v1",
        context_token=EmailScenarioAgent.context_token(source),
        internal_resource_id=source.context.internal_resource_id,
        main=message,
        background=[
            dict(message, subject="План навчання", body_text="Навчальні новини.")
        ],
        indicators=["Заклик до термінової дії"],
        claimed_cues=["B.4.4"],
        expected_actions=[
            "inspect_sender",
            "inspect_link",
            "report",
            "decline",
            "open_internal",
        ],
    )


def web_payload(source: WebInputV1) -> dict:
    return dict(
        schema_version="web-slots-v1",
        context_token=WebScenarioAgent.context_token(source),
        internal_resource_id=source.context.internal_resource_id,
        template=source.template,
        tab_title="Навчальне повідомлення",
        display_url="https://alpha.invalid/notice",
        heading="Навчальна установа Альфа",
        body_text="Синтетичне службове повідомлення",
        button_labels=["Закрити"],
        fields=[],
        instructions=["Не вводьте справжні дані."],
        allowed_actions=["inspect_address", "leave", "report"],
        educational_cues=["Перевірте відображувану адресу"],
    )


def fact() -> FactV1:
    return FactV1(
        fact_id="checked_sender",
        observation="Адресу відправника перевірено.",
        explanation="Перевірка відправника допомагає виявляти підозрілі повідомлення.",
        defensive_behavior="Використовуйте незалежний довірений канал.",
        topic="sender_verification",
    )


def explanation_payload() -> dict:
    return dict(
        schema_version="explanation-selection-v1",
        fact_ids=["checked_sender"],
        recommended_topics=["sender_verification"],
        evidence="supplied_facts",
        difficulty_suggestion="keep",
    )


def scripted_gateway(*payloads) -> tuple[LLMGateway, MockLLMProvider]:
    import json

    mock = MockLLMProvider(
        [
            ProviderResponse(text=json.dumps(payload, ensure_ascii=False))
            for payload in payloads
        ]
    )
    return LLMGateway(
        GatewayConfig(
            limits={
                key: RateLimits(tpm=1000000, tpd=1000000)
                for key in ("mock", "mock:mock-v1")
            }
        ),
        {Provider.MOCK: mock},
    ), mock


def main() -> None:
    source = email_input()
    gateway, _ = scripted_gateway(email_payload(source))
    email = EmailScenarioAgent(gateway).run(source)
    assert email.status == "pending_review"
    web_source = WebInputV1(
        **source.model_dump(exclude={"previous", "refinement_scope"}),
        email=email.draft,
        template="notice",
    )
    gateway, _ = scripted_gateway(web_payload(web_source))
    web = WebScenarioAgent(gateway).run(web_source)
    mentor_source = MentorInputV1(
        synthetic=True,
        objective="Перевірка відправника",
        facts=(fact(),),
        permitted_topics=("sender_verification",),
        result=ResultFactsV1(
            status="completed",
            score_percent=100,
            rubric_version="demo-v1",
            web_status="correctly_skipped",
        ),
    )
    assistant_source = AssistantInputV1(
        synthetic=True,
        objective="Перевірка відправника",
        facts=(fact(),),
        permitted_topics=("sender_verification",),
        scenario_version=1,
        aggregate=AggregateV1(attempts=10, completed=10, mean_score=80),
    )
    for agent_type, item in (
        (MentorAgent, mentor_source),
        (AssistantAgent, assistant_source),
    ):
        gateway, _ = scripted_gateway(explanation_payload())
        result = agent_type(gateway).run(item)
        assert result.status == "pending_review"
        print(f"{agent_type.__name__}: {result.status}; публікація заборонена")
    assert web.status == "pending_review"
    print("EmailScenarioAgent / WebScenarioAgent: узгоджені чернетки, pending_review")
    print("MockLLMProvider; мережа та база даних не використовуються.")


if __name__ == "__main__":
    main()
