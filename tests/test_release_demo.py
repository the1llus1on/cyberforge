"""Recreate the versioned demo without touching the normal profile or network."""

import json
import socket
from decimal import Decimal
from pathlib import Path

import pytest

from cyberforge.analytics.contracts import AnalyticsQueryV1
from cyberforge.application.accounts import AccountService
from cyberforge.application.analytics import ScenarioAnalyticsService
from cyberforge.application.email_materials import EmailMaterialService
from cyberforge.application.evaluations import EvaluationService
from cyberforge.application.learner_attempts import LearnerAttemptService
from cyberforge.application.mentor_feedback import MentorFeedbackService
from cyberforge.application.release_demo import CREDENTIALS_NAME, prepare_demo_profile
from cyberforge.application.scenario_integration import ScenarioIntegrationService
from cyberforge.application.scenario_publication import (
    PublicationAccessService,
    ScenarioPublicationService,
)
from cyberforge.application.scenario_readiness import ScenarioReadinessService
from cyberforge.application.scenarios import ScenarioService
from cyberforge.application.web_materials import WebMaterialService
from cyberforge.domain.accounts import ApplicationError
from cyberforge.llm.factory import create_gateway
from cyberforge.persistence.profile import PrivateProfile
from cyberforge.persistence.recovery import ProfileRecovery
from tests.test_analytics import complete


def exercise(container: PrivateProfile):
    with container.acquire():
        with pytest.raises(ApplicationError, match="ще не підготовлено"):
            prepare_demo_profile(container, initialize=False)
        active = prepare_demo_profile(container, initialize=True)
        path = active.root / CREDENTIALS_NAME
        original = path.read_bytes()
        assert prepare_demo_profile(container, initialize=True).root == active.root
        assert original == path.read_bytes()
        credentials = json.loads(original)
        with active.acquire():
            db = ProfileRecovery(active).startup()
            try:
                accounts = AccountService(db)
                gateway = create_gateway()
                emails = EmailMaterialService(
                    ScenarioService(accounts), gateway, demo=True
                )
                integration = ScenarioIntegrationService(
                    WebMaterialService(emails, demo=True)
                )
                access = PublicationAccessService(
                    ScenarioPublicationService(ScenarioReadinessService(integration))
                )
                attempts = LearnerAttemptService(access)
                evaluation = EvaluationService(attempts)
                mentor = MentorFeedbackService(evaluation, gateway)
                results = []
                content = None
                for login, web in (("learner_demo_1", False), ("learner_demo_2", True)):
                    token = accounts.login(login, credentials[login])
                    (lesson,) = attempts.catalog(token)
                    assert not attempts.history(token)
                    _, state = access.content(token, lesson.publication_id)
                    content = (
                        state.web.page.model_dump(exclude={"internal_resource_id"}),
                        tuple(c.criterion_id for c in state.rubric.criteria),
                    )
                    attempt = complete(
                        evaluation, token, lesson.scenario_id, inspect=True, web=web
                    )
                    result = evaluation.evaluate(token, attempt.attempt_id)
                    feedback = mentor.generate(token, attempt.attempt_id)
                    assert feedback.mode == "DETERMINISTIC"
                    results.append((result.path.kind, result.score_percent))
                teacher = accounts.login(
                    "teacher_demo_1", credentials["teacher_demo_1"]
                )
                snapshot = ScenarioAnalyticsService(evaluation).summary(
                    teacher, AnalyticsQueryV1(scenario_id=lesson.scenario_id)
                )
                assert snapshot.metrics.lifecycle.completed == 2
                assert snapshot.quality.selected.verified == 2
                return content, tuple(results), credentials
            finally:
                db.close()


def test_versioned_demo_reproducible_with_private_random_credentials(
    tmp_path, monkeypatch
):
    def blocked(*args, **kwargs):
        pytest.fail("the demo attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    normal = Path(tmp_path / "normal")
    normal.mkdir()
    sentinel = normal / "unchanged.txt"
    sentinel.write_text("normal profile state")
    first_content, first_outcomes, first_keys = exercise(
        PrivateProfile(tmp_path / "first")
    )
    second_content, second_outcomes, second_keys = exercise(
        PrivateProfile(tmp_path / "second")
    )
    assert first_content == second_content
    assert (
        first_outcomes
        == second_outcomes
        == (
            ("SAFE_DECLINE", Decimal("100")),
            ("WEB_VISITED", Decimal("33.33")),
        )
    )
    assert first_keys.keys() == second_keys.keys()
    assert all(first_keys[key] != second_keys[key] for key in first_keys)
    assert sentinel.read_text() == "normal profile state"
