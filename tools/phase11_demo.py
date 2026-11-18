"""Create and measure a fresh isolated offline Analytics demonstration."""

import argparse
import json
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
from uuid import uuid4

from cyberforge.analytics.contracts import AnalyticsQueryV1
from cyberforge.application import analytics
from cyberforge.application.accounts import AccountService
from cyberforge.application.demo import initialize_demo
from cyberforge.application.email_materials import EmailMaterialService
from cyberforge.application.evaluations import EvaluationService
from cyberforge.application.learner_attempts import (
    AttemptEventService,
    LearnerAttemptService,
)
from cyberforge.application.learner_demo import publish_demo_version
from cyberforge.application.mentor_feedback import MentorFeedbackService
from cyberforge.application.scenario_integration import ScenarioIntegrationService
from cyberforge.application.scenario_publication import (
    PublicationAccessService,
    ScenarioPublicationService,
)
from cyberforge.application.scenario_readiness import ScenarioReadinessService
from cyberforge.application.scenarios import ScenarioService
from cyberforge.application.web_materials import WebMaterialService
from cyberforge.groups.service import GroupService
from cyberforge.llm.config import GatewayConfig
from cyberforge.llm.factory import create_gateway
from cyberforge.persistence.database import Database


def exercise(evaluations, learner, scenario, path):
    attempts = evaluations.attempts
    events = AttemptEventService(attempts)
    attempt = attempts.start_or_resume(learner, scenario.id)
    if path == "in_progress":
        return attempt

    def record(surface, action, **values):
        nonlocal attempt
        attempt = events.record(
            learner,
            attempt.attempt_id,
            request_id=uuid4(),
            expected_revision=attempt.revision,
            surface=surface,
            action_id=action,
            **values,
        )

    record("email", "email_opened")
    if path == "abandoned":
        record("system", "abandoned")
        return attempt
    if path == "web":
        _, state = attempts.content(learner, attempt.attempt_id)
        record(
            "transition",
            "open_internal",
            navigation=attempts.access.resolve_internal(
                learner, attempt.publication_id
            ),
            source_message_identifier=state.link.source_message_identifier,
        )
        attempt = events._display_acknowledger(learner, attempt.attempt_id)(
            request_id=uuid4(),
            expected_revision=attempt.revision,
        )
    else:
        if path == "strong":
            record("email", "inspect_sender")
        record("transition", "decline")
    record("system", "completed")
    if path != "pending":
        evaluations.evaluate(learner, attempt.attempt_id)
    return attempt


def populate(accounts, credentials_path, repetitions):
    initialize_demo(accounts, credentials_path)
    credentials = json.loads(credentials_path.read_text(encoding="utf-8"))
    admin = accounts.login("Administrator_demo", credentials["Administrator_demo"])
    teacher = accounts.login("teacher_demo_1", credentials["teacher_demo_1"])
    instructor = accounts.current(teacher)
    learners = tuple(
        accounts.login(f"learner_demo_{i}", credentials[f"learner_demo_{i}"])
        for i in range(1, 5)
    )
    groups = GroupService(accounts)
    first, second = groups.list_groups(admin)
    groups.set_members(
        admin, second.id, (*second.instructors, instructor.id), second.learners
    )

    scenarios = ScenarioService(accounts)
    gateway = create_gateway(GatewayConfig())
    emails = EmailMaterialService(scenarios, gateway, demo=True)
    integration = ScenarioIntegrationService(WebMaterialService(emails, demo=True))
    publications = ScenarioPublicationService(ScenarioReadinessService(integration))
    evaluations = EvaluationService(
        LearnerAttemptService(PublicationAccessService(publications))
    )
    mentor = MentorFeedbackService(evaluations, gateway)
    options = dict(
        topic="Навчальний портал: перевірка повідомлення", difficulty="beginner"
    )
    main = scenarios.create(teacher, options)
    secondary = scenarios.create(
        teacher, options | {"topic": "Практика перевірки відправника"}
    )
    scopes = (first.id, second.id)
    first_publication = publish_demo_version(publications, teacher, main, scopes)
    publish_demo_version(publications, teacher, secondary, scopes)
    for _ in range(repetitions):
        for index, learner in enumerate(learners):
            exercise(
                evaluations, learner, main, ("strong", "web", "decline", "web")[index]
            )
            exercise(
                evaluations,
                learner,
                secondary,
                ("web", "strong", "decline", "strong")[index],
            )
    main = scenarios.create_next_draft(teacher, scenarios.get(teacher, main.id))
    publish_demo_version(publications, teacher, main, scopes)
    for _ in range(repetitions):
        for index, learner in enumerate(learners):
            exercise(
                evaluations,
                learner,
                main,
                ("decline", "strong", "web", "strong")[index],
            )

    exercise(evaluations, learners[0], main, "strong")
    exercise(evaluations, learners[1], main, "pending")
    exercise(evaluations, learners[2], main, "abandoned")
    exercise(evaluations, learners[2], main, "in_progress")
    attempt = exercise(evaluations, learners[3], main, "web")
    mentor.generate(learners[3], attempt.attempt_id)
    learner_id = accounts.current(learners[0]).id
    groups.set_members(
        admin,
        first.id,
        first.instructors,
        tuple(i for i in first.learners if i != learner_id),
    )
    publications.change_grant(
        teacher, first_publication.id, first.id, active=False, expected_revision=1
    )
    return analytics.ScenarioAnalyticsService(evaluations), teacher, main.id


