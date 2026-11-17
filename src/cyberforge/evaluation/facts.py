"educational-facts-v1: local fixed facts; no model or personal-data input."

from types import MappingProxyType

from cyberforge.agents.contracts import ExplanationV1, FactV1, ResultFactsV1
from cyberforge.agents.specialized import RECOMMENDATIONS as ACCEPTED_RECOMMENDATIONS

RECOMMENDATIONS = MappingProxyType(dict(ACCEPTED_RECOMMENDATIONS))

TOPICS = ("sender_verification", "link_inspection", "reporting", "data_protection")
OBJECTIVE = "Пояснити зафіксовані навчальні дії та безпечні способи перевірки."
LIMIT = (
    "AI обирає лише надані пояснення; причинні та "
    "психологічні висновки не встановлюються."
)
UNSCORABLE = (
    "Для цього завершеного шляху немає застосовних числових "
    "критеріїв; оцінка відсутня, це не нуль."
)


def _fact(identifier, observation, explanation, topic):
    return FactV1(
        fact_id=identifier,
        observation=observation,
        explanation=explanation,
        defensive_behavior=RECOMMENDATIONS[topic],
        topic=topic,
    )


def _catalogue():
    values = {}
    entries = (
        (
            "email_sender",
            "sender_verification",
            "перевірку відправника листа",
            "перевірки відправника листа",
        ),
        (
            "email_link",
            "link_inspection",
            "перевірку навчального посилання",
            "перевірки навчального посилання",
        ),
        ("email_report", "reporting", "повідомлення про лист", "повідомлення про лист"),
        (
            "web_address",
            "link_inspection",
            "перевірку адреси сайту",
            "перевірки адреси сайту",
        ),
        (
            "web_leave",
            "link_inspection",
            "дію виходу зі сторінки",
            "виходу зі сторінки",
        ),
        ("web_report", "reporting", "повідомлення про сайт", "повідомлення про сайт"),
    )
    for stem, topic, positive, negative in entries:
        values[stem + "_met"] = _fact(
            stem + "_met",
            f"Зафіксовано {positive}.",
            "Цей факт підтверджує записану дію, а не правильне розпізнавання загрози.",
            topic,
        )
        values[stem + "_not_met"] = _fact(
            stem + "_not_met",
            f"У записі спроби немає події {negative}.",
            (
                "Відсутність події описує запис цієї спроби й не "
                "встановлює причин поведінки."
            ),
            topic,
        )
    for stem, suffix, observation, explanation, topic in (
        (
            "transition_safe_decline",
            "met",
            "Зафіксовано завершення з відмовою від переходу без відвідування Web.",
            "Критерій підтверджується фінальною відмовою та завершенням без Web.",
            "link_inspection",
        ),
        (
            "transition_safe_decline",
            "not_met",
            "Спробу завершено з відвідуванням Web; відмова не є фінальним шляхом.",
            (
                "Перехід до Web не підтверджує фінальну відмову від "
                "переходу, незалежно від попередніх рішень."
            ),
            "link_inspection",
        ),
    ):
        identifier = stem + "_" + suffix
        values[identifier] = _fact(identifier, observation, explanation, topic)
    for stem in ("transition_safe_decline", "web_address", "web_leave", "web_report"):
        identifier = stem + "_not_applicable"
        values[identifier] = _fact(
            identifier,
            "Критерій не застосовується до фактичного шляху цієї спроби.",
            "Числове значення відсутнє; вагу критерію виключено з обох сум.",
            "reporting" if stem == "web_report" else "link_inspection",
        )
    for identifier, observation, explanation, topic in (
        (
            "transition_decision_decline",
            "Фінальне рішення про перехід — відмова.",
            "Це опис рішення без окремої числової оцінки.",
            "link_inspection",
        ),
        (
            "transition_decision_open_internal",
            "Фінальне рішення про перехід — внутрішній перехід.",
            "Це опис рішення без окремої числової оцінки.",
            "link_inspection",
        ),
        (
            "transition_decision_reversed",
            "Після відмови зафіксовано внутрішній перехід.",
            "Попередня відмова не є доказом фінального завершення без Web.",
            "link_inspection",
        ),
        (
            "web_confirm_observed",
            "Зафіксовано дію підтвердження на навчальній сторінці.",
            "Сам факт цієї дії не встановлює критичної помилки.",
            "data_protection",
        ),
        (
            "web_submit_synthetic_observed",
            "Зафіксовано дію надсилання синтетичної навчальної форми.",
            (
                "Подія не містить значень полів і не доводить "
                "передавання справжніх облікових даних."
            ),
            "data_protection",
        ),
        (
            "critical_policy_not_configured",
            "Правила критичних порушень для цієї публікації не налаштовано.",
            "Це не доводить відсутності порушень; штрафи не застосовуються.",
            "data_protection",
        ),
        (
            "evaluation_unscorable",
            "Для цього завершеного шляху немає застосовних числових критеріїв.",
            "Підсумкова оцінка відсутня; це не нульова оцінка.",
            "data_protection",
        ),
        (
            "evidence_interpretation_limit",
            "Запис спроби містить факти дозволених дій.",
            (
                "Ці дані не встановлюють психологічних причин або "
                "правильності інтерпретації загрози."
            ),
            "data_protection",
        ),
    ):
        values[identifier] = _fact(identifier, observation, explanation, topic)
    return tuple(values.values())


CATALOGUE = _catalogue()


def fact(identifier):
    for value in CATALOGUE:
        if value.fact_id == identifier:
            return value
    raise ValueError("unknown_fact")


