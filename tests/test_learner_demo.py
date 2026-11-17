"""Explicit fresh offline demo publication without cloud access or overwrites."""

import json
import socket

import pytest

from cyberforge.application.accounts import AccountService
from cyberforge.application.demo import initialize_demo
from cyberforge.application.email_materials import EmailMaterialService
from cyberforge.application.learner_attempts import LearnerAttemptService
from cyberforge.application.learner_demo import prepare_publication
from cyberforge.application.scenario_integration import ScenarioIntegrationService
from cyberforge.application.scenario_publication import (
    PublicationAccessService,
    ScenarioPublicationService,
)
from cyberforge.application.scenario_readiness import ScenarioReadinessService
from cyberforge.application.scenarios import ScenarioService
from cyberforge.application.web_materials import WebMaterialService
from cyberforge.llm.factory import create_gateway
from cyberforge.main import main
from cyberforge.persistence.database import Database


def test_offline_demo_publishes_through_services_and_preserves_credentials(
    tmp_path, monkeypatch
):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network in Phase9 demo")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    database = Database(tmp_path / "fresh.sqlite3")
    try:
        database.upgrade()
        accounts = AccountService(database)
        credentials = tmp_path / "credentials.json"
        assert initialize_demo(accounts, credentials)
        before = credentials.read_bytes()
        publication = prepare_publication(accounts, credentials)
        assert credentials.read_bytes() == before
        assert not initialize_demo(accounts, credentials)
        password = json.loads(before)["learner_demo_1"]
        token = accounts.login("learner_demo_1", password)
        integration = ScenarioIntegrationService(
            WebMaterialService(
                EmailMaterialService(
                    ScenarioService(accounts), create_gateway(), demo=True
                ),
                demo=True,
            )
        )
        attempts = LearnerAttemptService(
            PublicationAccessService(
                ScenarioPublicationService(ScenarioReadinessService(integration))
            )
        )
        _, state = attempts.access.content(token, publication.id)
        actions = {
            a.id for c in state.web.page.components for a in getattr(c, "actions", ())
        }
        assert actions == {
            "inspect_address",
            "report",
            "leave",
            "confirm",
            "submit_synthetic",
        }
        assert len(attempts.catalog(token)) == 1
        assert not attempts.history(token)
        exercise = attempts.catalog(token)[0]
        assert (
            attempts.start_or_resume(token, exercise.scenario_id).publication_id
            == publication.id
        )
    finally:
        database.close()


def test_demo_cli_refuses_existing_database_before_opening(tmp_path):
    database = tmp_path / "existing.sqlite3"
    database.write_bytes(b"owner data sentinel")
    with pytest.raises(SystemExit):
        main(
            [
                "--init-demo",
                "--learner-demo",
                "--database",
                str(database),
                "--credentials-file",
                str(tmp_path / "new-credentials.json"),
            ]
        )
    assert database.read_bytes() == b"owner data sentinel"
    assert not (tmp_path / "new-credentials.json").exists()