def measure(service, actor, scenario_id, folder):
    query = AnalyticsQueryV1(
        scenario_id=scenario_id, aggregation="ALL_COMPLETED_ATTEMPTS"
    )
    stats = {"integrity": 0.0, "aggregation": 0.0, "validated": 0}

    def measure_call(name, method, *args, **kwargs):
        start = perf_counter()
        try:
            return method(*args, **kwargs)
        finally:
            stats[name] += perf_counter() - start
            if name == "integrity":
                stats["validated"] += 1

    validate = service.evaluations.integrity.validate
    aggregate = analytics.aggregate
    start = perf_counter()
    with (
        patch.object(
            service.evaluations.integrity,
            "validate",
            lambda *a, **k: measure_call("integrity", validate, *a, **k),
        ),
        patch.object(
            analytics,
            "aggregate",
            lambda *a, **k: measure_call("aggregation", aggregate, *a, **k),
        ),
    ):
        summary = service.summary(actor, query)
    print(
        f"Зведення {perf_counter() - start:.3f} с · "
        f"спроби {summary.metrics.lifecycle.total} · "
        f"валідація {stats['integrity']:.3f} с ({stats['validated']}) · "
        f"агрегація {stats['aggregation']:.3f} с"
    )
    operations = (
        (
            "Фільтр і сторінка",
            lambda: service.summary(
                actor,
                query.model_copy(
                    update={
                        "search": "learner_demo",
                        "page": 2,
                        "page_size": 2,
                        "sort": "score",
                    },
                ),
            ),
        ),
        (
            "Експорт CSV",
            lambda: service.export(actor, query, folder / "analytics.csv", "csv"),
        ),
        (
            "Експорт JSON",
            lambda: service.export(actor, query, folder / "analytics.json", "json"),
        ),
    )
    for label, operation in operations:
        start = perf_counter()
        operation()
        print(f"{label} {perf_counter() - start:.3f} с")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Новий демонстраційний каталог")
    parser.add_argument(
        "--repetitions", type=int, default=6, choices=range(1, 21), metavar="1–20"
    )
    parser.add_argument(
        "--measure",
        action="store_true",
        help="Виміряти читання та створити тестові експорти",
    )
    args = parser.parse_args()
    args.directory.mkdir(mode=0o700)
    database = Database(args.directory / "demo.sqlite3")
    try:
        database.upgrade()
        service, teacher, scenario_id = populate(
            AccountService(database),
            args.directory / "credentials.json",
            args.repetitions,
        )
        if args.measure:
            measure(service, teacher, scenario_id, args.directory)
        print(f"Демонстраційний сценарій · ID {scenario_id}")
    finally:
        database.close()


if __name__ == "__main__":
    main()
