"""Real migration/schema/transaction integration using immutable source bundles."""

import pytest
from sqlalchemy import text

from cyberforge.application.evaluations import EvaluationService
from cyberforge.application.learner_attempts import LearnerAttemptService
from cyberforge.evaluation.canonical import canonical_bytes
from tests.test_evaluation import bundle, frozen  # noqa: F401
from tests.test_scenario_integration import publication_env  # noqa: F401


def test_production_evaluate_retry_read(bundle, publication_env):  # noqa: F811
    _, evidence, result, feedback, sources = bundle
    e = publication_env
    service = EvaluationService(LearnerAttemptService(e.access))
    token = e.tokens["learner"]
    actual = service.evaluate(token, evidence.attempt.attempt_id)
    assert actual.criteria == result.criteria
    assert actual.score_percent == result.score_percent
    assert canonical_bytes(
        service.evaluate(token, actual.attempt.attempt_id)
    ) == canonical_bytes(actual)
    assert service.read(token, actual.attempt.attempt_id) == actual
    assert service.history(token)[0].result == actual
    with e.database.engine.connect() as c:
        assert not c.exec_driver_sql("PRAGMA foreign_key_check").all()
        assert (
            c.execute(text("SELECT count(*) FROM evaluation_results")).scalar_one() == 1
        )


def test_production_feedback(bundle, publication_env):  # noqa: F811
    from cyberforge.application.mentor_feedback import MentorFeedbackService
    from cyberforge.llm.factory import create_gateway

    _, evidence, _, expected, _ = bundle
    ev = EvaluationService(LearnerAttemptService(publication_env.access))
    service = MentorFeedbackService(ev, create_gateway())
    token, aid = publication_env.tokens["learner"], evidence.attempt.attempt_id
    actual = service.generate(token, aid)
    assert actual.explanation == expected.explanation
    assert actual.facts == expected.facts
    assert actual.mode == "DETERMINISTIC"
    assert service.generate(token, aid) == actual
    assert service.read(token, aid) == actual


def test_prospective_publication_rejects_nonnumerical_paths(publication_env):  # noqa: F811
    from cyberforge.domain.accounts import ApplicationError
    from cyberforge.scenario_integration.contracts import criterion
    from tests.test_scenario_integration import confirm, link, materials

    e = publication_env
    materials(e)
    link(e)
    for revision, criteria in enumerate(
        (
            (criterion("transition.decision"),),
            (criterion("transition.safe_decline", applicability="web_not_visited"),),
        )
    ):
        e.integration.save_rubric(
            e.token, e.scenario, criteria, expected_revision=revision
        )
        report = e.readiness.evaluate(
            e.token, e.scenario, selected_group_ids=(e.group.id,)
        )
        assert not report.technical_ready
        assert (
            next(
                c.status
                for c in report.checks
                if c.check_id == "numerical_completion_paths"
            )
            == "BLOCKED"
        )
        with pytest.raises(ApplicationError):
            confirm(e, report)
        with pytest.raises(ApplicationError):
            e.publications.publish(e.token, e.scenario, confirmation_id="invalid")
