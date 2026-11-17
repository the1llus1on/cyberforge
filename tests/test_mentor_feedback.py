"""Provider-neutral feedback privacy and deterministic fallback, no live API."""

import json

import pytest
from sqlalchemy import event, text

from cyberforge.application.evaluations import EvaluationFailure
from cyberforge.application.mentor_feedback import MentorFeedbackService
from cyberforge.llm.config import GatewayConfig
from cyberforge.llm.contracts import (
    ErrorCategory,
    GenerationError,
    Provider,
    ProviderResponse,
)
from cyberforge.llm.gateway import LLMGateway
from cyberforge.llm.mock import MockLLMProvider
from tests.test_evaluation import frozen  # noqa: F401
from tests.test_evaluation_persistence import runtime  # noqa: F401
from tests.test_scenario_integration import publication_env  # noqa: F401


class RecordingMock(MockLLMProvider):
    def generate(self, request, schema):
        self.request = request
        return super().generate(request, schema)


def cloud_gateway(response):
    provider = RecordingMock([response])
    gateway = LLMGateway(
        GatewayConfig(
            provider=Provider.GROQ, model="openai/gpt-oss-120b", max_retries=0
        ),
        {Provider.GROQ: provider},
    )
    return gateway, provider


@pytest.mark.parametrize(
    "mode",
    [
        "valid",
        "timeout",
        "unavailable",
        "invalid_json",
        "fact",
        "topic",
        "score",
        "claim",
    ],
)
def test_cloud_selection_and_fallback(runtime, mode):  # noqa: F811
    e = runtime
    candidate = dict(
        schema_version="explanation-selection-v1",
        fact_ids=["email_sender_met"],
        recommended_topics=["sender_verification"],
        evidence="supplied_facts",
        difficulty_suggestion="keep",
    )
    if mode == "fact":
        candidate["fact_ids"] = ["unsupported_fact"]
    if mode == "topic":
        candidate["recommended_topics"] = ["unapproved_topic"]
    if mode == "score":
        candidate["score_percent"] = 99
    if mode == "claim":
        candidate["explanation"] = "Unsupported causal judgment"
    response = (
        GenerationError(ErrorCategory.TIMEOUT)
        if mode == "timeout"
        else GenerationError(ErrorCategory.UNAVAILABLE)
        if mode == "unavailable"
        else ProviderResponse(
            text="{invalid" if mode == "invalid_json" else json.dumps(candidate),
            actual_model="openai/gpt-oss-120b",
        )
    )
    gateway, provider = cloud_gateway(response)
    service = MentorFeedbackService(e.ev, gateway)
    result = e.ev.evaluate(e.learner, e.aid)
    feedback = service.generate(e.learner, e.aid)
    assert provider.calls == 1
    assert feedback.mode == ("MODEL_SELECTION" if mode == "valid" else "DETERMINISTIC")
    if mode != "valid":
        assert feedback.fallback_reason == (
            "PROVIDER_FAILURE"
            if mode in {"timeout", "unavailable"}
            else "INVALID_SELECTION"
        )
    assert service.generate(e.learner, e.aid) == feedback and provider.calls == 1
    assert e.ev.read(e.learner, e.aid) == result
    prompt = str(provider.request.prompt)
    for forbidden in (
        str(e.aid),
        str(result.result_id),
        result.source.rubric_id,
        result.source.manifest_digest,
        result.events_digest,
        e.password,
        "attempt_id",
        "publication_id",
        "component_id",
        "operation_digest",
        e.evidence.attempt.scenario_name,
    ):
        assert forbidden not in prompt
    assert "rubric-revision-1" in prompt
    assert feedback.explanation.result.score_percent == float(result.score_percent)


def test_missing_cloud_key_falls_back_offline(runtime):  # noqa: F811
    from cyberforge.llm.factory import create_gateway

    service = MentorFeedbackService(
        runtime.ev,
        create_gateway(
            GatewayConfig(
                provider=Provider.GROQ, model="openai/gpt-oss-120b", max_retries=0
            )
        ),
    )
    value = service.generate(runtime.learner, runtime.aid)
    assert value.mode == "DETERMINISTIC" and value.fallback_reason == "PROVIDER_FAILURE"


def test_deactivation_during_provider_call_denies_feedback_commit(runtime):  # noqa: F811
    e = runtime
    gateway, provider = cloud_gateway(GenerationError(ErrorCategory.TIMEOUT))
    original = provider.generate

    def generate(*args):
        response = None
        try:
            response = original(*args)
        finally:
            with e.accounts.transaction(write=True) as db:
                db.execute(
                    text("UPDATE users SET active=0 WHERE id=:id"),
                    dict(id=e.evidence.attempt.learner_id),
                )
        return response

    provider.generate = generate
    with pytest.raises(EvaluationFailure) as exc:
        MentorFeedbackService(e.ev, gateway).generate(e.learner, e.aid)
    assert exc.value.error.code == "ACCESS_DENIED"
    with e.database.engine.connect() as c:
        assert (
            c.exec_driver_sql("SELECT count(*) FROM evaluation_results").scalar_one()
            == 1
        )
        assert (
            c.exec_driver_sql("SELECT count(*) FROM mentor_feedback").scalar_one() == 0
        )


def test_feedback_storage_failure_preserves_score(runtime):  # noqa: F811
    e = runtime
    result = e.ev.evaluate(e.learner, e.aid)

    def fail(conn, cursor, sql, params, context, many):
        if sql.startswith("INSERT INTO mentor_feedback"):
            raise RuntimeError("forced feedback failure")

    event.listen(e.database.engine, "after_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError):
            e.mentor.generate(e.learner, e.aid)
    finally:
        event.remove(e.database.engine, "after_cursor_execute", fail)
    assert e.ev.read(e.learner, e.aid) == result
    assert e.mentor.read(e.learner, e.aid) is None
    assert e.mentor.generate(e.learner, e.aid).result_id == result.result_id


@pytest.mark.parametrize("mutation", ["payload", "projection", "digest", "time"])
def test_feedback_corruption_preserves_valid_result(runtime, mutation):  # noqa: F811
    e = runtime
    value = e.mentor.generate(e.learner, e.aid)
    result = e.ev.read(e.learner, e.aid)
    with e.database.engine.begin() as c:
        c.exec_driver_sql("DROP TRIGGER mentor_feedback_no_update")
        sql = {
            "payload": "feedback_json='{}'",
            "projection": "mode='MODEL_SELECTION'",
            "digest": "feedback_digest='bad'",
            "time": "created_at='2020-01-01T00:00:00.000000Z'",
        }[mutation]
        c.exec_driver_sql("UPDATE mentor_feedback SET " + sql)
    for call in (e.mentor.read, e.mentor.generate):
        with pytest.raises(EvaluationFailure) as exc:
            call(e.learner, e.aid)
        assert exc.value.error.code == "STORED_FEEDBACK_INTEGRITY_ERROR"
    assert e.ev.read(e.learner, e.aid) == result
    with e.database.engine.connect() as c:
        assert c.exec_driver_sql("SELECT id FROM mentor_feedback").scalar_one() == str(
            value.feedback_id
        )