def project_facts(result):
    "Pure projection from an already validated result; never raw event text."
    from .canonical import canonical_bytes
    from .contracts import EvaluationResultV1

    result = EvaluationResultV1.model_validate_json(canonical_bytes(result))
    ids = []
    for c in result.criteria:
        if c.outcome != "DESCRIPTIVE":
            ids.append(
                c.criterion.criterion_id.replace(".", "_") + "_" + c.outcome.lower()
            )
    if any(c.outcome == "DESCRIPTIVE" for c in result.criteria):
        ids.append("transition_decision_" + result.transition.final_action_id)
        if (
            len(result.transition.event_refs) > 1
            and result.transition.final_action_id == "open_internal"
        ):
            ids.append("transition_decision_reversed")
    actions = {o.action_id for o in result.critical_observations}
    ids.extend(
        "web_" + a + "_observed"
        for a in ("confirm", "submit_synthetic")
        if a in actions
    )
    ids.append("critical_policy_not_configured")
    if result.status == "UNSCORABLE":
        ids.append("evaluation_unscorable")
    ids.append("evidence_interpretation_limit")
    facts = tuple(fact(i) for i in ids)
    return facts, tuple(t for t in TOPICS if any(f.topic == t for f in facts))


def deterministic_explanation(result):
    facts, topics = project_facts(result)
    summary = None
    limitations = [LIMIT]
    if result.status == "SCORED":
        summary = ResultFactsV1(
            status="completed",
            score_percent=float(result.score_percent),
            rubric_version=result.source.rubric_id,
            web_status="correctly_skipped"
            if result.path.kind == "SAFE_DECLINE"
            else "visited",
        )
        if result.path.kind == "SAFE_DECLINE":
            limitations.append(
                "Правильне завершення без переходу до Web не є автоматичною помилкою."
            )
    else:
        limitations.append(UNSCORABLE)
    return ExplanationV1(
        selected_facts=facts,
        recommendations=tuple(RECOMMENDATIONS[t] for t in topics),
        limitations=tuple(limitations),
        result=summary,
        aggregate=None,
        difficulty_suggestion="keep",
        decision_maker="instructor",
    )


def validate_feedback(value):
    from .validation import require

    require(value.objective == OBJECTIVE, "untrusted_objective")
    require(
        len({f.fact_id for f in value.facts}) == len(value.facts)
        and all(f == fact(f.fact_id) for f in value.facts),
        "unsupported_fact",
    )
    topics = tuple(t for t in TOPICS if any(f.topic == t for f in value.facts))
    require(value.permitted_topics == topics, "feedback_topics")
    e = value.explanation
    require(
        len({f.fact_id for f in e.selected_facts}) == len(e.selected_facts)
        and all(f in value.facts for f in e.selected_facts),
        "unsupported_selected_fact",
    )
    require(not value.facts or bool(e.selected_facts), "missing_selected_fact")
    require(
        e.aggregate is None
        and LIMIT in e.limitations
        and len(set(e.recommendations)) == len(e.recommendations)
        and all(
            r in tuple(RECOMMENDATIONS[t] for t in topics) for r in e.recommendations
        ),
        "feedback_grounding",
    )
    require(
        (value.evaluation_status == "SCORED") == (e.result is not None),
        "feedback_result_status",
    )
    expected_limits = [LIMIT]
    if value.evaluation_status == "UNSCORABLE":
        expected_limits.append(UNSCORABLE)
    elif e.result is not None and e.result.web_status == "correctly_skipped":
        expected_limits.append(
            "Правильне завершення без переходу до Web не є автоматичною помилкою."
        )
    require(e.limitations == tuple(expected_limits), "unsupported_limitations")
    if value.mode == "DETERMINISTIC":
        require(
            value.provider is None
            and value.model is None
            and value.fallback_reason is not None
            and e.selected_facts == value.facts
            and e.recommendations == tuple(RECOMMENDATIONS[t] for t in topics)
            and e.difficulty_suggestion == "keep",
            "fallback_provenance",
        )
    else:
        require(
            value.provider is not None
            and value.model is not None
            and value.fallback_reason is None
            and 1 <= len(value.model) <= 128
            and all(c.isalnum() or c in "/._-" for c in value.model),
            "model_provenance",
        )
    if value.evaluation_status == "UNSCORABLE":
        require(
            value.mode == "DETERMINISTIC"
            and value.fallback_reason == "UNSCORABLE"
            and UNSCORABLE in e.limitations,
            "unscorable_feedback",
        )
    else:
        require(
            value.fallback_reason != "UNSCORABLE" and e.result.status == "completed",
            "scored_feedback",
        )


def validate_feedback_against_result(value, result):
    from .canonical import canonical_bytes
    from .contracts import LocalMentorFeedbackV1

    value = LocalMentorFeedbackV1.model_validate_json(canonical_bytes(value))
    from .validation import require

    require(
        (
            value.result_id,
            value.result_digest,
            value.evidence_digest,
            value.evaluation_status,
        )
        == (
            result.result_id,
            result.result_digest,
            result.evidence_digest,
            result.status,
        ),
        "feedback_result_binding",
    )
    require(
        (value.facts, value.permitted_topics) == project_facts(result),
        "feedback_fact_projection",
    )
    expected = deterministic_explanation(result)
    require(
        value.explanation.result == expected.result
        and value.explanation.limitations == expected.limitations,
        "feedback_summary_limitations",
    )
    if value.mode == "DETERMINISTIC":
        require(value.explanation == expected, "deterministic_feedback")
