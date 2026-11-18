"""Local instructor advisory from verified aggregate criterion outcomes."""

from cyberforge.evaluation.facts import RECOMMENDATIONS

TOPIC_BY_CRITERION = {
    "email.sender": "sender_verification",
    "email.link": "link_inspection",
    "email.report": "reporting",
    "transition.safe_decline": "data_protection",
    "web.address": "link_inspection",
    "web.report": "reporting",
    "web.leave": "data_protection",
}


class InstructorRecommendationsService:
    @staticmethod
    def from_aggregates(metrics, quality, criteria):
        messages = []
        for series in criteria:
            topic = TOPIC_BY_CRITERION.get(series.key.criterion_id)
            if topic and series.not_met:
                messages.append(
                    f"Версія {series.key.scenario_version}, "
                    f"рубрика {series.key.rubric_revision}. "
                    f"«{series.label}» не виконано у {series.not_met} із "
                    f"{series.met_rate.denominator} застосовних результатів. "
                    f"{RECOMMENDATIONS[topic]}"
                )
        if not messages:
            messages.append(
                "Перегляньте з учнями способи перевірки відправника, посилань "
                "та повідомлення про підозрілі звернення."
            )
        if quality.selected.verified == 0:
            messages.insert(0, "Перевірених результатів недостатньо для висновків.")
        if quality.selected.total > quality.selected.verified:
            messages.insert(0, "Частина вибраних спроб не має перевірених результатів.")
        if (
            len({series.key.publication_id for series in criteria}) > 1
            or metrics.scored_versions > 1
        ):
            messages.insert(
                0,
                "Вибірка містить різні версії. "
                "Переглядайте критерії окремо за версіями.",
            )
        return tuple(messages[:12])
