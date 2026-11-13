"Four provider-neutral specialists with deterministic grounding gates."

from cyberforge.agents.contracts import (
    AssistantInputV1,
    EmailDraftV2,
    EmailInputV1,
    EmailSlotsV1,
    ExplanationSelectionV1,
    ExplanationV1,
    MentorInputV1,
    WebDraftV2,
    WebInputV1,
    WebSlotsV1,
    source_provenance,
)
from cyberforge.agents.workflow import SpecializedAgent
from cyberforge.llm.contracts import EmailArtifactV1, WebArtifactV1

RECOMMENDATIONS = {
    "sender_verification": (
        "Перевіряйте адресу відправника через незалежний довірений канал."
    ),
    "link_inspection": (
        "Перевіряйте адресу посилання перед переходом; за сумніву "
        "відмовтеся від переходу."
    ),
    "reporting": "Повідомляйте про підозрілі повідомлення за затвердженою процедурою.",
    "data_protection": (
        "Не вводьте справжні облікові дані в навчальні форми чи на "
        "підозрілих сторінках."
    ),
}


class EmailScenarioAgent(SpecializedAgent):
    kind = "email"
    input_type = EmailInputV1
    slots_type = EmailSlotsV1

    def validate_output(
        self, source: EmailInputV1, candidate: EmailSlotsV1
    ) -> EmailDraftV2:
        if (
            candidate.context_token != self.context_token(source)
            or candidate.internal_resource_id != source.context.internal_resource_id
            or candidate.main.sender_name != source.context.sender_name
            or not set(candidate.claimed_cues) <= set(source.parameters.nist_cues)
        ):
            raise ValueError("email_consistency")
        return EmailDraftV2(
            artifact=EmailArtifactV1(
                schema_version="email-artifact-v1",
                context=source.context,
                subject=candidate.main.subject,
                body_text=candidate.main.body_text,
            ),
            slots=candidate,
            parameters=source.parameters,
            scenario_id=source.scenario_id,
            scenario_version=source.scenario_version,
            selected_cues=source.parameters.nist_cues,
            provenance=source_provenance(source),
        )


class WebScenarioAgent(SpecializedAgent):
    kind = "web"
    input_type = WebInputV1
    slots_type = WebSlotsV1

    def validate_output(self, source: WebInputV1, candidate: WebSlotsV1) -> WebDraftV2:
        if (
            candidate.context_token != self.context_token(source)
            or candidate.internal_resource_id != source.context.internal_resource_id
            or candidate.internal_resource_id != source.email.slots.internal_resource_id
            or candidate.template != source.template
        ):
            raise ValueError("web_consistency")
        return WebDraftV2(
            artifact=WebArtifactV1(
                schema_version="web-artifact-v1",
                context=source.context,
                heading=candidate.heading,
                body_text=candidate.body_text,
                action_label=candidate.button_labels[0],
            ),
            slots=candidate,
            scenario_id=source.scenario_id,
            scenario_version=source.scenario_version,
            provenance=source_provenance(source, web=True),
        )


def grounded_explanation(source, candidate: ExplanationSelectionV1) -> ExplanationV1:
    facts = {fact.fact_id: fact for fact in source.facts}
    insufficient = not facts or (
        isinstance(source, AssistantInputV1) and source.aggregate.completed == 0
    )
    if (
        len(set(candidate.fact_ids)) != len(candidate.fact_ids)
        or not set(candidate.fact_ids) <= facts.keys()
        or not set(candidate.recommended_topics) <= set(source.permitted_topics)
        or (candidate.evidence == "insufficient") != insufficient
        or (facts and not candidate.fact_ids and not insufficient)
        or (insufficient and candidate.difficulty_suggestion != "keep")
    ):
        raise ValueError("unsupported_evidence")
    limitations = [
        (
            "AI обирає лише надані пояснення; причинні та психологічні "
            "висновки не встановлюються."
        )
    ]
    if insufficient:
        limitations.append("Недостатньо даних для висновків про результати навчання.")
    result = source.result if isinstance(source, MentorInputV1) else None
    if result:
        if result.status == "no_result":
            limitations.append("Немає записаного результату; оцінка відсутня.")
        elif result.status == "incomplete":
            limitations.append("Спроба незавершена; підсумкова оцінка відсутня.")
        if result.web_status == "correctly_skipped":
            limitations.append(
                "Правильне завершення без переходу до Web не є автоматичною помилкою."
            )
    return ExplanationV1(
        selected_facts=tuple(facts[key] for key in candidate.fact_ids),
        recommendations=tuple(
            RECOMMENDATIONS[key] for key in candidate.recommended_topics
        ),
        limitations=tuple(limitations),
        result=result,
        aggregate=source.aggregate if isinstance(source, AssistantInputV1) else None,
        difficulty_suggestion=candidate.difficulty_suggestion,
    )


class MentorAgent(SpecializedAgent):
    kind = "mentor"
    input_type = MentorInputV1
    slots_type = ExplanationSelectionV1

    def validate_output(
        self, source: MentorInputV1, candidate: ExplanationSelectionV1
    ) -> ExplanationV1:
        return grounded_explanation(source, candidate)


class AssistantAgent(SpecializedAgent):
    kind = "assistant"
    input_type = AssistantInputV1
    slots_type = ExplanationSelectionV1

    def validate_output(
        self, source: AssistantInputV1, candidate: ExplanationSelectionV1
    ) -> ExplanationV1:
        return grounded_explanation(source, candidate)
